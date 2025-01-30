import os
import logging
import requests
from typing import List, Optional, Dict

from data.cache import get_cache
from data.models import (
    Price,
    PriceResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyNews,
    CompanyNewsResponse,
)
from data.connectors.base import DataConnector

logger = logging.getLogger(__name__)


class FinancialDatasetsConnector(DataConnector):
    """Connector for Financial Datasets API (api.financialdatasets.ai)."""

    def __init__(self):
        self.base_url = os.environ.get("FINANCIAL_DATASETS_BASE_URL", "https://api.financialdatasets.ai")
        self.cache = get_cache()
        self.headers = {}
        if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
            self.headers["X-API-KEY"] = api_key

    def _make_request(self, endpoint: str, params: dict = None, method: str = "GET", data: dict = None) -> dict:
        """Make a request to the API with proper error handling."""
        try:
            if method == "GET":
                response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(f"{self.base_url}/{endpoint}", headers=self.headers, json=data)
            else:
                raise ValueError("Invalid request method")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code == 401:
                    raise ValueError("Invalid API key") from e
                elif e.response.status_code == 429:
                    raise ValueError("Rate limit exceeded") from e
                elif e.response.status_code == 404:
                    raise ValueError(f"Data not found for endpoint: {endpoint}") from e
            raise ValueError(f"API request failed: {str(e)}") from e
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}") from e

    def get_prices(self, ticker: str, start_date: str, end_date: str, interval: str = "day", interval_multiplier: int = 1) -> List[Price]:
        """Get historical price data for a ticker."""
        # Check cache first
        if cached_data := self.cache.get_prices(ticker):
            filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
            if filtered_data:
                return filtered_data

        try:
            # Prepare request parameters
            params = {"ticker": ticker, "start_date": start_date, "end_date": end_date, "interval": interval, "interval_multiplier": interval_multiplier, "limit": 5000}  # API maximum

            # Make the API request
            data = self._make_request("prices", params=params)

            if not data or "prices" not in data:
                logger.error(f"No price data returned for {ticker}")
                raise ValueError(f"No price data found for {ticker}")

            # Convert API response to Price objects
            prices = []
            for price_data in data["prices"]:
                try:
                    price = Price(time=price_data["time"], open=float(price_data["open"]), high=float(price_data["high"]), low=float(price_data["low"]), close=float(price_data["close"]), volume=int(price_data["volume"]), market_cap=float(price_data.get("market_cap", 0)) or None)
                    prices.append(price)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error parsing price data for {ticker}: {str(e)}")
                    continue

            if not prices:
                raise ValueError(f"Failed to parse any valid price data for {ticker}")

            # Cache the results
            self.cache.set_prices(ticker, [p.model_dump() for p in prices])

            return prices

        except Exception as e:
            logger.error(f"Error fetching prices for {ticker}: {str(e)}")
            raise ValueError(f"Failed to fetch price data for {ticker}: {str(e)}")

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> List[FinancialMetrics]:
        # Check cache first
        if cached_data := self.cache.get_financial_metrics(ticker):
            filtered_data = [FinancialMetrics(**metric) for metric in cached_data if metric["report_period"] <= end_date]
            filtered_data.sort(key=lambda x: x.report_period, reverse=True)
            if filtered_data:
                return filtered_data[:limit]

        # Fetch from API
        url = f"{self.base_url}/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
        try:
            data = self._make_request("financial-metrics", params={"ticker": ticker, "report_period_lte": end_date, "limit": limit, "period": period})
            metrics_response = FinancialMetricsResponse(**data)
            financial_metrics = metrics_response.financial_metrics

            if financial_metrics:
                self.cache.set_financial_metrics(ticker, [m.model_dump() for m in financial_metrics])
            return financial_metrics
        except Exception as e:
            logger.error(f"Error fetching financial metrics: {str(e)}")
            raise Exception(f"Error fetching data: {str(e)}")

    def search_line_items(self, ticker: str, line_items: List[str], end_date: str, period: str = "ttm", limit: int = 10) -> List[LineItem]:
        # Check cache first
        if cached_data := self.cache.get_line_items(ticker):
            filtered_data = [LineItem(**item) for item in cached_data if item["report_period"] <= end_date]
            filtered_data.sort(key=lambda x: x.report_period, reverse=True)
            if filtered_data:
                return filtered_data[:limit]

        # Fetch from API
        url = f"{self.base_url}/financials/search/line-items"
        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }
        try:
            data = self._make_request("financials/search/line-items", method="POST", data=body)
            response_model = LineItemResponse(**data)
            search_results = response_model.search_results

            if search_results:
                self.cache.set_line_items(ticker, [item.model_dump() for item in search_results])
            return search_results[:limit]
        except Exception as e:
            logger.error(f"Error fetching line items: {str(e)}")
            raise Exception(f"Error fetching data: {str(e)}")

    def get_insider_trades(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 1000) -> List[InsiderTrade]:
        # Check cache first
        if cached_data := self.cache.get_insider_trades(ticker):
            filtered_data = [InsiderTrade(**trade) for trade in cached_data if (start_date is None or (trade.get("transaction_date") or trade["filing_date"]) >= start_date) and (trade.get("transaction_date") or trade["filing_date"]) <= end_date]
            filtered_data.sort(key=lambda x: x.transaction_date or x.filing_date, reverse=True)
            if filtered_data:
                return filtered_data

        # Fetch from API with pagination
        all_trades = []
        current_end_date = end_date

        while True:
            url = f"{self.base_url}/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            url += f"&limit={limit}"

            try:
                data = self._make_request("insider-trades", params={"ticker": ticker, "filing_date_lte": current_end_date, "limit": limit})
                response_model = InsiderTradeResponse(**data)
                insider_trades = response_model.insider_trades

                if not insider_trades:
                    break

                all_trades.extend(insider_trades)

                if not start_date or len(insider_trades) < limit:
                    break

                current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

                if current_end_date <= start_date:
                    break
            except Exception as e:
                logger.error(f"Error fetching insider trades: {str(e)}")
                raise Exception(f"Error fetching data: {str(e)}")

        if all_trades:
            self.cache.set_insider_trades(ticker, [trade.model_dump() for trade in all_trades])
        return all_trades

    def get_company_news(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get company news articles."""
        # Check cache first
        if cached_news := self.cache.get_company_news(ticker):
            return cached_news

        all_news = []
        current_end_date = end_date

        while True:
            try:
                params = {"ticker": ticker, "end_date": current_end_date}
                if start_date:
                    params["start_date"] = start_date
                if limit:
                    params["limit"] = min(limit, 100)  # API max is 100

                try:
                    data = self._make_request("news", params=params)
                    news_items = data.get("news", [])

                    if not news_items:
                        break

                    all_news.extend(news_items)

                    if not start_date or len(news_items) < limit:
                        break

                    current_end_date = min(news["published_date"] for news in news_items)

                    if current_end_date <= start_date:
                        break

                except Exception as e:
                    logger.error(f"Error fetching company news: {str(e)}")
                    if "404" in str(e):
                        # Try alternate endpoint
                        try:
                            data = self._make_request("company/news", params=params)
                            news_items = data.get("news", [])
                            if news_items:
                                all_news.extend(news_items)
                                break
                        except Exception as alt_e:
                            raise ValueError(f"Failed to fetch news from both endpoints: {str(e)}, {str(alt_e)}")
                    else:
                        raise ValueError(f"Error fetching news: {str(e)}")

            except Exception as e:
                logger.error(f"Error in news fetch loop: {str(e)}")
                raise ValueError(f"Failed to fetch company news: {str(e)}")

        if all_news:
            self.cache.set_company_news(ticker, all_news)
        return all_news

    def get_market_cap(self, ticker: str, end_date: str) -> float:
        """Get market cap for a ticker on a specific date.

        Args:
            ticker: The stock ticker
            end_date: The date to get market cap for

        Returns:
            float: Market cap in dollars, or 0 if not available
        """
        # Try to get from financial metrics first as it's more reliable
        metrics = self.get_financial_metrics(ticker, end_date, period="ttm", limit=1)
        if metrics and metrics[0].market_cap:
            return metrics[0].market_cap

        # Fallback to price data if metrics don't have market cap
        prices = self.get_prices(ticker, end_date, end_date)
        if prices and prices[0].market_cap:
            return prices[0].market_cap

        # If both methods fail, log warning and return 0
        logger.warning(f"Could not fetch market cap for {ticker} on {end_date}")
        return 0.0

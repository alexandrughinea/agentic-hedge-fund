import os
from datetime import datetime
from typing import List, Optional

import requests
from data.cache import get_cache
from data.models import (
    Price,
    FinancialMetrics,
    LineItem,
    InsiderTrade,
    CompanyNews,
)
from data.connectors.base import DataConnector


class SeekingAlphaConnector(DataConnector):
    """Connector for Seeking Alpha API."""

    def __init__(self):
        self.base_url = os.environ.get("SEEKING_ALPHA_BASE_URL", "https://seeking-alpha-api.p.rapidapi.com")
        self.cache = get_cache()
        self.headers = {"x-rapidapi-host": os.environ.get("SEEKING_ALPHA_HOST", "seeking-alpha-api.p.rapidapi.com"), "x-rapidapi-key": os.environ.get("SEEKING_ALPHA_API_KEY", "")}
        if not self.headers["x-rapidapi-key"]:
            raise ValueError("SEEKING_ALPHA_API_KEY environment variable is not set")

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a request to the Seeking Alpha API."""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
        return response.json()

    def get_prices(self, ticker: str, start_date: str, end_date: str, interval: str = "day", interval_multiplier: int = 1) -> List[Price]:
        """Get historical price data for a ticker.

        Note: Seeking Alpha's free tier doesn't provide historical prices.
        We'll use the screener endpoint to get the latest price data.
        """
        # Check cache first
        if cached_data := self.cache.get_prices(ticker):
            filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
            if filtered_data:
                return filtered_data

        data = self._make_request("screener", {"type": "stocks"})

        # Find the ticker in the screener data
        stocks = data.get("metrics", {}).get("data", [])
        stock_data = next((s for s in stocks if s["attributes"]["symbol"] == ticker), None)

        if not stock_data:
            return []

        # Create a single price point from the available data
        attrs = stock_data["attributes"]
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        price = Price(ticker=ticker, time=current_time, open=float(attrs.get("price", 0.0)), high=float(attrs.get("day_high", 0.0)), low=float(attrs.get("day_low", 0.0)), close=float(attrs.get("price", 0.0)), volume=int(attrs.get("volume", 0)), market_cap=float(attrs.get("market_cap", 0.0)))

        # Cache the result
        self.cache.set_prices(ticker, [price.model_dump()])
        return [price]

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> List[FinancialMetrics]:
        """Get financial metrics for a ticker."""
        # Check cache first
        if cached_data := self.cache.get_financial_metrics(ticker):
            return [FinancialMetrics(**metric) for metric in cached_data]

        # Use screener to get basic financial metrics
        data = self._make_request("screener", {"type": "stocks"})
        stock_data = next((s for s in data.get("metrics", {}).get("data", []) if s["attributes"]["symbol"] == ticker), None)

        if not stock_data:
            return []

        attrs = stock_data["attributes"]
        current_date = datetime.now().strftime("%Y-%m-%d")

        metric = FinancialMetrics(
            ticker=ticker,
            calendar_date=current_date,
            report_period=current_date,
            period=period,
            currency="USD",
            market_cap=float(attrs.get("market_cap", 0.0)),
            enterprise_value=None,
            price_to_earnings_ratio=float(attrs.get("pe_ratio", 0.0)),
            price_to_book_ratio=float(attrs.get("price_to_book", 0.0)),
            price_to_sales_ratio=None,
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=None,
            operating_margin=float(attrs.get("operating_margin", 0.0)),
            net_margin=float(attrs.get("net_margin", 0.0)),
            return_on_equity=float(attrs.get("roe", 0.0)),
            return_on_assets=float(attrs.get("roa", 0.0)),
            return_on_invested_capital=None,
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=None,
            quick_ratio=None,
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=float(attrs.get("debt_to_equity", 0.0)),
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=float(attrs.get("revenue_growth", 0.0)),
            earnings_growth=float(attrs.get("earnings_growth", 0.0)),
            book_value_growth=None,
            earnings_per_share_growth=float(attrs.get("eps_growth", 0.0)),
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=float(attrs.get("eps", 0.0)),
            book_value_per_share=None,
            free_cash_flow_per_share=None,
        )

        # Cache the result
        self.cache.set_financial_metrics(ticker, [metric.model_dump()])
        return [metric]

    def search_line_items(self, ticker: str, line_items: List[str], end_date: str, period: str = "ttm", limit: int = 10) -> List[LineItem]:
        """Search for specific line items in financial statements.

        Note: This functionality is not directly available in the free tier.
        """
        return []

    def get_insider_trades(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 1000) -> List[InsiderTrade]:
        """Get insider trading data for a ticker.

        Note: This functionality is not directly available in the free tier.
        """
        return []

    def get_company_news(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 1000) -> List[CompanyNews]:
        """Get company news articles."""
        # Check cache first
        if cached_data := self.cache.get_company_news(ticker):
            return [CompanyNews(**news) for news in cached_data]

        # First get leading stories
        news_data = self._make_request("leading-story")

        # Filter news for the specific ticker
        all_news = []
        for story in news_data.get("leading_news_story", []):
            attrs = story["attributes"]
            if ticker.lower() in attrs.get("headline", "").lower():
                all_news.append(CompanyNews(ticker=ticker, title=attrs["headline"], url=attrs["url"], published_date=end_date, source="Seeking Alpha", summary=attrs.get("description", ""), sentiment=0.0))  # API doesn't provide date in free tier  # API doesn't provide sentiment

        # Also check dividend news if applicable
        div_data = self._make_request("dividend-investing")
        div_stocks = div_data.get("dividend_investing", {}).get("attributes", {})

        # Check trending dividend stocks
        for stock in div_stocks.get("trending_dividend_stocks", []):
            if stock["slug"] == ticker:
                all_news.append(CompanyNews(ticker=ticker, title=f"Dividend Yield: {stock['div_yield_fwd']}%", url=f"https://seekingalpha.com/symbol/{ticker}", published_date=end_date, source="Seeking Alpha", summary=f"{stock['name']} is trending among dividend stocks", sentiment=0.0))

        # Check recent dividend increases
        for stock in div_stocks.get("dividend_increases", []):
            if stock["slug"] == ticker:
                all_news.append(CompanyNews(ticker=ticker, title="Recent Dividend Increase", url=f"https://seekingalpha.com/symbol/{ticker}", published_date=end_date, source="Seeking Alpha", summary=f"{stock['name']} recently increased its dividend", sentiment=1.0))

        # Check upcoming ex-dividend dates
        for stock in div_stocks.get("upcoming_exdates", []):
            if stock["slug"] == ticker:
                all_news.append(CompanyNews(ticker=ticker, title=f"Upcoming Ex-Dividend Date: {stock['date']}", url=f"https://seekingalpha.com/symbol/{ticker}", published_date=end_date, source="Seeking Alpha", summary=f"{stock['name']} has an upcoming ex-dividend date", sentiment=0.0))

        # Cache the result
        self.cache.set_company_news(ticker, [news.model_dump() for news in all_news])
        return all_news[:limit]

    def get_market_cap(self, ticker: str, end_date: str) -> float:
        """Get market capitalization for a ticker."""
        prices = self.get_prices(ticker, end_date, end_date)
        if not prices:
            return 0.0
        return prices[0].market_cap

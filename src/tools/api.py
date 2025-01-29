import os
import pandas as pd
import requests
from typing import List

from data.cache import get_cache
from data.models import (
    Price,
)
from data.connectors.factory import get_connector

# Global cache instance
_cache = get_cache()

# Load limits from environment variables
FINANCIAL_METRICS_LIMIT = int(os.getenv("FINANCIAL_METRICS_LIMIT", "10"))
INSIDER_TRADES_LIMIT = int(os.getenv("INSIDER_TRADES_LIMIT", "1000"))
NEWS_LIMIT = int(os.getenv("NEWS_LIMIT", "1000"))
BALANCE_SHEET_LIMIT = int(os.getenv("BALANCE_SHEET_LIMIT", "2"))


def get_prices(ticker: str, start_date: str, end_date: str) -> List[Price]:
    """Fetch price data using the configured data connector."""
    return get_connector().get_prices(ticker, start_date, end_date)


def get_financial_metrics(ticker: str, end_date: str, period: str = "ttm", limit: int = None):
    """Fetch financial metrics using the configured data connector."""
    return get_connector().get_financial_metrics(ticker, end_date, period, limit or FINANCIAL_METRICS_LIMIT)


def search_line_items(ticker: str, line_items: List[str], end_date: str, period: str = "ttm", limit: int = None):
    """Search for line items using the configured data connector."""
    return get_connector().search_line_items(ticker, line_items, end_date, period, limit or BALANCE_SHEET_LIMIT)


def get_insider_trades(ticker: str, end_date: str, start_date: str = None, limit: int = None):
    """Fetch insider trades using the configured data connector."""
    return get_connector().get_insider_trades(ticker, end_date, start_date, limit or INSIDER_TRADES_LIMIT)


def get_company_news(ticker: str, end_date: str, start_date: str = None, limit: int = None):
    """Fetch company news using the configured data connector."""
    return get_connector().get_company_news(ticker, end_date, start_date, limit or NEWS_LIMIT)


def get_market_cap(ticker: str, end_date: str) -> float:
    """Fetch market cap using the configured data connector."""
    return get_connector().get_market_cap(ticker, end_date)


def prices_to_df(prices: List[Price]) -> pd.DataFrame:
    """Convert a list of Price objects to a pandas DataFrame."""
    if not prices:
        return pd.DataFrame()
    
    return pd.DataFrame([{
        'date': price.time.split('T')[0],
        'open': price.open,
        'high': price.high,
        'low': price.low,
        'close': price.close,
        'volume': price.volume,
        'market_cap': price.market_cap
    } for price in prices])


def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get price data as a DataFrame."""
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)

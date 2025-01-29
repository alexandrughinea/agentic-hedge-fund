from abc import ABC, abstractmethod
from typing import List, Optional

from data.models import (
    Price,
    FinancialMetrics,
    LineItem,
    InsiderTrade,
    CompanyNews
)

class DataConnector(ABC):
    """Base class for data connectors."""
    
    @abstractmethod
    def get_prices(self, ticker: str, start_date: str, end_date: str, interval: str = "day", interval_multiplier: int = 1) -> List[Price]:
        """Get historical price data for a ticker."""
        pass
    
    @abstractmethod
    def get_financial_metrics(
        self,
        ticker: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 10
    ) -> List[FinancialMetrics]:
        """Get financial metrics for a ticker."""
        pass
    
    @abstractmethod
    def search_line_items(
        self,
        ticker: str,
        query: str = None,
        limit: int = 10
    ) -> List[LineItem]:
        """Search line items for a ticker."""
        pass
    
    @abstractmethod
    def get_insider_trades(
        self,
        ticker: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> List[InsiderTrade]:
        """Get insider trades for a ticker."""
        pass
    
    @abstractmethod
    def get_company_news(
        self,
        ticker: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> List[CompanyNews]:
        """Get company news articles."""
        pass
    
    @abstractmethod
    def get_market_cap(self, ticker: str, end_date: str) -> float:
        """Get market cap for a ticker on a specific date."""
        pass

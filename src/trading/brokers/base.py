from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union
from datetime import datetime


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float


@dataclass
class Order:
    symbol: str
    quantity: float
    side: OrderSide
    type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"
    client_order_id: Optional[str] = None


@dataclass
class OrderResponse:
    order_id: str
    status: str
    filled_qty: float
    filled_avg_price: Optional[float]
    remaining_qty: float
    client_order_id: Optional[str]


class BrokerConnector(ABC):
    """Abstract base class for broker connectors."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the broker."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the broker."""
        pass

    @abstractmethod
    def get_account_info(self) -> Dict:
        """Get account information including cash balance, equity, etc."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        pass

    @abstractmethod
    def place_order(self, order: Order) -> OrderResponse:
        """Place a new order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResponse:
        """Get status of an order."""
        pass

    @abstractmethod
    def get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        pass

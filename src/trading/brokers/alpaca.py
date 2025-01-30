import os
from typing import Dict, List, Optional
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, StopLimitOrderRequest
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

from .base import BrokerConnector, Order, OrderResponse, Position, OrderType, OrderSide


class AlpacaBrokerConnector(BrokerConnector):
    """Alpaca implementation of the BrokerConnector."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, paper: bool = True):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.api_secret = api_secret or os.getenv("ALPACA_API_SECRET")
        if not self.api_key or not self.api_secret:
            raise ValueError("Alpaca API key and secret must be provided")

        self.paper = paper
        self.trading_client = None
        self.data_client = None

    def connect(self) -> bool:
        try:
            self.trading_client = TradingClient(self.api_key, self.api_secret, paper=self.paper)
            self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
            return True
        except Exception as e:
            print(f"Failed to connect to Alpaca: {e}")
            return False

    def disconnect(self) -> bool:
        self.trading_client = None
        self.data_client = None
        return True

    def get_account_info(self) -> Dict:
        account = self.trading_client.get_account()
        return {"cash": float(account.cash), "equity": float(account.equity), "buying_power": float(account.buying_power), "day_trade_count": account.daytrade_count}

    def get_positions(self) -> List[Position]:
        positions = []
        for pos in self.trading_client.get_all_positions():
            positions.append(Position(symbol=pos.symbol, quantity=float(pos.qty), avg_entry_price=float(pos.avg_entry_price), current_price=float(pos.current_price), market_value=float(pos.market_value), unrealized_pl=float(pos.unrealized_pl)))
        return positions

    def _create_order_request(self, order: Order):
        side = AlpacaOrderSide.BUY if order.side == OrderSide.BUY else AlpacaOrderSide.SELL

        if order.type == OrderType.MARKET:
            return MarketOrderRequest(symbol=order.symbol, qty=order.quantity, side=side, time_in_force=TimeInForce.DAY)
        elif order.type == OrderType.LIMIT:
            return LimitOrderRequest(symbol=order.symbol, qty=order.quantity, side=side, time_in_force=TimeInForce.DAY, limit_price=order.limit_price)
        elif order.type == OrderType.STOP:
            return StopOrderRequest(symbol=order.symbol, qty=order.quantity, side=side, time_in_force=TimeInForce.DAY, stop_price=order.stop_price)
        elif order.type == OrderType.STOP_LIMIT:
            return StopLimitOrderRequest(symbol=order.symbol, qty=order.quantity, side=side, time_in_force=TimeInForce.DAY, stop_price=order.stop_price, limit_price=order.limit_price)

    def place_order(self, order: Order) -> OrderResponse:
        order_request = self._create_order_request(order)
        response = self.trading_client.submit_order(order_data=order_request)

        return OrderResponse(order_id=response.id, status=response.status, filled_qty=float(response.filled_qty), filled_avg_price=float(response.filled_avg_price) if response.filled_avg_price else None, remaining_qty=float(response.qty) - float(response.filled_qty), client_order_id=response.client_order_id)

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.trading_client.cancel_order(order_id)
            return True
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> OrderResponse:
        order = self.trading_client.get_order_by_id(order_id)
        return OrderResponse(order_id=order.id, status=order.status, filled_qty=float(order.filled_qty), filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None, remaining_qty=float(order.qty) - float(order.filled_qty), client_order_id=order.client_order_id)

    def get_market_price(self, symbol: str) -> float:
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self.data_client.get_stock_latest_quote(request)
        return float(quotes[symbol].ask_price)

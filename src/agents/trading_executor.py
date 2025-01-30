import logging
from typing import Dict, Optional
import json

from graph.state import AgentState
from trading.brokers import create_broker, BrokerType, Order, OrderSide, OrderType
from utils.progress import progress

logger = logging.getLogger(__name__)


class TradingExecutor:
    """Executes trading decisions through the broker"""

    def __init__(self, paper: bool = True):
        try:
            self.broker = create_broker(BrokerType.ALPACA, paper=paper)
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to initialize broker: {str(e)}")
            raise ValueError(f"Failed to initialize broker: {str(e)}")

    def connect(self) -> bool:
        """Connect to the broker"""
        try:
            if not self.connected:
                self.connected = self.broker.connect()
            return self.connected
        except Exception as e:
            logger.error(f"Failed to connect to broker: {str(e)}")
            raise ValueError(f"Failed to connect to broker: {str(e)}")

    def disconnect(self):
        """Disconnect from the broker"""
        try:
            if self.connected:
                self.broker.disconnect()
                self.connected = False
        except Exception as e:
            logger.error(f"Failed to disconnect from broker: {str(e)}")
            raise ValueError(f"Failed to disconnect from broker: {str(e)}")

    def execute_portfolio_decisions(self, state: AgentState) -> AgentState:
        """Execute the portfolio management decisions"""
        try:
            # Get the latest message which should contain the decisions
            if not state["messages"]:
                progress.update_status("trading_executor", "", "No messages found")
                return state

            last_message = state["messages"][-1]
            try:
                portfolio_decisions = json.loads(last_message.content)
            except json.JSONDecodeError:
                progress.update_status("trading_executor", "", "Invalid portfolio decisions format")
                return state

            if not portfolio_decisions:
                progress.update_status("trading_executor", "", "No portfolio decisions found")
                return state

            # Connect to broker if not already connected
            if not self.connected:
                self.connect()

            # Execute each decision
            execution_results = {}
            for ticker, decision in portfolio_decisions.items():
                try:
                    action = decision.get("action", "").lower()
                    quantity = decision.get("quantity", 0)

                    if action not in ["buy", "sell"] or quantity <= 0:
                        progress.update_status("trading_executor", ticker, f"✓ HOLD (no action needed)")
                        continue

                    progress.update_status("trading_executor", ticker, f"Executing {action.upper()} order")

                    # Create and execute order
                    order = Order(symbol=ticker, quantity=quantity, side=OrderSide.BUY if action == "buy" else OrderSide.SELL, type=OrderType.MARKET)

                    result = self.broker.place_order(order)
                    execution_results[ticker] = {"status": "success", "action": action, "quantity": quantity, "order_id": result.get("id", "unknown")}

                    progress.update_status("trading_executor", ticker, f"✓ {action.upper()} {quantity} shares")

                except Exception as e:
                    logger.error(f"Error executing order for {ticker}: {str(e)}")
                    execution_results[ticker] = {"status": "error", "error": str(e)}
                    progress.update_status("trading_executor", ticker, f"Error: {str(e)}")

            # Update the portfolio state
            self._update_portfolio_state(state)

            # Add execution results to state
            state["data"]["execution_results"] = execution_results

            # Show final status with action summary
            action_summary = []
            for ticker, result in execution_results.items():
                if result["status"] == "success":
                    action_summary.append(f"{ticker}: {result['action'].upper()} {result['quantity']}")

            if action_summary:
                progress.update_status("trading_executor", "", f"Done - {', '.join(action_summary)}")
            else:
                progress.update_status("trading_executor", "", "Done - No trades executed")

            return state

        except Exception as e:
            logger.error(f"Trading execution error: {str(e)}")
            progress.update_status("trading_executor", "", f"Error: {str(e)}")
            return state

    def _update_portfolio_state(self, state: AgentState):
        """Update the portfolio state with current positions and cash"""
        try:
            # Get account info
            account_info = self.broker.get_account_info()

            # Get current positions
            positions = self.broker.get_positions()

            # Update portfolio in state
            if "portfolio" not in state["data"]:
                state["data"]["portfolio"] = {}

            state["data"]["portfolio"]["cash"] = float(account_info["cash"])
            state["data"]["portfolio"]["positions"] = {pos.symbol: {"shares": pos.quantity, "avg_price": pos.avg_entry_price, "market_value": pos.market_value, "unrealized_pl": pos.unrealized_pl} for pos in positions}

        except Exception as e:
            logger.error(f"Error updating portfolio state: {str(e)}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting."""
        try:
            self.broker.close()
        except Exception as e:
            logger.error(f"Error closing Alpaca connection: {e}")
        finally:
            # Ensure we return a valid state update even on error
            return {"portfolio": self.portfolio, "orders": self.orders, "cash": self.cash, "status": "completed"}

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
    
    def execute_portfolio_decisions(self, state: AgentState) -> Dict:
        """Execute the portfolio management decisions"""
        execution_results = {}
        
        try:
            # Wait for portfolio management to complete by checking messages
            import time
            max_wait = 30  # Maximum wait time in seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                if portfolio_decisions := state.get("portfolio_decisions"):
                    break
                time.sleep(0.1)
                
            if not portfolio_decisions:
                progress.update_status("trading_executor", "", "Timeout waiting for Portfolio Management")
                return {"error": "Timeout waiting for Portfolio Management"}

            # Connect to broker if not already connected
            if not self.connected:
                self.connect()

            # Execute each decision
            for ticker, decision in portfolio_decisions.items():
                try:
                    progress.update_status("trading_executor", ticker, f"Executing {decision['action']} order")
                    
                    # Create and execute order
                    order = Order(
                        symbol=ticker,
                        quantity=decision["quantity"],
                        side=OrderSide.BUY if decision["action"] == "buy" else OrderSide.SELL,
                        type=OrderType.MARKET
                    )
                    
                    result = self.broker.place_order(order)
                    execution_results[ticker] = {
                        "status": "success",
                        "action": decision["action"],
                        "quantity": decision["quantity"],
                        "order_id": result.get("id", "unknown")
                    }
                    
                    progress.update_status("trading_executor", ticker, "✓ Order executed successfully")
                    
                except Exception as e:
                    logger.error(f"Error executing order for {ticker}: {str(e)}")
                    execution_results[ticker] = {
                        "status": "error",
                        "error": str(e)
                    }
                    progress.update_status("trading_executor", ticker, f"❌ Order execution failed: {str(e)}")

            return execution_results
            
        except Exception as e:
            error_msg = f"❌ Error executing trades: {str(e)}"
            progress.update_status("trading_executor", "", error_msg)
            return {"error": error_msg}
        
        finally:
            try:
                self.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from broker: {str(e)}")

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
            state["data"]["portfolio"]["positions"] = {
                pos.symbol: {
                    "shares": pos.quantity,
                    "avg_price": pos.avg_entry_price,
                    "market_value": pos.market_value,
                    "unrealized_pl": pos.unrealized_pl
                }
                for pos in positions
            }
            
        except Exception as e:
            logger.error(f"Error updating portfolio state: {str(e)}")

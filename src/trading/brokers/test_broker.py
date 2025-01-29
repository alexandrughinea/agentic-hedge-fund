import logging
from .factory import create_broker, BrokerType
from .base import Order, OrderType, OrderSide

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_alpaca_broker():
    """Test the Alpaca broker implementation"""
    # Create broker instance (will use environment variables for credentials)
    broker = create_broker(BrokerType.ALPACA, paper=True)
    
    # Connect to the broker
    if not broker.connect():
        logger.error("Failed to connect to Alpaca")
        return
    
    try:
        # Get account information
        logger.info("\nGetting account info...")
        account_info = broker.get_account_info()
        logger.info(f"Account info: {account_info}")
        
        # Get current positions
        logger.info("\nGetting positions...")
        positions = broker.get_positions()
        logger.info(f"Current positions: {positions}")
        
        # Get market price for a symbol
        symbol = "AAPL"
        logger.info(f"\nGetting market price for {symbol}...")
        price = broker.get_market_price(symbol)
        logger.info(f"Current price for {symbol}: ${price:.2f}")
        
        # Place a market buy order
        logger.info("\nPlacing market buy order...")
        order = Order(
            symbol=symbol,
            quantity=1,
            side=OrderSide.BUY,
            type=OrderType.MARKET
        )
        response = broker.place_order(order)
        logger.info(f"Order response: {response}")
        
        # Get order status
        logger.info("\nGetting order status...")
        status = broker.get_order_status(response.order_id)
        logger.info(f"Order status: {status}")
        
    finally:
        # Disconnect from broker
        broker.disconnect()
        logger.info("\nDisconnected from broker")

if __name__ == "__main__":
    test_alpaca_broker()

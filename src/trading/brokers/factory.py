from enum import Enum
from typing import Optional

from .base import BrokerConnector
from .alpaca import AlpacaBrokerConnector

class BrokerType(Enum):
    ALPACA = "alpaca"
    # Add more broker types as they are implemented
    # INTERACTIVE_BROKERS = "interactive_brokers"

def create_broker(
    broker_type: BrokerType,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    paper: bool = True
) -> BrokerConnector:
    """
    Factory function to create broker instances.
    
    Args:
        broker_type: Type of broker to create
        api_key: Optional API key (can also be set via environment variables)
        api_secret: Optional API secret (can also be set via environment variables)
        paper: Whether to use paper trading (default: True)
    
    Returns:
        BrokerConnector instance
    """
    if broker_type == BrokerType.ALPACA:
        return AlpacaBrokerConnector(api_key=api_key, api_secret=api_secret, paper=paper)
    
    raise ValueError(f"Unsupported broker type: {broker_type}")

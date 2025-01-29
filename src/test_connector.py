import logging
import os
from datetime import datetime, timedelta

from data.connectors.factory import get_connector
from data.connectors.financial_datasets import FinancialDatasetsConnector
from data.connectors.seeking_alpha import SeekingAlphaConnector

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_financial_datasets():
    """Test Financial Datasets connector"""
    connector = FinancialDatasetsConnector()
    
    # Test dates
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Test get_prices
    logger.info("\nTesting get_prices...")
    try:
        prices = connector.get_prices("AAPL", start_date, end_date)
        logger.info(f"Got {len(prices)} price points for AAPL")
    except Exception as e:
        logger.error(f"Error getting prices: {e}")

def test_seeking_alpha():
    """Test Seeking Alpha connector"""
    connector = SeekingAlphaConnector()
    
    # Test dates
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Test get_prices
    logger.info("\nTesting get_prices...")
    try:
        prices = connector.get_prices("AAPL", start_date, end_date)
        logger.info(f"Got {len(prices)} price points for AAPL")
    except Exception as e:
        logger.error(f"Error getting prices: {e}")

if __name__ == "__main__":
    # Test Financial Datasets connector
    logger.info("Testing Financial Datasets connector...")
    test_financial_datasets()
    
    # Test Seeking Alpha connector
    logger.info("\nTesting Seeking Alpha connector...")
    test_seeking_alpha()

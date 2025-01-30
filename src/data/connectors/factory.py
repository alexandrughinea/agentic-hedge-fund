from typing import Optional
from data.connectors.base import DataConnector
from data.connectors.financial_datasets import FinancialDatasetsConnector

_default_connector: Optional[DataConnector] = None


def get_connector() -> DataConnector:
    """Get the default data connector instance."""
    global _default_connector
    if _default_connector is None:
        _default_connector = FinancialDatasetsConnector()
    return _default_connector


def set_connector(connector: DataConnector) -> None:
    """Set a custom data connector instance."""
    global _default_connector
    _default_connector = connector

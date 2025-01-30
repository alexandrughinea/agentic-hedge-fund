"""Utilities for checking market hours and scheduling."""

from datetime import datetime, timedelta
import pytz


def is_market_open() -> bool:
    """Check if the US stock market is currently open.

    Returns:
        bool: True if market is open, False otherwise
    """
    now = datetime.now(pytz.timezone("America/New_York"))

    # Check if it's a weekday
    if now.weekday() > 4:  # Saturday = 5, Sunday = 6
        return False

    # Check if it's during market hours (9:30 AM - 4:00 PM)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close


def get_next_market_open() -> datetime:
    """Get the next market opening time.

    Returns:
        datetime: Next market opening time in NY timezone
    """
    ny_tz = pytz.timezone("America/New_York")
    now = datetime.now(ny_tz)

    # Start with tomorrow if we're past today's market close
    if now.hour >= 16:
        now += timedelta(days=1)

    # Set to market open time (9:30 AM)
    next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

    # If it's weekend, move to Monday
    while next_open.weekday() > 4:
        next_open += timedelta(days=1)

    return next_open

"""Scheduler for autonomous trading operations."""

import logging
import time
import os
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from main import run_trading_cycle
from utils.market_hours import is_market_open, get_next_market_open
from utils.progress import progress

logger = logging.getLogger(__name__)

class TradingScheduler:
    """Manages scheduled trading operations."""
    
    def __init__(self, tickers: list, trading_hours_only: bool = True, timezone: str = "America/New_York"):
        self.tickers = tickers
        self.trading_hours_only = trading_hours_only
        self.timezone = pytz.timezone(timezone)
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        self.scheduler.add_listener(self._handle_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
        
        # Load safety limits from environment
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', '25000'))
        self.max_portfolio_value = float(os.getenv('MAX_PORTFOLIO_VALUE', '1000000'))
        self.retry_attempts = int(os.getenv('RETRY_ATTEMPTS', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '5'))
        
    def _handle_job_event(self, event):
        """Handle scheduler job events."""
        if event.exception:
            logger.error(f"Trading cycle failed: {str(event.exception)}")
            progress.update_status("scheduler", "", f"Trading cycle failed: {str(event.exception)}")
        else:
            logger.info("Trading cycle completed successfully")
            progress.update_status("scheduler", "", "Trading cycle completed successfully")
            
    def _can_trade_now(self) -> bool:
        """Check if trading is allowed at current time."""
        if not self.trading_hours_only:
            return True
            
        return is_market_open()
        
    def _execute_trading_cycle(self):
        """Execute one complete trading cycle."""
        if not self._can_trade_now():
            next_open = get_next_market_open()
            logger.info(f"Market is closed. Next trading window opens at {next_open}")
            progress.update_status("scheduler", "", f"Market closed. Next window: {next_open}")
            return
            
        attempts = 0
        while attempts < self.retry_attempts:
            try:
                result = run_trading_cycle(self.tickers)
                if result:
                    logger.info("Trading cycle completed successfully")
                    progress.update_status("scheduler", "", "Trading cycle completed")
                break
            except Exception as e:
                attempts += 1
                if attempts >= self.retry_attempts:
                    logger.error(f"Trading cycle failed after {attempts} attempts: {str(e)}")
                    progress.update_status("scheduler", "", f"Failed after {attempts} attempts: {str(e)}")
                else:
                    logger.warning(f"Attempt {attempts} failed, retrying in {self.retry_delay}s: {str(e)}")
                    progress.update_status("scheduler", "", f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
            
    def start(self, interval_minutes: int = 60):
        """Start the scheduler with specified interval."""
        # Validate interval
        min_interval = int(os.getenv('MIN_TRADING_INTERVAL', '5'))
        max_interval = int(os.getenv('MAX_TRADING_INTERVAL', '240'))
        
        if not min_interval <= interval_minutes <= max_interval:
            raise ValueError(f"Trading interval must be between {min_interval} and {max_interval} minutes")
        
        # Add trading job
        self.scheduler.add_job(
            self._execute_trading_cycle,
            'interval',
            minutes=interval_minutes,
            id='trading_cycle'
        )
        
        # Add market hours check job (runs every morning)
        if self.trading_hours_only:
            self.scheduler.add_job(
                self._execute_trading_cycle,
                CronTrigger(hour=9, minute=31, timezone=self.timezone),
                id='market_open'
            )
            
        self.scheduler.start()
        logger.info(f"Scheduler started. Trading every {interval_minutes} minutes")
        progress.update_status("scheduler", "", f"Started. Trading every {interval_minutes} min")
        
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
        progress.update_status("scheduler", "", "Stopped")

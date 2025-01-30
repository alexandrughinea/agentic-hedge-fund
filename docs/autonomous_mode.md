# Autonomous Mode

The autonomous mode allows the hedge fund to run continuously, making trading decisions at specified intervals during market hours.

## Quick Start

```bash
# Run with default settings (hourly trading)
poetry run python src/main.py --autonomous

# Run with custom interval (30-minute trading)
poetry run python src/main.py --autonomous --interval 30

# Run with specific tickers
poetry run python src/main.py --autonomous --interval 60 --tickers "AAPL,MSFT,GOOGL"
```

## Features

### 1. Market Hours Management
- Only trades during US market hours (9:30 AM - 4:00 PM ET)
- Automatically detects market open/close
- Handles pre-market and after-hours periods
- Respects market holidays (coming soon)

### 2. Scheduling
- Configurable trading intervals (in minutes)
- Default: 60 minutes between trades
- Minimum interval: 5 minutes
- Maximum interval: 240 minutes (4 hours)

### 3. Error Handling
- Automatic retry on API failures
- Graceful degradation if analysts fail
- Timeout protection for each component
- Rate limiting awareness

### 4. Monitoring
- Real-time status updates
- Progress tracking for each analyst
- Error logging and reporting
- Performance metrics collection

## Configuration

### Environment Variables
```bash
# Trading Configuration
TICKERS=AAPL,MSFT,GOOGL
INITIAL_CASH=100000.0
SHOW_REASONING=true

# API Configuration
OPENAI_API_KEY=your-key
FINANCIAL_DATASETS_API_KEY=your-key
ALPACA_API_KEY=your-key
ALPACA_API_SECRET=your-key

# Analyst Selection
SELECTED_ANALYSTS=technical_analyst_agent,fundamentals_agent,sentiment_analysis_agent,valuation_agent

# Autonomous Mode Settings (Optional)
TRADING_INTERVAL=60  # Minutes between trades
MARKET_HOURS_ONLY=true  # Only trade during market hours
```

### Command Line Arguments
```bash
--autonomous          Enable autonomous mode
--interval MINUTES    Trading interval in minutes
--tickers SYMBOLS    Comma-separated list of tickers
--initial-cash AMOUNT Initial portfolio cash
--show-reasoning     Show detailed analysis
```

## Safety Features

### 1. Position Limits
- Maximum position size per ticker
- Portfolio-wide exposure limits
- Automatic position scaling

### 2. Rate Limiting
- API call throttling
- Quota management
- Fallback mechanisms

### 3. Error Recovery
- Automatic retry on transient errors
- Circuit breaker on persistent failures
- Graceful degradation modes

### 4. Market Conditions
- Volatility checks
- Volume monitoring
- Spread analysis

## Monitoring and Maintenance

### 1. Logs
```bash
# View real-time logs
tail -f logs/autonomous_trading.log

# View error logs
tail -f logs/error.log
```

### 2. Status Checks
- Current positions and P&L
- API quota usage
- Error rates and types
- Performance metrics

### 3. Alerts
- Error notifications
- Position limit warnings
- API quota alerts
- Market condition warnings

## Best Practices

1. **Testing**
   - Start with paper trading
   - Test during market hours
   - Verify all API connections
   - Monitor initial trades closely

2. **Risk Management**
   - Set conservative position limits
   - Enable all safety features
   - Monitor frequently
   - Have stop procedures ready

3. **Maintenance**
   - Regular log review
   - API quota monitoring
   - Performance analysis
   - Strategy adjustment

4. **Emergency Procedures**
   - How to stop trading
   - Position liquidation process
   - Error escalation path
   - Recovery procedures

## Limitations

1. **Market Hours**
   - US market hours only
   - No pre/post market trading
   - Holiday calendar needed

2. **API Dependencies**
   - OpenAI API availability
   - Financial data API limits
   - Broker API stability

3. **Resource Usage**
   - CPU/Memory consumption
   - Network bandwidth
   - Disk space for logs

4. **Known Issues**
   - Potential LLM timeout
   - API rate limiting
   - Market data delays

## Future Enhancements

1. **Planned Features**
   - Market holiday calendar
   - Multi-exchange support
   - Advanced risk metrics
   - Performance analytics

2. **Under Consideration**
   - Pre/post market trading
   - Multiple portfolio support
   - Custom trading schedules
   - Enhanced monitoring

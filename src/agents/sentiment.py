from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
import pandas as pd
import numpy as np
import json

from tools.api import get_insider_trades, get_company_news


##### Sentiment Agent #####
def sentiment_agent(state: AgentState):
    """Analyzes market sentiment and generates trading signals for multiple tickers."""
    try:
        data = state.get("data", {})
        end_date = data.get("end_date")
        tickers = data.get("tickers")

        # Initialize sentiment analysis for each ticker
        sentiment_analysis = {}

        for ticker in tickers:
            try:
                progress.update_status("sentiment_agent", ticker, "Fetching insider trades")

                # Get the insider trades
                try:
                    insider_trades = get_insider_trades(
                        ticker=ticker,
                        end_date=end_date,
                        limit=1000,
                    )
                except Exception as e:
                    progress.update_status("sentiment_agent", ticker, f"\033[91mError: Failed to fetch insider trades - {str(e)}\033[0m")
                    raise

                progress.update_status("sentiment_agent", ticker, "Analyzing trading patterns")

                # Get the signals from the insider trades
                transaction_shares = pd.Series([t.transaction_shares for t in insider_trades]).dropna()
                insider_signals = np.where(transaction_shares < 0, "bearish", "bullish").tolist()

                progress.update_status("sentiment_agent", ticker, "Fetching company news")

                # Get the company news
                try:
                    company_news = get_company_news(ticker, end_date, limit=100)
                except Exception as e:
                    progress.update_status("sentiment_agent", ticker, f"\033[91mError: Failed to fetch company news - {str(e)}\033[0m")
                    raise

                # Get the sentiment from the company news
                sentiment = pd.Series([n.get('sentiment', 'neutral') for n in company_news]).dropna()
                news_signals = np.where(sentiment == "negative", "bearish", 
                                    np.where(sentiment == "positive", "bullish", "neutral")).tolist()
                
                progress.update_status("sentiment_agent", ticker, "Combining signals")
                # Combine signals from both sources with weights
                insider_weight = 0.3
                news_weight = 0.7
                
                # Calculate bullish and bearish percentages for insider trades
                insider_bullish = insider_signals.count("bullish") / len(insider_signals) if insider_signals else 0.5
                insider_bearish = insider_signals.count("bearish") / len(insider_signals) if insider_signals else 0.5
                
                # Calculate bullish and bearish percentages for news
                news_bullish = news_signals.count("bullish") / len(news_signals) if news_signals else 0.5
                news_bearish = news_signals.count("bearish") / len(news_signals) if news_signals else 0.5
                
                # Combine signals with weights
                combined_bullish = (insider_weight * insider_bullish + news_weight * news_bullish)
                combined_bearish = (insider_weight * insider_bearish + news_weight * news_bearish)
                
                # Determine final signal and confidence
                if combined_bullish > combined_bearish:
                    signal = "bullish"
                    confidence = (combined_bullish - 0.5) * 200  # Scale to 0-100
                else:
                    signal = "bearish"
                    confidence = (combined_bearish - 0.5) * 200  # Scale to 0-100

                sentiment_analysis[ticker] = {
                    "signal": signal,
                    "confidence": confidence,
                    "insider_trades": len(insider_signals),
                    "news_count": len(news_signals),
                }

                progress.update_status("sentiment_agent", ticker, "Done")

            except Exception as e:
                progress.update_status("sentiment_agent", ticker, f"\033[91mError: {str(e)}\033[0m")
                # Add error signal for this ticker
                sentiment_analysis[ticker] = {
                    "signal": "neutral",  # Default to neutral on error
                    "confidence": 0,
                    "error": str(e)
                }

        # Create the sentiment message
        message = HumanMessage(
            content=json.dumps(sentiment_analysis),
            name="sentiment",
        )

        # Show reasoning if flag is set
        if state["metadata"]["show_reasoning"]:
            show_agent_reasoning(sentiment_analysis, "Sentiment Agent")

        return {
            "messages": state["messages"] + [message],
            "data": {
                **state["data"],
                "analyst_signals": {
                    **state["data"].get("analyst_signals", {}),
                    "sentiment_agent": sentiment_analysis
                }
            },
        }

    except Exception as e:
        # Handle any unexpected errors at the top level
        progress.update_status("sentiment_agent", None, f"\033[91mError: {str(e)}\033[0m")
        return {
            "messages": state["messages"],
            "data": state["data"]
        }

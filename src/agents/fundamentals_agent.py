from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
import json

from tools.api import get_financial_metrics


def fundamentals_agent(state: AgentState):
    """Analyzes fundamental data and generates trading signals for multiple tickers."""
    try:
        data = state["data"]
        end_date = data["end_date"]
        tickers = data["tickers"]

        # Initialize fundamental analysis for each ticker
        fundamental_analysis = {}

        for ticker in tickers:
            try:
                progress.update_status("fundamentals_agent", ticker, "Fetching financial metrics")

                # Get the financial metrics
                try:
                    financial_metrics = get_financial_metrics(
                        ticker=ticker,
                        end_date=end_date,
                        period="ttm",
                        limit=10,
                    )
                except Exception as e:
                    progress.update_status("fundamentals_agent", ticker, f"\033[91mError: Failed to fetch metrics - {str(e)}\033[0m")
                    fundamental_analysis[ticker] = {"signal": "neutral", "confidence": 0, "error": str(e)}
                    continue

                if not financial_metrics:
                    progress.update_status("fundamentals_agent", ticker, f"\033[91mError: No financial metrics found\033[0m")
                    fundamental_analysis[ticker] = {"signal": "neutral", "confidence": 0, "error": "No financial metrics found"}
                    continue

                # Pull the most recent financial metrics
                metrics = financial_metrics[0]

                # Initialize signals list for different fundamental aspects
                signals = []
                reasoning = {}

                progress.update_status("fundamentals_agent", ticker, "Analyzing profitability")
                # 1. Profitability Analysis
                return_on_equity = metrics.return_on_equity
                net_margin = metrics.net_margin
                operating_margin = metrics.operating_margin

                thresholds = [
                    (return_on_equity, 0.15),  # Strong ROE above 15%
                    (net_margin, 0.20),  # Healthy profit margins
                    (operating_margin, 0.15),  # Strong operating efficiency
                ]

                profitability_score = sum(1 for value, threshold in thresholds if value and value > threshold)
                signals.append("bullish" if profitability_score >= 2 else "bearish")
                reasoning["profitability"] = f"Profitability score: {profitability_score}/3"

                progress.update_status("fundamentals_agent", ticker, "Analyzing valuation")
                # 2. Valuation Analysis
                pe_ratio = metrics.price_to_earnings_ratio
                price_to_book = metrics.price_to_book_ratio
                price_to_sales = metrics.price_to_sales_ratio

                # Check if valuation metrics are attractive (below industry averages)
                valuation_checks = [
                    (pe_ratio, 20),  # PE ratio below 20
                    (price_to_book, 3),  # P/B ratio below 3
                    (price_to_sales, 2),  # P/S ratio below 2
                ]

                valuation_score = sum(1 for value, threshold in valuation_checks if value and value < threshold)
                signals.append("bullish" if valuation_score >= 2 else "bearish")
                reasoning["valuation"] = f"Valuation score: {valuation_score}/3"

                progress.update_status("fundamentals_agent", ticker, "Analyzing growth")
                # 3. Growth Analysis
                revenue_growth = metrics.revenue_growth
                earnings_growth = metrics.earnings_growth

                growth_checks = [
                    (revenue_growth, 0.10),  # Revenue growth above 10%
                    (earnings_growth, 0.10),  # Earnings growth above 10%
                ]

                growth_score = sum(1 for value, threshold in growth_checks if value and value > threshold)
                signals.append("bullish" if growth_score == 2 else "bearish")
                reasoning["growth"] = f"Growth score: {growth_score}/2"

                # Calculate overall signal and confidence
                bullish_signals = signals.count("bullish")
                total_signals = len(signals)

                if bullish_signals > total_signals / 2:
                    signal = "bullish"
                    confidence = (bullish_signals / total_signals) * 100
                else:
                    signal = "bearish"
                    confidence = ((total_signals - bullish_signals) / total_signals) * 100

                fundamental_analysis[ticker] = {"signal": signal, "confidence": confidence, "reasoning": reasoning}

                progress.update_status("fundamentals_agent", ticker, "Done")

            except Exception as e:
                progress.update_status("fundamentals_agent", ticker, f"\033[91mError: {str(e)}\033[0m")
                fundamental_analysis[ticker] = {"signal": "neutral", "confidence": 0, "error": str(e)}

        # Create the fundamentals message
        message = HumanMessage(
            content=json.dumps(fundamental_analysis),
            name="fundamentals",
        )

        # Show reasoning if flag is set
        if state["metadata"]["show_reasoning"]:
            show_agent_reasoning(fundamental_analysis, "Fundamentals Agent")

        return {
            "messages": state["messages"] + [message],
            "data": {**state["data"], "analyst_signals": {**state["data"].get("analyst_signals", {}), "fundamentals_agent": fundamental_analysis}},
        }

    except Exception as e:
        # Handle any unexpected errors at the top level
        progress.update_status("fundamentals_agent", None, f"\033[91mError: {str(e)}\033[0m")
        return {"messages": state["messages"], "data": state["data"]}

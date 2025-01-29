from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
import os
import sys
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import argparse
from tabulate import tabulate
import logging
import json

# Initialize logger
logger = logging.getLogger(__name__)

from agents.fundamentals import fundamentals_agent
from agents.portfolio_manager import portfolio_management_agent
from agents.technicals import technical_analyst_agent
from agents.risk_manager import risk_management_agent
from agents.sentiment import sentiment_agent
from graph.state import AgentState
from agents.valuation import valuation_agent
from utils.display import print_trading_output
from utils.analysts import ANALYST_ORDER
from utils.progress import progress
from agents.trading_executor import TradingExecutor

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)

def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state

def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)

    # Add start node
    workflow.add_node("start", start)

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = ["technical_analyst", "fundamentals_analyst", "sentiment_analyst", "valuation_analyst"]

    # Add selected analysts
    for analyst in selected_analysts:
        if analyst == "technical_analyst":
            workflow.add_node("technical_analyst", technical_analyst_agent)
        elif analyst == "fundamentals_analyst":
            workflow.add_node("fundamentals_analyst", fundamentals_agent)
        elif analyst == "sentiment_analyst":
            workflow.add_node("sentiment_analyst", sentiment_agent)
        elif analyst == "valuation_analyst":
            workflow.add_node("valuation_analyst", valuation_agent)

    # Add risk management and portfolio management
    workflow.add_node("risk_management", risk_management_agent)
    workflow.add_node("portfolio_management", portfolio_management_agent)

    # Connect start to all analysts
    for analyst in selected_analysts:
        workflow.add_edge("start", analyst)

    # Connect analysts to risk management
    for analyst in selected_analysts:
        workflow.add_edge(analyst, "risk_management")

    # Connect risk management to portfolio management
    workflow.add_edge("risk_management", "portfolio_management")
    workflow.add_edge("portfolio_management", END)

    # Set the entry point
    workflow.set_entry_point("start")

    return workflow

# Create default workflow
default_workflow = create_workflow()
app = default_workflow.compile()

def get_analysts():
    """Get all available analyst agents"""
    return [
        fundamentals_agent,
        technical_analyst_agent,
        sentiment_agent,
        valuation_agent,
        risk_management_agent,
        portfolio_management_agent
    ]

##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list = None,
    agent: object = None,
):
    """Run the hedge fund with the given parameters"""
    try:
        progress.start()
        
        # Initialize the trading executor
        executor = TradingExecutor(paper=True)
        
        # Create initial state
        initial_state = {
            "messages": [
                HumanMessage(content="Starting new trading cycle")
            ],
            "data": {
                "tickers": tickers,
                "portfolio": portfolio,
                "start_date": start_date,
                "end_date": end_date,
                "analyst_signals": {}
            },
            "metadata": {
                "show_reasoning": show_reasoning
            }
        }

        # Run the workflow
        if agent is None:
            agent = app
            
        final_state = agent.invoke(initial_state)
        
        # Execute trades
        final_state = executor.execute_portfolio_decisions(final_state)

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
            "execution_results": final_state["data"].get("execution_results", {})
        }
    except Exception as e:
        logger.error(f"Failed to run hedge fund: {e}")
        return {
            "decisions": None,
            "analyst_signals": None,
            "execution_results": None,
            "error": str(e)
        }
    finally:
        progress.stop()

def parse_hedge_fund_response(response):
    """Parse the portfolio manager's response into a decisions dictionary."""
    try:
        if isinstance(response, str):
            decisions = json.loads(response)
        else:
            decisions = response
            
        # Ensure each decision has the required fields
        parsed_decisions = {}
        for ticker, decision in decisions.items():
            parsed_decisions[ticker] = {
                "action": decision.get("action", "HOLD"),
                "quantity": decision.get("quantity", 0),
                "confidence": decision.get("confidence", 0.0),
                "reasoning": decision.get("reasoning", "No reasoning provided")
            }
        return parsed_decisions
    except Exception as e:
        logger.error(f"Error parsing portfolio manager response: {e}")
        logger.error(f"Raw response: {response}")
        return None


def run_trading_cycle(tickers: list, selected_analysts: list = None):
    """Run a single trading cycle"""
    try:
        # Create the workflow with selected analysts if specified, otherwise use default
        if selected_analysts is not None:
            workflow = create_workflow(selected_analysts)
            agent = workflow.compile()
        else:
            agent = app

        # Set dates
        end_date = os.getenv("END_DATE") or datetime.now().strftime("%Y-%m-%d")
        if not os.getenv("START_DATE"):
            # Calculate 3 months before end_date
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
        else:
            start_date = os.getenv("START_DATE")

        # Initialize portfolio
        portfolio = {
            "cash": float(os.getenv("INITIAL_CASH", "100000.0")),
            "positions": {ticker: 0 for ticker in tickers}
        }

        result = run_hedge_fund(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=os.getenv("SHOW_REASONING", "").lower() == "true",
            selected_analysts=selected_analysts,
            agent=agent
        )
        
        if result.get("status") == "error":
            logger.error(f"Trading cycle failed: {result.get('error')}")
            return {"decisions": None, "analyst_signals": None, "error": result.get('error')}
            
        return result
    except Exception as e:
        logger.error(f"Trading cycle error: {e}")
        return {"decisions": None, "analyst_signals": None, "error": str(e)}
    finally:
        # Ensure we clean up any remaining connections
        try:
            for analyst in get_analysts():
                if hasattr(analyst, 'cleanup'):
                    analyst.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AI Hedge Fund')
    parser.add_argument('--tickers', type=str, help='Comma-separated list of tickers')
    parser.add_argument('--initial-cash', type=float, help='Initial cash position')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--show-reasoning', action='store_true', help='Show detailed reasoning')
    parser.add_argument('--autonomous', action='store_true', help='Run in autonomous mode')
    parser.add_argument('--interval', type=int, help='Trading interval in minutes (autonomous mode only)')
    args = parser.parse_args()

    # Get configuration from environment or CLI args
    tickers = args.tickers or os.getenv('TICKERS', 'AAPL,MSFT,GOOGL')
    tickers = [t.strip() for t in tickers.split(',')]

    # Check for autonomous mode from CLI or env
    autonomous_mode = args.autonomous or os.getenv('AUTONOMOUS_MODE', '').lower() == 'true'

    if autonomous_mode:
        from scheduler import TradingScheduler

        # Get autonomous mode settings
        interval = args.interval or int(os.getenv('TRADING_INTERVAL', '60'))
        market_hours_only = os.getenv('MARKET_HOURS_ONLY', 'true').lower() == 'true'
        timezone = os.getenv('TRADING_TIMEZONE', 'America/New_York')

        # Initialize scheduler with configuration
        scheduler = TradingScheduler(
            tickers=tickers,
            trading_hours_only=market_hours_only,
            timezone=timezone
        )

        try:
            scheduler.start(interval_minutes=interval)
            print(f"Running in autonomous mode. Trading every {interval} minutes.")
            print(f"Market hours only: {market_hours_only}")
            print(f"Timezone: {timezone}")
            print("Press Ctrl+C to stop...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping autonomous trading...")
            scheduler.stop()
    else:
        # Interactive mode
        try:
            # Run a single trading cycle
            print(f"\nStarting trading cycle for: {', '.join(tickers)}")
            
            # Select analysts
            print("\nSelect analysts to use:")
            analysts = get_analysts()
            choices = [
                {"name": "Technical Analyst", "value": "technical_analyst"},
                {"name": "Fundamentals Analyst", "value": "fundamentals_analyst"},
                {"name": "Sentiment Analyst", "value": "sentiment_analyst"},
                {"name": "Valuation Analyst", "value": "valuation_analyst"}
            ]
            selected = questionary.checkbox(
                "Choose analysts:",
                choices=choices
            ).ask()
            
            if not selected:
                print("No analysts selected. Using all analysts.")
                selected = None

            # Run the trading cycle
            result = run_trading_cycle(tickers, selected)
            
            if result.get("error"):
                print(f"\n{Fore.RED}Trading cycle failed: {result['error']}{Style.RESET_ALL}")
                return

            # Print results
            print("\nTrading Results:")
            print("----------------")
            
            # Print analyst signals
            if result.get("analyst_signals"):
                print("\nAnalyst Signals:")
                for analyst, signals in result["analyst_signals"].items():
                    print(f"\n{analyst}:")
                    for ticker, signal in signals.items():
                        if "error" in signal:
                            print(f"  {ticker}: {Fore.RED}Error: {signal['error']}{Style.RESET_ALL}")
                        else:
                            print(f"  {ticker}: {signal}")

            # Print decisions
            if result.get("decisions"):
                print("\nTrading Decisions:")
                decisions_table = []
                for ticker, decision in result["decisions"].items():
                    decisions_table.append([
                        ticker,
                        decision.get("action", "HOLD").upper(),
                        decision.get("quantity", 0),
                        f"{decision.get('confidence', 0):.1f}%",
                        decision.get("reasoning", "No reasoning provided")
                    ])
                print(tabulate(decisions_table, headers=["Ticker", "Action", "Quantity", "Confidence", "Reasoning"]))

            # Print execution results
            if result.get("execution_results"):
                print("\nExecution Results:")
                execution_table = []
                for ticker, execution in result["execution_results"].items():
                    if execution["status"] == "success":
                        status = f"{Fore.GREEN}✓{Style.RESET_ALL}"
                        details = f"{execution['action'].upper()} {execution['quantity']} shares"
                    else:
                        status = f"{Fore.RED}✗{Style.RESET_ALL}"
                        details = f"Error: {execution.get('error', 'Unknown error')}"
                    execution_table.append([ticker, status, details])
                print(tabulate(execution_table, headers=["Ticker", "Status", "Details"]))

        except KeyboardInterrupt:
            print("\nTrading cycle interrupted.")
        except Exception as e:
            print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()

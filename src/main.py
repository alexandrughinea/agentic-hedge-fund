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

##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list = None,
):
    # Start progress tracking
    progress.start()

    try:
        # Create a new workflow if analysts are customized
        if selected_analysts is not None:
            workflow = create_workflow(selected_analysts)
            agent = workflow.compile()
        else:
            agent = app

        final_state = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Make trading decisions based on the provided data.",
                    )
                ],
                "data": {
                    "tickers": tickers,
                    "portfolio": portfolio,
                    "start_date": start_date,
                    "end_date": end_date,
                    "analyst_signals": {},
                },
                "metadata": {
                    "show_reasoning": show_reasoning,
                },
            },
        )

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
        }
    finally:
        # Stop progress tracking
        progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = ["technical_analyst", "fundamentals_analyst", "sentiment_analyst", "valuation_analyst"]

    # Dictionary of all available analysts
    analyst_nodes = {
        "technical_analyst": ("technical_analyst_agent", technical_analyst_agent),
        "fundamentals_analyst": ("fundamentals_agent", fundamentals_agent),
        "sentiment_analyst": ("sentiment_agent", sentiment_agent),
        "valuation_analyst": ("valuation_agent", valuation_agent),
    }

    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always add risk and portfolio management
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_management_agent", portfolio_management_agent)

    # Add trading executor
    trading_executor = TradingExecutor(paper=True)
    workflow.add_node("trading_executor", trading_executor.execute_portfolio_decisions)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_management_agent")
    workflow.add_edge("portfolio_management_agent", "trading_executor")
    workflow.add_edge("trading_executor", END)

    workflow.set_entry_point("start_node")
    return workflow


def parse_hedge_fund_response(response):
    import json

    try:
        return json.loads(response)
    except:
        print(f"Error parsing response: {response}")
        return None


def run_trading_cycle(tickers: list, selected_analysts: list = None):
    """Run a single trading cycle"""
    if selected_analysts is None:
        # Get analysts from environment variable
        env_analysts = os.getenv("SELECTED_ANALYSTS", "").strip()
        selected_analysts = [a.strip() for a in env_analysts.split(",")] if env_analysts else []
        
        # If no analysts configured, use all
        if not selected_analysts:
            selected_analysts = [value for _, value in ANALYST_ORDER]

    # Create the workflow with selected analysts
    workflow = create_workflow(selected_analysts)
    app = workflow.compile()

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

    # Run the hedge fund
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=os.getenv("SHOW_REASONING", "").lower() == "true",
        selected_analysts=selected_analysts,
    )
    return result


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
        if len(sys.argv) > 1:  # CLI mode
            # Show analyst selection if not configured
            env_analysts = os.getenv("SELECTED_ANALYSTS", "").strip()
            if not env_analysts:
                choices = questionary.checkbox(
                    "Select your AI analysts.",
                    choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
                    instruction="\n\nInstructions: \n1. Press Space to select/unselect analysts.\n2. Press 'a' to select/unselect all.\n3. Press Enter when done to run the hedge fund.\n",
                    validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
                    style=questionary.Style([
                        ("checkbox-selected", "fg:green"),
                        ("selected", "fg:green noinherit"),
                        ("highlighted", "noinherit"),
                        ("pointer", "noinherit"),
                    ]),
                ).ask()
                
                if choices:
                    selected_analysts = choices
                    print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}\n")
                else:
                    selected_analysts = None
            else:
                selected_analysts = None
        else:
            selected_analysts = None

        result = run_trading_cycle(tickers, selected_analysts)
        print_trading_output(result)

if __name__ == "__main__":
    main()

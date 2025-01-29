from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Back, Style, init
import questionary
import os
import sys

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

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tabulate import tabulate

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    import json

    try:
        return json.loads(response)
    except:
        print(f"Error parsing response: {response}")
        return None


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


if __name__ == "__main__":
    # Check if any command line arguments were provided
    cli_mode = len(sys.argv) > 1
    
    # Get analysts from environment variable
    env_analysts = os.getenv("SELECTED_ANALYSTS", "").strip()
    selected_analysts = [a.strip() for a in env_analysts.split(",")] if env_analysts else []
    
    # Only show CLI interface if in CLI mode and no analysts configured
    if cli_mode and not selected_analysts:
        parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
        parser.add_argument(
            "--initial-cash",
            type=float,
            default=float(os.getenv("INITIAL_CASH", "100000.0")),
            help="Initial cash position. Defaults to env INITIAL_CASH or 100000.0"
        )
        parser.add_argument(
            "--tickers",
            type=str,
            default=os.getenv("TICKERS"),
            help="Comma-separated list of stock ticker symbols. Defaults to env TICKERS"
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default=os.getenv("START_DATE"),
            help="Start date (YYYY-MM-DD). Defaults to env START_DATE or 3 months before end date",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=os.getenv("END_DATE"),
            help="End date (YYYY-MM-DD). Defaults to env END_DATE or today"
        )
        parser.add_argument(
            "--show-reasoning",
            action="store_true",
            default=os.getenv("SHOW_REASONING", "").lower() == "true",
            help="Show reasoning from each agent. Defaults to env SHOW_REASONING"
        )

        args = parser.parse_args()

        if not args.tickers:
            raise ValueError("No tickers specified. Set either --tickers argument or TICKERS environment variable")

        # Parse tickers from comma-separated string
        tickers = [ticker.strip() for ticker in args.tickers.split(",")]

        # Only show analyst selection if no analysts configured in env
        choices = questionary.checkbox(
            "Select your AI analysts.",
            choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
            instruction="\n\nInstructions: \n1. Press Space to select/unselect analysts.\n2. Press 'a' to select/unselect all.\n3. Press Enter when done to run the hedge fund.\n",
            validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
            style=questionary.Style(
                [
                    ("checkbox-selected", "fg:green"),
                    ("selected", "fg:green noinherit"),
                    ("highlighted", "noinherit"),
                    ("pointer", "noinherit"),
                ]
            ),
        ).ask()

        if not choices:
            print("You must select at least one analyst. Using all analysts by default.")
            selected_analysts = [value for _, value in ANALYST_ORDER]
        else:
            selected_analysts = choices
            print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}\n")
    else:
        # Use environment variables for everything
        tickers = [ticker.strip() for ticker in os.getenv("TICKERS", "").split(",")]
        if not tickers or not tickers[0]:
            raise ValueError("No tickers specified in TICKERS environment variable")
            
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
    print_trading_output(result)

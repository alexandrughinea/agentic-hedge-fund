from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import questionary
import os
import sys
import argparse

import matplotlib.pyplot as plt
import pandas as pd
from colorama import Fore, Style, init
from dotenv import load_dotenv

from utils.analysts import ANALYST_ORDER
from main import run_hedge_fund
from tools.api import (
    get_company_news,
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
    search_line_items,
)
from utils.display import print_backtest_results, format_backtest_row

# Load environment variables
load_dotenv()

init(autoreset=True)


class Backtester:
    def __init__(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        selected_analysts: list = None,
        show_reasoning: bool = False
    ):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.selected_analysts = selected_analysts
        self.show_reasoning = show_reasoning
        self.portfolio = {
            "cash": initial_capital,
            "positions": {ticker: 0 for ticker in tickers},
            "realized_gains": {ticker: 0 for ticker in tickers},
            "cost_basis": {ticker: 0 for ticker in tickers},
        }
        self.portfolio_values = []

    def prefetch_data(self):
        """Pre-fetch all data needed for the backtest period."""
        print("\nPre-fetching data for the entire backtest period...")

        # Convert end_date string to datetime, perform arithmetic, then back to string
        end_date_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        start_date_dt = end_date_dt - relativedelta(years=1)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        for ticker in self.tickers:
            # Fetch price data for the entire period, plus 1 year
            get_prices(ticker, start_date_str, self.end_date)

            # Fetch financial metrics
            get_financial_metrics(ticker, self.end_date, limit=10)

            # Fetch insider trades for the entire period
            get_insider_trades(ticker, self.end_date, start_date=self.start_date, limit=1000)

            # Fetch company news for the entire period
            get_company_news(ticker, self.end_date, start_date=self.start_date, limit=1000)

            # Fetch common line items used by valuation agent
            search_line_items(
                ticker,
                [
                    "free_cash_flow",
                    "net_income",
                    "depreciation_and_amortization",
                    "capital_expenditure",
                    "working_capital",
                ],
                self.end_date,
                period="ttm",
                limit=2,  # Need current and previous for working capital change
            )

        print("Data pre-fetch complete.")

    def run_backtest(self):
        """Run the backtest simulation."""
        print(f"\n{Fore.CYAN}Starting backtest simulation...{Style.RESET_ALL}")
        print(f"Period: {self.start_date} to {self.end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Tickers: {', '.join(self.tickers)}")
        
        # Pre-fetch data
        self.prefetch_data()
        
        # Initialize tracking variables
        current_date = datetime.strptime(self.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(self.end_date, "%Y-%m-%d")
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Run the hedge fund strategy
            result = run_hedge_fund(
                tickers=self.tickers,
                start_date=self.start_date,
                end_date=date_str,
                portfolio=self.portfolio,
                show_reasoning=self.show_reasoning,
                selected_analysts=self.selected_analysts
            )
            
            # Update portfolio based on the result
            if result:
                self.portfolio = result
                
            # Record portfolio value
            total_value = self.portfolio["cash"]
            for ticker in self.tickers:
                price_data = get_prices(ticker, date_str, date_str)
                if price_data:
                    price = price_data[0].close
                    total_value += self.portfolio["positions"][ticker] * price
            
            self.portfolio_values.append({
                "date": date_str,
                "value": total_value
            })
            
            # Move to next day
            current_date += timedelta(days=1)
            
        print(f"\n{Fore.GREEN}Backtest completed successfully!{Style.RESET_ALL}")

    def analyze_performance(self):
        """Analyze the backtest performance."""
        if not self.portfolio_values:
            print(f"{Fore.RED}No portfolio values to analyze{Style.RESET_ALL}")
            return pd.DataFrame()

        # Create performance DataFrame
        performance_df = pd.DataFrame(self.portfolio_values)
        performance_df.set_index("date", inplace=True)
        performance_df.index = pd.to_datetime(performance_df.index)
        performance_df.columns = ["Portfolio Value"]

        # Calculate metrics
        total_return = (performance_df["Portfolio Value"].iloc[-1] / performance_df["Portfolio Value"].iloc[0] - 1) * 100
        print(f"\nTotal Return: {Fore.GREEN if total_return >= 0 else Fore.RED}{total_return:.2f}%{Style.RESET_ALL}")

        # Plot results
        plt.figure(figsize=(12, 6))
        plt.plot(performance_df.index, performance_df["Portfolio Value"], color="blue")
        plt.title("Portfolio Value Over Time")
        plt.ylabel("Portfolio Value ($)")
        plt.xlabel("Date")
        plt.grid(True)
        plt.show()

        # Calculate additional metrics
        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change()
        mean_daily_return = performance_df["Daily Return"].mean()
        std_daily_return = performance_df["Daily Return"].std()
        sharpe_ratio = (mean_daily_return / std_daily_return) * (252**0.5) if std_daily_return != 0 else 0
        
        # Calculate drawdown
        rolling_max = performance_df["Portfolio Value"].cummax()
        drawdown = performance_df["Portfolio Value"] / rolling_max - 1
        max_drawdown = drawdown.min()

        # Print metrics
        print(f"\nPerformance Metrics:")
        print(f"Sharpe Ratio: {Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}")
        print(f"Maximum Drawdown: {Fore.RED}{max_drawdown * 100:.2f}%{Style.RESET_ALL}")

        return performance_df


if __name__ == "__main__":
    # Check if any command line arguments were provided
    cli_mode = len(sys.argv) > 1
    
    # Get analysts from environment variable
    env_analysts = os.getenv("SELECTED_ANALYSTS", "").strip()
    selected_analysts = [a.strip() for a in env_analysts.split(",")] if env_analysts else []
    
    # Get other settings from environment
    env_tickers = os.getenv("TICKERS", "").strip()
    tickers = [t.strip() for t in env_tickers.split(",")] if env_tickers else []
    
    # Only show CLI interface if in CLI mode
    if cli_mode:
        parser = argparse.ArgumentParser(description="Run backtesting simulation")
        parser.add_argument(
            "--tickers",
            type=str,
            default=env_tickers,
            help="Comma-separated list of stock ticker symbols (e.g., AAPL,MSFT,GOOGL)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=os.getenv("END_DATE", datetime.now().strftime("%Y-%m-%d")),
            help="End date in YYYY-MM-DD format",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default=os.getenv("START_DATE", (datetime.now() - relativedelta(months=12)).strftime("%Y-%m-%d")),
            help="Start date in YYYY-MM-DD format",
        )
        parser.add_argument(
            "--initial-capital",
            type=float,
            default=float(os.getenv("INITIAL_CASH", "100000.0")),
            help="Initial capital amount",
        )
        parser.add_argument(
            "--show-reasoning",
            action="store_true",
            default=os.getenv("SHOW_REASONING", "").lower() == "true",
            help="Show reasoning from each analyst",
        )

        args = parser.parse_args()

        if args.tickers:
            tickers = [ticker.strip() for ticker in args.tickers.split(",")]
        
        if not tickers:
            raise ValueError("No tickers specified. Set either --tickers argument or TICKERS environment variable")

        # Only show analyst selection if no analysts configured in env
        if not selected_analysts:
            choices = questionary.checkbox(
                "Select your AI analysts.",
                choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
                instruction="\n\nInstructions: \n1. Press Space to select/unselect analysts.\n2. Press 'a' to select/unselect all.\n3. Press Enter when done to run the backtest.\n",
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
                
        start_date = args.start_date
        end_date = args.end_date
        initial_capital = args.initial_capital
        show_reasoning = args.show_reasoning
    else:
        # Use environment variables
        if not tickers:
            raise ValueError("No tickers specified in TICKERS environment variable")
            
        # If no analysts configured, use all
        if not selected_analysts:
            selected_analysts = [value for _, value in ANALYST_ORDER]
            
        # Get other settings from env
        end_date = os.getenv("END_DATE") or datetime.now().strftime("%Y-%m-%d")
        if not os.getenv("START_DATE"):
            # Calculate default start date (1 year before end date)
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (end_date_obj - relativedelta(months=12)).strftime("%Y-%m-%d")
        else:
            start_date = os.getenv("START_DATE")
            
        initial_capital = float(os.getenv("INITIAL_CASH", "100000.0"))
        show_reasoning = os.getenv("SHOW_REASONING", "").lower() == "true"

    # Create and run backtester
    backtester = Backtester(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        selected_analysts=selected_analysts,
        show_reasoning=show_reasoning
    )

    # Run the backtesting process
    backtester.run_backtest()
    performance_df = backtester.analyze_performance()

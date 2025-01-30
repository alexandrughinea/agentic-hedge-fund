from colorama import Fore, Style
from .analysts import ANALYST_ORDER
import os
from rich.console import Console
from rich.table import Table
from typing import Any, Dict

console = Console()


def sort_analyst_signals(signals):
    """Sort analyst signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {agent: idx for idx, agent in enumerate(ANALYST_ORDER)}
    analyst_order["risk_management_agent"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0].lower().replace(" ", "_"), 999))


def print_trading_output(result: Dict[str, Any]) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    decisions = result.get("decisions")
    if not decisions:
        console.print("[red]No trading decisions available[/]")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        console.print(f"\n[white bold]Analysis for [cyan]{ticker}[/]")
        console.print("[white bold]" + "=" * 50 + "[/]")

        # Prepare analyst signals table for this ticker
        signals_table = Table(title=f"[white bold]ANALYST SIGNALS: [cyan]{ticker}[/]")
        signals_table.add_column("Analyst", style="cyan")
        signals_table.add_column("Signal", justify="center")
        signals_table.add_column("Confidence", justify="right", style="yellow")

        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()

            signal_style = {
                "BULLISH": "green",
                "BEARISH": "red",
                "NEUTRAL": "yellow",
            }.get(signal_type, "white")

            signals_table.add_row(agent_name, f"[{signal_style}]{signal_type}[/]", f"{signal.get('confidence')}%")

        # Sort and display signals
        console.print(signals_table)

        # Print Trading Decision Table
        decision_table = Table(title=f"[white bold]TRADING DECISION: [cyan]{ticker}[/]")
        decision_table.add_column("Metric", style="white")
        decision_table.add_column("Value", justify="right")

        action = decision.get("action", "").upper()
        action_style = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(action, "white")

        decision_table.add_row("Action", f"[{action_style}]{action}[/]")
        decision_table.add_row("Quantity", f"[{action_style}]{decision.get('quantity', 'N/A')}[/]")

        # Add confidence if available and valid
        confidence = decision.get("confidence")
        if confidence is not None and isinstance(confidence, (int, float)):
            decision_table.add_row("Confidence", f"{confidence:.1f}%")
        else:
            decision_table.add_row("Confidence", "N/A")

        console.print(decision_table)

        # Print Reasoning
        console.print(f"\n[white bold]Reasoning:[/] [cyan]{decision.get('reasoning')}[/]")

    # Print Portfolio Summary
    portfolio_table = Table(title="[white bold]PORTFOLIO SUMMARY[/]")
    portfolio_table.add_column("Ticker", style="cyan")
    portfolio_table.add_column("Action", justify="center")
    portfolio_table.add_column("Quantity", justify="right")
    portfolio_table.add_column("Confidence", justify="right", style="yellow")

    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_style = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(action, "white")

        portfolio_table.add_row(ticker, f"[{action_style}]{action}[/]", f"[{action_style}]{decision.get('quantity')}[/]", f"{decision.get('confidence', 0):.1f}%")

    console.print("\n", portfolio_table)


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    # Print the table with just ticker rows
    table = Table(title="Backtest Results")
    table.add_column("Date", style="white")
    table.add_column("Ticker", style="cyan")
    table.add_column("Action", justify="center")
    table.add_column("Quantity", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("Position Value", justify="right", style="yellow")
    table.add_column("Bullish", justify="right", style="green")
    table.add_column("Bearish", justify="right", style="red")
    table.add_column("Neutral", justify="right", style="blue")

    for row in ticker_rows:
        table.add_row(
            row[0],
            f"[cyan]{row[1]}[/]",
            f"[{Fore.GREEN if row[2] == 'BUY' else Fore.RED if row[2] == 'SELL' else Fore.YELLOW if row[2] == 'HOLD' else Fore.WHITE}]{row[2]}[/]",
            f"[{Fore.GREEN if row[2] == 'BUY' else Fore.RED if row[2] == 'SELL' else Fore.YELLOW if row[2] == 'HOLD' else Fore.WHITE}]{row[3]:,.0f}[/]",
            f"{row[4]:,.2f}",
            f"{row[5]:,.0f}",
            f"{row[6]:,.2f}",
            f"{row[7]}",
            f"{row[8]}",
            f"{row[9]}",
        )

    console.print(table)

    # Display latest portfolio summary
    if summary_rows:
        latest_summary = summary_rows[-1]
        console.print(f"\n[white bold]PORTFOLIO SUMMARY:[/]")
        console.print(f"Cash Balance: [cyan]${float(latest_summary[7].split('$')[1].split(Style.RESET_ALL)[0].replace(',', '')):,.2f}[/]")
        console.print(f"Total Position Value: [yellow]${float(latest_summary[6].split('$')[1].split(Style.RESET_ALL)[0].replace(',', '')):,.2f}[/]")
        console.print(f"Total Value: [white]${float(latest_summary[8].split('$')[1].split(Style.RESET_ALL)[0].replace(',', '')):,.2f}[/]")
        console.print(f"Return: {latest_summary[9]}")

    # Add vertical spacing for progress display
    console.print("\n" * 8)  # Add 8 blank lines for progress display


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    shares_owned: float,
    position_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
) -> list[Any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "BUY": Fore.GREEN,
        "SELL": Fore.RED,
        "HOLD": Fore.YELLOW,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}",
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]

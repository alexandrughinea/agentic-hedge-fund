import json
import os
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI

from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from utils.progress import progress
import logging

logger = logging.getLogger(__name__)

class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders for multiple tickers"""
    try:
        # Get the portfolio and analyst signals
        portfolio = state["data"]["portfolio"]
        analyst_signals = state["data"]["analyst_signals"]
        tickers = state["data"]["tickers"]

        progress.update_status("portfolio_management_agent", None, "Analyzing signals")

        # Get position limits, current prices, and signals for every ticker
        position_limits = {}
        current_prices = {}
        max_shares = {}
        signals_by_ticker = {}
        for ticker in tickers:
            try:
                progress.update_status("portfolio_management_agent", ticker, "Processing analyst signals")

                # Check if any analyst had errors
                for agent_name, signals in analyst_signals.items():
                    if ticker in signals and "error" in signals[ticker]:
                        error_msg = signals[ticker]["error"]
                        progress.update_status("portfolio_management_agent", ticker, f"\033[91mError from {agent_name}: {error_msg}\033[0m")
                        raise ValueError(f"Error from {agent_name}: {error_msg}")

                # Collect signals for this ticker
                signals_by_ticker[ticker] = {}
                for agent_name, signals in analyst_signals.items():
                    if ticker in signals:
                        signals_by_ticker[ticker][agent_name] = signals[ticker]

            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                progress.update_status("portfolio_management_agent", ticker, f"Error: {str(e)}")
                continue

        # Create prompt for the LLM
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a portfolio manager making trading decisions based on analyst signals.
                For each ticker, decide whether to buy, sell, or hold based on the signals and confidence levels from different analysts.
                Consider the maximum allowed position size and current portfolio holdings.
                Provide clear reasoning for each decision."""),
            ("human", "{signals}")
        ])

        # Make trading decisions
        progress.update_status("portfolio_management_agent", None, "Making trading decisions")
        decisions = make_decision(prompt, signals_by_ticker)
        
        if not decisions:
            progress.update_status("portfolio_management_agent", None, "Error: Failed to make decisions")
            return state
            
        # Update state with decisions
        state["messages"].append(
            HumanMessage(content=json.dumps(decisions))
        )
        
        progress.update_status("portfolio_management_agent", None, "Done")
        return state

    except Exception as e:
        logger.error(f"Portfolio management error: {str(e)}")
        progress.update_status("portfolio_management_agent", None, f"Error: {str(e)}")
        return state


def make_decision(prompt, signals_by_ticker):
    """Make trading decisions using LLM."""
    try:
        # Initialize LLM
        model = ChatOpenAI(
            model=os.getenv("GPT_MODEL", "gpt-4"),
            temperature=float(os.getenv("GPT_TEMPERATURE", "0.1")),
        )

        # Format signals for the LLM
        formatted_signals = json.dumps(signals_by_ticker, indent=2)

        # Get LLM response
        response = model.invoke(
            prompt.format_messages(signals=formatted_signals)
        )

        # Parse the response
        try:
            decisions = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response.content}")
            return None

        # Validate and format decisions
        formatted_decisions = {}
        for ticker, decision in decisions.items():
            # Ensure required fields are present
            action = decision.get("action", "hold").lower()
            quantity = int(decision.get("quantity", 0))
            confidence = float(decision.get("confidence", 0.0))
            reasoning = decision.get("reasoning", "No reasoning provided")

            # Validate action
            if action not in ["buy", "sell", "hold"]:
                action = "hold"

            # Validate quantity and confidence
            quantity = max(0, quantity)
            confidence = max(0.0, min(100.0, confidence))

            formatted_decisions[ticker] = {
                "action": action,
                "quantity": quantity,
                "confidence": confidence,
                "reasoning": reasoning
            }

        return formatted_decisions

    except Exception as e:
        logger.error(f"Error in make_decision: {str(e)}")
        return None

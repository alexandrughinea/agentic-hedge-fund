import json
import os
from typing import Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai.chat_models import ChatOpenAI
from pydantic import BaseModel, Field
from typing_extensions import Literal
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
import logging

logger = logging.getLogger(__name__)

class PortfolioDecision(BaseModel):
    """Trading decision for a specific ticker."""
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(description="Number of shares to trade", ge=0)
    confidence: float = Field(description="Confidence level in the decision", ge=0.0, le=100.0)
    reasoning: str = Field(description="Explanation for the trading decision")

class PortfolioDecisions(BaseModel):
    """Collection of trading decisions for multiple tickers."""
    decisions: Dict[str, PortfolioDecision] = Field(
        description="Map of ticker symbols to their trading decisions"
    )

def make_decision(
    signals_by_ticker: Dict,
    portfolio: Optional[Dict] = None,
    position_limits: Optional[Dict] = None
) -> Optional[Dict[str, Dict]]:
    """
    Generate trading decisions based on market signals and portfolio state.
    
    Args:
        signals_by_ticker: Dictionary of market signals per ticker
        portfolio: Optional current portfolio state
        position_limits: Optional position limits per ticker
        
    Returns:
        Dictionary mapping tickers to trading decisions, or None if an error occurs
    """
    try:
        # Initialize LLM
        model = ChatOpenAI(
            model=os.getenv("GPT_MODEL", "gpt-4o"),
            temperature=float(os.getenv("GPT_TEMPERATURE", "0.1")),
        )

        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a portfolio manager making trading decisions based on analyst signals.
                For each ticker, decide whether to buy, sell, or hold based on the signals and confidence levels.
                Consider the maximum allowed position size and current portfolio holdings.
                Return your decisions in the following JSON format:
                {format_instructions}"""),
            ("human", "Here are the signals to analyze:\n{signals}")
        ])

        # Add portfolio context if available
        messages = []
        if portfolio:
            messages.append(
                HumanMessage(content=f"Current portfolio holdings:\n{json.dumps(portfolio, indent=2)}")
            )

        # Setup parser and format signals
        parser = PydanticOutputParser(pydantic_object=PortfolioDecisions)
        formatted_signals = json.dumps(signals_by_ticker, indent=2)

        # Get LLM response
        response = model.invoke(prompt.format_messages(
            format_instructions=parser.get_format_instructions(),
            signals=formatted_signals
        ))

        # Parse response and apply position limits
        decisions = parser.parse(response.content)
        decisions_dict = {}
        
        for ticker, decision in decisions.decisions.items():
            decision_dict = decision.dict()
            if position_limits and ticker in position_limits:
                limit = position_limits[ticker]
                if decision.quantity > limit:
                    decision_dict["quantity"] = limit
            decisions_dict[ticker] = decision_dict

        return decisions_dict

    except Exception as e:
        logger.error(f"Error in make_decision: {str(e)}")
        return None

def portfolio_management_agent(state: AgentState) -> AgentState:
    """Makes final trading decisions and generates orders for multiple tickers"""
    try:
        # Extract data from state
        portfolio = state["data"]["portfolio"]
        analyst_signals = state["data"]["analyst_signals"]
        tickers = state["data"]["tickers"]
        position_limits = state["data"].get("position_limits", {})

        progress.update_status("portfolio_management_agent", None, "Analyzing signals")

        # Process signals for each ticker
        signals_by_ticker = {}
        for ticker in tickers:
            try:
                # Check for analyst errors
                for agent_name, signals in analyst_signals.items():
                    if ticker in signals and "error" in signals[ticker]:
                        error_msg = signals[ticker]["error"]
                        logger.error(f"Error from {agent_name} for {ticker}: {error_msg}")
                        continue

                # Collect valid signals
                ticker_signals = {
                    agent_name: signals[ticker]
                    for agent_name, signals in analyst_signals.items()
                    if ticker in signals and "error" not in signals[ticker]
                }

                if ticker_signals:
                    signals_by_ticker[ticker] = ticker_signals

            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                continue

        # Make trading decisions
        progress.update_status("portfolio_management_agent", None, "Making trading decisions")
        decisions = make_decision(
            signals_by_ticker=signals_by_ticker,
            portfolio=portfolio,
            position_limits=position_limits
        )

        if not decisions:
            logger.error("Failed to generate trading decisions")
            return state
        
        progress.update_status("portfolio_management_agent", None, "Done")

        # Update state with decisions
        state["decisions"] = decisions
        state["messages"].append(HumanMessage(content=json.dumps(decisions)))
        show_agent_reasoning(state, "portfolio_management_agent")
        
        # Mark each ticker with a decision as Done
        for ticker in decisions:
            progress.update_status("portfolio_management_agent", ticker, "Done")
        
        return state

    except Exception as e:
        logger.error(f"Portfolio management error: {str(e)}")
        return state

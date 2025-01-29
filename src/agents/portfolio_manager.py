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

                # Get position limits and current prices for the ticker
                risk_data = analyst_signals.get("risk_management_agent", {}).get(ticker, {})
                if not risk_data:
                    raise ValueError("Missing risk management data")
                
                position_limits[ticker] = risk_data.get("remaining_position_limit")
                if position_limits[ticker] is None:
                    raise ValueError("Missing position limit data")
                    
                current_prices[ticker] = risk_data.get("current_price")
                if not current_prices[ticker]:
                    raise ValueError("Missing current price data")

                # Calculate maximum shares allowed based on position limit and price
                if current_prices[ticker] > 0:
                    max_shares[ticker] = int(position_limits[ticker] / current_prices[ticker])
                else:
                    raise ValueError("Invalid current price (zero or negative)")

                # Collect signals from all analysts
                signals_by_ticker[ticker] = {}
                for agent, signals in analyst_signals.items():
                    if ticker in signals:
                        signals_by_ticker[ticker][agent] = signals[ticker]

                progress.update_status("portfolio_management_agent", ticker, "Generating decision")

            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                progress.update_status("portfolio_management_agent", ticker, f"\033[91mError: {str(e)}\033[0m")
                # Default to HOLD with 0 quantity on error
                signals_by_ticker[ticker] = {
                    "error": str(e),
                    "decision": PortfolioDecision(
                        action="hold",
                        quantity=0,
                        confidence=0,
                        reasoning=f"Error occurred: {str(e)}"
                    )
                }

        try:
            # Generate the prompt for the LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a portfolio manager making trading decisions based on analyst signals.
                For each ticker, decide whether to buy, sell, or hold based on the signals and confidence levels from different analysts.
                Consider the maximum allowed position size and current portfolio holdings.
                Provide clear reasoning for each decision."""),
                ("human", "{signals}")
            ])

            # Make the decision using the LLM
            decisions = make_decision(prompt, signals_by_ticker)
            
            # Validate and process the decisions
            portfolio_decisions = {}
            for ticker, decision in decisions.items():
                try:
                    # Ensure the decision respects position limits
                    if decision.action != "hold":
                        max_allowed = max_shares.get(ticker, 0)
                        if decision.quantity > max_allowed:
                            logger.warning(f"Reducing {ticker} quantity from {decision.quantity} to {max_allowed} due to position limits")
                            decision.quantity = max_allowed
                            decision.reasoning += f"\nQuantity adjusted to {max_allowed} due to position limits."
                    
                    portfolio_decisions[ticker] = decision
                    progress.update_status("portfolio_management_agent", ticker, "Done")
                
                except Exception as e:
                    logger.error(f"Error processing decision for {ticker}: {str(e)}")
                    progress.update_status("portfolio_management_agent", ticker, f"\033[91mError processing decision: {str(e)}\033[0m")
                    # Default to HOLD on error
                    portfolio_decisions[ticker] = PortfolioDecision(
                        action="hold",
                        quantity=0,
                        confidence=0,
                        reasoning=f"Error processing decision: {str(e)}"
                    )

            # Create the portfolio management message
            message = HumanMessage(
                content=json.dumps({ticker: decision.model_dump() for ticker, decision in portfolio_decisions.items()}),
                name="portfolio_management",
            )

            # Show reasoning if flag is set
            if state["metadata"]["show_reasoning"]:
                show_agent_reasoning(portfolio_decisions, "Portfolio Management Agent")

            return {
                "messages": state["messages"] + [message],
                "data": {
                    **state["data"],
                    "portfolio_decisions": portfolio_decisions
                }
            }

        except Exception as e:
            logger.error(f"Error in decision making: {str(e)}")
            progress.update_status("portfolio_management_agent", None, f"\033[91mError in decision making: {str(e)}\033[0m")
            # Return empty decisions on error
            return {
                "messages": state["messages"],
                "data": {
                    **state["data"],
                    "portfolio_decisions": {
                        ticker: PortfolioDecision(
                            action="hold",
                            quantity=0,
                            confidence=0,
                            reasoning=f"Error in decision making: {str(e)}"
                        ) for ticker in tickers
                    }
                }
            }

    except Exception as e:
        logger.error(f"Critical error in portfolio management: {str(e)}")
        progress.update_status("portfolio_management_agent", None, f"\033[91mCritical error: {str(e)}\033[0m")
        return {
            "messages": state["messages"],
            "data": state["data"]
        }


def make_decision(prompt, signals_by_ticker):
    """Make trading decisions using LLM"""
    try:
        # Use gpt-3.5-turbo as default model
        model = os.getenv("PORTFOLIO_MANAGER_MODEL", "gpt-3.5-turbo")
        llm = ChatOpenAI(
            model=model,
            temperature=0.1,
            request_timeout=30
        )

        # Format the input data
        formatted_signals = {}
        for ticker, signals in signals_by_ticker.items():
            if isinstance(signals, dict):
                formatted_signals[ticker] = {
                    agent: {
                        k: v for k, v in signal.items() 
                        if k not in ['error', 'reasoning'] and not isinstance(v, (dict, list))
                    } 
                    for agent, signal in signals.items()
                    if isinstance(signal, dict)
                }

        # Get the LLM response
        try:
            response = llm.invoke(prompt.format_messages(signals=json.dumps(formatted_signals, indent=2)))
        except Exception as e:
            if "model_not_found" in str(e):
                # Try fallback model
                logger.warning(f"Model {model} not found, falling back to gpt-3.5-turbo")
                llm = ChatOpenAI(
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    request_timeout=30
                )
                response = llm.invoke(prompt.format_messages(signals=json.dumps(formatted_signals, indent=2)))
            else:
                raise
        
        try:
            # Parse the response
            content = response.content
            if isinstance(content, str):
                decisions_dict = json.loads(content)
            else:
                decisions_dict = content

            # Validate the response structure
            if not isinstance(decisions_dict, dict):
                raise ValueError(f"Expected dict response, got {type(decisions_dict)}")
            
            if 'decisions' not in decisions_dict:
                raise ValueError("Response missing 'decisions' key")
            
            decisions = decisions_dict['decisions']
            if not isinstance(decisions, dict):
                raise ValueError(f"Expected dict for decisions, got {type(decisions)}")
            
            # Convert to portfolio decisions
            portfolio_decisions = {}
            
            for ticker, decision in decisions.items():
                if not isinstance(decision, dict):
                    raise ValueError(f"Expected dict for decision, got {type(decision)}")
                
                required_fields = ['action', 'quantity', 'confidence', 'reasoning']
                missing_fields = [f for f in required_fields if f not in decision]
                if missing_fields:
                    raise ValueError(f"Decision missing required fields: {missing_fields}")
                
                try:
                    portfolio_decisions[ticker] = PortfolioDecision(
                        action=str(decision['action']).lower(),
                        quantity=int(float(decision['quantity'])),
                        confidence=float(decision['confidence']),
                        reasoning=str(decision['reasoning'])
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value in decision for {ticker}: {str(e)}")
            
            if not portfolio_decisions:
                raise ValueError("No valid decisions in response")
            
            return portfolio_decisions

        except (json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.error(f"Raw response: {response.content}")
            raise ValueError(f"Portfolio Management failed: {str(e)}")

    except Exception as e:
        logger.error(f"Error in Portfolio Management: {str(e)}")
        raise ValueError(f"Portfolio Management failed: {str(e)}")

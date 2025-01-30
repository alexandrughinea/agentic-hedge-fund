"""Constants and utilities related to analysts configuration."""

# Order of analysts in the workflow
ANALYST_ORDER = ["technical_analyst_agent", "fundamentals_agent", "sentiment_analysis_agent", "valuation_agent"]


def get_agent_display_name(technical_name: str) -> str:
    """Convert technical name to display name (e.g., technical_analyst_agent -> Technical Analyst)"""
    return technical_name.replace("_agent", "").replace("_", " ").title()

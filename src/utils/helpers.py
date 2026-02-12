"""
Utility helper functions.
"""

from datetime import datetime
from typing import Optional


def format_usd(amount: float) -> str:
    """Format amount as USD currency."""
    return f"${amount:,.2f}"


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"{value:.2%}"


def calculate_pnl_percentage(entry: float, exit: float) -> float:
    """Calculate P&L percentage."""
    if entry == 0:
        return 0.0
    return ((exit - entry) / entry) * 100


def time_until(target_time: datetime) -> int:
    """
    Calculate seconds until target time.

    Returns:
        Seconds remaining (0 if target is in the past)
    """
    delta = (target_time - datetime.utcnow()).total_seconds()
    return max(0, int(delta))


def format_time_remaining(seconds: int) -> str:
    """Format seconds as human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

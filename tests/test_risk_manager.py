"""
Unit tests for risk manager.

TODO: Implement comprehensive test coverage
"""

import pytest
from datetime import datetime
from src.core.risk_manager import RiskManager, PositionInfo, RiskState


class TestRiskManager:
    """Test cases for RiskManager class."""

    def test_initialization(self):
        """Test risk manager initializes correctly."""
        rm = RiskManager(initial_balance=100.0)
        assert rm.state.total_balance == 100.0
        assert rm.state.available_balance == 100.0
        assert rm.state.total_trades == 0

    def test_calculate_position_size(self):
        """Test position size calculation."""
        rm = RiskManager(initial_balance=100.0, max_position_pct=0.05)
        size = rm.calculate_position_size()
        assert size == 5.0  # 5% of 100

    def test_can_open_position_success(self):
        """Test that valid position can be opened."""
        rm = RiskManager(initial_balance=100.0)
        can_open, reason = rm.can_open_position(5.0)
        assert can_open is True
        assert reason == "OK"

    def test_can_open_position_insufficient_balance(self):
        """Test rejection when balance is insufficient."""
        rm = RiskManager(initial_balance=10.0)
        can_open, reason = rm.can_open_position(50.0)
        assert can_open is False
        assert "Onvoldoende balance" in reason

    def test_can_open_position_too_large(self):
        """Test rejection when position is too large."""
        rm = RiskManager(initial_balance=100.0, max_position_pct=0.05)
        can_open, reason = rm.can_open_position(10.0)  # 10% > 5% max
        assert can_open is False
        assert "te groot" in reason

    def test_open_position(self):
        """Test opening a position."""
        rm = RiskManager(initial_balance=100.0)
        position = rm.open_position(
            market_id="test-market",
            token_id="test-token",
            direction="up",
            entry_price=0.80,
            size_usd=5.0
        )

        assert position.market_id == "test-market"
        assert position.size_usd == 5.0
        assert rm.state.available_balance == 95.0
        assert rm.state.locked_in_positions == 5.0

    def test_close_position_win(self):
        """Test closing a winning position."""
        rm = RiskManager(initial_balance=100.0)

        # Open position
        rm.open_position(
            market_id="test-market",
            token_id="test-token",
            direction="up",
            entry_price=0.80,
            size_usd=5.0
        )

        # Close with win
        position = rm.close_position(
            market_id="test-market",
            exit_price=1.0,
            won=True
        )

        assert position.pnl > 0
        assert rm.state.winning_trades == 1
        assert rm.state.consecutive_wins == 1
        assert rm.state.consecutive_losses == 0

    def test_close_position_loss(self):
        """Test closing a losing position."""
        rm = RiskManager(initial_balance=100.0)

        # Open position
        rm.open_position(
            market_id="test-market",
            token_id="test-token",
            direction="up",
            entry_price=0.80,
            size_usd=5.0
        )

        # Close with loss
        position = rm.close_position(
            market_id="test-market",
            exit_price=0.0,
            won=False
        )

        assert position.pnl < 0
        assert rm.state.losing_trades == 1
        assert rm.state.consecutive_losses == 1
        assert rm.state.consecutive_wins == 0

    def test_pause_after_max_losses(self):
        """Test that pause is triggered after max consecutive losses."""
        rm = RiskManager(initial_balance=100.0, max_consecutive_losses=3)

        # Simulate 3 consecutive losses
        for i in range(3):
            rm.open_position(
                market_id=f"market-{i}",
                token_id=f"token-{i}",
                direction="up",
                entry_price=0.80,
                size_usd=5.0
            )
            rm.close_position(
                market_id=f"market-{i}",
                exit_price=0.0,
                won=False
            )

        assert rm.is_paused is True

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        rm = RiskManager(initial_balance=100.0)
        assert rm.state.win_rate == 0.0  # No trades yet

        # Simulate some trades
        rm._state.total_trades = 10
        rm._state.winning_trades = 7
        assert rm.state.win_rate == 0.7


# TODO: Add more test cases
# - Test balance updates
# - Test position size recalculation
# - Test has_open_position
# - Test get_open_position

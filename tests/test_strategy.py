"""
Unit tests for trading strategy.

TODO: Implement comprehensive test coverage
"""

import pytest
from datetime import datetime, timedelta
from src.core.strategy import (
    TradingStrategy,
    MarketState,
    TradeDecision,
    TradeSignal
)


def create_test_market(
    up_prob: float = 0.85,
    time_remaining: int = 120,
    btc_current: float = 95000.0,
    btc_target: float = 94950.0
) -> MarketState:
    """Helper to create test market state."""
    return MarketState(
        market_id="test-market",
        token_id_up="token-up",
        token_id_down="token-down",
        bitcoin_current_price=btc_current,
        bitcoin_target_price=btc_target,
        up_probability=up_prob,
        down_probability=1.0 - up_prob,
        time_remaining_seconds=time_remaining,
        market_end_time=datetime.utcnow() + timedelta(seconds=time_remaining),
        up_bid=0.84,
        up_ask=0.86,
        down_bid=0.14,
        down_ask=0.16,
        volume_24h=10000.0
    )


class TestTradingStrategy:
    """Test cases for TradingStrategy class."""

    def test_initialization(self):
        """Test strategy initializes with correct defaults."""
        strategy = TradingStrategy()
        assert strategy.min_confidence == 0.80
        assert strategy.min_time_remaining == 60
        assert strategy.max_time_remaining == 180

    def test_entry_signal_all_criteria_met(self):
        """Test that buy signal is generated when all criteria are met."""
        strategy = TradingStrategy()
        market = create_test_market(
            up_prob=0.85,
            time_remaining=120,
            btc_current=95100.0,  # $150 above target
            btc_target=94950.0
        )

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            consecutive_losses=0,
            has_open_position=False
        )

        assert decision.signal == TradeSignal.BUY_UP
        assert decision.direction == "up"
        assert decision.confidence >= 0.80

    def test_hold_signal_low_confidence(self):
        """Test that hold signal is generated when confidence is too low."""
        strategy = TradingStrategy()
        market = create_test_market(
            up_prob=0.75,  # Below 80% threshold
            time_remaining=120
        )

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            consecutive_losses=0,
            has_open_position=False
        )

        assert decision.signal == TradeSignal.HOLD
        assert "Confidence te laag" in decision.reason

    def test_hold_signal_insufficient_time(self):
        """Test that hold signal is generated when time is insufficient."""
        strategy = TradingStrategy()
        market = create_test_market(
            up_prob=0.85,
            time_remaining=30  # Below 60s minimum
        )

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            consecutive_losses=0,
            has_open_position=False
        )

        assert decision.signal == TradeSignal.HOLD
        assert "weinig tijd" in decision.reason

    def test_hold_signal_small_spread(self):
        """Test that hold signal is generated when spread is too small."""
        strategy = TradingStrategy()
        market = create_test_market(
            up_prob=0.85,
            time_remaining=120,
            btc_current=94970.0,  # Only $20 above target
            btc_target=94950.0
        )

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            consecutive_losses=0,
            has_open_position=False
        )

        assert decision.signal == TradeSignal.HOLD
        assert "Spread te klein" in decision.reason

    def test_pause_signal_max_losses(self):
        """Test that pause is triggered after max consecutive losses."""
        strategy = TradingStrategy()
        market = create_test_market()

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            consecutive_losses=3,  # Max is 3
            has_open_position=False
        )

        assert decision.signal == TradeSignal.PAUSE

    def test_profit_lock_exit(self):
        """Test that profit lock triggers exit."""
        strategy = TradingStrategy(
            profit_lock_enabled=True,
            profit_lock_threshold=0.92
        )
        market = create_test_market(up_prob=0.95)  # Above threshold

        decision = strategy.analyze(
            market_state=market,
            current_balance=100.0,
            has_open_position=True,
            open_position_direction="up"
        )

        assert decision.signal == TradeSignal.EXIT
        assert "Profit Lock" in decision.reason


# TODO: Add more test cases
# - Test pause/resume functionality
# - Test position sizing
# - Test edge cases
# - Test consistency check

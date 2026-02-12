"""
Trading strategie implementatie.
Bevat alle regels voor entry, exit, en trade management.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import logging

from src.config import settings


logger = logging.getLogger(__name__)


class MarketSide(Enum):
    """Market side (UP or DOWN)."""
    UP = "up"
    DOWN = "down"


class TradeSignal(Enum):
    """Mogelijke trade signalen."""
    BUY_UP = "buy_up"
    BUY_DOWN = "buy_down"
    HOLD = "hold"
    EXIT = "exit"
    PAUSE = "pause"


@dataclass
class MarketState:
    """Huidige staat van een Bitcoin Up/Down market."""

    market_id: str
    token_id_up: str
    token_id_down: str

    # Prijzen
    bitcoin_current_price: float
    bitcoin_target_price: float

    # Odds
    up_probability: float  # 0.0 - 1.0
    down_probability: float

    # Timing
    time_remaining_seconds: int
    market_end_time: datetime

    # Liquidity
    up_bid: float
    up_ask: float
    down_bid: float
    down_ask: float
    volume_24h: float

    @property
    def spread_above_target(self) -> float:
        """Verschil tussen huidige prijs en target."""
        return self.bitcoin_current_price - self.bitcoin_target_price

    @property
    def is_above_target(self) -> bool:
        """Bitcoin staat boven de target price."""
        return self.spread_above_target > 0

    @property
    def dominant_direction(self) -> str:
        """Welke richting heeft de hoogste probability."""
        return "up" if self.up_probability > self.down_probability else "down"

    @property
    def dominant_probability(self) -> float:
        """Hoogste probability van up of down."""
        return max(self.up_probability, self.down_probability)


@dataclass
class TradeDecision:
    """Resultaat van de strategie analyse."""

    signal: TradeSignal
    confidence: float
    reason: str

    # Trade details (indien signal != HOLD/PAUSE)
    direction: Optional[str] = None  # "up" of "down"
    token_id: Optional[str] = None
    suggested_size_usd: Optional[float] = None
    entry_price: Optional[float] = None

    # Meta
    timestamp: datetime = None
    market_state: Optional[MarketState] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class TradeOrder:
    """
    Trade order for execution.
    Used by OrderExecutor to place orders.
    """

    market_id: str
    token_id_up: str
    token_id_down: str
    side: MarketSide  # UP or DOWN
    price: float  # Entry price (0.0 - 1.0)
    size: float  # Position size in USD
    expected_edge: float  # Expected profit edge
    market_end_time: datetime

    # Optional metadata
    confidence: Optional[float] = None
    reason: Optional[str] = None


class TradingStrategy:
    """
    Implementeert de trading strategie regels.

    Entry criteria:
    1. Market confidence 80-95% (sweet spot)
    2. Resterende tijd tussen 1-3 minuten
    3. Bitcoin prijs >= $30 boven/onder target
    4. Geen actief nieuws-pause
    5. Geen maximum consecutive losses bereikt

    Note: Confidence >95% is avoided because fees/spread eat the profit margin.
    """

    def __init__(
        self,
        min_confidence: float = None,
        max_confidence: float = None,
        min_time_remaining: int = None,
        max_time_remaining: int = None,
        min_spread: float = None,
        profit_lock_enabled: bool = None,
        profit_lock_threshold: float = None,
    ):
        # Gebruik config defaults indien niet gespecificeerd
        self.min_confidence = min_confidence or settings.trading.min_confidence
        self.max_confidence = max_confidence or settings.trading.max_confidence
        self.min_time_remaining = min_time_remaining or settings.trading.min_time_remaining_seconds
        self.max_time_remaining = max_time_remaining or settings.trading.max_time_remaining_seconds
        self.min_spread = min_spread or 30.0  # Default $30 spread
        self.profit_lock_enabled = profit_lock_enabled if profit_lock_enabled is not None else settings.trading.profit_lock_enabled
        self.profit_lock_threshold = profit_lock_threshold or settings.trading.profit_lock_threshold

        # State
        self._is_paused = False
        self._pause_until: Optional[datetime] = None
        self._pause_reason: Optional[str] = None

    def analyze(
        self,
        market_state: MarketState,
        current_balance: float,
        consecutive_losses: int = 0,
        has_open_position: bool = False,
        open_position_direction: Optional[str] = None,
    ) -> TradeDecision:
        """
        Analyseer de huidige markt en geef een trade beslissing.

        Args:
            market_state: Huidige staat van de market
            current_balance: Beschikbaar saldo in USDC
            consecutive_losses: Aantal opeenvolgende verliezen
            has_open_position: Of er al een open positie is
            open_position_direction: Richting van open positie ("up"/"down")

        Returns:
            TradeDecision met signal en details
        """

        # Check 1: Is de bot gepauzeerd?
        if self._is_paused:
            if datetime.utcnow() < self._pause_until:
                return TradeDecision(
                    signal=TradeSignal.PAUSE,
                    confidence=0.0,
                    reason=f"Bot is gepauzeerd: {self._pause_reason}. Hervat om {self._pause_until}",
                )
            else:
                self._is_paused = False
                self._pause_reason = None

        # Check 2: Maximum consecutive losses?
        if consecutive_losses >= settings.trading.max_consecutive_losses:
            return TradeDecision(
                signal=TradeSignal.PAUSE,
                confidence=0.0,
                reason=f"Maximum consecutive losses bereikt ({consecutive_losses}). Automatische pauze.",
            )

        # Check 3: Hebben we al een open positie?
        if has_open_position:
            return self._check_exit_conditions(market_state, open_position_direction)

        # Check 4: Entry criteria
        return self._check_entry_conditions(market_state, current_balance)

    def _check_entry_conditions(
        self,
        market_state: MarketState,
        current_balance: float,
    ) -> TradeDecision:
        """Check of we een nieuwe positie moeten openen."""

        # Regel 1a: Minimum confidence
        if market_state.dominant_probability < self.min_confidence:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Confidence te laag: {market_state.dominant_probability:.1%} < {self.min_confidence:.1%}",
                market_state=market_state,
            )

        # Regel 1b: Maximum confidence (boven 95% eten fees de margin op)
        if market_state.dominant_probability > self.max_confidence:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Confidence te hoog: {market_state.dominant_probability:.1%} > {self.max_confidence:.1%} "
                       f"(fees/spread eten de margin op)",
                market_state=market_state,
            )

        # Regel 2: Tijd check
        if market_state.time_remaining_seconds < self.min_time_remaining:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Te weinig tijd over: {market_state.time_remaining_seconds}s < {self.min_time_remaining}s",
                market_state=market_state,
            )

        if market_state.time_remaining_seconds > self.max_time_remaining:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Te veel tijd over: {market_state.time_remaining_seconds}s > {self.max_time_remaining}s",
                market_state=market_state,
            )

        # Regel 3: Spread check
        spread = abs(market_state.spread_above_target)
        if spread < self.min_spread:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Spread te klein: ${spread:.2f} < ${self.min_spread:.2f}",
                market_state=market_state,
            )

        # Regel 4: Consistentie check - prijs en odds moeten aligned zijn
        price_suggests_up = market_state.is_above_target
        odds_suggest_up = market_state.dominant_direction == "up"

        if price_suggests_up != odds_suggest_up:
            return TradeDecision(
                signal=TradeSignal.HOLD,
                confidence=market_state.dominant_probability,
                reason=f"Inconsistentie: Prijs suggereert {'up' if price_suggests_up else 'down'}, "
                       f"maar odds suggereren {market_state.dominant_direction}",
                market_state=market_state,
            )

        # ✅ Alle checks passed - genereer trade signal
        direction = market_state.dominant_direction
        token_id = market_state.token_id_up if direction == "up" else market_state.token_id_down
        entry_price = market_state.up_ask if direction == "up" else market_state.down_ask

        # Bereken positie grootte (max 5% van balance)
        max_position = current_balance * settings.trading.max_position_pct
        suggested_size = min(max_position, current_balance)  # Nooit meer dan we hebben

        signal = TradeSignal.BUY_UP if direction == "up" else TradeSignal.BUY_DOWN

        return TradeDecision(
            signal=signal,
            confidence=market_state.dominant_probability,
            reason=f"Entry criteria voldaan: {market_state.dominant_probability:.1%} confidence, "
                   f"${spread:.2f} spread, {market_state.time_remaining_seconds}s remaining",
            direction=direction,
            token_id=token_id,
            suggested_size_usd=suggested_size,
            entry_price=entry_price,
            market_state=market_state,
        )

    def _check_exit_conditions(
        self,
        market_state: MarketState,
        position_direction: str,
    ) -> TradeDecision:
        """Check of we een bestaande positie moeten sluiten."""

        current_prob = (
            market_state.up_probability
            if position_direction == "up"
            else market_state.down_probability
        )

        # Profit Lock check
        if self.profit_lock_enabled and current_prob >= self.profit_lock_threshold:
            return TradeDecision(
                signal=TradeSignal.EXIT,
                confidence=current_prob,
                reason=f"Profit Lock triggered: {current_prob:.1%} >= {self.profit_lock_threshold:.1%}",
                direction=position_direction,
                market_state=market_state,
            )

        # Geen exit nodig
        return TradeDecision(
            signal=TradeSignal.HOLD,
            confidence=current_prob,
            reason=f"Holding position. Current probability: {current_prob:.1%}",
            market_state=market_state,
        )

    def pause(self, duration_seconds: int, reason: str):
        """Pauzeer de trading voor een bepaalde tijd."""
        self._is_paused = True
        self._pause_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        self._pause_reason = reason
        logger.info(f"Trading gepauzeerd voor {duration_seconds}s: {reason}")

    def resume(self):
        """Hervat trading."""
        self._is_paused = False
        self._pause_until = None
        self._pause_reason = None
        logger.info("Trading hervat")

    @property
    def is_paused(self) -> bool:
        """Check of de strategy momenteel gepauzeerd is."""
        if self._is_paused and datetime.utcnow() >= self._pause_until:
            self._is_paused = False
        return self._is_paused

    def analyze_simple(self, market_state: MarketState) -> Optional[TradeOrder]:
        """
        Simplified analyze that returns TradeOrder directly.
        Used by the bot main loop.

        Args:
            market_state: Market to analyze

        Returns:
            TradeOrder if trade criteria met, None otherwise
        """
        # Use simplified analyze (no balance/position tracking for now)
        decision = self.analyze(
            market_state=market_state,
            current_balance=1000.0,  # Dummy balance
            consecutive_losses=0,
            has_open_position=False,
        )

        # Convert to order
        return self.decision_to_order(decision)

    def decision_to_order(self, decision: TradeDecision) -> Optional[TradeOrder]:
        """
        Convert TradeDecision to TradeOrder for execution.

        Args:
            decision: TradeDecision from analyze()

        Returns:
            TradeOrder or None if no trade should be made
        """
        if decision.signal not in [TradeSignal.BUY_UP, TradeSignal.BUY_DOWN]:
            return None

        if not decision.market_state or not decision.direction:
            return None

        # Apply safety limit: max $5 per trade
        size = min(decision.suggested_size_usd or 0, settings.max_position_size)

        # Determine side
        side = MarketSide.UP if decision.direction == "up" else MarketSide.DOWN

        # Calculate expected edge
        # Edge = (probability * payout) - cost
        # For binary markets: payout = 1.0, cost = entry_price
        probability = (
            decision.market_state.up_probability
            if side == MarketSide.UP
            else decision.market_state.down_probability
        )
        expected_edge = (probability * 1.0) - decision.entry_price

        return TradeOrder(
            market_id=decision.market_state.market_id,
            token_id_up=decision.market_state.token_id_up,
            token_id_down=decision.market_state.token_id_down,
            side=side,
            price=decision.entry_price,
            size=size,
            expected_edge=expected_edge,
            market_end_time=decision.market_state.market_end_time,
            confidence=decision.confidence,
            reason=decision.reason,
        )

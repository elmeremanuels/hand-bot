"""
Risk management module.
Beheert bankroll, position sizing, en loss limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

from src.config import settings


logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """Informatie over een open positie."""

    market_id: str
    token_id: str
    direction: str  # "up" of "down"
    entry_price: float
    size_shares: float
    size_usd: float
    entry_time: datetime

    # Optional exit info
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None

    @property
    def is_closed(self) -> bool:
        return self.exit_time is not None


@dataclass
class RiskState:
    """Huidige staat van risk management."""

    total_balance: float
    available_balance: float
    locked_in_positions: float

    # Trade history
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Consecutive tracking
    consecutive_wins: int = 0
    consecutive_losses: int = 0

    # P&L
    total_pnl: float = 0.0
    session_pnl: float = 0.0

    # Timestamps
    session_start: datetime = field(default_factory=datetime.utcnow)
    last_trade_time: Optional[datetime] = None

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def pnl_percentage(self) -> float:
        if self.total_balance == 0:
            return 0.0
        return (self.session_pnl / (self.total_balance - self.session_pnl)) * 100


class RiskManager:
    """
    Beheert alle risk-gerelateerde logica.

    Verantwoordelijkheden:
    - Position sizing (max 5% per trade)
    - Loss limits (pauze na 3 consecutive losses)
    - Balance tracking
    - P&L berekening
    """

    def __init__(
        self,
        initial_balance: float,
        max_position_pct: float = None,
        max_consecutive_losses: int = None,
        pause_duration_minutes: int = None,
    ):
        self.initial_balance = initial_balance
        self.max_position_pct = max_position_pct or settings.trading.max_position_pct
        self.max_consecutive_losses = max_consecutive_losses or settings.trading.max_consecutive_losses
        self.pause_duration_minutes = pause_duration_minutes or settings.trading.pause_after_losses_minutes

        # State
        self._state = RiskState(
            total_balance=initial_balance,
            available_balance=initial_balance,
            locked_in_positions=0.0,
        )

        # Open posities
        self._open_positions: dict[str, PositionInfo] = {}

        # Pause state
        self._is_paused = False
        self._pause_until: Optional[datetime] = None

    @property
    def state(self) -> RiskState:
        """Huidige risk state."""
        return self._state

    @property
    def is_paused(self) -> bool:
        """Check of risk manager gepauzeerd is."""
        if self._is_paused and datetime.utcnow() >= self._pause_until:
            self._is_paused = False
            logger.info("Risk manager pause verlopen, trading hervat")
        return self._is_paused

    def calculate_position_size(self, available_balance: float = None) -> float:
        """
        Bereken de maximale positie grootte voor een nieuwe trade.

        Returns:
            Maximum positie in USD
        """
        balance = available_balance or self._state.available_balance
        max_size = balance * self.max_position_pct

        logger.debug(f"Position size berekend: ${max_size:.2f} ({self.max_position_pct:.1%} van ${balance:.2f})")
        return max_size

    def can_open_position(self, size_usd: float) -> tuple[bool, str]:
        """
        Check of een nieuwe positie geopend mag worden.

        Returns:
            (allowed, reason)
        """
        # Check 1: Is er een pauze actief?
        if self.is_paused:
            return False, f"Trading gepauzeerd tot {self._pause_until}"

        # Check 2: Consecutive losses check
        if self._state.consecutive_losses >= self.max_consecutive_losses:
            self._trigger_pause()
            return False, f"Max consecutive losses bereikt ({self._state.consecutive_losses})"

        # Check 3: Voldoende balance?
        if size_usd > self._state.available_balance:
            return False, f"Onvoldoende balance: ${size_usd:.2f} > ${self._state.available_balance:.2f}"

        # Check 4: Niet meer dan max position size
        max_size = self.calculate_position_size()
        if size_usd > max_size:
            return False, f"Positie te groot: ${size_usd:.2f} > ${max_size:.2f} (max {self.max_position_pct:.1%})"

        return True, "OK"

    def open_position(
        self,
        market_id: str,
        token_id: str,
        direction: str,
        entry_price: float,
        size_usd: float,
    ) -> PositionInfo:
        """
        Registreer een nieuwe open positie.

        Returns:
            PositionInfo object
        """
        # Bereken aantal shares
        size_shares = size_usd / entry_price

        # Maak positie object
        position = PositionInfo(
            market_id=market_id,
            token_id=token_id,
            direction=direction,
            entry_price=entry_price,
            size_shares=size_shares,
            size_usd=size_usd,
            entry_time=datetime.utcnow(),
        )

        # Update state
        self._open_positions[market_id] = position
        self._state.available_balance -= size_usd
        self._state.locked_in_positions += size_usd

        logger.info(
            f"Positie geopend: {direction.upper()} {size_shares:.2f} shares @ ${entry_price:.4f} "
            f"(${size_usd:.2f}) in {market_id}"
        )

        return position

    def close_position(
        self,
        market_id: str,
        exit_price: float,
        won: bool,
    ) -> PositionInfo:
        """
        Sluit een positie en bereken P&L.

        Args:
            market_id: ID van de market
            exit_price: Prijs bij sluiting ($1.00 bij winst, $0.00 bij verlies voor binaire markets)
            won: Of de trade gewonnen is

        Returns:
            Updated PositionInfo
        """
        if market_id not in self._open_positions:
            raise ValueError(f"Geen open positie gevonden voor {market_id}")

        position = self._open_positions[market_id]

        # Bereken P&L
        exit_value = position.size_shares * exit_price
        pnl = exit_value - position.size_usd

        # Update position
        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()
        position.pnl = pnl

        # Update state
        self._state.available_balance += exit_value
        self._state.locked_in_positions -= position.size_usd
        self._state.total_balance = self._state.available_balance + self._state.locked_in_positions

        self._state.total_trades += 1
        self._state.total_pnl += pnl
        self._state.session_pnl += pnl
        self._state.last_trade_time = datetime.utcnow()

        if won:
            self._state.winning_trades += 1
            self._state.consecutive_wins += 1
            self._state.consecutive_losses = 0
        else:
            self._state.losing_trades += 1
            self._state.consecutive_losses += 1
            self._state.consecutive_wins = 0

            # Check voor pause trigger
            if self._state.consecutive_losses >= self.max_consecutive_losses:
                self._trigger_pause()

        # Verwijder uit open positions
        del self._open_positions[market_id]

        logger.info(
            f"Positie gesloten: {'WIN' if won else 'LOSS'} - "
            f"P&L: ${pnl:+.2f} ({position.direction.upper()}) - "
            f"New balance: ${self._state.total_balance:.2f}"
        )

        return position

    def _trigger_pause(self):
        """Trigger een trading pauze na te veel losses."""
        self._is_paused = True
        self._pause_until = datetime.utcnow() + timedelta(minutes=self.pause_duration_minutes)

        logger.warning(
            f"⚠️ PAUSE TRIGGERED: {self._state.consecutive_losses} consecutive losses. "
            f"Trading gepauzeerd tot {self._pause_until}"
        )

    def update_balance(self, new_balance: float):
        """Update de balance (voor sync met Polymarket)."""
        old_balance = self._state.total_balance
        self._state.total_balance = new_balance
        self._state.available_balance = new_balance - self._state.locked_in_positions

        logger.info(f"Balance updated: ${old_balance:.2f} -> ${new_balance:.2f}")

    def recalculate_position_sizes(self):
        """
        Herbereken position sizes na significante balance verandering.
        Wordt aangeroepen na elke 25% groei.
        """
        growth_pct = (self._state.total_balance - self.initial_balance) / self.initial_balance

        if growth_pct >= 0.25:
            # Update initial balance naar nieuwe baseline
            old_max = self.calculate_position_size(self.initial_balance)
            self.initial_balance = self._state.total_balance
            new_max = self.calculate_position_size()

            logger.info(
                f"🎯 25% groei bereikt! Position size herberekend: "
                f"${old_max:.2f} -> ${new_max:.2f}"
            )

    def get_open_position(self, market_id: str) -> Optional[PositionInfo]:
        """Haal open positie op voor een market."""
        return self._open_positions.get(market_id)

    def has_open_position(self, market_id: str = None) -> bool:
        """Check of er open posities zijn."""
        if market_id:
            return market_id in self._open_positions
        return len(self._open_positions) > 0

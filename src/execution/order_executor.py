"""
Order execution engine for placing and managing trades on Polymarket.
Handles order placement, position tracking, and PnL calculation.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from decimal import Decimal

from src.config import settings
from src.core.strategy import TradeSignal, MarketSide

logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Executes trades on Polymarket and tracks positions.

    Responsibilities:
    - Place market orders based on TradeSignals
    - Track open positions
    - Calculate profit/loss
    - Enforce position limits and risk controls
    """

    def __init__(self, polymarket_client, risk_manager=None):
        """
        Initialize order executor.

        Args:
            polymarket_client: PolymarketClient instance for API calls
            risk_manager: Optional RiskManager for pre-trade checks
        """
        self.client = polymarket_client
        self.risk_manager = risk_manager

        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.order_history: List[Dict] = []

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

    async def execute_signal(self, signal: TradeSignal) -> Optional[str]:
        """
        Execute a trade signal.

        Args:
            signal: TradeSignal from strategy

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            logger.info(
                f"🎯 Executing {signal.side.value.upper()} signal for {signal.market_id}: "
                f"${signal.size:.2f} @ {signal.price:.3f} (edge: {signal.expected_edge:.1%})"
            )

            # Pre-trade risk checks
            if not self._pre_trade_checks(signal):
                logger.warning("Pre-trade checks failed, skipping order")
                return None

            # Determine token ID based on side
            token_id = (
                signal.token_id_up if signal.side == MarketSide.UP
                else signal.token_id_down
            )

            # Calculate shares to buy
            shares = self._calculate_shares(signal.size, signal.price)

            if shares <= 0:
                logger.error(f"Invalid share calculation: {shares}")
                return None

            # Place order on Polymarket
            if settings.paper_trading:
                order_id = await self._place_paper_order(signal, token_id, shares)
            else:
                order_id = await self._place_real_order(signal, token_id, shares)

            if not order_id:
                logger.error("Order placement failed")
                return None

            # Track position
            self._open_position(signal, order_id, shares)

            # Update stats
            self.total_trades += 1

            logger.info(f"✅ Order placed: {order_id} ({shares:.0f} shares)")
            return order_id

        except Exception as e:
            logger.exception(f"Error executing signal: {e}")
            return None

    async def _place_real_order(
        self, signal: TradeSignal, token_id: str, shares: float
    ) -> Optional[str]:
        """
        Place a real order on Polymarket.

        Args:
            signal: Trade signal
            token_id: Token ID to buy
            shares: Number of shares to buy

        Returns:
            Order ID or None
        """
        try:
            # Place market buy order
            order = await self.client.place_market_order(
                token_id=token_id,
                side="buy",
                amount=shares,
            )

            if not order or "order_id" not in order:
                logger.error(f"Invalid order response: {order}")
                return None

            order_id = order["order_id"]
            logger.info(f"Real order placed: {order_id}")

            # Store order details
            self.order_history.append({
                "order_id": order_id,
                "timestamp": datetime.utcnow(),
                "signal": signal,
                "token_id": token_id,
                "shares": shares,
                "type": "real",
            })

            return order_id

        except Exception as e:
            logger.exception(f"Error placing real order: {e}")
            return None

    async def _place_paper_order(
        self, signal: TradeSignal, token_id: str, shares: float
    ) -> Optional[str]:
        """
        Simulate a paper trading order.

        Args:
            signal: Trade signal
            token_id: Token ID to buy
            shares: Number of shares to buy

        Returns:
            Simulated order ID
        """
        # Generate simulated order ID
        order_id = f"paper_{signal.market_id}_{int(datetime.utcnow().timestamp())}"

        logger.info(f"📝 Paper order placed: {order_id} ({shares:.0f} shares)")

        # Store paper order
        self.order_history.append({
            "order_id": order_id,
            "timestamp": datetime.utcnow(),
            "signal": signal,
            "token_id": token_id,
            "shares": shares,
            "type": "paper",
        })

        return order_id

    def _calculate_shares(self, size_usd: float, price: float) -> float:
        """
        Calculate number of shares to buy.

        Args:
            size_usd: Position size in USD
            price: Price per share (0.0 to 1.0)

        Returns:
            Number of shares
        """
        if price <= 0 or price >= 1.0:
            logger.error(f"Invalid price: {price}")
            return 0.0

        # shares * price = size_usd
        shares = size_usd / price

        return round(shares, 2)

    def _pre_trade_checks(self, signal: TradeSignal) -> bool:
        """
        Run pre-trade validation checks.

        Args:
            signal: Trade signal to validate

        Returns:
            True if all checks pass
        """
        # Check 1: Valid signal
        if signal.size <= 0:
            logger.warning(f"Invalid signal size: ${signal.size}")
            return False

        # Check 2: Price in valid range
        if signal.price <= 0 or signal.price >= 1.0:
            logger.warning(f"Invalid signal price: {signal.price}")
            return False

        # Check 3: Risk manager approval (if available)
        if self.risk_manager:
            if not self.risk_manager.approve_trade(signal):
                logger.warning("Risk manager rejected trade")
                return False

        # Check 4: Position limit
        if len(self.positions) >= settings.max_open_positions:
            logger.warning(
                f"Maximum positions reached: {len(self.positions)}/{settings.max_open_positions}"
            )
            return False

        # All checks passed
        return True

    def _open_position(self, signal: TradeSignal, order_id: str, shares: float):
        """
        Track a new open position.

        Args:
            signal: Trade signal
            order_id: Order ID
            shares: Number of shares purchased
        """
        position = Position(
            market_id=signal.market_id,
            token_id_up=signal.token_id_up,
            token_id_down=signal.token_id_down,
            side=signal.side,
            entry_price=signal.price,
            shares=shares,
            size_usd=signal.size,
            order_id=order_id,
            entry_time=datetime.utcnow(),
            market_end_time=signal.market_end_time,
        )

        self.positions[signal.market_id] = position
        logger.debug(f"Opened position: {signal.market_id} ({signal.side.value})")

    async def check_positions(self) -> List[Dict]:
        """
        Check all open positions and close any that should be closed.

        Returns:
            List of closed positions with PnL
        """
        closed_positions = []

        for market_id, position in list(self.positions.items()):
            # Check if market has ended
            if datetime.utcnow() >= position.market_end_time:
                pnl = await self._close_position(market_id, reason="market_ended")
                if pnl is not None:
                    closed_positions.append({
                        "market_id": market_id,
                        "pnl": pnl,
                        "reason": "market_ended",
                    })

        return closed_positions

    async def _close_position(
        self, market_id: str, reason: str = "manual"
    ) -> Optional[float]:
        """
        Close a position and calculate PnL.

        Args:
            market_id: Market ID of position to close
            reason: Reason for closing

        Returns:
            PnL in USD or None if error
        """
        if market_id not in self.positions:
            logger.warning(f"Position not found: {market_id}")
            return None

        position = self.positions[market_id]

        try:
            # Get market outcome
            outcome = await self._get_market_outcome(market_id)

            if outcome is None:
                logger.warning(f"Could not determine outcome for {market_id}")
                return None

            # Calculate PnL
            pnl = self._calculate_pnl(position, outcome)

            # Update stats
            self.total_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1

            logger.info(
                f"💰 Closed position {market_id}: "
                f"PnL=${pnl:+.2f} ({reason})"
            )

            # Remove from positions
            del self.positions[market_id]

            return pnl

        except Exception as e:
            logger.exception(f"Error closing position {market_id}: {e}")
            return None

    async def _get_market_outcome(self, market_id: str) -> Optional[MarketSide]:
        """
        Get the outcome of a resolved market.

        Args:
            market_id: Market ID

        Returns:
            MarketSide.UP if UP won, MarketSide.DOWN if DOWN won, None if unresolved
        """
        try:
            # Query Polymarket for market resolution
            market = await self.client.get_market(market_id)

            if not market or "outcome" not in market:
                return None

            outcome = market["outcome"]

            # Map outcome to side
            if outcome == "up" or outcome == 1:
                return MarketSide.UP
            elif outcome == "down" or outcome == 0:
                return MarketSide.DOWN
            else:
                logger.warning(f"Unknown outcome: {outcome}")
                return None

        except Exception as e:
            logger.exception(f"Error getting market outcome: {e}")
            return None

    def _calculate_pnl(self, position: "Position", outcome: MarketSide) -> float:
        """
        Calculate profit/loss for a position.

        Args:
            position: Position to calculate PnL for
            outcome: Market outcome (UP or DOWN)

        Returns:
            PnL in USD (positive = profit, negative = loss)
        """
        # If we bet correctly, we get $1 per share
        # If we bet incorrectly, we get $0 per share

        if position.side == outcome:
            # Win: shares worth $1 each
            final_value = position.shares * 1.0
        else:
            # Loss: shares worth $0
            final_value = 0.0

        # PnL = final value - initial cost
        pnl = final_value - position.size_usd

        return pnl

    def get_statistics(self) -> Dict:
        """
        Get trading statistics.

        Returns:
            Dict with performance metrics
        """
        win_rate = (
            self.winning_trades / self.total_trades
            if self.total_trades > 0
            else 0.0
        )

        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "open_positions": len(self.positions),
            "avg_pnl_per_trade": (
                self.total_pnl / self.total_trades
                if self.total_trades > 0
                else 0.0
            ),
        }


class Position:
    """Represents an open trading position."""

    def __init__(
        self,
        market_id: str,
        token_id_up: str,
        token_id_down: str,
        side: MarketSide,
        entry_price: float,
        shares: float,
        size_usd: float,
        order_id: str,
        entry_time: datetime,
        market_end_time: datetime,
    ):
        self.market_id = market_id
        self.token_id_up = token_id_up
        self.token_id_down = token_id_down
        self.side = side
        self.entry_price = entry_price
        self.shares = shares
        self.size_usd = size_usd
        self.order_id = order_id
        self.entry_time = entry_time
        self.market_end_time = market_end_time

    def __repr__(self):
        return (
            f"Position(market={self.market_id}, side={self.side.value}, "
            f"shares={self.shares:.0f}, entry={self.entry_price:.3f})"
        )

"""
Main trading bot orchestrator.
Coordinates market scanning, strategy analysis, and order execution.
"""

import asyncio
import logging
import signal
from datetime import datetime, timedelta
from typing import Optional

from src.config import settings
from src.api.polymarket_client import PolymarketClient
from src.data.market_scanner import MarketScanner
from src.core.strategy import TradingStrategy
from src.execution.order_executor import OrderExecutor
from src.execution.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class PolymarketBot:
    """
    Main trading bot for Polymarket crypto Up/Down markets.

    Orchestrates:
    1. Market scanning (find active markets)
    2. Strategy analysis (identify trading opportunities)
    3. Order execution (place trades)
    4. Position management (track and close positions)
    """

    def __init__(self):
        """Initialize the trading bot."""
        self.running = False
        self.shutdown_requested = False

        # Initialize components
        logger.info("🤖 Initializing Polymarket Trading Bot...")

        # API client
        self.client = PolymarketClient(
            api_key=settings.polymarket_api_key,
            private_key=settings.polymarket_private_key,
            paper_trading=settings.paper_trading,
        )

        # Risk management
        self.risk_manager = RiskManager(
            max_position_size=settings.max_position_size,
            max_open_positions=settings.max_open_positions,
            max_total_exposure=settings.max_total_exposure,
        )

        # Order execution
        self.executor = OrderExecutor(
            polymarket_client=self.client,
            risk_manager=self.risk_manager,
        )

        # Market scanner
        self.scanner = MarketScanner(
            polymarket_client=self.client,
            price_feed=None,  # TODO: Add real price feed
        )

        # Trading strategy
        self.strategy = TradingStrategy()

        # Performance tracking
        self.start_time: Optional[datetime] = None
        self.scan_count = 0
        self.signals_generated = 0
        self.orders_placed = 0

        logger.info("✅ Bot initialized successfully")

    async def start(self):
        """Start the trading bot main loop."""
        logger.info("=" * 60)
        logger.info("🚀 Starting Polymarket Trading Bot")
        logger.info("=" * 60)
        logger.info(f"Mode: {'📝 Paper Trading' if settings.paper_trading else '💰 Live Trading'}")
        logger.info(f"Max Position Size: ${settings.max_position_size:.2f}")
        logger.info(f"Max Open Positions: {settings.max_open_positions}")
        logger.info(f"Scan Interval: {settings.scan_interval_seconds}s")
        logger.info("=" * 60)

        self.running = True
        self.start_time = datetime.utcnow()

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        try:
            # Initialize API client
            await self.client.initialize()

            # Main loop
            await self._main_loop()

        except KeyboardInterrupt:
            logger.info("⚠️ Keyboard interrupt received")
        except Exception as e:
            logger.exception(f"Fatal error in bot: {e}")
        finally:
            await self.shutdown()

    async def _main_loop(self):
        """Main trading loop."""
        logger.info("🔄 Entering main loop...")

        while self.running and not self.shutdown_requested:
            try:
                loop_start = datetime.utcnow()

                # 1. Scan for markets
                markets = await self.scanner.scan(asset=settings.target_asset)
                self.scan_count += 1

                if not markets:
                    logger.debug("No markets found in this scan")
                else:
                    logger.info(f"📊 Found {len(markets)} markets to analyze")

                    # 2. Analyze each market with strategy
                    for market in markets:
                        # Check if we should continue
                        if self.shutdown_requested:
                            break

                        # Check if tradeable
                        is_tradeable, reason = self.scanner.is_tradeable(market)
                        if not is_tradeable:
                            logger.debug(f"Market {market.market_id} not tradeable: {reason}")
                            continue

                        # Analyze with strategy
                        signal = self.strategy.analyze(market)

                        if signal:
                            self.signals_generated += 1
                            logger.info(
                                f"🎯 SIGNAL: {signal.side.value.upper()} "
                                f"${signal.size:.2f} @ {signal.price:.3f} "
                                f"(edge: {signal.expected_edge:.1%})"
                            )

                            # 3. Execute the signal
                            order_id = await self.executor.execute_signal(signal)

                            if order_id:
                                self.orders_placed += 1
                                logger.info(f"✅ Order executed: {order_id}")
                            else:
                                logger.warning("❌ Order execution failed")

                # 4. Check and manage existing positions
                closed_positions = await self.executor.check_positions()

                if closed_positions:
                    for pos in closed_positions:
                        logger.info(
                            f"📊 Position closed: {pos['market_id']} "
                            f"PnL: ${pos['pnl']:+.2f}"
                        )

                # 5. Log statistics periodically
                if self.scan_count % 10 == 0:  # Every 10 scans
                    self._log_statistics()

                # 6. Sleep until next scan
                loop_duration = (datetime.utcnow() - loop_start).total_seconds()
                sleep_time = max(0, settings.scan_interval_seconds - loop_duration)

                if sleep_time > 0:
                    logger.debug(f"💤 Sleeping for {sleep_time:.1f}s until next scan...")
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.exception(f"Error in main loop: {e}")
                # Sleep briefly before retrying
                await asyncio.sleep(5)

        logger.info("🛑 Main loop ended")

    def _log_statistics(self):
        """Log bot performance statistics."""
        stats = self.executor.get_statistics()
        uptime = datetime.utcnow() - self.start_time if self.start_time else timedelta(0)

        logger.info("=" * 60)
        logger.info("📈 BOT STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Uptime: {uptime}")
        logger.info(f"Scans: {self.scan_count}")
        logger.info(f"Signals Generated: {self.signals_generated}")
        logger.info(f"Orders Placed: {self.orders_placed}")
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Winning Trades: {stats['winning_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.1%}")
        logger.info(f"Total PnL: ${stats['total_pnl']:+.2f}")
        logger.info(f"Avg PnL/Trade: ${stats['avg_pnl_per_trade']:+.2f}")
        logger.info(f"Open Positions: {stats['open_positions']}")
        logger.info("=" * 60)

    async def shutdown(self):
        """Gracefully shutdown the bot."""
        logger.info("🛑 Shutting down bot...")

        self.running = False

        # Close any open positions (optional - depends on strategy)
        if self.executor.positions:
            logger.info(f"⚠️ {len(self.executor.positions)} positions still open")
            # Could implement auto-close here if desired

        # Final statistics
        self._log_statistics()

        # Cleanup API client
        await self.client.close()

        logger.info("✅ Shutdown complete")

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown on SIGINT/SIGTERM."""
        def signal_handler(sig, frame):
            logger.info(f"⚠️ Received signal {sig}")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Entry point for the trading bot."""
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create and start bot
    bot = PolymarketBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())

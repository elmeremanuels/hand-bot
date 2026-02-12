"""
Market scanner for finding active Bitcoin Up/Down markets.
Scans for tradeable crypto short-term prediction markets.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio

from src.config import settings
from src.core.strategy import MarketState

logger = logging.getLogger(__name__)


class MarketScanner:
    """
    Scans Polymarket for active crypto Up or Down markets.

    Filters for:
    - Supported assets: BTC, ETH, SOL, XRP
    - Short-term markets (5, 10, or 15 minute windows)
    - Sufficient liquidity
    - Clear price targets
    """

    def __init__(self, polymarket_client, price_feed=None):
        """
        Initialize market scanner.

        Args:
            polymarket_client: PolymarketClient instance
            price_feed: Optional price feed for real-time crypto prices
        """
        self.client = polymarket_client
        self.price_feed = price_feed
        self.scan_interval = 10  # seconds

        # Cache to avoid duplicate processing
        self._seen_markets: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)

    async def scan(self, asset: Optional[str] = None) -> List[MarketState]:
        """
        Scan for tradeable crypto Up/Down markets.

        Args:
            asset: Optional asset filter (bitcoin, ethereum, solana, xrp)

        Returns:
            List of MarketState objects ready for strategy analysis
        """
        logger.debug(f"Scanning for markets{f' ({asset})' if asset else ''}...")

        try:
            # Get markets from Polymarket
            markets = await self.client.find_crypto_markets(asset)

            if not markets:
                logger.debug("No crypto Up/Down markets found")
                return []

            # Convert to MarketState objects
            market_states = []
            for market in markets:
                market_state = await self._build_market_state(market)
                if market_state:
                    market_states.append(market_state)

            # Cleanup old cache entries
            self._cleanup_cache()

            logger.info(f"Found {len(market_states)} tradeable markets")
            return market_states

        except Exception as e:
            logger.exception(f"Error scanning markets: {e}")
            return []

    async def _build_market_state(self, market: Dict) -> Optional[MarketState]:
        """
        Build a MarketState object from raw market data.

        Args:
            market: Market data from PolymarketClient

        Returns:
            MarketState object or None if invalid
        """
        try:
            market_id = market["market_id"]

            # Check if we've seen this market recently
            if market_id in self._seen_markets:
                last_seen = self._seen_markets[market_id]
                if datetime.utcnow() - last_seen < timedelta(seconds=30):
                    # Skip if seen in last 30 seconds
                    return None

            # Mark as seen
            self._seen_markets[market_id] = datetime.utcnow()

            # Get token IDs
            token_id_up = market["token_id_up"]
            token_id_down = market["token_id_down"]

            # Get orderbooks for both tokens
            orderbook_up = await self.client.get_market_orderbook(token_id_up)
            orderbook_down = await self.client.get_market_orderbook(token_id_down)

            # Extract probabilities
            up_probability = orderbook_up.get("probability", 0.5)
            down_probability = orderbook_down.get("probability", 0.5)

            # Normalize probabilities to sum to 1.0
            total = up_probability + down_probability
            if total > 0:
                up_probability = up_probability / total
                down_probability = down_probability / total
            else:
                up_probability = 0.5
                down_probability = 0.5

            # Get bid/ask prices
            up_bid = orderbook_up.get("best_bid", 0.0)
            up_ask = orderbook_up.get("best_ask", 1.0)
            down_bid = orderbook_down.get("best_bid", 0.0)
            down_ask = orderbook_down.get("best_ask", 1.0)

            # Calculate time remaining
            end_time = market.get("end_time")
            if not end_time:
                logger.warning(f"Market {market_id} has no end_time")
                return None

            time_remaining = int((end_time - datetime.utcnow()).total_seconds())
            if time_remaining <= 0:
                logger.debug(f"Market {market_id} already expired")
                return None

            # Get current crypto price and target
            asset = market["asset"]
            current_price = await self._get_crypto_price(asset)
            target_price = self._extract_target_price(market)

            if current_price is None or target_price is None:
                logger.warning(f"Could not determine prices for {market_id}")
                return None

            # Get volume
            volume_24h = market.get("volume_24h", 0.0)

            # Build MarketState
            market_state = MarketState(
                market_id=market_id,
                token_id_up=token_id_up,
                token_id_down=token_id_down,
                bitcoin_current_price=current_price,
                bitcoin_target_price=target_price,
                up_probability=up_probability,
                down_probability=down_probability,
                time_remaining_seconds=time_remaining,
                market_end_time=end_time,
                up_bid=up_bid,
                up_ask=up_ask,
                down_bid=down_bid,
                down_ask=down_ask,
                volume_24h=volume_24h,
            )

            logger.debug(
                f"Market {asset.upper()}: "
                f"${current_price:.2f} vs ${target_price:.2f} | "
                f"Up: {up_probability:.1%} | "
                f"{time_remaining}s remaining"
            )

            return market_state

        except Exception as e:
            logger.exception(f"Error building market state: {e}")
            return None

    async def _get_crypto_price(self, asset: str) -> Optional[float]:
        """
        Get current crypto price.

        Args:
            asset: Asset name (bitcoin, ethereum, solana, xrp)

        Returns:
            Current price in USD or None
        """
        # If we have a price feed, use it
        if self.price_feed:
            try:
                price = await self.price_feed.get_price(asset)
                if price:
                    return price
            except Exception as e:
                logger.warning(f"Price feed failed for {asset}: {e}")

        # Fallback: Use Polymarket's own price oracle or simulated data
        # TODO: Implement real price feed integration (CoinGecko, Binance, etc.)

        # For now, return a placeholder that would come from a real price feed
        # In production, this should NEVER return None
        if settings.paper_trading:
            # Simulated prices for paper trading
            simulated_prices = {
                "bitcoin": 95000.0,
                "ethereum": 3200.0,
                "solana": 105.0,
                "xrp": 0.52,
            }
            price = simulated_prices.get(asset)
            if price:
                logger.debug(f"📝 Paper trading: using simulated {asset} price ${price:.2f}")
                return price

        logger.error(f"No price available for {asset} - price feed not implemented")
        return None

    def _extract_target_price(self, market: Dict) -> Optional[float]:
        """
        Extract target price from market question or metadata.

        Args:
            market: Market data

        Returns:
            Target price or None
        """
        # The target price is typically embedded in the market question
        # Example: "Will Bitcoin be above $94,950 at 9:05 PM ET?"

        question = market.get("question", "")
        slug = market.get("slug", "")

        # Try to extract price from question using common patterns
        import re

        # Pattern: $XX,XXX or $XXXXX
        price_patterns = [
            r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $95,000 or $95,000.00
            r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:USD|usd|dollars?)',  # 95,000 USD
        ]

        for pattern in price_patterns:
            matches = re.findall(pattern, question + " " + slug)
            if matches:
                # Take the first match and clean it
                price_str = matches[0].replace(',', '')
                try:
                    return float(price_str)
                except ValueError:
                    continue

        # If we can't extract it, log and return None
        logger.warning(f"Could not extract target price from: {question}")
        return None

    def _cleanup_cache(self):
        """Remove old entries from the seen markets cache."""
        cutoff = datetime.utcnow() - self._cache_ttl
        self._seen_markets = {
            k: v for k, v in self._seen_markets.items()
            if v > cutoff
        }

    def is_tradeable(self, market_state: MarketState) -> tuple[bool, str]:
        """
        Quick check if a market is tradeable (basic filters).

        Note: This is a preliminary check. The strategy will do detailed analysis.

        Args:
            market_state: Market to check

        Returns:
            (is_tradeable, reason)
        """
        # Check 1: Minimum liquidity (volume)
        if market_state.volume_24h < 100:  # $100 minimum volume
            return False, f"Insufficient liquidity: ${market_state.volume_24h:.2f}"

        # Check 2: Valid orderbook
        if market_state.up_ask >= 1.0 or market_state.down_ask >= 1.0:
            return False, "Invalid orderbook (ask >= $1.00)"

        # Check 3: Spread not too wide
        up_spread = market_state.up_ask - market_state.up_bid
        down_spread = market_state.down_ask - market_state.down_bid

        if up_spread > 0.10 or down_spread > 0.10:  # 10% spread max
            return False, f"Spread too wide: {max(up_spread, down_spread):.1%}"

        # All basic checks passed
        return True, "OK"

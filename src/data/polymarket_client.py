"""
Polymarket API wrapper.
Provides interface to Polymarket CLOB and Gamma APIs.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import httpx

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    CLOB_CLIENT_AVAILABLE = True
except ImportError:
    CLOB_CLIENT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("py-clob-client not installed. Install with: pip install py-clob-client")

from src.config import settings

logger = logging.getLogger(__name__)


# Supported crypto assets for Up/Down markets
SUPPORTED_ASSETS = ["bitcoin", "ethereum", "solana", "xrp"]


class PolymarketClient:
    """
    Wrapper around Polymarket's py-clob-client.

    Provides simplified interface for:
    - Market discovery (crypto Up/Down markets only)
    - Order placement (with paper trading support)
    - Position tracking
    - Balance queries
    """

    def __init__(self):
        self.host = settings.polymarket.clob_host
        self.gamma_host = settings.polymarket.gamma_host
        self.chain_id = settings.polymarket.chain_id

        self.client: Optional[ClobClient] = None
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Initialize CLOB client if available and not in paper trading
        if CLOB_CLIENT_AVAILABLE and not settings.paper_trading:
            try:
                self.client = ClobClient(
                    host=self.host,
                    key=settings.polymarket.private_key,
                    chain_id=self.chain_id,
                    signature_type=settings.polymarket.signature_type,
                    funder=settings.polymarket.funder_address
                )

                # Set API credentials
                self.client.set_api_creds(self.client.create_or_derive_api_creds())
                logger.info(f"✅ Polymarket CLOB client initialized (host: {self.host})")

            except Exception as e:
                logger.error(f"❌ Failed to initialize CLOB client: {e}")
                self.client = None
        else:
            if settings.paper_trading:
                logger.info(f"📝 Polymarket client in PAPER TRADING mode")
            else:
                logger.warning("⚠️ CLOB client not available - install py-clob-client")

    async def get_balance(self) -> float:
        """
        Get current USDC balance.

        Returns:
            Balance in USDC
        """
        if settings.paper_trading:
            # In paper trading, return a simulated balance
            logger.debug("📝 Paper trading: returning simulated balance")
            return 100.0

        if not self.client:
            logger.error("CLOB client not initialized")
            return 0.0

        try:
            # Get balance from Polymarket
            balance_response = self.client.get_balance()
            usdc_balance = float(balance_response.get("balance", 0))
            logger.debug(f"Current balance: ${usdc_balance:.2f} USDC")
            return usdc_balance

        except Exception as e:
            logger.exception(f"Error getting balance: {e}")
            return 0.0

    async def find_crypto_markets(self, asset: Optional[str] = None) -> List[Dict]:
        """
        Find active crypto Up/Down markets.

        Args:
            asset: Specific asset to filter for (bitcoin, ethereum, solana, xrp)
                   If None, returns all supported assets

        Returns:
            List of market objects with relevant data
        """
        try:
            # Query Gamma API for markets
            url = f"{self.gamma_host}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": 100
            }

            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            all_markets = response.json()

            # Filter for crypto Up/Down markets
            crypto_markets = []
            for market in all_markets:
                slug = market.get("slug", "").lower()
                question = market.get("question", "").lower()

                # Check if it's a supported crypto Up/Down market
                if self._is_crypto_updown_market(slug, question, asset):
                    parsed = self._parse_market_data(market)
                    if parsed:
                        crypto_markets.append(parsed)

            logger.info(
                f"Found {len(crypto_markets)} active crypto Up/Down markets"
                f"{f' for {asset}' if asset else ''}"
            )
            return crypto_markets

        except Exception as e:
            logger.exception(f"Error finding crypto markets: {e}")
            return []

    def _is_crypto_updown_market(
        self,
        slug: str,
        question: str,
        asset_filter: Optional[str] = None
    ) -> bool:
        """
        Check if a market is a supported crypto Up/Down market.

        Args:
            slug: Market slug
            question: Market question
            asset_filter: Optional asset to filter for

        Returns:
            True if market matches criteria
        """
        # Check for "up or down" pattern
        if "up-or-down" not in slug and "up or down" not in question:
            return False

        # Check if it's one of the supported assets
        assets_to_check = [asset_filter] if asset_filter else SUPPORTED_ASSETS

        for asset in assets_to_check:
            if asset in slug or asset in question:
                return True

        return False

    def _parse_market_data(self, market: Dict) -> Optional[Dict]:
        """
        Parse market data into a simplified format.

        Args:
            market: Raw market data from API

        Returns:
            Parsed market dict or None if invalid
        """
        try:
            # Extract basic info
            market_id = market.get("condition_id") or market.get("id")
            question = market.get("question", "")
            slug = market.get("slug", "")

            # Determine asset type
            asset = None
            for crypto in SUPPORTED_ASSETS:
                if crypto in slug.lower() or crypto in question.lower():
                    asset = crypto
                    break

            if not asset:
                return None

            # Get tokens (Up and Down)
            tokens = market.get("tokens", [])
            if len(tokens) != 2:
                logger.warning(f"Market {market_id} doesn't have 2 tokens")
                return None

            # Identify Up and Down tokens
            token_up = None
            token_down = None

            for token in tokens:
                outcome = token.get("outcome", "").lower()
                if "up" in outcome or "yes" in outcome:
                    token_up = token
                elif "down" in outcome or "no" in outcome:
                    token_down = token

            if not token_up or not token_down:
                logger.warning(f"Could not identify up/down tokens for {market_id}")
                return None

            # Get end time
            end_date_str = market.get("end_date_iso")
            end_time = None
            if end_date_str:
                try:
                    end_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                except:
                    pass

            # Get volume
            volume = float(market.get("volume", 0))

            return {
                "market_id": market_id,
                "slug": slug,
                "question": question,
                "asset": asset,
                "token_id_up": token_up.get("token_id"),
                "token_id_down": token_down.get("token_id"),
                "outcome_up": token_up.get("outcome"),
                "outcome_down": token_down.get("outcome"),
                "end_time": end_time,
                "volume_24h": volume,
                "active": market.get("active", True),
            }

        except Exception as e:
            logger.exception(f"Error parsing market data: {e}")
            return None

    async def get_market_orderbook(self, token_id: str) -> Dict:
        """
        Get orderbook for a specific token.

        Args:
            token_id: Token ID

        Returns:
            Orderbook data with bids/asks and probabilities
        """
        if settings.paper_trading:
            # Return simulated orderbook for paper trading
            logger.debug(f"📝 Paper trading: returning simulated orderbook for {token_id}")
            return {
                "bids": [{"price": "0.84", "size": "100"}],
                "asks": [{"price": "0.86", "size": "100"}],
                "timestamp": datetime.utcnow().isoformat()
            }

        if not self.client:
            logger.error("CLOB client not initialized")
            return {"bids": [], "asks": []}

        try:
            # Get orderbook from Polymarket
            orderbook = self.client.get_order_book(token_id)

            # Calculate probabilities from mid price
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])

            best_bid = float(bids[0]["price"]) if bids else 0.0
            best_ask = float(asks[0]["price"]) if asks else 1.0
            mid_price = (best_bid + best_ask) / 2

            return {
                "bids": bids,
                "asks": asks,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "mid_price": mid_price,
                "probability": mid_price,  # Mid price approximates probability
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.exception(f"Error getting orderbook for {token_id}: {e}")
            return {"bids": [], "asks": []}

    async def place_order(
        self,
        token_id: str,
        side: str,
        size: float,
        price: float,
        order_type: str = "GTC"  # Good-Til-Cancelled
    ) -> Optional[str]:
        """
        Place a limit order.

        Args:
            token_id: Token to buy/sell
            side: "BUY" or "SELL"
            size: Number of shares
            price: Limit price (0.0 - 1.0)
            order_type: Order type (GTC, FOK, etc.)

        Returns:
            Order ID or None if failed
        """
        # Paper trading mode
        if settings.paper_trading:
            logger.info(
                f"📝 PAPER TRADE: {side} {size:.2f} shares of {token_id} @ ${price:.4f}"
            )
            return f"paper-{datetime.utcnow().timestamp()}"

        if not self.client:
            logger.error("CLOB client not initialized - cannot place real order")
            return None

        try:
            # Create order arguments
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side.upper(),
                fee_rate_bps=0,  # Will be set by client
            )

            # Place order
            signed_order = self.client.create_order(order_args)
            resp = self.client.post_order(signed_order, order_type=order_type)

            order_id = resp.get("orderID")
            logger.info(
                f"✅ Order placed: {side} {size:.2f} shares @ ${price:.4f} "
                f"(Order ID: {order_id})"
            )

            return order_id

        except Exception as e:
            logger.exception(f"❌ Error placing order: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Success status
        """
        if settings.paper_trading:
            logger.info(f"📝 Paper trading: simulating cancel order {order_id}")
            return True

        if not self.client:
            logger.error("CLOB client not initialized")
            return False

        try:
            self.client.cancel_order(order_id)
            logger.info(f"✅ Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.exception(f"❌ Error cancelling order {order_id}: {e}")
            return False

    async def get_positions(self) -> List[Dict]:
        """
        Get current open positions.

        Returns:
            List of position objects
        """
        if settings.paper_trading:
            logger.debug("📝 Paper trading: no real positions")
            return []

        if not self.client:
            logger.error("CLOB client not initialized")
            return []

        try:
            positions = self.client.get_positions()
            return positions

        except Exception as e:
            logger.exception(f"Error getting positions: {e}")
            return []

    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get status of a specific order.

        Args:
            order_id: Order ID

        Returns:
            Order status dict or None
        """
        if settings.paper_trading:
            logger.debug(f"📝 Paper trading: simulating order status for {order_id}")
            return {
                "orderID": order_id,
                "status": "FILLED",
                "timestamp": datetime.utcnow().isoformat()
            }

        if not self.client:
            logger.error("CLOB client not initialized")
            return None

        try:
            order = self.client.get_order(order_id)
            return order

        except Exception as e:
            logger.exception(f"Error getting order status for {order_id}: {e}")
            return None

    async def close(self):
        """Close HTTP client connections."""
        await self.http_client.aclose()
        logger.info("Polymarket client connections closed")

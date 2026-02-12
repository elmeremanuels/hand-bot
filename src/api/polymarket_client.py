"""
Polymarket API client for interacting with prediction markets.
Handles authentication, market queries, and order placement.
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct
import json

logger = logging.getLogger(__name__)


class PolymarketClient:
    """
    Client for interacting with Polymarket API.

    Features:
    - Market queries and filtering
    - Orderbook data
    - Order placement (market orders)
    - Balance checking
    - Authentication with private key signing
    """

    # Polymarket API endpoints
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_API_URL = "https://gamma-api.polymarket.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        paper_trading: bool = True,
    ):
        """
        Initialize Polymarket client.

        Args:
            api_key: Polymarket API key (CLOB_API_KEY)
            private_key: Ethereum private key for signing (0x...)
            paper_trading: If True, simulate orders instead of placing them
        """
        self.api_key = api_key
        self.private_key = private_key
        self.paper_trading = paper_trading

        self.session: Optional[aiohttp.ClientSession] = None
        self.account: Optional[Account] = None

        # Paper trading state
        self.paper_balance = 1000.0  # Simulated starting balance
        self.paper_orders: List[Dict] = []

        logger.info(
            f"Polymarket client initialized (mode: {'📝 Paper' if paper_trading else '💰 Live'})"
        )

    async def initialize(self):
        """Initialize the client session and authentication."""
        # Create aiohttp session
        self.session = aiohttp.ClientSession(
            headers={
                "Content-Type": "application/json",
            }
        )

        # Initialize Ethereum account for signing
        if self.private_key and not self.paper_trading:
            try:
                self.account = Account.from_key(self.private_key)
                logger.info(f"🔐 Authenticated with address: {self.account.address}")
            except Exception as e:
                logger.error(f"Failed to initialize account: {e}")
                raise

        logger.info("✅ Polymarket client initialized")

    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            logger.debug("Session closed")

    # ==================== MARKET QUERIES ====================

    async def find_crypto_markets(
        self, asset: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find active crypto Up/Down markets.

        Args:
            asset: Filter by asset (bitcoin, ethereum, solana, xrp)

        Returns:
            List of market dictionaries
        """
        try:
            # Query Gamma API for markets
            url = f"{self.GAMMA_API_URL}/markets"

            params = {
                "active": "true",
                "closed": "false",
            }

            if asset:
                # Add asset filter
                params["tag"] = asset.lower()

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch markets: {response.status}")
                    return []

                data = await response.json()

                # Filter for crypto Up/Down markets
                markets = []
                for market in data:
                    if self._is_crypto_updown_market(market):
                        parsed = self._parse_market(market)
                        if parsed:
                            markets.append(parsed)

                return markets

        except Exception as e:
            logger.exception(f"Error fetching markets: {e}")
            return []

    def _is_crypto_updown_market(self, market: Dict) -> bool:
        """
        Check if a market is a crypto Up/Down market.

        Args:
            market: Market data

        Returns:
            True if crypto Up/Down market
        """
        question = market.get("question", "").lower()
        description = market.get("description", "").lower()

        # Check for crypto keywords
        crypto_keywords = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp"]
        has_crypto = any(kw in question or kw in description for kw in crypto_keywords)

        # Check for Up/Down structure
        has_updown = "above" in question or "below" in question or "will" in question

        return has_crypto and has_updown

    def _parse_market(self, market: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse raw market data into structured format.

        Args:
            market: Raw market data from API

        Returns:
            Parsed market dict or None
        """
        try:
            # Extract basic info
            market_id = market.get("condition_id")
            question = market.get("question", "")
            slug = market.get("slug", "")

            # Get end time
            end_date_str = market.get("end_date_iso")
            if end_date_str:
                end_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            else:
                end_time = None

            # Get tokens (outcomes)
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                return None

            # Typically tokens[0] = YES/UP, tokens[1] = NO/DOWN
            token_up = tokens[0]
            token_down = tokens[1]

            # Extract asset from question
            asset = self._extract_asset(question)

            return {
                "market_id": market_id,
                "question": question,
                "slug": slug,
                "end_time": end_time,
                "token_id_up": token_up.get("token_id"),
                "token_id_down": token_down.get("token_id"),
                "asset": asset,
                "volume_24h": float(market.get("volume_24hr", 0)),
                "liquidity": float(market.get("liquidity", 0)),
            }

        except Exception as e:
            logger.exception(f"Error parsing market: {e}")
            return None

    def _extract_asset(self, question: str) -> str:
        """
        Extract asset name from market question.

        Args:
            question: Market question

        Returns:
            Asset name (bitcoin, ethereum, solana, xrp)
        """
        question_lower = question.lower()

        if "bitcoin" in question_lower or "btc" in question_lower:
            return "bitcoin"
        elif "ethereum" in question_lower or "eth" in question_lower:
            return "ethereum"
        elif "solana" in question_lower or "sol" in question_lower:
            return "solana"
        elif "xrp" in question_lower:
            return "xrp"
        else:
            return "bitcoin"  # Default

    async def get_market(self, market_id: str) -> Optional[Dict]:
        """
        Get detailed market information.

        Args:
            market_id: Market/condition ID

        Returns:
            Market data or None
        """
        try:
            url = f"{self.GAMMA_API_URL}/markets/{market_id}"

            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch market {market_id}: {response.status}")
                    return None

                return await response.json()

        except Exception as e:
            logger.exception(f"Error fetching market {market_id}: {e}")
            return None

    async def get_market_orderbook(self, token_id: str) -> Dict[str, Any]:
        """
        Get orderbook for a specific token.

        Args:
            token_id: Token ID

        Returns:
            Orderbook data with bids, asks, and probability
        """
        try:
            url = f"{self.BASE_URL}/book"
            params = {"token_id": token_id}

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch orderbook for {token_id}: {response.status}")
                    return self._empty_orderbook()

                data = await response.json()

                # Parse orderbook
                bids = data.get("bids", [])
                asks = data.get("asks", [])

                # Calculate best bid/ask
                best_bid = float(bids[0]["price"]) if bids else 0.0
                best_ask = float(asks[0]["price"]) if asks else 1.0

                # Estimate probability from mid-price
                mid_price = (best_bid + best_ask) / 2.0

                return {
                    "token_id": token_id,
                    "bids": bids,
                    "asks": asks,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "probability": mid_price,
                }

        except Exception as e:
            logger.exception(f"Error fetching orderbook for {token_id}: {e}")
            return self._empty_orderbook()

    def _empty_orderbook(self) -> Dict[str, Any]:
        """Return empty orderbook structure."""
        return {
            "token_id": None,
            "bids": [],
            "asks": [],
            "best_bid": 0.0,
            "best_ask": 1.0,
            "probability": 0.5,
        }

    # ==================== ORDER PLACEMENT ====================

    async def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Place a market order.

        Args:
            token_id: Token ID to trade
            side: "buy" or "sell"
            amount: Number of shares to trade

        Returns:
            Order response or None
        """
        if self.paper_trading:
            return await self._place_paper_order(token_id, side, amount)
        else:
            return await self._place_real_order(token_id, side, amount)

    async def _place_real_order(
        self, token_id: str, side: str, amount: float
    ) -> Optional[Dict[str, Any]]:
        """
        Place a real order on Polymarket CLOB.

        Args:
            token_id: Token ID
            side: "buy" or "sell"
            amount: Number of shares

        Returns:
            Order response
        """
        try:
            # Get current orderbook to determine price
            orderbook = await self.get_market_orderbook(token_id)

            if side == "buy":
                price = orderbook["best_ask"]  # Take the ask
            else:
                price = orderbook["best_bid"]  # Hit the bid

            # Build order payload
            order = {
                "token_id": token_id,
                "side": side,
                "type": "market",
                "size": str(amount),
                "price": str(price),
            }

            # Sign order
            signed_order = self._sign_order(order)

            # Submit order
            url = f"{self.BASE_URL}/order"

            async with self.session.post(url, json=signed_order) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Order placement failed: {response.status} - {error}")
                    return None

                result = await response.json()
                logger.info(f"✅ Order placed: {result.get('order_id')}")

                return result

        except Exception as e:
            logger.exception(f"Error placing real order: {e}")
            return None

    async def _place_paper_order(
        self, token_id: str, side: str, amount: float
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate a paper order.

        Args:
            token_id: Token ID
            side: "buy" or "sell"
            amount: Number of shares

        Returns:
            Simulated order response
        """
        # Get current orderbook for realistic pricing
        orderbook = await self.get_market_orderbook(token_id)

        if side == "buy":
            price = orderbook["best_ask"]
        else:
            price = orderbook["best_bid"]

        cost = amount * price

        # Check paper balance
        if side == "buy" and cost > self.paper_balance:
            logger.warning(f"Insufficient paper balance: ${self.paper_balance:.2f} < ${cost:.2f}")
            return None

        # Deduct from paper balance (for buys)
        if side == "buy":
            self.paper_balance -= cost

        # Create simulated order
        order_id = f"paper_{token_id}_{int(datetime.utcnow().timestamp())}"

        order = {
            "order_id": order_id,
            "token_id": token_id,
            "side": side,
            "amount": amount,
            "price": price,
            "cost": cost,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "filled",
        }

        self.paper_orders.append(order)

        logger.info(
            f"📝 Paper order: {side.upper()} {amount:.0f} shares @ ${price:.3f} "
            f"(cost: ${cost:.2f}, balance: ${self.paper_balance:.2f})"
        )

        return order

    def _sign_order(self, order: Dict) -> Dict:
        """
        Sign an order with the private key.

        Args:
            order: Order payload

        Returns:
            Signed order with signature
        """
        if not self.account:
            raise ValueError("Account not initialized")

        # Create message to sign
        message = json.dumps(order, sort_keys=True)
        message_hash = encode_defunct(text=message)

        # Sign message
        signed = self.account.sign_message(message_hash)

        # Add signature to order
        order["signature"] = signed.signature.hex()

        return order

    # ==================== BALANCE ====================

    async def get_balance(self) -> float:
        """
        Get account balance in USDC.

        Returns:
            Balance in USD
        """
        if self.paper_trading:
            return self.paper_balance

        try:
            # Query balance from Polymarket
            url = f"{self.BASE_URL}/balance"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch balance: {response.status}")
                    return 0.0

                data = await response.json()
                balance = float(data.get("balance", 0))

                logger.debug(f"💰 Balance: ${balance:.2f}")
                return balance

        except Exception as e:
            logger.exception(f"Error fetching balance: {e}")
            return 0.0

    async def get_open_orders(self) -> List[Dict]:
        """
        Get all open orders.

        Returns:
            List of open orders
        """
        if self.paper_trading:
            # Return paper orders that are "open" (not filled)
            return [o for o in self.paper_orders if o.get("status") != "filled"]

        try:
            url = f"{self.BASE_URL}/orders"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch orders: {response.status}")
                    return []

                data = await response.json()
                return data.get("orders", [])

        except Exception as e:
            logger.exception(f"Error fetching orders: {e}")
            return []

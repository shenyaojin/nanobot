"""Binance exchange tool wrapping the coin_margined_fra Exchange class."""

import os
import asyncio
from typing import Any, Dict, List, Optional
import pandas as pd
from dotenv import load_dotenv
from nanobot.agent.tools.base import Tool

class BinanceTool(Tool):
    """
    Tool to interact with Binance exchange via the coin_margined_fra package.
    Supports spot and COIN-M inverse futures.
    """

    def __init__(self, sandbox_mode: bool = True, username: str = 'default'):
        self._sandbox_mode = sandbox_mode
        self._username = username
        self._exchange = None
        # Load environment variables from standard locations if not already set
        self._load_env()

    def _load_env(self):
        """Load environment variables from common .env locations."""
        # Check for a user-specified .env path
        env_path = os.getenv("BINANCE_DOTENV_PATH")
        if env_path and os.path.exists(env_path):
            load_dotenv(env_path)
        else:
            # Default to the path used in the user's provided example
            default_crypto_env = "/home/ubuntu/.crypto/.env"
            if os.path.exists(default_crypto_env):
                load_dotenv(default_crypto_env)
            # Also try the standard project root .env
            if os.path.exists(".env"):
                load_dotenv(".env")

    def _get_exchange(self):
        """Lazy load and initialize the exchange client."""
        if self._exchange is None:
            try:
                from coin_margined_fra.core.exchange import Exchange
            except ImportError:
                raise ImportError(
                    "The 'coin_margined_fra' package is not installed in the current environment. "
                    "Please ensure you are running in the 'oc_crypto' conda environment."
                )

            if self._sandbox_mode:
                api_key = os.getenv("BINANCE_TESTNET_API_KEY")
                api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")
            else:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_API_SECRET")

            if not api_key or not api_secret:
                raise ValueError(
                    f"Binance API credentials not found in environment for "
                    f"{'sandbox' if self._sandbox_mode else 'production'} mode. "
                    f"Please set BINANCE{'_TESTNET' if self._sandbox_mode else ''}_API_KEY/SECRET."
                )

            self._exchange = Exchange(
                api_key=api_key,
                api_secret=api_secret,
                sandbox_mode=self._sandbox_mode,
                username=self._username
            )
        return self._exchange

    @property
    def name(self) -> str:
        return "binance"

    @property
    def description(self) -> str:
        return (
            "Interact with Binance exchange for spot and inverse futures. "
            "Supported actions: get_balances, get_positions, get_prices, "
            "get_funding_rates, get_trade_fee, set_leverage, create_order, "
            "transfer, get_convert_trade_history, get_income_history."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform on Binance.",
                    "enum": [
                        "get_balances",
                        "get_positions",
                        "get_prices",
                        "get_funding_rates",
                        "get_trade_fee",
                        "set_leverage",
                        "create_order",
                        "transfer",
                        "wait_for_order_to_fill",
                        "get_convert_trade_history",
                        "get_income_history"
                    ]
                },
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of symbols for get_prices (e.g., ['BTC/USDT', 'BTC/USD:BTC'])."
                },
                "symbol": {
                    "type": "string",
                    "description": "A single symbol for get_trade_fee, set_leverage, or create_order."
                },
                "leverage": {
                    "type": "integer",
                    "description": "Leverage value for set_leverage."
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Order side for create_order."
                },
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit"],
                    "description": "Order type for create_order."
                },
                "amount": {
                    "type": "number",
                    "description": "Order amount (quantity) for create_order or transfer."
                },
                "price": {
                    "type": "number",
                    "description": "Order price for limit orders."
                },
                "coin": {
                    "type": "string",
                    "description": "Coin for transfer (e.g., 'BTC')."
                },
                "from_account": {
                    "type": "string",
                    "enum": ["spot", "inverse"],
                    "description": "Source account for transfer."
                },
                "to_account": {
                    "type": "string",
                    "enum": ["spot", "inverse"],
                    "description": "Destination account for transfer."
                },
                "order_params": {
                    "type": "object",
                    "description": "Additional parameters for create_order (e.g., {'quoteOrderQty': 100})."
                },
                "income_type": {
                    "type": "string",
                    "description": "Income type for get_income_history (e.g., 'FUNDING_FEE')."
                },
                "limit": {
                    "type": "integer",
                    "description": "Result limit for history actions."
                },
                "since": {
                    "type": "integer",
                    "description": "Timestamp in ms for history actions."
                },
                "order_id": {
                    "type": "string",
                    "description": "Order ID to wait for."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds to wait for an order (default 60)."
                },
                "is_inverse": {
                    "type": "boolean",
                    "description": "Whether the order is on the inverse/futures exchange."
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        try:
            exchange = self._get_exchange()
            
            if action == "get_balances":
                return await self._get_balances(exchange)
            elif action == "get_positions":
                return await self._get_positions(exchange)
            elif action == "get_prices":
                return await self._get_prices(exchange, kwargs.get("symbols"))
            elif action == "get_funding_rates":
                return await self._get_funding_rates(exchange)
            elif action == "get_trade_fee":
                return await self._get_trade_fee(exchange, kwargs.get("symbol"))
            elif action == "set_leverage":
                return await self._set_leverage(exchange, kwargs.get("symbol"), kwargs.get("leverage"))
            elif action == "create_order":
                return await self._create_order(
                    exchange, 
                    kwargs.get("symbol"), 
                    kwargs.get("order_type"), 
                    kwargs.get("side"), 
                    kwargs.get("amount"), 
                    kwargs.get("price"), 
                    kwargs.get("order_params", {})
                )
            elif action == "transfer":
                return await self._transfer(
                    exchange, 
                    kwargs.get("coin"), 
                    kwargs.get("amount"), 
                    kwargs.get("from_account"), 
                    kwargs.get("to_account")
                )
            elif action == "wait_for_order_to_fill":
                return await self._wait_for_order_to_fill(
                    exchange,
                    kwargs.get("order_id"),
                    kwargs.get("symbol"),
                    kwargs.get("timeout", 60),
                    kwargs.get("is_inverse", False)
                )
            elif action == "get_convert_trade_history":
                return await self._get_convert_trade_history(
                    exchange, 
                    kwargs.get("coin"), 
                    kwargs.get("since"), 
                    kwargs.get("limit")
                )
            elif action == "get_income_history":
                return await self._get_income_history(
                    exchange, 
                    kwargs.get("income_type", "FUNDING_FEE"), 
                    kwargs.get("symbol"), 
                    kwargs.get("limit", 100)
                )
            else:
                return f"Error: Action '{action}' not implemented."

        except Exception as e:
            return f"Error executing Binance action '{action}': {str(e)}"

    async def _get_balances(self, exchange) -> str:
        balances = await asyncio.to_thread(exchange.get_balances)
        res = "### Account Balances\n\n"
        if not balances['spot'].empty:
            res += "**Spot Wallet:**\n\n" + balances['spot'].to_markdown() + "\n\n"
        if not balances['inverse'].empty:
            res += "**COIN-M (Inverse Futures) Wallet:**\n\n" + balances['inverse'].to_markdown() + "\n"
        
        if balances['spot'].empty and balances['inverse'].empty:
            return "No non-zero balances found in spot or inverse wallets."
        return res

    async def _get_positions(self, exchange) -> str:
        positions = await asyncio.to_thread(exchange.get_positions)
        if positions.empty:
            return "No open COIN-M (Inverse Futures) positions found."
        return "### Open COIN-M Positions\n\n" + positions.to_markdown()

    async def _get_prices(self, exchange, symbols: List[str]) -> str:
        if not symbols:
            return "Error: 'symbols' parameter is required for get_prices."
        prices = await asyncio.to_thread(exchange.get_market_prices, symbols)
        if not prices:
            return "No price data found for the specified symbols."
        df = pd.DataFrame(list(prices.items()), columns=['Symbol', 'Price'])
        return "### Market Prices\n\n" + df.to_markdown(index=False)

    async def _get_funding_rates(self, exchange) -> str:
        df = await asyncio.to_thread(exchange.get_funding_rates)
        if df.empty:
            return "No funding rate data available."
        return "### Funding Rates\n\n" + df.to_markdown()

    async def _get_trade_fee(self, exchange, symbol: str) -> str:
        if not symbol:
            return "Error: 'symbol' parameter is required for get_trade_fee."
        df = await asyncio.to_thread(exchange.get_trade_fee, symbol)
        if df.empty:
            return f"No trade fee data found for {symbol}."
        return f"### Trade Fee for {symbol}\n\n" + df.to_markdown()

    async def _set_leverage(self, exchange, symbol: str, leverage: int) -> str:
        if not symbol or leverage is None:
            return "Error: 'symbol' and 'leverage' parameters are required."
        success = await asyncio.to_thread(exchange.set_leverage, symbol, leverage)
        return f"{'Successfully set' if success else 'Failed to set'} leverage to {leverage}x for {symbol}."

    async def _create_order(self, exchange, symbol, order_type, side, amount, price, params) -> str:
        if not all([symbol, order_type, side]):
            return "Error: 'symbol', 'order_type', and 'side' are required for create_order."
        
        # Binance API is sensitive to scientific notation (e.g., 1e-05).
        # We ensure amount and price are passed as floats, but we also provide
        # explicit guidance in the skill documentation.
        # If amount is provided, ensure it's a float or None.
        if amount is not None:
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return f"Error: Invalid amount '{amount}'. Must be a number."

        if price is not None:
            try:
                price = float(price)
            except (ValueError, TypeError):
                return f"Error: Invalid price '{price}'. Must be a number."

        order = await asyncio.to_thread(
            exchange.create_order, 
            symbol, order_type, side, amount, price, params
        )
        if not order:
            return "Failed to create order. Check logs for details (likely precision or balance issue)."
        return f"Order created successfully:\n\n```json\n{order}\n```"

    async def _transfer(self, exchange, coin, amount, from_acc, to_acc) -> str:
        if not all([coin, amount, from_acc, to_acc]):
            return "Error: 'coin', 'amount', 'from_account', and 'to_account' are required for transfer."
        
        # Ensure coin is uppercase (Binance requirement)
        coin = str(coin).upper()
        
        # Ensure amount is a float to avoid scientific notation or string issues
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return f"Error: Invalid amount '{amount}'. Must be a number."

        result = await asyncio.to_thread(exchange.transfer, coin, amount, from_acc, to_acc)
        if not result or (isinstance(result, dict) and not result.get('tranId')):
            return "Failed to execute transfer. Ensure you have sufficient balance and both wallets are active."
        return f"Transfer successful:\n\n```json\n{result}\n```"

    async def _wait_for_order_to_fill(self, exchange, order_id, symbol, timeout, is_inverse) -> str:
        if not order_id or not symbol:
            return "Error: 'order_id' and 'symbol' are required for wait_for_order_to_fill."
        filled = await asyncio.to_thread(exchange.wait_for_order_to_fill, order_id, symbol, timeout, is_inverse)
        return f"Order {order_id} {'is filled' if filled else 'did not fill within timeout'}."

    async def _get_convert_trade_history(self, exchange, coin, since, limit) -> str:
        df = await asyncio.to_thread(exchange.get_convert_trade_history, coin, since, limit)
        if df.empty:
            return "No convert trade history found."
        return "### Convert Trade History\n\n" + df.to_markdown()

    async def _get_income_history(self, exchange, income_type, symbol, limit) -> str:
        df = await asyncio.to_thread(exchange.get_income_history, income_type, symbol, limit)
        if df.empty:
            return "No income history found."
        return f"### Income History ({income_type})\n\n" + df.to_markdown()

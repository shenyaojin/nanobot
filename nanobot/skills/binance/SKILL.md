---
name: binance
description: Connect to Binance exchange for spot and COIN-M inverse futures trading.
metadata: {"nanobot":{"emoji":"📈","requires":{"envs":["BINANCE_API_KEY", "BINANCE_API_SECRET"]}}}
---

# Binance Exchange

Interact with Binance Spot and COIN-M Inverse Futures using the `binance` tool.

## Symbols Format

- **Spot:** `BASE/QUOTE` (e.g., `BTC/USDT`, `ETH/USDT`)
- **COIN-M (Inverse Futures):** `BASE/QUOTE:SETTLEMENT` (e.g., `BTC/USD:BTC`, `ETH/USD:ETH`)

## Order Parameters Setup

When calling `binance(action="create_order", ...)`:

### 1. Spot Market Buy (Spending USDT)
To spend a specific amount of USDT (quote currency) instead of buying a specific amount of the asset:
- Set `side="buy"`, `order_type="market"`.
- Set `amount=null`.
- Set `order_params={"quoteOrderQty": 100}` (to spend 100 USDT).

### 2. Spot Market Sell (Selling Asset)
- Set `side="sell"`, `order_type="market"`.
- Set `amount` to the asset quantity (e.g., `0.005` for 0.005 BTC).

### 3. COIN-M Futures (Inverse)
- **Amount is in CONTRACTS**, not the coin amount.
  - For `BTC/USD:BTC`: 1 contract = **$100 USD**.
  - For `ETH/USD:ETH`: 1 contract = **$10 USD**.
- **Example:** To open a $1000 short position on BTC, use `amount=10` (10 * $100).
- **Leverage:** Use `binance(action="set_leverage", symbol="BTC/USD:BTC", leverage=10)` **BEFORE** creating the order.

## Transfers

Transfer funds between your Spot and COIN-M accounts using `binance(action="transfer", ...)`.

### Mandatory Requirements:
1.  **Asset Name:** Must be the base coin (e.g., `BTC`, `ETH`, `BNB`). Always provide it in uppercase.
2.  **Wallet Activation:** Both your Spot and COIN-M accounts must be fully set up on Binance.
3.  **Available Balance:** You must have enough of the asset in the source account. Note that locked funds (in open orders or used as margin) cannot be transferred.
4.  **Transfer Direction:**
    - `from_account="spot"`, `to_account="inverse"`: Move from Spot to COIN-M.
    - `from_account="inverse"`, `to_account="spot"`: Move from COIN-M back to Spot.

### Common Transfer Errors:
- **"Unknown Error":** Usually caused by trying to transfer an asset with 0 balance or using scientific notation in the amount (fixed in this tool).
- **"Account has insufficient balance":** Check `get_balances` first to ensure enough "free" or "withdrawAvailable" funds exist.

## Handling Precision & Scientific Notation

If you receive an error about "Illegal characters" in `quantity` or `amount`:
1. Ensure the value is a pure number (integer or float).
2. For very small amounts (e.g., 0.00001), the tool now handles type conversion, but ensure you aren't passing it as a string formatted as "1e-05".
3. Check the market's "Lot Size" (minimum quantity).

## Examples

### View Account
```bash
# Check non-zero balances in Spot and COIN-M
binance(action="get_balances")

# Check open futures positions
binance(action="get_positions")
```

### Trading Example
```bash
# Spend 50 USDT to buy BTC on Spot
binance(action="create_order", symbol="BTC/USDT", side="buy", order_type="market", amount=null, order_params={"quoteOrderQty": 50})

# Open a 5 contract long position on ETH/USD Inverse Futures at 10x leverage
binance(action="set_leverage", symbol="ETH/USD:ETH", leverage=10)
binance(action="create_order", symbol="ETH/USD:ETH", side="buy", order_type="market", amount=5)
```

### Transfers
```bash
# Move 0.005 BTC from Spot to COIN-M Futures wallet
binance(action="transfer", coin="BTC", amount=0.005, from_account="spot", to_account="inverse")
```

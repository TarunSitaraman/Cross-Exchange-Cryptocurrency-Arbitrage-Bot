import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from exchange_client import ExchangeClient, OrderResult
from arbitrage_detector import ArbitrageOpportunity
from logger import setup_logger

logger = setup_logger("execution_engine")

@dataclass
class ExecutionResult:
    opp_id: str
    buy_order: Optional[OrderResult]
    sell_order: Optional[OrderResult]
    buy_filled: float
    sell_filled: float
    actual_net_profit: float
    execution_time_sec: float
    status: str                    # 'success', 'partial', 'failed', 'cancelled'
    notes: str

class ExecutionEngine:
    def __init__(self, client: ExchangeClient):
        self.client = client
        self.failed_attempts = 0

    async def execute_arbitrage(self, opp: ArbitrageOpportunity) -> ExecutionResult:
        start_time = time.time()
        logger.info(f"Executing Arbitrage: Buy {opp.buy_exchange} ({opp.buy_price}), Sell {opp.sell_exchange} ({opp.sell_price}), Qty {opp.quantity}")

        if self.failed_attempts >= 3:
            logger.error("Circuit breaker triggered: Too many failed execution attempts.")
            raise Exception("Circuit breaker triggered: Too many failed execution attempts.")

        # 1. Pre-flight checks
        buy_exchange_balances = await self.client.get_account_balance(opp.buy_exchange)
        sell_exchange_balances = await self.client.get_account_balance(opp.sell_exchange)

        # We need quote asset (e.g. USDT) on buy exchange and base asset (e.g. BTC) on sell exchange
        # More robust parsing: check common quotes first
        quote_asset = "USDT"
        if opp.symbol.endswith("USDT"):
            base_asset = opp.symbol[:-4]
            quote_asset = "USDT"
        elif opp.symbol.endswith("-USD"):
            base_asset = opp.symbol[:-4]
            quote_asset = "USD"
        elif opp.symbol.endswith("USD"):
            base_asset = opp.symbol[:-3]
            quote_asset = "USD"
        else:
            base_asset = opp.symbol # Fallback

        if base_asset == "XBT":
            base_asset = "BTC" # Kraken specific logic

        required_quote = opp.quantity * opp.buy_price
        required_base = opp.quantity

        buy_quote_balance = buy_exchange_balances.get(quote_asset, 0)
        sell_base_balance = sell_exchange_balances.get(base_asset, 0)
        
        if buy_quote_balance < required_quote or sell_base_balance < required_base:
            logger.warning(f"Insufficient balances. Buy Exch {quote_asset}: {buy_quote_balance}/{required_quote}. Sell Exch {base_asset}: {sell_base_balance}/{required_base}")
            return ExecutionResult(
                opp_id=str(int(start_time)),
                buy_order=None,
                sell_order=None,
                buy_filled=0,
                sell_filled=0,
                actual_net_profit=0,
                execution_time_sec=time.time() - start_time,
                status="failed",
                notes="Insufficient balances"
            )

        # 2. Simultaneous Order Placement
        try:
            buy_task = self.client.place_buy_order(
                opp.buy_exchange, opp.symbol, opp.quantity, opp.buy_price
            )
            sell_task = self.client.place_sell_order(
                opp.sell_exchange, opp.symbol, opp.quantity, opp.sell_price
            )
            
            # Place both orders at the same time
            buy_res, sell_res = await asyncio.gather(buy_task, sell_task)
            
        except Exception as e:
            logger.error(f"Critical failure during order placement: {e}")
            return ExecutionResult(
                opp_id=str(int(start_time)),
                buy_order=None,
                sell_order=None,
                buy_filled=0,
                sell_filled=0,
                actual_net_profit=0,
                execution_time_sec=time.time() - start_time,
                status="failed",
                notes=str(e)
            )

        # 3. Wait for Fills and Reconcile (Simplified for Phase 1)
        # In a real system, we would poll order status for ~10 seconds
        await asyncio.sleep(2) # Give it a moment to fill
        
        # Re-fetch order status (Mocked for now - assuming immediate fill or rejected)
        # In production, you would call get_order_status
        
        buy_filled = buy_res.filled_quantity if buy_res else 0
        sell_filled = sell_res.filled_quantity if sell_res else 0
        
        # Logic for status
        status = "success"
        notes = ""
        if buy_filled == 0 and sell_filled == 0:
            status = "failed"
        elif buy_filled < opp.quantity or sell_filled < opp.quantity:
            status = "partial"
            
        # Rollback / Hedging Logic for unhedged states
        if buy_filled != sell_filled:
            self.failed_attempts += 1
            diff = abs(buy_filled - sell_filled)
            import aiohttp

            async def execute_and_poll(exchange, symbol, qty, price, side):
                try:
                    if side == "sell":
                        order = await self.client.place_sell_order(exchange, symbol, qty, price)
                    else:
                        order = await self.client.place_buy_order(exchange, symbol, qty, price)

                    if not order or not order.order_id:
                        return False

                    # Poll for up to 10 seconds
                    for _ in range(10):
                        await asyncio.sleep(1)
                        status = await self.client.get_order_status(exchange, symbol, order.order_id)
                        if status and status.status == "filled":
                            return True
                        if status and status.status in ["cancelled", "rejected"]:
                            return False

                    # Timeout reached
                    await self.client.cancel_order(exchange, symbol, order.order_id)
                    return False
                except aiohttp.ClientError as e:
                    logger.error(f"Rollback client error: {e}")
                    return False

            if buy_filled > sell_filled:
                # Unhedged long exposure, need to sell
                logger.warning(f"Unhedged exposure ({diff} long). Attempting to rollback by selling on {opp.buy_exchange}")
                rollback_price = opp.buy_price * 0.95
                success = await execute_and_poll(opp.buy_exchange, opp.symbol, diff, rollback_price, "sell")
                notes = "Partial fill. Rolled back long exposure." if success else "Partial fill. Rollback FAILED."
            else:
                # Unhedged short exposure, need to buy
                logger.warning(f"Unhedged exposure ({diff} short). Attempting to rollback by buying on {opp.sell_exchange}")
                rollback_price = opp.sell_price * 1.05
                success = await execute_and_poll(opp.sell_exchange, opp.symbol, diff, rollback_price, "buy")
                notes = "Partial fill. Rolled back short exposure." if success else "Partial fill. Rollback FAILED."

        # 4. Calculation of realized profit
        # (Actually we should use the prices from the fills, but for now we assume slippage accounted)
        realized_profit = (sell_filled * opp.sell_price) - (buy_filled * opp.buy_price)

        # Get dynamic trading fees
        buy_fees = await self.client.get_trading_fees(opp.buy_exchange)
        sell_fees = await self.client.get_trading_fees(opp.sell_exchange)

        from config import EXCHANGE_FEES
        default_buy_fee = EXCHANGE_FEES.get(opp.buy_exchange, {}).get("taker", 0.001)
        default_sell_fee = EXCHANGE_FEES.get(opp.sell_exchange, {}).get("taker", 0.0026)

        buy_fee_pct = buy_fees.get("taker", default_buy_fee)
        sell_fee_pct = sell_fees.get("taker", default_sell_fee)

        # Subtract fees (simplified)
        realized_profit -= (buy_filled * opp.buy_price * buy_fee_pct) + (sell_filled * opp.sell_price * sell_fee_pct)

        result = ExecutionResult(
            opp_id=str(int(start_time)),
            buy_order=buy_res,
            sell_order=sell_res,
            buy_filled=buy_filled,
            sell_filled=sell_filled,
            actual_net_profit=realized_profit,
            execution_time_sec=time.time() - start_time,
            status=status,
            notes=notes
        )
        
        if status == "success":
            self.failed_attempts = 0 # Fully reset failures on a completely successful trade

        logger.info(f"Execution finished with status: {status}. Profit: {realized_profit:.4f} USDT")
        return result

async def test_execution():
    from exchange_client import ExchangeClient
    # This won't actually place orders if keys are invalid, but good for structure
    # Use a dummy client for simulation if needed
    pass

if __name__ == "__main__":
    asyncio.run(test_execution())

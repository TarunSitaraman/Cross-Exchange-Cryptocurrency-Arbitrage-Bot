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
        self.precondition_failures = 0

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
            self.precondition_failures += 1
            logger.info(f"Precondition failure count: {self.precondition_failures}")
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
            if buy_filled > sell_filled:
                # Unhedged long exposure, need to sell
                logger.warning(f"Unhedged exposure ({diff} long). Attempting to rollback by selling on {opp.buy_exchange}")
                notes = await self._execute_rollback(
                    exchange=opp.buy_exchange,
                    symbol=opp.symbol,
                    quantity=diff,
                    side="sell",
                    reference_price=opp.buy_price,
                    slippage_factor=0.95
                )
            else:
                # Unhedged short exposure, need to buy
                logger.warning(f"Unhedged exposure ({diff} short). Attempting to rollback by buying on {opp.sell_exchange}")
                notes = await self._execute_rollback(
                    exchange=opp.sell_exchange,
                    symbol=opp.symbol,
                    quantity=diff,
                    side="buy",
                    reference_price=opp.sell_price,
                    slippage_factor=1.05
                )

        # 4. Calculation of realized profit
        # (Actually we should use the prices from the fills, but for now we assume slippage accounted)
        realized_profit = (sell_filled * opp.sell_price) - (buy_filled * opp.buy_price)

        # Get dynamic trading fees
        buy_fees = await self.client.get_trading_fees(opp.buy_exchange)
        sell_fees = await self.client.get_trading_fees(opp.sell_exchange)
        buy_fee_pct = buy_fees.get("taker", 0.001)
        sell_fee_pct = sell_fees.get("taker", 0.0026)

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
            self.failed_attempts = max(0, self.failed_attempts - 1)

        logger.info(f"Execution finished with status: {status}. Profit: {realized_profit:.4f} USDT")
        return result

    async def _execute_rollback(
        self,
        exchange: str,
        symbol: str,
        quantity: float,
        side: str,
        reference_price: float,
        slippage_factor: float
    ) -> str:
        """
        Execute a rollback order with status polling and timeout handling.

        Args:
            exchange: Exchange to execute on
            symbol: Trading symbol
            quantity: Quantity to rollback
            side: 'buy' or 'sell'
            reference_price: Reference price for the order
            slippage_factor: Price adjustment factor (0.95 for sell, 1.05 for buy)

        Returns:
            Status message string
        """
        rollback_price = reference_price * slippage_factor
        rollback_order = None

        try:
            # Place the rollback order
            if side == "sell":
                rollback_order = await self.client.place_sell_order(exchange, symbol, quantity, rollback_price)
            else:
                rollback_order = await self.client.place_buy_order(exchange, symbol, quantity, rollback_price)

            if not rollback_order or not rollback_order.order_id:
                logger.error("Rollback order placement returned no order ID")
                return "Partial fill. Rollback order placement FAILED."

            logger.info(f"Rollback order placed: {rollback_order.order_id}")

            # Poll order status with timeout
            timeout_sec = 10
            poll_interval_sec = 1
            elapsed = 0

            while elapsed < timeout_sec:
                await asyncio.sleep(poll_interval_sec)
                elapsed += poll_interval_sec

                try:
                    status_result = await self.client.get_order_status(exchange, symbol, rollback_order.order_id)

                    if status_result.status == "filled":
                        logger.info(f"Rollback order {rollback_order.order_id} filled successfully")
                        return f"Partial fill. Rolled back {side} exposure successfully."
                    elif status_result.status in ["cancelled", "rejected"]:
                        logger.error(f"Rollback order {rollback_order.order_id} was {status_result.status}")
                        return f"Partial fill. Rollback {status_result.status}."
                    elif status_result.status == "partially_filled":
                        logger.warning(f"Rollback order {rollback_order.order_id} partially filled: {status_result.filled_quantity}/{quantity}")
                        # Continue polling

                except ValueError as e:
                    # Exchange not supported or other validation error
                    logger.error(f"Rollback status check failed with ValueError: {e}")
                    return f"Partial fill. Rollback status check FAILED: {e}"
                except Exception as e:
                    # API errors during status check
                    logger.error(f"Rollback status check failed: {e}")
                    # Continue polling in case it's a transient error

            # Timeout reached - cancel the order
            logger.warning(f"Rollback order {rollback_order.order_id} timed out after {timeout_sec}s")
            try:
                cancel_success = await self.client.cancel_order(exchange, symbol, rollback_order.order_id)
                if cancel_success:
                    logger.info(f"Rollback order {rollback_order.order_id} cancelled successfully")
                    return "Partial fill. Rollback timed out and cancelled."
                else:
                    logger.error(f"Failed to cancel rollback order {rollback_order.order_id}")
                    return "Partial fill. Rollback timed out, cancel FAILED."
            except ValueError as e:
                logger.error(f"Rollback cancel failed with ValueError: {e}")
                return f"Partial fill. Rollback cancel FAILED: {e}"
            except Exception as e:
                logger.error(f"Rollback cancel failed: {e}")
                return f"Partial fill. Rollback cancel FAILED: {e}"

        except ValueError as e:
            # Exchange not supported or validation errors
            logger.error(f"Rollback order placement failed with ValueError: {e}")
            return f"Partial fill. Rollback FAILED: {e}"
        except Exception as e:
            # Re-raise unexpected errors instead of swallowing them
            logger.error(f"Unexpected error during rollback: {e}")
            raise

async def test_execution():
    from exchange_client import ExchangeClient
    # This won't actually place orders if keys are invalid, but good for structure
    # Use a dummy client for simulation if needed
    pass

if __name__ == "__main__":
    asyncio.run(test_execution())

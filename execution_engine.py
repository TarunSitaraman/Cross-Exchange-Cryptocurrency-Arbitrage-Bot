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

    async def execute_arbitrage(self, opp: ArbitrageOpportunity) -> ExecutionResult:
        start_time = time.time()
        logger.info(f"Executing Arbitrage: Buy {opp.buy_exchange} ({opp.buy_price}), Sell {opp.sell_exchange} ({opp.sell_price}), Qty {opp.quantity}")

        # 1. Pre-flight checks
        # TODO: Implement balance checks here if needed, but for MVP we assume pre-funded
        
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
        if buy_filled == 0 and sell_filled == 0:
            status = "failed"
        elif buy_filled < opp.quantity or sell_filled < opp.quantity:
            status = "partial"
            
        # 4. Calculation of realized profit
        # (Actually we should use the prices from the fills, but for now we assume slippage accounted)
        realized_profit = (sell_filled * opp.sell_price) - (buy_filled * opp.buy_price)
        # Subtract fees (simplified)
        realized_profit -= (buy_filled * opp.buy_price * 0.001) + (sell_filled * opp.sell_price * 0.0026)

        result = ExecutionResult(
            opp_id=str(int(start_time)),
            buy_order=buy_res,
            sell_order=sell_res,
            buy_filled=buy_filled,
            sell_filled=sell_filled,
            actual_net_profit=realized_profit,
            execution_time_sec=time.time() - start_time,
            status=status,
            notes=""
        )
        
        logger.info(f"Execution finished with status: {status}. Profit: {realized_profit:.4f} USDT")
        return result

async def test_execution():
    from exchange_client import ExchangeClient
    # This won't actually place orders if keys are invalid, but good for structure
    # Use a dummy client for simulation if needed
    pass

if __name__ == "__main__":
    asyncio.run(test_execution())

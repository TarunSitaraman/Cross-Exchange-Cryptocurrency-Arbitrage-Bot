import asyncio
import time
from exchange_client import ExchangeClient
from arbitrage_detector import compute_spread
from execution_engine import ExecutionEngine
from portfolio_manager import Portfolio, PortfolioManager
from risk_manager import RiskManager
from order_book_monitor import OrderBookMonitor
from state_persistence import save_bot_state
from logger import setup_logger
from config import (
    SYMBOLS, EXCHANGES, EXCHANGE_FEES,
    WITHDRAWAL_FEES_BTC, PAPER_TRADING,
    DEFAULT_TRADE_QTY
)
import itertools

logger = setup_logger("main")

class CryptoArbBot:
    def __init__(self):
        self.portfolio = Portfolio()
        self.portfolio_manager = PortfolioManager(self.portfolio)
        self.risk_manager = RiskManager(self.portfolio)
        self.monitor = None 
        
    async def run(self):
        mode = "PAPER TRADING (SIMULATION)" if PAPER_TRADING else "LIVE TRADING"
        logger.info(f"Starting Cross-Exchange Arbitrage Bot Phase 2... [{mode}]")
        
        async with ExchangeClient() as client:
            self.monitor = OrderBookMonitor(client)
            execution_engine = ExecutionEngine(client)
            
            while True:
                try:
                    logger.info(f"Cycle start - Monitoring {len(SYMBOLS)} assets across {len(EXCHANGES)} exchanges...")
                    
                    for asset, exchange_map in SYMBOLS.items():
                        # Fetch all available books for this asset
                        books = {}
                        for exchange in EXCHANGES:
                            if exchange in exchange_map:
                                symbol = exchange_map[exchange]
                                try:
                                    books[exchange] = await self.monitor.get_latest_book(exchange, symbol)
                                except Exception as e:
                                    logger.error(f"Failed to fetch {asset} on {exchange}: {e}")

                        # Check all pairs (Combinations of 2)
                        if len(books) < 2:
                            continue

                        for ex1, ex2 in itertools.permutations(books.keys(), 2):
                            book1 = books[ex1]
                            book2 = books[ex2]
                            
                            fees1 = EXCHANGE_FEES[ex1]
                            fees2 = EXCHANGE_FEES[ex2]
                            
                            opp = compute_spread(
                                book1, book2, 
                                DEFAULT_TRADE_QTY[asset],
                                fees1, fees2,
                                withdrawal_fee_btc=WITHDRAWAL_FEES_BTC
                            )
                            
                            if opp:
                                logger.info(f"Opportunity: {asset} | {opp.buy_exchange} -> {opp.sell_exchange} | Margin: {opp.profit_margin_pct:.2f}%")
                                
                                is_safe, reason = self.risk_manager.should_trade(opp)
                                if is_safe:
                                    logger.info(f"Risk Check PASSED for {asset}. Executing...")
                                    result = await execution_engine.execute_arbitrage(opp)
                                    self.portfolio_manager.add_execution(result)
                                else:
                                    logger.warning(f"Risk Check FAILED ({asset}): {reason}")

                        # 5. Save State for Dashboard after each asset check
                        # (We'll update this to save a more comprehensive state)
                        save_bot_state(self.portfolio, list(books.values())[0] if books else None, None)

                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                
                # Run every 1 second for live demo
                await asyncio.sleep(1)

if __name__ == "__main__":
    bot = CryptoArbBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

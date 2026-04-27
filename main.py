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
    SYMBOL_BINANCE, SYMBOL_KRAKEN, 
    BINANCE_TAKER_FEE, KRAKEN_TAKER_FEE, 
    BINANCE_WITHDRAWAL_FEE_BTC, KRAKEN_WITHDRAWAL_FEE_BTC,
    PAPER_TRADING
)

logger = setup_logger("main")

class CryptoArbBot:
    def __init__(self):
        self.portfolio = Portfolio()
        self.portfolio_manager = PortfolioManager(self.portfolio)
        self.risk_manager = RiskManager(self.portfolio)
        self.monitor = None # Initialized in run()
        
    async def run(self):
        mode = "PAPER TRADING (SIMULATION)" if PAPER_TRADING else "LIVE TRADING"
        logger.info(f"Starting Cross-Exchange Arbitrage Bot Phase 1... [{mode}]")
        
        async with ExchangeClient() as client:
            self.monitor = OrderBookMonitor(client)
            execution_engine = ExecutionEngine(client)
            
            while True:
                try:
                    logger.info("Cycle start - Monitoring order books...")
                    
                    # 1. Fetch Order Books (via Monitor for caching)
                    binance_book = await self.monitor.get_latest_book("Binance", SYMBOL_BINANCE)
                    kraken_book = await self.monitor.get_latest_book("Kraken", SYMBOL_KRAKEN)
                    
                    # 2. Check for Arbitrage
                    fees_binance = {"taker": BINANCE_TAKER_FEE}
                    fees_kraken = {"taker": KRAKEN_TAKER_FEE}
                    
                    # Max quantity for arb - for Phase 1 we use a small safety quantity or configurable max
                    # Let's say we want to trade max 0.01 BTC per arb for testing
                    MAX_TEST_QTY = 0.01 
                    
                    opp = compute_spread(
                        binance_book, 
                        kraken_book, 
                        MAX_TEST_QTY, 
                        fees_binance, 
                        fees_kraken,
                        withdrawal_fee_btc=max(BINANCE_WITHDRAWAL_FEE_BTC, KRAKEN_WITHDRAWAL_FEE_BTC)
                    )
                    
                    if opp:
                        logger.info(f"Potential Opportunity Found! {opp.buy_exchange} -> {opp.sell_exchange} | Margin: {opp.profit_margin_pct:.2f}%")
                        
                        # 3. Risk Guardrails
                        is_safe, reason = self.risk_manager.should_trade(opp)
                        if is_safe:
                            logger.info("Risk Check PASSED. Executing trade...")
                            # 4. Execute Trade
                            result = await execution_engine.execute_arbitrage(opp)
                            self.portfolio_manager.add_execution(result)
                            
                            stats = self.portfolio_manager.portfolio.get_portfolio_stats()
                            logger.info(f"Portfolio Stats: Total PnL: {stats['total_pnl']:.4f} USDT | Trades: {stats['num_trades']}")
                        else:
                            logger.warning(f"Risk Check FAILED: {reason}")
                    # 5. Save State for Dashboard
                    save_bot_state(self.portfolio, binance_book, kraken_book)

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

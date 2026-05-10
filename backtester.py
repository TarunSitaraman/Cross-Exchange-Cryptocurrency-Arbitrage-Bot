import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Tuple
from arbitrage_detector import compute_spread, ArbitrageOpportunity
from exchange_client import OrderBook
from portfolio_manager import Portfolio, PortfolioManager
from config import (
    EXCHANGE_FEES,
    WITHDRAWAL_FEES_BTC
)

class Backtester:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.portfolio = Portfolio()
        self.portfolio_manager = PortfolioManager(self.portfolio)
        
    def generate_mock_history(self, hours: int = 24, frequency_sec: int = 10) -> List[Tuple[datetime, OrderBook, OrderBook]]:
        """
        Generates synthetic historical order book snapshots for testing.
        """
        history = []
        start_time = datetime.now() - timedelta(hours=hours)
        
        # Starting price
        base_price = 65000.0
        
        for i in range(0, hours * 3600, frequency_sec):
            timestamp = start_time + timedelta(seconds=i)
            
            # Simulated price movement (random walk)
            base_price += random.uniform(-10, 10)
            
            # Binance Book
            binance_noise = random.uniform(-5, 5)
            binance_book = OrderBook(
                exchange="Binance",
                symbol="BTCUSDT",
                timestamp=timestamp,
                bids=[(base_price + binance_noise - 5, 0.5)],
                asks=[(base_price + binance_noise + 5, 0.5)],
                best_bid=base_price + binance_noise - 5,
                best_ask=base_price + binance_noise + 5
            )
            
            # Kraken Book (slightly different price to create occasional arbs)
            kraken_noise = random.uniform(-7, 7)
            # Occasional spike to create a clear arb opportunity
            if random.random() < 0.05: # 5% chance of an arb
                kraken_noise += random.choice([-50, 50])
                
            kraken_book = OrderBook(
                exchange="Kraken",
                symbol="BTCUSDT",
                timestamp=timestamp,
                bids=[(base_price + kraken_noise - 5, 0.5)],
                asks=[(base_price + kraken_noise + 5, 0.5)],
                best_bid=base_price + kraken_noise - 5,
                best_ask=base_price + kraken_noise + 5
            )
            
            history.append((timestamp, binance_book, kraken_book))
        
        return history

    def run_backtest(self, history: List[Tuple[datetime, OrderBook, OrderBook]]):
        print(f"Starting Backtest over {len(history)} snapshots...")
        
        fees_binance = EXCHANGE_FEES['Binance']
        fees_kraken = EXCHANGE_FEES['Kraken']
        withdrawal_fee = WITHDRAWAL_FEES_BTC
        
        for timestamp, binance_book, kraken_book in history:
            # 1. Detect
            opp = compute_spread(
                binance_book,
                kraken_book,
                0.1, # Target quantity
                fees_binance,
                fees_kraken,
                withdrawal_fee_btc=withdrawal_fee
            )
            
            if opp:
                # 2. Simulated Execution
                # (We skip risk_manager in simple backtest or add it if needed)
                
                # Create a mock execution result
                from execution_engine import ExecutionResult, OrderResult
                
                res = ExecutionResult(
                    opp_id=f"backtest_{timestamp.timestamp()}",
                    buy_order=OrderResult(
                        order_id="bt_1", exchange=opp.buy_exchange, side="buy",
                        quantity=opp.quantity, price=opp.buy_price, status="filled",
                        filled_quantity=opp.quantity, timestamp=timestamp
                    ),
                    sell_order=OrderResult(
                        order_id="bt_2", exchange=opp.sell_exchange, side="sell",
                        quantity=opp.quantity, price=opp.sell_price, status="filled",
                        filled_quantity=opp.quantity, timestamp=timestamp
                    ),
                    buy_filled=opp.quantity,
                    sell_filled=opp.quantity,
                    actual_net_profit=opp.net_profit,
                    execution_time_sec=0.1,
                    status="success",
                    notes="backtest trade"
                )
                self.portfolio_manager.add_execution(res)

        # 3. Summary
        stats = self.portfolio.get_portfolio_stats()
        print("\n--- Backtest Results ---")
        print(f"Total Profit: {stats['total_pnl']:.2f} USDT")
        print(f"Total Trades: {stats['num_trades']}")
        print(f"Win Rate: {stats['win_rate']*100:.1f}%")
        print(f"Avg Profit/Trade: {stats['avg_profit_per_trade']:.2f} USDT")
        print("------------------------\n")
        return stats

if __name__ == "__main__":
    backtester = Backtester()
    history = backtester.generate_mock_history(hours=24)
    backtester.run_backtest(history)

from dataclasses import dataclass, field
from typing import List, Dict
from execution_engine import ExecutionResult

@dataclass
class Portfolio:
    trades: List[ExecutionResult] = field(default_factory=list)
    exchange_balances: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    def record_trade(self, result: ExecutionResult) -> None:
        self.trades.append(result)
        # In a real app, update balances here or refresh from API
        
    def get_realized_pnl(self) -> float:
        return sum(t.actual_net_profit for t in self.trades)
        
    def get_position_exposure(self) -> Dict[str, float]:
        exposure = {"BTC": 0.0, "USDT": 0.0}
        for t in self.trades:
            # Simple net exposure calculation
            # Buy increases BTC, Sell decreases it
            if t.buy_order and t.buy_order.exchange:
                 exposure["BTC"] += t.buy_filled
                 exposure["USDT"] -= t.buy_filled * t.buy_order.price
            if t.sell_order and t.sell_order.exchange:
                 exposure["BTC"] -= t.sell_filled
                 exposure["USDT"] += t.sell_filled * t.sell_order.price
        return exposure
        
    def get_portfolio_stats(self) -> Dict:
        total_pnl = self.get_realized_pnl()
        num_trades = len(self.trades)
        wins = len([t for t in self.trades if t.actual_net_profit > 0])
        win_rate = (wins / num_trades) if num_trades > 0 else 0
        
        return {
            "total_pnl": total_pnl,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "avg_profit_per_trade": (total_pnl / num_trades) if num_trades > 0 else 0
        }

class PortfolioManager:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        
    def update_balance(self, exchange: str, balances: Dict[str, float]):
        self.portfolio.exchange_balances[exchange] = balances
        
    def add_execution(self, result: ExecutionResult):
        self.portfolio.record_trade(result)

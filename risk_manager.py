from typing import Tuple
from arbitrage_detector import ArbitrageOpportunity
from portfolio_manager import Portfolio
from config import (
    MIN_PROFIT_MARGIN_PCT,
    MAX_DAILY_LOSS_USD,
    MAX_POSITION_BTC,
    MAX_EXPOSURE_PER_TRADE_FRAC
)

class RiskManager:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def should_trade(self, opp: ArbitrageOpportunity) -> Tuple[bool, str]:
        """
        Check if an arbitrage opportunity should be executed based on risk limits.
        """
        # 1. Profit Margin Check
        if opp.profit_margin_pct < MIN_PROFIT_MARGIN_PCT:
            return False, f"Profit margin {opp.profit_margin_pct:.2f}% below threshold {MIN_PROFIT_MARGIN_PCT}%"

        # 2. Daily Loss Limit Check
        realized_pnl = self.portfolio.get_realized_pnl()
        if realized_pnl < -MAX_DAILY_LOSS_USD:
            return False, f"Daily loss limit exceeded: {realized_pnl:.2f} USD"

        # 3. Position Size Limit (BTC exposure)
        exposure = self.portfolio.get_position_exposure()
        net_btc = exposure.get("BTC", 0)
        
        # We check if the new trade would exceed the limit
        # Arbitrage is theoretically exposure-neutral if filled perfectly, 
        # but we track net in case of partial fills.
        if abs(net_btc + opp.quantity) > MAX_POSITION_BTC:
            return False, f"Max position BTC limit would be exceeded: {abs(net_btc + opp.quantity):.4f}"

        # 4. Exposure Per Trade
        # Assuming we have total capital info, ensuring we don't risk too much on one arb
        # For Phase 1, we'll keep it simple
        
        return True, "Approved"

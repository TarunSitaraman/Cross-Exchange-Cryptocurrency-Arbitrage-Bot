from dataclasses import dataclass
from datetime import datetime
from exchange_client import OrderBook
from typing import Optional
from config import MIN_PROFIT_MARGIN_PCT

@dataclass
class ArbitrageOpportunity:
    buy_exchange: str
    sell_exchange: str
    symbol: str
    buy_price: float
    sell_price: float
    quantity: float           # max qty limited by both order books
    gross_spread: float       # sell_price - buy_price
    net_profit: float         # spread - fees - withdrawal
    profit_margin_pct: float
    roi_annualized: float     # (daily_profit / capital) × 365 (simplified)
    timestamp: datetime

def compute_spread(
    book1: OrderBook, 
    book2: OrderBook, 
    max_quantity: float, 
    fees1: dict, 
    fees2: dict,
    withdrawal_fee_btc: float = 0.0005,
    slippage_pct: float = 0.0001 # 0.01% safety margin
) -> Optional[ArbitrageOpportunity]:
    """
    Checks for arbitrage in both directions:
    1. Buy book1, Sell book2
    2. Buy book2, Sell book1
    """
    
    opportunities = []

    # Case 1: Buy on Book1 (Ask), Sell on Book2 (Bid)
    opp1 = _check_direction(book1, book2, max_quantity, fees1['taker'], fees2['taker'], withdrawal_fee_btc, slippage_pct)
    if opp1:
        opportunities.append(opp1)

    # Case 2: Buy on Book2 (Ask), Sell on Book1 (Bid)
    opp2 = _check_direction(book2, book1, max_quantity, fees2['taker'], fees1['taker'], withdrawal_fee_btc, slippage_pct)
    if opp2:
        opportunities.append(opp2)

    if not opportunities:
        return None

    # Return the most profitable one
    return max(opportunities, key=lambda x: x.profit_margin_pct)

def _check_direction(
    buy_book: OrderBook,
    sell_book: OrderBook,
    max_target_quantity: float,
    buy_fee_pct: float,
    sell_fee_pct: float,
    withdrawal_fee: float,
    slippage_pct: float
) -> Optional[ArbitrageOpportunity]:
    
    # Apply slippage to estimated execution prices
    buy_price = buy_book.best_ask * (1 + slippage_pct)
    sell_price = sell_book.best_bid * (1 - slippage_pct)
    
    if sell_price <= buy_price:
        return None
        
    # Determine max executable quantity based on depth at best prices
    # For Phase 1, we just look at the top level quantity
    qty_at_buy_ask = buy_book.asks[0][1]
    qty_at_sell_bid = sell_book.bids[0][1]
    
    executable_quantity = min(max_target_quantity, qty_at_buy_ask, qty_at_sell_bid)
    
    if executable_quantity <= 0:
        return None
        
    gross_profit_per_unit = sell_price - buy_price
    gross_profit = gross_profit_per_unit * executable_quantity
    
    buy_cost = executable_quantity * buy_price * buy_fee_pct
    sell_cost = executable_quantity * sell_price * sell_fee_pct
    
    # We assume withdrawal happens once per arb or we account for it as a fixed cost per execution
    total_fees = buy_cost + sell_cost + (withdrawal_fee * buy_price) 
    
    net_profit = gross_profit - total_fees
    capital_required = executable_quantity * buy_price
    
    profit_margin_pct = (net_profit / capital_required) * 100
    
    if profit_margin_pct < MIN_PROFIT_MARGIN_PCT:
        return None
        
    return ArbitrageOpportunity(
        buy_exchange=buy_book.exchange,
        sell_exchange=sell_book.exchange,
        symbol=buy_book.symbol,
        buy_price=buy_price,
        sell_price=sell_price,
        quantity=executable_quantity,
        gross_spread=sell_price - buy_price,
        net_profit=net_profit,
        profit_margin_pct=profit_margin_pct,
        roi_annualized=profit_margin_pct * 365, # Very rough estimate
        timestamp=datetime.now()
    )

if __name__ == "__main__":
    # Mock test
    from datetime import datetime
    
    book_binance = OrderBook(
        exchange="Binance",
        symbol="BTCUSDT",
        timestamp=datetime.now(),
        bids=[(60000.0, 1.0)],
        asks=[(60100.0, 1.0)],
        best_bid=60000.0,
        best_ask=60100.0
    )
    
    book_kraken = OrderBook(
        exchange="Kraken",
        symbol="BTCUSDT",
        timestamp=datetime.now(),
        bids=[(60500.0, 0.5)],
        asks=[(60600.0, 0.5)],
        best_bid=60500.0,
        best_ask=60600.0
    )
    
    fees_binance = {"taker": 0.001}
    fees_kraken = {"taker": 0.0026}
    
    opp = compute_spread(book_binance, book_kraken, 1.0, fees_binance, fees_kraken)
    if opp:
        print(f"Opportunity Found!")
        print(f"Buy: {opp.buy_exchange} @ {opp.buy_price}")
        print(f"Sell: {opp.sell_exchange} @ {opp.sell_price}")
        print(f"Quantity: {opp.quantity}")
        print(f"Net Profit: {opp.net_profit:.2f} USDT")
        print(f"Margin: {opp.profit_margin_pct:.2f}%")
    else:
        print("No opportunity found.")

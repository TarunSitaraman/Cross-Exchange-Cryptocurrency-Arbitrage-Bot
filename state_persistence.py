import json
import os
from typing import Dict, Any
from portfolio_manager import Portfolio
from execution_engine import ExecutionResult

def save_bot_state(portfolio: Portfolio, binance_book: Any, kraken_book: Any, state_file: str = "bot_state.json"):
    """
    Saves the current bot state to a JSON file for the dashboard to read.
    """
    
    # Helper to convert ExecutionResult to dict
    def result_to_dict(res: ExecutionResult):
        return {
            "opp_id": res.opp_id,
            "buy_filled": res.buy_filled,
            "sell_filled": res.sell_filled,
            "actual_net_profit": res.actual_net_profit,
            "status": res.status,
            "timestamp": res.buy_order.timestamp.isoformat() if res.buy_order else ""
        }

    # Load existing state to preserve history
    existing_state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                existing_state = json.load(f)
            except:
                pass

    price_history = existing_state.get("price_history", [])
    new_price_entry = {
        "timestamp": binance_book.timestamp.strftime("%H:%M:%S") if binance_book else "",
        "binance": (binance_book.best_bid + binance_book.best_ask) / 2 if binance_book else 0,
        "kraken": (kraken_book.best_bid + kraken_book.best_ask) / 2 if kraken_book else 0
    }
    price_history.append(new_price_entry)
    # Keep last 50 entries
    price_history = price_history[-50:]

    state = {
        "total_pnl": portfolio.get_realized_pnl(),
        "trades": [result_to_dict(t) for t in portfolio.trades[-10:]],
        "exposure": portfolio.get_position_exposure(),
        "binance_best_bid": binance_book.best_bid if binance_book else 0,
        "binance_best_ask": binance_book.best_ask if binance_book else 0,
        "kraken_best_bid": kraken_book.best_bid if kraken_book else 0,
        "kraken_best_ask": kraken_book.best_ask if kraken_book else 0,
        "price_history": price_history,
        "last_update": binance_book.timestamp.strftime("%Y-%m-%d %H:%M:%S") if binance_book else ""
    }
    
    with open(state_file, "w") as f:
        json.dump(state, f)

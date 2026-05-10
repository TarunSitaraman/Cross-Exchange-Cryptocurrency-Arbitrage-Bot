from datetime import datetime
import json
import os
import tempfile
from typing import Dict, Any
from portfolio_manager import Portfolio
from execution_engine import ExecutionResult

def save_bot_state(portfolio: Portfolio, primary_book: Any, secondary_book: Any = None, state_file: str = "bot_state.json"):
    """
    Saves the current bot state to a JSON file for the dashboard to read.
    """
    
    def result_to_dict(res: ExecutionResult):
        return {
            "opp_id": res.opp_id,
            "buy_filled": res.buy_filled,
            "sell_filled": res.sell_filled,
            "actual_net_profit": res.actual_net_profit,
            "status": res.status,
            "timestamp": res.buy_order.timestamp.isoformat() if res.buy_order else ""
        }

    existing_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                existing_state = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Log error and start with empty state to recover gracefully
            print(f"Error reading state file {state_file}: {e}")
            existing_state = {}

    if not isinstance(existing_state, dict):
        existing_state = {}

    price_history = existing_state.get("price_history", [])
    if not isinstance(price_history, list):
        price_history = []
    
    # Track mid-prices for the active primary/secondary books
    # Ensure they are numeric
    def _safe_float(val, default=0.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    p_price = (_safe_float(primary_book.best_bid) + _safe_float(primary_book.best_ask)) / 2 if primary_book else 0
    s_price = (_safe_float(secondary_book.best_bid) + _safe_float(secondary_book.best_ask)) / 2 if secondary_book else p_price * 0.998 # Mock spread for viz if 2nd missing
    
    new_price_entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "binance": p_price if primary_book and getattr(primary_book, 'exchange', '') == "Binance" else (s_price if secondary_book and getattr(secondary_book, 'exchange', '') == "Binance" else 0),
        "kraken": p_price if primary_book and getattr(primary_book, 'exchange', '') == "Kraken" else (s_price if secondary_book and getattr(secondary_book, 'exchange', '') == "Kraken" else 0)
    }
    
    # If we have 0s, try to keep previous values for chart continuity
    if price_history:
        last = price_history[-1]
        if isinstance(last, dict):
            if new_price_entry["binance"] == 0:
                new_price_entry["binance"] = _safe_float(last.get("binance", 0))
            if new_price_entry["kraken"] == 0:
                new_price_entry["kraken"] = _safe_float(last.get("kraken", 0))

    price_history.append(new_price_entry)
    price_history = price_history[-50:]

    state = {
        "total_pnl": portfolio.get_realized_pnl(),
        "trades": [result_to_dict(t) for t in portfolio.trades[-10:]],
        "exposure": portfolio.get_position_exposure(),
        "price_history": price_history,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    target_dir = os.path.dirname(os.path.abspath(state_file))

    with tempfile.NamedTemporaryFile("w", dir=target_dir, delete=False) as f:
        temp_path = f.name
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, state_file)

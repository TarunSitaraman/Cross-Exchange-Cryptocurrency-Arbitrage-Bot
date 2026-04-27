import os
from dotenv import load_dotenv

load_dotenv()

# Simulation Mode
PAPER_TRADING = True  # Set to False to use real API keys and capital
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "your_binance_key")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "your_binance_secret")

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "your_kraken_key")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "your_kraken_secret")

COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "your_coinbase_key")
COINBASE_API_SECRET = os.getenv("COINBASE_API_SECRET", "your_coinbase_secret")

# Trading Assets
SYMBOLS = {
    "BTC": {"Binance": "BTCUSDT", "Kraken": "XBTUSDT", "Coinbase": "BTC-USD"},
    "ETH": {"Binance": "ETHUSDT", "Kraken": "ETHUSDT", "Coinbase": "ETH-USD"},
    "SOL": {"Binance": "SOLUSDT", "Kraken": "SOLUSDT", "Coinbase": "SOL-USD"},
    "XRP": {"Binance": "XRPUSDT", "Kraken": "XRPUSDT", "Coinbase": "XRP-USD"},
}

EXCHANGES = ["Binance", "Kraken", "Coinbase"]

# Execution Depth settings
ORDER_BOOK_DEPTH = 20
DEFAULT_TRADE_QTY = {
    "BTC": 0.01,
    "ETH": 0.1,
    "SOL": 5.0,
    "XRP": 100.0,
}

# Fees & Withdrawal (Averaged for Phase 2)
EXCHANGE_FEES = {
    "Binance": {"taker": 0.001},
    "Kraken": {"taker": 0.0026},
    "Coinbase": {"taker": 0.006} # Coinbase Advanced taker is roughly 0.6%
}

WITHDRAWAL_FEES_BTC = 0.0005

# Arbitrage Thresholds
MIN_PROFIT_MARGIN_PCT = 0.05  # Lowered for demonstration (0.05%)

# Risk Management
MAX_POSITION_BTC = 1.0
MAX_DAILY_LOSS_USD = 200.0
MAX_EXPOSURE_PER_TRADE_FRAC = 0.10

# Logging
LOG_FILE = "arb_bot.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

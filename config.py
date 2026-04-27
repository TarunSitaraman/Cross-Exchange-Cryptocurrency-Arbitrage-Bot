import os
from dotenv import load_dotenv

load_dotenv()

# Simulation Mode
PAPER_TRADING = True  # Set to False to use real API keys and capital
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "your_binance_key")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "your_binance_secret")

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "your_kraken_key")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "your_kraken_secret")

# Trading Parameters
SYMBOL_BINANCE = "BTCUSDT"
SYMBOL_KRAKEN = "XBTUSDT"  # Kraken uses XBT for BTC

# Fees (Taker fees for Phase 1)
BINANCE_TAKER_FEE = 0.001  # 0.1%
KRAKEN_TAKER_FEE = 0.0026  # 0.26%

# Withdrawal Fees (Fixed amounts)
BINANCE_WITHDRAWAL_FEE_BTC = 0.0005  # Standard BTC withdrawal fee
KRAKEN_WITHDRAWAL_FEE_BTC = 0.0004   # Standard BTC withdrawal fee

# Arbitrage Thresholds
MIN_PROFIT_MARGIN_PCT = 0.05  # Lowered for demonstration (0.05%)

# Risk Management
MAX_POSITION_BTC = 1.0
MAX_DAILY_LOSS_USD = 200.0
MAX_EXPOSURE_PER_TRADE_FRAC = 0.10

# Logging
LOG_FILE = "arb_bot.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

import os
from dotenv import load_dotenv

load_dotenv()

# Angel One Credentials
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_KEY = os.getenv("ANGEL_TOTP_KEY")

# Telegram Credentials - EQUITY (NIFTY)
TELEGRAM_BOT_TOKEN_EQUITY = os.getenv("TELEGRAM_BOT_TOKEN_EQUITY")
TELEGRAM_CHAT_ID_EQUITY = os.getenv("TELEGRAM_CHAT_ID_EQUITY")

# Telegram Credentials - CRYPTO (BTC/ETH)
TELEGRAM_BOT_TOKEN_CRYPTO = os.getenv("TELEGRAM_BOT_TOKEN_CRYPTO")
TELEGRAM_CHAT_ID_CRYPTO = os.getenv("TELEGRAM_CHAT_ID_CRYPTO")

# Delta Exchange Credentials (Optional if public)
DELTA_API_KEY = os.getenv("DELTA_API_KEY") # Not strictly needed for public candles
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET")

# Crypto Symbols
CRYPTO_SYMBOLS = ["BTCUSD", "ETHUSD"]

# Strategy Parameters
RSI_PERIOD = 14
RSI_PARENT_THRESHOLD = 60  # Minimum RSI for Parent timeframes (LONG)
RSI_PARENT_SHORT_THRESHOLD = 40 # Maximum RSI for Parent timeframes (SHORT)
RSI_CHILD_SUPPORT_LOW = 38
RSI_CHILD_SUPPORT_HIGH = 40
RSI_CHILD_RESISTANCE_LOW = 60
RSI_CHILD_RESISTANCE_HIGH = 62

# Timeframe Sets
STRATEGY_SETS = [
    {
        "name": "INTRADAY",
        "p1": "ONE_HOUR",
        "p2": "FIFTEEN_MINUTE",
        "child": "FIVE_MINUTE"
    },
    {
        "name": "SWING",
        "p1": "ONE_DAY",
        "p2": "ONE_HOUR",
        "child": "FIFTEEN_MINUTE"
    }
]

# Symbols will be loaded dynamically in main.py
SYMBOLS = []

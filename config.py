import os
from dotenv import load_dotenv

load_dotenv()

# Angel One Credentials
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_KEY = os.getenv("ANGEL_TOTP_KEY")

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Strategy Parameters
RSI_PERIOD = 14
RSI_PARENT_THRESHOLD = 60  # Minimum RSI for Parent timeframes
RSI_CHILD_SUPPORT_LOW = 38
RSI_CHILD_SUPPORT_HIGH = 40

# Timeframes (Angel One format)
# "ONE_DAY", "ONE_HOUR", "FIFTEEN_MINUTE", "FIVE_MINUTE"
TF_PARENT_1 = "ONE_HOUR"
TF_PARENT_2 = "FIFTEEN_MINUTE"
TF_CHILD = "FIVE_MINUTE"

from token_loader import TokenLoader

# Symbols to Scan
# Dynamic Loading for All NSE FNO Stocks
try:
    loader = TokenLoader()
    SYMBOLS = loader.get_fno_equity_list()
    # Add Indices manually if needed, or rely on FNO list
    if not any(s['symbol'] == 'NIFTY' for s in SYMBOLS):
         SYMBOLS.append({"symbol": "NIFTY", "token": "99926000", "exchange": "NSE"})
    if not any(s['symbol'] == 'BANKNIFTY' for s in SYMBOLS):
         SYMBOLS.append({"symbol": "BANKNIFTY", "token": "99926009", "exchange": "NSE"})
except Exception as e:
    print(f"Error loading tokens: {e}")
    SYMBOLS = []

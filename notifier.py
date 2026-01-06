import requests
from logzero import logger
import config

class TelegramNotifier:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID

    def send_alert(self, message):
        if not self.bot_token or not self.chat_id or "your_" in self.bot_token:
            logger.warning("Telegram credentials not configured. Skipping alert.")
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Telegram Alert Sent Successfully.")
            else:
                logger.error(f"Failed to send alert: {response.text}")
        except Exception as e:
            logger.error(f"Telegram Exception: {e}")

    def format_rep_signal(self, symbol, time, price, child_rsi, p1_rsi, p2_rsi):
        msg = f"*🔥 REP Strategy Signal 🔥*\n\n"
        msg += f"*Symbol*: {symbol}\n"
        msg += f"*Time*: {time}\n"
        msg += f"*Price*: {price}\n\n"
        msg += f"✅ *Setup Confirmed*:\n"
        msg += f"• Child RSI (5m): {child_rsi:.2f} (Support Bounce)\n"
        msg += f"• Parent 1 (1h): {p1_rsi:.2f} (Bullish)\n"
        msg += f"• Parent 2 (15m): {p2_rsi:.2f} (Bullish)\n\n"
        msg += f"⚡ *Action*: Look for Buy Entry above candle High."
        return msg

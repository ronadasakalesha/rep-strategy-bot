from SmartApi import SmartConnect
import pyotp
from logzero import logger
import time
from datetime import datetime, timedelta
import pandas as pd

class SmartApiHelper:
    def __init__(self, api_key, client_id, password, totp_key):
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.totp_key = totp_key
        self.smartApi = SmartConnect(api_key=self.api_key)
        self.login()

    def login(self):
        try:
            totp = pyotp.TOTP(self.totp_key).now()
            data = self.smartApi.generateSession(self.client_id, self.password, totp)
            if data['status'] == False:
                logger.error(f"Login Failed: {data}")
            else:
                self.auth_token = data['data']['jwtToken']
                self.feed_token = self.smartApi.getfeedToken()
                logger.info("Login Successful")
        except Exception as e:
            logger.error(f"Login Exception: {e}")

    def get_historical_data(self, token, exchange, timeframe, duration_days=5):
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=duration_days)
            
            params = {
                "exchange": exchange,
                "symboltoken": token,
                "interval": timeframe,
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            }
            
            candle_data = self.smartApi.getCandleData(params)
            if candle_data['status'] == True and candle_data['data']:
                df = pd.DataFrame(candle_data['data'], columns=["date", "open", "high", "low", "close", "volume"])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric)
                return df
            else:
                logger.warning(f"No Data for {token} {timeframe}")
                return None
        except Exception as e:
            logger.error(f"Data Fetch Exception: {e}")
            return None


import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from logzero import logger

class DeltaApiHelper:
    def __init__(self, api_key=None, api_secret=None):
        self.base_url = "https://api.india.delta.exchange"
        self.api_key = api_key
        self.api_secret = api_secret
        # Public endpoints usually don't need auth for market data, 
        # but good to have structure if we need private later.

    def get_timeframe_code(self, timeframe):
        # Map bot timeframes to Delta resolution
        mapping = {
            "ONE_HOUR": "1h",
            "FIFTEEN_MINUTE": "15m",
            "FIVE_MINUTE": "5m",
            "ONE_DAY": "1d"
        }
        return mapping.get(timeframe, "5m")

    def get_historical_data(self, symbol, exchange="DELTA", timeframe="FIVE_MINUTE", duration_days=5):
        """
        Fetches historical candle data from Delta Exchange India.
        """
        resolution = self.get_timeframe_code(timeframe)
        
        # Calculate start/end time
        # Delta expects epoch timestamps (seconds)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=duration_days)
        
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())
        
        url = f"{self.base_url}/v2/history/candles"
        params = {
            "resolution": resolution,
            "symbol": symbol, # e.g., BTCUSD
            "start": start_ts,
            "end": end_ts
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if response.status_code != 200:
                logger.error(f"Delta API Error ({symbol}): {data}")
                return None
                
            if "result" not in data:
                return None
            
            candles = data["result"]
            if not candles:
                return None
                
            # Delta returns: [timestamp, open, high, low, close, volume]
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
            
            # Standardize columns to match SmartApiHelper
            # 'time' is epoch in seconds
            df['date'] = pd.to_datetime(df['time'], unit='s')
            # Adjust timezone to IST? The bot seems to use local time or naive. 
            # SmartApi returns string or datetime?
            # SmartApiHelper usually returns 'date' as datetime object or string.
            # Let's check SmartApiHelper implementation if needed. 
            # For now, keeping as datetime.
            
            # Sort by date ascending (Delta returns descending usually?)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Ensure numeric
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            
            # Drop unnecessary
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            logger.error(f"Delta Fetch Exception ({symbol}): {e}")
            return None

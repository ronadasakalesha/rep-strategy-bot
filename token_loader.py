import requests
from logzero import logger

import json
import os

class TokenLoader:
    def __init__(self):
        self.url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        self.cache_file = "fno_tokens.json"

    def fetch_scrip_master(self):
        try:
            logger.info("Fetching Angel One Scrip Master JSON...")
            response = requests.get(self.url)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch scrip master: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Token Fetch Exception: {e}")
            return None

    def get_fno_equity_list(self, force_refresh=False):
        """
        Returns a list of symbols for NSE FNO (Futures & Options) stocks.
        Checks for local cache first.
        """
        # 1. Try to load from cache
        if not force_refresh and os.path.exists(self.cache_file):
            try:
                logger.info(f"Loading tokens from local cache: {self.cache_file}")
                with open(self.cache_file, 'r') as f:
                    tokens = json.load(f)
                    if tokens:
                        logger.info(f"Loaded {len(tokens)} tokens from cache.")
                        return tokens
            except Exception as e:
                logger.error(f"Error loading cache: {e}")

        # 2. Fetch if no cache or force_refresh
        data = self.fetch_scrip_master()
        if not data:
            return []
            
        logger.info(f"Total Scrips Fetched: {len(data)}")
        
        # Identify symbols present in NFO segment (Futures)
        fno_symbols = set()
        for scrip in data:
            if scrip['exch_seg'] == 'NFO' and 'FUTSTK' in scrip['instrumenttype']:
                fno_symbols.add(scrip['name'])
        
        logger.info(f"Identified {len(fno_symbols)} FNO Stocks.")
        
        # Get the NSE Equity Tokens for these symbols
        fno_equity_tokens = []
        for scrip in data:
            if scrip['exch_seg'] == 'NSE' and scrip['symbol'].endswith('-EQ'):
                stock_name = scrip['name']
                if stock_name in fno_symbols:
                    fno_equity_tokens.append({
                        "symbol": scrip['symbol'].replace('-EQ', ''),
                        "token": scrip['token'],
                        "exchange": "NSE"
                    })
        
        # 3. Save to cache (Handle Read-Only Filesystems like Render free tier basic)
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(fno_equity_tokens, f, indent=4)
            logger.info(f"Saved {len(fno_equity_tokens)} tokens to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Could not save cache (expected on Read-Only FS): {e}")
            
        return fno_equity_tokens

if __name__ == "__main__":
    loader = TokenLoader()
    tokens = loader.get_fno_equity_list()
    # Print first 5
    print(tokens[:5])

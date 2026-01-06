from smart_api_helper import SmartApiHelper
from strategy_rep import REPStrategy
import config
from logzero import logger
import pandas as pd
import time

def scan_nifty50_stocks():
    logger.info("Initializing Nifty 50 Stock Scanner...")
    
    helper = SmartApiHelper(
        api_key=config.API_KEY,
        client_id=config.CLIENT_ID,
        password=config.PASSWORD,
        totp_key=config.TOTP_KEY
    )
    
    strategy = REPStrategy(rsi_period=config.RSI_PERIOD)
    
    # Top Nifty 50 Stocks with Angel One Tokens (NSE Equity)
    # These tokens are based on common mappings; if API fails, we search dynamically if possible or skip.
    # Tokens: Reliance (2885), HDFC Bank (1333), Infosys (1594), TCS (11536), ICICI Bank (4963), SBI (3045)
    # Note: Infosys token 1594 is common, but let's check a few high weights.
    
    stocks = [
        {"symbol": "RELIANCE", "token": "2885"},
        {"symbol": "HDFCBANK", "token": "1333"},
        {"symbol": "INFY", "token": "1594"},
        {"symbol": "TCS", "token": "11536"},
        {"symbol": "ICICIBANK", "token": "4963"},
        {"symbol": "SBIN", "token": "3045"}
    ]
    
    found_any = False
    
    for stock in stocks:
        symbol = stock['symbol']
        token = stock['token']
        exchange = "NSE"
        
        logger.info(f"Scanning {symbol}...")
        
        # 1. Fetch Data (Parent 1: 1h, Parent 2: 15m, Child: 5m)
        # Using extended duration to find ANY recent trade if not live
        try:
            p1_df = helper.get_historical_data(token, exchange, config.TF_PARENT_1, duration_days=30)
            p2_df = helper.get_historical_data(token, exchange, config.TF_PARENT_2, duration_days=15)
            child_df = helper.get_historical_data(token, exchange, config.TF_CHILD, duration_days=10)
            
            if p1_df is None or p2_df is None or child_df is None:
                logger.warning(f"Skipping {symbol} due to missing data.")
                continue

            # 2. Calculate RSI
            p1_df = strategy.calculate_rsi(p1_df)
            p2_df = strategy.calculate_rsi(p2_df)
            child_df = strategy.calculate_rsi(child_df)
            
            # 3. Iterate backwards (Newest to Oldest) to find the LATEST trade
            # We want "Last one trade", so finding the most recent valid setup is best.
            
            valid_trades = []
            
            # Start loop from end
            for i in range(len(child_df) - 1, 50, -1):
                current_time = child_df.index[i]
                
                # Slices
                p1_slice = p1_df[p1_df.index <= current_time]
                p2_slice = p2_df[p2_df.index <= current_time]
                
                if len(p1_slice) == 0 or len(p2_slice) == 0:
                    continue
                    
                p1_row = p1_slice.iloc[-1]
                p2_row = p2_slice.iloc[-1]
                
                # Check Parents > 60
                if p1_row['rsi'] > 60 and p2_row['rsi'] > 60:
                    
                    child_row = child_df.iloc[i]
                    prev_child = child_df.iloc[i-1]
                    
                    # Check Child Support & Green Candle
                    is_support = (38 <= prev_child['rsi'] <= 42) or (38 <= child_row['rsi'] <= 42)
                    is_green = child_row['close'] > child_row['open']
                    
                    if is_support and is_green:
                        # FOUND ONE!
                        trade = {
                            "Symbol": symbol,
                            "Time": current_time,
                            "Price": child_row['close'],
                            "RSI_5m": child_row['rsi'],
                            "RSI_15m": p2_row['rsi'],
                            "RSI_1h": p1_row['rsi']
                        }
                        valid_trades.append(trade)
                        # We only need the last one per stock, or just ONE overall?
                        # User said "give me last one trade in nifty50... give me any one stocks"
                        # So just one total is enough, but let's collect recent ones.
                        break # Found latest for this stock
            
            if valid_trades:
                trade = valid_trades[0]
                print("\n" + "*"*50)
                print(f"TRADE FOUND: {trade['Symbol']}")
                print("*"*50)
                print(f"Time      : {trade['Time']}")
                print(f"Entry Price: {trade['Price']}")
                print(f"RSI 5m    : {trade['RSI_5m']:.2f}")
                print(f"RSI 15m   : {trade['RSI_15m']:.2f}")
                print(f"RSI 1h    : {trade['RSI_1h']:.2f}")
                print("*"*50 + "\n")
                found_any = True
                
                # If we just need "any one", we can stop here.
                return 

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
        
        time.sleep(1) # Rate limit safety

    if not found_any:
        print("\nNo valid trades found in the scanned top Nifty stocks.")

if __name__ == "__main__":
    scan_nifty50_stocks()

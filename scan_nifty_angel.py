from smart_api_helper import SmartApiHelper
from strategy_rep import REPStrategy
import config
from logzero import logger
import pandas as pd

def scan_nifty_last_trade():
    logger.info("Initializing Angel One Scanner...")
    
    # Initialize API Helper
    helper = SmartApiHelper(
        api_key=config.API_KEY,
        client_id=config.CLIENT_ID,
        password=config.PASSWORD,
        totp_key=config.TOTP_KEY
    )
    
    # Initialize Strategy
    strategy = REPStrategy(rsi_period=config.RSI_PERIOD)
    
    # NIFTY 50 Token
    nifty_token = "99926000"
    exchange = "NSE"
    symbol = "NIFTY"
    
    logger.info(f"Fetching Data for {symbol}...")
    
    # Fetch Data with extended duration
    parent1_df = helper.get_historical_data(nifty_token, exchange, config.TF_PARENT_1, duration_days=60)
    parent2_df = helper.get_historical_data(nifty_token, exchange, config.TF_PARENT_2, duration_days=30)
    child_df = helper.get_historical_data(nifty_token, exchange, config.TF_CHILD, duration_days=30)
    
    if parent1_df is None or len(parent1_df) == 0:
        logger.error("Failed to fetch Parent 1 data")
        return
    if child_df is None or len(child_df) == 0:
         logger.error("Failed to fetch Child data")
         return

    # Calculate RSI
    parent1_df = strategy.calculate_rsi(parent1_df)
    parent2_df = strategy.calculate_rsi(parent2_df)
    child_df = strategy.calculate_rsi(child_df)
    
    logger.info(f"Data Loaded. Child Candles: {len(child_df)}")
    
    # Debug Stats
    logger.info(f"Max Parent 1 RSI: {parent1_df['rsi'].max():.2f}")
    logger.info(f"Max Parent 2 RSI: {parent2_df['rsi'].max():.2f}")
    logger.info(f"Min Child RSI: {child_df['rsi'].min():.2f}")
    
    logger.info("Scanning for setup...")
    
    found_trades = []
    
    for i in range(50, len(child_df)):
        current_time = child_df.index[i]
        
        # Get Parents State at this time
        p1_slice = parent1_df[parent1_df.index <= current_time]
        p2_slice = parent2_df[parent2_df.index <= current_time]
        
        if len(p1_slice) == 0 or len(p2_slice) == 0:
            continue
            
        p1_row = p1_slice.iloc[-1]
        p2_row = p2_slice.iloc[-1]
        
        # Check Parents
        if p1_row['rsi'] > 60 and p2_row['rsi'] > 60:
            
            child_row = child_df.iloc[i]
            prev_child_row = child_df.iloc[i-1]
            
            # Use slightly wider zone for detection in history (35-45) to see near misses
            # But strictly report 38-42
            is_support = (38 <= prev_child_row['rsi'] <= 42) or (38 <= child_row['rsi'] <= 42)
            is_green = child_row['close'] > child_row['open']
            
            if is_support and is_green:
                trade = {
                    "Time": current_time,
                    "Price": child_row['close'],
                    "RSI_5m": child_row['rsi'],
                    "RSI_15m": p2_row['rsi'],
                    "RSI_1h": p1_row['rsi']
                }
                found_trades.append(trade)

    if found_trades:
        last_trade = found_trades[-1]
        print("\n" + "="*50 + "\nLAST CONFIRMED REP TRADE (NIFTY 50)\n" + "="*50)
        print(f"Signal Time : {last_trade['Time']}")
        print(f"Entry Price : {last_trade['Price']}")
        print(f"Child RSI   : {last_trade['RSI_5m']:.2f}")
        print(f"15m RSI     : {last_trade['RSI_15m']:.2f}")
        print(f"1h RSI      : {last_trade['RSI_1h']:.2f}")
        print("="*50 + "\n")
        print(f"Total signals in last 30 days: {len(found_trades)}")
    else:
        print("\nNo valid REP trades found even with extended 30-day scan.")
        print("This suggests the market has not aligned (Parents > 60 + Child Dip 38-40) recently.")

if __name__ == "__main__":
    scan_nifty_last_trade()

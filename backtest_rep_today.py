
import time
import pandas as pd
from logzero import logger
import config
from datetime import datetime
from smart_api_helper import SmartApiHelper
from strategy_rep import REPStrategy
from token_loader import TokenLoader

def main():
    logger.info("Initializing REP Strategy Backtest for Today...")

    # 1. Initialize API Helper
    helper = SmartApiHelper(
        api_key=config.API_KEY,
        client_id=config.CLIENT_ID,
        password=config.PASSWORD,
        totp_key=config.TOTP_KEY
    )

    # 2. Initialize Strategy
    strategy = REPStrategy(rsi_period=config.RSI_PERIOD)
    
    # 3. Load Tokens
    loader = TokenLoader()
    tokens = loader.get_fno_equity_list()
    # Add Indices
    if not any(s['symbol'] == 'NIFTY' for s in tokens):
        tokens.append({"symbol": "NIFTY", "token": "99926000", "exchange": "NSE"})
    if not any(s['symbol'] == 'BANKNIFTY' for s in tokens):
        tokens.append({"symbol": "BANKNIFTY", "token": "99926009", "exchange": "NSE"})
    
    total_signals = 0
    signals_list = []
    
    logger.info(f"Starting Backtest for {len(tokens)} Symbols...")
    
    # Define Date for "Today" (Assuming script is run on the same day or we iterate all data fetched)
    # We will fetch last 5 days but only scan the last day's 5m candles.
    
    for i, item in enumerate(tokens):
        symbol = item['symbol']
        token = item['token']
        exchange = item['exchange']
        
        try:
            # logger.info(f"Scanning {symbol} ({i+1}/{len(tokens)})...")
            
            # Rate Limit Protection
            time.sleep(0.2) 

            # Fetch Data for 3 Timeframes
            # We fetch a bit more history to ensure RSI is stable
            parent1_df = helper.get_historical_data(token, exchange, config.TF_PARENT_1, duration_days=10) # 1 Hour
            parent2_df = helper.get_historical_data(token, exchange, config.TF_PARENT_2, duration_days=10) # 15 Min
            child_df = helper.get_historical_data(token, exchange, config.TF_CHILD, duration_days=5)     # 5 Min
            
            if parent1_df is None or parent2_df is None or child_df is None:
                continue
                
            # Calculate RSI
            parent1_df = strategy.calculate_rsi(parent1_df)
            parent2_df = strategy.calculate_rsi(parent2_df)
            child_df = strategy.calculate_rsi(child_df)
            
            # Drop NaN RSIs
            parent1_df.dropna(subset=['rsi'], inplace=True)
            parent2_df.dropna(subset=['rsi'], inplace=True)
            child_df.dropna(subset=['rsi'], inplace=True)

            # --- Multi-Timeframe Alignment (Merge AsOf) ---
            # Pre-processing for merge
            # Ensure index is datetime or we have a datetime column
            # SmartApiHelper usually sets index as datetime 'date'
            
            # Reset index to columns for merging if needed, or ensure they are sorted datetime
            if parent1_df.index.name == 'date': parent1_df = parent1_df.reset_index()
            if parent2_df.index.name == 'date': parent2_df = parent2_df.reset_index()
            if child_df.index.name == 'date': child_df = child_df.reset_index()
            
            # Rename columns to avoid collision
            p1_subset = parent1_df[['date', 'rsi']].rename(columns={'rsi': 'rsi_1h'})
            p2_subset = parent2_df[['date', 'rsi']].rename(columns={'rsi': 'rsi_15m'})
            c_subset = child_df.copy() # Keep all cols for child
            c_subset.rename(columns={'rsi': 'rsi_5m'}, inplace=True)

            # Sort
            p1_subset.sort_values('date', inplace=True)
            p2_subset.sort_values('date', inplace=True)
            c_subset.sort_values('date', inplace=True)

            # Merge 15m to 5m
            # direction='backward' matches the last available 15m candle at or before the 5m candle time
            merged_df = pd.merge_asof(c_subset, p2_subset, on='date', direction='backward', tolerance=pd.Timedelta('15min'))
            
            # Merge 1h to Result
            merged_df = pd.merge_asof(merged_df, p1_subset, on='date', direction='backward', tolerance=pd.Timedelta('60min'))

            # Filter for "Today" (Latest Date in the data)
            if merged_df.empty: continue
            
            last_date = merged_df['date'].max().date()
            today_df = merged_df[merged_df['date'].dt.date == last_date].copy()
            
            # DEBUG
            logger.info(f"{symbol}: Last Date {last_date}, Rows {len(today_df)}")
            
            if today_df.empty: continue

            # --- Scan Logic ---
            # We iterate through today's 5m candles to find signals
            # Using Strategy Logic:
            # 1. Parent RSI > 60 (from merged cols)
            # 2. Child RSI Dip (38-40)
            # 3. Green Candle Confirmation
            
            # To detect "Dip", we need to look at sequence. 
            # But the strategy class `check_child_condition` looks at a window (tail 5).
            # Here in backtest, we iterate candle by candle.
            
            # We will use a sliding window approach or just simple state machine?
            # Or simpler: reuse `check_child_condition`?
            # `check_child_condition` takes a DF and checks the *end* of it.
            # So if we feed it `today_df.iloc[:i+1]` it might work but is slow (O(N^2)).
            
            # Let's iterate linearly.
            
            # State for Setup
            # We need to find: 
            # 1. Parents were valid at time T (or T-k)
            # 2. 5M RSI dipped into zone (38-40)
            # 3. 5M Candle turns Green
            
            # Note: The strategy `check_child_condition` looks for a dip in the last 5 candles.
            
            for idx in range(1, len(today_df)):
                row = today_df.iloc[idx]
                
                # Check Parents
                if pd.isna(row['rsi_1h']) or pd.isna(row['rsi_15m']):
                    continue
                    
                if row['rsi_1h'] > config.RSI_PARENT_THRESHOLD and row['rsi_15m'] > config.RSI_PARENT_THRESHOLD:
                    # Parents OK.
                    
                    # Check Child Setup (Dip + Green)
                    # We look at the current candle and previous few to see if there was a dip.
                    
                    # Current candle must be Green for entry
                    if row['close'] > row['open']:
                        # Check if any of the last few candles (including this one or prev ones) 
                        # had RSI in 38-40
                        
                        # Look back window of 5 candles
                        start_idx = max(0, idx - 5)
                        window = today_df.iloc[start_idx : idx + 1]
                        
                        # Check for dip
                        dip_found = False
                        for w_idx in range(len(window)):
                             r_val = window.iloc[w_idx]['rsi_5m']
                             if config.RSI_CHILD_SUPPORT_LOW <= r_val <= config.RSI_CHILD_SUPPORT_HIGH:
                                 dip_found = True
                                 break
                        
                        if dip_found:
                             # Signal!
                             # We should handle duplicates (e.g. multiple signals in same move).
                             # For now, just log all valid triggers.
                             
                             signal_time = row['date']
                             price = row['close']
                             
                             logger.info(f"SIGNAL: {symbol} at {signal_time} | Price: {price} | RSIs: 1H={row['rsi_1h']:.1f} 15M={row['rsi_15m']:.1f} 5M={row['rsi_5m']:.1f}")
                             
                             signals_list.append({
                                 "symbol": symbol,
                                 "time": signal_time,
                                 "price": price,
                                 "rsi_1h": row['rsi_1h'],
                                 "rsi_15m": row['rsi_15m'],
                                 "rsi_5m": row['rsi_5m']
                             })
                             
                             # Skip next few candles to avoid duplicate alerts for same setup?
                             # Or just let it be.
                             
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    logger.info("========================================")
    logger.info(f"Total Signals Generated: {len(signals_list)}")
    logger.info("========================================")
    for s in signals_list:
        print(f"{s['symbol']} - {s['time']} - {s['price']}")

if __name__ == "__main__":
    main()

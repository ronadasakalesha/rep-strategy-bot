
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
    
    # Create a wrapper function for processing one stock
    def process_stock(item):
        symbol = item['symbol']
        token = item['token']
        exchange = item['exchange']
        local_signals = []
        
        # Helper for retrying
        def fetch_with_retry(t, e, tf, d):
            for attempt in range(3):
                res = helper.get_historical_data(t, e, tf, duration_days=d)
                if res is not None:
                     return res
                # If None, it might be No Data or Error. get_historical_data currently logs error.
                # If it was a rate limit error (which we can't easily distinguish from None without changing helper), we wait.
                # Assuming helper returns None on error.
                time.sleep(0.5 * (attempt + 1))
            return None

        try:
            # Fetch Data for 3 Timeframes
            # NOTE: Removed Fail-Fast optimization because checking EOD RSI filters out valid morning trades.
            parent1_df = fetch_with_retry(token, exchange, config.TF_PARENT_1, 10) 
            parent2_df = fetch_with_retry(token, exchange, config.TF_PARENT_2, 10) 
            child_df = fetch_with_retry(token, exchange, config.TF_CHILD, 5)     
            
            if parent1_df is None or parent2_df is None or child_df is None:
                return []
                
            # Calculate RSI
            parent1_df = strategy.calculate_rsi(parent1_df)
            parent2_df = strategy.calculate_rsi(parent2_df)
            child_df = strategy.calculate_rsi(child_df)
            
            if parent2_df is None or child_df is None:
                return []
                
            # Calculate RSI for others
            parent2_df = strategy.calculate_rsi(parent2_df)
            child_df = strategy.calculate_rsi(child_df)
            
            # Drop NaN RSIs
            parent1_df.dropna(subset=['rsi'], inplace=True)
            parent2_df.dropna(subset=['rsi'], inplace=True)
            child_df.dropna(subset=['rsi'], inplace=True)

            # --- Multi-Timeframe Alignment (Merge AsOf) ---
            if parent1_df.index.name == 'date': parent1_df = parent1_df.reset_index()
            if parent2_df.index.name == 'date': parent2_df = parent2_df.reset_index()
            if child_df.index.name == 'date': child_df = child_df.reset_index()
            
            # Rename columns
            p1_subset = parent1_df[['date', 'rsi']].rename(columns={'rsi': 'rsi_1h'})
            p2_subset = parent2_df[['date', 'rsi']].rename(columns={'rsi': 'rsi_15m'})
            c_subset = child_df.copy()
            c_subset.rename(columns={'rsi': 'rsi_5m'}, inplace=True)

            # Sort
            p1_subset.sort_values('date', inplace=True)
            p2_subset.sort_values('date', inplace=True)
            c_subset.sort_values('date', inplace=True)

            # Merge
            merged_df = pd.merge_asof(c_subset, p2_subset, on='date', direction='backward', tolerance=pd.Timedelta('15min'))
            merged_df = pd.merge_asof(merged_df, p1_subset, on='date', direction='backward', tolerance=pd.Timedelta('60min'))

            if merged_df.empty: return []
            
            if merged_df.empty: return []
            
            last_date = merged_df['date'].max().date()
            
            # Find start index for today
            today_mask = merged_df['date'].dt.date == last_date
            if not today_mask.any(): return []
            
            start_today_idx = today_mask.idxmax()
            
            # --- Scan Logic ---
            # Iterate only through today's candles, but use merged_df (full history) for lookback
            for idx in range(start_today_idx, len(merged_df)):
                row = merged_df.iloc[idx]
                
                if pd.isna(row['rsi_1h']) or pd.isna(row['rsi_15m']):
                    continue
                
                # --- LONG CHECK ---
                if row['rsi_1h'] > config.RSI_PARENT_THRESHOLD and row['rsi_15m'] > config.RSI_PARENT_THRESHOLD:
                    if row['close'] > row['open']: # Green Candle
                        start_idx = max(0, idx - 5)
                        window = merged_df.iloc[start_idx : idx + 1]
                        dip_found = False
                        for w_idx in range(len(window)):
                             r_val = window.iloc[w_idx]['rsi_5m']
                             if config.RSI_CHILD_SUPPORT_LOW <= r_val <= config.RSI_CHILD_SUPPORT_HIGH:
                                 dip_found = True
                                 break
                        
                        if dip_found:
                             signal_time = row['date']
                             price = row['close']
                             local_signals.append({
                                 "symbol": symbol, "type": "LONG", "time": signal_time, "price": price,
                                 "rsi_1h": row['rsi_1h'], "rsi_15m": row['rsi_15m'], "rsi_5m": row['rsi_5m']
                             })

                # --- SHORT CHECK ---
                elif row['rsi_1h'] < config.RSI_PARENT_SHORT_THRESHOLD and row['rsi_15m'] < config.RSI_PARENT_SHORT_THRESHOLD:
                    if row['close'] < row['open']: # Red Candle
                        if row['rsi_5m'] < 60: 
                             start_idx = max(0, idx - 5)
                             window = merged_df.iloc[start_idx : idx + 1]
                             rally_found = False
                             if window['rsi_5m'].max() > 60:
                                 rally_found = True
                             
                             if rally_found:
                                 signal_time = row['date']
                                 price = row['close']
                                 local_signals.append({
                                     "symbol": symbol, "type": "SHORT", "time": signal_time, "price": price,
                                     "rsi_1h": row['rsi_1h'], "rsi_15m": row['rsi_15m'], "rsi_5m": row['rsi_5m']
                                 })
            return local_signals

        except Exception as e:
            # logger.error(f"Error processing {symbol}: {e}")
            return []

    # --- Scope: NIFTY 50 INDEX ONLY ---
    # User strictly requested to track only the Nifty 50 Index.
    tokens = [
        {"symbol": "NIFTY 50", "token": "99926000", "exchange": "NSE"}
    ]
    logger.info(f"Starting Scan for NIFTY 50 INDEX (Token: 99926000)...")
    
    signals_list = []

    # Process sequentially (It's just one item)
    for item in tokens:
        res = process_stock(item)
        if res:
            signals_list.extend(res)

    logger.info("========================================")
    logger.info(f"Total Signals Generated: {len(signals_list)}")
    
    if not signals_list:
        logger.info("No Signals Found for NIFTY 50 Today.")
    
    for s in signals_list:
        print(f"{s['type']} - {s['symbol']} - {s['time']}")
        logger.info(f"{s['type']} SIGNAL: {s['symbol']} at {s['time']} | Price: {s['price']}")

    logger.info("========================================")

if __name__ == "__main__":
    main()

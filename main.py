import time
import schedule
from logzero import logger
import config
from datetime import datetime
from notifier import TelegramNotifier
from smart_api_helper import SmartApiHelper
from strategy_rep import REPStrategy

def main():
    logger.info("Initializing REP Strategy Bot...")

    # 1. Initialize API Helper
    helper = SmartApiHelper(
        api_key=config.API_KEY,
        client_id=config.CLIENT_ID,
        password=config.PASSWORD,
        totp_key=config.TOTP_KEY
    )

    # 2. Initialize Strategy
    strategy = REPStrategy(rsi_period=config.RSI_PERIOD)
    
    # 3. Initialize Notifier
    notifier = TelegramNotifier()
    try:
        notifier.send_alert("🚀 REP Strategy Bot Started on Render/Server")
    except Exception as e:
        logger.error(f"Startup Alert Failed: {e}")

    def is_market_open():
        # IST is UTC+5:30. Ensure server time is handled or assume strict time checks if running local/cloud with timezone set.
        # Ideally handle timezone explicitly.
        # For simplicity, assuming system time is IST or converting.
        # Render/Heroku are UTC. We must convert to IST.
        from datetime import timedelta, timezone
        
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        
        current_time = ist_now.time()
        start_time = datetime.strptime("09:15", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        
        logger.info(f"Checking Market Open. UTC: {utc_now.strftime('%H:%M')}, IST: {ist_now.strftime('%H:%M')} | Weekday: {ist_now.weekday()}")

        # Check if Weekend
        if ist_now.weekday() >= 5: # 5=Sat, 6=Sun
            logger.info("Market Closed (Weekend)")
            return False
            
        is_open = start_time <= current_time <= end_time
        if not is_open:
            logger.info(f"Market Closed (Time {current_time} outside {start_time}-{end_time})")
        
        return is_open

    # Lazy Load Tokens
    from token_loader import TokenLoader
    
    def load_tokens():
        logger.info("Loading FNO Tokens...")
        try:
            loader = TokenLoader()
            tokens = loader.get_fno_equity_list()
            # Add Indices
            if not any(s['symbol'] == 'NIFTY' for s in tokens):
                tokens.append({"symbol": "NIFTY", "token": "99926000", "exchange": "NSE"})
            if not any(s['symbol'] == 'BANKNIFTY' for s in tokens):
                tokens.append({"symbol": "BANKNIFTY", "token": "99926009", "exchange": "NSE"})
            config.SYMBOLS = tokens
            logger.info(f"Loaded {len(config.SYMBOLS)} Symbols.")
        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")

    def run_scan():
        # Ensure tokens are loaded
        if not config.SYMBOLS:
            load_tokens()

        if not is_market_open():
            logger.info("Market Closed. Sleeping...")
            return

        logger.info(f"Starting Scan Cycle for {len(config.SYMBOLS)} Symbols...")
        
        for item in config.SYMBOLS:
            symbol = item['symbol']
            token = item['token']
            exchange = item['exchange']
            
            try:
                # Rate Limiting: 3 requests per stock (Parent1, Parent2, Child)
                # Angel One Limit is ~3 req/sec. Safe logic: 1 stock per second.
                time.sleep(0.4) 

                # Fetch Data for 3 Timeframes
                parent1_df = helper.get_historical_data(token, exchange, config.TF_PARENT_1)
                
                # Check Parent 1 first to save API calls if invalid? 
                # Optimization: Yes. If Parent 1 (Hourly) is not > 60, don't fetch others.
                if parent1_df is None: continue
                
                parent1_df = strategy.calculate_rsi(parent1_df)
                if parent1_df['rsi'].iloc[-1] <= config.RSI_PARENT_THRESHOLD:
                    # logger.debug(f"{symbol}: Skipped (Parent 1 RSI {parent1_df['rsi'].iloc[-1]:.2f} <= 60)")
                    continue

                time.sleep(0.2)
                parent2_df = helper.get_historical_data(token, exchange, config.TF_PARENT_2)
                if parent2_df is None: continue
                
                parent2_df = strategy.calculate_rsi(parent2_df)
                if parent2_df['rsi'].iloc[-1] <= config.RSI_PARENT_THRESHOLD:
                     # logger.debug(f"{symbol}: Skipped (Parent 2 RSI <= 60)")
                     continue
                
                time.sleep(0.2)
                child_df = helper.get_historical_data(token, exchange, config.TF_CHILD)
                if child_df is None: continue
                child_df = strategy.calculate_rsi(child_df)

                # Check Conditions
                parents_ok, parents_msg = strategy.check_parent_conditions(
                    parent1_df, parent2_df, threshold=config.RSI_PARENT_THRESHOLD
                )
                
                if parents_ok:
                    child_ok, child_msg, confirmation_candle = strategy.check_child_condition(
                        child_df, 
                        support_low=config.RSI_CHILD_SUPPORT_LOW, 
                        support_high=config.RSI_CHILD_SUPPORT_HIGH
                    )
                    
                    if child_ok:
                        logger.info(f"*** SIGNAL FOUND for {symbol} ***")
                        # Send Telegram Alert
                        rsi_5m = child_df['rsi'].iloc[-1]
                        rsi_1h = parent1_df['rsi'].iloc[-1]
                        rsi_15m = parent2_df['rsi'].iloc[-1]
                        entry_price = confirmation_candle['high']
                        
                        msg = notifier.format_rep_signal(
                            symbol, 
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            entry_price,
                            rsi_5m,
                            rsi_1h,
                            rsi_15m
                        )
                        notifier.send_alert(msg)
            
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                time.sleep(1)

        logger.info("Scan Cycle Complete.")

    # Run Scan Logic in a separate thread sc that Flask can run in main thread (or vice versa)
    import threading
    
    # Schedule the scan
    schedule.every(5).minutes.do(run_scan)
    
    # Run once immediately
    threading.Thread(target=run_scan).start()

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    # Start Scheduler in Background Thread
    threading.Thread(target=run_scheduler, daemon=True).start()

    # --- Keep-Alive Web Server (for Render/Heroku) ---
    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def health_check():
        return "REP Bot is Running!"

    # Get Port from Environment (Render sets this)
    import os
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Web Server on port {port}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()

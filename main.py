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

    # State for Market Status Tracking
    bot_state = {"last_status": None}

    def run_scan():
        # Ensure tokens are loaded
        if not config.SYMBOLS:
            load_tokens()

        current_status = is_market_open()

        # Check for Status Change
        if bot_state["last_status"] is not None:
             if current_status and not bot_state["last_status"]:
                 msg = f"🟢 **Market Opened**\nBot is now scanning {len(config.SYMBOLS)} tokens."
                 try:
                     notifier.send_alert(msg)
                 except Exception as e:
                     logger.error(f"Failed to send Open Alert: {e}")
             
             elif not current_status and bot_state["last_status"]:
                 msg = f"🔴 **Market Closed**\nBot is sleeping until next session."
                 try:
                     notifier.send_alert(msg)
                 except Exception as e:
                     logger.error(f"Failed to send Close Alert: {e}")

        # Update State
        bot_state["last_status"] = current_status

        if not current_status:
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
                # Optimization: If Parent 1 (Hourly) is not > 60 AND not < 40, don't fetch others.
                if parent1_df is None: continue
                
                parent1_df = strategy.calculate_rsi(parent1_df)
                p1_rsi = parent1_df['rsi'].iloc[-1]
                
                # If neither LONG candidate nor SHORT candidate, skip
                if not (p1_rsi >= config.RSI_PARENT_THRESHOLD or p1_rsi <= config.RSI_PARENT_SHORT_THRESHOLD):
                     # logger.debug(f"{symbol}: Skipped (Parent 1 RSI {p1_rsi:.2f} neutral)")
                     continue
                
                time.sleep(0.2)
                parent2_df = helper.get_historical_data(token, exchange, config.TF_PARENT_2)
                if parent2_df is None: continue
                
                parent2_df = strategy.calculate_rsi(parent2_df)
                p2_rsi = parent2_df['rsi'].iloc[-1]
                
                # Check consistency
                # If p1 was LONG (>60), p2 must be >60. If p1 was SHORT (<40), p2 must be <40.
                if p1_rsi >= config.RSI_PARENT_THRESHOLD and p2_rsi < config.RSI_PARENT_THRESHOLD:
                     continue # Mixed signals
                if p1_rsi <= config.RSI_PARENT_SHORT_THRESHOLD and p2_rsi > config.RSI_PARENT_SHORT_THRESHOLD:
                     continue # Mixed signals
                
                time.sleep(0.2)
                child_df = helper.get_historical_data(token, exchange, config.TF_CHILD)
                if child_df is None: continue
                child_df = strategy.calculate_rsi(child_df)

                # Check Conditions
                parents_ok, parents_msg, mode = strategy.check_parent_conditions(
                    parent1_df, parent2_df, 
                    threshold_long=config.RSI_PARENT_THRESHOLD,
                    threshold_short=config.RSI_PARENT_SHORT_THRESHOLD
                )
                
                # --- Early Warning / Approaching Zone Check ---
                # Check using 15M (Parent 2) context as per user request
                warning_triggered, warning_msg = strategy.check_early_warning(child_df, parent2_df)
                
                if warning_triggered:
                    # Key: "NIFTY 50_WARN"
                    warn_key = f"{symbol}_WARN"
                    last_warn = bot_state.get("alerts", {}).get(warn_key, 0)
                    
                    # Alert every 15 minutes max for warnings
                    if time.time() - last_warn > 900: 
                        notifier.send_alert(f"{warning_msg}\nSymbol: {symbol}\nTime: {datetime.now().strftime('%H:%M')}")
                        if "alerts" not in bot_state: bot_state["alerts"] = {}
                        bot_state["alerts"][warn_key] = time.time()

                # --- Exit Alert Check ---
                exit_triggered, exit_msg = strategy.check_exit_condition(child_df, parent2_df)
                
                if exit_triggered:
                    exit_key = f"{symbol}_EXIT"
                    last_exit = bot_state.get("alerts", {}).get(exit_key, 0)
                    
                    # Alert every 15 mins (or maybe more frequent? kept 15m for safety)
                    if time.time() - last_exit > 900:
                         notifier.send_alert(f"{exit_msg}\nSymbol: {symbol}\nTime: {datetime.now().strftime('%H:%M')}")
                         if "alerts" not in bot_state: bot_state["alerts"] = {}
                         bot_state["alerts"][exit_key] = time.time()

                if parents_ok and mode:
                    child_ok, child_msg, confirmation_candle = strategy.check_child_condition(
                        child_df, 
                        mode=mode,
                        support_low=config.RSI_CHILD_SUPPORT_LOW, 
                        support_high=config.RSI_CHILD_SUPPORT_HIGH,
                        resist_low=config.RSI_CHILD_RESISTANCE_LOW,
                        resist_high=config.RSI_CHILD_RESISTANCE_HIGH
                    )
                    
                    if child_ok:
                        logger.info(f"*** {mode} SIGNAL FOUND for {symbol} ***")
                        # Send Telegram Alert
                        rsi_5m = child_df['rsi'].iloc[-1]
                        rsi_1h = parent1_df['rsi'].iloc[-1]
                        rsi_15m = parent2_df['rsi'].iloc[-1]
                        
                        entry_price = confirmation_candle['low'] if mode == "SHORT" else confirmation_candle['high'] 
                        # Use Low for Short entry break? Or just Close? 
                        # Usually entry is on close or break of low. 
                        # For now, let's just log the Close/Trigger Price.
                        # Actually logic says "TAKE A SHORT TRADE", usually at close.
                        trigger_price = confirmation_candle['close']
                        
                        msg = f"🚀 **REP {mode} SIGNAL**\nSymbol: {symbol}\nPrice: {trigger_price}\nRSI(5m): {rsi_5m:.2f}\nRSI(1h): {rsi_1h:.2f}\nRSI(15m): {rsi_15m:.2f}\nTime: {datetime.now().strftime('%H:%M:%S')}"
                        
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

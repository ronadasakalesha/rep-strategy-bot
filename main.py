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
    
    # 3. Initialize Notifiers
    notifier_eq = TelegramNotifier(config.TELEGRAM_BOT_TOKEN_EQUITY, config.TELEGRAM_CHAT_ID_EQUITY)
    notifier_crypto = TelegramNotifier(config.TELEGRAM_BOT_TOKEN_CRYPTO, config.TELEGRAM_CHAT_ID_CRYPTO)
    
    # 4. Initialize Delta Helper
    from delta_api_helper import DeltaApiHelper
    delta_helper = DeltaApiHelper(config.DELTA_API_KEY, config.DELTA_API_SECRET)

    try:
        notifier_eq.send_alert("🚀 REP Strategy Bot Started - Equity Module Active")
        notifier_crypto.send_alert("🚀 REP Strategy Bot Started - Crypto Module Active")
    except Exception as e:
        logger.error(f"Startup Alert Failed: {e}")

    def is_angel_market_open():
        # IST Check for Angel One
        from datetime import timedelta, timezone
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        current_time = ist_now.time()
        start_time = datetime.strptime("09:15", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        
        # Weekend Check
        if ist_now.weekday() >= 5: return False
        return start_time <= current_time <= end_time

    # Lazy Load Tokens
    from token_loader import TokenLoader
    def load_tokens():
        if not config.SYMBOLS:
            logger.info("Configuring Symbols (Restricted to NIFTY, BTC, ETH)...")
            try:
                # User requested ONLY Nifty 50 Index
                # bypassing TokenLoader().get_fno_equity_list()
                
                restricted_list = [
                    {"symbol": "NIFTY", "token": "99926000", "exchange": "NSE"}
                ]
                
                config.SYMBOLS = restricted_list
                logger.info(f"Loaded {len(config.SYMBOLS)} Equity Symbol(s): {[s['symbol'] for s in config.SYMBOLS]}")
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")

    bot_state = {"last_angel_status": None}

    def process_symbol(symbol, identifier, exchange, helper_obj, notifier_obj, timeframes):
        """
        Common logic to process a symbol for a specific timeframe set.
        """
        strat_name = timeframes['name']
        try:
            # Rate Limit Sleep
            time.sleep(0.5)

            # 1. Parent 1
            p1 = helper_obj.get_historical_data(identifier, exchange, timeframes['p1'])
            if p1 is None: return
            p1 = strategy.calculate_rsi(p1)
            p1_rsi = p1['rsi'].iloc[-1]

            # Filter: Must be trending (>60 or <40)
            if not (p1_rsi >= config.RSI_PARENT_THRESHOLD or p1_rsi <= config.RSI_PARENT_SHORT_THRESHOLD):
                return

            # 2. Parent 2
            p2 = helper_obj.get_historical_data(identifier, exchange, timeframes['p2'])
            if p2 is None: return
            p2 = strategy.calculate_rsi(p2)
            p2_rsi = p2['rsi'].iloc[-1]

            # Consistency Check
            if p1_rsi >= config.RSI_PARENT_THRESHOLD and p2_rsi < config.RSI_PARENT_THRESHOLD: return
            if p1_rsi <= config.RSI_PARENT_SHORT_THRESHOLD and p2_rsi > config.RSI_PARENT_SHORT_THRESHOLD: return

            # 3. Child (Entry)
            child = helper_obj.get_historical_data(identifier, exchange, timeframes['child'])
            if child is None: return
            child = strategy.calculate_rsi(child)

            # 4. Strategy Check
            parents_ok, parents_msg, mode = strategy.check_parent_conditions(
                p1, p2, 
                threshold_long=config.RSI_PARENT_THRESHOLD,
                threshold_short=config.RSI_PARENT_SHORT_THRESHOLD
            )

            # Warnings & Exits
            warning_triggered, warning_msg = strategy.check_early_warning(child, p2)
            if warning_triggered:
                warn_key = f"{symbol}_{strat_name}_WARN"
                last_warn = bot_state.get("alerts", {}).get(warn_key, 0)
                if time.time() - last_warn > 900:
                    notifier_obj.send_alert(f"{warning_msg}\nType: {strat_name}\nSymbol: {symbol}\nTime: {datetime.now().strftime('%H:%M')}")
                    if "alerts" not in bot_state: bot_state["alerts"] = {}
                    bot_state["alerts"][warn_key] = time.time()

            exit_triggered, exit_msg = strategy.check_exit_condition(child, p2)
            if exit_triggered:
                exit_key = f"{symbol}_{strat_name}_EXIT"
                last_exit = bot_state.get("alerts", {}).get(exit_key, 0)
                if time.time() - last_exit > 900:
                    notifier_obj.send_alert(f"{exit_msg}\nType: {strat_name}\nSymbol: {symbol}\nTime: {datetime.now().strftime('%H:%M')}")
                    if "alerts" not in bot_state: bot_state["alerts"] = {}
                    bot_state["alerts"][exit_key] = time.time()

            # Signal Check
            if parents_ok and mode:
                child_ok, child_msg, confirmation_candle = strategy.check_child_condition(
                    child, 
                    mode=mode,
                    support_low=config.RSI_CHILD_SUPPORT_LOW, 
                    support_high=config.RSI_CHILD_SUPPORT_HIGH,
                    resist_low=config.RSI_CHILD_RESISTANCE_LOW,
                    resist_high=config.RSI_CHILD_RESISTANCE_HIGH
                )
                
                if child_ok:
                    rsi_child_val = child['rsi'].iloc[-1]
                    trigger_price = confirmation_candle['close']
                    msg = (f"🚀 **REP {mode} SIGNAL** ({strat_name})\n"
                           f"Symbol: {symbol}\n"
                           f"Price: {trigger_price}\n"
                           f"Entry RSI: {rsi_child_val:.2f}\n"
                           f"P1 RSI: {p1_rsi:.2f}\n"
                           f"P2 RSI: {p2_rsi:.2f}\n"
                           f"Time: {datetime.now().strftime('%H:%M:%S')}")
                    logger.info(f"SIGNAL: {symbol} {mode} [{strat_name}]")
                    notifier_obj.send_alert(msg)

        except Exception as e:
            logger.error(f"Error processing {symbol} ({strat_name}): {e}")


    def run_scan():
        load_tokens()
        
        # --- 1. Process Angel One (Equity based on Market Hours) ---
        angel_open = is_angel_market_open()
        
        # Alert Status Change - EQUITY
        if bot_state["last_angel_status"] is not None:
             if angel_open and not bot_state["last_angel_status"]:
                 notifier_eq.send_alert("🟢 **Equity Market Open**")
             elif not angel_open and bot_state["last_angel_status"]:
                 notifier_eq.send_alert("🔴 **Equity Market Closed**")
        bot_state["last_angel_status"] = angel_open

        if angel_open:
            logger.info(f"Scanning {len(config.SYMBOLS)} Angel Symbols...")
            for item in config.SYMBOLS:
                # Iterate through all configured strategy sets
                for strat_set in config.STRATEGY_SETS:
                    process_symbol(item['symbol'], item['token'], item['exchange'], helper, notifier_eq, strat_set)
        else:
            logger.info("Equity Market Closed. Skipping Angel symbols.")

        # --- 2. Process Delta Exchange (Crypto 24/7) ---
        if config.CRYPTO_SYMBOLS:
            logger.info(f"Scanning {len(config.CRYPTO_SYMBOLS)} Crypto Symbols...")
            for sym in config.CRYPTO_SYMBOLS:
                # Iterate through all configured strategy sets
                for strat_set in config.STRATEGY_SETS:
                    process_symbol(sym, sym, "DELTA", delta_helper, notifier_crypto, strat_set)

        logger.info("Scan Cycle Complete.")

    # Run Scan Logic in a separate thread so that we can keep the main thread for the scheduler
    import threading
    
    # Schedule the scan
    schedule.every(5).minutes.do(run_scan)
    
    # Run once immediately
    threading.Thread(target=run_scan).start()

    logger.info("Bot Scheduler is running...")
    
    # Run Scheduler in Main Thread (Blocking)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()

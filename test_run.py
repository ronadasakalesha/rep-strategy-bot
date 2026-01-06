import config
from logzero import logger
import main

# Override SYMBOLS to a small list for quick testing
logger.info("Overriding SYMBOLS for Test Run...")
config.SYMBOLS = [
    {"symbol": "ICICIBANK", "token": "4963", "exchange": "NSE"},
    {"symbol": "SBIN", "token": "3045", "exchange": "NSE"},
    {"symbol": "RELIANCE", "token": "2885", "exchange": "NSE"},
    {"symbol": "INFY", "token": "1594", "exchange": "NSE"} 
]

# Disable the infinite loop in main for testing, we just want to run the scan logic
# We can extract the 'run_scan' inner function if we refactor main, 
# OR we can just copy the logic here since 'run_scan' is inside 'main()' scope and not easily accessible 
# unless we modify main.py.

# Let's modify main.py slightly to allow importing run_scan or just copy the init logic.
# Actually, better to just instantiate and run here to verify components.

from smart_api_helper import SmartApiHelper
from strategy_rep import REPStrategy
from notifier import TelegramNotifier
import time
from datetime import datetime

def test_run():
    logger.info("Initializing Test Bot...")
    
    helper = SmartApiHelper(config.API_KEY, config.CLIENT_ID, config.PASSWORD, config.TOTP_KEY)
    strategy = REPStrategy(rsi_period=config.RSI_PERIOD)
    notifier = TelegramNotifier()
    
    logger.info(f"Scanning {len(config.SYMBOLS)} test symbols...")
    
    for item in config.SYMBOLS:
        symbol = item['symbol']
        token = item['token']
        exchange = item['exchange']
        
        try:
            logger.info(f"Scanning {symbol}...")
            # Reduced sleep for test
            time.sleep(0.1)
            
            p1 = helper.get_historical_data(token, exchange, config.TF_PARENT_1)
            if p1 is None: continue
            p1 = strategy.calculate_rsi(p1)
            p1_rsi = p1['rsi'].iloc[-1]
            logger.info(f"  {symbol} 1h RSI: {p1_rsi:.2f}")
            
            if p1_rsi <= config.RSI_PARENT_THRESHOLD:
                logger.info(f"  > Skipping {symbol} (Parent 1 not confirmed)")
                continue
                
            p2 = helper.get_historical_data(token, exchange, config.TF_PARENT_2)
            p2 = strategy.calculate_rsi(p2)
            p2_rsi = p2['rsi'].iloc[-1]
            logger.info(f"  {symbol} 15m RSI: {p2_rsi:.2f}")

            if p2_rsi <= config.RSI_PARENT_THRESHOLD:
                 logger.info(f"  > Skipping {symbol} (Parent 2 not confirmed)")
                 continue

            c = helper.get_historical_data(token, exchange, config.TF_CHILD)
            c = strategy.calculate_rsi(c)
            
            # Check Parents
            ok, msg = strategy.check_parent_conditions(p1, p2, config.RSI_PARENT_THRESHOLD)
            if ok:
                child_ok, child_msg, conf = strategy.check_child_condition(c, config.RSI_CHILD_SUPPORT_LOW, config.RSI_CHILD_SUPPORT_HIGH)
                if child_ok:
                    logger.info(f"*** SIGNAL SIMULATED for {symbol} ***")
                    msg = notifier.format_rep_signal(symbol, datetime.now(), conf['high'], c['rsi'].iloc[-1], p1_rsi, p2_rsi)
                    # Send actual alert to prove it works
                    notifier.send_alert(msg)
                else:
                    logger.info(f"  > Parents OK. Child condition: {child_msg}")

        except Exception as e:
            logger.error(e)

if __name__ == "__main__":
    test_run()

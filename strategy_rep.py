import pandas_ta as ta
import pandas as pd
from logzero import logger

class REPStrategy:
    def __init__(self, rsi_period=14):
        self.rsi_period = rsi_period

    def calculate_rsi(self, df):
        if df is None or len(df) < self.rsi_period:
            return None
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        return df

    def check_parent_conditions(self, parent1_df, parent2_df, threshold=60):
        """
        Checks if RSI is above threshold (60) for both parent timeframes.
        """
        if parent1_df is None or parent2_df is None:
            return False, "Data Missing"

        rsi1 = parent1_df['rsi'].iloc[-1]
        rsi2 = parent2_df['rsi'].iloc[-1]

        if rsi1 > threshold and rsi2 > threshold:
            return True, f"Parents Bullish (RSI1: {rsi1:.2f}, RSI2: {rsi2:.2f})"
        else:
            return False, f"Parents Failed (RSI1: {rsi1:.2f}, RSI2: {rsi2:.2f})"

    def check_child_condition(self, child_df, support_low=38, support_high=40):
        """
        Checks if Child RSI dipped into 38-40 zone and we have a GREEN confirmation candle.
        """
        if child_df is None:
            return False, "Data Missing", None

        # Look at the last few candles to find a dip into the zone
        last_candles = child_df.tail(5) 
        
        confirmation_candle = None
        rsi_dip_found = False

        for i in range(len(last_candles) - 1): # Iterate up to the second to last candle
            rsi_val = last_candles['rsi'].iloc[i]
            if support_low <= rsi_val <= support_high:
                 rsi_dip_found = True
                 # Check if the NEXT candle (or current one) is green
                 # We look for a green candle occurring AFTER or DURING the dip
                 potential_conf_idx = i + 1
                 if potential_conf_idx < len(last_candles):
                     close = last_candles['close'].iloc[potential_conf_idx]
                     open_ = last_candles['open'].iloc[potential_conf_idx]
                     if close > open_:
                         confirmation_candle = last_candles.iloc[potential_conf_idx]
                         break
        
        # Also check just the very last completed candle for live trading
        current_rsi = child_df['rsi'].iloc[-1]
        current_close = child_df['close'].iloc[-1]
        current_open = child_df['open'].iloc[-1]
        
        if support_low <= current_rsi <= support_high:
             if current_close > current_open:
                 confirmation_candle = child_df.iloc[-1]
                 return True, f"Child Setup Found: RSI {current_rsi:.2f} in Zone & Green Candle", confirmation_candle

        if confirmation_candle is not None:
             return True, "Child Setup Found (Recent): RSI Dip & Green Candle", confirmation_candle
            
        return False, f"Child No Setup (Current RSI: {child_df['rsi'].iloc[-1]:.2f})", None

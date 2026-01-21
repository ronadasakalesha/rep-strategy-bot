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

    def check_parent_conditions(self, parent1_df, parent2_df, threshold_long=60, threshold_short=40, lookback=10):
        """
        Checks parent timeframes.
        Logic: 
        - Parent 1 (1H): STRICT. Current RSI must be > threshold_long or < threshold_short.
        - Parent 2 (15M): STRICT. Current RSI must be > threshold_long or < threshold_short.
        (Both must satisfy the condition currently)
        Returns: (bool, str, mode)
        """
        if parent1_df is None or parent2_df is None:
            return False, "Data Missing", None

        # 1. Check Parent 1 (1H)
        p1_rsi = parent1_df['rsi'].iloc[-1]
        p1_mode = "NEUTRAL"
        if p1_rsi > threshold_long:
            p1_mode = "LONG"
        elif p1_rsi < threshold_short:
            p1_mode = "SHORT"
        
        if p1_mode == "NEUTRAL":
             return False, f"Parent 1 (1H) Neutral (RSI: {p1_rsi:.2f})", None

        # 2. Check Parent 2 (15M) - STRICT
        p2_rsi = parent2_df['rsi'].iloc[-1]
        p2_mode = "NEUTRAL"
        if p2_rsi > threshold_long:
            p2_mode = "LONG"
        elif p2_rsi < threshold_short:
            p2_mode = "SHORT"

        # 3. Validation: Both must agree strictly
        if p1_mode == "LONG" and p2_mode == "LONG":
            return True, f"Parents Bullish (P1: {p1_rsi:.2f}, P2: {p2_rsi:.2f})", "LONG"
        
        if p1_mode == "SHORT" and p2_mode == "SHORT":
            return True, f"Parents Bearish (P1: {p1_rsi:.2f}, P2: {p2_rsi:.2f})", "SHORT"

        return False, f"Parents Mismatch (P1:{p1_mode}, P2:{p2_mode})", None

    def _check_strict_zone_touch(self, child_df, mode, lookback=10, support_low=38, support_high=40, resist_low=60, resist_high=62):
        """
        OPTION 1: Strict Zone Touch.
        Checks if RSI touched a specific zone within the last 'lookback' candles and is now reversing.
        """
        current_rsi = child_df['rsi'].iloc[-1]
        # Check history excluding current candle
        recent_history = child_df['rsi'].iloc[-lookback-1 : -1]

        if mode == "LONG":
            # Check if ANY candle in lookback touched the zone
            touched_support = ((recent_history >= support_low) & (recent_history <= support_high)).any()
            if touched_support:
                # Trigger: Closed back above upper bound
                if current_rsi > support_high:
                    return True, f"LONG (Strict Zone): Touched {support_low}-{support_high}, Now {current_rsi:.2f}", child_df.iloc[-1]
                else:
                    return False, f"Waiting Trigger (Strict): {current_rsi:.2f} <= {support_high}", None
        
        elif mode == "SHORT":
            # Check if ANY candle in lookback touched the zone
            touched_resistance = ((recent_history >= resist_low) & (recent_history <= resist_high)).any()
            if touched_resistance:
                # Trigger: Closed back below lower bound
                if current_rsi < resist_low:
                     return True, f"SHORT (Strict Zone): Touched {resist_low}-{resist_high}, Now {current_rsi:.2f}", child_df.iloc[-1]
                else:
                    return False, f"Waiting Trigger (Strict): {current_rsi:.2f} >= {resist_low}", None
        
        return False, "No Strict Setup", None

    def _check_swing_pivot(self, child_df, mode, max_rsi_for_support=55, min_rsi_for_resistance=45):
        """
        OPTION 2: Dynamic Swing Pivot.
        Detects V-Shape (Buy) or A-Shape (Sell) reversal without needing strict zone touch.
        """
        if len(child_df) < 3: return False, "Not Enough Data", None

        rsi_now = child_df['rsi'].iloc[-1]
        rsi_mid = child_df['rsi'].iloc[-2]
        rsi_left = child_df['rsi'].iloc[-3]

        if mode == "LONG":
            # 1. V-Shape: Left > Low AND Now > Low
            is_pivot_low = (rsi_left > rsi_mid) and (rsi_now > rsi_mid)
            # 2. Level: Low was "low enough" (e.g. < 55)
            is_low_enough = rsi_mid < max_rsi_for_support
            
            if is_pivot_low and is_low_enough:
                 return True, f"LONG (Swing Pivot): Supported at {rsi_mid:.2f} (Pivot < {max_rsi_for_support})", child_df.iloc[-1]
                 
        elif mode == "SHORT":
            # 1. A-Shape: Left < High AND Now < High
            is_pivot_high = (rsi_left < rsi_mid) and (rsi_now < rsi_mid)
            # 2. Level: High was "high enough" (e.g. > 45)
            is_high_enough = rsi_mid > min_rsi_for_resistance
            
            if is_pivot_high and is_high_enough:
                return True, f"SHORT (Swing Pivot): Resisted at {rsi_mid:.2f} (Pivot > {min_rsi_for_resistance})", child_df.iloc[-1]

        return False, "No Swing Setup", None

    def check_child_condition(self, child_df, mode):
        """
        Checks 5M Entry Triggers.
        Currently ACTIVE: Option 2 (Swing Pivot).
        """
        if child_df is None or mode is None:
            return False, "Data Missing", None

        # --- OPTION 1: STRICT ZONE (Inactive for now) ---
        # To enable, uncomment below and return its result
        # is_setup, msg, candle = self._check_strict_zone_touch(child_df, mode)
        # if is_setup: return True, msg, candle
        
        # --- OPTION 2: SWING PIVOT (Active) ---
        # Allows entering on shallow pullbacks in strong trends
        return self._check_swing_pivot(child_df, mode)

    def check_early_warning(self, child_df, parent_df):
        """
        Checks for Early Warning / Approaching Zone.
        Context based on 15M RSI (Parent 2).
        15M > 60 -> Alert if Child touches 40.
        15M < 40 -> Alert if Child touches 60.
        """
        if child_df is None or parent_df is None:
            return False, None

        current_rsi = child_df['rsi'].iloc[-1]
        parent_rsi = parent_df['rsi'].iloc[-1]

        if parent_rsi > 60:
            # Long Context
            if current_rsi <= 42:
                return True, f"⚠️ **Watch Alert**: RSI {current_rsi:.2f} near 40 (Support) | 15M Bullish ({parent_rsi:.2f})"
        
        if parent_rsi < 40:
            # Short Context
            if current_rsi >= 58:
                return True, f"⚠️ **Watch Alert**: RSI {current_rsi:.2f} near 60 (Resistance) | 15M Bearish ({parent_rsi:.2f})"
            
        return False, None

    def check_exit_condition(self, child_df, parent_df):
        """
        Checks for Exit Alerts.
        Buy Exit: 15M > 60 AND 5M touches 60.
        Sell Exit: 15M < 40 AND 5M touches 40.
        """
        if child_df is None or parent_df is None:
            return False, None
            
        current_5m_rsi = child_df['rsi'].iloc[-1]
        current_15m_rsi = parent_df['rsi'].iloc[-1]
        
        # Buy Exit (Both High)
        if current_15m_rsi > 60 and current_5m_rsi >= 60:
             return True, f"🚨 **Buy Exit Alert**: 5M RSI ({current_5m_rsi:.2f}) touched 60 while 15M > 60"

        # Sell Exit (Both Low)
        if current_15m_rsi < 40 and current_5m_rsi <= 40:
             return True, f"🚨 **Sell Exit Alert**: 5M RSI ({current_5m_rsi:.2f}) touched 40 while 15M < 40"
             
        return False, None

import pandas as pd
import numpy as np

def add_advanced_technicals(df):
    if df is None or df.empty:
        return df
    df = df.copy()

    # --- 1. 移動平均線 ---
    df['MA25'] = df['Close'].rolling(window=25).mean()
    df['MA75'] = df['Close'].rolling(window=75).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # --- 2. RSI (ワイルダー式: 機関投資家標準) ---
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(alpha=1/14, adjust=False).mean()
    ema_down = down.ewm(alpha=1/14, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))

    # --- 3. MACD (12, 26, 9) ---
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # --- 4. ボリンジャーバンド (20日, ±2σ, ±3σ) ---
    ma20 = df['Close'].rolling(window=20).mean()
    std20 = df['Close'].rolling(window=20).std(ddof=0)
    df['BB_upper2'] = ma20 + (std20 * 2)
    df['BB_lower2'] = ma20 - (std20 * 2)
    df['BB_upper3'] = ma20 + (std20 * 3)
    df['BB_lower3'] = ma20 - (std20 * 3)

    # --- 5. 出来高移動平均 (Volume MA 25日) ---
    df['Vol_MA25'] = df['Volume'].rolling(window=25).mean()

    # JSONでエラーにならないよう、NaNをNoneに置換（行自体は消さない）
    df = df.replace({np.nan: None})
    return df
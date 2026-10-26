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

    # --- 6. 20日EMA & ADX (ホーリー・グレイル & トレンド強度) ---
    df = add_adx_and_ema20(df)

    # JSONでエラーにならないよう、NaNをNoneに置換（行自体は消さない）
    df = df.replace({np.nan: None})
    return df

def add_adx_and_ema20(df, period=14):
    """Wilder式のADX (+DI, -DI, ADX) と 20日EMAを算出する"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    alpha = 1.0 / period
    tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=alpha, adjust=False).mean()

    plus_di = (plus_dm_smooth / tr_smooth) * 100
    minus_di = (minus_dm_smooth / tr_smooth) * 100

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = (di_diff / di_sum.replace(0, np.nan)) * 100
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    df['EMA20'] = close.ewm(span=20, adjust=False).mean()
    df['Plus_DI'] = plus_di
    df['Minus_DI'] = minus_di
    df['ADX'] = adx
    return df

def detect_holy_grail_and_n_pattern(df):
    """
    1. リンダ・ラシュキの「ホーリー・グレイル（聖杯）」シグナル
       - ADX(14) >= 25（強いトレンド）かつ +DI > -DI（上昇トレンド）
       - 20日EMAへの押し目タッチ（Low <= EMA20 * 1.01 かつ Close >= EMA20 * 0.985）
       - 当日反発（陽線または前日高値超え）
    2. 水平線「N字ブレイク（ロールリバーサル）」シグナル
       - 過去20〜60日の高値（旧レジスタンス）を直近でブレイクした実績
       - その旧高値ライン付近（±2.5%）まで押し目を形成して反発
    """
    if df is None or len(df) < 30:
        return {"is_holy_grail": False, "is_n_pattern": False, "signals": []}

    df_calc = add_adx_and_ema20(df.copy())
    latest = df_calc.iloc[-1]
    prev = df_calc.iloc[-2]

    adx = latest['ADX']
    plus_di = latest['Plus_DI']
    minus_di = latest['Minus_DI']
    ema20 = latest['EMA20']
    close_p = latest['Close']
    open_p = latest['Open']

    signals = []

    # ① ホーリー・グレイル判定
    is_strong_uptrend = (adx >= 25.0) and (plus_di > minus_di)
    recent_lows = df_calc['Low'].tail(3)
    recent_ema20 = df_calc['EMA20'].tail(3)
    touched_ema20 = any(low <= ema * 1.01 for low, ema in zip(recent_lows, recent_ema20))
    is_bouncing = (close_p >= ema20 * 0.985) and (close_p > open_p or close_p > prev['High'])

    is_holy_grail = bool(is_strong_uptrend and touched_ema20 and is_bouncing)
    if is_holy_grail:
        signals.append(f"🏆 [聖杯・20日線押し目] ADX={adx:.1f} / 20日EMA反発")

    # ② N字ロールリバーサル判定
    window_df = df_calc.iloc[-60:-3] if len(df_calc) >= 63 else df_calc.iloc[:-3]
    is_n_pattern = False
    if len(window_df) >= 15:
        prior_resistance = float(window_df['High'].max())
        recent_window = df_calc.iloc[-10:]
        has_broken_out = any(recent_window['High'] > prior_resistance * 1.01)
        touched_support = any(abs(low - prior_resistance) / prior_resistance <= 0.025 for low in recent_lows)
        is_support_rebound = (close_p >= prior_resistance * 0.99) and (close_p > open_p)

        if has_broken_out and touched_support and is_support_rebound:
            is_n_pattern = True
            signals.append(f"📐 [N字ロールリバーサル] 旧高値({prior_resistance:,.0f}円)支持反発")

    return {
        "is_holy_grail": is_holy_grail,
        "is_n_pattern": is_n_pattern,
        "adx": round(float(adx), 1) if pd.notna(adx) else 0.0,
        "plus_di": round(float(plus_di), 1) if pd.notna(plus_di) else 0.0,
        "minus_di": round(float(minus_di), 1) if pd.notna(minus_di) else 0.0,
        "ema20": round(float(ema20), 1) if pd.notna(ema20) else 0.0,
        "signals": signals
    }

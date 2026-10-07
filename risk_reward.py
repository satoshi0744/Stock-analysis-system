import pandas as pd
import numpy as np

def analyze_candlestick(df):
    """
    ローソク足の形状から「ダマシ・高値掴みの罠（Fakeout / Bull Trap）」を検証する。
    
    Returns:
        dict:
            is_trap (bool): トラップ・ダマシの疑いがあるか
            trap_reasons (list): トラップと判定された理由
            upper_wick_ratio (float): 上ヒゲがレンジ全体に占める割合 (0.0〜1.0)
            is_pure_bullish (bool): 当日終値が始値より高い真の陽線か
            is_bearish (bool): 当日終値が始値より低い陰線か
            body_ratio (float): 実体の比率
    """
    if df is None or len(df) < 2:
        return {
            "is_trap": False,
            "trap_reasons": [],
            "upper_wick_ratio": 0.0,
            "is_pure_bullish": False,
            "is_bearish": False,
            "body_ratio": 0.0
        }

    latest = df.iloc[-1]
    open_p = float(latest['Open'])
    high_p = float(latest['High'])
    low_p = float(latest['Low'])
    close_p = float(latest['Close'])

    tr = high_p - low_p
    body = abs(close_p - open_p)
    upper_wick = high_p - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low_p
    upper_wick_ratio = upper_wick / tr if tr > 0 else 0.0

    is_pure_bullish = close_p > open_p
    is_bearish = close_p < open_p

    trap_reasons = []

    # 1. 当日陰線（寄り天・ブレイク失敗・利確売りに押された形）
    if is_bearish:
        trap_reasons.append("当日陰線（寄り天・売り優勢）")

    # 2. 上ヒゲ過大（レンジの40%以上が上ヒゲ）
    if upper_wick_ratio >= 0.40:
        trap_reasons.append(f"上ヒゲ過大 ({upper_wick_ratio*100:.1f}%)")

    # 3. 実体に比べて上ヒゲが長すぎる（実体の1.5倍超かつ上ヒゲ率35%以上）
    if tr > 0 and upper_wick > body * 1.5 and upper_wick_ratio >= 0.35:
        if f"上ヒゲ過大 ({upper_wick_ratio*100:.1f}%)" not in trap_reasons:
            trap_reasons.append("上ヒゲが実体より長い（上値圧迫）")

    is_trap = len(trap_reasons) > 0

    return {
        "is_trap": is_trap,
        "trap_reasons": trap_reasons,
        "upper_wick_ratio": round(upper_wick_ratio, 3),
        "is_pure_bullish": is_pure_bullish,
        "is_bearish": is_bearish,
        "body_ratio": round(body / tr, 3) if tr > 0 else 0.0,
        "lower_wick_ratio": round(lower_wick / tr, 3) if tr > 0 else 0.0
    }

def calculate_risk_reward(df):
    """
    直近スイング安値（SL: 損切りライン）と想定上値抵抗線（TP: 目標利確）からリスクリワード比を算出する。
    
    Returns:
        dict:
            sl_price (float): 推奨損切り価格
            sl_type (str): 損切りラインの根拠
            risk_amount (float): 1株あたりリスク額
            risk_pct (float): リスク比率 (%)
            tp_price (float): 目標利確価格
            tp_type (str): 目標価格の根拠
            reward_amount (float): 1株あたり想定リワード額
            reward_pct (float): リワード比率 (%)
            rr_ratio (float): リスクリワード比 (リワード/リスク)
            rr_eval (str): 評価文言
            rr_color (str): UI表示色
    """
    if df is None or len(df) < 20:
        return None

    latest = df.iloc[-1]
    close_p = float(latest['Close'])

    # --- 1. 推奨損切りライン (SL: Stop Loss) ---
    # 直近5日間の最安値（直近スイングの支持帯）
    window_5 = min(5, len(df))
    window_10 = min(10, len(df))
    recent_5_low = float(df['Low'].tail(window_5).min())
    recent_10_low = float(df['Low'].tail(window_10).min())

    sl_price = recent_5_low
    sl_type = f"直近{window_5}日スイング安値"
    risk_amount = close_p - sl_price
    risk_pct = (risk_amount / close_p) * 100 if close_p > 0 else 0.0

    # リスク幅が狭すぎる場合（1.5%未満：日常ノイズで簡単に狩られるリスク大）
    if risk_pct < 1.5:
        sl_price = recent_10_low
        sl_type = f"直近{window_10}日スイング安値"
        risk_amount = close_p - sl_price
        risk_pct = (risk_amount / close_p) * 100 if close_p > 0 else 0.0

    # スイング安値が現在値と同じ、または極端に近い場合のフェイルセーフ（-3.5%固定サポート）
    if risk_amount <= 0 or risk_pct < 1.0:
        sl_price = round(close_p * 0.965, 1)
        sl_type = "基準支持ライン (-3.5%)"
        risk_amount = close_p - sl_price
        risk_pct = 3.5

    # 損切り幅が12%を超えて広すぎる場合、前日安値または直近ブレイクラインを代替参照
    if risk_pct > 12.0 and len(df) >= 2:
        prev_low = float(df['Low'].iloc[-2])
        if close_p > prev_low:
            sl_price = prev_low
            sl_type = "前日安値ライン"
            risk_amount = close_p - sl_price
            risk_pct = (risk_amount / close_p) * 100

    # --- 2. 想定利確目標 (TP: Take Profit) ---
    # 過去60日高値、過去120日高値を探索
    window_60 = min(60, len(df))
    window_120 = min(120, len(df))
    high_60 = float(df['High'].tail(window_60).max())
    high_120 = float(df['High'].tail(window_120).max())

    # 上値抵抗線までの距離を確認
    if close_p < high_60 * 0.985:
        tp_price = high_60
        tp_type = f"直近レジスタンス (過去{window_60}日高値)"
    elif close_p < high_120 * 0.985:
        tp_price = high_120
        tp_type = f"中期レジスタンス (過去{window_120}日高値)"
    else:
        # 新高値・青天井ゾーン：直近リスク幅の2倍をプロジェクション
        tp_price = close_p + (risk_amount * 2.0)
        tp_type = "新高値ブレイク目標 (R/R 1:2 プロジェクション)"

    reward_amount = tp_price - close_p
    reward_pct = (reward_amount / close_p) * 100 if close_p > 0 else 0.0

    # --- 3. リスクリワード比 (R/R Ratio) ---
    rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0

    if rr_ratio >= 2.0:
        rr_eval = "優良 (1:2以上)"
        rr_color = "#69f0ae"  # 緑
    elif rr_ratio >= 1.5:
        rr_eval = "適正 (1:1.5以上)"
        rr_color = "#ffd700"  # 黄色
    else:
        rr_eval = "警戒 (1:1.5未満・割安感薄)"
        rr_color = "#ff5252"  # 赤

    return {
        "sl_price": round(sl_price, 1),
        "sl_type": sl_type,
        "risk_amount": round(risk_amount, 1),
        "risk_pct": round(risk_pct, 2),
        "tp_price": round(tp_price, 1),
        "tp_type": tp_type,
        "reward_amount": round(reward_amount, 1),
        "reward_pct": round(reward_pct, 2),
        "rr_ratio": round(rr_ratio, 2),
        "rr_eval": rr_eval,
        "rr_color": rr_color
    }

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import concurrent.futures
import time
import json

JST = timezone(timedelta(hours=9))

def load_watchlist():
    """GitHub上の最新のwatchlist.jsonを読み込む"""
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return {}

def check_market_trend(start_str, end_str):
    try:
        ticker = yf.Ticker("^N225")
        df = ticker.history(start=start_str, end=end_str)
        if df.empty or len(df) < 200:
            return False, "判定不能"
        
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_above_ma200 = bool(latest['Close'] > latest['MA200'])
        is_above_ma25 = bool(latest['Close'] > latest['MA25'])
        is_above_ma5 = bool(latest['Close'] > latest['MA5'])
        is_falling = bool(latest['Close'] < prev['Close']) 
        
        # 厳格な地合い判定（続落時は良好と出さない）
        if is_above_ma200 and is_above_ma25 and is_above_ma5 and not is_falling:
            is_good = True
            text = "🟩 良好 (200日・25日線上 / 短期リバ期待)"
        elif is_above_ma200 and (not is_above_ma25 or is_falling):
            is_good = False 
            text = "🟨 調整局面 (続落中につき静観推奨)"
        else:
            is_good = False
            text = "⚠️ 警戒 (長期トレンド下落中)"
            
        return is_good, text
    except:
        return False, "データ取得エラー"

def process_ticker(code, name, start_str, end_str, is_good_market):
    try:
        ticker = yf.Ticker(f"{code}.T")
        df = ticker.history(start=start_str, end=end_str)
        if df.empty or len(df) < 200: return None
        df.index = df.index.tz_localize(None)
        
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['High_20'] = df['High'].rolling(window=20).max().shift(1)
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        is_yosen = latest['Close'] > latest['Open']
        
        # RSI計算
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = round(100 - (100 / (1 + (gain / loss))), 1)

        group = "B"
        signals = []
        
        # 1. 上昇加速型 (A群) - 地合い良好時のみ
        vol_avg20 = df['Volume'].rolling(window=20).mean().iloc[-2]
        vol_ratio = latest['Volume'] / vol_avg20 if vol_avg20 > 0 else 0
        if is_good_market and latest['Close'] > latest['High_20'] and vol_ratio >= 1.5 and latest['Close'] > latest['MA200']:
            group = "A"
            signals.append("🚀 上昇加速型 (20日高値更新)")

        # 2. 底打ち確認型 (復元：RSI30以下かつMA25乖離)
        if rsi <= 30 and latest['Close'] < latest['MA25'] * 0.95 and is_yosen:
            group = "A"
            signals.append("🔄 底打ち確認 (RSI低位・MA25乖離)")

        if not signals: return None

        df_clean = df.tail(100)
        history = [{"time": i.strftime('%Y-%m-%d'), "open": r['Open'], "high": r['High'], "low": r['Low'], "close": r['Close']} for i, r in df_clean.iterrows()]

        return {
            "group": group,
            "data": {
                "code": code, "name": name, "price": int(latest['Close']), 
                "price_diff": int(latest['Close'] - prev['Close']),
                "rsi": rsi, "signals": signals, "history_data": history
            }
        }
    except: return None

def scan_b_type(target_date_str=None):
    # 最新の監視銘柄リストを取得
    watchlist = load_watchlist()
    
    end = datetime.now(JST)
    start = end - timedelta(days=500) 
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    
    is_good_market, market_text = check_market_trend(start_str, end_str)
    
    scan_a = []
    scan_b = []
    
    # watchlistの内容に基づいて並列スキャン実行
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_ticker, code, name, start_str, end_str, is_good_market): code for code, name in watchlist.items()}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                if result["group"] == "A": scan_a.append(result["data"])
                else: scan_b.append(result["data"])
            
    return {
        "market_info": {"is_good": is_good_market, "text": market_text},
        "scan_a": scan_a,
        "scan_b": scan_b
    }

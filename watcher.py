import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import time
import os

# AI連携モジュールのインポート（GitHub上にこれらのファイルが必要です）
from ai_analyzer import get_ai_analysis
from news_fetcher import fetch_recent_news

JST = timezone(timedelta(hours=9))

WATCH_TICKERS = {
    "7203": "トヨタ自動車", "6758": "ソニーグループ", "8306": "三菱UFJ Fg", "9984": "ソフトバンクG", 
    "6861": "キーエンス", "8035": "東京エレクトロン", "9432": "NTT", "8058": "三菱商事", 
    "7974": "任天堂", "6146": "ディスコ", "4063": "信越化学工業", "8411": "みずほFg"
}

def generate_watch_comment(signals, rsi, position, ma25_trend, vol_ratio):
    """【APIキー未設定時のフォールバック用】従来の定型文エンジン"""
    comment = ""
    if "⚠️ [天井警戒型]" in "".join(signals):
        comment += "【🚨天井警戒】直近高値付近で上値が重く反落（ダブルトップ形成の兆し）しており、RSIも過熱圏から下落に転じました。急な調整下落リスクが高まっています。\n"
    elif "🔄 [底打ち確認型]" in "".join(signals):
        comment += "【🔄底打ち確認】直近安値を割らずに反発し、さらに5日移動平均線（MA5）を明確に上抜けました！「落ちるナイフ」のダマシを回避したこの条件の過去勝率は「50.9%（平均+0.05%）」に改善しており、下落トレンドからの転換を狙う打診買いの候補となります。\n"
    elif "🟢 [押し目拾い型]" in "".join(signals):
        comment += "【🎯押し目拾い】主要な移動平均線（75日/200日）の強固なサポートライン付近まで調整し、本日反発を見せました。過去の統計上、この条件達成時の5日後勝率は「52.1%（平均+0.32%）」と最も安定しており、順張りの絶好のエントリーポイントです。\n"
    
    if "🌟 ゴールデンクロス発生" in signals:
        comment += "中期線(MA25)が長期線(MA75)を上抜けるゴールデンクロスも発生し、中長期的な上昇トレンドの形成を後押ししています。"
    elif "⚠️ デッドクロス発生" in signals:
        comment += "デッドクロスが発生しており、相場の地合いは悪化傾向です。"
    
    if not comment:
        if position == "200日線上":
            comment += "【順張り継続】200日線上で推移しており、基本的には上目線です。" + ("MA25も上向きで強い買い意欲を感じます。" if ma25_trend == "UP" else "ただし短期MAが下向きで、日柄調整の段階にあります。")
        else:
            comment += "【下落トレンド中】200日線の下で上値の重い展開です。" + ("底打ちの明確なサイン（MA5上抜け等）が出るまで様子見が賢明です。" if ma25_trend == "DOWN" else "短期MAが上向きに転じており、反転の初動の可能性があります。")

    if type(rsi) != str:
        if rsi >= 75 and "⚠️ [天井警戒型]" not in "".join(signals):
            comment += f" ただしRSI={rsi}と短期的な過熱サインが点灯中。高値掴みには注意してください。"
            
    return comment

def process_watch_ticker(code, name, start_str, end_str, api_key):
    max_retries = 3
    base_wait = 2

    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 200:
                return {"code": code, "name": name, "error": True, "error_msg": "データ不足（新規上場など）"}
                
            df.index = df.index.tz_localize(None)
            
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA25'] = df['Close'].rolling(window=25).mean()
            df['MA75'] = df['Close'].rolling(window=75).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            
            df['High_20'] = df['High'].rolling(window=20).max().shift(1)
            df['Low_20'] = df['Low'].rolling(window=20).min().shift(1)
            
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = int(latest['Close'])
            price_diff = int(latest['Close'] - prev['Close'])
            rsi = round(latest['RSI'], 1)
            prev_rsi = round(prev['RSI'], 1) if pd.notna(prev['RSI']) else rsi
            ma200 = latest['MA200']
            
            rsi_diff = rsi - prev_rsi
            if rsi_diff > 2:
                rsi_trend = f"RSI 上昇 (+{round(rsi_diff, 1)})"
            elif rsi_diff < -2:
                rsi_trend = f"RSI 低下 ({round(rsi_diff, 1)})"
            else:
                rsi_trend = "RSI 横ばい"

            vol_avg20 = df['Volume'].rolling(window=20).mean().iloc[-2]
            vol_latest = latest['Volume']
            vol_comment = ""
            vol_ratio = 1.0
            if vol_avg20 > 0 and not pd.isna(vol_avg20):
                vol_ratio = vol_latest / vol_avg20
                if vol_ratio >= 2.0:
                    vol_comment = f"急増 ({round(vol_ratio, 1)}倍) "
                elif vol_ratio <= 0.5:
                    vol_comment = f"急減 ({round(vol_ratio, 1)}倍) "
            
            vol_text = f"{vol_comment}{vol_latest/10000:.1f}万株" if vol_latest < 100000000 else f"{vol_comment}{vol_latest/100000000:.1f}億株"

            position = "200日線上" if price >= ma200 else "200日線下"
            ma25_trend = "UP" if latest['MA25'] > prev['MA25'] else "DOWN"

            signals = []
            is_yosen = latest['Close'] > latest['Open']
            is_insen = latest['Close'] < latest['Open']
            
            if pd.notna(latest['High_20']):
                if latest['High'] >= latest['High_20'] * 0.97 and is_insen and prev_rsi >= 65 and rsi < prev_rsi:
                    signals.append("⚠️ [天井警戒型] ダブルトップ警戒")

            if pd.notna(latest['Low_20']) and pd.notna(latest['MA5']) and pd.notna(latest['MA25']):
                if (latest['Low'] <= latest['Low_20'] * 1.05 and 
                    latest['Low'] >= latest['Low_20'] and 
                    is_yosen and 
                    rsi <= 30 and 
                    latest['Close'] < latest['MA25'] * 0.95 and 
                    latest['Close'] > latest['MA5']):
                    signals.

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

WATCH_TICKERS = {
    "7203": "トヨタ自動車", "6758": "ソニーグループ", "8306": "三菱UFJ Fg", "9984": "ソフトバンクG", 
    "6861": "キーエンス", "8035": "東京エレクトロン", "9432": "NTT", "8058": "三菱商事", 
    "7974": "任天堂", "6146": "ディスコ", "4063": "信越化学工業", "8411": "みずほFg"
}

def analyze_watch_tickers(target_date_str=None):
    results = []
    
    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').replace(tzinfo=JST)
        end = target_date + timedelta(hours=23, minutes=59)
    else:
        end = datetime.now(JST)

    # 💡【修正】カレンダー500日分（約340営業日）を取得し、MA200を確実に計算させる
    start = end - timedelta(days=500)
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')

    for code, name in WATCH_TICKERS.items():
        try:
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 200:
                results.append({"code": code, "name": name, "error": True, "error_msg": "データ不足（新規上場など）"})
                continue
                
            df.index = df.index.tz_localize(None)
            
            df['MA25'] = df['Close'].rolling(window=25).mean()
            df['MA75'] = df['Close'].rolling(window=75).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = int(latest['Close'])
            price_diff = int(latest['Close'] - prev['Close'])
            rsi = round(latest['RSI'], 1)
            ma200 = latest['MA200']
            
            position = "200日線上" if price >= ma200 else "200日線下"

            signals = []
            if prev['MA25'] <= prev['MA75'] and latest['MA25'] > latest['MA75']:
                signals.append("🌟 ゴールデンクロス発生")
            if prev['MA25'] >= prev['MA75'] and latest['MA25'] < latest['MA75']:
                signals.append("⚠️ デッドクロス発生")
            if price > ma200 and latest['Low'] <= ma200 * 1.03 and price_diff > 0:
                signals.append("🟩 200日線付近で反発")

            df_clean = df.dropna(subset=['Open', 'High', 'Low', 'Close']).tail(120)
            history_data = []
            for date_index, row in df_clean.iterrows():
                history_data.append({
                    "time": date_index.strftime('%Y-%m-%d'),
                    "open": float(row['Open']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "close": float(row['Close']),
                    "volume": float(row['Volume']),
                    "ma25": float(row['MA25']) if pd.notna(row['MA25']) else None,
                    "ma75": float(row['MA75']) if pd.notna(row['MA75']) else None,
                    "ma200": float(row['MA200']) if pd.notna(row['MA200']) else None
                })

            results.append({
                "code": code, "name": name, "price": price, "price_diff": price_diff,
                "rsi": rsi, "position": position, "signals": signals,
                "history_data": history_data, "error": False
            })
        except Exception as e:
            results.append({"code": code, "name": name, "error": True, "error_msg": str(e)})
            
    return results

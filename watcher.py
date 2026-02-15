import pandas as pd
import pandas_datareader.data as web
from datetime import datetime, timedelta, timezone
JST = timezone(timedelta(hours=9))

WATCH_LIST = {
    "7203": "トヨタ自動車", "6758": "ソニーグループ", "8411": "みずほFG",
    "5020": "ENEOS", "8058": "三菱商事", "7011": "三菱重工業",
    "9984": "ソフトバンクG", "6146": "ディスコ", "6857": "アドバンテスト",
    "8306": "三菱UFJ"
}

def analyze_watch_tickers():
    results = []
    end = datetime.now(JST)
    start = end - timedelta(days=400) 
    
    for code, name in WATCH_LIST.items():
        try:
            df = web.DataReader(f"{code}.JP", "stooq", start, end).sort_index()
            if len(df) < 200:
                results.append({"code": code, "name": name, "error": True, "error_msg": f"データ不足({len(df)}件)"})
                continue
            
            latest = df.iloc[-1]
            sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            position = "200日線上" if latest['Close'] >= sma200 else "200日線下"
            
            # 基本データの作成
            item_data = {
                "code": code, "name": name, "price": int(latest['Close']),
                "position": position, "rsi": round(rsi, 1), "error": False
            }

            # ---------------------------------------------------------
            # 【修正】Step 4-A-1: 7203(トヨタ)限定（鉄壁のデータクリーニング）
            # ---------------------------------------------------------
            if code == "7203":
                # 1. 念のため明示的に古い順（昇順）に並べ替え
                df_clean = df.sort_index(ascending=True)
                # 2. 重複した日付を排除（最後を残す）
                df_clean = df_clean[~df_clean.index.duplicated(keep='last')].copy()
                # 3. 出来高の欠損(NaN)は「0」で埋める（エラー回避）
                df_clean['Volume'] = df_clean['Volume'].fillna(0)
                # 4. 価格データ(OHLC)が欠損している異常な日だけを除外
                df_clean = df_clean.dropna(subset=['Open', 'High', 'Low', 'Close'])
                
                df_120 = df_clean.tail(120)
                history_data = []
                for date_index, row in df_120.iterrows():
                    history_data.append({
                        "time": date_index.strftime('%Y-%m-%d'),
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": float(row['Volume'])
                    })
                item_data["history_data"] = history_data
            # ---------------------------------------------------------
            results.append(item_data)

        except Exception:
            results.append({"code": code, "name": name, "error": True, "error_msg": "取得スキップ"})
            
    return results

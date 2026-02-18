import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

WATCH_LIST = {
    "7203": "トヨタ自動車", "6758": "ソニーグループ", "8411": "みずほFG",
    "5020": "ENEOS", "8058": "三菱商事", "7011": "三菱重工業",
    "9984": "ソフトバンクG", "6146": "ディスコ", "6857": "アドバンテスト",
    "8306": "三菱UFJ"
}

def analyze_watch_tickers(target_date_str=None):
    results = []
    
    # --- 【追加】タイムマシン・ロジック ---
    if target_date_str:
        # 指定された日の 23:59 を仮想の「現在」とする
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').replace(tzinfo=JST)
        end = target_date + timedelta(hours=23, minutes=59)
    else:
        end = datetime.now(JST)
    # ------------------------------------

    start = end - timedelta(days=400) 
    
    # yfinance用に文字列の日付を用意（endは含まれないため+1日する）
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    
    for code, name in WATCH_LIST.items():
        try:
            # 【換装】yfinanceからデータを取得 (コード末尾は .T)
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 200:
                results.append({"code": code, "name": name, "error": True, "error_msg": f"データ不足({len(df)}件)"})
                continue
            
            # yfinance特有のタイムゾーン情報を削除して既存システムと合わせる
            df.index = df.index.tz_localize(None)

            # --- 【追加】移動平均線の計算 ---
            df['MA25'] = df['Close'].rolling(window=25).mean()
            df['MA75'] = df['Close'].rolling(window=75).mean()
            # ------------------------------
            
            latest = df.iloc[-1]
            sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            position = "200日線上" if latest['Close'] >= sma200 else "200日線下"
            
            item_data = {
                "code": code, "name": name, "price": int(latest['Close']),
                "position": position, "rsi": round(rsi, 1), "error": False
            }

            # 全監視銘柄へチャート用データを展開
            df_clean = df.sort_index(ascending=True)
            df_clean = df_clean[~df_clean.index.duplicated(keep='last')].copy()
            df_clean['Volume'] = df_clean['Volume'].fillna(0)
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
                    "volume": float(row['Volume']),
                    # --- 【追加】MAデータの格納 ---
                    "ma25": float(row['MA25']) if pd.notna(row['MA25']) else None,
                    "ma75": float(row['MA75']) if pd.notna(row['MA75']) else None
                    # ----------------------------
                })
            item_data["history_data"] = history_data

            results.append(item_data)

        except Exception:
            results.append({"code": code, "name": name, "error": True, "error_msg": "取得スキップ"})
            
    return results

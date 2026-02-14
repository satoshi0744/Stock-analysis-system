import pandas_datareader.data as web
from datetime import datetime, timedelta

# サトシさんの監視銘柄（いつでも追加・変更可能）
WATCH_LIST = {
    "7203": "トヨタ自動車",
    "6758": "ソニーグループ",
    "8411": "みずほFG",
    "5020": "ENEOS",
    "8058": "三菱商事",
    "7011": "三菱重工業",
    "9984": "ソフトバンクG",
    "6146": "ディスコ",
    "6857": "アドバンテスト",
    "8306": "三菱UFJ"
}

def analyze_watch_tickers():
    results = []
    end = datetime.now()
    # 【修正】営業日200日を確実に確保するため、過去400日分を取得する
    start = end - timedelta(days=400) 
    
    for code, name in WATCH_LIST.items():
        try:
            # Stooqからデータ取得
            df = web.DataReader(f"{code}.JP", "stooq", start, end).sort_index()
            if len(df) < 200:
                results.append(f"・{code} {name}: データ不足(取得件数: {len(df)}件)")
                continue
            
            latest = df.iloc[-1]
            sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            # RSI(14日)計算
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            position = "200日線上" if latest['Close'] >= sma200 else "200日線下"
            
            results.append(f"・{code} {name}: {int(latest['Close']):,}円 ({position} / RSI: {rsi:.1f})")
            
        except Exception as e:
            results.append(f"・{code} {name}: データ取得スキップ")
            
    return results

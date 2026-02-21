import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

SCAN_UNIVERSE = {
    "7203": "トヨタ自動車", "6758": "ソニーG", "8306": "三菱UFJ", "9984": "ソフトバンクG", "6861": "キーエンス", "8035": "東エレク", "9432": "NTT", "8058": "三菱商事", "7974": "任天堂", "6146": "ディスコ",
    "4063": "信越化学", "8411": "みずほ", "8316": "三井住友", "6920": "レーザーテック", "4568": "第一三共", "6857": "アドバンテスト", "7011": "三菱重工", "6098": "リクルート", "6501": "日立", "8002": "丸紅",
    "8031": "三井物産", "4502": "武田薬品", "3382": "セブン&アイ", "4519": "中外製薬", "6902": "デンソー", "8766": "東京海上", "8053": "住友商事", "9433": "KDDI", "6702": "富士通", "5108": "ブリヂストン",
    "6503": "三菱電機", "6981": "村田製作所", "4543": "テルモ", "4503": "アステラス", "4901": "富士フイルム", "8591": "オリックス", "2914": "JT", "9022": "JR東海", "6954": "ファナック", "7741": "HOYA",
    "8801": "三井不動産", "1925": "大和ハウス", "2502": "アサヒ", "6752": "パナソニック", "6723": "ルネサス", "9020": "JR東日本", "8802": "三菱地所", "7267": "ホンダ", "6301": "コマツ", "4452": "花王",
    "7269": "スズキ", "5020": "ENEOS", "1928": "積水ハウス", "8604": "野村HD", "9101": "日本郵船", "3402": "東レ", "6594": "ニデック", "2802": "味の素", "7201": "日産自動車", "9104": "商船三井",
    "5401": "日本製鉄", "6971": "京セラ", "7751": "キヤノン", "6645": "オムロン", "7309": "シマノ", "3407": "旭化成", "4911": "資生堂", "9202": "ANA", "9735": "セコム", "9009": "京成電鉄",
    "7270": "SUBARU", "1801": "大成建設", "6367": "ダイキン", "5802": "住友電工", "2503": "キリン", "5713": "住友鉱山", "8725": "MS&AD", "3281": "GLP", "9021": "JR西日本", "8309": "三井住友トラスト",
    "2413": "エムスリー", "1802": "大林組", "8267": "イオン", "4523": "エーザイ", "1812": "鹿島建設", "5332": "TOTO", "1911": "住友林業", "4507": "塩野義製薬", "8795": "T&D", "9434": "ソフトバンク",
    "8630": "SOMPO", "3092": "ZOZO", "4704": "トレンドマイクロ", "7012": "川崎重工", "6762": "TDK", "6506": "安川電機", "8252": "丸井", "4188": "三菱ケミカル", "4661": "OLC", "7259": "アイシン"
}

def scan_b_type(target_date_str=None):
    results = []
    
    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').replace(tzinfo=JST)
        end = target_date + timedelta(hours=23, minutes=59)
    else:
        end = datetime.now(JST)

    start = end - timedelta(days=300) 
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    
    for code, name in SCAN_UNIVERSE.items():
        try:
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 200: 
                continue
                
            df.index = df.index.tz_localize(None)
            
            # 移動平均線の計算
            df['MA25'] = df['Close'].rolling(window=25).mean()
            df['MA75'] = df['Close'].rolling(window=75).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            vol_avg20 = df['Volume'].rolling(window=20).mean().iloc[-2]
            if vol_avg20 == 0 or pd.isna(vol_avg20): 
                continue
                
            vol_ratio = latest['Volume'] / vol_avg20
            
            # シグナル判定（出来高急増＋上昇）
            if vol_ratio >= 2.5 and latest['Close'] > prev['Close']:
                price_diff = int(latest['Close'] - prev['Close'])
                price = int(latest['Close'])
                ma200 = latest['MA200']
                
                # 💡 【追加】客観的イベントシグナルの検知
                signals = [f"🔥 出来高急増 ({round(vol_ratio, 1)}倍)"]
                
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
                    "code": code, 
                    "name": name, 
                    "price": price, 
                    "vol_ratio": round(vol_ratio, 1),
                    "price_diff": price_diff,
                    "signals": signals, # バッジ用データを追加
                    "history_data": history_data
                })
        except Exception:
            pass
    return results

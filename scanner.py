import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

SCAN_UNIVERSE = [
    "7203", "6758", "8306", "9984", "6861", "8035", "9432", "8058", "7974", "6146",
    "4063", "8411", "8316", "6920", "4568", "6857", "7011", "6098", "6501", "8002",
    "8031", "4502", "3382", "4519", "6902", "8766", "8053", "9433", "6702", "5108",
    "6503", "6981", "4543", "4503", "4901", "8591", "2914", "9022", "6954", "7741",
    "8801", "1925", "2502", "6752", "6723", "9020", "8802", "7267", "6301", "4452",
    "7269", "5020", "1928", "8604", "9101", "3402", "6594", "2802", "7201", "9104",
    "5401", "6971", "7751", "6645", "7309", "3407", "4911", "9202", "9735", "9009",
    "7270", "1801", "6367", "5802", "2503", "5713", "8725", "3281", "9021", "8309",
    "2413", "1802", "8267", "4523", "1812", "5332", "1911", "4507", "8795", "9434",
    "8630", "3092", "4704", "7012", "6762", "6506", "8252", "4188", "4661", "7259"
]

def scan_b_type():
    results = []
    end = datetime.now(JST)
    start = end - timedelta(days=60) 
    
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    
    for code in SCAN_UNIVERSE:
        try:
            # 【換装】yfinanceからデータを取得
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 25: 
                continue
                
            df.index = df.index.tz_localize(None)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            vol_avg20 = df['Volume'].rolling(window=20).mean().iloc[-2]
            
            if vol_avg20 == 0 or pd.isna(vol_avg20): 
                continue
                
            vol_ratio = latest['Volume'] / vol_avg20
            
            if vol_ratio >= 2.5 and latest['Close'] > prev['Close']:
                results.append({"code": code, "price": int(latest['Close']), "vol_ratio": round(vol_ratio, 1)})
        except Exception:
            pass
    return results

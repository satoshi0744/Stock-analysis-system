import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
import concurrent.futures
import time
import json

JST = timezone(timedelta(hours=9))

def load_watchlist():
    """GitHub上の最新のwatchlist.jsonを読み込む。失敗時は勝手なスキャンを防ぐため空を返す。"""
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Watchlist load error: {e}")
        return {}

def generate_ai_comment(group, vol_ratio, is_yosen, is_above_ma200, rsi, is_breakout):
    """銘柄の各種データから生きたAIコメントを生成するエンジン"""
    comment = ""
    if group == "A" and is_breakout:
        comment += f"【🚀上昇加速型】過去20日間の高値を明確にブレイクアウト！出来高も{vol_ratio}倍と大口の買いが明白です。過去の統計上、この条件達成時の5日後勝率は「51.4%（平均+0.71%）」であり、明日の寄り付きでの順張りエントリーに最も高い優位性が確認されています。"
    elif group == "A":
        comment += f"【本命シグナル】出来高急増（{vol_ratio}倍）を伴い前日高値を抜けました。200日線上の強い上昇トレンドに乗る形ですが、直近高値の更新（完全なブレイクアウト）には至っていません。"
    else:
        comment += f"【動意確認】出来高は{vol_ratio}倍と資金流入が見られますが、"
        if not is_yosen:
            comment += "前日高値を抜けきれず上値の重さが残ります。"
        elif not is_above_ma200:
            comment += "200日線の下にあり、長期トレンドは依然として下落・調整局面です。"
        else:
            comment += "地合い等のフィルターにより本命からは外れました。"

    if type(rsi) != str:
        if rsi >= 75:
            comment += f" ただし、RSIが{rsi}と短期的な過熱感を示しており、高値掴みには警戒が必要です。"
        elif rsi <= 30:
            comment += f" RSIは{rsi}と売られすぎ水準にあり、自律反発に優位性が見込めます。"
        elif group == "A" and 40 <= rsi <= 70:
            comment += f" RSIも{rsi}と過熱感はなく、ここから上値余地が十分に狙える理想的な状態です。"

    return comment

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
        
        # 💡 厳格判定：MAを上回っていても、本日がマイナス引けなら「調整局面」とする
        if is_above_ma200 and is_above_ma25 and is_above_ma5 and not is_falling:
            is_good = True
            text = "🟩 良好 (短期・中期・長期すべて上向き)"
        elif is_above_ma200 and (not is_above_ma25 or is_falling):
            is_good = False
            text = "🟨 調整局面 (日経平均 続落・短期トレンド崩れ)"
        else:
            is_good = False
            text = "⚠️ 警戒 (日経平均 200日線下)"
            
        return is_good, text
    except:
        return False, "データ取得エラー"

def process_ticker(code, name, start_str, end_str, is_good_market):
    max_retries = 3
    base_wait = 2

    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(f"{code}.T")
            df = ticker.history(start=start_str, end=end_str)
            
            if df.empty or len(df) < 200: 
                return None
                
            df.index = df.index.tz_localize(None)
            df['MA25'] = df['Close'].rolling(window=25).mean()
            df['MA75'] = df['Close'].rolling(window=75).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            
            df['High_20'] = df['High'].rolling(window=20).max().shift(1)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            vol_avg20 = df['Volume'].rolling(window=20).mean().iloc[-2]
            if vol_avg20 == 0 or pd.isna(vol_avg20): 
                return None
                
            vol_ratio = latest['Volume'] / vol_avg20
            
            if vol_ratio >= 2.5:
                price_diff = int(latest['Close'] - prev['Close'])
                price = int(latest['Close'])
                ma200 = latest['MA200']
                
                is_yosen = latest['Close'] > prev['High'] 
                is_above_ma200 = price > ma200
                is_breakout = latest['Close'] > latest['High_20'] if pd.notna(latest['High_20']) else False
                
                signals = [f"🔥 出来高 ({round(vol_ratio, 1)}倍)"]
                
                if is_breakout: signals.append("👑 [🚀 上昇加速型] 20日高値更新")
                elif is_yosen: signals.append("📈 前日高値抜け")
                if is_above_ma200: signals.append("🟩 200日線上")
                
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

                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))

                rsi = round(df.iloc[-1]['RSI'], 1)
                prev_rsi = round(df.iloc[-2]['RSI'], 1) if pd.notna(df.iloc[-2]['RSI']) else rsi
                rsi_diff = rsi - prev_rsi

                if rsi_diff > 2:
                    rsi_trend = f"RSI 上昇 (+{round(rsi_diff, 1)})"
                elif rsi_diff < -2:
                    rsi_trend = f"RSI 低下 ({round(rsi_diff, 1)})"
                else:
                    rsi_trend = "RSI 横ばい"

                vol_latest = latest['Volume']
                if vol_ratio >= 2.0:
                    vol_comment = f"急増 ({round(vol_ratio, 1)}倍) "
                elif vol_ratio <= 0.5:
                    vol_comment = f"急減 ({round(vol_ratio, 1)}倍) "
                else:
                    vol_comment = ""
                
                vol_text = f"{vol_comment}{vol_latest/10000:.1f}万株" if vol_latest < 100000000 else f"{vol_comment}{vol_latest/100000000:.1f}億株"

                # 💡 底打ちロジック（RSI30以下）
                if rsi <= 30 and latest['Close'] < latest['MA25'] * 0.95 and latest['Close'] > latest['Open']:
                    signals.append("🔄 [底打ち確認型] RSI低位・MA25乖離")

                group = "A" if (is_good_market and is_yosen and is_above_ma200 and is_breakout) or ("底打ち" in str(signals)) else "B"
                ai_comment = generate_ai_comment(group, round(float(vol_ratio), 1), is_yosen, is_above_ma200, rsi, is_breakout)

                item_data = {
                    "code": code, "name": name, "price": price, "vol_ratio": round(float(vol_ratio), 1),
                    "price_diff": price_diff, "signals": signals, "history_data": history_data,
                    "position": "200日線上" if is_above_ma200 else "200日線下",
                    "rsi": rsi, "rsi_trend": rsi_trend, "vol_text": vol_text, "ai_comment": ai_comment
                }
                
                return {"group": group, "data": item_data}

            return None

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(base_wait * (2 ** attempt))
            else:
                return None

def scan_b_type(target_date_str=None):
    # 💡 常に watchlist.json を読み込んでスキャン対象とする
    watchlist = load_watchlist()
    
    # リストが空（エラー等）の場合は安全に終了する
    if not watchlist:
        return {"market_info": {"is_good": False, "text": "監視リスト読込エラー"}, "scan_a": [], "scan_b": []}

    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').replace(tzinfo=JST)
        end = target_date + timedelta(hours=23, minutes=59)
    else:
        end = datetime.now(JST)

    start = end - timedelta(days=500) 
    start_str = start.strftime('%Y-%m-%d')
    end_str = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    
    is_good_market, market_text = check_market_trend(start_str, end_str)
    
    scan_a = []
    scan_b = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_ticker, code, name, start_str, end_str, is_good_market): code for code, name in watchlist.items()}
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                if result["group"] == "A":
                    scan_a.append(result["data"])
                elif result["group"] == "B":
                    scan_b.append(result["data"])
            
    return {
        "market_info": {"is_good": is_good_market, "text": market_text},
        "scan_a": scan_a,
        "scan_b": scan_b
    }

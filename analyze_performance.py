import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from scanner import SCAN_UNIVERSE
from price_store import get_stock_df
import concurrent.futures
import time

JST = timezone(timedelta(hours=9))

def process_backtest_ticker(code, nk_data, start_str, end_str):
    max_retries = 3
    base_wait = 2

    stats = {
        "BREAKOUT": {"trades": 0, "wins": 0, "return_pct": 0.0},
        "PULLBACK": {"trades": 0, "wins": 0, "return_pct": 0.0},
        "REVERSAL": {"trades": 0, "wins": 0, "return_pct": 0.0}
    }

    for attempt in range(max_retries):
        try:
            df = get_stock_df(code)
            if df.empty or len(df) < 250:
                return stats

            df.index = df.index.tz_localize(None)
            
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA25'] = df['Close'].rolling(window=25).mean()  # 💡 MA25を追加
            df['MA75'] = df['Close'].rolling(window=75).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            df['Vol_Avg20'] = df['Volume'].rolling(window=20).mean().shift(1)
            df['Vol_Ratio'] = df['Volume'] / df['Vol_Avg20']
            df['Prev_High'] = df['High'].shift(1)
            
            df['High_20'] = df['High'].rolling(window=20).max().shift(1)
            df['Low_20'] = df['Low'].rolling(window=20).min().shift(1)
            
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            df = df.join(nk_data[['Is_Good_Market']], how='left')
            df['Is_Good_Market'] = df['Is_Good_Market'].ffill()

            is_yosen = df['Close'] > df['Open']
            
            m_breakout = (
                (df['Is_Good_Market'] == True) & 
                (df['Vol_Ratio'] >= 2.5) & 
                (df['Close'] > df['Prev_High']) & 
                (df['Close'] > df['MA200']) &
                (df['Close'] > df['High_20'])
            )
            
            # 💡 底打ち確認型の超・厳格化
            m_reversal = (
                (df['Low'] <= df['Low_20'] * 1.05) & 
                (df['Low'] >= df['Low_20']) & 
                is_yosen & 
                (df['RSI'] <= 30) &
                (df['Close'] < df['MA25'] * 0.95) &
                (df['Close'] > df['MA5'])
            )
            
            ma75_supp = (df['Low'] <= df['MA75'] * 1.03) & (df['Close'] > df['MA75'])
            ma200_supp = (df['Low'] <= df['MA200'] * 1.03) & (df['Close'] > df['MA200'])
            m_pullback = (ma75_supp | ma200_supp) & is_yosen & (~m_reversal)

            signal_indices = df[m_breakout | m_pullback | m_reversal].index

            for signal_date in signal_indices:
                idx = df.index.get_loc(signal_date)
                
                if idx + 5 < len(df):
                    buy_price = df.iloc[idx + 1]['Open']
                    sell_price = df.iloc[idx + 5]['Close']
                    
                    if pd.isna(buy_price) or pd.isna(sell_price) or buy_price == 0:
                        continue

                    trade_return = (sell_price - buy_price) / buy_price * 100
                    is_win = 1 if trade_return > 0 else 0
                    
                    if m_breakout.loc[signal_date]:
                        stats["BREAKOUT"]["trades"] += 1
                        stats["BREAKOUT"]["wins"] += is_win
                        stats["BREAKOUT"]["return_pct"] += trade_return
                        
                    if m_pullback.loc[signal_date]:
                        stats["PULLBACK"]["trades"] += 1
                        stats["PULLBACK"]["wins"] += is_win
                        stats["PULLBACK"]["return_pct"] += trade_return
                        
                    if m_reversal.loc[signal_date]:
                        stats["REVERSAL"]["trades"] += 1
                        stats["REVERSAL"]["wins"] += is_win
                        stats["REVERSAL"]["return_pct"] += trade_return

            return stats

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(base_wait * (2 ** attempt))
            else:
                return stats

def analyze():
    end_date = datetime.now(JST)
    start_date = end_date - timedelta(days=700)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        nk = get_stock_df("^N225")
        nk.index = nk.index.tz_localize(None)
        nk['MA200'] = nk['Close'].rolling(window=200).mean()
        nk['Is_Good_Market'] = nk['Close'] > nk['MA200']
    except Exception as e:
        print(f"日経平均データの取得に失敗: {e}")
        return

    agg_stats = {
        "BREAKOUT": {"trades": 0, "wins": 0, "return_pct": 0.0},
        "PULLBACK": {"trades": 0, "wins": 0, "return_pct": 0.0},
        "REVERSAL": {"trades": 0, "wins": 0, "return_pct": 0.0}
    }

    print("🔍 スイングトレード（5日後決済）の戦術別バックテストを開始します...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_backtest_ticker, code, nk, start_str, end_str): code for code in SCAN_UNIVERSE.keys()}
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            for strategy in agg_stats.keys():
                agg_stats[strategy]["trades"] += res[strategy]["trades"]
                agg_stats[strategy]["wins"] += res[strategy]["wins"]
                agg_stats[strategy]["return_pct"] += res[strategy]["return_pct"]

    total_trades = sum(agg_stats[s]["trades"] for s in agg_stats)
    total_wins = sum(agg_stats[s]["wins"] for s in agg_stats)
    total_return = sum(agg_stats[s]["return_pct"] for s in agg_stats)
    
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    overall_avg_return = (total_return / total_trades) if total_trades > 0 else 0.0

    summary = {
        "total_signals": total_trades,
        "win_rate": round(overall_win_rate, 2),
        "avg_return": round(overall_avg_return, 2),
        "expectancy": round(overall_avg_return, 2),
        "strategies": {}
    }

    strategy_names = {
        "BREAKOUT": "🚀 上昇加速型",
        "PULLBACK": "🟢 押し目拾い型",
        "REVERSAL": "🔄 底打ち確認型"
    }

    for strategy, data in agg_stats.items():
        st_trades = data["trades"]
        st_win_rate = (data["wins"] / st_trades * 100) if st_trades > 0 else 0.0
        st_avg_return = (data["return_pct"] / st_trades) if st_trades > 0 else 0.0
        
        summary["strategies"][strategy] = {
            "total_signals": st_trades,
            "win_rate": round(st_win_rate, 2),
            "avg_return": round(st_avg_return, 2)
        }
        
        display_name = strategy_names[strategy]
        print(f"[{display_name}] 回数: {st_trades} | 勝率: {round(st_win_rate, 1)}% | 平均リターン: {round(st_avg_return, 2)}%")

    print(f"✅ 全テスト完了: 合計トレード {total_trades}回 / 全体勝率 {round(overall_win_rate, 2)}%")

    os.makedirs("public", exist_ok=True)
    with open("public/performance_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    analyze()

import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from scanner import SCAN_UNIVERSE

JST = timezone(timedelta(hours=9))

def analyze():
    # 過去約2年分（約500営業日）のデータを取得してテストする
    end_date = datetime.now(JST)
    start_date = end_date - timedelta(days=700)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')

    # まず日経平均（地合い）のデータを取得
    try:
        nk = yf.Ticker("^N225").history(start=start_str, end=end_str)
        nk.index = nk.index.tz_localize(None)
        nk['MA200'] = nk['Close'].rolling(window=200).mean()
        nk['Is_Good_Market'] = nk['Close'] > nk['MA200']
    except Exception as e:
        print(f"日経平均データの取得に失敗: {e}")
        return

    total_trades = 0
    winning_trades = 0
    total_return_pct = 0.0

    print("🔍 スイングトレード（5日後決済）のバックテストを開始します...")

    for code in SCAN_UNIVERSE.keys():
        try:
            df = yf.Ticker(f"{code}.T").history(start=start_str, end=end_str)
            if df.empty or len(df) < 250:
                continue

            df.index = df.index.tz_localize(None)
            df['MA200'] = df['Close'].rolling(window=200).mean()
            df['Vol_Avg20'] = df['Volume'].rolling(window=20).mean().shift(1)
            df['Vol_Ratio'] = df['Volume'] / df['Vol_Avg20']
            df['Prev_High'] = df['High'].shift(1)
            
            # 日経平均の地合いデータを結合
            df = df.join(nk[['Is_Good_Market']], how='left')
            df['Is_Good_Market'] = df['Is_Good_Market'].ffill()

            # A群の条件判定（シグナル発生日を探す）
            # 条件: 出来高2.5倍以上 ＆ 終値が前日高値超え(陽線) ＆ 200日線上 ＆ 地合い良好
            signals = df[
                (df['Vol_Ratio'] >= 2.5) & 
                (df['Close'] > df['Prev_High']) & 
                (df['Close'] > df['MA200']) & 
                (df['Is_Good_Market'] == True)
            ]

            # 各シグナルについて、仮想トレードを実行
            for signal_date, signal_row in signals.iterrows():
                # シグナル発生日のインデックス番号を取得
                idx = df.index.get_loc(signal_date)
                
                # 翌日(idx+1)に買い、5日後(idx+5)に売る
                # データが最後まで（5日後まで）存在するかチェック
                if idx + 5 < len(df):
                    buy_price = df.iloc[idx + 1]['Open']
                    sell_price = df.iloc[idx + 5]['Close']
                    
                    if pd.isna(buy_price) or pd.isna(sell_price) or buy_price == 0:
                        continue

                    trade_return = (sell_price - buy_price) / buy_price * 100
                    
                    total_trades += 1
                    total_return_pct += trade_return
                    if trade_return > 0:
                        winning_trades += 1

        except Exception as e:
            continue

    # 結果の集計
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    avg_return = (total_return_pct / total_trades) if total_trades > 0 else 0.0
    expectancy = avg_return # 単純な期待値（1トレードあたりの平均リターン）

    summary = {
        "total_signals": total_trades,
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "expectancy": round(expectancy, 2)
    }

    print(f"✅ バックテスト完了: トレード回数 {total_trades}回 / 勝率 {round(win_rate, 2)}%")

    os.makedirs("public", exist_ok=True)
    with open("public/performance_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    analyze()

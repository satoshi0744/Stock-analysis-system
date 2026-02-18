import os
import json
import time
import yfinance as yf
from datetime import datetime, timedelta, timezone
from watcher import analyze_watch_tickers
from scanner import scan_b_type

JST = timezone(timedelta(hours=9))
HISTORY_DIR = "public/history"

def get_trading_days(days_back):
    """7203(トヨタ)を基準に、過去の『実際の営業日』リストを取得する"""
    end = datetime.now(JST)
    start = end - timedelta(days=days_back * 2) # 祝日を加味して余裕を持って取得
    ticker = yf.Ticker("7203.T")
    df = ticker.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    
    if df.empty:
        return []
        
    df.index = df.index.tz_localize(None)
    dates = df.index.strftime('%Y-%m-%d').tolist()
    
    # 当日（今日）のデータは、日次の main.py に任せるため除外
    today_str = end.strftime('%Y-%m-%d')
    past_dates = [d for d in dates if d < today_str]
    
    return past_dates[-days_back:]

def run_backfill(days_back=10):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    trading_days = get_trading_days(days_back)
    
    print(f"--- バックフィル開始: 過去 {len(trading_days)} 営業日 ---")
    
    for date_str in trading_days:
        filepath = os.path.join(HISTORY_DIR, f"{date_str}.json")
        
        # 既に履歴が存在する場合はスキップ（既存の正常データを壊さない）
        if os.path.exists(filepath):
            print(f"⏩ スキップ: {date_str} (既に存在します)")
            continue
            
        print(f"⏳ 処理中: {date_str} ...", end="", flush=True)
        
        # 1. 指定日の監視銘柄データを取得
        watch_data = analyze_watch_tickers(date_str)
        
        # --- 🛡️ データの健全性チェック（GPT防衛線） ---
        # 取得したデータの「最新日付」が、本当に target_date と一致しているか検証
        is_valid = False
        for w in watch_data:
            if w["code"] == "7203" and not w["error"] and "history_data" in w:
                if len(w["history_data"]) > 0:
                    latest_history_date = w["history_data"][-1]["time"]
                    if latest_history_date == date_str:
                        is_valid = True
                break
        
        if not is_valid:
            print(f" ⚠️ データ不整合（非営業日またはAPI遅延）のため保存をスキップ")
            continue
            
        # 2. 指定日のスキャンデータを取得
        scan_data = scan_b_type(date_str)
        
        # 3. JSON保存（HTML等の公開ファイルは上書きせず、純粋な履歴のみ生成）
        report_dict = {
            "updated_at": f"{date_str} 19:45 (Backfill)",
            "date": date_str,
            "watch_data": watch_data,
            "scan_data": scan_data
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
            
        print(f" ✅ 保存完了")
        time.sleep(2) # yfinanceへのAPIリクエスト過多（Rate Limit）を防ぐためのインターバル
        
    print("--- バックフィル完了 ---")
    print("💡 次回の main.py 実行時、performance_tracker がこれらの過去シグナルに対するリターンを自動計算します。")

if __name__ == "__main__":
    # 軽量バックフィルとして、とりあえず過去10営業日（約2週間分）を実行
    run_backfill(10)

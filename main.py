import os
import sys
import time
import json
import smtplib
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from scanner import scan_b_type
from watcher import analyze_watch_tickers
from report_generator import generate_files, load_previous_report

# 日本時間のタイムゾーン設定
JST = timezone(timedelta(hours=9))

# Windows等のcp932環境での絵文字出力エラー防止
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# 🚨【新規追加】APIキーを環境変数またはテキストファイルから読み込む
def load_api_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key and os.path.exists("api_key.txt"):
        with open("api_key.txt", "r", encoding="utf-8") as f:
            key = f.read().strip()
    return key

def send_email(text_body, subject=None):
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_PASSWORD")
    if not user or not pwd: return

    msg = MIMEMultipart()
    msg['Subject'] = subject if subject else f"投資戦略レポート [{datetime.now(JST).strftime('%m/%d')}]"
    msg['From'] = user
    msg['To'] = user
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(user, pwd)
        server.send_message(msg)
        server.quit()
    except Exception:
        pass

def get_last_processed_data_date():
    """既存の履歴ファイル（public/history/*.json）から直近レポートの株価データ基準日を取得する。"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(base_dir, "public", "history")
    if not os.path.exists(history_dir):
        history_dir = "public/history"
    if not os.path.exists(history_dir):
        return None
    files = sorted([f for f in os.listdir(history_dir) if f.endswith(".json")], reverse=True)
    for f_name in files:
        file_path = os.path.join(history_dir, f_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "data_date" in data:
                return data["data_date"]
            watch_data = data.get("watch_data", [])
            for w in watch_data:
                hist = w.get("history_data", [])
                if hist and "time" in hist[-1]:
                    return hist[-1]["time"]
        except Exception:
            continue
    return None

def get_unprocessed_market_dates():
    """yfinanceの7203.Tから直近営業日リストを取得し、前回処理済み日より後の未処理日付リストを返す。"""
    last_processed = get_last_processed_data_date()
    try:
        ticker = yf.Ticker("7203.T")
        df = ticker.history(period="15d")
        if df.empty:
            return [], "データプロバイダ（yfinance）からの取得失敗", None
        
        df = df.dropna(subset=['Close'])
        if df.empty:
            return [], "有効データなし", None
        
        df.index = df.index.tz_localize(None)
        all_dates = [idx.strftime('%Y-%m-%d') for idx in df.index]
        
        if not all_dates:
            return [], "営業日データなし", None

        latest_market_date = all_dates[-1]

        # 履歴が一切ない場合は最新日のみ
        if not last_processed:
            return [latest_market_date], f"初回実行（最新日: {latest_market_date}）", latest_market_date

        # 前回処理済み日付よりも新しい営業日データを抽出
        unprocessed = [d for d in all_dates if d > last_processed]

        if not unprocessed:
            return [], f"最新データ（{latest_market_date}）は既に前回レポート済みです（新データ未反映または休場日）。", latest_market_date

        return unprocessed, f"未処理の営業日データ {len(unprocessed)} 件を検出: {', '.join(unprocessed)}", latest_market_date
    except Exception as e:
        return [], f"株価取得エラー: {str(e)}", None

def main():
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    gemini_api_key = load_api_key()
    
    force_run = os.environ.get("FORCE_RUN", "").lower() in ["true", "1"] or ("--force" in sys.argv)
    
    unprocessed_dates, reason, latest_date = get_unprocessed_market_dates()
    
    if force_run and not unprocessed_dates and latest_date:
        print(f"⚡ [FORCE] 強制実行フラグが有効です。最新営業日（{latest_date}）でレポート生成・メール送信を実行します。")
        unprocessed_dates = [latest_date]
    elif not unprocessed_dates:
        subject = f"🚨【休場・未更新】株価データ処理スキップ [{today_str}]"
        body = f"本日（{today_str}）の株価データ分析・配信を安全にスキップしました。\n\n"
        body += f"【スキップ理由】\n{reason}\n\n"
        if latest_date:
            body += f"最新取得可能データ日付：{latest_date}\n\n"
        body += "誤ったデータや重複配信による統計汚染を防ぐための正常な処理ストップです。\n"
        body += "相場再開および最新データの反映が確認され次第、自動的に正常稼働いたします。\n"
        print(f"🛑 [SKIP] データ未更新のため処理を安全に停止します: {reason}")
        send_email(body, subject=subject)
        sys.exit(0)

    print(f"🚀 [START] 株価分析システム 本番バッチ処理を開始します...")
    print(f"📋 処理対象の未処理営業日: {unprocessed_dates}")

    # 1. 過去の未処理営業日がある場合は順次バックフィル（履歴JSONのみ生成）
    if len(unprocessed_dates) > 1:
        for past_date in unprocessed_dates[:-1]:
            print(f"\n📦 [Backfill] 過去日 {past_date} のデータ積み上げ処理中...")
            past_watch = analyze_watch_tickers(target_date_str=past_date)
            past_scan = scan_b_type(target_date_str=past_date, api_key="") # 過去分はAPI制限回避のため定型文
            generate_files(past_watch, past_scan, data_date=past_date)
            print(f"✅ [Backfill] {past_date} の履歴JSON保存完了")
            time.sleep(2)

    # 2. 最新営業日の本番分析を実行
    target_latest_date = unprocessed_dates[-1]
    print(f"\n🌟 [Latest] 最新営業日 {target_latest_date} の本番分析を開始...")
    
    print("\n🔍 監視銘柄の分析を開始...")
    watch_results = analyze_watch_tickers(target_date_str=target_latest_date)
    print(f"✅ 監視銘柄の分析完了: {len(watch_results)}銘柄")

    print("\n🔍 市場全体のスキャンを開始...")
    scan_results = scan_b_type(target_date_str=target_latest_date, api_key=gemini_api_key)
    print(f"✅ スキャン完了: A群 {len(scan_results['scan_a'])}銘柄 / B群 {len(scan_results['scan_b'])}銘柄")

    print("\n📊 ダッシュボードの生成を開始...")
    os.makedirs("public", exist_ok=True)
    prev_report = load_previous_report()
    generate_files(watch_results, scan_results, prev_report=prev_report, data_date=target_latest_date)
    print(f"✅ ダッシュボード生成完了: public/index.html (データ基準日: {target_latest_date})")
    
    print("\n📧 メール配信準備中...")
    market_info = scan_results.get("market_info", {})
    scan_a = scan_results.get("scan_a", [])
    
    backfill_note = f"（※未反映だった過去営業日 {', '.join(unprocessed_dates[:-1])} のデータも正常に蓄積・保存完了しました）\n\n" if len(unprocessed_dates) > 1 else ""
    body = f"【📈 本日の相場環境 (データ基準日: {target_latest_date})】\n{market_info.get('text', '')}\n\n{backfill_note}"
    body += "【👑 本日の条件達成銘柄】\n"
    if scan_a:
        for item in scan_a:
            # 一推し銘柄には🌟マークをつける
            star = "🌟(一推し) " if item.get("is_top_pick") else ""
            rr = item.get("risk_reward")
            rr_str = f" [SL: {rr['sl_price']:,}円(-{rr['risk_pct']}%) / TP: {rr['tp_price']:,}円 / R/R 1:{rr['rr_ratio']}]" if rr else ""
            body += f"・{star}{item['code']} {item['name']} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円){rr_str}\n"
    else:
        body += "・本日の鉄板条件クリア銘柄なし（休むも相場です）\n"
    body += "\n"

    scan_b = scan_results.get("scan_b", [])
    if scan_b:
        body += "【⚡ 出来高急増・注目銘柄（資金流入）】\n"
        for item in scan_b[:5]:
            signals_str = " / ".join([s for s in item.get('signals', []) if '出来高' not in s])
            sig_text = f" ({signals_str})" if signals_str else ""
            rr = item.get("risk_reward")
            rr_str = f" [SL: {rr['sl_price']:,}円 / R/R 1:{rr['rr_ratio']}]" if rr else ""
            body += f"・{item['code']} {item['name']} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円{sig_text}){rr_str}\n"
        body += "\n"
        
    body += "【📋 監視銘柄の状況】\n"
    if watch_results:
        for item in watch_results:
            if item["error"]:
                body += f"・{item['code']} {item['name']}: {item['error_msg']}\n"
            else:
                diff = item.get("price_diff", 0)
                diff_str = f"+{diff:,}" if diff > 0 else (f"{diff:,}" if diff < 0 else "±0")
                rsi = item.get('rsi', '-')
                rr = item.get("risk_reward")
                rr_str = f" [SL: {rr['sl_price']:,}円 / R/R 1:{rr['rr_ratio']}]" if rr else ""
                body += f"・{item['code']} {item['name']}: {item['price']:,}円 ({diff_str}円) ({item['position']} / RSI: {rsi}){rr_str}\n"
    else:
        body += "・データなし\n"
    body += "\n"
        
    repo_path = os.environ.get("GITHUB_REPOSITORY", "your-username/your-repo")
    username = repo_path.split('/')[0] if '/' in repo_path else ""
    repo_name = repo_path.split('/')[1] if '/' in repo_path else ""
    pages_url = f"https://{username}.github.io/{repo_name}/"
    
    body += f"ダッシュボードはこちら: {pages_url}\n\n"
    subject = f"投資戦略レポート [{target_latest_date} 終値]"
    send_email(body, subject=subject)
    
    print("\n🎉 [SUCCESS] すべての処理が正常に完了し、メール送信を予約しました！")

if __name__ == "__main__":
    main()
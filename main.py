import os
import sys
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

def get_expected_market_date():
    """現在時刻（JST）から期待される最新の市場営業日（YYYY-MM-DD）を算出する。
    平日16:00以降なら当日。深夜・早朝（遅延実行時）なら前営業日。
    土日は直前の金曜日に巻き戻す。
    """
    now = datetime.now(JST)
    if now.hour >= 16:
        target = now.date()
    else:
        target = now.date() - timedelta(days=1)
    
    while target.weekday() >= 5:  # 5=土, 6=日
        target -= timedelta(days=1)
    return target.strftime('%Y-%m-%d')

def check_market_updated():
    """東証の最新株価データが取得可能か、および前回処理済みデータとの重複がないかを検証する。
    Returns:
        (is_valid, reason, latest_market_date)
    """
    expected_date = get_expected_market_date()
    last_processed_date = get_last_processed_data_date()

    try:
        ticker = yf.Ticker("7203.T")
        df = ticker.history(period="5d")
        if df.empty:
            return False, "データプロバイダ（yfinance）からの取得失敗", None
        
        df = df.dropna(subset=['Close'])
        if df.empty:
            return False, "有効データなし", None
        
        df.index = df.index.tz_localize(None)
        latest_market_date = df.index[-1].strftime('%Y-%m-%d')

        # 1. 重複チェック（前回のレポートと全く同じデータ日の場合はスキップ）
        if last_processed_date and latest_market_date == last_processed_date and latest_market_date != expected_date:
            return False, f"最新データ（{latest_market_date}）は既に前回レポート済みです。新データ未反映のためスキップします。", latest_market_date

        # 2. 最新性が期待営業日に達しているかチェック（休場日・未反映判定）
        if latest_market_date != expected_date:
            return False, f"期待される営業日（{expected_date}）のデータが未反映、または休場日のため（最新取得日: {latest_market_date}）。", latest_market_date

        return True, f"最新データ（{latest_market_date}）取得完了", latest_market_date
    except Exception as e:
        return False, f"株価取得エラー: {str(e)}", None

def main():
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    
    is_updated, reason, latest_date = check_market_updated()
    
    if not is_updated:
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

    print(f"🚀 [START] 株価分析システム 本番バッチ処理を開始します... (データ基準日: {latest_date})")
    
    print("\n🔍 監視銘柄の分析を開始...")
    watch_results = analyze_watch_tickers()
    print(f"✅ 監視銘柄の分析完了: {len(watch_results)}銘柄")

    print("\n🔍 市場全体のスキャンを開始...")
    gemini_api_key = load_api_key()
    scan_results = scan_b_type(api_key=gemini_api_key)
    print(f"✅ スキャン完了: A群 {len(scan_results['scan_a'])}銘柄 / B群 {len(scan_results['scan_b'])}銘柄")

    print("\n📊 ダッシュボードの生成を開始...")
    os.makedirs("public", exist_ok=True)
    prev_report = load_previous_report()
    generate_files(watch_results, scan_results, prev_report=prev_report, data_date=latest_date)
    print("✅ ダッシュボード生成完了: public/index.html")
    
    print("\n📧 メール配信準備中...")
    market_info = scan_results.get("market_info", {})
    scan_a = scan_results.get("scan_a", [])
    
    body = f"【📈 本日の相場環境】\n{market_info.get('text', '')}\n\n"
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
    send_email(body)
    
    print("\n🎉 [SUCCESS] すべての処理が正常に完了し、メール送信を予約しました！")

if __name__ == "__main__":
    main()
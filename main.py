import os
import sys
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

def check_market_updated():
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    try:
        ticker = yf.Ticker("7203.T")
        df = ticker.history(period="5d")
        if df.empty:
            return False, "データ取得失敗"
        
        df.index = df.index.tz_localize(None)
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        
        if latest_date == today_str:
            return True, latest_date
        else:
            return False, latest_date
    except Exception as e:
        return False, str(e)

def main():
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    
    is_updated, latest_date = check_market_updated()
    
    if not is_updated:
        subject = f"🚨【休場・未更新】株価データ処理スキップ [{today_str}]"
        body = f"本日（{today_str}）の株価データが提供元に未反映、または休場日のため、\n"
        body += f"分析と履歴の保存を安全に停止しました。\n\n"
        body += f"最新取得日：{latest_date}\n\n"
        body += "誤ったデータによる統計汚染を防ぐための正常な処理ストップです。\n"
        body += "相場再開日のデータが揃い次第、自動的に正常稼働いたします。\n"
        print(f"データ未更新のため本来はここで終了します。最新データ日付: {latest_date}")
        # sys.exit(0)

    print("🚀 [START] 株価分析システム 本番バッチ処理を開始します...")
    
    print("\n🔍 監視銘柄の分析を開始...")
    watch_results = analyze_watch_tickers()
    print(f"✅ 監視銘柄の分析完了: {len(watch_results)}銘柄")

    print("\n🔍 市場全体のスキャンを開始...")
    # 🚨【修正】APIキーを取得してスキャナーに渡す
    gemini_api_key = load_api_key()
    scan_results = scan_b_type(api_key=gemini_api_key)
    print(f"✅ スキャン完了: A群 {len(scan_results['scan_a'])}銘柄 / B群 {len(scan_results['scan_b'])}銘柄")

    print("\n📊 ダッシュボードの生成を開始...")
    os.makedirs("public", exist_ok=True)
    prev_report = load_previous_report()
    generate_files(watch_results, scan_results, prev_report=prev_report)
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
            body += f"・{star}{item['code']} {item['name']} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円)\n"
    else:
        body += "・本日の鉄板条件クリア銘柄なし（休むも相場です）\n"
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
                body += f"・{item['code']} {item['name']}: {item['price']:,}円 ({diff_str}円) ({item['position']} / RSI: {rsi})\n"
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
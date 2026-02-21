import os
import sys
import smtplib
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from watcher import analyze_watch_tickers
from scanner import scan_b_type
from report_generator import generate_files
from performance_tracker import update_performance
from analyze_performance import analyze

JST = timezone(timedelta(hours=9))

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
        subject = f"🚨【警告】株価データ未更新 [{today_str}]"
        body = f"本日（{today_str}）の株価データが提供元に未反映のため、\n"
        body += f"分析と履歴の保存を安全に停止しました。\n\n"
        body += f"最新取得日：{latest_date}\n\n"
        body += "これはAPIの更新遅延によるものです。誤ったデータによる統計汚染を防ぐため処理を中断しました。\n"
        body += "明日以降の実行時にデータが揃い次第、正常に再開されます。\n"
        send_email(body, subject)
        print(f"データ未更新のため終了します。最新データ日付: {latest_date}")
        sys.exit(0)

    update_performance()
    analyze()
    
    watch_data = analyze_watch_tickers()
    scan_data = scan_b_type()
    
    generate_files(watch_data, scan_data)
    
    body = "【🚀 本日の市場テーマ候補】\n"
    if scan_data:
        for item in scan_data:
            company_name = item.get("name", "")
            body += f"・{item['code']} {company_name} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円)\n"
        body += "\n"
    else:
        body += "・本日の該当銘柄なし（またはスキップ）\n\n"

    body += "【📋 監視銘柄の状況】\n"
    if watch_data:
        for item in watch_data:
            if item["error"]:
                body += f"・{item['code']} {item['name']}: {item['error_msg']}\n"
            else:
                diff = item.get("price_diff", 0)
                if diff > 0:
                    diff_str = f"(+{diff:,}円)"
                elif diff < 0:
                    diff_str = f"({diff:,}円)"
                else:
                    diff_str = "(±0円)"
                
                body += f"・{item['code']} {item['name']}: {item['price']:,}円 {diff_str} ({item['position']} / RSI: {item['rsi']})\n"
        body += "\n"
    else:
        body += "・データなし\n\n"
        
    repo_path = os.environ.get("GITHUB_REPOSITORY", "your-username/your-repo")
    username = repo_path.split('/')[0] if '/' in repo_path else ""
    repo_name = repo_path.split('/')[1] if '/' in repo_path else ""
    pages_url = f"https://{username}.github.io/{repo_name}/"
    
    body += f"📱 スマホ用Webダッシュボードはこちら:\n{pages_url}\n\n"
    
    body += "-" * 40 + "\n【💡 投資用語メモ】\n"
    body += "・RSI：過熱感の指標（70以上買われすぎ、30以下売られすぎ）。\n"
    body += "・200日線：過去約1年の平均。長期トレンドの最重要ライン。\n"
    body += "・出来高急増：大口資金流入のサイン。\n" + "-" * 40 + "\n"
    
    send_email(body)

if __name__ == "__main__":
    main()

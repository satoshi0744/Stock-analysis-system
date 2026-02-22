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

def main():
    # 【テスト用】休日フィルターを無効化し、強制実行します
    print("🔧 テストモード: 休日フィルターをスキップします")

    # 💡 5日後スイングシミュレーターの実行
    analyze()
    
    watch_data = analyze_watch_tickers()
    scan_dict = scan_b_type()
    
    generate_files(watch_data, scan_dict)
    
    market_info = scan_dict.get("market_info", {})
    scan_a = scan_dict.get("scan_a", [])
    scan_b = scan_dict.get("scan_b", [])
    
    body = f"【📈 本日の相場環境】\n{market_info.get('text', '')}\n\n"
    
    body += "【👑 本日の本命候補 (A群)】\n"
    if scan_a:
        for item in scan_a:
            body += f"・{item['code']} {item['name']} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円)\n"
        body += "\n"
    else:
        body += "・本日の鉄板条件クリア銘柄なし（休むも相場です）\n\n"
        
    if scan_b:
        body += f"※次点候補(B群)が {len(scan_b)} 件あります。詳細はダッシュボードの折りたたみから確認してください。\n\n"

    body += "【📋 監視銘柄の状況】\n"
    if watch_data:
        for item in watch_data:
            if item["error"]:
                body += f"・{item['code']} {item['name']}: {item['error_msg']}\n"
            else:
                diff = item.get("price_diff", 0)
                diff_str = f"(+{diff:,}円)" if diff > 0 else (f"({diff:,}円)" if diff < 0 else "(±0円)")
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

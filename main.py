import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from watcher import analyze_watch_tickers
from scanner import scan_b_type
from report_generator import generate_files

def send_email(text_body):
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_PASSWORD")
    if not user or not pwd: return

    msg = MIMEMultipart()
    msg['Subject'] = f"投資戦略レポート [{datetime.now().strftime('%m/%d')}]"
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
    watch_data = analyze_watch_tickers()
    scan_data = scan_b_type()
    
    # 【NEW】HTMLとJSONの生成職人を呼び出す
    generate_files(watch_data, scan_data)
    
    # データをメール用のテキストに組み立てる
    body = "【📋 保有・監視銘柄の動向】\n"
    if watch_data:
        for item in watch_data:
            if item["error"]:
                body += f"・{item['code']} {item['name']}: {item['error_msg']}\n"
            else:
                body += f"・{item['code']} {item['name']}: {item['price']:,}円 ({item['position']} / RSI: {item['rsi']})\n"
        body += "\n"
    else:
        body += "・データなし\n\n"

    body += "【🚀 本日の市場テーマ候補】\n"
    if scan_data:
        for item in scan_data:
            body += f"・{item['code']} (出来高 {item['vol_ratio']}倍 / 終値 {item['price']:,}円)\n"
        body += "\n"
    else:
        body += "・本日の該当銘柄なし（またはスキップ）\n\n"
        
    # GitHub PagesのURLを自動生成して本文に入れる
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

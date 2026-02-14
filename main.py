import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from watcher import analyze_watch_tickers
from scanner import scan_b_type

def send_email(text_body):
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_PASSWORD")
    
    if not user or not pwd:
        print("【警告】メール設定がありません。ログにのみ出力します。")
        print(text_body)
        return

    msg = MIMEMultipart()
    msg['Subject'] = f"投資戦略レポート(Step1) [{datetime.now().strftime('%m/%d')}]"
    msg['From'] = user
    msg['To'] = user
    # 飾り気のないテキスト形式（plain）で送信。バグ要因を排除。
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(user, pwd)
        server.send_message(msg)
        server.quit()
        print("メール送信完了しました。")
    except Exception as e:
        print(f"メール送信エラー: {e}")

def main():
    print("--- 監視銘柄 (Watcher) 分析開始 ---")
    watch_results = analyze_watch_tickers()
    
    print("--- B型 (Scanner) スキャン開始 ---")
    scan_results = scan_b_type()
    
    # -------------------------
    # メールの本文作成（B案形式）
    # -------------------------
    body = "【B型：本日の動意銘柄（出来高20日平均の2.5倍以上 ＋ 上昇）】\n"
    if scan_results:
        body += "\n".join(scan_results) + "\n\n"
    else:
        body += "・本日の該当銘柄なし（またはデータ取得スキップ）\n\n"
        
    body += "【監視銘柄の状況（200日線 / RSI）】\n"
    if watch_results:
        body += "\n".join(watch_results) + "\n\n"
    else:
        body += "・データなし\n\n"
        
    body += "※エラーが発生した銘柄は自動スキップし、完走を優先しています。\n"
    
    # 送信
    send_email(body)

if __name__ == "__main__":
    main()

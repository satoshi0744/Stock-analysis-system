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
        print("【警告】メール設定がありません。")
        return

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
        print("メール送信完了しました。")
    except Exception as e:
        print(f"メール送信エラー: {e}")

def main():
    print("--- 監視銘柄 (Watcher) 分析開始 ---")
    watch_results = analyze_watch_tickers()
    
    print("--- スキャン (Scanner) 開始 ---")
    scan_results = scan_b_type()
    
    body = "【📋 保有・監視銘柄の動向（200日線 / RSI）】\n"
    if watch_results:
        body += "\n".join(watch_results) + "\n\n"
    else:
        body += "・データなし\n\n"

    body += "【🚀 本日の市場テーマ候補（出来高20日平均の2.5倍以上 ＋ 上昇）】\n"
    if scan_results:
        body += "\n".join(scan_results) + "\n\n"
    else:
        body += "・本日の該当銘柄なし（またはデータ取得スキップ）\n\n"
        
    body += "※エラーが発生した銘柄は自動スキップし、完走を優先しています。\n\n"
    
    # -------------------------
    # 【追加】サトシさんご提案の用語解説セクション
    # -------------------------
    body += "-" * 40 + "\n"
    body += "【💡 投資用語メモ】\n"
    body += "・RSI（相対力指数）：株価の過熱感を指数化したもの。70％以上で買われすぎ、30％以下で売られすぎの目安。50%が強弱の中心。\n"
    body += "・200日線（移動平均線）：過去200営業日（約1年）の平均株価。長期トレンドの最重要ライン。株価がこの線上にあれば長期上昇トレンド、下なら下落トレンドとされる。\n"
    body += "・出来高急増（動意）：取引成立数の急拡大。株価を動かすエネルギーであり、大口資金（機関投資家など）が流入し、新たなテーマが始まる初動のサインとなることが多い。\n"
    body += "-" * 40 + "\n"
    
    send_email(body)

if __name__ == "__main__":
    main()

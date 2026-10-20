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
from market_calendar import get_trading_dates, get_yfinance_available_dates

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
    """
    東証の営業日（日経平均ベース・個別銘柄非依存）と、分析データ供給元(yfinance)の反映状況を突き合わせ、
    処理すべき日付を判定する。

    戻り値: dict
      ready     : 今回処理する日付（yfinance反映済みで、古い順に連続しているもの）
      pending   : 営業日だが yfinance 未反映のため保留する日付
      latest    : 確定済みの最新営業日
      source    : 営業日判定に使ったソース
      reason    : 判定内容の説明
      error     : 営業日取得自体に失敗した場合のエラー文（なければ None）
    """
    last_processed = get_last_processed_data_date()
    result = {"ready": [], "pending": [], "latest": None, "source": "", "reason": "",
              "error": None, "last_processed": last_processed}
    try:
        trading_dates, source = get_trading_dates()
    except Exception as e:
        result["error"] = str(e)
        result["reason"] = f"営業日の判定に失敗しました: {e}"
        return result

    result["source"] = source
    if not trading_dates:
        result["reason"] = "確定済みの営業日が取得できませんでした。"
        return result
    result["latest"] = trading_dates[-1]

    if last_processed:
        unprocessed = [d for d in trading_dates if d > last_processed]
    else:
        unprocessed = [trading_dates[-1]]

    if not unprocessed:
        today_now = datetime.now(JST).strftime('%Y-%m-%d')
        if today_now in trading_dates:
            result["already_done"] = True
            result["reason"] = f"本日（{today_now}）分は処理済みです（重複実行のため何もしません）。"
            return result
        result["reason"] = (f"新しい営業日はありません（確定済み最新営業日 {trading_dates[-1]} は処理済み）。"
                            f"本日は休場日です。")
        return result

    # yfinance に日足が入っている日付だけを、古い順に「途切れなく」処理する。
    # 途中の日が未反映なのに後の日を処理すると、前回処理日が進んでその日が永久に抜けるため。
    available = get_yfinance_available_dates()
    ready = []
    for d in unprocessed:
        if d in available:
            ready.append(d)
        else:
            break
    pending = unprocessed[len(ready):]
    result["ready"] = ready
    result["pending"] = pending

    if ready and not pending:
        result["reason"] = f"未処理の営業日 {len(ready)} 件を検出: {', '.join(ready)}"
    elif ready and pending:
        result["reason"] = (f"処理可能: {', '.join(ready)} / yfinance未反映のため保留: {', '.join(pending)}")
    else:
        latest_yf = max(available) if available else "取得失敗"
        result["reason"] = (f"東証は営業日（{', '.join(pending)}）ですが、分析用データ（yfinance）に未反映です"
                            f"（yfinance上の最新: {latest_yf}）。")
    return result

def main():
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    gemini_api_key = load_api_key()
    
    force_run = os.environ.get("FORCE_RUN", "").lower() in ["true", "1"] or ("--force" in sys.argv)
    
    status = get_unprocessed_market_dates()
    unprocessed_dates = status["ready"]
    latest_date = status["latest"]
    reason = status["reason"]
    print(f"🗓️ 営業日判定ソース: {status['source'] or '取得失敗'}")
    print(f"🗓️ 前回処理済み: {status['last_processed']} / 確定済み最新営業日: {latest_date}")
    print(f"🗓️ 判定: {reason}")
    
    if force_run and not unprocessed_dates and latest_date and not status["pending"]:
        print(f"⚡ [FORCE] 強制実行フラグが有効です。最新営業日（{latest_date}）でレポート生成・メール送信を実行します。")
        unprocessed_dates = [latest_date]
    elif not unprocessed_dates and status.get("already_done"):
        print(f"✅ [DONE] {reason}")
        sys.exit(0)
    elif not unprocessed_dates:
        if status["error"]:
            subject = f"⚠️【判定エラー】株価データ処理スキップ [{today_str}]"
        elif status["pending"]:
            subject = f"⏳【データ未反映】株価データ処理を保留 [{today_str}]"
        else:
            subject = f"💤【休場日】株価データ処理スキップ [{today_str}]"
        body = f"本日（{today_str}）の株価データ分析・配信をスキップしました。\n\n"
        body += f"【理由】\n{reason}\n\n"
        body += "【判定の詳細】\n"
        body += f"・営業日判定ソース：{status['source'] or '取得失敗'}\n"
        body += f"・確定済み最新営業日：{latest_date or '不明'}\n"
        body += f"・前回処理済みデータ日：{status['last_processed'] or 'なし'}\n"
        if status["pending"]:
            body += f"・保留中の営業日：{', '.join(status['pending'])}\n"
        body += f"・実行時刻（JST）：{datetime.now(JST).strftime('%Y-%m-%d %H:%M')}\n\n"
        if status["pending"]:
            body += "保留した営業日は、次回実行時にデータ反映を確認して自動で補完（バックフィル）します。\n"
        print(f"🛑 [SKIP] {reason}")
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
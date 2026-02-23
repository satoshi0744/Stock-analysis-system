import os
from datetime import datetime, timedelta, timezone
from scanner import scan_b_type
from watcher import analyze_watch_tickers
from report_generator import generate_html_report

# 日本時間のタイムゾーン設定
JST = timezone(timedelta(hours=9))

def main():
    print("🚀 [START] 株価分析システム 本番バッチ処理を開始します...")
    
    # 1. 監視銘柄（ウォッチャー）の分析
    print("\n🔍 監視銘柄の分析を開始...")
    watch_results = analyze_watch_tickers()
    print(f"✅ 監視銘柄の分析完了: {len(watch_results)}銘柄")

    # 2. 全銘柄スキャン（A群・B群の判定）
    print("\n🔍 市場全体のスキャンを開始...")
    scan_results = scan_b_type()
    print(f"✅ スキャン完了: A群 {len(scan_results['scan_a'])}銘柄 / B群 {len(scan_results['scan_b'])}銘柄")

    # 3. HTMLレポートの生成（ダッシュボード構築）
    print("\n📊 ダッシュボードの生成を開始...")
    # publicフォルダが存在しない場合は作成
    os.makedirs("public", exist_ok=True)
    generate_html_report(scan_results, watch_results)
    print("✅ ダッシュボード生成完了: public/index.html")
    
    print("\n🎉 [SUCCESS] すべての処理が正常に完了しました！")

if __name__ == "__main__":
    main()
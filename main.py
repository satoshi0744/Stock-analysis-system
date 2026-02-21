import builtins
from watcher import analyze_watch_tickers
from scanner import scan_b_type
from report_generator import generate_files

def main():
    print("🔧 【Phase 2 テストモード】新しい分析エンジンを実行中...")
    
    # 候補銘柄が存在した木曜日（2月19日）を指定してエンジンを回す
    target_date = "2026-02-19"
    print(f"📅 {target_date} のデータを再取得して、200日線とシグナルを計算します...")

    # 新しいエンジンでデータを取得
    watch_data = analyze_watch_tickers(target_date)
    scan_data = scan_b_type(target_date)

    # 🚨 履歴フォルダ（統計データ）を汚さないための安全装置
    original_open = builtins.open
    def safe_open(file, mode='r', *args, **kwargs):
        if "history" in str(file) and 'w' in mode:
            import io
            return io.StringIO() 
        return original_open(file, mode, *args, **kwargs)
    builtins.open = safe_open
    
    # HTML（画面）を再生成
    generate_files(watch_data, scan_data)
    print("✅ 画面（HTML）の再生成が完了しました！GitHub Pagesをご確認ください。")

if __name__ == "__main__":
    main()

import json
import builtins
import os
from report_generator import generate_files

def main():
    print("🔧 UI確認用テストモードで実行中...")
    
    # 金曜日の最新データを読み込む
    if not os.path.exists("public/report.json"):
        print("エラー: public/report.json が見つかりません。")
        return
        
    with open("public/report.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 🚨 履歴フォルダを汚さないための安全装置
    # （historyフォルダへの書き込みを検知して、保存を「空振り」させます）
    original_open = builtins.open
    def safe_open(file, mode='r', *args, **kwargs):
        if "history" in str(file) and 'w' in mode:
            import io
            return io.StringIO() 
        return original_open(file, mode, *args, **kwargs)
    builtins.open = safe_open
    
    # HTML（画面）だけを再生成
    generate_files(data.get("watch_data", []), data.get("scan_data", []))
    print("✅ 画面（HTML）の再生成が完了しました！GitHub Pagesに反映されます。")

if __name__ == "__main__":
    main()

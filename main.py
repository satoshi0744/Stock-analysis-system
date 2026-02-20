import json
import builtins
import os
import glob
from report_generator import generate_files

def main():
    print("🔧 UI確認用テストモード（候補銘柄がある過去日を検索中...）")
    
    # historyフォルダ内のJSONを新しい順に取得
    history_files = sorted(glob.glob("public/history/*.json"), reverse=True)
    
    target_data = None
    target_date = ""
    
    for file in history_files:
        with open(file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # scan_data（候補銘柄）が存在し、空ではない日を探す
                if data.get("scan_data") and len(data["scan_data"]) > 0:
                    target_data = data
                    target_date = file
                    break
            except Exception:
                continue
                
    if not target_data:
        print("エラー: 候補銘柄が存在する過去のデータが見つかりませんでした。")
        return
        
    print(f"📅 {target_date} のデータを読み込んで画面を生成します...")

    # 🚨 履歴フォルダを汚さないための安全装置
    original_open = builtins.open
    def safe_open(file, mode='r', *args, **kwargs):
        if "history" in str(file) and 'w' in mode:
            import io
            return io.StringIO() 
        return original_open(file, mode, *args, **kwargs)
    builtins.open = safe_open
    
    # HTML（画面）だけを再生成
    generate_files(target_data.get("watch_data", []), target_data.get("scan_data", []))
    print("✅ 画面（HTML）の再生成が完了しました！GitHub Pagesをご確認ください。")

if __name__ == "__main__":
    main()

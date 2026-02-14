import os
import json

HISTORY_DIR = "public/history"
SUMMARY_FILE = "public/performance_summary.json"

def analyze():
    if not os.path.exists(HISTORY_DIR):
        return

    total_signals = 0
    wins = 0
    losses = 0
    total_return = 0.0

    # 履歴ファイルをすべて読み込む
    for filename in os.listdir(HISTORY_DIR):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(HISTORY_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("scan_data", []):
            # next_day_return（翌日リターン）が計算済みのものだけを集計
            if "next_day_return" in item:
                ret = item["next_day_return"]
                total_signals += 1
                total_return += ret
                if ret > 0:
                    wins += 1
                elif ret < 0:
                    losses += 1

    # 統計の計算
    win_rate = (wins / total_signals * 100) if total_signals > 0 else 0.0
    avg_return = (total_return / total_signals) if total_signals > 0 else 0.0
    # 簡易的な期待値（勝率×平均利益 - 負率×平均損失）※ここでは全体の平均リターンを近似値として使用
    expectancy = avg_return 

    summary = {
        "total_signals": total_signals,
        "win_rate": round(win_rate, 1),
        "avg_return": round(avg_return, 2),
        "expectancy": round(expectancy, 2)
    }

    # 結果を保存
    os.makedirs("public", exist_ok=True)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    analyze()

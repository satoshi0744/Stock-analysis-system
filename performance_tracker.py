import os
import json
import pandas_datareader.data as web
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HISTORY_DIR = "public/history"

def calculate_return(signal_date, code, entry_price):
    try:
        start = datetime.strptime(signal_date, "%Y-%m-%d")
        end = start + timedelta(days=10)

        df = web.DataReader(f"{code}.JP", "stooq", start, end).sort_index()

        if len(df) < 2:
            return None

        next_close = df.iloc[1]["Close"]
        return round(((next_close - entry_price) / entry_price) * 100, 2)

    except Exception:
        return None

def update_performance():
    if not os.path.exists(HISTORY_DIR):
        return

    today = datetime.now(JST).strftime("%Y-%m-%d")

    for filename in os.listdir(HISTORY_DIR):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(HISTORY_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        signal_date = data.get("date")

        # 当日ファイルはまだ翌日データがない可能性があるためスキップ
        if not signal_date or signal_date >= today:
            continue

        updated = False

        for item in data.get("scan_data", []):
            if "next_day_return" in item:
                continue

            result = calculate_return(signal_date, item["code"], item["price"])
            if result is not None:
                item["next_day_return"] = result
                updated = True

        if updated:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

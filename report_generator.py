import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data_dict):
    os.makedirs("public", exist_ok=True)
    now = datetime.now(JST)
    now_str = now.strftime('%Y/%m/%d %H:%M')
    date_str = now.strftime('%Y-%m-%d')
    
    # 💡 並び順をwatchlist.jsonの順序に再ソート
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            order = list(json.load(f).keys())
        watch_data = sorted(watch_data, key=lambda x: order.index(x['code']) if x['code'] in order else 999)
    except:
        pass # JSON読み込み失敗時はそのまま

    report_dict = {
        "updated_at": now_str,
        "date": date_str,
        "watch_data": watch_data,
        "scan_data": scan_data_dict
    }
    
    with open("public/report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    market_info = scan_data_dict.get("market_info", {"text": "判定不能", "is_good": False})
    scan_a = scan_data_dict.get("scan_a", [])
            
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投資戦略ダッシュボード</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 15px; line-height: 1.6; }}
        h1 {{ font-size: 1.4rem; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        h2 {{ font-size: 1.1rem; margin-top: 25px; color: #4db8ff; border-left: 4px solid #4db8ff; padding-left: 8px; }}
        .card {{ background-color: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        .card-title {{ font-weight: bold; font-size: 1.1rem; margin-bottom: 8px; color: #fff; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 5px; display: inline-block; margin-bottom: 4px; }}
        .badge-up {{ background-color: #2e7d32; color: white; }}
        .badge-down {{ background-color: #c62828; color: white; }}
        .badge-signal {{ background-color: rgba(103,58,183,0.15); color: #d1c4e9; border: 1px solid #673ab7; }}
        .rsi-high {{ color: #ff5252; font-weight: bold; }}
        .rsi-low {{ color: #69f0ae; font-weight: bold; }}
        .ai-comment-box {{ background: linear-gradient(145deg, #1e253c, #151a2a); border-left: 4px solid #b388ff; border-radius: 6px; padding: 12px 15px; margin-top: 15px; font-size: 0.9rem; color: #e8eaf6; }}
        .diff-up {{ color: #69f0ae; font-weight: bold; }}
        .diff-down {{ color: #ff5252; font-weight: bold; }}
    </style>
</head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px;">
        <h1 style="margin: 0;">📊 投資戦略ダッシュボード</h1>
        <a href="analyzer.html" target="_blank" style="background-color: #1a237e; color: #4db8ff; text-decoration: none; padding: 8px 15px; border-radius: 4px; font-size: 0.9rem; font-weight: bold; border: 1px solid #3949ab;">🔍 個別銘柄分析を開く</a>
    </div>

    <div style="background-color: #1e1e1e; padding: 10px 15px; border-radius: 6px; margin-bottom: 15px; border-left: 4px solid {'#2e7d32' if market_info['is_good'] else '#fbc02d'};">
        <span style="font-size: 0.9rem; color: #aaa;">本日の相場環境：</span> 
        <strong style="font-size: 1.1rem; color: #fff;">{market_info['text']}</strong>
        <div id="tv-nikkei-container" style="width: 100%; height: 400px; margin-top: 15px;"></div>
    </div>

    <h2>📋 監視銘柄の状況</h2>
"""
    # 監視銘柄カードの生成（以前のきれいな形式を復元）
    for item in watch_data:
        diff = item.get("price_diff", 0)
        diff_html = f'<span class="diff-up">(+{diff:,}円)</span>' if diff > 0 else (f'<span class="diff-down">({diff:,}円)</span>' if diff < 0 else '<span>(±0円)</span>')
        pos_class = "badge-up" if "上" in item.get("position", "") else "badge-down"
        rsi = item.get("rsi", 0)
        rsi_class = "rsi-high" if rsi >= 70 else ("rsi-low" if rsi <= 30 else "")

        html += f"""
        <div class="card">
            <div class="card-title">{item["code"]} {item["name"]}</div>
            <div>現在値: <strong>{item["price"]:,}円</strong> {diff_html}</div>
            <div style="margin-top:8px;">
                <span class="badge {pos_class}">{item.get("position", "-")}</span>
                <span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{rsi}</span></span>
            </div>
            {f'<div class="ai-comment-box">🤖 {item["ai_comment"]}</div>' if item.get("ai_comment") else ""}
        </div>"""

    html += f"""
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script type="text/javascript">
        new TradingView.widget({{
            "width": "100%", "height": 400, "symbol": "NI225",
            "interval": "D", "timezone": "Asia/Tokyo", "theme": "dark",
            "container_id": "tv-nikkei-container", "locale": "ja"
        }});
    </script>
</body></html>"""
    
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)

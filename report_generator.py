import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data_dict):
    os.makedirs("public", exist_ok=True)
    now_str = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
    
    # 並び順固定
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            order = list(json.load(f).keys())
        watch_data = sorted(watch_data, key=lambda x: order.index(x['code']) if x['code'] in order else 999)
    except: pass

    summary = {"total_signals": 0, "win_rate": 0, "avg_return": 0, "strategies": {}}
    if os.path.exists("public/performance_summary.json"):
        with open("public/performance_summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)

    market_info = scan_data_dict.get("market_info", {"text": "判定不能", "is_good": False})
    scan_a = scan_data_dict.get("scan_a", [])
    scan_b = scan_data_dict.get("scan_b", [])

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><title>投資戦略ダッシュボード</title>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
    body {{ font-family: sans-serif; background-color: #121212; color: #e0e0e0; padding: 15px; }}
    .card {{ background-color: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    .highlight {{ border-left: 4px solid #ffab00; }}
    .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 5px; display: inline-block; }}
    .badge-up {{ background-color: #2e7d32; }} .badge-down {{ background-color: #c62828; }}
    .badge-signal {{ background-color: #673ab7; color: white; }}
    .ai-comment-box {{ background: #1e253c; border-left: 4px solid #b388ff; padding: 12px; margin-top: 10px; font-size: 0.9rem; }}
    .stats-box {{ background-color: #1a237e; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
    .chart-container {{ width: 100%; height: 250px; margin-top: 15px; border: 1px solid #333; }}
</style></head>
<body>
    <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 10px;">
        <h1>📊 投資戦略ダッシュボード</h1>
        <div class="update-time">最終更新: {now_str}</div>
    </div>

    <div class="card" style="border-left: 4px solid {'#2e7d32' if market_info['is_good'] else '#fbc02d'};">
        <span>本日の相場環境：</span><strong style="font-size: 1.2rem;">{market_info['text']}</strong>
        <div id="tv-nikkei-container" style="height: 400px; margin-top: 15px;"></div>
    </div>

    <h2>👑 本日の条件達成銘柄</h2>
    {"".join([f'<div class="card highlight"><h3>{item["code"]} {item["name"]}</h3><div id="chart-scan-{item["code"]}" class="chart-container"></div></div>' for item in scan_a]) if scan_a else '<p>なし</p>'}

    <details class="stats-box"><summary>📈 条件達成銘柄の検証データ</summary>
        <p>総シグナル: {summary["total_signals"]} / 勝率: {summary["win_rate"]}%</p>
    </details>

    <details class="card"><summary>📁 次点・監視用ログ ({len(scan_b)}件)</summary>
        {"".join([f'<div>{item["code"]} {item["name"]}</div>' for item in scan_b])}
    </details>

    <h2>📋 監視銘柄の状況</h2>
    {"".join([f'''<div class="card">
        <h3>{item["code"]} {item["name"]}</h3>
        <div>現在値: {item["price"]:,}円 <span class="{'badge-up' if item['price_diff'] > 0 else 'badge-down'}">{item['price_diff']}円</span></div>
        <div style="margin-top:10px;"><span class="badge badge-up">{item['position']}</span> RSI: {item['rsi']}</div>
        <div class="ai-comment-box">🤖 {item['ai_comment']}</div>
        <div id="chart-watch-{item['code']}" class="chart-container"></div>
    </div>''' for item in watch_data])}

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        new TradingView.widget({{"container_id": "tv-nikkei-container", "width": "100%", "height": 400, "symbol": "NI225", "interval": "D", "theme": "dark", "locale": "ja"}});
        const render = (item, type) => {{
            const container = document.getElementById('chart-' + type + '-' + item.code);
            if (!container) return;
            const chart = LightweightCharts.createChart(container, {{ layout: {{ background: {{ color: '#1e1e1e' }}, textColor: '#d1d4dc' }}, grid: {{ vertLines: {{ color: '#2b2b43' }} }} }});
            const s = chart.addCandlestickSeries();
            s.setData(item.history_data);
            chart.timeScale().fitContent();
        }};
        {json.dumps(watch_data)}.forEach(i => render(i, 'watch'));
        {json.dumps(scan_a)}.forEach(i => render(i, 'scan'));
    </script>
</body></html>"""
    with open("public/index.html", "w", encoding="utf-8") as f: f.write(html)

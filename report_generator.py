import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data_dict):
    os.makedirs("public", exist_ok=True)
    now_str = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
    
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            order = list(json.load(f).keys())
        watch_data = sorted(watch_data, key=lambda x: order.index(x['code']) if x['code'] in order else 999)
    except: pass

    summary = {"total_signals": 0, "win_rate": 0, "avg_return": 0, "expectancy": 0}
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
    body {{ font-family: -apple-system, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 15px; line-height: 1.6; }}
    h1 {{ font-size: 1.4rem; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
    h2 {{ font-size: 1.1rem; margin-top: 25px; color: #4db8ff; border-left: 4px solid #4db8ff; padding-left: 8px; }}
    .card {{ background-color: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    .highlight {{ border-left: 4px solid #ffab00; }}
    .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 5px; display: inline-block; }}
    .badge-up {{ background-color: #2e7d32; color: white; }} .badge-down {{ background-color: #c62828; color: white; }}
    .ai-comment-box {{ background: linear-gradient(145deg, #1e253c, #151a2a); border-left: 4px solid #b388ff; padding: 12px; margin-top: 15px; font-size: 0.9rem; border-radius: 6px; }}
    .chart-container {{ width: 100%; height: 250px; margin-top: 15px; border: 1px solid #333; position: relative; }}
    .legend {{ position: absolute; top: 10px; left: 10px; z-index: 10; font-size: 0.75rem; background: rgba(30,30,30,0.7); padding: 5px; border-radius: 4px; display: flex; gap: 10px; }}
    .stats-box {{ background-color: #1a237e; border: 1px solid #3949ab; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
    .diff-up {{ color: #69f0ae; font-weight: bold; }} .diff-down {{ color: #ff5252; font-weight: bold; }}
</style></head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px;">
        <h1 style="margin: 0;">📊 投資戦略ダッシュボード</h1>
        <a href="analyzer.html" target="_blank" style="background-color: #1a237e; color: #4db8ff; text-decoration: none; padding: 8px 15px; border-radius: 4px; font-size: 0.9rem; font-weight: bold; border: 1px solid #3949ab;">🔍 個別銘柄分析を開く</a>
    </div>
    <div style="text-align: right; color: #888; font-size: 0.8rem; margin-top: -10px; margin-bottom: 10px;">最終更新: {now_str}</div>

    <div class="card" style="border-left: 4px solid {'#2e7d32' if market_info['is_good'] else '#fbc02d'};">
        <span>本日の相場環境：</span><strong style="font-size: 1.1rem;">{market_info['text']}</strong>
        <div id="tv-nikkei-container" style="width: 100%; height: 400px; margin-top: 15px; border-radius: 4px; overflow: hidden; border: 1px solid #333;"></div>
    </div>

    <h2 style="color: #ffab00;">👑 本日の条件達成銘柄</h2>
    {"".join([f'''<div class="card highlight">
        <div style="font-weight:bold; font-size:1.1rem;">{item["code"]} {item["name"]}</div>
        <div>現在値: {item["price"]:,}円 <span class="{'diff-up' if item['price_diff'] > 0 else 'diff-down'}">({item['price_diff'] if item['price_diff'] < 0 else '+' + str(item['price_diff'])}円)</span></div>
        <div class="chart-container">
            <div id="legend-scan-{item["code"]}" class="legend"></div>
            <div id="chart-scan-{item["code"]}" style="width:100%; height:250px;"></div>
        </div>
    </div>''' for item in scan_a]) if scan_a else '<p style="color:#888; margin-left:15px;">本日の鉄板条件クリア銘柄なし</p>'}

    <details class="stats-box"><summary style="color:#fff; cursor:pointer; font-weight:bold;">📈 条件達成銘柄の検証データ（5営業日スイング）</summary>
        <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; margin-top:10px; text-align:center;">
            <div style="background:rgba(0,0,0,0.2); padding:10px;"><div style="font-size:1.2rem; font-weight:bold;">{summary["total_signals"]}</div><div style="font-size:0.7rem; color:#9fa8da;">総シグナル</div></div>
            <div style="background:rgba(0,0,0,0.2); padding:10px;"><div style="font-size:1.2rem; font-weight:bold;">{summary["win_rate"]}%</div><div style="font-size:0.7rem; color:#9fa8da;">勝率</div></div>
        </div>
    </details>

    <details class="card"><summary style="color:#888; cursor:pointer;">📁 次点・監視用ログ ({len(scan_b)}件)</summary>
        <div style="margin-top:10px; font-size:0.85rem; color:#bbb;">
            {"".join([f'<div style="border-bottom:1px solid #333; padding:5px 0;">{item["code"]} {item["name"]} ({item["price"]:,}円) <span style="font-size:0.75rem; color:#777;">{" ".join(item["signals"])}</span></div>' for item in scan_b])}
        </div>
    </details>

    <h2>📋 監視銘柄の状況</h2>
    {"".join([f'''<div class="card">
        <div style="font-weight:bold; font-size:1.1rem;">{item["code"]} {item["name"]}</div>
        <div>現在値: {item["price"]:,}円 <span class="{'diff-up' if item['price_diff'] > 0 else 'diff-down'}">({item['price_diff'] if item['price_diff'] < 0 else '+' + str(item['price_diff'])}円)</span></div>
        <div style="margin-top:10px;">
            <span class="badge {'badge-up' if '上' in item['position'] else 'badge-down'}">{item['position']}</span>
            <span style="font-size:0.9rem;">RSI: {item['rsi']}</span>
        </div>
        <div class="ai-comment-box">🤖 {item['ai_comment']}</div>
        <div class="chart-container">
            <div id="legend-watch-{item["code"]}" class="legend"></div>
            <div id="chart-watch-{item["code"]}" style="width:100%; height:250px;"></div>
        </div>
    </div>''' for item in watch_data])}

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        // 日経平均チャート：TVC指定でOK回避
        new TradingView.widget({{
            "container_id": "tv-nikkei-container", "width": "100%", "height": 400,
            "symbol": "TVC:NI225", "interval": "D", "timezone": "Asia/Tokyo",
            "theme": "dark", "style": "1", "locale": "ja", "enable_publishing": false
        }});

        const renderChart = (item, type) => {{
            const container = document.getElementById('chart-' + type + '-' + item.code);
            const legend = document.getElementById('legend-' + type + '-' + item.code);
            if (!container || !item.history_data) return;

            const chart = LightweightCharts.createChart(container, {{
                layout: {{ background: {{ color: '#1e1e1e' }}, textColor: '#d1d4dc' }},
                grid: {{ vertLines: {{ color: '#2b2b43' }}, horzLines: {{ color: '#2b2b43' }} }},
                timeScale: {{ borderColor: '#2b2b43' }}, rightPriceScale: {{ borderColor: '#2b2b43' }}
            }});

            const candle = chart.addCandlestickSeries({{ upColor: '#FF5252', downColor: '#26a69a' }});
            candle.setData(item.history_data.map(d => ({{ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }})));

            const addMA = (color, period) => {{
                const ma = chart.addLineSeries({{ color: color, lineWidth: 1, lastValueVisible: false, priceLineVisible: false }});
                const data = item.history_data.filter(d => d['ma'+period]).map(d => ({{ time: d.time, value: d['ma'+period] }}));
                ma.setData(data);
                return data.length > 0 ? data[data.length-1].value.toFixed(0) : '-';
            }};

            const last25 = addMA('#2962FF', 25);
            const last75 = addMA('#FF5252', 75);
            const last200 = addMA('#FF9800', 200);

            if (legend) legend.innerHTML = `
                <div style="color:#2962FF">■ MA25: ${{last25}}</div>
                <div style="color:#FF5252">■ MA75: ${{last75}}</div>
                <div style="color:#FF9800">■ MA200: ${{last200}}</div>
            `;
            chart.timeScale().fitContent();
        }};

        const watchData = {json.dumps(watch_data)};
        const scanAData = {json.dumps(scan_a)};
        watchData.forEach(i => renderChart(i, 'watch'));
        scanAData.forEach(i => renderChart(i, 'scan'));
    </script>
</body></html>"""
    with open("public/index.html", "w", encoding="utf-8") as f: f.write(html)

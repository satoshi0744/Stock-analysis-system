import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data_dict):
    os.makedirs("public", exist_ok=True)
    now = datetime.now(JST).strftime('%Y/%m/%d %H:%M')
    
    # 💡 並び順をwatchlist.jsonの順序に再ソート
    with open("watchlist.json", "r", encoding="utf-8") as f:
        order = list(json.load(f).keys())
    
    # watch_dataをコード順ではなく、jsonの定義順に並び替え
    watch_data_sorted = sorted(watch_data, key=lambda x: order.index(x['code']) if x['code'] in order else 999)

    market_info = scan_data_dict.get("market_info", {"text": "判定不能", "is_good": False})
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>投資戦略ダッシュボード</title>
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            /* 既存のスタイルを維持 */
            body {{ background-color: #121212; color: #e0e0e0; font-family: sans-serif; padding: 20px; }}
            .card {{ background: #1e1e1e; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #333; }}
            .good {{ border-left-color: #2e7d32; }}
            .adjust {{ border-left-color: #fbc02d; }}
        </style>
    </head>
    <body>
        <h1>📊 投資戦略ダッシュボード</h1>
        <div class="card {'good' if market_info['is_good'] else 'adjust'}">
            <h3>本日の相場環境: {market_info['text']}</h3>
            <div id="tv_chart" style="height:400px;"></div>
        </div>
        
        <h2>📋 監視銘柄の状況 (Watchlist順)</h2>
        {''.join([f'<div class="card"><strong>{d["code"]} {d["name"]}</strong>: {d["price"]:,}円 (RSI: {d["rsi"]})</div>' for d in watch_data_sorted])}

        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
            new TradingView.widget({{
                "container_id": "tv_chart",
                "width": "100%", "height": 400,
                "symbol": "OANDA:JP225JPY",
                "interval": "D", "timezone": "Asia/Tokyo",
                "theme": "dark", "style": "1", "locale": "ja",
                "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true
            }});
        </script>
    </body>
    </html>
    """
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

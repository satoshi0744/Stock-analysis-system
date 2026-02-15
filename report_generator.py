import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data):
    os.makedirs("public", exist_ok=True)
    os.makedirs("public/history", exist_ok=True)
    
    now = datetime.now(JST)
    now_str = now.strftime('%Y/%m/%d %H:%M')
    date_str = now.strftime('%Y-%m-%d')
    
    report_dict = {
        "updated_at": now_str,
        "date": date_str,
        "watch_data": watch_data,
        "scan_data": scan_data
    }
    
    with open("public/report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
    history_path = f"public/history/{date_str}.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    # パフォーマンス集計データの読み込み
    summary = {"total_signals": 0, "win_rate": 0.0, "avg_return": 0.0, "expectancy": 0.0}
    if os.path.exists("public/performance_summary.json"):
        with open("public/performance_summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)
            
    # HTML生成
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投資戦略ダッシュボード</title>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 15px; line-height: 1.6; }}
        h1 {{ font-size: 1.4rem; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        h2 {{ font-size: 1.1rem; margin-top: 25px; color: #4db8ff; border-left: 4px solid #4db8ff; padding-left: 8px; }}
        .card {{ background-color: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        .card-title {{ font-weight: bold; font-size: 1.1rem; margin-bottom: 8px; color: #fff; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 5px; }}
        .badge-up {{ background-color: #2e7d32; color: white; }}
        .badge-down {{ background-color: #c62828; color: white; }}
        .badge-neutral {{ background-color: #424242; color: white; }}
        .rsi-high {{ color: #ff5252; font-weight: bold; }}
        .rsi-low {{ color: #69f0ae; font-weight: bold; }}
        .highlight {{ border-left: 4px solid #ffab00; background-color: #2a2a2a; }}
        .stats-box {{ background-color: #1a237e; border: 1px solid #3949ab; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 10px; }}
        .stat-item {{ text-align: center; background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }}
        .stat-value {{ font-size: 1.3rem; font-weight: bold; color: #fff; }}
        .stat-label {{ font-size: 0.75rem; color: #9fa8da; }}
        .glossary {{ background-color: #1a1a1a; padding: 15px; border-radius: 8px; font-size: 0.85rem; margin-top: 30px; border-top: 1px solid #333; }}
        .glossary dt {{ font-weight: bold; color: #ffca28; margin-top: 10px; }}
        .glossary dd {{ margin-left: 0; margin-bottom: 10px; color: #bbb; }}
        .error-text {{ color: #757575; font-style: italic; font-size: 0.9rem; }}
        .update-time {{ font-size: 0.85rem; color: #888; text-align: right; margin-top: -15px; margin-bottom: 15px; }}
        /* 【NEW】チャート用コンテナのスタイル */
        .chart-container {{ width: 100%; height: 250px; margin-top: 15px; border: 1px solid #333; border-radius: 4px; overflow: hidden; }}
    </style>
</head>
<body>
    <h1>📊 投資戦略ダッシュボード</h1>
    <div class="update-time">最終更新: {now_str}</div>

    <div class="stats-box">
        <div style="font-weight:bold; color:#c5cae9; border-bottom:1px solid #3949ab; padding-bottom:5px;">📈 市場テーマ戦略（出来高急増） パフォーマンス検証</div>
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-value">{summary["total_signals"]}</div><div class="stat-label">総シグナル数</div></div>
            <div class="stat-item"><div class="stat-value">{summary["win_rate"]}%</div><div class="stat-label">勝率</div></div>
            <div class="stat-item"><div class="stat-value">{summary["avg_return"]}%</div><div class="stat-label">平均翌日リターン</div></div>
            <div class="stat-item"><div class="stat-value">{summary["expectancy"]}%</div><div class="stat-label">期待値</div></div>
        </div>
        <div style="font-size: 0.75rem; color: #7986cb; text-align: right; margin-top: 8px;">※翌日リターン確定分のみ集計</div>
    </div>
    
    <h2>📋 監視銘柄の状況</h2>
"""
    for item in watch_data:
        html += '<div class="card">'
        if item["error"]:
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div><div class="error-text">⚠️ {item["error_msg"]}</div>'
        else:
            pos_class = "badge-up" if "上" in item["position"] else "badge-down"
            rsi_class = "rsi-high" if item["rsi"] >= 70 else ("rsi-low" if item["rsi"] <= 30 else "")
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div>'
            html += f'<div>現在値: <strong style="font-size:1.1rem;">{item["price"]:,}円</strong></div>'
            html += f'<div style="margin-top:8px;"><span class="badge {pos_class}">{item["position"]}</span><span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{item["rsi"]}</span></span></div>'
            
            # 【NEW】配列データを持っている場合はチャート用の箱(div)を用意する
            if "history_data" in item:
                html += f'<div id="chart-{item["code"]}" class="chart-container"></div>'

        html += '</div>'

    html += '<h2>🚀 本日の市場テーマ候補</h2><p style="font-size: 0.85rem; color: #888; margin-top:-5px;">出来高20日平均の2.5倍以上 ＋ 上昇</p>'
    
    if not scan_data:
        html += '<div class="card"><div class="error-text">本日の該当銘柄なし（またはデータ取得スキップ）</div></div>'
    else:
        for item in scan_data:
            html += f'<div class="card highlight"><div class="card-title">コード: {item["code"]}</div>'
            html += f'<div>終値: {item["price"]:,}円 <span class="badge badge-neutral" style="margin-left:10px;">出来高 {item["vol_ratio"]}倍</span></div></div>'
            
    # 【NEW】Pythonから渡されたデータをJSに渡し、チャートを描画する処理
    watch_data_json = json.dumps(watch_data, ensure_ascii=False)
    
    html += f"""
    <div class="glossary">
        <div style="font-weight:bold; font-size:1rem; margin-bottom:8px; border-bottom:1px solid #333; padding-bottom:5px;">💡 投資用語メモ</div>
        <dl>
            <dt>RSI（相対力指数）</dt><dd>株価の過熱感を指数化したもの。70％以上買われすぎ、30％以下売られすぎ。</dd>
            <dt>200日線（移動平均線）</dt><dd>過去200営業日（約1年）の平均。長期トレンドの最重要ライン。</dd>
            <dt>出来高急増（動意）</dt><dd>大口資金が流入し、新たなテーマが始まる初動サイン。</dd>
        </dl>
    </div>

    <script>
        // Pythonから出力された監視銘柄データを受け取る
        const watchData = {watch_data_json};
        
        watchData.forEach(item => {{
            // 履歴データが存在し、かつ描画用の枠がある場合のみ実行
            if(item.history_data && document.getElementById('chart-' + item.code)) {{
                const container = document.getElementById('chart-' + item.code);
                
                // チャートの初期化（ダークモード仕様）
                const chart = LightweightCharts.createChart(container, {{
                    layout: {{ background: {{ type: 'solid', color: '#1e1e1e' }}, textColor: '#d1d4dc', }},
                    grid: {{ vertLines: {{ color: '#2b2b43' }}, horzLines: {{ color: '#2b2b43' }} }},
                    rightPriceScale: {{ borderColor: '#2b2b43' }},
                    timeScale: {{ borderColor: '#2b2b43', timeVisible: false }},
                    handleScroll: false, // スマホでスクロール時に邪魔にならないよう無効化
                    handleScale: false
                }});

                // ローソク足シリーズの追加
                const candleSeries = chart.addCandlestickSeries({{
                    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                    wickUpColor: '#26a69a', wickDownColor: '#ef5350'
                }});

                // 出来高シリーズの追加（下部に重ねる）
                const volumeSeries = chart.addHistogramSeries({{
                    color: '#26a69a',
                    priceFormat: {{ type: 'volume' }},
                    priceScaleId: '', 
                }});
                
                // 出来高グラフの高さをチャートの下20%に抑える
                chart.priceScale('').applyOptions({{
                    scaleMargins: {{ top: 0.8, bottom: 0 }},
                }});

                const candleData = [];
                const volumeData = [];
                
                // データのマッピング
                item.history_data.forEach(d => {{
                    candleData.push({{ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }});
                    volumeData.push({{
                        time: d.time,
                        value: d.volume,
                        color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
                    }});
                }});

                // データをセットして表示範囲を調整
                candleSeries.setData(candleData);
                volumeSeries.setData(volumeData);
                chart.timeScale().fitContent();
            }}
        }});
    </script>
</body></html>"""
    
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)

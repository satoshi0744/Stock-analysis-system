import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def generate_files(watch_data, scan_data_dict):
    os.makedirs("public", exist_ok=True)
    os.makedirs("public/history", exist_ok=True)
    
    now = datetime.now(JST)
    now_str = now.strftime('%Y/%m/%d %H:%M')
    date_str = now.strftime('%Y-%m-%d')
    
    report_dict = {
        "updated_at": now_str,
        "date": date_str,
        "watch_data": watch_data,
        "scan_data": scan_data_dict # A/B群のデータをすべて保存
    }
    
    with open("public/report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
    history_path = f"public/history/{date_str}.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    summary = {"total_signals": 0, "win_rate": 0.0, "avg_return": 0.0, "expectancy": 0.0}
    if os.path.exists("public/performance_summary.json"):
        with open("public/performance_summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)
            
    # データ展開
    market_info = scan_data_dict.get("market_info", {"text": "判定不能", "is_good": False})
    scan_a = scan_data_dict.get("scan_a", [])
    scan_b = scan_data_dict.get("scan_b", [])
            
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
        .badge-signal {{ background-color: #673ab7; color: white; border: 1px solid #9575cd; }}
        .rsi-high {{ color: #ff5252; font-weight: bold; }}
        .rsi-low {{ color: #69f0ae; font-weight: bold; }}
        .highlight {{ border-left: 4px solid #ffab00; background-color: #2a2a2a; }}
        .stats-box {{ background-color: #1a237e; border: 1px solid #3949ab; border-radius: 8px; padding: 15px; margin-bottom: 20px; transition: all 0.3s; }}
        .stats-box summary {{ list-style: none; cursor: pointer; font-weight:bold; color:#c5cae9; outline: none; }}
        .stats-box summary::-webkit-details-marker {{ display: none; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 15px; }}
        .stat-item {{ text-align: center; background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }}
        .stat-value {{ font-size: 1.3rem; font-weight: bold; color: #fff; }}
        .stat-label {{ font-size: 0.75rem; color: #9fa8da; }}
        .glossary {{ background-color: #1a1a1a; padding: 15px; border-radius: 8px; font-size: 0.85rem; margin-top: 30px; border-top: 1px solid #333; }}
        .error-text {{ color: #757575; font-style: italic; font-size: 0.9rem; }}
        .update-time {{ font-size: 0.85rem; color: #888; text-align: right; margin-top: -15px; margin-bottom: 15px; }}
        .chart-container {{ width: 100%; height: 250px; margin-top: 15px; border: 1px solid #333; border-radius: 4px; overflow: hidden; }}
        .diff-up {{ color: #69f0ae; font-weight: bold; font-size: 0.95rem; margin-left: 5px; }}
        .diff-down {{ color: #ff5252; font-weight: bold; font-size: 0.95rem; margin-left: 5px; }}
        .diff-even {{ color: #9e9e9e; font-weight: bold; font-size: 0.95rem; margin-left: 5px; }}
        .action-link {{ display: inline-block; padding: 6px 12px; margin-top: 12px; margin-right: 8px; background-color: #1a237e; color: #e8eaf6; text-decoration: none; border-radius: 4px; font-size: 0.85rem; font-weight: bold; border: 1px solid #3949ab; }}
        .b-group-box {{ background-color: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
        .b-group-item {{ border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 8px; }}
        .b-group-item:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
    </style>
</head>
<body>
    <h1>📊 投資戦略ダッシュボード</h1>
    <div class="update-time">最終更新: {now_str}</div>

    <div style="background-color: #1e1e1e; padding: 10px 15px; border-radius: 6px; margin-bottom: 15px; border-left: 4px solid {'#2e7d32' if market_info['is_good'] else '#c62828'};">
        <span style="font-size: 0.9rem; color: #aaa;">本日の相場環境：</span> 
        <strong style="font-size: 1.1rem; color: #fff;">{market_info['text']}</strong>
    </div>

    <h2 style="color: #ffab00; border-left: 4px solid #ffab00; margin-top: 5px;">👑 本日の本命候補 (A群)</h2>
"""
    if not scan_a:
        html += '<div class="card"><div class="error-text">本日の鉄板条件クリア銘柄なし（休むも相場です）</div></div>'
    else:
        for item in scan_a:
            company_name = item.get("name", "")
            diff = item.get("price_diff", 0)
            diff_html = f'<span class="diff-up">(+{diff:,}円)</span>' if diff > 0 else (f'<span class="diff-down">({diff:,}円)</span>' if diff < 0 else f'<span class="diff-even">(±0円)</span>')

            html += f'<div class="card highlight"><div class="card-title">{item["code"]} {company_name}</div>'
            html += f'<div style="margin-bottom: 8px;">現在値: <strong style="font-size:1.1rem;">{item["price"]:,}円</strong> {diff_html}</div>'
            
            if item.get("signals"):
                html += '<div>'
                for sig in item["signals"]:
                    html += f'<span class="badge badge-signal">{sig}</span>'
                html += '</div>'
            
            html += f'<div><a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T" target="_blank" class="action-link">📊 株価詳細</a> <a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T/news" target="_blank" class="action-link">📰 ニュース</a></div>'

            if "history_data" in item:
                html += f'<div id="chart-scan-{item["code"]}" class="chart-container"></div>'
            html += '</div>'

    # 📝 2. B群（次点・研究用）の折りたたみ表示
    if scan_b:
        html += f"""
        <details class="b-group-box">
            <summary style="font-weight:bold; color:#888; outline: none; cursor:pointer;">📁 本日の次点候補（研究用ログ: {len(scan_b)}件）</summary>
            <div style="margin-top: 15px;">
        """
        for item in scan_b:
            company_name = item.get("name", "")
            diff = item.get("price_diff", 0)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            sigs = " ".join([f"[{s}]" for s in item.get("signals", [])])
            html += f"""
                <div class="b-group-item">
                    <div style="font-weight: bold; color: #bbb;">{item["code"]} {company_name} <span style="font-weight:normal; font-size:0.9rem; color:#888;">({item["price"]:,}円 / {diff_str}円)</span></div>
                    <div style="font-size: 0.85rem; color: #777; margin-top:3px;">{sigs}</div>
                </div>
            """
        html += "</div></details>"
            
    # 📈 パフォーマンス検証
    html += f"""
    <details class="stats-box">
        <summary>📈 A群シグナル検証データ（5営業日スイング）</summary>
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-value">{summary["total_signals"]}</div><div class="stat-label">総シグナル数</div></div>
            <div class="stat-item"><div class="stat-value">{summary["win_rate"]}%</div><div class="stat-label">勝率</div></div>
            <div class="stat-item"><div class="stat-value">{summary["avg_return"]}%</div><div class="stat-label">平均リターン</div></div>
            <div class="stat-item"><div class="stat-value">{summary["expectancy"]}%</div><div class="stat-label">期待値</div></div>
        </div>
        <div style="font-size: 0.8rem; color: #9fa8da; margin-top: 15px; background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; line-height: 1.5;">
            ※シグナル発生日の翌日始値で買い、5営業日後の終値で売却したと仮定したシミュレーション結果です。
        </div>
    </details>
    """

    # 📋 3. 監視銘柄の状況
    html += '<h2>📋 監視銘柄の状況</h2>'
    
    for item in watch_data:
        html += '<div class="card">'
        if item["error"]:
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div><div class="error-text">⚠️ {item["error_msg"]}</div>'
        else:
            pos_class = "badge-up" if "上" in item["position"] else "badge-down"
            rsi_class = "rsi-high" if item["rsi"] >= 70 else ("rsi-low" if item["rsi"] <= 30 else "")
            
            diff = item.get("price_diff", 0)
            diff_html = f'<span class="diff-up">(+{diff:,}円)</span>' if diff > 0 else (f'<span class="diff-down">({diff:,}円)</span>' if diff < 0 else f'<span class="diff-even">(±0円)</span>')

            html += f'<div class="card-title">{item["code"]} {item["name"]}</div>'
            html += f'<div>現在値: <strong style="font-size:1.1rem;">{item["price"]:,}円</strong> {diff_html}</div>'
            html += f'<div style="margin-top:8px; margin-bottom:4px;"><span class="badge {pos_class}">{item["position"]}</span><span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{item["rsi"]}</span></span></div>'
            
            if item.get("signals"):
                html += '<div style="margin-top: 4px; margin-bottom: 4px;">'
                for sig in item["signals"]:
                    html += f'<span class="badge badge-signal

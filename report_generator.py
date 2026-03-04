import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def load_previous_report():
    history_dir = "public/history"
    if os.path.exists(history_dir):
        files = sorted([f for f in os.listdir(history_dir) if f.endswith(".json")], reverse=True)
        now_date = datetime.now(JST).strftime('%Y-%m-%d')
        for f_name in files:
            if f_name != f"{now_date}.json":
                try:
                    with open(os.path.join(history_dir, f_name), "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception: pass
    return None

def generate_files(watch_data, scan_data_dict, prev_report=None):
    os.makedirs("public", exist_ok=True)
    os.makedirs("public/history", exist_ok=True)
    
    now = datetime.now(JST)
    now_str = now.strftime('%Y/%m/%d %H:%M')
    date_str = now.strftime('%Y-%m-%d')
    
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            order = list(json.load(f).keys())
        watch_data = sorted(watch_data, key=lambda x: order.index(x['code']) if x['code'] in order else 999)
    except Exception: pass
        
    report_dict = {"updated_at": now_str, "date": date_str, "watch_data": watch_data, "scan_data": scan_data_dict}
    with open("public/report.json", "w", encoding="utf-8") as f: json.dump(report_dict, f, ensure_ascii=False, indent=2)
    with open(f"public/history/{date_str}.json", "w", encoding="utf-8") as f: json.dump(report_dict, f, ensure_ascii=False, indent=2)

    summary = {"total_signals": 0, "win_rate": 0.0, "avg_return": 0.0, "expectancy": 0.0}
    if os.path.exists("public/performance_summary.json"):
        with open("public/performance_summary.json", "r", encoding="utf-8") as f: summary = json.load(f)
            
    market_info = scan_data_dict.get("market_info", {"text": "判定不能", "is_good": False, "nikkei_data": {}})
    nikkei = market_info.get("nikkei_data", {})
    scan_a = scan_data_dict.get("scan_a", [])
    scan_b = scan_data_dict.get("scan_b", [])

    nikkei_html = ""
    if nikkei:
        diff = nikkei.get('diff', 0)
        diff_str = f"+{diff:,}" if diff > 0 else f"{diff:,}"
        diff_color = "#69f0ae" if diff > 0 else ("#ff5252" if diff < 0 else "#9e9e9e")

        nikkei_html = f"""
        <div style="margin-top: 15px; padding: 12px 18px; background-color: rgba(0,0,0,0.3); border-radius: 8px; border: 1px solid #333;">
            <div style="font-size: 1.3rem; font-weight: bold; margin-bottom: 8px; color: #fff;">
                日経平均株価: <span style="font-size: 1.5rem;">{nikkei.get('close', 0):,}円</span>
                <span style="color: {diff_color}; font-size: 1.1rem; margin-left: 10px;">({diff_str}円)</span>
            </div>
            <div style="font-size: 0.9rem; color: #bbb; display: flex; gap: 20px;">
                <span>始値: {nikkei.get('open', 0):,}円</span>
                <span>高値: {nikkei.get('high', 0):,}円</span>
                <span>安値: {nikkei.get('low', 0):,}円</span>
            </div>
        </div>
        """
        
    reflection_html = ""
    if prev_report and prev_report.get("scan_a"):
        prev_date = prev_report.get("date", "前回")
        reflection_html += f'<h2 style="color: #b388ff; border-left: 4px solid #b388ff; margin-top: 25px; margin-bottom: 10px;">🔄 昨日のA群（本命）の答え合わせ [{prev_date}]</h2>'
        all_today_items = watch_data + scan_a + scan_b
        today_price_dict = {item["code"]: item.get("price") for item in all_today_items if "code" in item}

        for prev_item in prev_report["scan_a"]:
            code = prev_item.get("code")
            name = prev_item.get("name", "")
            prev_price = prev_item.get("price", 0)
            today_price = today_price_dict.get(code)

            if today_price and prev_price > 0:
                diff = today_price - prev_price
                pct = (diff / prev_price) * 100
                diff_str = f"+{diff:,}円" if diff > 0 else (f"{diff:,}円" if diff < 0 else "±0円")
                pct_str = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
                color_class = "diff-up" if diff > 0 else ("diff-down" if diff < 0 else "diff-even")
                color_hex = "#69f0ae" if diff > 0 else ("#ff5252" if diff < 0 else "#9e9e9e")

                reflection_html += f'''
                <div class="card" style="border-left: 4px solid {color_hex}; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: bold; color: #fff; font-size: 1.1rem;">{code} {name}</span>
                            <div style="font-size: 0.85rem; color: #aaa; margin-top: 4px;">昨日の推奨値: {prev_price:,}円</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; color: #aaa;">本日の終値</div>
                            <strong style="font-size: 1.2rem; color: #fff;">{today_price:,}円</strong>
                            <span class="{color_class}" style="margin-left: 8px;">{diff_str} ({pct_str})</span>
                        </div>
                    </div>
                </div>
                '''
            else:
                reflection_html += f'''
                <div class="card" style="border-left: 4px solid #757575; margin-bottom: 8px;">
                    <span style="font-weight: bold; color: #fff;">{code} {name}</span>
                    <span style="font-size: 0.85rem; color: #aaa; margin-left: 10px;">(本日の価格データ取得できず)</span>
                </div>
                '''

    top_pick_html = ""
    if scan_a and scan_a[0].get("is_top_pick"):
        top_item = scan_a[0]
        bold_pred = top_item.get("bold_prediction", "")
        if bold_pred:
            top_pick_html = f"""
            <div class="card" style="border: 2px solid #ffd700; background: linear-gradient(145deg, #2a2000, #1a1a1a); margin-top: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(255, 215, 0, 0.15);">
                <h2 style="color: #ffd700; margin-top: 0; border-bottom: 1px solid #554400; padding-bottom: 8px;">🌟 IPPOの渾身の一推し銘柄</h2>
                <div style="font-size: 1.3rem; font-weight: bold; color: #fff; margin-bottom: 10px;">
                    {top_item['code']} {top_item.get('name', '')} 
                    <span style="font-size: 0.95rem; font-weight: normal; margin-left: 12px; color: #ccc;">現在値: {top_item.get('price', 0):,}円</span>
                </div>
                <div class="ai-report" style="color: #e0e0e0; line-height: 1.8; font-size: 0.95rem;">
                    {bold_pred}
                </div>
            </div>
            """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投資戦略ダッシュボード</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 15px; line-height: 1.6; }}
        h1 {{ font-size: 1.4rem; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        h2 {{ font-size: 1.1rem; margin-top: 25px; color: #4db8ff; border-left: 4px solid #4db8ff; padding-left: 8px; }}
        .card {{ background-color: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        .card-title {{ font-weight: bold; font-size: 1.1rem; margin-bottom: 8px; color: #fff; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 5px; display: inline-block; margin-bottom: 4px; }}
        .badge-up {{ background-color: #2e7d32; color: white; }} .badge-down {{ background-color: #c62828; color: white; }}
        .badge-signal {{ background-color: rgba(103,58,183,0.15); color: #d1c4e9; border: 1px solid #673ab7; }}
        .badge-breakout {{ background-color: rgba(255,152,0,0.15); color: #ffe082; border: 1px solid #ff9800; font-size: 0.85rem; padding: 4px 10px; }}
        .badge-alert {{ background-color: rgba(244,67,54,0.15); color: #ffcdd2; border: 1px solid #f44336; }}
        .badge-reversal {{ background-color: rgba(3,169,244,0.15); color: #b3e5fc; border: 1px solid #03a9f4; }}
        .badge-pullback {{ background-color: rgba(76,175,80,0.15); color: #c8e6c9; border: 1px solid #4caf50; }}
        .badge-volume {{ background-color: rgba(255,255,255,0.1); color: #e0e0e0; border: 1px solid #757575; }}
        .rsi-high {{ color: #ff5252; font-weight: bold; }} .rsi-low {{ color: #69f0ae; font-weight: bold; }}
        .highlight {{ border-left: 4px solid #ffab00; background-color: #2a2a2a; }}
        .stats-box {{ background-color: #1a237e; border: 1px solid #3949ab; border-radius: 8px; padding: 15px; margin-bottom: 20px; transition: all 0.3s; }}
        .stats-box summary {{ list-style: none; cursor: pointer; font-weight:bold; color:#c5cae9; outline: none; }}
        .stats-box summary::-webkit-details-marker {{ display: none; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 15px; }}
        .stat-item {{ text-align: center; background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; }}
        .stat-value {{ font-size: 1.3rem; font-weight: bold; color: #fff; }} .stat-label {{ font-size: 0.75rem; color: #9fa8da; }}
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
        .ai-comment-box {{ background: linear-gradient(145deg, #1e253c, #151a2a); border-left: 4px solid #b388ff; border-radius: 6px; padding: 12px 15px; margin-top: 15px; font-size: 0.9rem; color: #e8eaf6; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
        .ai-comment-header {{ font-weight: bold; color: #b388ff; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }}
    </style>
</head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px;">
        <h1 style="margin: 0; border: none; padding: 0;">📊 投資戦略ダッシュボード</h1>
        <a href="analyzer.html" style="background-color: #1a237e; color: #4db8ff; text-decoration: none; padding: 8px 15px; border-radius: 4px; font-size: 0.9rem; font-weight: bold; border: 1px solid #3949ab;">🔍 個別銘柄分析を開く</a>
    </div>
    <div class="update-time">最終更新: {now_str}</div>

    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 6px; margin-bottom: 15px; border-left: 4px solid {'#2e7d32' if market_info['is_good'] else ('#fbc02d' if '調整' in market_info['text'] else '#c62828')};">
        <div style="margin-bottom: 5px;">
            <span style="font-size: 0.9rem; color: #aaa;">本日の相場環境：</span> 
            <strong style="font-size: 1.2rem; color: #fff;">{market_info['text']}</strong>
        </div>
        {nikkei_html}
    </div>

    {reflection_html}
    {top_pick_html}

    <h2 style="color: #ffab00; border-left: 4px solid #ffab00; margin-top: 5px;">👑 本日の条件達成銘柄</h2>
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

            rsi = item.get("rsi", "-")
            rsi_trend = item.get("rsi_trend", "")
            vol_text = item.get("vol_text", "")
            rsi_class = "rsi-high" if type(rsi) != str and rsi >= 70 else ("rsi-low" if type(rsi) != str and rsi <= 30 else "")
            
            html += f'<div style="margin-top:4px; margin-bottom:8px; display:flex; flex-wrap:wrap; gap:6px align-items:center;">'
            html += f'<span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{rsi}</span> <span style="color:#aaa; font-size:0.8rem;">({rsi_trend})</span></span>'
            html += f'<span style="font-size:0.9rem; margin-left:8px;">出来高: <span style="color:#aaa; font-size:0.8rem;">{vol_text}</span></span>'
            html += f'</div>'
            
            if item.get("signals"):
                html += '<div style="margin-top: 6px; margin-bottom: 6px; display:flex; flex-wrap:wrap; gap:4px;">'
                for sig in item["signals"]:
                    badge_cls = "badge-signal"
                    if "[BREAKOUT]" in sig: badge_cls = "badge-breakout"
                    elif "[ALERT]" in sig: badge_cls = "badge-alert"
                    elif "[REVERSAL]" in sig: badge_cls = "badge-reversal"
                    elif "[PULLBACK]" in sig: badge_cls = "badge-pullback"
                    elif "出来高" in sig: badge_cls = "badge-volume"
                    html += f'<span class="badge {badge_cls}">{sig}</span>'
                html += '</div>'
            
            html += f'<div><a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T" target="_blank" class="action-link">📊 株価詳細</a> <a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T/news" target="_blank" class="action-link">📰 ニュース</a></div>'

            ai_comment = item.get("ai_comment", "")
            if ai_comment:
                html += f'<div class="ai-comment-box"><div class="ai-comment-header"><span>🤖</span> AIテクニカル分析</div><div>{ai_comment}</div></div>'

            if "history_data" in item:
                html += f'<div style="position:relative; margin-top:15px;" id="chart-wrapper-{item["code"]}">'
                html += f'<div id="legend-{item["code"]}" style="position:absolute; top:8px; left:12px; z-index:10; font-size:0.85rem; padding:4px 8px; background:rgba(30,30,30,0.8); border-radius:4px; border:1px solid #444; color:#fff; display:flex; gap:12px;"></div>'
                html += f'<div id="chart-scan-{item["code"]}" style="width:100%; height:250px; border:1px solid #333; border-radius:4px; overflow:hidden;"></div>'
                html += f'</div>'
            html += '</div>'

    if scan_b:
        html += f"""
        <details class="b-group-box">
            <summary style="font-weight:bold; color:#888; outline: none; cursor:pointer;">📁 次点・監視用ログ（{len(scan_b)}件）</summary>
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
            
    html += f"""
    <details class="stats-box">
        <summary>📈 条件達成銘柄の検証データ（5営業日スイング）</summary>
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-value">{summary["total_signals"]}</div><div class="stat-label">総シグナル数</div></div>
            <div class="stat-item"><div class="stat-value">{summary["win_rate"]}%</div><div class="stat-label">全体勝率</div></div>
            <div class="stat-item"><div class="stat-value">{summary["avg_return"]}%</div><div class="stat-label">平均リターン</div></div>
            <div class="stat-item"><div class="stat-value">{summary.get("expectancy", "-")}%</div><div class="stat-label">期待値</div></div>
        </div>
    """
    
    strategies = summary.get("strategies", {})
    if strategies:
        html += """
        <div style="margin-top: 15px; border-top: 1px solid #3949ab; padding-top: 15px;">
            <div style="font-size: 0.85rem; font-weight: bold; color: #c5cae9; margin-bottom: 8px;">戦術別パフォーマンス</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; color: #e0e0e0;">
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: #9fa8da;">
                    <th style="padding: 6px 4px; text-align: left;">戦術</th>
                    <th style="padding: 6px 4px; text-align: right;">回数</th>
                    <th style="padding: 6px 4px; text-align: right;">勝率</th>
                    <th style="padding: 6px 4px; text-align: right;">平均リターン</th>
                </tr>
"""
        strategy_names = {"BREAKOUT": "🚀 上昇加速型", "PULLBACK": "🟢 押し目拾い型", "REVERSAL": "🔄 底打ち確認型"}
        for st_name in ["BREAKOUT", "PULLBACK", "REVERSAL"]:
            if st_name in strategies:
                st = strategies[st_name]
                display_name = strategy_names.get(st_name, st_name)
                html += f"""
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 6px 4px; font-weight: bold;">{display_name}</td>
                    <td style="padding: 6px 4px; text-align: right;">{st["total_signals"]}</td>
                    <td style="padding: 6px 4px; text-align: right;">{st["win_rate"]}%</td>
                    <td style="padding: 6px 4px; text-align: right;">{st["avg_return"]}%</td>
                </tr>
"""
        html += "</table></div>"

    html += """
        <div style="font-size: 0.8rem; color: #9fa8da; margin-top: 15px; background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; line-height: 1.5;">
            ※シグナル発生日の翌日始値で買い、5営業日後の終値で売却したと仮定したシミュレーション結果です。
        </div>
    </details>
    """

    html += '<h2>📋 監視銘柄の状況</h2>'
    
    for item in watch_data:
        html += '<div class="card">'
        if item.get("error"):
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div><div class="error-text">⚠️ {item.get("error_msg", "エラー")}</div>'
        else:
            pos_class = "badge-up" if "上" in item.get("position", "") else "badge-down"
            rsi_class = "rsi-high" if item.get("rsi", 50) >= 70 else ("rsi-low" if item.get("rsi", 50) <= 30 else "")
            diff = item.get("price_diff", 0)
            diff_html = f'<span class="diff-up">(+{diff:,}円)</span>' if diff > 0 else (f'<span class="diff-down">({diff:,}円)</span>' if diff < 0 else f'<span class="diff-even">(±0円)</span>')

            html += f'<div class="card-title">{item["code"]} {item.get("name", "")}</div>'
            html += f'<div>現在値: <strong style="font-size:1.1rem;">{item.get("price", 0):,}円</strong> {diff_html}</div>'
            
            rsi_trend = item.get("rsi_trend", "")
            vol_text = item.get("vol_text", "")
            html += f'<div style="margin-top:8px; margin-bottom:4px; display:flex; flex-wrap:wrap; gap:6px align-items:center;">'
            html += f'<span class="badge {pos_class}">{item.get("position", "")}</span>'
            html += f'<span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{item.get("rsi", "-")}</span> <span style="color:#aaa; font-size:0.8rem;">({rsi_trend})</span></span>'
            html += f'<span style="font-size:0.9rem; margin-left:8px;">出来高: <span style="color:#aaa; font-size:0.8rem;">{vol_text}</span></span>'
            html += f'</div>'
            
            if item.get("signals"):
                html += '<div style="margin-top: 6px; margin-bottom: 6px; display:flex; flex-wrap:wrap; gap:4px;">'
                for sig in item["signals"]:
                    badge_cls = "badge-signal"
                    if "[BREAKOUT]" in sig: badge_cls = "badge-breakout"
                    elif "[ALERT]" in sig: badge_cls = "badge-alert"
                    elif "[REVERSAL]" in sig: badge_cls = "badge-reversal"
                    elif "[PULLBACK]" in sig: badge_cls = "badge-pullback"
                    elif "出来高" in sig: badge_cls = "badge-volume"
                    html += f'<span class="badge {badge_cls}">{sig}</span>'
                html += '</div>'
            
            html += f'<div><a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T" target="_blank" class="action-link">📊 株価詳細</a> <a href="https://finance.yahoo.co.jp/quote/{item["code"]}.T/news" target="_blank" class="action-link">📰 ニュース</a></div>'

            ai_comment = item.get("ai_comment", "")
            if ai_comment:
                html += f'<div class="ai-comment-box"><div class="ai-comment-header"><span>🤖</span> AIテクニカル分析</div><div>{ai_comment}</div></div>'

            if "history_data" in item:
                html += f'<div style="position:relative; margin-top:15px;" id="chart-wrapper-{item["code"]}">'
                html += f'<div id="legend-{item["code"]}" style="position:absolute; top:8px; left:12px; z-index:10; font-size:0.85rem; padding:4px 8px; background:rgba(30,30,30,0.8); border-radius:4px; border:1px solid #444; color:#fff; display:flex; gap:12px;"></div>'
                html += f'<div id="chart-watch-{item["code"]}" style="width:100%; height:250px; border:1px solid #333; border-radius:4px; overflow:hidden;"></div>'
                html += f'</div>'

        html += '</div>'

    watch_data_json = json.dumps(watch_data, ensure_ascii=False)
    scan_a_json = json.dumps(scan_a, ensure_ascii=False)
    
    # 🚨【修正ポイント】f文字列をやめて通常の文字列にし、エラーを完全に回避しました
    html += """
    <div class="glossary">
        <div style="font-weight:bold; font-size:1rem; margin-bottom:8px; border-bottom:1px solid #333; padding-bottom:5px;">💡 投資用語メモ</div>
        <dl>
            <dt>RSI（相対力指数）</dt><dd>株価の過熱感を指数化したもの。70％以上買われすぎ、30％以下売られすぎ。</dd>
            <dt>200日線（移動平均線）</dt><dd>過去200営業日（約1年）の平均。長期トレンドの最重要ライン。</dd>
            <dt>出来高急増（動意）</dt><dd>大口資金が流入し、新たなテーマが始まる初動サイン。</dd>
        </dl>
    </div>

    <script>
        const watchData = """ + watch_data_json + """;
        const scanData = """ + scan_a_json + """;
        
        function renderChart(item, prefix) {
            const containerId = 'chart-' + prefix + '-' + item.code;
            if(item.history_data && document.getElementById(containerId)) {
                const container = document.getElementById(containerId);
                const chart = LightweightCharts.createChart(container, {
                    autoSize: true,
                    layout: { background: { type: 'solid', color: '#1e1e1e' }, textColor: '#d1d4dc', },
                    grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
                    rightPriceScale: { borderColor: '#2b2b43' },
                    timeScale: { borderColor: '#2b2b43', timeVisible: true },
                    handleScroll: false,
                    handleScale: false
                });
                const candleSeries = chart.addCandlestickSeries({
                    upColor: '#FF5252', downColor: '#26a69a', borderVisible: false,
                    wickUpColor: '#FF5252', wickDownColor: '#26a69a'
                });
                const ma25Series = chart.addLineSeries({
                    color: '#2962FF', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
                });
                const ma75Series = chart.addLineSeries({
                    color: '#FF5252', lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
                });
                const ma200Series = chart.addLineSeries({
                    color: '#FF9800', lineWidth: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
                });
                const volumeSeries = chart.addHistogramSeries({
                    color: '#26a69a', lastValueVisible: false, priceLineVisible: false,
                    priceFormat: { 
                        type: 'custom',
                        formatter: (price) => {
                            if (price >= 100000000) return (price / 100000000).toFixed(1) + '億';
                            if (price >= 10000) return (price / 10000).toFixed(1) + '万';
                            return price.toString();
                        }
                    },
                    priceScaleId: 'volume_scale',
                });
                chart.priceScale('volume_scale').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, });

                let lastMa25 = null; let lastMa75 = null;
                let lastMa200 = null;
                const candleData = []; const volumeData = []; const ma25Data = []; const ma75Data = [];
                const ma200Data = [];
                let lastTime = "";

                item.history_data.forEach(d => {
                    if (d.open != null && d.close != null && d.time !== lastTime) {
                        candleData.push({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close });
                        volumeData.push({ time: d.time, value: d.volume || 0, color: d.close >= d.open ? 'rgba(255, 82, 82, 0.5)' : 'rgba(38, 166, 154, 0.5)' });
                        if (d.ma25 !== undefined && d.ma25 !== null) { ma25Data.push({ time: d.time, value: d.ma25 }); lastMa25 = d.ma25.toFixed(1); }
                        if (d.ma75 !== undefined && d.ma75 !== null) { ma75Data.push({ time: d.time, value: d.ma75 }); lastMa75 = d.ma75.toFixed(1); }
                        if (d.ma200 !== undefined && d.ma200 !== null) { ma200Data.push({ time: d.time, value: d.ma200 }); lastMa200 = d.ma200.toFixed(1); }
                        lastTime = d.time;
                    }
                });

                candleSeries.setData(candleData); volumeSeries.setData(volumeData);
                ma25Series.setData(ma25Data); ma75Series.setData(ma75Data); ma200Series.setData(ma200Data);
                chart.timeScale().fitContent();
                const legend = document.getElementById('legend-' + item.code);
                if(legend) {
                    legend.innerHTML = `<div><span style="color:#2962FF; font-weight:bold;">■</span> MA25: ${lastMa25}</div>
                                        <div><span style="color:#FF5252; font-weight:bold;">■</span> MA75: ${lastMa75}</div>
                                        <div><span style="color:#FF9800; font-weight:bold;">■</span> MA200: ${lastMa200}</div>`;
                }
            }
        }

        watchData.forEach(item => renderChart(item, 'watch'));
        scanData.forEach(item => renderChart(item, 'scan'));
    </script>
</body></html>"""
    
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)
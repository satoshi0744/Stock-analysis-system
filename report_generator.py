import json
import os
from datetime import datetime

def generate_files(watch_data, scan_data):
    # 保存用のフォルダを作成
    os.makedirs("public", exist_ok=True)
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    
    # ---------------------------------------------------------
    # 1. JSONデータの生成（将来のAI分析やグラフ化用）
    # ---------------------------------------------------------
    report_dict = {
        "updated_at": now_str,
        "watch_data": watch_data,
        "scan_data": scan_data
    }
    with open("public/report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
    # ---------------------------------------------------------
    # 2. スマホ対応HTMLの生成（ダークモード・軽量CSS）
    # ---------------------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投資戦略ダッシュボード</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 15px; line-height: 1.6; }}
        h1 {{ font-size: 1.4rem; border-bottom: 2px solid #333; padding-bottom: 10px; }}
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
        .glossary {{ background-color: #1a1a1a; padding: 15px; border-radius: 8px; font-size: 0.85rem; margin-top: 30px; border-top: 1px solid #333; }}
        .glossary dt {{ font-weight: bold; color: #ffca28; margin-top: 10px; }}
        .glossary dd {{ margin-left: 0; margin-bottom: 10px; color: #bbb; }}
        .error-text {{ color: #757575; font-style: italic; font-size: 0.9rem; }}
        .update-time {{ font-size: 0.85rem; color: #888; text-align: right; }}
    </style>
</head>
<body>
    <h1>📊 投資戦略ダッシュボード</h1>
    <div class="update-time">最終更新: {now_str}</div>
    
    <h2>📋 監視銘柄の状況</h2>
"""
    # 監視銘柄のカード化
    for item in watch_data:
        html += '<div class="card">'
        if item["error"]:
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div>'
            html += f'<div class="error-text">⚠️ {item["error_msg"]}</div>'
        else:
            pos_class = "badge-up" if "上" in item["position"] else "badge-down"
            rsi_class = "rsi-high" if item["rsi"] >= 70 else ("rsi-low" if item["rsi"] <= 30 else "")
            html += f'<div class="card-title">{item["code"]} {item["name"]}</div>'
            html += f'<div>現在値: <strong style="font-size:1.1rem;">{item["price"]:,}円</strong></div>'
            html += f'<div style="margin-top:8px;">'
            html += f'<span class="badge {pos_class}">{item["position"]}</span>'
            html += f'<span style="font-size:0.9rem;">RSI: <span class="{rsi_class}">{item["rsi"]}</span></span>'
            html += f'</div>'
        html += '</div>'

    html += """
    <h2>🚀 本日の市場テーマ候補</h2>
    <p style="font-size: 0.85rem; color: #888; margin-top:-5px;">出来高20日平均の2.5倍以上 ＋ 上昇</p>
"""
    # 動意銘柄のカード化
    if not scan_data:
        html += '<div class="card"><div class="error-text">本日の該当銘柄なし（またはデータ取得スキップ）</div></div>'
    else:
        for item in scan_data:
            html += f'<div class="card highlight">'
            html += f'<div class="card-title">コード: {item["code"]}</div>'
            html += f'<div>終値: {item["price"]:,}円 <span class="badge badge-neutral" style="margin-left:10px;">出来高 {item["vol_ratio"]}倍</span></div>'
            html += '</div>'
            
    html += """
    <div class="glossary">
        <div style="font-weight:bold; font-size:1rem; margin-bottom:8px; border-bottom:1px solid #333; padding-bottom:5px;">💡 投資用語メモ</div>
        <dl>
            <dt>RSI（相対力指数）</dt>
            <dd>株価の過熱感を指数化したもの。70％以上で買われすぎ、30％以下で売られすぎの目安。50%が中心。</dd>
            <dt>200日線（移動平均線）</dt>
            <dd>過去200営業日（約1年）の平均。この線上にあれば長期上昇トレンド、下なら下落トレンド。</dd>
            <dt>出来高急増（動意）</dt>
            <dd>取引の急拡大。大口資金が流入し、新たなテーマが始まる初動サインとなることが多い。</dd>
        </dl>
    </div>
</body>
</html>
"""
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)

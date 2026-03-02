import requests

def get_ai_analysis(ticker_code, current_price, tech_data, news_list, api_key):
    if not api_key: return "APIキー未設定"

    model_name = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={api_key}"
    
    news_text = "\n".join([f"・{n['title']}" for n in news_list]) if news_list else "特になし"
    
    # 💡 指標の「見せ方」を細かく指定したプロンプト
    prompt = f"""
    銘柄:{ticker_code} / 現在値:{current_price}円
    テクニカルデータ:{tech_data}
    ニュース:{news_text}
    
    あなたはプロのAI参謀「IPPO」です。挨拶不要。
    提供されたデータを統合分析し、以下の構成でレポートを出力してください。
    ※重要: ```html などのマークダウン記法は絶対に避け、純粋なHTMLタグとテキストのみを出力してください。

    【出力構成ルール】
    1. 最初に「📊 主要テクニカル指標」という小見出し（<h4>タグ等）をつけ、指標を見やすく整理して箇条書き（<ul><li>）で出力してください。
       - ボリンジャーバンドは「±2σ」「±3σ」など、関連するものを1行にまとめるなどしてスッキリ見せること。
       - もし提供されたデータ内に「前日比」や「前日の数値」があれば、必ず併記して比較できるようにすること。
    2. その下に「💡 IPPOの分析見解」という小見出しをつけ、結論から鋭く語る200文字程度の分析コメントを記述してください。
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=30)
        res_data = response.json()

        if response.status_code == 200:
            answer = res_data['candidates'][0]['content']['parts'][0]['text']
            # 装飾タグの強制除去
            answer = answer.replace("```html\n", "").replace("```html", "").replace("```", "").strip()
            return answer
        else:
            err_msg = res_data.get('error', {}).get('message', '不明なエラー')
            return f"<div style='color:#ff4d4d;'>【APIエラー】<br>理由: {err_msg}</div>"

    except Exception as e:
        return f"<p style='color:red;'>通信エラー: {str(e)}</p>"
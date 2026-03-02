import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

def fetch_recent_news(ticker_code, source="google_rss", limit=5):
    """
    指定された情報源から最新ニュースを取得し、日付が新しい順（降順）に並び替えて返す。
    """
    news_items = []
    
    if source == "google_rss":
        # Google News RSS (キーワード検索)
        # 【修正箇所】検索クエリに「when:7d」を追加し、過去7日以内のニュースに限定することで速報性を高める
        query = urllib.parse.quote(f"{ticker_code} 株 when:7d")
        url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                xml_data = response.read()
            
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            
            if channel is not None:
                for item in channel.findall("item"):
                    title = item.find("title").text if item.find("title") is not None else "No Title"
                    link = item.find("link").text if item.find("link") is not None else ""
                    pubDate = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    
                    # 日付の変換 (例: "Tue, 27 Feb 2024 ...")
                    try:
                        dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
                        formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_date = pubDate
                        
                    news_items.append({
                        "title": title,
                        "publisher": "Google News",
                        "link": link,
                        "date": formatted_date
                    })
        except Exception as e:
            print(f"ニュース取得エラー: {e}")
            
    # 日付(date)を基準に、新しいものが上(降順)になるようソート
    news_items.sort(key=lambda x: x['date'], reverse=True)
    
    # ソートした後に指定件数(limit)だけ返す
    return news_items[:limit]

# --- テスト用 ---
if __name__ == "__main__":
    print("【テスト】最新ニュースを取得します...")
    news = fetch_recent_news("7203", limit=5)
    for n in news:
        print(f"[{n['date']}] {n['title']}")
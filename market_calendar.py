"""
東証の営業日判定モジュール。

設計方針:
- 個別銘柄（監視銘柄など変更されうるもの）には一切依存しない。
- 一次ソース: Yahoo!ファイナンス（日本）の日経平均株価（998407.O）時系列ページ。
- 予備ソース: ローカル保存済み日経平均データ + yfinance の ^N225（日経平均）。
- 日付はすべて日本標準時（JST）で扱う。
- 大引け確定（15:45 JST）より前の実行（深夜〜翌日開場前〜取引時間中）では、
  当日はまだ未確定として除外し、直近の確定営業日（前営業日など）を最新営業日として扱う。
"""
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from price_store import get_stock_df

JST = timezone(timedelta(hours=9))

YAHOO_JP_NIKKEI_HISTORY_URL = "https://finance.yahoo.co.jp/quote/998407.O/history"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 大引け(15:30)後、確定値が出揃うまでの余裕を見た時刻。これより前の「当日」は未確定扱い。
MARKET_CLOSE_CONFIRM_HOUR = 15
MARKET_CLOSE_CONFIRM_MINUTE = 45


def _fetch_from_yahoo_japan(timeout=15, retries=3):
    """Yahoo!ファイナンス（日本）の日経平均時系列から営業日リスト（昇順, 'YYYY-MM-DD'）を取得する。"""
    last_error = None
    for _ in range(retries):
        try:
            resp = requests.get(
                YAHOO_JP_NIKKEI_HISTORY_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            dates = set()
            for tr in soup.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                if len(cells) < 5:
                    continue
                m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", cells[0].get_text().strip())
                if not m:
                    continue
                # 終値セルが数値であることを確認（未確定・空欄行の除外）
                close_text = cells[4].get_text().strip().replace(",", "")
                try:
                    float(close_text)
                except ValueError:
                    continue
                dates.add(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
            if len(dates) >= 5:
                return sorted(dates)
            last_error = f"営業日行が不足（{len(dates)}件）。ページ構造が変わった可能性"
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(f"Yahoo!ファイナンス（日本）取得失敗: {last_error}")


def _fetch_from_yfinance_nikkei():
    """予備: yfinance の ^N225 から営業日リストを取得する。"""
    import yfinance as yf
    df = yf.Ticker("^N225").history(period="1mo")
    df = df.dropna(subset=["Close"])
    if df.empty:
        raise RuntimeError("yfinance ^N225 のデータが空")
    idx = df.index
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Tokyo")
    return sorted({d.strftime("%Y-%m-%d") for d in idx})


def get_trading_dates(now=None):
    """
    確定済みの東証営業日リストを返す。
    戻り値: (dates: list[str], source: str)
    大引け確定前（15:45 JST前）の当日分は除外する。
    """
    now = now or datetime.now(JST)
    try:
        dates = _fetch_from_yahoo_japan()
        source = "Yahoo!ファイナンス（日本）日経平均"
    except Exception as e_primary:
        try:
            dates = _fetch_from_yfinance_nikkei()
            source = f"yfinance ^N225（予備。一次ソース失敗: {e_primary}）"
        except Exception as e_backup:
            raise RuntimeError(f"営業日の取得に失敗（一次: {e_primary} / 予備: {e_backup}）")

    today_str = now.strftime("%Y-%m-%d")
    confirmed = now.replace(
        hour=MARKET_CLOSE_CONFIRM_HOUR, minute=MARKET_CLOSE_CONFIRM_MINUTE, second=0, microsecond=0
    )
    if now < confirmed:
        dates = [d for d in dates if d != today_str]
    return dates, source


def get_available_price_dates(now=None):
    """
    ローカル保存＋差分積み重ね（Yahoo!ファイナンス日本 / yfinance）によって
    現在取得・分析可能な営業日の集合を返す。
    """
    try:
        df = get_stock_df("^N225", now=now)
        if df is not None and not df.empty:
            return {d.strftime("%Y-%m-%d") for d in df.index}
    except Exception:
        pass
    try:
        dates, _ = get_trading_dates(now=now)
        return set(dates)
    except Exception:
        return set()


# 後方互換エイリアス
get_yfinance_available_dates = get_available_price_dates


if __name__ == "__main__":
    d, s = get_trading_dates()
    print("ソース:", s)
    print("直近の営業日:", d[-10:])
    print("利用可能データ日:", sorted(get_available_price_dates())[-5:])

"""
株価データのローカル保存＋差分積み重ね（インクリメンタル更新）モジュール。

設計方針:
1. 初回（または新規に監視銘柄・スキャン銘柄へ登録された時）のみ、過去500日分のデータを取得して
   `data/prices/{code}.csv` に保存する。
2. 2回目以降は毎回500日分を取り直さず、保存済みCSVの最終日より後の「差分（その日のデータ）」だけを
   取得して末尾に積み重ねる。
3. 差分取得は Yahoo!ファイナンス（日本）の時系列ページを優先利用し、yfinance の反映遅延（夜間・翌朝まで
   当日分が入らない問題）に左右されず、大引け後や日をまたいだ翌日開場前でも確実にデータを揃える。
4. 株式分割・併合などで過去価格が変動した場合は、重複日の終値乖離を検知して自動で再取得する。
"""
import os
import re
import threading
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRICE_DIR = os.path.join(BASE_DIR, "data", "prices")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 大引け(15:30)後、確定値が出揃う時刻。これより前の「当日」行は取引中・未確定として除外する
MARKET_CLOSE_CONFIRM_HOUR = 15
MARKET_CLOSE_CONFIRM_MINUTE = 45

# ローカルCSVに保持する最大営業日数（200日移動平均＋十分な余裕）
MAX_KEEP_ROWS = 400

_file_locks = {}
_global_lock = threading.Lock()


def _get_lock(key):
    with _global_lock:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


def _safe_filename(code):
    """'^N225' -> 'N225.csv', '7203' -> '7203.csv'"""
    clean = str(code).replace("^", "").replace(".T", "").strip()
    return f"{clean}.csv"


def _csv_path(code):
    os.makedirs(PRICE_DIR, exist_ok=True)
    return os.path.join(PRICE_DIR, _safe_filename(code))


def _confirmed_cutoff_date_str(now=None):
    """現在時刻(JST)において日足が確定している最新カレンダー日付('YYYY-MM-DD')を返す。"""
    now = now or datetime.now(JST)
    confirmed_time = now.replace(
        hour=MARKET_CLOSE_CONFIRM_HOUR,
        minute=MARKET_CLOSE_CONFIRM_MINUTE,
        second=0,
        microsecond=0,
    )
    if now < confirmed_time:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def _load_cached_df(code):
    path = _csv_path(code)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if df.empty or "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
        df = df.set_index("Date")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])
        return df
    except Exception:
        return None


def _save_cached_df(code, df):
    if df is None or df.empty:
        return
    path = _csv_path(code)
    out = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    out = out.dropna(subset=["Close"])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if len(out) > MAX_KEEP_ROWS:
        out = out.iloc[-MAX_KEEP_ROWS:]
    out_reset = out.reset_index()
    out_reset["Date"] = pd.to_datetime(out_reset["Date"]).dt.strftime("%Y-%m-%d")
    out_reset.to_csv(path, index=False, encoding="utf-8")


def _parse_num(text):
    cleaned = text.strip().replace(",", "")
    if not cleaned or cleaned in ("---", "-", ""):
        return None
    return float(cleaned)


def _fetch_recent_from_yahoo_japan(code, timeout=12, now=None):
    """
    Yahoo!ファイナンス（日本）の時系列ページから直近（約20営業日分）の4本値・出来高を取得する。
    code: '7203' などの銘柄コード、または '^N225'
    """
    is_nikkei = str(code) in ("^N225", "N225", "998407.O")
    yj_code = "998407.O" if is_nikkei else f"{str(code).replace('.T', '')}.T"
    url = f"https://finance.yahoo.co.jp/quote/{yj_code}/history"

    cutoff_date = _confirmed_cutoff_date_str(now)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    records = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 5:
            continue
        date_text = cells[0].get_text().strip()
        m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", date_text)
        if not m:
            continue
        d_str = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # 大引け確定前の当日データは除外
        if d_str > cutoff_date:
            continue

        o = _parse_num(cells[1].get_text())
        h = _parse_num(cells[2].get_text())
        l = _parse_num(cells[3].get_text())
        c = _parse_num(cells[4].get_text())
        if None in (o, h, l, c):
            continue

        if is_nikkei:
            v = 0.0
        else:
            v = _parse_num(cells[5].get_text()) if len(cells) >= 6 else 0.0
            if v is None:
                v = 0.0

        records.append({
            "Date": pd.to_datetime(d_str),
            "Open": o,
            "High": h,
            "Low": l,
            "Close": c,
            "Volume": v,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    return df.set_index("Date")


def _fetch_from_yfinance(code, start_str, end_str, now=None):
    """yfinance から指定期間のデータを取得する（初回500日取得、または長期差分の補完用）。"""
    is_nikkei = str(code) in ("^N225", "N225")
    yf_symbol = "^N225" if is_nikkei else f"{str(code).replace('.T', '')}.T"
    cutoff_date = _confirmed_cutoff_date_str(now)

    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(start=start_str, end=end_str)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.dropna(subset=["Close"])
    if df.empty:
        return pd.DataFrame()

    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Tokyo").tz_localize(None)
    else:
        df.index = df.index.tz_localize(None)

    df.index = pd.to_datetime(df.index.strftime("%Y-%m-%d"))
    df = df[df.index <= pd.to_datetime(cutoff_date)]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = 0.0
    return df[["Open", "High", "Low", "Close", "Volume"]]


def get_stock_df(code, target_date_str=None, days_initial=500, now=None):
    """
    銘柄の株価DataFrameを取得する。
    - キャッシュがあれば読み込み、不足している最新日（差分）のみを積み重ねて保存する。
    - キャッシュがなければ（新規登録銘柄など）初回のみ過去500日分を取得して保存する。
    """
    lock = _get_lock(_safe_filename(code))
    with lock:
        cutoff_date = _confirmed_cutoff_date_str(now)
        need_until = min(target_date_str, cutoff_date) if target_date_str else cutoff_date

        df = _load_cached_df(code)

        # 1. 初回取得（未保存の銘柄、またはデータ行数が足りない場合）
        if df is None or len(df) < 200:
            end_dt = datetime.now(JST)
            start_str = (end_dt - timedelta(days=days_initial)).strftime("%Y-%m-%d")
            end_str = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            df = _fetch_from_yfinance(code, start_str, end_str, now=now)

            # yfinance に直近（当日・前日）が未反映の場合に備え、Yahoo!ファイナンス日本で最新差分を積み重ねる
            if not df.empty:
                last_dt_str = df.index[-1].strftime("%Y-%m-%d")
                if last_dt_str < need_until:
                    try:
                        yj_df = _fetch_recent_from_yahoo_japan(code, now=now)
                        if not yj_df.empty:
                            new_rows = yj_df[yj_df.index > df.index[-1]]
                            if not new_rows.empty:
                                df = pd.concat([df, new_rows]).sort_index()
                    except Exception:
                        pass
                _save_cached_df(code, df)

        # 2. 2回目以降：ローカル保存済みデータに「差分（未取得日分）」だけを積み重ねる
        else:
            last_cached_dt = df.index[-1]
            last_cached_str = last_cached_dt.strftime("%Y-%m-%d")

            if last_cached_str < need_until:
                updated = False
                need_full_refetch = False

                # まず Yahoo!ファイナンス（日本）から直近差分を取得（引け後すぐ反映され遅延がない）
                try:
                    yj_df = _fetch_recent_from_yahoo_japan(code, now=now)
                    if not yj_df.empty:
                        # 株式分割・併合チェック: 重複する最終日の終値が1%以上乖離していたらフル再取得
                        if last_cached_dt in yj_df.index:
                            cached_close = float(df.loc[last_cached_dt, "Close"])
                            yj_close = float(yj_df.loc[last_cached_dt, "Close"])
                            if cached_close > 0 and abs(cached_close - yj_close) / cached_close > 0.01:
                                need_full_refetch = True

                        # キャッシュ最終日より新しい日が20営業日以上空いてギャップがある場合もyfinanceで間を埋める
                        earliest_yj_str = yj_df.index[0].strftime("%Y-%m-%d")
                        if earliest_yj_str > last_cached_str:
                            need_full_refetch = True

                        if not need_full_refetch:
                            new_rows = yj_df[yj_df.index > last_cached_dt]
                            if not new_rows.empty:
                                df = pd.concat([df, new_rows]).sort_index()
                                updated = True
                except Exception:
                    pass

                # 分割検知時や長期ギャップ時、またはYahoo!ファイナンス日本で未取得だった場合のフォールバック
                if need_full_refetch:
                    end_dt = datetime.now(JST)
                    start_str = (end_dt - timedelta(days=days_initial)).strftime("%Y-%m-%d")
                    end_str = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                    fresh_df = _fetch_from_yfinance(code, start_str, end_str, now=now)
                    if not fresh_df.empty:
                        df = fresh_df
                        try:
                            yj_df = _fetch_recent_from_yahoo_japan(code, now=now)
                            if not yj_df.empty:
                                new_rows = yj_df[yj_df.index > df.index[-1]]
                                if not new_rows.empty:
                                    df = pd.concat([df, new_rows]).sort_index()
                        except Exception:
                            pass
                        updated = True
                elif not updated or df.index[-1].strftime("%Y-%m-%d") < need_until:
                    # 差分期間だけを yfinance から取得して積み重ねる
                    start_str = last_cached_str
                    end_str = (datetime.now(JST) + timedelta(days=1)).strftime("%Y-%m-%d")
                    try:
                        diff_df = _fetch_from_yfinance(code, start_str, end_str, now=now)
                        if not diff_df.empty:
                            new_rows = diff_df[diff_df.index > df.index[-1]]
                            if not new_rows.empty:
                                df = pd.concat([df, new_rows]).sort_index()
                                updated = True
                    except Exception:
                        pass

                if updated:
                    _save_cached_df(code, df)

        if df is None or df.empty:
            return pd.DataFrame()

        if target_date_str:
            df = df[df.index <= pd.to_datetime(target_date_str)]
        return df.copy()

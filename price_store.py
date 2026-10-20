"""
株価データのローカル永続保存（過去10年分＋日次差分積み重ね）モジュール。

設計方針:
1. 初回（または新規に監視銘柄へ登録された時）に1回だけ、過去10年分（period="10y"）の
   日足データを一括取得して `data/prices/{code}.csv` に保存する。古いデータの切り捨ては行わない。
2. 2回目以降（毎日の定期実行）は、米国 yfinance を使わず、Yahoo!ファイナンス（日本）の
   時系列ページから「その日の差分データ（未取得営業日分）」だけを取得してCSV末尾に積み重ねる。
3. 株式分割・併合などで過去価格が変動した場合は、重複日の終値乖離（1%超）を自動検知して
   10年分を取り直し、価格の連続性を維持する。
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
    """過去データを切り捨てず、全期間（10年分＋日々の積み重ね）を保存する。"""
    if df is None or df.empty:
        return
    path = _csv_path(code)
    out = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    out = out.dropna(subset=["Close"])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    for col in ["Open", "High", "Low", "Close"]:
        out[col] = out[col].round(2)
    out["Volume"] = out["Volume"].fillna(0).astype("int64")
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
    日常の差分更新はこの関数だけで完結する。
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


def _fetch_initial_10y(code, period="10y", now=None):
    """
    新規銘柄の初回登録時（または株式分割による再構築時）のみ、過去10年分を一括取得する。
    直近の未反映分があれば Yahoo!ファイナンス（日本）のデータで末尾を補完する。
    """
    is_nikkei = str(code) in ("^N225", "N225")
    yf_symbol = "^N225" if is_nikkei else f"{str(code).replace('.T', '')}.T"
    cutoff_date = _confirmed_cutoff_date_str(now)

    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(period=period)
    if df is None or df.empty:
        df = pd.DataFrame()
    else:
        df = df.dropna(subset=["Close"])
        if not df.empty:
            if df.index.tz is not None:
                df.index = df.index.tz_convert("Asia/Tokyo").tz_localize(None)
            else:
                df.index = df.index.tz_localize(None)
            df.index = pd.to_datetime(df.index.strftime("%Y-%m-%d"))
            df = df[df.index <= pd.to_datetime(cutoff_date)]
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col not in df.columns:
                    df[col] = 0.0
            df = df[["Open", "High", "Low", "Close", "Volume"]]

    # 直近分を Yahoo!ファイナンス（日本）で補完
    try:
        yj_df = _fetch_recent_from_yahoo_japan(code, now=now)
        if not yj_df.empty:
            if df.empty:
                df = yj_df
            else:
                new_rows = yj_df[yj_df.index > df.index[-1]]
                if not new_rows.empty:
                    df = pd.concat([df, new_rows]).sort_index()
    except Exception:
        pass

    return df


def get_stock_df(code, target_date_str=None, now=None):
    """
    銘柄の株価DataFrame（過去10年分＋最新差分）を取得する。
    - ローカルCSVがあれば読み込み、不足している最新日（差分）のみを Yahoo!ファイナンス（日本）から積み重ねる。
    - ローカルCSVがなければ（新規登録銘柄など）初回のみ過去10年分を取得して保存する。
    """
    lock = _get_lock(_safe_filename(code))
    with lock:
        cutoff_date = _confirmed_cutoff_date_str(now)
        need_until = min(target_date_str, cutoff_date) if target_date_str else cutoff_date

        df = _load_cached_df(code)

        # 1. 初回取得（未保存の新規登録銘柄など）
        if df is None or df.empty:
            df = _fetch_initial_10y(code, period="10y", now=now)
            if not df.empty:
                _save_cached_df(code, df)

        # 2. 2回目以降：ローカル保存済みデータに Yahoo!ファイナンス（日本）から「差分」だけを積み重ねる
        else:
            last_cached_dt = df.index[-1]
            last_cached_str = last_cached_dt.strftime("%Y-%m-%d")

            if last_cached_str < need_until:
                need_full_rebuild = False
                updated = False

                try:
                    yj_df = _fetch_recent_from_yahoo_japan(code, now=now)
                    if not yj_df.empty:
                        # 株式分割・併合チェック: 重複する最終日の終値が1%以上乖離していたら10年分を再構築
                        if last_cached_dt in yj_df.index:
                            cached_close = float(df.loc[last_cached_dt, "Close"])
                            yj_close = float(yj_df.loc[last_cached_dt, "Close"])
                            if cached_close > 0 and abs(cached_close - yj_close) / cached_close > 0.01:
                                need_full_rebuild = True

                        # 20営業日以上の長期ブランクがある場合も再構築
                        earliest_yj_str = yj_df.index[0].strftime("%Y-%m-%d")
                        if earliest_yj_str > last_cached_str:
                            need_full_rebuild = True

                        if not need_full_rebuild:
                            new_rows = yj_df[yj_df.index > last_cached_dt]
                            if not new_rows.empty:
                                df = pd.concat([df, new_rows]).sort_index()
                                updated = True
                except Exception:
                    pass

                if need_full_rebuild:
                    fresh_df = _fetch_initial_10y(code, period="10y", now=now)
                    if not fresh_df.empty:
                        df = fresh_df
                        updated = True

                if updated:
                    _save_cached_df(code, df)

        if df is None or df.empty:
            return pd.DataFrame()

        if target_date_str:
            df = df[df.index <= pd.to_datetime(target_date_str)]
        return df.copy()


def summarize_long_term_context(df):
    """
    10年分の時系列データから、AI分析や長期判断に役立つ長期指標（52週高安・5年/10年レンジ位置）を算出する。
    """
    if df is None or len(df) < 250:
        return {}
    latest_close = float(df["Close"].iloc[-1])

    # 1年（約245営業日）
    df_1y = df.tail(245)
    high_1y = float(df_1y["High"].max())
    low_1y = float(df_1y["Low"].min())
    pct_from_1y_high = round((latest_close - high_1y) / high_1y * 100, 1) if high_1y > 0 else 0.0

    # 全保存期間（最大10年）
    years_span = round((df.index[-1] - df.index[0]).days / 365.25, 1)
    high_all = float(df["High"].max())
    low_all = float(df["Low"].min())
    pos_in_all = round((latest_close - low_all) / (high_all - low_all) * 100, 1) if high_all > low_all else 50.0

    return {
        "years_span": years_span,
        "high_1y": int(high_1y),
        "low_1y": int(low_1y),
        "pct_from_1y_high": pct_from_1y_high,
        "high_10y": int(high_all),
        "low_10y": int(low_all),
        "pos_in_10y_range_pct": pos_in_all,
    }

"""שכבת נתוני שוק (yfinance). מחזירה תמיד את מחיר הסגירה האחרון הזמין,
כך שסופי שבוע, חגים ושעות שהבורסה סגורה עובדים בלי טיפול מיוחד."""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def _last_close(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else None


def last_prices(tickers: list[str]) -> dict[str, float]:
    """מחיר אחרון (סגירה אחרונה, או מחיר חי אם הבורסה פתוחה) לכל סימול. סימול ללא נתונים מושמט."""
    tickers = sorted(set(tickers))
    out: dict[str, float] = {}
    if not tickers:
        return out
    try:
        # חלון של 10 ימים מכסה סוף שבוע ארוך וחגים
        df = yf.download(tickers, period="10d", interval="1d", auto_adjust=False,
                         progress=False, group_by="ticker", threads=True)
        for t in tickers:
            try:
                close = df[t]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
                price = _last_close(close)
                if price:
                    out[t] = price
            except (KeyError, TypeError):
                continue
    except Exception:
        pass
    # גיבוי לסימולים שחסרים (למשל כשההורדה הקבוצתית נכשלה חלקית)
    for t in tickers:
        if t in out:
            continue
        try:
            price = _last_close(yf.Ticker(t).history(period="10d", auto_adjust=False)["Close"])
            if price:
                out[t] = price
        except Exception:
            continue
    return out


# תווית -> (period, interval)
CHART_RANGES = {
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
}


def price_history(ticker: str, label: str) -> pd.DataFrame:
    """DataFrame עם עמודות date, price (ריק אם אין נתונים)."""
    period, interval = CHART_RANGES[label]
    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    if h is None or h.empty:
        return pd.DataFrame(columns=["date", "price"])
    idx = h.index.tz_localize(None) if getattr(h.index, "tz", None) is not None else h.index
    return pd.DataFrame({"date": idx, "price": h["Close"].astype(float).values}).dropna()

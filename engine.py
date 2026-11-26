"""מנוע המשחק: מצב, עמלות, מיסים, אימות ושמירה. ללא תלות ב-Streamlit / yfinance."""
from __future__ import annotations

import hashlib
import hmac
import os
import random
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import storage
from storage import ConflictError, StorageError

START_CASH = 10_000.00
FEE_RATE = 0.01        # 1% על כל קנייה וכל מכירה
TAX_RATE = 0.25        # 25% על רווח הון נטו (אם יש)
BENCH_TICKER = "SPY"
BOT_NAME = "S&P 500 Index (SPY)"
LEGACY_BOT_NAME = "מדד S&P 500 (SPY)"   # שם קודם; משחקים קיימים מועברים אוטומטית
MIN_TRADE = 1.00       # מינימום עסקה בדולרים
MIN_PASSWORD = 6
MAX_PASSWORD = 64

# נעילה אחת לכל התהליך: כל הסשנים של Streamlit חולקים את אותו מודול
LOCK = threading.RLock()

# הגנה בסיסית מפני ניחוש סיסמאות (בזיכרון בלבד)
_FAILS: dict[str, tuple[int, float]] = {}
MAX_FAILS = 5
LOCKOUT_SECONDS = 60

_BACKEND = None


class GameError(Exception):
    """שגיאה שמוצגת למשתמש (הודעה בעברית)."""


# ---------------------------------------------------------------- אחסון
def backend():
    global _BACKEND
    want_supabase = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))
    stale = want_supabase and not isinstance(_BACKEND, storage.SupabaseBackend) and getattr(_BACKEND, "auto", False)
    if _BACKEND is None or stale:
        _BACKEND = storage.default_backend(Path(__file__).with_name("game_data.json"))
        _BACKEND.auto = True   # נוצר אוטומטית (לא הוגדר ידנית בבדיקות), אפשר להחליף אותו
    return _BACKEND


def set_backend(b) -> None:
    """לבדיקות / הגדרה ידנית."""
    global _BACKEND
    _BACKEND = b


def storage_name() -> str:
    return backend().name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_state() -> dict:
    return {"version": 1, "game_start": None, "players": {}}


def load_state() -> dict:
    try:
        raw, rev = backend().load()
    except StorageError as e:
        raise GameError(str(e)) from e
    state = raw if raw else new_state()
    state.setdefault("players", {})
    state.setdefault("game_start", None)
    state["_rev"] = rev
    return state


def save_state(state: dict) -> None:
    """מעלה ConflictError אם המצב השתנה במקביל (ה-backend מזהה לפי rev)."""
    rev = state.get("_rev", 0)
    data = {k: v for k, v in state.items() if k != "_rev"}
    try:
        backend().save(data, rev)
    except StorageError as e:
        raise GameError(str(e)) from e
    state["_rev"] = rev + 1


class _NoSave(Exception):
    def __init__(self, value=None):
        self.value = value


def _transaction(fn):
    """טוען מצב, מריץ fn(state) ושומר. אם מישהו שמר באותו רגע (ConflictError) טוענים מחדש וחוזרים על הפעולה."""
    for attempt in range(8):
        with LOCK:
            state = load_state()
            try:
                result = fn(state)
            except _NoSave as ns:
                return ns.value
            try:
                save_state(state)
                return result
            except ConflictError:
                pass
        time.sleep(random.uniform(0.05, 0.25) * (attempt + 1))
    raise GameError("The server is busy. Try again in a moment.")


# ---------------------------------------------------------------- שחקנים וסיסמאות
def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def _blank_player(**extra) -> dict:
    p = {
        "cash": START_CASH,
        "positions": {},          # ticker -> {"shares": float, "cost_basis": float}
        "transactions": [],
        "fees_paid": 0.0,
        "taxes_paid": 0.0,
        "created": _now(),
    }
    p.update(extra)
    return p


def player_names(state: dict) -> list[str]:
    return sorted(n for n, p in state["players"].items() if not p.get("is_bot"))


def find_player(state: dict, username: str) -> str | None:
    """חיפוש שם משתמש ללא תלות באותיות גדולות/קטנות. מחזיר את השם המדויק השמור."""
    u = (username or "").strip().casefold()
    for n, p in state["players"].items():
        if not p.get("is_bot") and n.casefold() == u:
            return n
    return None


def register_player(name: str, password: str) -> str:
    """יוצר שחקן ומחזיר את שם המשתמש השמור."""
    name = (name or "").strip()
    if not (2 <= len(name) <= 24):
        raise GameError("Username must be 2 to 24 characters.")
    if name.casefold() == BOT_NAME.casefold():
        raise GameError("That name is reserved for the index bot.")
    if not (MIN_PASSWORD <= len(password or "") <= MAX_PASSWORD):
        raise GameError(f"Password must be at least {MIN_PASSWORD} characters.")

    def work(state):
        if any(n.casefold() == name.casefold() for n in state["players"]):
            raise GameError("That username is taken.")
        salt = secrets.token_hex(16)
        state["players"][name] = _blank_player(pw_salt=salt, pw_hash=_hash_pw(password, salt))
        return name

    return _transaction(work)


def authenticate(username: str, password: str) -> str | None:
    """מחזיר את שם המשתמש אם הפרטים נכונים, אחרת None. נועל ל-60 שניות אחרי 5 כשלונות."""
    key = (username or "").strip().casefold()
    fails, until = _FAILS.get(key, (0, 0.0))
    if fails >= MAX_FAILS and time.time() < until:
        raise GameError(f"Too many failed attempts. Try again in {int(until - time.time())} seconds.")
    state = load_state()
    name = find_player(state, username)
    if name:
        p = state["players"][name]
        ok = hmac.compare_digest(_hash_pw(password or "", p["pw_salt"]), p["pw_hash"])
    else:
        _hash_pw(password or "", "00" * 16)   # מאזן זמני תגובה, כדי לא לחשוף אילו שמות קיימים
        ok = False
    if ok:
        _FAILS.pop(key, None)
        return name
    fails = 1 if (fails >= MAX_FAILS and time.time() >= until) else fails + 1
    _FAILS[key] = (fails, time.time() + LOCKOUT_SECONDS)
    return None


# ---------------------------------------------------------------- בוט הייחוס
def ensure_bot(spy_price: float) -> bool:
    """יוצר את בוט ה-SPY (קנה בכל ה-$10,000, ללא עמלה, ולא פועל יותר). True אם נוצר עכשיו."""
    if not spy_price or spy_price <= 0:
        return False

    def work(state):
        if BOT_NAME in state["players"]:
            raise _NoSave(False)
        if LEGACY_BOT_NAME in state["players"]:        # שדרוג משחק קיים: רק משנים את שם הבוט
            state["players"][BOT_NAME] = state["players"].pop(LEGACY_BOT_NAME)
            return True
        shares = START_CASH / spy_price
        bot = _blank_player(is_bot=True)
        bot["cash"] = 0.0
        bot["positions"][BENCH_TICKER] = {"shares": shares, "cost_basis": START_CASH}
        bot["transactions"].append({
            "ts": _now(), "type": "buy", "ticker": BENCH_TICKER, "price": spy_price, "shares": shares,
            "gross": START_CASH, "fee": 0.0, "tax": 0.0, "realized_gain": 0.0, "cash_after": 0.0,
        })
        state["players"][BOT_NAME] = bot
        state["game_start"] = state.get("game_start") or _now()
        return True

    return _transaction(work)


# ---------------------------------------------------------------- חישובי עסקאות
def _r(x: float) -> float:
    return round(x + 0.0, 2)


def quote_buy(amount: float, price: float) -> dict:
    """amount = הסכום הכולל שיורד מהמזומן (כולל העמלה)."""
    fee = _r(amount * FEE_RATE)
    net = amount - fee
    return {"gross": _r(amount), "fee": fee, "invested": _r(net), "shares": net / price, "tax": 0.0}


def quote_sell(position: dict, amount: float | None, price: float) -> dict:
    """amount = שווי ברוטו של המכירה; None = למכור הכול. מחזיר פירוט כולל מס."""
    shares_held, basis = position["shares"], position["cost_basis"]
    value = shares_held * price
    sell_all = amount is None or amount >= value - 0.005
    if sell_all:
        shares_sold, gross, cost_part = shares_held, _r(value), basis
    else:
        shares_sold = amount / price
        gross = _r(amount)
        cost_part = basis * (shares_sold / shares_held)
    fee = _r(gross * FEE_RATE)
    # בסיס העלות כולל את עמלת הקנייה, ועמלת המכירה מקוזזת כאן: הרווח הוא נטו משתי העמלות
    gain = gross - fee - cost_part
    tax = _r(max(gain, 0.0) * TAX_RATE)
    return {
        "gross": gross, "fee": fee, "tax": tax, "net_cash": _r(gross - fee - tax),
        "shares": shares_sold, "cost_part": cost_part, "gain": gain, "sell_all": sell_all,
    }


# ---------------------------------------------------------------- ביצוע
def _get_human(state: dict, name: str) -> dict:
    p = state["players"].get(name)
    if not p or p.get("is_bot"):
        raise GameError("Player not found.")
    return p


def buy(name: str, ticker: str, amount: float, price: float, allowed: set[str] | None = None) -> dict:
    if allowed is not None and ticker not in allowed:
        raise GameError("Only S&P 500 stocks can be traded.")
    if not price or price <= 0:
        raise GameError("No valid price for this stock.")
    if amount < MIN_TRADE:
        raise GameError(f"Minimum trade is ${MIN_TRADE:.2f}.")

    def work(state):
        p = _get_human(state, name)
        if amount > p["cash"] + 0.004:
            raise GameError(f"Not enough cash. Available: ${p['cash']:,.2f}.")
        q = quote_buy(amount, price)
        p["cash"] = _r(p["cash"] - q["gross"])
        pos = p["positions"].setdefault(ticker, {"shares": 0.0, "cost_basis": 0.0})
        pos["shares"] += q["shares"]
        pos["cost_basis"] += q["gross"]          # כולל עמלת קנייה
        p["fees_paid"] = _r(p["fees_paid"] + q["fee"])
        tx = {"ts": _now(), "type": "buy", "ticker": ticker, "price": price, "shares": q["shares"],
              "gross": q["gross"], "fee": q["fee"], "tax": 0.0, "realized_gain": 0.0, "cash_after": p["cash"]}
        p["transactions"].append(tx)
        return tx

    return _transaction(work)


def sell(name: str, ticker: str, amount: float | None, price: float, allowed: set[str] | None = None) -> dict:
    """amount=None => מכירת כל הפוזיציה."""
    if allowed is not None and ticker not in allowed:
        raise GameError("Only S&P 500 stocks can be traded.")
    if not price or price <= 0:
        raise GameError("No valid price for this stock.")

    def work(state):
        p = _get_human(state, name)
        pos = p["positions"].get(ticker)
        if not pos or pos["shares"] <= 0:
            raise GameError("You don't own this stock.")
        value = pos["shares"] * price
        if amount is not None:
            if amount < MIN_TRADE and amount < value - 0.005:
                raise GameError(f"Minimum trade is ${MIN_TRADE:.2f}.")
            if amount > value + 0.005:
                raise GameError(f"You can sell up to ${value:,.2f} of this stock.")
        q = quote_sell(pos, amount, price)
        p["cash"] = _r(p["cash"] + q["net_cash"])
        if q["sell_all"]:
            del p["positions"][ticker]
        else:
            pos["shares"] -= q["shares"]
            pos["cost_basis"] -= q["cost_part"]
        p["fees_paid"] = _r(p["fees_paid"] + q["fee"])
        p["taxes_paid"] = _r(p["taxes_paid"] + q["tax"])
        tx = {"ts": _now(), "type": "sell", "ticker": ticker, "price": price, "shares": q["shares"],
              "gross": q["gross"], "fee": q["fee"], "tax": q["tax"], "realized_gain": _r(q["gain"]),
              "cash_after": p["cash"]}
        p["transactions"].append(tx)
        return tx

    return _transaction(work)


# ---------------------------------------------------------------- שווי וטבלת מובילים
def held_tickers(state: dict) -> set[str]:
    return {t for p in state["players"].values() for t in p["positions"]}


def holdings_value(player: dict, prices: dict[str, float]) -> float:
    total = 0.0
    for t, pos in player["positions"].items():
        # אם מחיר חסר זמנית, מעריכים לפי עלות כדי לא להציג שווי מוטעה של אפס
        total += pos["shares"] * prices[t] if t in prices else pos["cost_basis"]
    return total


def leaderboard(state: dict, prices: dict[str, float]) -> list[dict]:
    rows = []
    for name, p in state["players"].items():
        stocks = holdings_value(p, prices)
        total = p["cash"] + stocks
        rows.append({
            "name": name, "is_bot": bool(p.get("is_bot")), "total": total, "cash": p["cash"],
            "stocks": stocks, "return_pct": (total / START_CASH - 1) * 100,
            "fees": p["fees_paid"], "taxes": p["taxes_paid"], "spent": p["fees_paid"] + p["taxes_paid"],
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    bench = next((r["total"] for r in rows if r["is_bot"]), None)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["beats_bench"] = None if (r["is_bot"] or bench is None) else r["total"] > bench
    return rows

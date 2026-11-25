"""מנוע המשחק: מצב, עמלות, מיסים ושמירה ל-JSON. ללא תלות ב-Streamlit / yfinance."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

START_CASH = 10_000.00
FEE_RATE = 0.01        # 1% על כל קנייה וכל מכירה
TAX_RATE = 0.25        # 25% על רווח הון נטו (אם יש)
BENCH_TICKER = "SPY"
BOT_NAME = "מדד S&P 500 (SPY)"
MIN_TRADE = 1.00       # מינימום עסקה בדולרים

DATA_FILE = Path(os.environ.get("PAPER_DATA_FILE", Path(__file__).with_name("game_data.json")))

# נעילה אחת לכל התהליך: כל הסשנים של Streamlit חולקים את אותו מודול
LOCK = threading.RLock()

# הגנה בסיסית מפני ניחוש PIN (בזיכרון בלבד)
_FAILS: dict[str, tuple[int, float]] = {}
MAX_FAILS = 5
LOCKOUT_SECONDS = 60


class GameError(Exception):
    """שגיאה שמוצגת למשתמש (הודעה בעברית)."""


# ---------------------------------------------------------------- שמירה / טעינה

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_state() -> dict:
    return {"version": 1, "game_start": None, "players": {}}


def load_state() -> dict:
    with LOCK:
        if not DATA_FILE.exists():
            return new_state()
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            # לא מוחקים קובץ פגום: שומרים עותק ומתריעים
            backup = DATA_FILE.with_suffix(f".corrupt-{int(time.time())}.json")
            os.replace(DATA_FILE, backup)
            raise GameError(f"קובץ הנתונים היה פגום ונשמר בשם {backup.name}. מתחילים משחק חדש.") from e
        state.setdefault("players", {})
        state.setdefault("game_start", None)
        return state


def save_state(state: dict) -> None:
    """כתיבה אטומית: קובץ זמני ואז החלפה, כדי שקריסה באמצע לא תשחית את הנתונים."""
    with LOCK:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=DATA_FILE.parent, prefix=".tmp_game_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, DATA_FILE)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


# ---------------------------------------------------------------- שחקנים ו-PIN

def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 100_000).hex()


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
    """שמות השחקנים האנושיים (בלי הבוט), לתפריט ההתחברות."""
    return sorted(n for n, p in state["players"].items() if not p.get("is_bot"))


def register_player(name: str, pin: str) -> None:
    name = (name or "").strip()
    if not (2 <= len(name) <= 24):
        raise GameError("השם חייב להכיל 2 עד 24 תווים.")
    if name == BOT_NAME:
        raise GameError("השם הזה שמור לבוט המדד.")
    if not (len(pin) == 4 and pin.isdigit()):
        raise GameError("קוד ה-PIN חייב להיות בדיוק 4 ספרות.")
    with LOCK:
        state = load_state()
        if name in state["players"]:
            raise GameError("כבר קיים שחקן בשם הזה.")
        salt = secrets.token_hex(16)
        state["players"][name] = _blank_player(pin_salt=salt, pin_hash=_hash_pin(pin, salt))
        save_state(state)


def verify_pin(name: str, pin: str) -> bool:
    fails, until = _FAILS.get(name, (0, 0.0))
    if fails >= MAX_FAILS and time.time() < until:
        raise GameError(f"יותר מדי ניסיונות שגויים. נסו שוב בעוד {int(until - time.time())} שניות.")
    state = load_state()
    p = state["players"].get(name)
    ok = bool(
        p and not p.get("is_bot") and len(pin) == 4 and pin.isdigit()
        and hmac.compare_digest(_hash_pin(pin, p["pin_salt"]), p["pin_hash"])
    )
    if ok:
        _FAILS.pop(name, None)
    else:
        fails = 1 if (fails >= MAX_FAILS and time.time() >= until) else fails + 1
        _FAILS[name] = (fails, time.time() + LOCKOUT_SECONDS)
    return ok


# ---------------------------------------------------------------- בוט הייחוס

def ensure_bot(spy_price: float) -> bool:
    """יוצר את בוט ה-SPY (קנה בכל ה-$10,000, ללא עמלה, ולא פועל יותר). True אם נוצר עכשיו."""
    with LOCK:
        state = load_state()
        if BOT_NAME in state["players"]:
            return False
        if not spy_price or spy_price <= 0:
            return False
        bot = _blank_player(is_bot=True)
        bot["cash"] = 0.0
        bot["positions"][BENCH_TICKER] = {"shares": START_CASH / spy_price, "cost_basis": START_CASH}
        bot["transactions"].append({
            "ts": _now(), "type": "buy", "ticker": BENCH_TICKER, "price": spy_price,
            "shares": START_CASH / spy_price, "gross": START_CASH, "fee": 0.0, "tax": 0.0,
            "realized_gain": 0.0, "cash_after": 0.0,
        })
        state["players"][BOT_NAME] = bot
        if not state.get("game_start"):
            state["game_start"] = _now()
        save_state(state)
        return True


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

def buy(name: str, ticker: str, amount: float, price: float, allowed: set[str] | None = None) -> dict:
    if allowed is not None and ticker not in allowed:
        raise GameError("אפשר לסחור רק במניות מתוך S&P 500.")
    if not price or price <= 0:
        raise GameError("לא התקבל מחיר תקין למניה.")
    if amount < MIN_TRADE:
        raise GameError(f"עסקה מינימלית: ${MIN_TRADE:.2f}.")
    with LOCK:
        state = load_state()
        p = _get_human(state, name)
        if amount > p["cash"] + 0.004:
            raise GameError(f"אין מספיק מזומן. זמין: ${p['cash']:,.2f}.")
        q = quote_buy(amount, price)
        p["cash"] = _r(p["cash"] - q["gross"])
        pos = p["positions"].setdefault(ticker, {"shares": 0.0, "cost_basis": 0.0})
        pos["shares"] += q["shares"]
        pos["cost_basis"] += q["gross"]          # כולל עמלת קנייה
        p["fees_paid"] = _r(p["fees_paid"] + q["fee"])
        tx = {"ts": _now(), "type": "buy", "ticker": ticker, "price": price, "shares": q["shares"],
              "gross": q["gross"], "fee": q["fee"], "tax": 0.0, "realized_gain": 0.0, "cash_after": p["cash"]}
        p["transactions"].append(tx)
        save_state(state)
        return tx


def sell(name: str, ticker: str, amount: float | None, price: float, allowed: set[str] | None = None) -> dict:
    """amount=None => מכירת כל הפוזיציה."""
    if allowed is not None and ticker not in allowed:
        raise GameError("אפשר לסחור רק במניות מתוך S&P 500.")
    if not price or price <= 0:
        raise GameError("לא התקבל מחיר תקין למניה.")
    with LOCK:
        state = load_state()
        p = _get_human(state, name)
        pos = p["positions"].get(ticker)
        if not pos or pos["shares"] <= 0:
            raise GameError("אין לך מניות מהסוג הזה.")
        value = pos["shares"] * price
        if amount is not None:
            if amount < MIN_TRADE and amount < value - 0.005:
                raise GameError(f"עסקה מינימלית: ${MIN_TRADE:.2f}.")
            if amount > value + 0.005:
                raise GameError(f"אפשר למכור עד ${value:,.2f} ממניה זו.")
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
        save_state(state)
        return tx


def _get_human(state: dict, name: str) -> dict:
    p = state["players"].get(name)
    if not p or p.get("is_bot"):
        raise GameError("שחקן לא קיים.")
    return p


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

"""משחק סימולציית מניות (Paper Trading) לחברים. הרצה: streamlit run app.py"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import engine as E
import market as M
import sp500

st.set_page_config(page_title="משחק המניות", page_icon="📈", layout="wide")

# ---------------------------------------------------------------- RTL
st.markdown(
    """
<style>
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
[data-testid="stMetric"], .stTabs, .stRadio, .stSelectbox, .stNumberInput, .stTextInput,
.stAlert, .stExpander, .stCheckbox, .stCaption { direction: rtl; text-align: right; }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { justify-content: flex-start; }
/* מספרים, סימולים וגרפים נשארים משמאל לימין */
input, [data-baseweb="select"] div[value], .vega-embed, code { direction: ltr; text-align: left; }
.stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; justify-content: flex-end; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- נתונים בקאש
@st.cache_data(ttl=86_400, show_spinner=False)
def get_universe() -> dict[str, str]:
    return sp500.load_sp500()


@st.cache_data(ttl=60, show_spinner=False)
def cached_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    return M.last_prices(list(tickers))


@st.cache_data(ttl=300, show_spinner=False)
def cached_history(ticker: str, label: str) -> pd.DataFrame:
    return M.price_history(ticker, label)


def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def fmt_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).dt.tz_convert("Asia/Jerusalem").dt.strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------- אתחול מצב ובוט
try:
    state = E.load_state()
except E.GameError as err:
    st.error(str(err))
    state = E.new_state()

if E.BOT_NAME not in state["players"]:
    spy = M.last_prices([E.BENCH_TICKER]).get(E.BENCH_TICKER)
    if spy and E.ensure_bot(spy):
        state = E.load_state()
    elif not spy:
        st.warning("לא הצלחתי למשוך את מחיר SPY, ולכן בוט המדד עוד לא נוצר. נסו לרענן.")

universe = get_universe()
allowed = set(universe)
user = st.session_state.get("user")
if user and user not in state["players"]:
    user = st.session_state["user"] = None

# ---------------------------------------------------------------- סרגל צד: התחברות
with st.sidebar:
    st.header("👤 שחקן")
    if user:
        st.success(f"מחובר/ת: **{user}**")
        if st.button("התנתקות", use_container_width=True):
            st.session_state["user"] = None
            st.rerun()
    else:
        names = E.player_names(state)
        if names:
            who = st.selectbox("בחרו שחקן", names)
            pin = st.text_input("קוד PIN (4 ספרות)", type="password", max_chars=4, key="login_pin")
            if st.button("התחברות", type="primary", use_container_width=True):
                try:
                    if E.verify_pin(who, pin):
                        st.session_state["user"] = who
                        st.rerun()
                    else:
                        st.error("קוד PIN שגוי.")
                except E.GameError as err:
                    st.error(str(err))
        else:
            st.info("אין עדיין שחקנים. הירשמו למטה.")

    with st.expander("➕ שחקן חדש", expanded=not E.player_names(state)):
        new_name = st.text_input("שם", max_chars=24, key="reg_name")
        new_pin = st.text_input("קוד PIN (4 ספרות)", type="password", max_chars=4, key="reg_pin")
        new_pin2 = st.text_input("אימות PIN", type="password", max_chars=4, key="reg_pin2")
        if st.button("הרשמה", use_container_width=True):
            if new_pin != new_pin2:
                st.error("קודי ה-PIN לא זהים.")
            else:
                try:
                    E.register_player(new_name, new_pin)
                    st.session_state["user"] = new_name.strip()
                    st.rerun()
                except E.GameError as err:
                    st.error(str(err))

    st.divider()
    st.caption(
        f"הון התחלתי {fmt_usd(E.START_CASH)} · עמלה {E.FEE_RATE:.0%} על כל קנייה ומכירה · "
        f"מס רווחי הון {E.TAX_RATE:.0%} על הרווח נטו בלבד · מחירים: סגירה אחרונה / מחיר אחרון"
    )

# ---------------------------------------------------------------- כותרת
st.title("📈 משחק המניות")
if state.get("game_start"):
    st.caption(f"המשחק התחיל ב-{pd.to_datetime(state['game_start']).tz_convert('Asia/Jerusalem'):%d/%m/%Y}")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_board, tab_trade, tab_hist = st.tabs(["🏆 טבלת מובילים", "💼 אזור מסחר", "📜 היסטוריית עסקאות"])

# ---------------------------------------------------------------- טבלת מובילים
with tab_board:
    held = tuple(sorted(E.held_tickers(state)))
    prices = cached_prices(held) if held else {}
    missing = [t for t in held if t not in prices]
    if missing:
        st.warning("חסר מחיר זמני עבור: " + ", ".join(missing) + ". המניות האלה מוערכות לפי עלות.")

    rows = E.leaderboard(state, prices)
    if not rows:
        st.info("עוד אין נתונים. הירשמו והתחילו לסחור!")
    else:
        df = pd.DataFrame(rows)
        df["מנצח את המדד?"] = df["beats_bench"].map({True: "✅", False: "❌", None: "—"})
        df["שחקן"] = df.apply(lambda r: f"🤖 {r['name']}" if r["is_bot"] else r["name"], axis=1)
        view = df[["rank", "שחקן", "total", "return_pct", "cash", "stocks", "fees", "taxes", "spent", "מנצח את המדד?"]]
        view.columns = ["מקום", "שחקן", "שווי תיק כולל", "תשואה", "מזומן", "שווי מניות",
                        "עמלות ששולמו", "מיסים ששולמו", "סה״כ עמלות+מיסים", "מנצח את המדד?"]
        usd = st.column_config.NumberColumn(format="$%.2f")
        st.dataframe(
            view, hide_index=True, use_container_width=True,
            column_config={
                "שווי תיק כולל": usd, "מזומן": usd, "שווי מניות": usd, "עמלות ששולמו": usd,
                "מיסים ששולמו": usd, "סה״כ עמלות+מיסים": usd,
                "תשואה": st.column_config.NumberColumn(format="%+.2f%%"),
            },
        )
        chart_df = df[["שחקן", "total", "is_bot"]].rename(columns={"total": "שווי"})
        chart_df["סוג"] = chart_df["is_bot"].map({True: "מדד", False: "שחקן"})
        bars = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("שחקן:N", sort="-y", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("שווי:Q", title="שווי תיק ($)", scale=alt.Scale(zero=False)),
            color=alt.Color("סוג:N", legend=None, scale=alt.Scale(domain=["שחקן", "מדד"], range=["#4c78a8", "#9aa0a6"])),
            tooltip=["שחקן", alt.Tooltip("שווי:Q", format="$,.2f")],
        )
        start_line = alt.Chart(pd.DataFrame({"y": [E.START_CASH]})).mark_rule(strokeDash=[6, 4], color="gray").encode(y="y:Q")
        st.altair_chart(bars + start_line, use_container_width=True)
        st.caption("הקו המקווקו = ההון ההתחלתי. שחקן מנצח את המדד כשהשווי הכולל שלו גבוה מזה של בוט ה-SPY.")

# ---------------------------------------------------------------- אזור מסחר
with tab_trade:
    if not user:
        st.info("התחברו בסרגל הצד כדי לסחור.")
    else:
        me = state["players"][user]
        held_me = tuple(sorted(me["positions"]))
        sel_default = held_me[0] if held_me else "AAPL"
        my_prices = cached_prices(held_me) if held_me else {}
        stocks_val = E.holdings_value(me, my_prices)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("שווי כולל", fmt_usd(me["cash"] + stocks_val), f"{(me['cash'] + stocks_val) / E.START_CASH - 1:+.2%}")
        c2.metric("מזומן", fmt_usd(me["cash"]))
        c3.metric("שווי מניות", fmt_usd(stocks_val))
        c4.metric("עמלות + מיסים", fmt_usd(me["fees_paid"] + me["taxes_paid"]),
                  f"עמלות {fmt_usd(me['fees_paid'])} · מיסים {fmt_usd(me['taxes_paid'])}", delta_color="off")

        st.subheader("התיק שלי")
        if not me["positions"]:
            st.caption("התיק ריק. קנו מניה בטופס למטה.")
        else:
            prow = []
            for t, pos in sorted(me["positions"].items()):
                px = my_prices.get(t)
                val = pos["shares"] * px if px else None
                pl = val - pos["cost_basis"] if val is not None else None
                prow.append({
                    "מניה": t, "כמות": pos["shares"], "עלות ממוצעת": pos["cost_basis"] / pos["shares"],
                    "מחיר נוכחי": px, "שווי": val, "רווח/הפסד ($)": pl,
                    "רווח/הפסד (%)": (pl / pos["cost_basis"] * 100) if pl is not None else None,
                })
            usd = st.column_config.NumberColumn(format="$%.2f")
            st.dataframe(
                pd.DataFrame(prow), hide_index=True, use_container_width=True,
                column_config={
                    "כמות": st.column_config.NumberColumn(format="%.4f"), "עלות ממוצעת": usd, "מחיר נוכחי": usd,
                    "שווי": usd, "רווח/הפסד ($)": st.column_config.NumberColumn(format="%+.2f$"),
                    "רווח/הפסד (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                },
            )
            st.caption("רווח/הפסד כאן לא ממומש: כולל את עמלת הקנייה, לפני עמלת המכירה והמס שיחולו במכירה.")

        st.divider()
        left, right = st.columns([3, 2])

        with right:
            st.subheader("קנייה / מכירה")
            ticker = st.selectbox(
                "מניה (S&P 500)", sorted(universe),
                index=sorted(universe).index(sel_default) if sel_default in universe else 0,
                format_func=lambda t: f"{t} · {universe[t]}" if universe.get(t) else t,
                key="sel_ticker",
            )
            px_now = cached_prices((ticker,)).get(ticker)
            if px_now is None:
                st.error("לא הצלחתי למשוך מחיר למניה הזו כרגע.")
            else:
                st.metric(f"מחיר {ticker}", fmt_usd(px_now))

            side = st.radio("פעולה", ["קנייה", "מכירה"], horizontal=True, key="side")
            pos = me["positions"].get(ticker)

            if side == "קנייה":
                amount = st.number_input("סכום לקנייה ($, כולל עמלה)", min_value=1.0, value=min(500.0, max(1.0, me["cash"])),
                                         step=50.0, format="%.2f", key="buy_amt")
                if px_now:
                    q = E.quote_buy(amount, px_now)
                    st.info(f"עמלה (1%): {fmt_usd(q['fee'])}  ·  מושקע: {fmt_usd(q['invested'])}  ·  כמות: {q['shares']:.4f} מניות")
                if st.button("בצע קנייה", type="primary", use_container_width=True, disabled=px_now is None):
                    fresh = M.last_prices([ticker]).get(ticker)
                    try:
                        tx = E.buy(user, ticker, float(amount), fresh, allowed)
                        st.session_state["flash"] = (
                            f"נקנו {tx['shares']:.4f} מניות {ticker} ב-{fmt_usd(tx['price'])} (עמלה {fmt_usd(tx['fee'])})")
                        st.rerun()
                    except E.GameError as err:
                        st.error(str(err))
            else:
                if not pos:
                    st.warning(f"אין לך מניות {ticker} למכירה.")
                else:
                    value = pos["shares"] * px_now if px_now else 0.0
                    st.caption(f"בבעלותך: {pos['shares']:.4f} מניות ששוות {fmt_usd(value)}")
                    sell_all = st.checkbox("מכור את כל הפוזיציה", key="sell_all")
                    amount = None
                    if not sell_all:
                        amount = st.number_input("סכום למכירה ($, ברוטו)", min_value=1.0,
                                                 max_value=max(1.0, round(value, 2)), value=max(1.0, round(value / 2, 2)),
                                                 step=50.0, format="%.2f", key="sell_amt")
                    if px_now:
                        q = E.quote_sell(pos, amount, px_now)
                        st.info(
                            f"עמלה (1%): {fmt_usd(q['fee'])}  ·  רווח נטו: {fmt_usd(q['gain'])}  ·  "
                            f"מס (25%): {fmt_usd(q['tax'])}\n\nלמזומן יתווסף: **{fmt_usd(q['net_cash'])}**")
                    if st.button("בצע מכירה", type="primary", use_container_width=True, disabled=px_now is None):
                        fresh = M.last_prices([ticker]).get(ticker)
                        try:
                            tx = E.sell(user, ticker, None if sell_all else float(amount), fresh, allowed)
                            st.session_state["flash"] = (
                                f"נמכרו {tx['shares']:.4f} מניות {ticker} ב-{fmt_usd(tx['price'])} · "
                                f"עמלה {fmt_usd(tx['fee'])} · מס {fmt_usd(tx['tax'])}")
                            st.rerun()
                        except E.GameError as err:
                            st.error(str(err))

        with left:
            st.subheader(f"גרף מחיר: {ticker}")
            rng = st.radio("טווח", list(M.CHART_RANGES), index=2, horizontal=True, key="rng")
            hist = cached_history(ticker, rng)
            if hist.empty:
                st.warning("אין נתוני גרף זמינים.")
            else:
                line = alt.Chart(hist).mark_line().encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("price:Q", title="מחיר ($)", scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip("date:T", title="תאריך", format="%d/%m/%Y %H:%M"),
                             alt.Tooltip("price:Q", title="מחיר", format="$,.2f")],
                )
                st.altair_chart(line, use_container_width=True)
                first, last = hist["price"].iloc[0], hist["price"].iloc[-1]
                st.caption(f"שינוי בטווח: {(last / first - 1):+.2%}")

# ---------------------------------------------------------------- היסטוריה
with tab_hist:
    if not user:
        st.info("התחברו כדי לראות את ההיסטוריה שלכם.")
    else:
        txs = state["players"][user]["transactions"]
        if not txs:
            st.caption("אין עדיין עסקאות.")
        else:
            h = pd.DataFrame(txs)[::-1].reset_index(drop=True)
            out = pd.DataFrame({
                "זמן": fmt_ts(h["ts"]),
                "פעולה": h["type"].map({"buy": "קנייה", "sell": "מכירה"}),
                "מניה": h["ticker"], "מחיר": h["price"], "כמות": h["shares"], "סכום ברוטו": h["gross"],
                "עמלה": h["fee"], "מס": h["tax"], "רווח ממומש (נטו)": h["realized_gain"], "מזומן אחרי": h["cash_after"],
            })
            usd = st.column_config.NumberColumn(format="$%.2f")
            st.dataframe(out, hide_index=True, use_container_width=True, column_config={
                "מחיר": usd, "סכום ברוטו": usd, "עמלה": usd, "מס": usd, "מזומן אחרי": usd,
                "כמות": st.column_config.NumberColumn(format="%.4f"),
                "רווח ממומש (נטו)": st.column_config.NumberColumn(format="%+.2f$"),
            })

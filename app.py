"""Stock Game: paper trading with friends. Run: streamlit run app.py"""
from __future__ import annotations

import html
import os

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Stock Game", page_icon="📈", layout="wide")

SECRETS_ERROR = None
# Pass Supabase settings from st.secrets to env vars (the engine doesn't depend on Streamlit)
try:
    for _k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
except Exception as _e:   # secrets missing or malformed: shown in a banner below
    SECRETS_ERROR = str(_e)

import engine as E  # noqa: E402
import market as M  # noqa: E402
import sp500  # noqa: E402

UP, DOWN, MUTED, LINE = "#22c55e", "#ef4444", "#8a9bb0", "#223044"

# ---------------------------------------------------------------- styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#0b0f14;--card:#121923;--card2:#17202c;--line:#223044;--txt:#e6edf5;--mut:#8a9bb0;
      --up:#22c55e;--down:#ef4444;--acc:#38bdf8;--gold:#f5c542;}
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li,
.stApp button, .stApp input, .stApp textarea, .stApp td, .stApp th {font-family:'Inter',system-ui,sans-serif;}
.stApp{background:radial-gradient(900px 420px at 90% -8%, rgba(56,189,248,.10), transparent 60%),
       radial-gradient(700px 380px at 0% 0%, rgba(34,197,94,.07), transparent 60%), var(--bg);}
.block-container{padding-top:2.2rem;max-width:1280px;}
footer{visibility:hidden;}
[data-testid="stSidebar"]{background:var(--card);border-right:1px solid var(--line);}
h1,h2,h3{letter-spacing:-.02em;}

.hero{margin:0 0 1.2rem 0}
.hero .title{font-size:2.5rem;font-weight:800;letter-spacing:-.03em;
  background:linear-gradient(90deg,#e6edf5,#38bdf8 60%,#22c55e);-webkit-background-clip:text;background-clip:text;color:transparent;}
.hero .sub{color:var(--mut);margin-top:.2rem}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:.6rem 0}
.chip{background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:5px 14px;font-size:.85rem;color:var(--txt)}
.chip b{color:var(--mut);font-weight:500;margin-right:6px}
.chip.hl{border-color:rgba(56,189,248,.5);background:rgba(56,189,248,.08)}

.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:var(--up)} .down{color:var(--down)} .mut{color:var(--mut)}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:.4rem 0 1.2rem}
.card{background:linear-gradient(160deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.card .lbl{color:var(--mut);font-size:.82rem;text-transform:uppercase;letter-spacing:.06em}
.card .val{font-size:1.75rem;font-weight:700;margin-top:4px}
.card .sub{font-size:.85rem;margin-top:2px;color:var(--mut)}

.podium{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin:.4rem 0 1.4rem}
.pod{background:linear-gradient(160deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:18px 20px}
.pod.r1{border-color:rgba(245,197,66,.6);box-shadow:0 10px 36px rgba(245,197,66,.10)}
.pod .medal{font-size:1.7rem}
.pod .nm{font-size:1.2rem;font-weight:700;margin-top:4px}
.pod .tot{font-size:1.9rem;font-weight:800;margin-top:6px}
.pod .ret{font-weight:600}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:600;
  background:rgba(138,155,176,.15);color:var(--mut);margin-top:8px}
.badge.up{background:rgba(34,197,94,.15);color:var(--up)} .badge.down{background:rgba(239,68,68,.15);color:var(--down)}
.badge.acc{background:rgba(56,189,248,.15);color:var(--acc)}

.tbl-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:16px;background:var(--card)}
.tbl{width:100%;border-collapse:collapse;font-size:.93rem}
.tbl th{color:var(--mut);font-weight:500;text-align:left;padding:.75rem 1rem;border-bottom:1px solid var(--line);white-space:nowrap;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
.tbl td{padding:.75rem 1rem;border-bottom:1px solid rgba(34,48,68,.55);white-space:nowrap}
.tbl tr:last-child td{border-bottom:0}
.tbl tr.me td{background:rgba(56,189,248,.08)}
.tbl tr.bot td{color:var(--mut)}
.tbl td.r,.tbl th.r{text-align:right}

.pricehead{display:flex;justify-content:space-between;align-items:baseline;margin:.2rem 0 .6rem}
.pricehead .tk{font-size:1.5rem;font-weight:800} .pricehead .co{color:var(--mut);font-size:.9rem}
.pricehead .px{font-size:2.1rem;font-weight:800}
.quote{background:var(--card2);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin:.4rem 0 .8rem}
.quote .row{display:flex;justify-content:space-between;padding:3px 0}
.quote .row.total{border-top:1px solid var(--line);margin-top:6px;padding-top:8px;font-weight:700}

[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important;border-radius:18px!important;background:rgba(18,25,35,.6)}
.stButton>button,[data-testid="stFormSubmitButton"]>button{border-radius:12px;font-weight:700;padding:.6rem 1rem;border:0}
.st-key-btn_sell button{background:var(--down)!important;color:#fff!important}
.st-key-btn_buy button{background:var(--up)!important;color:#04130a!important}
.st-key-btn_buy button:hover,.st-key-btn_sell button:hover{filter:brightness(1.1)}
.stTabs [data-baseweb="tab"]{font-weight:600;font-size:1rem}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- helpers
def esc(x) -> str:
    return html.escape(str(x))


def money(x: float) -> str:
    return f"${x:,.2f}"


def smoney(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


def pct(x: float) -> str:
    return f"{x:+.2f}%"


def tone(x: float) -> str:
    return "up" if x > 0.004 else ("down" if x < -0.004 else "")


def num(text: str, cls: str = "") -> str:
    return f'<span class="num {cls}">{esc(text)}</span>'


def card(label: str, value: str, sub: str = "") -> str:
    return f'<div class="card"><div class="lbl">{label}</div><div class="val">{value}</div><div class="sub">{sub}</div></div>'


def table(headers: list[tuple[str, bool]], rows: list[tuple[list[str], str]]) -> str:
    """headers: (title, right_aligned); rows: (cells_html, row_class)."""
    th = "".join(f'<th class="{"r" if r else ""}">{h}</th>' for h, r in headers)
    body = ""
    for cells, cls in rows:
        tds = "".join(f'<td class="{"r" if headers[i][1] else ""}">{c}</td>' for i, c in enumerate(cells))
        body += f'<tr class="{cls}">{tds}</tr>'
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def ts_local(ts: str) -> str:
    return pd.to_datetime(ts, utc=True).tz_convert("Asia/Jerusalem").strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------- cached market data
@st.cache_data(ttl=86_400, show_spinner=False)
def get_universe() -> dict[str, str]:
    return sp500.load_sp500()


@st.cache_data(ttl=60, show_spinner=False)
def cached_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    return M.last_prices(list(tickers))


@st.cache_data(ttl=300, show_spinner=False)
def cached_history(ticker: str, label: str) -> pd.DataFrame:
    return M.price_history(ticker, label)


def price_chart(hist: pd.DataFrame) -> alt.Chart:
    up = hist["price"].iloc[-1] >= hist["price"].iloc[0]
    color = UP if up else DOWN
    lo, hi = float(hist["price"].min()), float(hist["price"].max())
    pad = max((hi - lo) * 0.08, hi * 0.002)
    dom = [lo - pad, hi + pad]
    x = alt.X("date:T", title=None, axis=alt.Axis(labelColor=MUTED, grid=False, domain=False, ticks=False))
    y = alt.Y("price:Q", title=None, scale=alt.Scale(domain=dom, nice=False),
              axis=alt.Axis(format="$.2f", labelColor=MUTED, gridColor="#1b2634", domain=False, ticks=False))
    base = alt.Chart(hist).encode(x=x, y=y)
    area = base.mark_area(line=False, color=alt.Gradient(
        gradient="linear", x1=1, x2=1, y1=1, y2=0,
        stops=[alt.GradientStop(color=color + "00", offset=0), alt.GradientStop(color=color + "55", offset=1)],
    )).encode(y2=alt.datum(dom[0]))
    line = base.mark_line(color=color, strokeWidth=2.2)
    pts = base.mark_circle(opacity=0, size=260).encode(tooltip=[
        alt.Tooltip("date:T", title="Date", format="%d %b %Y %H:%M"),
        alt.Tooltip("price:Q", title="Price", format="$,.2f")])
    return alt.layer(area, line, pts).properties(height=340, background="transparent").configure_view(strokeWidth=0)


# ---------------------------------------------------------------- load state + benchmark bot
try:
    state = E.load_state()
except E.GameError as err:
    st.error(str(err))
    st.stop()   # don't continue with an empty state: it would look like the data was wiped

if E.BOT_NAME not in state["players"]:
    spy = M.last_prices([E.BENCH_TICKER]).get(E.BENCH_TICKER)
    if spy and E.ensure_bot(spy):
        state = E.load_state()
    elif not spy:
        st.warning("Couldn't fetch the SPY price, so the index bot hasn't been created yet. Try refreshing.")

universe = get_universe()
allowed = set(universe)
tickers_sorted = sorted(universe)
user = st.session_state.get("user")
if user and user not in state["players"]:
    user = st.session_state["user"] = None

# ---------------------------------------------------------------- sidebar: login
with st.sidebar:
    st.markdown("### 👤 Player")
    if user:
        st.success(f"Logged in as **{user}**")
        if st.button("Log out", use_container_width=True):
            st.session_state["user"] = None
            st.rerun()
    else:
        with st.form("login_form"):
            login_name = st.text_input("Username")
            login_pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary", use_container_width=True):
                try:
                    who = E.authenticate(login_name, login_pw)
                    if who:
                        st.session_state["user"] = who
                        st.rerun()
                    else:
                        st.error("Wrong username or password.")
                except E.GameError as err:
                    st.error(str(err))

        with st.expander("➕ New player", expanded=not E.player_names(state)):
            with st.form("register_form"):
                new_name = st.text_input("Choose a username", max_chars=24)
                new_pw = st.text_input(f"Password (min {E.MIN_PASSWORD} characters)", type="password")
                new_pw2 = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Sign up", use_container_width=True):
                    if new_pw != new_pw2:
                        st.error("Passwords don't match.")
                    else:
                        try:
                            st.session_state["user"] = E.register_player(new_name, new_pw)
                            st.rerun()
                        except E.GameError as err:
                            st.error(str(err))

    st.divider()
    st.caption(f"💾 Storage: {E.storage_name()}")

# ---------------------------------------------------------------- storage warning
if E.storage_name() != "Supabase" and not os.environ.get("PAPER_DATA_FILE"):
    st.error(
        "⚠️ Supabase is NOT connected. Players and trades are saved in a temporary local file and will be lost "
        "when the app restarts. Add SUPABASE_URL and SUPABASE_SERVICE_KEY under App settings → Secrets."
        + (f"\n\nSecrets error: `{SECRETS_ERROR}`" if SECRETS_ERROR else ""))

# ---------------------------------------------------------------- header
start = ""
if state.get("game_start"):
    start = f" · started {pd.to_datetime(state['game_start']).tz_convert('Asia/Jerusalem'):%d %b %Y}"
st.markdown(
    f'<div class="hero"><div class="title">📈 Stock Game</div>'
    f'<div class="sub">Paper trading with friends. Can you beat the S&amp;P 500?{start}</div>'
    f'<div class="chips">'
    f'<span class="chip"><b>Starting cash</b>{money(E.START_CASH)}</span>'
    f'<span class="chip"><b>Fee</b>{E.FEE_RATE:.0%} per buy &amp; sell</span>'
    f'<span class="chip"><b>Capital gains tax</b>{E.TAX_RATE:.0%} on net profit</span>'
    f'<span class="chip"><b>Prices</b>latest close / live</span></div></div>',
    unsafe_allow_html=True,
)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_board, tab_trade, tab_hist = st.tabs(["🏆 Leaderboard", "💼 Trade", "📜 History"])

# ---------------------------------------------------------------- leaderboard
with tab_board:
    held = tuple(sorted(E.held_tickers(state)))
    prices = cached_prices(held) if held else {}
    missing = [t for t in held if t not in prices]
    if missing:
        st.warning("Temporarily missing prices for: " + ", ".join(missing) + ". Those holdings are valued at cost.")

    rows = E.leaderboard(state, prices)
    if not rows:
        st.info("Nothing here yet. Sign up and start trading!")
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        pods = ""
        for r in rows[:3]:
            if r["is_bot"]:
                badge = '<span class="badge acc">Benchmark</span>'
            elif r["beats_bench"] is True:
                badge = '<span class="badge up">Beating the index</span>'
            elif r["beats_bench"] is False:
                badge = '<span class="badge down">Behind the index</span>'
            else:
                badge = ""
            nm = ("🤖 " if r["is_bot"] else "") + esc(r["name"])
            pods += (
                f'<div class="pod {"r1" if r["rank"] == 1 else ""}"><div class="medal">{medals[r["rank"]]}</div>'
                f'<div class="nm">{nm}</div><div class="tot">{num(money(r["total"]))}</div>'
                f'<div class="ret {tone(r["return_pct"])}">{num(pct(r["return_pct"]))}</div>{badge}</div>'
            )
        st.markdown(f'<div class="podium">{pods}</div>', unsafe_allow_html=True)

        headers = [("#", False), ("Player", False), ("Total value", True), ("Return", True), ("Cash", True),
                   ("Stocks", True), ("Fees paid", True), ("Taxes paid", True), ("Fees + taxes", True), ("Beats index?", False)]
        trs = []
        for r in rows:
            beats = {True: "✅", False: "❌", None: "—"}[r["beats_bench"]]
            name = ("🤖 " if r["is_bot"] else "") + esc(r["name"])
            trs.append(([str(r["rank"]), f"<b>{name}</b>", num(money(r["total"])),
                         num(pct(r["return_pct"]), tone(r["return_pct"])), num(money(r["cash"])),
                         num(money(r["stocks"])), num(money(r["fees"])), num(money(r["taxes"])),
                         num(money(r["spent"])), beats],
                        "bot" if r["is_bot"] else ("me" if r["name"] == user else "")))
        st.markdown(table(headers, trs), unsafe_allow_html=True)
        st.caption("Ranked by total value (cash + current stock value). The 🤖 bot bought SPY with the full "
                   f"{money(E.START_CASH)} on day one and never trades.")

# ---------------------------------------------------------------- trade
with tab_trade:
    if not user:
        st.info("Log in from the sidebar to start trading.")
    else:
        me = state["players"][user]
        held_me = tuple(sorted(me["positions"]))
        my_prices = cached_prices(held_me) if held_me else {}
        stocks_val = E.holdings_value(me, my_prices)
        total = me["cash"] + stocks_val
        ret = (total / E.START_CASH - 1) * 100

        st.markdown(
            '<div class="cards">'
            + card("Total value", num(money(total)), f'<span class="{tone(ret)}">{num(pct(ret))}</span> vs. start')
            + card("Cash", num(money(me["cash"])))
            + card("Stocks", num(money(stocks_val)))
            + card("Fees + taxes", num(money(me["fees_paid"] + me["taxes_paid"])),
                   f'{num(money(me["fees_paid"]))} fees · {num(money(me["taxes_paid"]))} taxes')
            + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("#### My portfolio")
        if not me["positions"]:
            st.caption("Your portfolio is empty. Buy a stock using the form below.")
        else:
            headers = [("Stock", False), ("Shares", True), ("Avg cost", True), ("Price", True),
                       ("Value", True), ("P/L ($)", True), ("P/L (%)", True)]
            trs = []
            for t, pos in sorted(me["positions"].items()):
                px = my_prices.get(t)
                val = pos["shares"] * px if px else None
                pl = (val - pos["cost_basis"]) if val is not None else None
                trs.append(([f"<b>{esc(t)}</b>", num(f"{pos['shares']:.4f}"), num(money(pos["cost_basis"] / pos["shares"])),
                             num(money(px)) if px else "—", num(money(val)) if val is not None else "—",
                             num(smoney(pl), tone(pl)) if pl is not None else "—",
                             num(pct(pl / pos["cost_basis"] * 100), tone(pl)) if pl is not None else "—"], ""))
            st.markdown(table(headers, trs), unsafe_allow_html=True)
            st.caption("Unrealized P/L includes the buy fee but not the sell fee or tax that apply when you sell.")

        st.markdown("&nbsp;")
        left, right = st.columns([3, 2], gap="large")
        sel_default = held_me[0] if held_me else "AAPL"

        with right:
            with st.container(border=True):
                st.markdown("#### Buy / Sell")
                ticker = st.selectbox(
                    "Stock (S&P 500)", tickers_sorted,
                    index=tickers_sorted.index(sel_default) if sel_default in universe else 0,
                    format_func=lambda t: f"{t} · {universe[t]}" if universe.get(t) else t, key="sel_ticker")
                px_now = cached_prices((ticker,)).get(ticker)
                st.markdown(
                    f'<div class="pricehead"><div><div class="tk">{esc(ticker)}</div>'
                    f'<div class="co">{esc(universe.get(ticker, ""))}</div></div>'
                    f'<div class="px">{num(money(px_now)) if px_now else "—"}</div></div>',
                    unsafe_allow_html=True)
                if px_now is None:
                    st.error("Couldn't fetch a price for this stock right now.")

                side = st.radio("Action", ["Buy", "Sell"], horizontal=True, key="side")
                pos = me["positions"].get(ticker)

                if side == "Buy":
                    amount = st.number_input("Amount to spend ($, fee included)", min_value=1.0,
                                             value=min(500.0, max(1.0, me["cash"])), step=50.0, format="%.2f", key="buy_amt")
                    if px_now:
                        q = E.quote_buy(amount, px_now)
                        shares_txt = f"{q['shares']:.4f}"
                        st.markdown(
                            '<div class="quote">'
                            f'<div class="row"><span class="mut">Fee (1%)</span>{num(money(q["fee"]))}</div>'
                            f'<div class="row"><span class="mut">Invested</span>{num(money(q["invested"]))}</div>'
                            f'<div class="row total"><span>Shares you get</span>{num(shares_txt)}</div></div>',
                            unsafe_allow_html=True)
                    if st.button(f"Buy {ticker}", use_container_width=True, disabled=px_now is None, key="btn_buy"):
                        fresh = M.last_prices([ticker]).get(ticker)
                        try:
                            tx = E.buy(user, ticker, float(amount), fresh, allowed)
                            st.session_state["flash"] = (f"Bought {tx['shares']:.4f} shares of {ticker} at "
                                                         f"{money(tx['price'])} (fee {money(tx['fee'])})")
                            st.rerun()
                        except E.GameError as err:
                            st.error(str(err))
                else:
                    if not pos or not px_now:
                        st.warning(f"You don't own any {ticker}." if not pos else "No price available.")
                    else:
                        value = pos["shares"] * px_now
                        st.caption(f"You own {pos['shares']:.4f} shares worth {money(value)}")
                        sell_all = st.checkbox("Sell my entire position", key="sell_all")
                        amount = None
                        if not sell_all:
                            amount = st.number_input("Amount to sell ($, before fee)", min_value=1.0,
                                                     max_value=max(1.0, round(value, 2)),
                                                     value=max(1.0, round(value / 2, 2)), step=50.0, format="%.2f", key="sell_amt")
                        q = E.quote_sell(pos, amount, px_now)
                        st.markdown(
                            '<div class="quote">'
                            f'<div class="row"><span class="mut">Fee (1%)</span>{num(money(q["fee"]))}</div>'
                            f'<div class="row"><span class="mut">Net profit</span>{num(smoney(q["gain"]), tone(q["gain"]))}</div>'
                            f'<div class="row"><span class="mut">Tax (25%)</span>{num(money(q["tax"]))}</div>'
                            f'<div class="row total"><span>Cash you receive</span>{num(money(q["net_cash"]))}</div></div>',
                            unsafe_allow_html=True)
                        if st.button(f"Sell {ticker}", use_container_width=True, key="btn_sell"):
                            fresh = M.last_prices([ticker]).get(ticker)
                            try:
                                tx = E.sell(user, ticker, None if sell_all else float(amount), fresh, allowed)
                                st.session_state["flash"] = (
                                    f"Sold {tx['shares']:.4f} shares of {ticker} at {money(tx['price'])} · "
                                    f"fee {money(tx['fee'])} · tax {money(tx['tax'])}")
                                st.rerun()
                            except E.GameError as err:
                                st.error(str(err))

        with left:
            with st.container(border=True):
                head, rng_col = st.columns([1, 2])
                head.markdown(f"#### {esc(ticker)} price")
                rng = rng_col.radio("Range", list(M.CHART_RANGES), index=2, horizontal=True,
                                    key="rng", label_visibility="collapsed")
                hist = cached_history(ticker, rng)
                if hist.empty:
                    st.warning("No chart data available.")
                else:
                    st.altair_chart(price_chart(hist), use_container_width=True, theme=None)
                    chg = hist["price"].iloc[-1] / hist["price"].iloc[0] - 1
                    st.markdown(f'Change over range: <span class="{tone(chg)}">{num(f"{chg:+.2%}")}</span>',
                                unsafe_allow_html=True)

# ---------------------------------------------------------------- history
with tab_hist:
    if not user:
        st.info("Log in to see your trade history.")
    else:
        txs = state["players"][user]["transactions"]
        if not txs:
            st.caption("No trades yet.")
        else:
            headers = [("Time", False), ("Action", False), ("Stock", False), ("Price", True), ("Shares", True),
                       ("Gross", True), ("Fee", True), ("Tax", True), ("Realized P/L", True), ("Cash after", True)]
            trs = []
            for t in reversed(txs[-200:]):
                is_buy = t["type"] == "buy"
                act = f'<span class="badge {"up" if is_buy else "down"}">{"BUY" if is_buy else "SELL"}</span>'
                trs.append(([esc(ts_local(t["ts"])), act, f"<b>{esc(t['ticker'])}</b>", num(money(t["price"])),
                             num(f"{t['shares']:.4f}"), num(money(t["gross"])), num(money(t["fee"])),
                             num(money(t["tax"])), "—" if is_buy else num(smoney(t["realized_gain"]), tone(t["realized_gain"])),
                             num(money(t["cash_after"]))], ""))
            st.markdown(table(headers, trs), unsafe_allow_html=True)
            if len(txs) > 200:
                st.caption(f"Showing the latest 200 of {len(txs)} trades.")

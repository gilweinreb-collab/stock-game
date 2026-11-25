"""רשימת מניות S&P 500. מנסים לרענן מוויקיפדיה (פעם ב-7 ימים); אם אין רשת - רשימה מובנית."""
from __future__ import annotations

import json
import time
from io import StringIO
from pathlib import Path

CACHE_FILE = Path(__file__).with_name("sp500_cache.json")
CACHE_MAX_AGE = 7 * 24 * 3600
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# רשימת גיבוי (קירוב להרכב המדד; הרשימה המלאה והעדכנית נמשכת מוויקיפדיה כשיש רשת)
FALLBACK = """
A AAPL ABBV ABNB ABT ACGL ACN ADBE ADI ADM ADP ADSK AEE AEP AES AFL AIG AIZ AJG AKAM ALB ALGN ALL ALLE AMAT AMCR AMD
AME AMGN AMP AMT AMZN ANET AON AOS APA APD APH APO APP APTV ARE ATO AVB AVGO AVY AWK AXON AXP AZO BA BAC BALL BAX BBY
BDX BEN BF-B BG BIIB BK BKNG BKR BLDR BLK BMY BR BRK-B BRO BSX BX BXP C CAG CAH CARR CAT CB CBOE CBRE CCI CCL CDNS CDW
CEG CF CFG CHD CHRW CHTR CI CINF CL CLX CMCSA CME CMG CMI CMS CNC CNP COF COIN COO COP COR COST CPAY CPB CPRT CPT CRL
CRM CRWD CSCO CSGP CSX CTAS CTRA CTSH CTVA CVS CVX CZR D DAL DASH DD DDOG DE DECK DELL DG DGX DHI DHR DIS DLR DLTR DOC
DOV DOW DPZ DRI DTE DUK DVA DVN DXCM EA EBAY ECL ED EFX EG EIX EL ELV EMN EMR ENPH EOG EPAM EQIX EQR EQT ERIE ES ESS
ETN ETR EVRG EW EXC EXE EXPD EXPE EXR F FANG FAST FCX FDS FDX FE FFIV FI FICO FIS FITB FOX FOXA FRT FSLR FTNT FTV GD
GDDY GE GEHC GEN GEV GILD GIS GL GLW GM GNRC GOOG GOOGL GPC GPN GRMN GS GWW HAL HAS HBAN HCA HD HIG HII HLT HOLX HON
HPE HPQ HRL HSIC HST HSY HUBB HUM HWM IBM ICE IDXX IEX IFF INCY INTC INTU INVH IP IPG IQV IR IRM ISRG IT ITW IVZ J JBHT
JBL JCI JKHY JNJ JPM K KDP KEY KEYS KHC KIM KKR KLAC KMB KMI KMX KO KR KVUE L LDOS LEN LH LHX LII LIN LKQ LLY LMT LNT
LOW LRCX LULU LUV LVS LW LYB LYV MA MAA MAR MAS MCD MCHP MCK MCO MDLZ MDT MET META MGM MHK MKC MKTX MLM MMC MMM MNST MO
MOH MOS MPC MPWR MRK MRNA MS MSCI MSFT MSI MTB MTCH MTD MU NCLH NDAQ NDSN NEE NEM NFLX NI NKE NOC NOW NRG NSC NTAP NTRS
NUE NVDA NVR NWS NWSA NXPI O ODFL OKE OMC ON ORCL ORLY OTIS OXY PANW PAYC PAYX PCAR PCG PEG PEP PFE PFG PG PGR PH PHM
PKG PLD PLTR PM PNC PNR PNW PODD POOL PPG PPL PRU PSA PSX PTC PWR PYPL QCOM RCL REG REGN RF RJF RL RMD ROK ROL ROP ROST
RSG RTX RVTY SBAC SBUX SCHW SHW SJM SLB SMCI SNA SNPS SO SOLV SPG SPGI SRE STE STLD STT STX STZ SW SWK SWKS SYF SYK SYY
T TAP TDG TDY TECH TEL TER TFC TGT TJX TKO TMO TMUS TPL TPR TRGP TRMB TROW TRV TSCO TSLA TSN TT TTWO TXN TXT TYL UAL
UBER UDR UHS ULTA UNH UNP UPS URI USB V VICI VLO VLTO VMC VRSK VRSN VRTX VST VTR VTRS VZ WAB WAT WDC WEC WELL WFC WM
WMB WMT WRB WST WTW WY WYNN XEL XOM XYL YUM ZBH ZBRA ZTS
""".split()


def _from_wikipedia() -> dict[str, str]:
    import pandas as pd
    import requests

    r = requests.get(WIKI_URL, headers={"User-Agent": "paper-trading-game/1.0"}, timeout=10)
    r.raise_for_status()
    df = pd.read_html(StringIO(r.text))[0]
    out = {str(s).replace(".", "-").strip(): str(n) for s, n in zip(df["Symbol"], df["Security"])}
    if len(out) < 400:
        raise ValueError("רשימה חלקית מדי")
    return out


def load_sp500() -> dict[str, str]:
    """מחזיר {symbol: company name}. בגיבוי השם ריק."""
    try:
        if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < CACHE_MAX_AGE:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if len(data) >= 400:
                return data
    except Exception:
        pass
    try:
        data = _from_wikipedia()
        CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception:
        pass
    try:  # מטמון ישן עדיף על רשימת הגיבוי
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if len(data) >= 400:
            return data
    except Exception:
        pass
    return {t: "" for t in FALLBACK}

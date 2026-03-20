"""
market_snapshot.py
------------------
Pulls a real-time snapshot of key macro & crypto market data points.

Sources:
  - Yahoo Finance (yfinance)       : VIX, DXY, Gold, Silver, WTI, Brent, S&P 500, Copper
  - CoinGecko public API           : BTC, ETH, SOL prices
  - Deribit public REST API        : BTC DVOL, ETH DVOL
  - CoinMarketCap API (free tier)  : Crypto Fear & Greed Index  [preferred]
  - alternative.me API             : Crypto Fear & Greed Index  [fallback — known to serve stale data]

Not available via free APIs (require Bloomberg / Refinitiv):
  - ADXY (Asian Dollar Index)
  - MOVE Index (ICE BofA bond volatility)

Requirements:
  pip install yfinance requests

CMC API key (optional but recommended for accurate Fear & Greed):
  Get a free key at https://coinmarketcap.com/api/
  Either set the CMC_API_KEY constant below, or export it as an env var:
    export CMC_API_KEY="your-key-here"
"""

import os
import requests
import yfinance as yf
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration — add your free CoinMarketCap API key here
# ---------------------------------------------------------------------------
CMC_API_KEY: Optional[str] = os.environ.get("CMC_API_KEY", None)
# Or hardcode it directly:  CMC_API_KEY = "your-key-here"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt(value: Optional[float], decimals: int = 2, prefix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{prefix}{value:,.{decimals}f}"


def get_yf_price(ticker: str) -> Optional[float]:
    """Fetch the latest closing price for a Yahoo Finance ticker."""
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="2d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def get_coingecko(coin_ids: list[str]) -> dict[str, Optional[float]]:
    """Fetch USD prices from CoinGecko for a list of coin ids."""
    try:
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {coin: data.get(coin, {}).get("usd") for coin in coin_ids}
    except Exception:
        return {coin: None for coin in coin_ids}


def get_deribit_dvol(currency: str) -> Optional[float]:
    """Fetch DVOL index from Deribit public API (BTC or ETH)."""
    try:
        url = (
            f"https://www.deribit.com/api/v2/public/get_index_price"
            f"?index_name={currency.lower()}_dvol"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        result = r.json().get("result", {})
        return result.get("index_price")
    except Exception:
        return None


def get_fear_and_greed(
    cmc_api_key: Optional[str] = None,
) -> tuple[Optional[int], Optional[str], Optional[str], str]:
    """Fetch Crypto Fear & Greed Index.

    Tries CoinMarketCap first (accurate, requires free API key), then falls
    back to alternative.me (free but known to serve stale data).

    Returns (value, classification, timestamp_str, source_label).
    Get a free CMC key at: https://coinmarketcap.com/api/
    """
    # --- Source 1: CoinMarketCap (preferred) ---
    if cmc_api_key:
        try:
            url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
            headers = {"X-CMC_PRO_API_KEY": cmc_api_key, "Accept": "application/json"}
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json().get("data", {})
            ts = data.get("update_time") or data.get("timestamp")
            dt = (
                datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M UTC")
                if ts else None
            )
            return int(data["value"]), data["value_classification"], dt, "CoinMarketCap"
        except Exception:
            pass  # fall through to alternative.me

    # --- Source 2: alternative.me (fallback — may be stale) ---
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        entry = r.json()["data"][0]
        ts = entry.get("timestamp")
        dt = (
            datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M UTC")
            if ts else None
        )
        return int(entry["value"]), entry["value_classification"], dt, "alternative.me ⚠ may be stale"
    except Exception:
        return None, None, None, "unavailable"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print(f"  MARKET SNAPSHOT  —  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # --- Macro via Yahoo Finance ---
    yf_tickers: dict[str, tuple[str, str, int, str]] = {
        # label              : (ticker,      section,       decimals, prefix)
        "VIX"                : ("^VIX",      "VOLATILITY",  2, ""),
        "MOVE Index"         : ("^MOVE",     "VOLATILITY",  2, ""),
        "S&P 500"            : ("^GSPC",     "EQUITIES",    2, ""),
        "DXY (US Dollar)"    : ("DX-Y.NYB",  "FX / RATES",  3, ""),
        "Gold ($/oz)"        : ("GC=F",      "COMMODITIES", 2, "$"),
        "Silver ($/oz)"      : ("SI=F",      "COMMODITIES", 3, "$"),
        "WTI Crude ($/bbl)"  : ("CL=F",      "COMMODITIES", 2, "$"),
        "Brent Crude ($/bbl)": ("BZ=F",      "COMMODITIES", 2, "$"),
        "Copper ($/lb)"      : ("HG=F",      "COMMODITIES", 4, "$"),
    }

    print("\nFetching Yahoo Finance data...")
    yf_results: dict[str, Optional[float]] = {}
    for label, (ticker, *_) in yf_tickers.items():
        yf_results[label] = get_yf_price(ticker)

    print("Fetching CoinGecko prices...")
    cg_prices = get_coingecko(["bitcoin", "ethereum", "solana"])

    print("Fetching Deribit DVOL...")
    btc_dvol = get_deribit_dvol("BTC")
    eth_dvol = get_deribit_dvol("ETH")

    print("Fetching Crypto Fear & Greed Index...")
    fg_value, fg_label, fg_ts, fg_source = get_fear_and_greed(CMC_API_KEY)

    # -----------------------------------------------------------------------
    # Display
    # -----------------------------------------------------------------------

    sections: dict[str, list[tuple[str, str]]] = {
        "VOLATILITY":    [],
        "EQUITIES":      [],
        "FX / RATES":    [],
        "COMMODITIES":   [],
        "CRYPTO PRICES": [],
        "CRYPTO VOL":    [],
        "SENTIMENT":     [],
    }

    for label, (ticker, section, decimals, prefix) in yf_tickers.items():
        sections[section].append((label, fmt(yf_results[label], decimals, prefix)))

    sections["CRYPTO PRICES"] = [
        ("Bitcoin  (BTC)", fmt(cg_prices.get("bitcoin"), 2, "$")),
        ("Ethereum (ETH)", fmt(cg_prices.get("ethereum"), 2, "$")),
        ("Solana   (SOL)", fmt(cg_prices.get("solana"),   2, "$")),
    ]

    sections["CRYPTO VOL"] = [
        ("BTC DVOL (Deribit)", fmt(btc_dvol, 2)),
        ("ETH DVOL (Deribit)", fmt(eth_dvol, 2)),
    ]

    fg_display = f"{fg_value} — {fg_label}" if fg_value is not None else "N/A"
    fg_ts_str  = f"as of {fg_ts}" if fg_ts else "timestamp unavailable"
    sections["SENTIMENT"] = [
        ("Crypto Fear & Greed",  fg_display),
        ("  source",             fg_source),
        ("  last updated",       fg_ts_str),
    ]

    not_available = ["ADXY (Asian Dollar Index)", "MOVE Index (ICE BofA)"]

    col_width = 26
    for section, rows in sections.items():
        if not rows:
            continue
        print(f"\n  {'— ' + section + ' —':^56}")
        print("  " + "-" * 54)
        for label, value in rows:
            print(f"  {label:<{col_width}}  {value:>22}")

    print(f"\n  {'— NOT AVAILABLE (proprietary) —':^56}")
    print("  " + "-" * 54)
    for item in not_available:
        print(f"  {item:<{col_width}}  {'Bloomberg/ICE only':>22}")

    print("\n" + "=" * 60)

    if not CMC_API_KEY:
        print("\n  Tip: set CMC_API_KEY for accurate Fear & Greed data.")
        print("  Free key at https://coinmarketcap.com/api/\n")


if __name__ == "__main__":
    main()
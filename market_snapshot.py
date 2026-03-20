"""
market_snapshot.py
------------------
Pulls a real-time snapshot of key macro & crypto market data points.

Sources:
  - Yahoo Finance (yfinance)  : VIX, DXY, Gold, Silver, WTI, Brent, S&P 500, Copper
  - CoinGecko public API      : BTC, ETH, SOL prices
  - Deribit public REST API   : BTC DVOL, ETH DVOL
  - alternative.me API        : Crypto Fear & Greed Index

Not available via free APIs (require Bloomberg / Refinitiv):
  - ADXY (Asian Dollar Index)
  - MOVE Index (ICE BofA bond volatility)

Requirements:
  pip install yfinance requests
"""

import requests
import yfinance as yf
from datetime import datetime
from typing import Optional


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
        url = f"https://www.deribit.com/api/v2/public/get_index_price?index_name={currency.lower()}_dvol"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        result = r.json().get("result", {})
        return result.get("index_price")
    except Exception:
        return None


def get_fear_and_greed() -> tuple[Optional[int], Optional[str]]:
    """Fetch Crypto Fear & Greed Index from alternative.me."""
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        entry = r.json()["data"][0]
        return int(entry["value"]), entry["value_classification"]
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 56)
    print(f"  MARKET SNAPSHOT  —  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 56)

    # --- Macro via Yahoo Finance ---
    yf_tickers: dict[str, tuple[str, str, int, str]] = {
        # label          : (ticker,   section,      decimals, prefix)
        "VIX"            : ("^VIX",   "VOLATILITY",  2, ""),
        "MOVE Index"     : ("^MOVE",  "VOLATILITY",  2, ""),
        "S&P 500"        : ("^GSPC",  "EQUITIES",    2, ""),
        "DXY (US Dollar)": ("DX-Y.NYB","FX / RATES", 3, ""),
        "Gold ($/oz)"    : ("GC=F",   "COMMODITIES", 2, "$"),
        "Silver ($/oz)"  : ("SI=F",   "COMMODITIES", 3, "$"),
        "WTI Crude ($/bbl)"  : ("CL=F",  "COMMODITIES", 2, "$"),
        "Brent Crude ($/bbl)": ("BZ=F",  "COMMODITIES", 2, "$"),
        "Copper ($/lb)"  : ("HG=F",   "COMMODITIES", 4, "$"),
    }

    # Fetch all yfinance tickers in one pass
    print("\nFetching Yahoo Finance data...")
    yf_results: dict[str, Optional[float]] = {}
    for label, (ticker, *_) in yf_tickers.items():
        yf_results[label] = get_yf_price(ticker)

    # --- Crypto prices via CoinGecko ---
    print("Fetching CoinGecko prices...")
    cg_prices = get_coingecko(["bitcoin", "ethereum", "solana"])

    # --- DVOL via Deribit ---
    print("Fetching Deribit DVOL...")
    btc_dvol = get_deribit_dvol("BTC")
    eth_dvol = get_deribit_dvol("ETH")

    # --- Fear & Greed ---
    print("Fetching Crypto Fear & Greed Index...")
    fg_value, fg_label = get_fear_and_greed()

    # -----------------------------------------------------------------------
    # Display
    # -----------------------------------------------------------------------

    sections: dict[str, list[tuple[str, str]]] = {
        "VOLATILITY":   [],
        "EQUITIES":     [],
        "FX / RATES":   [],
        "COMMODITIES":  [],
        "CRYPTO PRICES":[],
        "CRYPTO VOL":   [],
        "SENTIMENT":    [],
    }

    # Populate macro sections
    for label, (ticker, section, decimals, prefix) in yf_tickers.items():
        value = yf_results[label]
        sections[section].append((label, fmt(value, decimals, prefix)))

    # Crypto prices
    sections["CRYPTO PRICES"] = [
        ("Bitcoin  (BTC)", fmt(cg_prices.get("bitcoin"), 2, "$")),
        ("Ethereum (ETH)", fmt(cg_prices.get("ethereum"), 2, "$")),
        ("Solana   (SOL)", fmt(cg_prices.get("solana"),   2, "$")),
    ]

    # Crypto vol
    sections["CRYPTO VOL"] = [
        ("BTC DVOL (Deribit)", fmt(btc_dvol, 2)),
        ("ETH DVOL (Deribit)", fmt(eth_dvol, 2)),
    ]

    # Sentiment
    fg_display = f"{fg_value} — {fg_label}" if fg_value is not None else "N/A"
    sections["SENTIMENT"] = [
        ("Crypto Fear & Greed", fg_display),
    ]

    # Not available note
    not_available = ["ADXY (Asian Dollar Index)", "MOVE Index (ICE BofA)"]

    col_width = 26
    for section, rows in sections.items():
        if not rows:
            continue
        print(f"\n  {'— ' + section + ' —':^52}")
        print("  " + "-" * 50)
        for label, value in rows:
            print(f"  {label:<{col_width}}  {value:>18}")

    print(f"\n  {'— NOT AVAILABLE (proprietary) —':^52}")
    print("  " + "-" * 50)
    for item in not_available:
        print(f"  {item:<{col_width}}  {'Bloomberg/ICE only':>18}")

    print("\n" + "=" * 56)


if __name__ == "__main__":
    main()

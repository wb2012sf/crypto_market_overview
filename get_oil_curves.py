"""
Brent Crude Oil Futures Curve Fetcher
=====================================
Fetches the entire Brent crude futures term structure from Yahoo Finance
using yfinance. Displays expiry months and last prices for all available
contract months.

Ticker convention on Yahoo Finance (NYMEX Brent Last Day Financial):
  - Front month:  BZ=F
  - Specific:     BZ{month_code}{YY}.NYM
    where month_code = F,G,H,J,K,M,N,Q,U,V,X,Z  (Jan–Dec)

Usage:
    pip install yfinance pandas
    python brent_futures_curve.py
"""

from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf


# Futures month codes: F=Jan, G=Feb, ..., Z=Dec
MONTH_CODES: dict[int, str] = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}

MONTH_NAMES: dict[str, str] = {v: k for k, v in {
    "Jan": "F", "Feb": "G", "Mar": "H", "Apr": "J",
    "May": "K", "Jun": "M", "Jul": "N", "Aug": "Q",
    "Sep": "U", "Oct": "V", "Nov": "X", "Dec": "Z",
}.items()}


def build_tickers(start_year: int = 2026, end_year: int = 2033) -> list[tuple[str, str]]:
    """
    Build a list of (ticker, label) pairs for Brent futures contracts.
    Returns tickers from start_year through end_year.
    """
    tickers: list[tuple[str, str]] = []
    for year in range(start_year, end_year + 1):
        yy: str = str(year)[-2:]
        for month_num, code in MONTH_CODES.items():
            label: str = f"{MONTH_NAMES[code]} {year}"
            ticker: str = f"BZ{code}{yy}.NYM"
            tickers.append((ticker, label))
    return tickers


def fetch_futures_curve(
    start_year: int = 2026,
    end_year: int = 2033,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Fetch the Brent crude futures curve (all listed contract months).

    Returns a DataFrame with columns:
        ticker, contract, last_price, bid, ask, volume, open_interest
    """
    candidates: list[tuple[str, str]] = build_tickers(start_year, end_year)
    rows: list[dict] = []

    if verbose:
        print(f"Scanning {len(candidates)} potential contract months...\n")

    for ticker, label in candidates:
        try:
            t: yf.Ticker = yf.Ticker(ticker)
            info: dict = t.info or {}

            # Try multiple fields for last price
            price: Optional[float] = (
                info.get("regularMarketPrice")
                or info.get("previousClose")
                or info.get("lastPrice")
            )

            if price is None or price == 0:
                continue

            rows.append({
                "ticker": ticker,
                "contract": label,
                "last_price": price,
                "bid": info.get("bid"),
                "ask": info.get("ask"),
                "volume": info.get("volume"),
                "open_interest": info.get("openInterest"),
            })

            if verbose:
                print(f"  {label:10s}  {ticker:14s}  ${price:.2f}")

        except Exception:
            # Contract doesn't exist or data unavailable — skip
            continue

    df: pd.DataFrame = pd.DataFrame(rows)
    return df


def print_curve(df: pd.DataFrame) -> None:
    """Pretty-print the futures curve."""
    if df.empty:
        print("No data retrieved.")
        return

    print("\n" + "=" * 70)
    print("BRENT CRUDE OIL FUTURES CURVE")
    print(f"As of {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print(f"{'Contract':<12} {'Ticker':<16} {'Last':>8} {'Bid':>8} {'Ask':>8} {'Volume':>10}")
    print("-" * 70)

    for _, row in df.iterrows():
        bid_str: str = f"${row['bid']:.2f}" if pd.notna(row["bid"]) else "   n/a"
        ask_str: str = f"${row['ask']:.2f}" if pd.notna(row["ask"]) else "   n/a"
        vol_str: str = f"{int(row['volume']):>10,}" if pd.notna(row["volume"]) else "       n/a"
        print(
            f"{row['contract']:<12} {row['ticker']:<16} "
            f"${row['last_price']:>7.2f} {bid_str:>8} {ask_str:>8} {vol_str}"
        )

    front: float = df.iloc[0]["last_price"]
    back: float = df.iloc[-1]["last_price"]
    spread: float = back - front
    shape: str = "contango" if spread > 0 else "backwardation"
    print("-" * 70)
    print(f"Contracts found: {len(df)}")
    print(f"Front month:     ${front:.2f}")
    print(f"Back month:      ${back:.2f}  ({label}: {df.iloc[-1]['contract']})")
    print(f"Spread:          ${spread:+.2f}  ({shape})")
    print("=" * 70)


def main() -> None:
    df: pd.DataFrame = fetch_futures_curve(
        start_year=2026,
        end_year=2033,
        verbose=True,
    )
    print_curve(df)

    # Save to CSV for further analysis
    if not df.empty:
        output_path: str = "brent_futures_curve.csv"
        df.to_csv(output_path, index=False)
        print(f"\nData saved to {output_path}")


if __name__ == "__main__":
    main()

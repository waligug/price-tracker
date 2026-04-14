"""Generate price history charts as PNG files."""

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# Dark theme colors (GitHub dark)
BG_COLOR = "#0d1117"
CARD_COLOR = "#161b22"
LINE_COLOR = "#58a6ff"
TEXT_COLOR = "#c9d1d9"
GRID_COLOR = "#21262d"
MIN_COLOR = "#3fb950"
MAX_COLOR = "#f85149"


def generate_charts(history, product_map, charts_dir):
    """Generate a chart PNG for each product.

    Args:
        history: dict of {product_id: [(date_str, price), ...]}
        product_map: dict of {product_id: product_dict}
        charts_dir: output directory for PNGs
    """
    os.makedirs(charts_dir, exist_ok=True)

    for pid, entries in history.items():
        if len(entries) < 1:
            continue

        product = product_map.get(pid, {})
        name = product.get("name", pid)

        dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in entries]
        prices = [p for _, p in entries]

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor(BG_COLOR)
        ax.set_facecolor(CARD_COLOR)

        # Plot line
        ax.plot(dates, prices, color=LINE_COLOR, linewidth=2, marker="o",
                markersize=4 if len(dates) < 30 else 0)

        # Fill under the line
        ax.fill_between(dates, prices, alpha=0.1, color=LINE_COLOR)

        # Mark min and max
        if len(prices) > 1:
            min_price = min(prices)
            max_price = max(prices)
            min_idx = prices.index(min_price)
            max_idx = prices.index(max_price)

            if min_price != max_price:
                ax.annotate(f"${min_price:.2f}", (dates[min_idx], min_price),
                            textcoords="offset points", xytext=(0, -15),
                            ha="center", fontsize=9, color=MIN_COLOR, fontweight="bold")
                ax.annotate(f"${max_price:.2f}", (dates[max_idx], max_price),
                            textcoords="offset points", xytext=(0, 10),
                            ha="center", fontsize=9, color=MAX_COLOR, fontweight="bold")

        # Current price label
        current = prices[-1]
        ax.set_title(f"{name}\nCurrent: ${current:.2f} CAD", color=TEXT_COLOR,
                     fontsize=12, fontweight="bold", pad=10)

        # Formatting
        ax.set_ylabel("Price (CAD)", color=TEXT_COLOR, fontsize=10)
        ax.tick_params(colors=TEXT_COLOR, labelsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.5)

        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)

        # Y-axis: zoom to price range, never start from 0
        min_p, max_p = min(prices), max(prices)
        if min_p == max_p:
            # Flat line: show +/- 5% around the price
            padding = max_p * 0.05 if max_p > 0 else 10
            ax.set_ylim(min_p - padding, max_p + padding)
        else:
            price_range = max_p - min_p
            ax.set_ylim(min_p - price_range * 0.15, max_p + price_range * 0.15)

        fig.autofmt_xdate()
        plt.tight_layout()

        out_path = os.path.join(charts_dir, f"{pid}.png")
        fig.savefig(out_path, dpi=100, facecolor=BG_COLOR)
        plt.close(fig)
        print(f"  Chart: {out_path}")

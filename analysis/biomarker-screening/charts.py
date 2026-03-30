"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

If DATAWRAPPER_API_TOKEN is set, creates publication-quality charts via the
Datawrapper API. Otherwise falls back to seaborn/matplotlib PNGs.

Usage:
    from charts import get_renderer
    renderer = get_renderer(output_dir)
    renderer.stacked_area(df, x="FY", y_cols=[...], labels=[...], ...)
"""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("colorblind")


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path) -> "SeabornRenderer | DatawrapperRenderer":
    """Return Datawrapper renderer if token is set, else seaborn fallback."""
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if token:
        return DatawrapperRenderer(output_dir, token)
    print("  [charts] No DATAWRAPPER_API_TOKEN — using seaborn/matplotlib fallback")
    return SeabornRenderer(output_dir)


class SeabornRenderer:
    """Fallback renderer using seaborn/matplotlib -> PNG files."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "seaborn"

    def stacked_area(
        self,
        df: pd.DataFrame,
        x: str,
        y_cols: list[str],
        labels: list[str],
        title: str,
        filename: str,
        ylabel: str = "Total Funding",
        vlines: list[int] | None = None,
    ):
        fig, ax = plt.subplots(figsize=(12, 6))
        bottom = pd.Series(0.0, index=df.index)
        for col, label, color in zip(y_cols, labels, PALETTE):
            ax.fill_between(
                df[x], bottom, bottom + df[col], alpha=0.7, label=label, color=color
            )
            bottom = bottom + df[col]

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(loc="upper left")

        if vlines:
            for yr in vlines:
                ax.axvline(x=yr, color="red", linestyle="--", alpha=0.4)
                ax.annotate(
                    "data gap",
                    xy=(yr, ax.get_ylim()[1] * 0.95),
                    fontsize=8,
                    color="red",
                    ha="center",
                )

        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def horizontal_bar(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        filename: str,
        annotations: str | None = None,
    ):
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.barplot(data=df, y=y, x=x, ax=ax, palette="viridis")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Total Funding")
        ax.set_ylabel("")
        ax.set_title(title)

        if annotations:
            for i, row in enumerate(df.itertuples()):
                val = getattr(row, annotations)
                ax.text(
                    getattr(row, x), i, f"  {val:,} grants", va="center", fontsize=8
                )

        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def area_by_category(self, pivot: pd.DataFrame, title: str, filename: str):
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot.plot.area(ax=ax, alpha=0.7)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("Total Funding")
        ax.set_title(title)
        ax.legend(title="Mechanism", bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def line(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        filename: str,
        ylabel: str = "",
        ylim: tuple | None = None,
        vlines: list[int] | None = None,
    ):
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df[x], df[y], marker="o", color=PALETTE[2], linewidth=2)
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        if ylim:
            ax.set_ylim(*ylim)
        if vlines:
            for yr in vlines:
                ax.axvline(x=yr, color="red", linestyle="--", alpha=0.4)
        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)


class DatawrapperRenderer:
    """Primary renderer using Datawrapper API -> published charts."""

    def __init__(self, output_dir: Path, token: str):
        from datawrapper import Datawrapper

        self.dw = Datawrapper(access_token=token)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "datawrapper"
        self.chart_urls: dict[str, str] = {}

    def _create_and_publish(
        self,
        chart_type: str,
        title: str,
        data: pd.DataFrame,
        filename: str,
        metadata: dict | None = None,
    ) -> str:
        chart_info = self.dw.create_chart(title=title, chart_type=chart_type)
        chart_id = chart_info["id"]
        self.dw.add_data(chart_id, data)
        if metadata:
            self.dw.update_metadata(chart_id, metadata)
        self.dw.publish_chart(chart_id)
        url = f"https://datawrapper.dwcdn.net/{chart_id}/"
        self.chart_urls[filename] = url

        ref_path = self.output_dir / f"{filename}.url"
        ref_path.write_text(url)
        print(f"  Published: {url}")
        return url

    def stacked_area(
        self,
        df: pd.DataFrame,
        x: str,
        y_cols: list[str],
        labels: list[str],
        title: str,
        filename: str,
        **kwargs,
    ):
        chart_df = df[[x] + y_cols].copy()
        chart_df.columns = [x] + labels
        return self._create_and_publish("d3-area", title, chart_df, filename)

    def horizontal_bar(
        self, df: pd.DataFrame, x: str, y: str, title: str, filename: str, **kwargs
    ):
        chart_df = df[[y, x]].copy()
        return self._create_and_publish("d3-bars", title, chart_df, filename)

    def area_by_category(self, pivot: pd.DataFrame, title: str, filename: str):
        chart_df = pivot.reset_index()
        return self._create_and_publish("d3-area", title, chart_df, filename)

    def line(
        self, df: pd.DataFrame, x: str, y: str, title: str, filename: str, **kwargs
    ):
        chart_df = df[[x, y]].copy()
        return self._create_and_publish("d3-lines", title, chart_df, filename)

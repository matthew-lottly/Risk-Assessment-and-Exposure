"""Map and figure plates for the risk assessment: a landscape page with a title block, a map or chart panel, a sidebar of measured numbers and notes, a legend and a source line.
Text is measured before it is placed, so nothing overlaps or runs off the page (a warning is printed if it would)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.textpath import TextPath

W, H = 16.0, 10.0
INK, TEXT, MUTED, RULE, ACCENT = "#15191D", "#2B3138", "#5B6470", "#D5D9DE", "#1F4E79"
FONT = "DejaVu Sans"
plt.rcParams.update({"font.family": FONT, "axes.edgecolor": "#9AA1AA", "axes.linewidth": 0.6})
OUT = Path(__file__).resolve().parents[2] / "outputs"


def text_width(s, size):
    return TextPath((0, 0), s, size=size, prop=FontProperties(family=FONT)).get_extents().width / 72.0


def wrap(s, width_in, size):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, size) <= width_in or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class Plate:
    def __init__(self, number, kicker, title, deck, source):
        self.number = number
        self.fig = plt.figure(figsize=(W, H), dpi=150)
        self.bg = self.fig.add_axes([0, 0, 1, 1])
        self.bg.set_xlim(0, W); self.bg.set_ylim(0, H); self.bg.axis("off")
        self.bg.text(0.6, 9.55, kicker.upper(), fontsize=8.5, color=ACCENT, fontweight="bold")
        self.bg.text(0.6, 9.08, title, fontsize=20, color=INK, fontweight="bold")
        y = 8.78
        for ln in wrap(deck, 14.8, 10.5):
            self.bg.text(0.6, y, ln, fontsize=10.5, color=MUTED, va="top")
            y -= 0.22
        self.top = y - 0.12
        self.bg.plot([0.6, 15.4], [self.top, self.top], color=INK, lw=1.1)
        self.bg.plot([0.6, 15.4], [0.72, 0.72], color=RULE, lw=0.6)
        yy = 0.6
        for ln in wrap(source, 13.2, 6.8)[:3]:
            self.bg.text(0.6, yy, ln, fontsize=6.8, color=MUTED, va="top")
            yy -= 0.13
        self.bg.text(15.4, 0.6, f"Plate {number}", fontsize=8.5, color=INK, fontweight="bold", ha="right", va="top")

    def ax(self, l, b, w, h, **kw):
        return self.fig.add_axes([l / W, b / H, w / W, h / H], **kw)

    def panel_title(self, x, y, letter, text, w):
        self.bg.add_patch(FancyBboxPatch((x, y - 0.09), 0.22, 0.22, boxstyle="circle,pad=0", fc=ACCENT, ec="none"))
        self.bg.text(x + 0.11, y + 0.02, letter, fontsize=7.5, color="white", fontweight="bold", ha="center", va="center")
        self.bg.text(x + 0.33, y + 0.02, text, fontsize=10, color=INK, fontweight="bold", va="center")
        self.bg.plot([x, x + w], [y - 0.2, y - 0.2], color=RULE, lw=0.6)

    def tiles(self, x, y, w, items):
        n = len(items)
        cw = w / n
        for i, (num, lab) in enumerate(items):
            xx = x + i * cw
            self.bg.text(xx + 0.02, y, num, fontsize=19, color=ACCENT, fontweight="bold", va="top")
            yy = y - 0.42
            for ln in wrap(lab, cw - 0.15, 7.6):
                self.bg.text(xx + 0.02, yy, ln, fontsize=7.6, color=MUTED, va="top")
                yy -= 0.15
            if i:
                self.bg.plot([xx - 0.08, xx - 0.08], [y + 0.02, y - 0.75], color=RULE, lw=0.6)
        return y - 0.95

    def notes(self, x, y, w, items, fs=8.3):
        for head, body in items:
            self.bg.text(x, y, head, fontsize=9.2, color=INK, fontweight="bold", va="top")
            y -= 0.24
            for ln in wrap(body, w, fs):
                self.bg.text(x, y, ln, fontsize=fs, color=TEXT, va="top")
                y -= fs / 72 * 1.5
            y -= 0.14
        if y < 0.8:
            print(f"  [plate {self.number}] text runs {0.8 - y:.2f} in below the margin")
        return y

    def legend(self, x, y, w, items, title=None, fs=7.6):
        if title:
            self.bg.text(x, y, title.upper(), fontsize=7.2, color=MUTED, fontweight="bold", va="top")
            y -= 0.22
        cx, cy = x, y
        for kind, col, lab in items:
            lw = text_width(lab, fs) + 0.42
            if cx + lw > x + w and cx > x:
                cx, cy = x, cy - 0.21
            yy = cy - 0.07
            if kind == "line":
                self.bg.plot([cx, cx + 0.24], [yy, yy], color=col, lw=2)
            elif kind == "dot":
                self.bg.plot([cx + 0.12], [yy], "o", color=col, ms=5, mec="white", mew=0.4)
            else:
                self.bg.add_patch(Rectangle((cx, yy - 0.06), 0.24, 0.12, fc=col, ec="#8A9099", lw=0.3))
            self.bg.text(cx + 0.32, yy, lab, fontsize=fs, color=TEXT, va="center")
            cx += lw + 0.25
        return cy - 0.28

    def colorbar(self, x, y, w, cmap, vmin, vmax, label, ticks=None, fmt="{:,.0f}"):
        import numpy as np
        a = self.ax(x, y - 0.16, w, 0.14)
        a.imshow(np.linspace(0, 1, 256)[None, :], aspect="auto", cmap=cmap, extent=(vmin, vmax, 0, 1))
        a.set_yticks([])
        if ticks is not None:
            a.set_xticks(ticks); a.set_xticklabels([fmt.format(t) for t in ticks])
        a.tick_params(labelsize=7, colors=MUTED, length=2)
        self.bg.text(x, y + 0.08, label.upper(), fontsize=7.2, color=MUTED, fontweight="bold")
        return y - 0.62

    def save(self, name):
        for a in self.fig.axes:  # geopandas labels map axes with the CRS units; maps here carry a scale bar instead
            if "metre" in a.get_xlabel() or "metre" in a.get_ylabel():
                a.set_xlabel(""); a.set_ylabel("")
        (OUT / "maps").mkdir(parents=True, exist_ok=True)
        p = OUT / "maps" / name
        self.fig.savefig(p, dpi=150, facecolor="white")
        plt.close(self.fig)
        print("wrote", p.name)
        return p


def scalebar(ax, km=10, loc=(0.04, 0.05)):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    bx, by = x0 + loc[0] * (x1 - x0), y0 + loc[1] * (y1 - y0)
    L = km * 1000
    ax.add_patch(Rectangle((bx - (x1 - x0) * 0.012, by - (y1 - y0) * 0.012), L + (x1 - x0) * 0.06, (y1 - y0) * 0.05, fc="white", ec="none", alpha=0.85, zorder=19))
    for i in range(4):
        ax.add_patch(Rectangle((bx + i * L / 4, by), L / 4, (y1 - y0) * 0.006, fc=INK if i % 2 == 0 else "white", ec=INK, lw=0.5, zorder=20))
    for v in (0, km / 2, km):
        ax.text(bx + v * 1000, by + (y1 - y0) * 0.014, f"{v:g}", fontsize=6.5, ha="center", color=INK, zorder=20)
    ax.text(bx + L + (x1 - x0) * 0.01, by, "km", fontsize=6.5, color=INK, va="bottom", zorder=20)


def north(ax, loc=(0.95, 0.9)):
    ax.add_patch(Rectangle((loc[0] - 0.018, loc[1] - 0.095), 0.036, 0.115, transform=ax.transAxes, fc="white", ec="none", alpha=0.85, zorder=19))
    ax.annotate("N", xy=loc, xytext=(loc[0], loc[1] - 0.07), xycoords="axes fraction", ha="center", fontsize=9, fontweight="bold", color=INK,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2), zorder=20)

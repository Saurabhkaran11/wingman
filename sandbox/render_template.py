"""Render a dossier PDF. Runs INSIDE the sandbox container.

Contract:
  input  -> /work/dossier.json  (a serialised wingman.models.Dossier)
  output -> /work/out/dossier.pdf  and  /work/out/timeline.png
"""

import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")  # no display inside a container
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

WORK = Path("/work")
OUT = WORK / "out"
ACCENT = "#2563EB"
KIND_COLORS = {"email": "#2563EB", "meeting": "#059669", "note": "#D97706"}


def draw_timeline(events: list[dict], path: Path) -> None:
    # One dot per interaction on a horizontal time axis, labels alternating
    # above and below the line so neighbours do not collide.
    # Example: [{"date": "2026-05-14", "kind": "email", "summary": "Intro"}] -> one blue dot in May.
    fig, ax = plt.subplots(figsize=(7.2, 2.2), dpi=200)
    ax.axhline(0, color="#CBD5E1", linewidth=2, zorder=1)
    for i, ev in enumerate(events):
        x = date.fromisoformat(ev["date"][:10])
        offset = 0.55 if i % 2 == 0 else -0.55
        ax.scatter([x], [0], s=90, color=KIND_COLORS.get(ev["kind"], "#64748B"), zorder=3)
        ax.annotate(
            f"{x:%b %d}\n{ev['summary'][:34]}",
            (x, 0),
            xytext=(0, 26 * (1 if offset > 0 else -1)),
            textcoords="offset points",
            ha="center",
            va="bottom" if offset > 0 else "top",
            fontsize=6.5,
            color="#0F172A",
        )
    ax.set_ylim(-1.6, 1.6)
    ax.margins(x=0.12)
    ax.axis("off")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_pdf(d: dict, timeline_png: Path | None, path: Path) -> None:
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=colors.HexColor("#475569"))
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, textColor=colors.HexColor(ACCENT), spaceBefore=9, spaceAfter=3)
    body = ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13)
    alert = ParagraphStyle("alert", parent=body, backColor=colors.HexColor("#FEF3C7"), borderPadding=4, spaceAfter=6)

    def bullets(items: list[str]) -> list:
        # Every string comes from an LLM or the web, so escape it before it
        # reaches ReportLab's mini-HTML parser.
        return [Paragraph(f"&bull; {escape(i)}", body) for i in items] or [Paragraph("None found.", body)]

    story = [
        Paragraph(escape(d["person"]), h1),
        Paragraph(escape(f"{d['role']} at {d['company']}"), sub),
        Spacer(1, 4),
        Paragraph(escape(d["how_we_know_each_other"]), body),
        Paragraph("Last time", h2),
        Paragraph(escape(f"{d['last_interaction']['date']}: {d['last_interaction']['summary']}"), body),
        Paragraph("You owe them", h2),
        *bullets(d["i_owe_them"]),
        Paragraph("They owe you", h2),
        *bullets(d["they_owe_me"]),
        Paragraph("What changed since you last spoke", h2),
    ]
    for f in d["whats_new"]:
        url = escape(f["source_url"], {'"': "&quot;"})
        story.append(Paragraph(f"&bull; {escape(f['statement'])} <font color='{ACCENT}'><link href=\"{url}\">[source]</link></font>", body))
    if d["stale_alerts"]:
        story.append(Paragraph("Stale memory alerts", h2))
        for a in d["stale_alerts"]:
            story.append(Paragraph(f"<b>Your notes say:</b> {escape(a['memory_says'])}<br/><b>The web says:</b> {escape(a['web_says'])}", alert))
    story += [Paragraph("Talking points", h2), *bullets(d["talking_points"])]
    if timeline_png:
        story += [Paragraph("Timeline", h2), Image(str(timeline_png), width=6.8 * inch, height=2.05 * inch)]

    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                      topMargin=0.6 * inch, bottomMargin=0.5 * inch, title=f"Wingman dossier: {d['person']}").build(story)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    dossier = json.loads((WORK / "dossier.json").read_text())
    png = None
    if dossier.get("timeline"):
        png = OUT / "timeline.png"
        draw_timeline(dossier["timeline"], png)
    build_pdf(dossier, png, OUT / "dossier.pdf")
    print("rendered", OUT / "dossier.pdf")

"""In-memory exports with spreadsheet formula neutralization and paginated PDF."""

from io import BytesIO
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime, timezone
from xml.sax.saxutils import escape
import re
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from .data_analysis import profile, kpis, facts, aggregate, numeric_columns


def safe_cell(value):
    if isinstance(value, str):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
        if value.lstrip().startswith(
            ("=", "+", "-", "@", "\t", "\r", "\n")
        ) or value.startswith(("\t", "\r", "\n")):
            return "'" + value
    return value


def safe_frame(df):
    out = df.copy()
    out.columns = [safe_cell(str(c)) for c in out.columns]
    for c in out:
        if pd.api.types.is_object_dtype(out[c]) or pd.api.types.is_string_dtype(out[c]):
            out[c] = out[c].map(safe_cell)
        if isinstance(out[c].dtype, pd.DatetimeTZDtype):
            out[c] = out[c].dt.tz_localize(None)
    return out


def csv_bytes(df):
    return safe_frame(df).to_csv(index=False).encode("utf-8-sig")


def excel_bytes(df, context, cleaning=None, breakdown=None):
    buffer = BytesIO()
    frames = {
        "Cleaned data": df,
        "Data quality": profile(df),
        "Context": pd.DataFrame(
            [{"Setting": k, "Value": str(v)} for k, v in context.items()]
        ),
        "Cleaning history": pd.DataFrame(cleaning or []),
    }
    nums = numeric_columns(df)
    if nums:
        frames["Statistics"] = df[nums].describe().T.rename_axis("Column").reset_index()
    if breakdown is not None:
        frames["Analysis"] = breakdown.reset_index(drop=True)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in frames.items():
            safe_frame(frame).to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            from openpyxl.styles import Font, PatternFill, Alignment

            for cell in ws[1]:
                cell.font = Font(color="FFFFFF", bold=True)
                cell.fill = PatternFill("solid", fgColor="133E45")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(
                    44, max(14, len(str(col[0].value or "")) + 3)
                )
    return buffer.getvalue()


def pdf_bytes(
    df, name, context, cleaning=None, metric=None, group=None, date=None, ai=None
):
    buffer = BytesIO()
    font_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    if "InsightSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("InsightSans", str(font_dir / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(
            TTFont("InsightSansBold", str(font_dir / "DejaVuSans-Bold.ttf"))
        )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = (
            "InsightSansBold"
            if style.name.startswith(("Heading", "Title"))
            else "InsightSans"
        )
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 14
    styles.add(
        ParagraphStyle(
            name="SmallNote",
            fontName="InsightSans",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#51636b"),
        )
    )
    styles["Title"].textColor = colors.HexColor("#133e45")
    styles["Heading2"].textColor = colors.HexColor("#0f766e")
    styles["BodyText"].spaceAfter = 6

    # Bundle a licensed Unicode font so PDF rendering is consistent on Windows/Linux.
    def p(value, style="BodyText"):
        value = (
            str(value)
            .replace("₦", "NGN ")
            .replace("×", " x ")
            .replace("–", "-")
            .replace("—", "-")
            .replace("→", " to ")
        )
        return Paragraph(escape(value), styles[style])

    story = [
        p("INSIGHTAI", "Title"),
        p("Analytical report", "Heading1"),
        p(name),
        p(
            datetime.now(timezone.utc).strftime("Generated %d %b %Y, %H:%M UTC"),
            "SmallNote",
        ),
        Spacer(1, 14),
    ]

    def heading(title):
        story.append(p(title, "Heading2"))

    def table(frame, widths=None, limit=25):
        data = [[p(c, "SmallNote") for c in frame.columns]]
        for row in frame.head(limit).itertuples(index=False, name=None):
            data.append(
                [
                    p(
                        (
                            "N/A"
                            if pd.isna(v)
                            else (f"{v:,.2f}" if isinstance(v, float) else str(v)[:180])
                        ),
                        "SmallNote",
                    )
                    for v in row
                ]
            )
        if not frame.columns.size:
            return
        tbl = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0f2f1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f5f7f9")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(tbl)
        if len(frame) > limit:
            story.append(
                p(
                    f"First {limit} of {len(frame)} rows shown. Download Excel for full analytical tables.",
                    "SmallNote",
                )
            )

    heading("Scope and filter context")
    for k, v in context.items():
        story.append(p(f"{k}: {v}", "SmallNote"))
    heading("Calculated findings")
    for item in facts(df, metric, group, date):
        story.append(p(f'{item["id"]}. {item["text"]}'))
    heading("Data quality")
    table(
        profile(df)[["Column", "Type", "Missing", "Missing %", "Unique"]],
        [150, 110, 65, 65, 65],
        100,
    )
    heading("Cleaning performed")
    if cleaning:
        for step in cleaning:
            story.append(
                p(
                    f'{step["operation"]} ({step["columns"] or "all columns"}): {step["rows_removed"]} rows removed; {step["cells_changed"]} cells changed; {step["invalid_to_missing"]} invalid values made missing.'
                )
            )
    else:
        story.append(p("No cleaning operations applied."))
    if metric and group:
        breakdown = (
            aggregate(df, group, metric)
            .dropna(subset=["Value"])
            .sort_values("Value", ascending=False)
        )
        heading(f"Recorded {metric} by {group}")
        if not breakdown.empty:
            chart_heading = story.pop()
            chart = Drawing(465, 215)
            top = breakdown.head(8).iloc[::-1]
            maxval = max(abs(top.Value).max(), 1)
            chart.add(Line(270, 20, 270, 210, strokeColor=colors.HexColor("#94a3b8")))
            for i, row in enumerate(top.itertuples()):
                y = 25 + i * 23
                label = str(row.Group)
                while pdfmetrics.stringWidth(label, "InsightSans", 8) > 145:
                    label = label[:-2] + "…"
                chart.add(String(0, y + 3, label, fontSize=8, fontName="InsightSans"))
                width = abs(row.Value) / maxval * 95
                chart.add(
                    Rect(
                        270 if row.Value >= 0 else 270 - width,
                        y,
                        width,
                        14,
                        fillColor=colors.HexColor("#0d9488"),
                        strokeColor=None,
                    )
                )
                chart.add(
                    String(
                        390,
                        y + 3,
                        f"{row.Value:,.0f}",
                        fontSize=8,
                        fontName="InsightSans",
                    )
                )
            story.append(KeepTogether([chart_heading, chart]))
            story.append(
                p(
                    "Top eight recorded category totals. Negative values extend left of the baseline.",
                    "SmallNote",
                )
            )
            table(breakdown, [290, 165])
    heading("Implications and recommended next steps")
    story.append(
        p(
            "Review missing values and category definitions before acting on totals. Investigate large category differences and unusual observations with domain knowledge. These are review steps, not evidence of causes or future performance."
        )
    )
    if ai:
        heading("Optional AI commentary - review before use")
        story.append(p(ai.get("executive_summary", "")))
        story.append(
            p("Evidence: " + ", ".join(ai.get("evidence_ids", [])), "SmallNote")
        )
        for key in ("hypotheses_to_investigate", "recommendations", "limitations"):
            story.append(p(key.replace("_", " ").title(), "Heading3"))
            for text in ai.get(key, []):
                story.append(p(text))
    heading("Limitations")
    story.append(
        p(
            "All results describe the selected records only. Missing numeric values are excluded, not treated as zero. Summing identifiers or rates may not be meaningful; verify the metric. Correlation does not establish causation. Calendar months may be incomplete. AI narrative is unverified interpretation; numeric findings are computed with Pandas. The bundled font supports many scripts, but complex-script shaping and every Unicode glyph are not guaranteed; use Excel for exact label fidelity."
        )
    )

    def footer(canvas, doc):
        canvas.setFont("InsightSans", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(
            40, 26, "InsightAI | Recorded observations, explicit limitations"
        )
        canvas.drawRightString(555, 26, f"Page {doc.page}")

    SimpleDocTemplate(
        buffer,
        pagesize=(595, 842),
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=45,
        title="InsightAI analytical report",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

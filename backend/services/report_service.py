"""PDF report generation service.

Generates professional multi-page safety briefings with matplotlib charts
and AI-written narrative sections. Uses ReportLab for PDF assembly.
"""

import asyncio
import io
import logging
import os
import sqlite3
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")  # Headless rendering for Docker
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)

from services.claude_service import get_claude_service, ClaudeServiceError
from services.prompts import (
    REPORT_SUMMARY_SYSTEM,
    REPORT_SUMMARY_USER,
    REPORT_RECOMMENDATIONS_SYSTEM,
    REPORT_RECOMMENDATIONS_USER,
)

logger = logging.getLogger(__name__)

# Brand assets
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "beacon_gom_logo_light.png")

# Brand colors
BRAND_NAVY = "#0A1628"
BRAND_TEAL = "#0891B2"
BRAND_TEAL_LIGHT = "#22D3EE"
BRAND_SLATE = "#64748B"

# Chart styling
CHART_COLORS = {
    "primary": BRAND_TEAL,
    "secondary": "#dc2626",
    "tertiary": "#059669",
    "gray": BRAND_SLATE,
}
plt.style.use("seaborn-v0_8-whitegrid")


class ReportService:
    """Generates PDF safety intelligence reports."""

    def __init__(self):
        self.db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
        self.claude = get_claude_service()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _query_data(
        self,
        operator: str | None,
        year_start: int | None,
        year_end: int | None,
    ) -> dict:
        """Query SQLite for report data. Returns dict of DataFrames."""
        conn = self._get_conn()

        # Build WHERE clauses
        conditions = []
        params: list = []
        if operator:
            conditions.append("OPERATOR_NAME = ?")
            params.append(operator)
        if year_start:
            conditions.append("YEAR >= ?")
            params.append(year_start)
        if year_end:
            conditions.append("YEAR <= ?")
            params.append(year_end)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Incidents by year
        incidents_by_year = pd.read_sql(
            f"SELECT YEAR, COUNT(*) as count FROM incidents WHERE {where} GROUP BY YEAR ORDER BY YEAR",
            conn, params=params,
        )

        # INCs by severity
        incs_by_severity = pd.read_sql(
            f"SELECT SEVERITY, COUNT(*) as count FROM incs WHERE {where} GROUP BY SEVERITY ORDER BY count DESC",
            conn, params=params,
        )

        # Production (for normalized metrics)
        prod_params = []
        prod_conditions = []
        if operator:
            prod_conditions.append("OPERATOR_NAME = ?")
            prod_params.append(operator)
        if year_start:
            prod_conditions.append("YEAR >= ?")
            prod_params.append(year_start)
        if year_end:
            prod_conditions.append("YEAR <= ?")
            prod_params.append(year_end)
        prod_where = " AND ".join(prod_conditions) if prod_conditions else "1=1"

        production_by_year = pd.read_sql(
            f"""SELECT YEAR,
                       SUM(OIL_BBL + GAS_MCF * 0.1781) as total_boe
                FROM production WHERE {prod_where}
                GROUP BY YEAR ORDER BY YEAR""",
            conn, params=prod_params,
        )

        # Root cause breakdown
        rc_conditions = []
        rc_params: list = []
        if operator:
            rc_conditions.append("i.OPERATOR_NAME = ?")
            rc_params.append(operator)
        if year_start:
            rc_conditions.append("i.YEAR >= ?")
            rc_params.append(year_start)
        if year_end:
            rc_conditions.append("i.YEAR <= ?")
            rc_params.append(year_end)
        rc_where = " AND ".join(rc_conditions) if rc_conditions else "1=1"

        root_causes = pd.read_sql(
            f"""SELECT rc.primary_cause, COUNT(*) as count
                FROM incident_root_causes rc
                JOIN incidents i ON i.INCIDENT_ID = rc.incident_id
                WHERE {rc_where}
                GROUP BY rc.primary_cause
                ORDER BY count DESC""",
            conn, params=rc_params,
        )

        # Summary stats
        total_incidents = pd.read_sql(
            f"SELECT COUNT(*) as total FROM incidents WHERE {where}",
            conn, params=params,
        ).iloc[0]["total"]

        total_incs = pd.read_sql(
            f"SELECT COUNT(*) as total FROM incs WHERE {where}",
            conn, params=params,
        ).iloc[0]["total"]

        conn.close()

        return {
            "incidents_by_year": incidents_by_year,
            "incs_by_severity": incs_by_severity,
            "production_by_year": production_by_year,
            "root_causes": root_causes,
            "total_incidents": int(total_incidents),
            "total_incs": int(total_incs),
        }

    def _make_incident_trend_chart(self, df: pd.DataFrame) -> io.BytesIO:
        """Line chart: incidents by year."""
        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        ax.plot(
            df["YEAR"], df["count"],
            marker="o", color=CHART_COLORS["primary"], linewidth=2, markersize=5,
        )
        ax.set_xlabel("Year")
        ax.set_ylabel("Incident Count")
        ax.set_title("Incident Trends Over Time")
        ax.set_xticks(df["YEAR"])
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_severity_chart(self, df: pd.DataFrame) -> io.BytesIO:
        """Bar chart: INCs by severity."""
        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        bar_colors = [CHART_COLORS["primary"], CHART_COLORS["secondary"], CHART_COLORS["tertiary"]]
        bars = ax.bar(
            df["SEVERITY"], df["count"],
            color=bar_colors[:len(df)],
        )
        ax.set_xlabel("Severity")
        ax.set_ylabel("Count")
        ax.set_title("Violations by Severity Level")
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2.0, height,
                    f"{int(height)}", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_normalized_chart(
        self, incidents: pd.DataFrame, production: pd.DataFrame,
    ) -> io.BytesIO | None:
        """Line chart: incidents per million BOE."""
        if incidents.empty or production.empty:
            return None

        merged = pd.merge(incidents, production, on="YEAR", how="inner")
        if merged.empty:
            return None

        merged["rate"] = merged["count"] / (merged["total_boe"] / 1_000_000)

        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        ax.plot(
            merged["YEAR"], merged["rate"],
            marker="s", color=CHART_COLORS["tertiary"], linewidth=2, markersize=5,
        )
        ax.set_xlabel("Year")
        ax.set_ylabel("Incidents per Million BOE")
        ax.set_title("Production-Normalized Incident Rate")
        ax.set_xticks(merged["YEAR"])
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_root_cause_chart(self, df: pd.DataFrame) -> io.BytesIO | None:
        """Pie chart: root cause distribution."""
        if df.empty:
            return None

        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        labels = [c.replace("_", " ").title() for c in df["primary_cause"]]
        ax.pie(
            df["count"], labels=labels, autopct="%1.0f%%",
            startangle=140, textprops={"fontsize": 8},
        )
        ax.set_title("Root Cause Distribution")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    async def generate_report(
        self,
        operator: str | None,
        year_start: int | None,
        year_end: int | None,
        include_ai: bool = True,
    ) -> bytes:
        """Generate a complete PDF safety briefing. Returns PDF bytes."""
        # 1. Query data
        data = self._query_data(operator, year_start, year_end)

        if data["total_incidents"] == 0 and data["total_incs"] == 0:
            raise ValueError("No data found for the specified filters.")

        # 2. Generate charts
        charts = {}
        if not data["incidents_by_year"].empty:
            charts["incident_trend"] = self._make_incident_trend_chart(data["incidents_by_year"])
        if not data["incs_by_severity"].empty:
            charts["severity"] = self._make_severity_chart(data["incs_by_severity"])
        charts["normalized"] = self._make_normalized_chart(
            data["incidents_by_year"], data["production_by_year"],
        )
        charts["root_cause"] = self._make_root_cause_chart(data["root_causes"])

        # 3. AI narrative (optional)
        summary_text = ""
        recommendations_text = ""
        if include_ai and self.claude.is_available:
            data_summary = (
                f"Operator: {operator or 'All GoM'}\n"
                f"Period: {year_start or 'All'} – {year_end or 'All'}\n"
                f"Total Incidents: {data['total_incidents']}\n"
                f"Total INCs (Violations): {data['total_incs']}\n"
                f"Incidents by Year: {data['incidents_by_year'].to_dict('records')}\n"
                f"INCs by Severity: {data['incs_by_severity'].to_dict('records')}\n"
            )

            try:
                summary_text = await asyncio.wait_for(
                    self.claude.generate(
                        system_prompt=REPORT_SUMMARY_SYSTEM,
                        user_prompt=REPORT_SUMMARY_USER.format(data_summary=data_summary),
                        max_tokens=1024,
                    ),
                    timeout=60,
                )
            except (ClaudeServiceError, asyncio.TimeoutError) as e:
                logger.warning("AI summary generation failed: %s", e)
                summary_text = "(AI summary generation failed. Data-only report.)"

            try:
                recommendations_text = await asyncio.wait_for(
                    self.claude.generate(
                        system_prompt=REPORT_RECOMMENDATIONS_SYSTEM,
                        user_prompt=REPORT_RECOMMENDATIONS_USER.format(data_summary=data_summary),
                        max_tokens=1024,
                    ),
                    timeout=60,
                )
            except (ClaudeServiceError, asyncio.TimeoutError) as e:
                logger.warning("AI recommendations generation failed: %s", e)
                recommendations_text = "(AI recommendations generation failed.)"

        # 4. Assemble PDF
        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buf, pagesize=letter,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
            topMargin=1.2 * inch, bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=26,
            leading=32,
            spaceAfter=20,
            textColor=colors.HexColor(BRAND_NAVY),
        ))
        styles.add(ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            spaceAfter=10,
            textColor=colors.HexColor(BRAND_SLATE),
        ))
        styles.add(ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=22,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor(BRAND_NAVY),
        ))
        styles.add(ParagraphStyle(
            name="BodyText2",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1E293B"),
        ))

        # Page header/footer callbacks for branding
        logo_path = LOGO_PATH if os.path.exists(LOGO_PATH) else None

        def _on_first_page(canvas, doc):
            """Draw branded header on the cover page."""
            canvas.saveState()
            if logo_path:
                canvas.drawImage(
                    logo_path,
                    0.75 * inch, letter[1] - 0.85 * inch,
                    width=2 * inch, height=0.5 * inch,
                    preserveAspectRatio=True, anchor="sw",
                    mask="auto",
                )
            else:
                # Fallback text-only branding
                canvas.setFont("Helvetica-Bold", 12)
                canvas.setFillColor(colors.HexColor(BRAND_NAVY))
                canvas.drawString(0.75 * inch, letter[1] - 0.6 * inch, "BEACON GoM")

            # Tagline to the right of logo
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor(BRAND_SLATE))
            canvas.drawString(
                2.9 * inch, letter[1] - 0.63 * inch,
                "AI Safety & Regulatory Intelligence",
            )
            # Top accent line
            canvas.setStrokeColor(colors.HexColor(BRAND_TEAL))
            canvas.setLineWidth(2)
            canvas.line(0.75 * inch, letter[1] - 0.92 * inch,
                        letter[0] - 0.75 * inch, letter[1] - 0.92 * inch)

            # Footer
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor(BRAND_SLATE))
            canvas.drawCentredString(
                letter[0] / 2, 0.4 * inch,
                "Beacon GoM — gomsafety.aigniteconsulting.ai — Confidential",
            )
            canvas.restoreState()

        def _on_later_pages(canvas, doc):
            """Draw branded header on subsequent pages."""
            canvas.saveState()
            if logo_path:
                canvas.drawImage(
                    logo_path,
                    0.75 * inch, letter[1] - 0.7 * inch,
                    width=1.4 * inch, height=0.35 * inch,
                    preserveAspectRatio=True, anchor="sw",
                    mask="auto",
                )
            else:
                canvas.setFont("Helvetica-Bold", 9)
                canvas.setFillColor(colors.HexColor(BRAND_NAVY))
                canvas.drawString(0.75 * inch, letter[1] - 0.5 * inch, "BEACON GoM")

            # Thin accent line
            canvas.setStrokeColor(colors.HexColor(BRAND_TEAL))
            canvas.setLineWidth(0.75)
            canvas.line(0.75 * inch, letter[1] - 0.78 * inch,
                        letter[0] - 0.75 * inch, letter[1] - 0.78 * inch)

            # Page number footer
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor(BRAND_SLATE))
            canvas.drawCentredString(
                letter[0] / 2, 0.4 * inch,
                f"Page {doc.page} — Beacon GoM",
            )
            canvas.restoreState()

        story = []

        # --- Cover page ---
        story.append(Spacer(1, 1.5 * inch))
        story.append(Paragraph(
            "Gulf of Mexico<br/>Safety Intelligence Report",
            styles["CoverTitle"],
        ))
        story.append(HRFlowable(width="80%", color=colors.HexColor(BRAND_TEAL)))
        story.append(Spacer(1, 0.3 * inch))

        op_label = operator or "GoM-Wide"
        year_label = f"{year_start or 'All'} – {year_end or 'All'}"
        now = datetime.now(timezone.utc).strftime("%B %d, %Y")

        story.append(Paragraph(f"<b>Operator:</b> {op_label}", styles["CoverSubtitle"]))
        story.append(Paragraph(f"<b>Period:</b> {year_label}", styles["CoverSubtitle"]))
        story.append(Paragraph(f"<b>Generated:</b> {now}", styles["CoverSubtitle"]))
        story.append(Spacer(1, 1 * inch))
        story.append(Paragraph(
            "Powered by <b>Beacon GoM</b> — AI Safety &amp; Regulatory Intelligence",
            styles["CoverSubtitle"],
        ))
        story.append(PageBreak())

        # --- Executive Summary ---
        story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
        if summary_text:
            for para in summary_text.strip().split("\n\n"):
                # Strip markdown formatting for PDF
                clean = para.replace("**", "").replace("*", "").strip()
                if clean:
                    story.append(Paragraph(clean, styles["BodyText2"]))
        else:
            story.append(Paragraph(
                "AI analysis not included. This is a data-only report.",
                styles["BodyText2"],
            ))
        story.append(Spacer(1, 0.3 * inch))

        # --- Incident Trends ---
        story.append(Paragraph("Incident Trends", styles["SectionTitle"]))
        if "incident_trend" in charts:
            story.append(Image(charts["incident_trend"], width=6.5 * inch, height=3.5 * inch))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(
            f"Total incidents in the selected period: <b>{data['total_incidents']}</b>",
            styles["BodyText2"],
        ))

        # Incident table
        if not data["incidents_by_year"].empty:
            table_data = [["Year", "Incidents"]]
            for _, row in data["incidents_by_year"].iterrows():
                table_data.append([str(int(row["YEAR"])), str(int(row["count"]))])

            t = Table(table_data, colWidths=[2 * inch, 2 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_TEAL)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]))
            story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # --- Compliance Overview ---
        story.append(Paragraph("Compliance Overview", styles["SectionTitle"]))
        if "severity" in charts:
            story.append(Image(charts["severity"], width=6.5 * inch, height=3.5 * inch))
        story.append(Paragraph(
            f"Total violations (INCs): <b>{data['total_incs']}</b>",
            styles["BodyText2"],
        ))
        story.append(Spacer(1, 0.3 * inch))

        # --- Production-Normalized Metrics ---
        if charts.get("normalized"):
            story.append(Paragraph("Production-Normalized Metrics", styles["SectionTitle"]))
            story.append(Image(charts["normalized"], width=6.5 * inch, height=3.5 * inch))
            story.append(Spacer(1, 0.3 * inch))

        # --- Root Cause Analysis ---
        if charts.get("root_cause"):
            story.append(Paragraph("Root Cause Analysis", styles["SectionTitle"]))
            story.append(Image(charts["root_cause"], width=6.5 * inch, height=3.5 * inch))
            story.append(Spacer(1, 0.3 * inch))

        # --- Recommendations ---
        if recommendations_text:
            story.append(PageBreak())
            story.append(Paragraph("Key Findings & Recommendations", styles["SectionTitle"]))
            for para in recommendations_text.strip().split("\n"):
                clean = para.replace("**", "").replace("*", "").strip()
                if clean:
                    story.append(Paragraph(clean, styles["BodyText2"]))
            story.append(Spacer(1, 0.3 * inch))

        # --- Data Sources ---
        story.append(Paragraph("Data Sources", styles["SectionTitle"]))
        story.append(Paragraph(
            "All data sourced from the Bureau of Safety and Environmental Enforcement (BSEE) "
            "public data portal at data.bsee.gov. This report uses publicly available "
            "government records and does not contain proprietary information.",
            styles["BodyText2"],
        ))
        story.append(Paragraph(
            "Tables: BSEE Incident Investigation Reports, Incidents of Non-Compliance (INCs), "
            "OCS Production data, Platform/Facility registry.",
            styles["BodyText2"],
        ))

        # Build PDF with branded page templates
        doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
        pdf_buf.seek(0)
        return pdf_buf.getvalue()


# Singleton
_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    """Get or create the singleton ReportService instance."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service

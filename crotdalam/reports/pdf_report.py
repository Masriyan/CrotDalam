import json
from html import escape

from .common import destination, envelope


class PDFReport:
    def generate(self, records, output, case_id="UNASSIGNED", analyst="Not specified"):
        try:
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.enums import TA_LEFT
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        except ImportError as exc:
            raise RuntimeError("PDF export requires ReportLab: pip install reportlab") from exc
        report = envelope(records, case_id, analyst)
        styles = getSampleStyleSheet()
        styles["BodyText"].wordWrap = "CJK"
        styles["BodyText"].alignment = TA_LEFT
        styles["Title"].textColor = colors.HexColor("#172e2a")
        story = [Paragraph("Forensic Evidence Report", styles["Title"])]
        for label, value in (("Case", case_id), ("Analyst", analyst), ("Generated UTC", report["generated_at"])):
            story.append(Paragraph(f"<b>{label}:</b> {escape(str(value))}", styles["BodyText"]))
        story.append(Paragraph("Supplied observations and hashes are not independently verified.", styles["BodyText"]))
        for index, record in enumerate(report["records"], 1):
            story.extend([Spacer(1, 16), Paragraph(f"Evidence {index:04d}", styles["Heading2"])])
            for key, value in record.items():
                text = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, dict) else str(value)
                # Separate lines allow large record bodies to flow across pages.
                story.append(Paragraph(escape(key), styles["Heading3"]))
                for line in text.splitlines() or [""]:
                    story.append(Paragraph(escape(line) or "&#160;", styles["BodyText"]))
        if not report["records"]:
            story.append(Paragraph("No records were supplied.", styles["BodyText"]))
        path = destination(output)
        SimpleDocTemplate(str(path), title="Forensic Evidence Report", author=str(analyst)).build(story)
        return path

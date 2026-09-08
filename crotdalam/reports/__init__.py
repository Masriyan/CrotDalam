"""All generators accept (records, output, case_id, analyst) and return Path."""

from .csv_report import CSVReport
from .html_report import HTMLReport
from .json_report import JSONReport
from .pdf_report import PDFReport

REPORTS = {"html": HTMLReport, "json": JSONReport, "csv": CSVReport, "pdf": PDFReport}


def generate(records, output, format="html", case_id="UNASSIGNED", analyst="Not specified"):
    if format not in REPORTS:
        raise ValueError(f"Unsupported report format: {format}")
    return REPORTS[format]().generate(records, output, case_id, analyst)


__all__ = ["HTMLReport", "PDFReport", "CSVReport", "JSONReport", "generate"]

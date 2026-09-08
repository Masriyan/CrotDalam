import csv
import json

from .common import FIELDS, destination, normalize


def safe_cell(value):
    text = str(value) if value is not None else ""
    # Spreadsheet engines may ignore leading whitespace before a formula marker.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


class CSVReport:
    def generate(self, records, output, case_id="UNASSIGNED", analyst="Not specified"):
        rows = normalize(records)
        path = destination(output)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("case_id", "analyst", *FIELDS))
            writer.writeheader()
            for record in rows:
                row = {key: record.get(key, "") for key in FIELDS}
                row.update(case_id=case_id, analyst=analyst)
                row["value"] = json.dumps(row["value"], ensure_ascii=False, allow_nan=False)
                writer.writerow({key: safe_cell(value) for key, value in row.items()})
        return path

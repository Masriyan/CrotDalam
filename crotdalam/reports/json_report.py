import json

from .common import destination, envelope


class JSONReport:
    def generate(self, records, output, case_id="UNASSIGNED", analyst="Not specified"):
        payload = envelope(records, case_id, analyst)
        path = destination(output)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        return path

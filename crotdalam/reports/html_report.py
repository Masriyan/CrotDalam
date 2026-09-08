"""Offline, script-free forensic report. All record content is untrusted."""

import json
from collections import Counter
from html import escape

from .common import UNKNOWN, destination, envelope


class HTMLReport:
    def generate(self, records, output, case_id="UNASSIGNED", analyst="Not specified"):
        report = envelope(records, case_id, analyst)
        rows = report["records"]
        esc = lambda value: escape(str(value), quote=True)
        risks = Counter()
        for record in rows:
            label = str(record["value"].get("risk", record["value"].get("severity", "unrated"))).lower()
            risks[label if label in ("critical", "high", "medium", "low", "info") else "unrated"] += 1
        bars = []
        for index, label in enumerate(("critical", "high", "medium", "low", "info", "unrated")):
            y = index * 35 + 20
            width = 260 * risks[label] / max(len(rows), 1)
            bars.append(f'<text x="0" y="{y + 13}">{label.title()}</text>'
                        f'<rect x="90" y="{y}" width="260" height="17" fill="#e4e6e2"/>'
                        f'<rect x="90" y="{y}" width="{width:.2f}" height="17" fill="#245c50"/>'
                        f'<text x="365" y="{y + 13}">{risks[label]}</text>')
        evidence = []
        for index, record in enumerate(rows, 1):
            evidence.append(f'''<article><header><span class="eyebrow">EVIDENCE {index:04d}</span>
<h3>{esc(record['data_type'])} <span class="muted">/</span> {esc(record['target'])}</h3></header>
<dl><dt>Captured</dt><dd>{esc(record.get('timestamp') or UNKNOWN)}</dd><dt>Source</dt><dd>{esc(record.get('source_url') or UNKNOWN)}</dd>
<dt>SHA-256 (supplied)</dt><dd class="mono">{esc(record.get('sha256') or UNKNOWN)}</dd></dl>
<pre>{esc(json.dumps(record['value'], indent=2, ensure_ascii=False))}</pre></article>''')
        html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>Forensic report | {esc(case_id)}</title><style>
:root{{color-scheme:light;--ink:#172e2a;--muted:#51665e;--paper:#f6f5ef;--line:#cbd3ca}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,serif}}
main{{max-width:1100px;margin:auto;padding:56px 32px}}.eyebrow,dt,.stat-label,footer{{font:12px/1.5 monospace;letter-spacing:.08em}}
.masthead{{border-top:7px solid var(--ink);border-bottom:1px solid var(--ink);padding:24px 0 30px}}
h1{{font-size:clamp(36px,6vw,66px);line-height:1.05;font-weight:400;margin:20px 0}}h2{{font-size:28px;font-weight:400}}
h3{{font-size:21px;margin:10px 0;overflow-wrap:anywhere}}.muted,dt{{color:var(--muted)}}
.summary{{display:grid;grid-template-columns:1fr 1fr;gap:44px;padding:26px 0;border-bottom:1px solid var(--line)}}
.number{{font-size:64px;line-height:1.2}}svg{{width:100%;max-width:430px;height:auto}}svg text{{font:12px monospace;fill:var(--ink)}}
article{{padding:28px 0;border-top:1px solid var(--line)}}dl{{display:grid;grid-template-columns:170px 1fr;gap:9px 18px}}
dd{{margin:0;overflow-wrap:anywhere}}pre{{background:#e9ece6;padding:22px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 monospace}}
.mono{{font-family:monospace;font-size:13px}}footer{{border-top:2px solid var(--ink);padding-top:20px}}
@media(max-width:640px){{main{{padding:24px 18px}}.summary{{grid-template-columns:1fr;gap:12px}}dl{{grid-template-columns:1fr;gap:3px}}dd{{margin-bottom:10px}}}}
@media print{{body{{background:white}}main{{padding:0}}pre{{border:1px solid #ccc}}h2,h3,dt{{break-after:avoid}}}}
</style></head><body><main>
<header class="masthead"><div class="eyebrow">CROTDALAM / INVESTIGATION RECORD</div><h1>Forensic Evidence<br>Report</h1>
<dl><dt>Case</dt><dd>{esc(case_id)}</dd><dt>Analyst</dt><dd>{esc(analyst)}</dd><dt>Generated (UTC)</dt><dd>{esc(report['generated_at'])}</dd></dl></header>
<section class="summary" aria-label="Summary"><div><div class="stat-label">RECORDED OBSERVATIONS</div><div class="number">{len(rows)}</div>
<p>{len({r['target'] for r in rows})} distinct targets. This report preserves supplied observations, not independently verified conclusions.</p></div>
<div><h2>Reported Risk Labels</h2><svg viewBox="0 0 430 235" role="img" aria-labelledby="risk-title"><title id="risk-title">Record counts by supplied risk label: {esc(', '.join(f'{k}: {risks[k]}' for k in ('critical', 'high', 'medium', 'low', 'info', 'unrated')))}</title>{''.join(bars)}</svg>
<p class="muted">Missing or unrecognized labels are unrated. No risk score is inferred.</p></div></section>
<section><h2>Evidence Register</h2>{''.join(evidence) or '<p>No records were supplied.</p>'}</section>
<footer>Schema {esc(report['schema_version'])} / Supplied hashes have not been recomputed or independently verified. Handle according to your case disclosure policy.</footer>
</main></body></html>'''
        path = destination(output)
        path.write_text(html, encoding="utf-8")
        return path

"""Bounded, offline HAR ingestion. Summaries never contain response values.

Only explicitly recognized TikTok containers become records. The retained
content is evidence, not anonymized data; protect the resulting database.
"""

import base64
import binascii
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_BODY_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 100_000
MAX_NODES = 500_000
MAX_DEPTH = 64

# Unknown segments are deliberately hidden: arbitrary slugs may be identifiers.
PATH_WORDS = set("api item list detail post recommend related search general full user profile comment reply publish digg collect favorite following follower music challenge hashtag feed live webcast room info batch report monitor log web common config status ping upload download video share node index html js css resource multi trending hot discover mssdk webmssdk get report_token getInfo get_info ads event events track pixel ttwid check heartbeat query notice inbox message settings self other mix playlist navigation seo suggest suggestion keyword feedback captcha verify region location translation translate commit delete update userinfo stats aweme v1 v2 v3 v4 v5 passport login logout auth account sdk webcast_im im service object image static assets business creative center analytics error health getClientConfig webreport browser collect_event comment_list item_list itemList userInfo UserModule users status_code status_msg tiktok login_panel".split())
SHAPE_KEYS = set("data body itemList item_list items comments userInfo UserModule ItemModule users stats user author video music challenges id cid aweme_id uniqueId unique_id nickname signature verified privateAccount desc text createTime create_time statusCode status_code statusMsg status_msg cursor hasMore has_more extra log_pb code message total logid search_id business_config appContext webapp.app-context webapp.user-detail webapp.video-detail __DEFAULT_SCOPE__ $type itemStruct item_list_data followerCount followingCount heartCount videoCount diggCount playCount commentCount shareCount collectCount duration width height cover playAddr downloadAddr secUid avatarLarger reply_comment_total reply_id search_item_list".split())


def sanitize_url(value):
    """Drop credentials/query/fragment and mask non-static path segments."""
    try:
        parsed = urlsplit(value if isinstance(value, str) else "")
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not re.fullmatch(r"[a-z0-9.-]+", host):
            return "https://redacted.invalid/"
        # Keep public service domains, not arbitrary attacker-controlled hosts.
        labels = host.split(".")
        suffixes = ("tiktok.com", "tiktokv.com", "tiktokcdn.com", "byteoversea.com", "ibytedtos.com", "ttwstatic.com", "muscdn.com")
        if not any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
            host = "redacted.invalid"
        elif len(labels) > 2:
            host = ".".join(label if label in {"www", "web", "api", "m", "us", "eu", "sg", "v16", "v19", "v21", "v45", "v77", "v99", "lf16", "lf19", "p16", "p19", "mon", "mssdk", "webcast", "webcast16-normal-c-useast1a", "webcast19-normal-c-useast1a"} else "redacted" for label in labels[:-2]) + "." + ".".join(labels[-2:])
        parts = [part if part in PATH_WORDS else "[redacted]" for part in unquote(parsed.path).split("/") if part]
        path = "/" + "/".join(parts) + ("/" if parts and parsed.path.endswith("/") else "")
        return f"{parsed.scheme}://{host}{path}"
    except (ValueError, TypeError):
        return "https://redacted.invalid/"


def _collected_at(value):
    """Aware ISO 8601 from a HAR entry startedDateTime, or None if unusable.

    HAR records this in ISO 8601; a naive or malformed value is dropped rather
    than assumed to be local time, so a record never carries a guessed origin.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _fields(node, keys):
    if not isinstance(node, dict):
        return {}
    return {key: node[key] for key in keys.split() if key in node
            and isinstance(node[key], (str, int, float, bool))
            and (not isinstance(node[key], float) or math.isfinite(node[key]))}


def _normalize(kind, node, stats=None):
    if not isinstance(node, dict):
        return None
    if kind == "video":
        if not isinstance(node.get("video"), dict):
            return None
        value = _fields(node, "id desc createTime")
        value["video"] = _fields(node["video"], "duration width height")
        value["author"] = _fields(node.get("author"), "id uniqueId nickname verified")
        value["stats"] = _fields(node.get("stats"), "diggCount playCount commentCount shareCount collectCount")
    elif kind == "profile":
        value = _fields(node, "id uniqueId nickname signature verified privateAccount")
        value["stats"] = _fields(stats, "followerCount followingCount heartCount videoCount diggCount")
        if not value.get("uniqueId"):
            return None
    else:
        value = _fields(node, "cid aweme_id text create_time digg_count reply_comment_total reply_id")
        value["user"] = _fields(node.get("user"), "uid unique_id nickname")
        if "text" not in value:
            return None
    identifier = value.get("cid" if kind == "comment" else "id")
    if not isinstance(identifier, (str, int)) or isinstance(identifier, bool) or not str(identifier).strip():
        return None
    value["availability"] = "local_har_response_only"
    return str(identifier), value


def import_har(path, *, inspect_only=False):
    """Return (records, safe_summary); inspect_only discards all record contents.

    Limits are fail-closed for the document/traversal and per-body for responses.
    Deduplication is local to this capture by kind+ID+normalized content.
    No request headers, request bodies, timings, or raw response objects survive.
    """
    try:
        with Path(path).open("rb") as stream:
            if stream.seek(0, 2) > MAX_FILE_BYTES:
                raise ValueError("HAR exceeds the 200 MiB file limit")
            stream.seek(0)
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("HAR exceeds the 200 MiB file limit")
        # Hash the exact bytes ingested so a record can be tied to its source
        # capture, not merely to an entry index within some unnamed file.
        source_sha256 = hashlib.sha256(raw).hexdigest()
        source_name = Path(path).name
        document = json.loads(raw, parse_constant=lambda _: None)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Invalid HAR JSON") from None
    except OSError:
        raise ValueError("Cannot read HAR input") from None
    del raw
    log = document.get("log") if isinstance(document, dict) else None
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError("HAR requires log.entries with at most 100000 entries")
    records, seen = [], set()
    statuses, mimes, bodies, types, shapes = (Counter() for _ in range(5))
    endpoints = {}
    duplicates = rejected = visited = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            bodies["malformed_entry"] += 1
            continue
        request = entry.get("request")
        response = entry.get("response")
        request = request if isinstance(request, dict) else {}
        response = response if isinstance(response, dict) else {}
        collected_at = _collected_at(entry.get("startedDateTime"))
        url = sanitize_url(request.get("url"))
        method = request.get("method")
        method = method if isinstance(method, str) and method in {"GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS", "CONNECT", "TRACE"} else "OTHER"
        status = response.get("status")
        status = str(status) if type(status) is int and 0 <= status <= 599 else "unknown"
        content = response.get("content")
        content = content if isinstance(content, dict) else {}
        mime = content.get("mimeType", "")
        mime = mime.split(";", 1)[0].strip().lower() if isinstance(mime, str) else ""
        mime = mime if mime in {"application/json", "text/json", "text/html", "text/plain", "text/css", "text/javascript", "application/javascript", "application/octet-stream", "image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml", "video/mp4", "audio/mpeg", "application/x-protobuf", "application/protobuf"} else "other/unknown"
        statuses[status] += 1
        mimes[mime] += 1
        endpoint = endpoints.setdefault((method, url), {"count": 0, "statuses": Counter(), "bodies": Counter(), "importable": 0})
        endpoint["count"] += 1
        endpoint["statuses"][status] += 1
        text = content.get("text")
        payload = None
        state = "missing" if text is None else "opaque"
        if isinstance(text, str):
            if not text:
                state = "empty"
            elif len(text) > MAX_BODY_BYTES * 4 // 3 + 4:
                state = "oversized"
            else:
                try:
                    encoding = content.get("encoding")
                    if encoding not in (None, "", "base64"):
                        state = "unsupported_encoding"
                    else:
                        decoded = base64.b64decode(text, validate=True) if encoding == "base64" else text.encode("utf-8")
                        if len(decoded) > MAX_BODY_BYTES:
                            state = "oversized"
                        else:
                            payload = json.loads(decoded, parse_constant=lambda _: None)
                            state = "json"
                except (UnicodeError, ValueError, binascii.Error, RecursionError):
                    state = "invalid_base64" if content.get("encoding") == "base64" and payload is None else "opaque"
                    # Valid base64 with non-JSON contents is simply opaque.
                    if content.get("encoding") == "base64":
                        try:
                            base64.b64decode(text, validate=True)
                            state = "opaque"
                        except (ValueError, binascii.Error):
                            pass
        bodies[state] += 1
        endpoint["bodies"][state] += 1
        if state != "json":
            continue
        candidates = []
        stack = [(payload, 0)]
        while stack:
            node, depth = stack.pop()
            visited += 1
            if visited > MAX_NODES or depth > MAX_DEPTH:
                raise ValueError("HAR JSON traversal budget exceeded")
            if isinstance(node, dict):
                shape = tuple(sorted({key if key in SHAPE_KEYS else "<other>" for key in node}))
                shapes[shape] += 1
                # Only recognized TikTok origins may produce evidence.
                if urlsplit(url).hostname in {"www.tiktok.com", "tiktok.com", "m.tiktok.com", "api.tiktok.com"}:
                    for key in ("itemList", "item_list", "items", "comments"):
                        if isinstance(node.get(key), list):
                            candidates.extend(("comment" if key == "comments" else "video", item, None) for item in node[key])
                    info = node.get("userInfo")
                    if isinstance(info, dict):
                        candidates.append(("profile", info.get("user"), info.get("stats")))
                    module = node.get("UserModule")
                    if isinstance(module, dict) and isinstance(module.get("users"), dict):
                        stats = module.get("stats")
                        for key, user in module["users"].items():
                            candidates.append(("profile", user, stats.get(key) if isinstance(stats, dict) else None))
                children = node.values()
            elif isinstance(node, list):
                children = node
            else:
                continue
            stack.extend((child, depth + 1) for child in children)
        for kind, node, stats in candidates:
            normalized = _normalize(kind, node, stats)
            if normalized is None:
                rejected += 1
                continue
            identifier, value = normalized
            digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
            identity = (kind, identifier, digest)
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            types[kind] += 1
            endpoint["importable"] += 1
            if not inspect_only:
                record = {"data_type": kind, "target": identifier, "value": value,
                          "source_url": url,
                          "provenance": {"collector": "har", "entry_index": index,
                                         "source_name": source_name, "source_sha256": source_sha256}}
                if collected_at is not None:
                    record["collected_at"] = collected_at
                records.append(record)
    summary = {"source": {"name": source_name, "sha256": source_sha256},
               "entries": len(entries), "statuses": dict(statuses), "mime_types": dict(mimes),
               "body_availability": dict(bodies), "importable": sum(types.values()), "data_types": dict(types),
               "duplicates": duplicates, "rejected_candidates": rejected,
               "endpoints": [{"method": method, "source_url": url, **values} for (method, url), values in sorted(endpoints.items())],
               "json_key_shapes": [{"keys": list(shape), "count": count} for shape, count in sorted(shapes.items())],
               "note": "Unknown hosts, path segments and JSON keys are redacted. Record bodies remain sensitive. Counts describe this capture only."}
    return records, summary

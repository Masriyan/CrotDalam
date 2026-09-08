"""Derive a directed graph from a corpus so NetworkAnalyzer has edges to work on.

NetworkAnalyzer consumes {"edges":[{source,target}], "nodes":[...]} but nothing
produced that shape from imported records. This bridges the two: it reads the
authorship and interaction relations already present in video, comment and
profile records and emits edges NetworkAnalyzer can rank. It invents no
relationship that is not explicit in a record.
"""

from .common import rows

MAX_NODES = 2000
MAX_EDGES = 10_000


def _node(prefix, identifier):
    if identifier is None:
        return None
    text = str(identifier).strip()
    if not text:
        return None
    return f"{prefix}:{text}"[:256]


def graph_from_corpus(data):
    """Return {"nodes":[...], "edges":[...]} for NetworkAnalyzer.

    Edges, by record type:
      video   author  -> video          (posted)
      comment user    -> video/aweme    (commented_on)
      comment user    -> parent user    (reply, when reply linkage is present)
    Node IDs are namespaced (user:, video:) so an ID reused across kinds does
    not collapse two different entities into one node.
    """
    nodes, edges, seen = set(), [], set()

    def add_edge(source, target, relation):
        if source is None or target is None or source == target:
            return
        nodes.add(source)
        nodes.add(target)
        key = (source, target, relation)
        if key in seen:
            return
        seen.add(key)
        edges.append({"source": source, "target": target, "relation": relation})

    for value in rows(data):
        author = value.get("author") if isinstance(value.get("author"), dict) else None
        user = value.get("user") if isinstance(value.get("user"), dict) else None
        # Video: author posted this video.
        if isinstance(value.get("video"), dict) or author is not None:
            video = _node("video", value.get("id"))
            actor = _node("user", (author or {}).get("uniqueId") or (author or {}).get("id"))
            add_edge(actor, video, "posted")
        # Comment: commenter -> the video it is on, and -> the account replied to.
        if "text" in value and (value.get("cid") or value.get("aweme_id")):
            commenter = _node("user", (user or {}).get("unique_id") or (user or {}).get("uid"))
            add_edge(commenter, _node("video", value.get("aweme_id")), "commented_on")
            add_edge(commenter, _node("user", value.get("reply_to_user")), "replied_to")
        if len(nodes) > MAX_NODES:
            raise ValueError("Derived graph exceeds 2000 nodes; narrow the corpus")
        if len(edges) > MAX_EDGES:
            raise ValueError("Derived graph exceeds 10000 edges; narrow the corpus")
    return {"nodes": sorted(nodes), "edges": edges}

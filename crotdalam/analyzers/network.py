"""NetworkX descriptive centrality and community analysis on imported edges."""

import networkx as nx
from .common import rows


class NetworkAnalyzer:
    """Accept {edges:[{source,target}], nodes:[str]} or dict/list edge records.

    Directed simple graph: duplicate edges are counted but collapsed, self
    loops excluded. Communities use undirected unweighted projection. Maximum
    2000 nodes/10000 edges. Betweenness samples 64 nodes above 200 nodes.
    Node identifiers must be nonempty strings <=256 characters.
    """

    def analyze(self, data):
        values = rows(data)
        declared = []
        if isinstance(data, dict) and "edges" in values[0]:
            container = values[0]
            if not isinstance(container["edges"], list):
                raise ValueError("edges must be a list")
            values = rows(container["edges"])
            declared = container.get("nodes", [])
            if not isinstance(declared, list):
                raise ValueError("nodes must be a list")
        if len(declared) > 2000:
            raise ValueError("Network exceeds 2000 declared nodes")

        def node_id(value):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError("Node IDs must be nonempty strings <=256 characters")
            return value

        graph = nx.DiGraph()
        graph.add_nodes_from(node_id(n) for n in declared)
        duplicate_edges = self_loops = 0
        for edge in values:
            source, target = node_id(edge.get("source")), node_id(edge.get("target"))
            graph.add_nodes_from((source, target))
            if graph.number_of_nodes() > 2000:
                raise ValueError("Network exceeds 2000 nodes")
            if source == target:
                self_loops += 1
                continue
            duplicate_edges += int(graph.has_edge(source, target))
            graph.add_edge(source, target)
        size = graph.number_of_nodes()
        projection = graph.to_undirected()
        communities = (list(nx.community.greedy_modularity_communities(projection))
                       if graph.number_of_edges() else [{n} for n in graph])
        groups = sorted((sorted(c) for c in communities), key=lambda c: (-len(c), c))
        degree = nx.degree_centrality(graph) if size > 1 else {n: 0.0 for n in graph}
        between = nx.betweenness_centrality(graph, k=64 if size > 200 else None, seed=0)
        return {"node_count": size, "edge_count": graph.number_of_edges(), "duplicate_edges": duplicate_edges,
                "excluded_self_loops": self_loops, "density": nx.density(graph),
                "centrality": {n: {"degree": degree[n], "betweenness": between[n],
                                   "in_degree": graph.in_degree(n), "out_degree": graph.out_degree(n)} for n in sorted(graph)},
                "communities": groups, "betweenness_approximate": size > 200,
                "uncertainty": ["Centrality describes the imported graph, not influence or coordinated abuse.",
                                "Communities use an undirected projection and may change with missing edges."]}

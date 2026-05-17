"""vis.js interactive graph rendering for encik linked entries."""

from __future__ import annotations

from typing import Any

from A_encik._display_html import _escape_html


def render_linked_graph_html(
    entry: dict[str, Any],
    max_depth: int = 2,
) -> str:
    """Render an entry and its linked graph as an interactive HTML page.

    Uses vis.js (CDN) for force-directed graph visualization of the
    entry's superklaso, subclasses, and ligilo connections.

    Args:
        entry: The root entry dict.
        max_depth: Maximum traversal depth for the graph.

    Returns:
        Full HTML document as a string.
    """
    from A_encik.service import get_service as _gs
    svc = _gs()
    graph = svc.get_linked_graph(entry["uuid"], max_depth=max_depth)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Build vis.js datasets
    from A_encik.display_helpers import entry_locale_title as _elt
    js_nodes = []
    for n in nodes:
        _label = _elt(n) or n.get("titolo", "") or n["uuid"][:8]
        _label_esc = _escape_html(_label)
        _uuid = n["uuid"]
        _depth = n.get("depth", 0)
        js_nodes.append(
            f'{{id: "{_uuid}", label: "{_label_esc}", group: {_depth}}}'
        )

    js_edges = []
    for e in edges:
        js_edges.append(
            f'{{from: "{e.get("from", "")}", to: "{e.get("to", "")}", '
            f'label: "{_escape_html(e.get("type", ""))}"}}'
        )

    nodes_json = "[\n    " + ",\n    ".join(js_nodes) + "\n  ]"
    edges_json = "[\n    " + ",\n    ".join(js_edges) + "\n  ]"

    _graph_title_str = _elt(entry) or "encik"
    title = _escape_html(_graph_title_str)

    return f"""<!DOCTYPE html>
<html lang="eo">
<head>
  <meta charset="UTF-8">
  <title>{title} — grafo</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/standalone/umd/vis-network.min.js"></script>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; }}
    #network {{ width: 100%; height: 100vh; border: none; }}
    .info {{ position: fixed; bottom: 10px; right: 10px; background: rgba(255,255,255,0.9); padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #666; }}
  </style>
</head>
<body>
  <div id="network"></div>
  <div class="info">{title} — {len(nodes)} nodoj, {len(edges)} rilatoj</div>
  <script>
    var nodes = new vis.DataSet({nodes_json});
    var edges = new vis.DataSet({edges_json});
    var container = document.getElementById("network");
    var data = {{ nodes: nodes, edges: edges }};
    var options = {{
      physics: {{ solver: "forceAtlas2Based", forceAtlas2Based: {{ gravitationalConstant: -40 }} }},
      groups: {{
        0: {{ color: {{ background: "#e74c3c", border: "#c0392b" }}, font: {{ size: 16, color: "#000" }} }},
        1: {{ color: {{ background: "#3498db", border: "#2980b9" }}, font: {{ size: 14 }} }},
        2: {{ color: {{ background: "#2ecc71", border: "#27ae60" }}, font: {{ size: 12 }} }},
        3: {{ color: {{ background: "#f39c12", border: "#e67e22" }}, font: {{ size: 12 }} }}
      }},
      edges: {{ font: {{ size: 10, color: "#666" }}, arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }} }}
    }};
    var network = new vis.Network(container, data, options);
    network.on("click", function(params) {{
      if (params.nodes.length > 0) {{
        var nodeId = params.nodes[0];
        window.location.href = "#" + nodeId;
      }}
    }});
  </script>
</body>
</html>"""


__all__ = ["render_linked_graph_html"]

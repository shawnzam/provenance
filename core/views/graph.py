"""
Link graph views.

  /graph/       — interactive vis.js graph
  /graph/data/  — JSON {nodes, edges}
"""
import json
import re
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render

from cli.paths import PROVENANCE_HOME as BASE_DIR

_WIKI_LINK_RE = re.compile(r"\[\[([^\]\n|]+)(?:\|[^\]]*)?\]\]")


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_graph() -> dict:
    """
    Walk all .md files and return {nodes: [...], edges: [...]}.

    Node schema:  {id, label, type, path}
    Edge schema:  {from, to}
    """
    from core.models import Meeting, Person

    nodes: dict[str, dict] = {}   # id → node
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    # ---- Seed nodes from DB ------------------------------------------------

    for p in Person.objects.all():
        nodes[p.slug] = {"id": p.slug, "label": p.name, "type": "person", "path": None}

    for m in Meeting.objects.all():
        nodes[m.slug] = {
            "id": m.slug,
            "label": m.title,
            "type": "meeting",
            "path": m.notes_file or None,
        }

    # ---- Walk notes/ for freeform files and extract links ------------------

    notes_dir = BASE_DIR / "notes"
    if not notes_dir.exists():
        return {"nodes": list(nodes.values()), "edges": edges}

    # Build file_path → meeting_slug so meeting note files use their DB slug
    file_to_meeting_slug: dict[str, str] = {}
    for m in Meeting.objects.all():
        if m.notes_file:
            file_to_meeting_slug[m.notes_file] = m.slug

    for md_file in sorted(notes_dir.rglob("*.md")):
        rel = str(md_file.relative_to(BASE_DIR))
        # Use meeting DB slug if this file is a meeting note, else use file stem
        slug = file_to_meeting_slug.get(rel, md_file.stem)

        # Add node for freeform notes not already seeded from DB
        if slug not in nodes:
            nodes[slug] = {
                "id": slug,
                "label": _title_from_file(md_file),
                "type": "note",
                "path": rel,
            }
        elif nodes[slug].get("path") is None:
            # DB node exists but had no path — fill it in now
            nodes[slug]["path"] = rel

        # Extract [[links]] and create edges
        try:
            content = md_file.read_text()
        except OSError:
            continue

        for m in _WIKI_LINK_RE.finditer(content):
            target_slug = m.group(1).strip()
            if target_slug == slug:
                continue  # skip self-links
            edge_key = (slug, target_slug)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append({"from": slug, "to": target_slug})

            # Ensure target has a node even if we haven't seen its file yet
            if target_slug not in nodes:
                nodes[target_slug] = {
                    "id": target_slug,
                    "label": target_slug,
                    "type": "unknown",
                    "path": None,
                }

    # ---- Build adjacency for filtering ------------------------------------
    from collections import defaultdict
    adj: dict[str, set] = defaultdict(set)
    for e in edges:
        adj[e["from"]].add(e["to"])
        adj[e["to"]].add(e["from"])

    # ---- Filter noisy nodes -----------------------------------------------
    # 1. Exclude person nodes whose only connections are to high-degree org-chart
    #    hub nodes (e.g. wharton-computing-org).  A person is "meaningful" if
    #    they appear in at least one meeting or freeform note.
    # 2. Exclude unknown nodes with very high degree — these are usually common
    #    words (e.g. "open", "context") that got accidentally linked.

    # Identify hub slugs: note nodes with degree ≥ 15 (e.g. org-chart dumps)
    hub_slugs: set[str] = {
        n["id"] for n in nodes.values()
        if n["type"] == "note" and len(adj[n["id"]]) >= 15
    }

    def _keep_node(n: dict) -> bool:
        nid = n["id"]
        neighbors = adj[nid]

        if n["type"] == "person":
            # Keep only if connected to something beyond the hub nodes
            return bool(neighbors - hub_slugs)

        if n["type"] == "unknown":
            # Drop unknown nodes with high degree (noise from common words)
            return len(neighbors) < 8

        # Notes always visible; meetings visible if connected
        if n["type"] == "note":
            return True
        return bool(neighbors)

    filtered_node_ids = {n["id"] for n in nodes.values() if _keep_node(n)}

    # Drop edges where either endpoint was filtered out
    final_edges = [e for e in edges
                   if e["from"] in filtered_node_ids and e["to"] in filtered_node_ids]

    final_nodes = [n for n in nodes.values() if n["id"] in filtered_node_ids]

    return {"nodes": final_nodes, "edges": final_edges}


def _title_from_file(path: Path) -> str:
    """Return the first # heading, or fall back to the file stem."""
    try:
        for line in path.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def graph_data(request):
    """JSON endpoint — returns nodes and edges."""
    return JsonResponse(_build_graph())


def graph_view(request):
    """Render the interactive graph page."""
    return render(request, "core/graph.html")


def node_content(request, slug):
    """Return raw markdown for a node so the browser can render it."""
    from cli.link_utils import resolve_slug
    content = resolve_slug(slug, BASE_DIR)
    if content is None:
        return JsonResponse({"error": f"No content for '{slug}'"}, status=404)
    return JsonResponse({"slug": slug, "content": content})

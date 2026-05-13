"""Knowledge graph mixin — subclass, superclass, and link graph traversal."""

from __future__ import annotations

from typing import Any


class GraphMixin:
    """Mixin for :class:`EncikService` providing graph traversal methods.

    Provides BFS-based subclass, superclass, sibling, and linked-graph
    queries for the encik knowledge graph.
    """

    def get_subclasses(
        self,
        uuid: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find all entries with *superklaso* pointing to this entry (BFS).

        Args:
            uuid: Root UUID to find subclasses for
            max_depth: Maximum traversal depth

        Returns:
            List of ``{"entry": …, "depth": int}``
        """
        entries = self.list()  # type: ignore[attr-defined]
        children_map: dict[str, set[str]] = {}

        for entry in entries:
            entry_uuid = entry.get("uuid")
            superklaso = entry.get("superklaso", [])
            if isinstance(superklaso, str):
                superklaso = [superklaso]
            for parent_uuid in superklaso:
                children_map.setdefault(parent_uuid, set()).add(entry_uuid)

        results: list[dict[str, Any]] = []
        visited: set[str] = {uuid}
        queue: list[tuple[str, int]] = [(uuid, 0)]

        while queue:
            current_uuid, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for child_uuid in children_map.get(current_uuid, set()):
                if child_uuid not in visited:
                    visited.add(child_uuid)
                    child_entry = self.get(child_uuid)  # type: ignore[attr-defined]
                    if child_entry:
                        results.append({"entry": child_entry, "depth": depth + 1})
                    queue.append((child_uuid, depth + 1))
        return results

    def get_superclasses(
        self,
        uuid: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find all entries this entry points to via *superklaso* (BFS).

        Args:
            uuid: Root UUID
            max_depth: Maximum traversal depth

        Returns:
            List of ``{"entry": …, "depth": int}``
        """
        entry = self.get(uuid)  # type: ignore[attr-defined]
        if not entry:
            return []

        results: list[dict[str, Any]] = []
        visited: set[str] = {uuid}
        queue: list[tuple[str, int]] = [
            (p, 1) for p in (entry.get("superklaso") or []) if p
        ]

        while queue:
            current_uuid, depth = queue.pop(0)
            if current_uuid in visited or depth > max_depth:
                continue
            visited.add(current_uuid)
            current_entry = self.get(current_uuid)  # type: ignore[attr-defined]
            if current_entry:
                results.append({"entry": current_entry, "depth": depth})
                for p in (current_entry.get("superklaso") or []):
                    if p and p not in visited:
                        queue.append((p, depth + 1))
        return results

    def get_siblings(
        self,
        uuid: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find entries sharing a *superklaso* with this entry.

        Args:
            uuid: Entry UUID
            limit: Max results

        Returns:
            List of sibling entries
        """
        entry = self.get(uuid)  # type: ignore[attr-defined]
        if not entry:
            return []

        my_superklaso = set(
            p for p in (entry.get("superklaso") or [])
            if isinstance(p, str) and p
        )
        if not my_superklaso:
            return []

        siblings: list[dict[str, Any]] = []
        all_entries = self.list()  # type: ignore[attr-defined]
        for e in all_entries:
            if e.get("uuid") == uuid:
                continue
            e_super = set(
                p for p in (e.get("superklaso") or [])
                if isinstance(p, str) and p
            )
            if my_superklaso & e_super:
                siblings.append(e)
                if len(siblings) >= limit:
                    break
        return siblings

    @staticmethod
    def _node_name(entry: dict) -> str:
        """Get a display name for a graph node from terminologio."""
        term = entry.get("terminologio") or {}
        for lang in ("eo", "en"):
            val = term.get(lang)
            if val:
                return str(val)
        for val in term.values():
            if val:
                return str(val)
        return entry.get("uuid", "")[:8]

    def get_linked_graph(
        self,
        uuid: str,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Get full graph of related entries (subclasses, superclasses, links).

        Args:
            uuid: Root UUID
            max_depth: Maximum traversal depth

        Returns:
            ``{"nodes": […], "edges": […]}"``
        """
        entry = self.get(uuid)  # type: ignore[attr-defined]
        if not entry:
            return {"nodes": [], "edges": []}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[str] = {uuid}

        nodes.append({
            "uuid": uuid,
            "titolo": self._node_name(entry),
            "depth": 0,
        })

        queue: list[tuple[str, int, str]] = []
        for p in (entry.get("superklaso") or []):
            if p:
                queue.append((p, 1, "superklaso"))
        for link in (entry.get("ligilo") or []):
            link_uuid = link if isinstance(link, str) else link[0]
            if link_uuid:
                queue.append((link_uuid, 1, "ligilo"))

        while queue:
            current_uuid, depth, rel_type = queue.pop(0)
            if current_uuid in visited or depth > max_depth:
                continue
            visited.add(current_uuid)
            current_entry = self.get(current_uuid)  # type: ignore[attr-defined]
            if current_entry:
                nodes.append({
                    "uuid": current_uuid,
                    "titolo": self._node_name(current_entry),
                    "depth": depth,
                })
                edges.append({
                    "from": uuid if depth == 1 else "",
                    "to": current_uuid,
                    "type": rel_type,
                })
                for p in (current_entry.get("superklaso") or []):
                    if p and p not in visited:
                        queue.append((p, depth + 1, "superklaso"))
                for link in (current_entry.get("ligilo") or []):
                    lu = link if isinstance(link, str) else link[0]
                    if lu and lu not in visited:
                        queue.append((lu, depth + 1, "ligilo"))
        return {"nodes": nodes, "edges": edges}

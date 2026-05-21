"""Bidirectional link mixin — reverse relation syncing for all link types."""

from __future__ import annotations

import json
from typing import Any


class LinksMixin:
    """Mixin for :class:`EncikService` providing bidirectional link management.

    When entry A has a *ligilo* entry pointing to entry B (via inline links,
    explicit ligilo, or superklaso), an automatic reverse link is added to
    B's *ligilo*. When links are removed from A, the stale reverse is cleaned
    up from B.
    """

    # Mapping of semantic relations and their inverses.
    # ec# prefix is stripped before lookup; non-mapped types get "ec#related".
    _REVERSE_MAP: dict[str, str] = {
        "rdfs:subClassOf": "rdfs:hasSubClass",
        "rdfs:hasSubClass": "rdfs:subClassOf",
        "rdf:type": "rdf:hasInstance",
        "rdf:hasInstance": "rdf:type",
        "wdt:P361": "wdt:P527",
        "wdt:P527": "wdt:P361",
        "wdt:P26": "wdt:P26",
    }

    @staticmethod
    def _reverse_tipo(tipo: str | None) -> str:
        """Get the reverse relation type for a given link type.

        Strips ``ec#`` prefix before lookup. Returns ``ec#related`` for
        unknown types.
        """
        if not tipo:
            return "ec#related"
        raw = tipo[3:] if tipo.startswith("ec#") else tipo
        rev = LinksMixin._REVERSE_MAP.get(raw)
        if rev:
            return f"ec#{rev}"
        return "ec#related"

    @staticmethod
    def _link_uuid(link: Any) -> str:
        """Extract UUID from a ligilo entry (list [uuid, tipo] or bare str)."""
        return link[0] if isinstance(link, list) else link

    def _add_reverse_link(
        self, source_uuid: str, target_uuid: str, tipo: str | None
    ) -> None:
        """Add a reverse link to *target_uuid* pointing back to *source_uuid*.

        Skips if the reverse link already exists.
        Uses direct DB update to avoid recursive ``_sync_links``.
        """
        target = self.get(target_uuid)
        if not target:
            return
        ligilo = target.get("ligilo") or []
        if isinstance(ligilo, str):
            try:
                ligilo = json.loads(ligilo)
            except (json.JSONDecodeError, ValueError):
                ligilo = []
        for link in (ligilo or []):
            if self._link_uuid(link) == source_uuid:
                return
        reverse_tipo = self._reverse_tipo(tipo)
        ligilo.append([source_uuid, reverse_tipo])
        # Direct DB write — avoid self.update() recursion
        self.db.execute(
            "UPDATE encik SET ligilo = ?, modifita_je = datetime('now') WHERE uuid = ?",
            (json.dumps(ligilo, ensure_ascii=False), target_uuid),
        )

    def _remove_reverse_link(self, source_uuid: str, target_uuid: str) -> None:
        """Remove any reverse link pointing to *source_uuid* from *target_uuid*.

        Uses direct DB update to avoid recursive ``_sync_links``.
        """
        target = self.get(target_uuid)
        if not target:
            return
        ligilo = target.get("ligilo") or []
        if isinstance(ligilo, str):
            try:
                ligilo = json.loads(ligilo)
            except (json.JSONDecodeError, ValueError):
                ligilo = []
        new_ligilo = [
            link for link in (ligilo or [])
            if self._link_uuid(link) != source_uuid
        ]
        if len(new_ligilo) != len(ligilo):
            self.db.execute(
                "UPDATE encik SET ligilo = ?, modifita_je = datetime('now') WHERE uuid = ?",
                (json.dumps(new_ligilo, ensure_ascii=False), target_uuid),
            )

    @staticmethod
    def _ligilo_uuids(ligilo: Any) -> set[str]:
        """Extract set of UUIDs from a ligilo list (normalised to lowercase)."""
        uuids: set[str] = set()
        for item in (ligilo or []):
            uid = item[0] if isinstance(item, list) else item
            if isinstance(uid, str):
                uuids.add(uid.lower())
        return uuids

    def _sync_bidirectional_relations(
        self, entry: dict[str, Any], previous_ligilo: list | None = None
    ) -> None:
        """Sync bidirectional relations by diffing old vs new ligilo.

        Called during update. Compares the previous ligilo (from DB before
        update) with the current ligilo (after ``_sync_links`` rebuilt it).
        Adds reverse links for newly added references and removes stale
        reverse links for removed references.
        """
        entry_uuid = entry.get("uuid", "")

        # Read the post-sync ligilo from DB (set by _sync_links)
        current = self.get(entry_uuid)
        if not current:
            return
        new_ligilo = current.get("ligilo") or []

        old_uuids = self._ligilo_uuids(previous_ligilo)
        new_uuids = self._ligilo_uuids(new_ligilo)

        added = new_uuids - old_uuids
        removed = old_uuids - new_uuids

        # Build a tipo map from the new ligilo for added links
        tipo_map: dict[str, str] = {}
        for item in (new_ligilo or []):
            if isinstance(item, list) and len(item) >= 2:
                tipo_map[item[0].lower()] = str(item[1])

        for target_uuid in added:
            tipo = tipo_map.get(target_uuid.lower())
            self._add_reverse_link(entry_uuid, target_uuid, tipo)

        for target_uuid in removed:
            self._remove_reverse_link(entry_uuid, target_uuid)

    def _remove_stale_reverse_links(
        self, uuid: str, old_ligilo: list
    ) -> None:
        """Remove reverse links from entries that pointed to this one.

        Uses a targeted SQL query (``LIKE`` on ligilo column) to find
        only candidates, avoiding a full table scan.
        Uses direct DB write to avoid recursive ``_sync_links``.
        """
        rows = self.db.execute(
            "SELECT uuid, ligilo FROM encik WHERE ligilo LIKE ?",
            (f"%{uuid}%",),
        )
        for row in rows:
            ligilo_raw = row.get("ligilo") or "[]"
            ligilo: Any = []
            if isinstance(ligilo_raw, str):
                try:
                    ligilo = json.loads(ligilo_raw)
                except (json.JSONDecodeError, ValueError):
                    continue
            elif isinstance(ligilo_raw, list):
                ligilo = ligilo_raw
            modified = False
            new_ligilo = []
            for link in ligilo:
                link_uuid = link if isinstance(link, str) else link[0]
                if link_uuid != uuid:
                    new_ligilo.append(link)
                else:
                    modified = True
            if modified:
                self.db.execute(
                    "UPDATE encik SET ligilo = ?, modifita_je = datetime('now') WHERE uuid = ?",
                    (json.dumps(new_ligilo, ensure_ascii=False), row["uuid"]),
                )

"""Bidirectional link mixin — reverse relation syncing for superklaso."""

from __future__ import annotations

from typing import Any


class LinksMixin:
    """Mixin for :class:`EncikService` providing bidirectional link management.

    When entry A has *superklaso* referencing entry B, an automatic reverse
    ``rdfs:hasSubClass`` link is added to B's *ligilo*.
    """

    # Mapping of semantic relations and their inverses
    _REVERSE_MAP: dict[str, str] = {
        "rdfs:subClassOf": "rdfs:hasSubClass",
        "rdfs:hasSubClass": "rdfs:subClassOf",
        "rdf:type": "rdf:hasInstance",
        "rdf:hasInstance": "rdf:type",
        "wdt:P361": "wdt:P527",
        "wdt:P527": "wdt:P361",
        "wdt:P26": "wdt:P26",
    }

    def _reverse_ligilo(self, tipo: str | None) -> str | None:
        """Get the reverse relation type for a given semantic link type."""
        if not tipo:
            return None
        return self._REVERSE_MAP.get(tipo)

    def _sync_bidirectional_relations(
        self,
        entry: dict[str, Any],
        previous_ligilo: list | None = None,
    ) -> None:
        """Sync bidirectional superklaso/ligilo relations.

        When an entry has *superklaso* references, automatically add
        reverse *ligilo* entries in the target entries.
        """
        superklaso = entry.get("superklaso", [])
        if isinstance(superklaso, str):
            superklaso = [superklaso]
        reverse_uuid = entry.get("uuid")

        for parent_uuid in superklaso:
            if not parent_uuid:
                continue
            parent = self.get(parent_uuid)  # type: ignore[attr-defined]
            if not parent:
                continue

            ligilo = parent.get("ligilo", [])
            if isinstance(ligilo, str):
                ligilo = [ligilo]

            needs_add = True
            for link in ligilo:
                link_uuid = link if isinstance(link, str) else link[0]
                if link_uuid == reverse_uuid:
                    needs_add = False
                    break

            if needs_add:
                new_ligilo = ligilo + [[reverse_uuid, "rdfs:hasSubClass"]]
                self.update(parent_uuid, {"ligilo": new_ligilo})  # type: ignore[attr-defined]

    def _remove_stale_reverse_links(
        self,
        uuid: str,
        old_ligilo: list,
    ) -> None:
        """Remove reverse links from entries that pointed to this one."""
        all_entries = self.list()  # type: ignore[attr-defined]
        for entry in all_entries:
            ligilo = entry.get("ligilo", [])
            if isinstance(ligilo, str):
                ligilo = [ligilo]
            modified = False
            new_ligilo = []
            for link in ligilo:
                link_uuid = link if isinstance(link, str) else link[0]
                if link_uuid != uuid:
                    new_ligilo.append(link)
                else:
                    modified = True
            if modified:
                self.update(entry["uuid"], {"ligilo": new_ligilo})  # type: ignore[attr-defined]

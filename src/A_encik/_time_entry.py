"""Time entry creation mixin — year → decade → century hierarchy."""

from __future__ import annotations

from typing import Any


class TimeEntryMixin:
    """Mixin for :class:`EncikService` providing calendar time hierarchy creation.

    Provides ``ensure_year()``, ``ensure_decade()``, ``ensure_century()``
    which cascade: century → decade → year, each setting the previous as
    ``superklaso`` (parent). All methods are idempotent.
    """

    # Type reference entry titles for the Gregorian calendar hierarchy.
    # These are auto-created on first use if they do not exist yet.
    _TYPE_ENTRY_TITLES: dict[str, str] = {
        "jaro": "jaro",
        "jardeko": "jardeko",
        "jarcento": "jarcento",
        "gregoria": "Gregoria kalendaro",
    }

    def _ensure_type_ref(self, key: str) -> str:
        """Get or create a type-reference entry, returning a UUID prefix.

        For backward compatibility with existing databases that may have
        these entries under arbitrary UUIDs, resolves by ``titolo`` match
        rather than hardcoding UUIDs.

        Args:
            key: ``"jaro"``, ``"jardeko"``, ``"jarcento"``, or ``"gregoria"``

        Returns:
            8-character UUID prefix
        """
        titolo = self._TYPE_ENTRY_TITLES.get(key)
        if not titolo:
            return ""
        existing = self.find_by_titolo(titolo)  # type: ignore[attr-defined]
        if existing:
            return existing["uuid"][:8]
        data: dict[str, Any] = {
            "titolo": titolo,
            "terminologio": {"eo": titolo},
            "difinoj": {"eo": f"Tipo: {titolo}"},
        }
        entry = self.create(data)  # type: ignore[attr-defined]
        return entry["uuid"][:8]

    @staticmethod
    def _validate_year(year: int) -> None:
        """Validate a year value for entry creation.

        Args:
            year: Positive integer year (1-3000)

        Raises:
            ValueError: If year is out of range
        """
        if not isinstance(year, int):
            raise ValueError("Jaro devas esti entjero")
        if year < 1:
            raise ValueError("Jaro devas esti pozitiva")
        if year > 3000:
            raise ValueError("Jaro tro granda (maksimumo: 3000)")

    @staticmethod
    def parse_year_text(text: str) -> int | None:
        """Parse a year string (CE or BCE) into a positive integer.

        Accepts ``"1879"`` → 1879, ``"44 BCE"`` → 44.

        Returns the numeric year (always positive), or *None* if not valid.
        """
        t = text.strip()
        bce_suffixes = ("bce", "bc", "a.k.e.", "a.k.")
        is_bce = any(t.lower().endswith(s) for s in bce_suffixes)
        if is_bce:
            for s in bce_suffixes:
                if t.lower().endswith(s):
                    t = t[: -len(s)].strip()
                    break
        if t.isdigit() and 1 <= len(t) <= 4:
            return int(t)
        return None

    @staticmethod
    def _era_label(bce: bool) -> tuple[str, str]:
        """Return (short, long) BCE/CE suffix labels."""
        if bce:
            return " a.K.E.", " (a.K.E.)"
        return "", ""

    def _find_or_create(
        self,
        titolo: str,
        terminologio_eo: str,
        difino_eo: str,
        superklaso: list[str] | None = None,
    ) -> str:
        """Find an entry by terminologio or create it. Returns UUID."""
        existing = self.find_by_terminologio(  # type: ignore[attr-defined]
            {"eo": terminologio_eo}
        )
        if existing:
            return existing["uuid"]

        data: dict[str, Any] = {
            "terminologio": {"eo": terminologio_eo},
            "difinoj": {"eo": difino_eo},
        }
        if superklaso:
            data["superklaso"] = superklaso
        entry = self.create(data)  # type: ignore[attr-defined]
        return entry["uuid"]

    def ensure_century(
        self,
        century: int,
        bce: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or retrieve a century entry. Idempotent.

        Cascades: creates type-reference entries (jarcento, Gregoria
        kalendaro) if they do not exist yet.

        Args:
            century: Century number (e.g. 18 for the 18th century)
            bce: *True* for BCE/BC centuries
            extra_fields: Optional extra fields to merge into the entry

        Returns:
            The century entry dict
        """
        self._validate_year(century * 100)
        _suf_short, _suf_long = self._era_label(bce)
        jarc_ref = self._ensure_type_ref("jarcento")
        greg_ref = self._ensure_type_ref("gregoria")

        eo_term = f"{century}a jarcento{_suf_long} (kalendara jarcento)"
        existing = self.find_by_terminologio(  # type: ignore[attr-defined]
            {"eo": eo_term}
        )
        if existing:
            if extra_fields:
                existing.update(extra_fields)
                self.update(existing["uuid"], existing)  # type: ignore[attr-defined]
            return existing

        data: dict[str, Any] = {
            "terminologio": {"eo": eo_term},
            "difinoj": {
                "eo": (
                    f"[jarcento](#{jarc_ref}, rdf:type) "
                    f"de la [Gregoria kalendaro](#{greg_ref}, wdt:P361)"
                ),
            },
        }
        if extra_fields:
            data.update(extra_fields)
        return self.create(data)  # type: ignore[attr-defined]

    def ensure_decade(
        self,
        decade_start: int,
        bce: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or retrieve a decade entry. Idempotent.

        Cascades: creates the parent century (and type entries) if needed.

        Args:
            decade_start: Decade start year (must be multiple of 10, e.g. 1780)
            bce: *True* for BCE/BC decades
            extra_fields: Optional extra fields to merge

        Returns:
            The decade entry dict
        """
        self._validate_year(decade_start)
        if decade_start % 10 != 0:
            raise ValueError("Jardeko devas esti oblo de 10 (ekz. 1780)")
        _suf_short, _suf_long = self._era_label(bce)
        jard_ref = self._ensure_type_ref("jardeko")
        greg_ref = self._ensure_type_ref("gregoria")
        century_num = (decade_start - 1) // 100 + 1
        century_entry = self.ensure_century(century_num, bce=bce)

        label = f"{decade_start}a jardeko{_suf_long}"
        eo_label = f"{label} (kalendara jardeko)"
        existing = self.find_by_terminologio(  # type: ignore[attr-defined]
            {"eo": eo_label}
        )
        if existing:
            if extra_fields:
                existing.update(extra_fields)
                self.update(existing["uuid"], existing)  # type: ignore[attr-defined]
            return existing

        data: dict[str, Any] = {
            "terminologio": {"eo": eo_label},
            "difinoj": {
                "eo": (
                    f"[jardeko](#{jard_ref}, rdf:type) "
                    f"de la [Gregoria kalendaro](#{greg_ref}, wdt:P361)"
                ),
            },
            "superklaso": [century_entry["uuid"]],
        }
        if extra_fields:
            data.update(extra_fields)
        return self.create(data)  # type: ignore[attr-defined]

    def ensure_year(
        self,
        year: int,
        bce: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or retrieve a year entry with century → decade → year hierarchy.

        Idempotent — if the year entry already exists, returns it.
        Cascades: creates parent decade and century entries as needed.

        Args:
            year: Year number (1-3000)
            bce: *True* for BCE/BC years
            extra_fields: Optional extra fields to merge into the year entry

        Returns:
            The year entry dict
        """
        self._validate_year(year)
        _suf_short, _suf_long = self._era_label(bce)
        jaro_ref = self._ensure_type_ref("jaro")
        greg_ref = self._ensure_type_ref("gregoria")
        decade_start = (year // 10) * 10
        decade_entry = self.ensure_decade(decade_start, bce=bce)

        label = f"{year}{_suf_short}"
        eo_label = f"{label} (kalendara jaro)"
        existing = self.find_by_terminologio(  # type: ignore[attr-defined]
            {"eo": eo_label}
        )
        if existing:
            if extra_fields:
                existing.update(extra_fields)
                self.update(existing["uuid"], existing)  # type: ignore[attr-defined]
            return existing

        data: dict[str, Any] = {
            "terminologio": {"eo": eo_label},
            "difinoj": {
                "eo": (
                    f"[jaro](#{jaro_ref}, rdf:type) "
                    f"de la [Gregoria kalendaro](#{greg_ref}, wdt:P361)"
                ),
            },
            "superklaso": [decade_entry["uuid"]],
        }
        if extra_fields:
            data.update(extra_fields)
        return self.create(data)  # type: ignore[attr-defined]

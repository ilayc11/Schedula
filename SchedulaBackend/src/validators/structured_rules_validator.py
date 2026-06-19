"""Contract-preserving validator for secretary edits of structured rules.

A lecturer's structured rule has a stable shape:

    {
        "atomic_constraints": [
            {
                "type": "block" | "preference",
                "days": [int, ...],            # 1..6, unique, non-empty
                "time_slot": null | {
                    "start_hour": int,         # 0..23
                    "end_hour": int,           # 0..24 (24 means "until end of day")
                    "start_minute": int,       # 0..59 (default 0)
                    "end_minute": int          # 0..59 (default 0)
                },
                "priority": "hard" | "soft"
            },
            ...
        ]
    }

When a secretary edits the rules we accept add / edit / delete operations,
but the `type` of any *surviving* atomic must not change (a "block" stays a
block, a "preference" stays a preference). Atomics are matched between old
and new lists positionally — index 0 in the new list corresponds to the
atomic that was at index 0 in the old list. Any new atomics appended at
the tail are considered fresh additions and may have any valid `type`.
"""

from typing import Any, Dict, List, Optional, Tuple


VALID_TYPES = {"block", "preference"}
VALID_PRIORITIES = {"hard", "soft"}
MIN_DAY = 1
MAX_DAY = 6


class StructuredRulesValidationError(Exception):
    """Raised when secretary-authored structured rules violate the contract.

    Carries a list of (path, message) field-level errors so the API layer can
    return them as a structured 422 response.
    """

    def __init__(self, errors: List[Tuple[str, str]]):
        self.errors = errors
        joined = "; ".join(f"{p}: {m}" for p, m in errors)
        super().__init__(f"Structured rules validation failed: {joined}")

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "errors": [{"path": p, "message": m} for p, m in self.errors],
        }


class StructuredRulesValidator:
    """Stateless validator. Use the class method :meth:`validate`."""

    @classmethod
    def validate(
        cls,
        old_rules: Optional[Dict[str, Any]],
        new_rules: Dict[str, Any],
    ) -> None:
        """Validate ``new_rules`` against the structural contract and the
        type-lock constraint relative to ``old_rules``.

        Raises :class:`StructuredRulesValidationError` if any check fails.
        """
        errors: List[Tuple[str, str]] = []

        if not isinstance(new_rules, dict):
            raise StructuredRulesValidationError(
                [("structured_rules", "must be an object")]
            )

        atomics = new_rules.get("atomic_constraints")
        if not isinstance(atomics, list):
            raise StructuredRulesValidationError(
                [("atomic_constraints", "must be a list")]
            )
        if len(atomics) == 0:
            raise StructuredRulesValidationError(
                [("atomic_constraints", "must contain at least one entry")]
            )

        # Per-atomic structural validation
        for i, atomic in enumerate(atomics):
            cls._validate_atomic(atomic, i, errors)

        # Reject duplicate atomics within the new list
        seen_signatures: Dict[str, int] = {}
        for i, atomic in enumerate(atomics):
            sig = cls._signature(atomic)
            if sig is None:
                continue  # skip atomics that already failed structural validation
            if sig in seen_signatures:
                errors.append(
                    (
                        f"atomic_constraints[{i}]",
                        f"duplicates atomic_constraints[{seen_signatures[sig]}]",
                    )
                )
            else:
                seen_signatures[sig] = i

        # Type-lock check: surviving atomics keep their original `type`.
        # Match positionally; any extra atomics at the tail of the new list are
        # treated as fresh additions (no type lock).
        old_atomics = []
        if isinstance(old_rules, dict):
            maybe_old = old_rules.get("atomic_constraints")
            if isinstance(maybe_old, list):
                old_atomics = maybe_old

        for i in range(min(len(old_atomics), len(atomics))):
            old_type = (
                old_atomics[i].get("type") if isinstance(old_atomics[i], dict) else None
            )
            new_type = (
                atomics[i].get("type") if isinstance(atomics[i], dict) else None
            )
            if old_type and new_type and old_type != new_type:
                errors.append(
                    (
                        f"atomic_constraints[{i}].type",
                        f"type cannot change from '{old_type}' to '{new_type}'",
                    )
                )

        if errors:
            raise StructuredRulesValidationError(errors)

    @classmethod
    def _validate_atomic(
        cls, atomic: Any, index: int, errors: List[Tuple[str, str]]
    ) -> None:
        prefix = f"atomic_constraints[{index}]"
        if not isinstance(atomic, dict):
            errors.append((prefix, "must be an object"))
            return

        # type
        a_type = atomic.get("type")
        if a_type not in VALID_TYPES:
            errors.append(
                (
                    f"{prefix}.type",
                    f"must be one of {sorted(VALID_TYPES)} (got {a_type!r})",
                )
            )

        # days
        days = atomic.get("days")
        if not isinstance(days, list) or len(days) == 0:
            errors.append((f"{prefix}.days", "must be a non-empty list"))
        else:
            seen = set()
            for j, d in enumerate(days):
                if not isinstance(d, int) or isinstance(d, bool):
                    errors.append(
                        (f"{prefix}.days[{j}]", "must be an integer in 1..6")
                    )
                    continue
                if d < MIN_DAY or d > MAX_DAY:
                    errors.append(
                        (
                            f"{prefix}.days[{j}]",
                            f"must be between {MIN_DAY} and {MAX_DAY} (got {d})",
                        )
                    )
                if d in seen:
                    errors.append(
                        (f"{prefix}.days[{j}]", f"duplicate day {d}")
                    )
                seen.add(d)

        # time_slot
        time_slot = atomic.get("time_slot")
        if time_slot is not None:
            cls._validate_time_slot(time_slot, f"{prefix}.time_slot", errors)

        # priority
        priority = atomic.get("priority")
        if priority not in VALID_PRIORITIES:
            errors.append(
                (
                    f"{prefix}.priority",
                    f"must be one of {sorted(VALID_PRIORITIES)} (got {priority!r})",
                )
            )

    @classmethod
    def _validate_time_slot(
        cls, time_slot: Any, prefix: str, errors: List[Tuple[str, str]]
    ) -> None:
        if not isinstance(time_slot, dict):
            errors.append((prefix, "must be null or an object"))
            return

        start_hour = time_slot.get("start_hour")
        end_hour = time_slot.get("end_hour")
        start_minute = time_slot.get("start_minute", 0) or 0
        end_minute = time_slot.get("end_minute", 0) or 0

        valid_hours = True
        for name, val, lo, hi in (
            ("start_hour", start_hour, 0, 23),
            ("end_hour", end_hour, 0, 24),
        ):
            if not isinstance(val, int) or isinstance(val, bool):
                errors.append((f"{prefix}.{name}", "must be an integer"))
                valid_hours = False
            elif val < lo or val > hi:
                errors.append(
                    (f"{prefix}.{name}", f"must be between {lo} and {hi} (got {val})")
                )
                valid_hours = False

        valid_minutes = True
        for name, val in (("start_minute", start_minute), ("end_minute", end_minute)):
            if not isinstance(val, int) or isinstance(val, bool):
                errors.append((f"{prefix}.{name}", "must be an integer"))
                valid_minutes = False
            elif val < 0 or val > 59:
                errors.append(
                    (f"{prefix}.{name}", f"must be between 0 and 59 (got {val})")
                )
                valid_minutes = False

        # start < end at minute resolution
        if valid_hours and valid_minutes:
            start_total = start_hour * 60 + start_minute
            end_total = end_hour * 60 + end_minute
            if start_total >= end_total:
                errors.append(
                    (
                        prefix,
                        f"start ({start_hour:02d}:{start_minute:02d}) must be before "
                        f"end ({end_hour:02d}:{end_minute:02d})",
                    )
                )

    @staticmethod
    def _signature(atomic: Dict[str, Any]) -> Optional[str]:
        """Build a comparable signature for duplicate detection. Returns None
        when the atomic is malformed (already reported by structural checks)."""
        try:
            days_part = ",".join(str(d) for d in sorted(atomic.get("days", [])))
            ts = atomic.get("time_slot")
            if ts is None:
                ts_part = "fullday"
            else:
                ts_part = (
                    f"{ts.get('start_hour')}:{ts.get('start_minute', 0) or 0}"
                    f"-{ts.get('end_hour')}:{ts.get('end_minute', 0) or 0}"
                )
            return f"{atomic.get('type')}|{days_part}|{ts_part}|{atomic.get('priority')}"
        except (TypeError, AttributeError):
            return None


# ---------------------------------------------------------------------------
# Preview text builder
# ---------------------------------------------------------------------------

DAY_NAMES = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
}


def _format_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _format_days(days: List[int]) -> str:
    if not days:
        return "(no days)"
    names = [DAY_NAMES.get(d, str(d)) for d in sorted(days)]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def build_preview_text(structured_rules: Dict[str, Any]) -> str:
    """Generate a human-readable preview from structured_rules.

    Mirrors the FE ``prettyRulesFromStructured`` so when the secretary doesn't
    supply ``raw_text`` the constraint card still shows something readable.
    """
    if not isinstance(structured_rules, dict):
        return ""

    atomics = structured_rules.get("atomic_constraints") or []
    if not isinstance(atomics, list) or not atomics:
        return ""

    lines: List[str] = []
    for atomic in atomics:
        if not isinstance(atomic, dict):
            continue

        a_type = atomic.get("type", "block")
        priority = atomic.get("priority", "soft")
        days = atomic.get("days") or []
        time_slot = atomic.get("time_slot")

        verb = "blocks" if a_type == "block" else "prefers no classes"
        priority_word = "hard" if priority == "hard" else "soft"

        if time_slot is None:
            time_part = "all day"
        else:
            sh = time_slot.get("start_hour", 0)
            eh = time_slot.get("end_hour", 0)
            sm = time_slot.get("start_minute", 0) or 0
            em = time_slot.get("end_minute", 0) or 0
            time_part = f"{_format_time(sh, sm)}-{_format_time(eh, em)}"

        lines.append(
            f"{verb.capitalize()} {_format_days(days)} {time_part} ({priority_word})"
        )

    return ". ".join(lines)

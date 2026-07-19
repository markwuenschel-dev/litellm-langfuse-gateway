"""File-backed cost reconciliation engine (INT-116 / S1′).

Pure comparison over a YAML run artifact. No network I/O. Does not invent amounts.
LLG_LIVE does not gate this path — it is reserved for future fetchers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import yaml

__all__ = [
    "CORE_SOURCE_ROLES",
    "LoadError",
    "PairReport",
    "ReconcileResult",
    "RunDocument",
    "SourceAmount",
    "format_human",
    "format_json",
    "load_run",
    "pair_within",
    "reconcile",
]

CORE_SOURCE_ROLES: frozenset[str] = frozenset({"provider", "litellm", "langfuse"})
_ALLOWED_ROLES: frozenset[str] = CORE_SOURCE_ROLES | frozenset({"custom"})
_ALLOWED_PROVENANCE: frozenset[str] = frozenset({"manual", "export", "api"})

# Dashboard-only URLs are not immutable evidence.
_DASHBOARD_ONLY = re.compile(
    r"^https?://",
    re.IGNORECASE,
)


class LoadError(ValueError):
    """Invalid or incomplete run artifact (maps to CLI exit 2)."""

    def __init__(self, message: str, *, code: str = "invalid_run") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime

    def as_dict(self) -> dict[str, str]:
        return {"start": _fmt_dt(self.start), "end": _fmt_dt(self.end)}


@dataclass(frozen=True)
class SourceAmount:
    source_role: str
    source_id: str
    amount: Decimal
    period: Period
    collected_at: datetime
    evidence_ref: str
    provenance: str
    inclusion_basis: str | None = None


@dataclass(frozen=True)
class Group:
    id: str
    comparison_scope_id: str
    inclusion_basis: str
    sources: tuple[SourceAmount, ...]


@dataclass(frozen=True)
class Tolerance:
    relative: Decimal
    absolute: Decimal


@dataclass(frozen=True)
class RunDocument:
    schema_version: int
    run_id: str
    currency: str
    tolerance: Tolerance
    required_source_roles: tuple[str, ...]
    groups: tuple[Group, ...]


@dataclass(frozen=True)
class PairReport:
    left_role: str
    right_role: str
    left_amount: str
    right_amount: str
    difference: str
    limit: str
    relative_delta: str | None
    within: bool


@dataclass
class GroupResult:
    group_id: str
    comparison_scope_id: str
    status: Literal["within", "outside", "unproven_zero_cost_group", "invalid"]
    pairs: list[PairReport] = field(default_factory=list)
    detail: str | None = None


@dataclass
class ReconcileResult:
    run_id: str
    currency: str
    complete: bool
    within_tolerance: bool
    exit_code: int
    reason_code: str
    groups: list[GroupResult]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "currency": self.currency,
            "complete": self.complete,
            "within_tolerance": self.within_tolerance,
            "exit_code": self.exit_code,
            "reason_code": self.reason_code,
            "errors": list(self.errors),
            "groups": [
                {
                    "group_id": g.group_id,
                    "comparison_scope_id": g.comparison_scope_id,
                    "status": g.status,
                    "detail": g.detail,
                    "pairs": [
                        {
                            "left_role": p.left_role,
                            "right_role": p.right_role,
                            "left_amount": p.left_amount,
                            "right_amount": p.right_amount,
                            "difference": p.difference,
                            "limit": p.limit,
                            "relative_delta": p.relative_delta,
                            "within": p.within,
                        }
                        for p in g.pairs
                    ],
                }
                for g in self.groups
            ],
        }


def pair_within(
    a: Decimal,
    b: Decimal,
    *,
    relative: Decimal,
    absolute: Decimal,
) -> tuple[bool, Decimal, Decimal, Decimal | None]:
    """DOC′ pairwise rule. Returns (within, difference, limit, relative_delta|None)."""
    difference = abs(a - b)
    scale = max(abs(a), abs(b))
    limit = max(relative * scale, absolute)
    if a == 0 and b == 0:
        relative_delta: Decimal | None = None
    elif scale == 0:
        relative_delta = None
    else:
        relative_delta = difference / scale
    return difference <= limit, difference, limit, relative_delta


def load_run(path: Path) -> RunDocument:
    """Load and validate a reconciliation YAML run file."""
    if not path.is_file():
        raise LoadError(f"run file not found: {path}", code="run_file_missing")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LoadError(f"YAML parse error: {exc}", code="yaml_parse") from exc
    if not isinstance(raw, dict):
        raise LoadError("root document must be a mapping", code="invalid_run")
    return _parse_run(raw)


def reconcile(run: RunDocument) -> ReconcileResult:
    """Pure evaluation of a loaded run. No I/O."""
    group_results: list[GroupResult] = []
    errors: list[str] = []

    for group in run.groups:
        gr, err = _reconcile_group(group, run)
        group_results.append(gr)
        if err:
            errors.append(err)

    if any(g.status == "unproven_zero_cost_group" for g in group_results):
        return ReconcileResult(
            run_id=run.run_id,
            currency=run.currency,
            complete=False,
            within_tolerance=False,
            exit_code=2,
            reason_code="unproven_zero_cost_group",
            groups=group_results,
            errors=errors or ["one or more groups have all required amounts zero"],
        )

    if any(g.status == "invalid" for g in group_results) or errors:
        return ReconcileResult(
            run_id=run.run_id,
            currency=run.currency,
            complete=False,
            within_tolerance=False,
            exit_code=2,
            reason_code="incomplete_or_invalid",
            groups=group_results,
            errors=errors or ["invalid group(s)"],
        )

    outside = any(g.status == "outside" for g in group_results)
    if outside:
        return ReconcileResult(
            run_id=run.run_id,
            currency=run.currency,
            complete=True,
            within_tolerance=False,
            exit_code=1,
            reason_code="outside_tolerance",
            groups=group_results,
            errors=[],
        )

    return ReconcileResult(
        run_id=run.run_id,
        currency=run.currency,
        complete=True,
        within_tolerance=True,
        exit_code=0,
        reason_code="within_tolerance",
        groups=group_results,
        errors=[],
    )


def format_human(result: ReconcileResult) -> str:
    lines: list[str] = [
        f"llg reconcile-cost — run_id={result.run_id}",
        f"currency={result.currency}  complete={result.complete}  "
        f"within_tolerance={result.within_tolerance}  reason={result.reason_code}",
        f"exit_code={result.exit_code}",
    ]
    if result.errors:
        lines.append("errors:")
        for e in result.errors:
            lines.append(f"  - {e}")
    for g in result.groups:
        lines.append("")
        lines.append(f"group={g.group_id}  scope={g.comparison_scope_id}  status={g.status}")
        if g.detail:
            lines.append(f"  detail: {g.detail}")
        for p in g.pairs:
            rel = p.relative_delta if p.relative_delta is not None else "null"
            flag = "OK" if p.within else "OUT"
            lines.append(
                f"  [{flag}] {p.left_role}↔{p.right_role}: "
                f"{p.left_amount} vs {p.right_amount}  "
                f"diff={p.difference} limit={p.limit} rel={rel}"
            )
    return "\n".join(lines) + "\n"


def format_json(result: ReconcileResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"


# --- internals ----------------------------------------------------------------


def _fmt_dt(dt: datetime) -> str:
    s = dt.isoformat()
    if s.endswith("+00:00"):
        return s[:-6] + "Z"
    return s


def _parse_decimal(value: Any, *, field_name: str) -> Decimal:
    if value is None:
        raise LoadError(f"{field_name} is required", code="invalid_amount")
    if isinstance(value, bool):
        raise LoadError(f"{field_name} must be a decimal string", code="invalid_amount")
    if isinstance(value, (int, float)):
        # Reject bare YAML floats/ints — require quoted strings for auditability.
        raise LoadError(
            f"{field_name} must be a quoted decimal string (got bare number {value!r})",
            code="invalid_amount",
        )
    if not isinstance(value, str) or not value.strip():
        raise LoadError(
            f"{field_name} must be a non-empty decimal string",
            code="invalid_amount",
        )
    try:
        d = Decimal(value.strip())
    except InvalidOperation as exc:
        raise LoadError(
            f"{field_name} is not a valid decimal: {value!r}",
            code="invalid_amount",
        ) from exc
    if not d.is_finite():
        raise LoadError(f"{field_name} must be finite", code="invalid_amount")
    if d < 0:
        raise LoadError(
            f"{field_name} must be non-negative in v1 (got {value!r})",
            code="negative_amount",
        )
    return d


def _parse_dt(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LoadError(f"{field_name} must be an ISO-8601 UTC string", code="invalid_period")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LoadError(
            f"{field_name} is not a valid ISO-8601 datetime: {value!r}",
            code="invalid_period",
        ) from exc
    if dt.tzinfo is None:
        raise LoadError(f"{field_name} must be timezone-aware UTC", code="invalid_period")
    # Normalize to UTC for exact bound equality across sources.
    return dt.astimezone(UTC)


def _parse_period(raw: Any, *, prefix: str) -> Period:
    if not isinstance(raw, dict):
        raise LoadError(f"{prefix}.period must be a mapping", code="invalid_period")
    start = _parse_dt(raw.get("start"), field_name=f"{prefix}.period.start")
    end = _parse_dt(raw.get("end"), field_name=f"{prefix}.period.end")
    if end <= start:
        raise LoadError(
            f"{prefix}.period must be half-open [start, end) with end > start",
            code="invalid_period",
        )
    return Period(start=start, end=end)


def _validate_evidence_ref(ref: Any, *, prefix: str) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise LoadError(f"{prefix}.evidence_ref is required", code="invalid_evidence")
    text = ref.strip()
    # Mutable dashboard URL alone is insufficient.
    if _DASHBOARD_ONLY.match(text) and " " not in text and "/" in text:
        # Pure URL with no path hint of a retained file — reject.
        # Allow URLs that look like retained exports (contain /exports/ or end with file ext)
        lower = text.lower()
        if not any(
            marker in lower
            for marker in (
                ".csv",
                ".json",
                ".pdf",
                ".png",
                ".jpg",
                ".md",
                "/exports/",
                "evidence/",
            )
        ):
            raise LoadError(
                f"{prefix}.evidence_ref must name a retained export/screenshot/note; "
                f"a mutable dashboard URL alone is not sufficient (got {text!r})",
                code="invalid_evidence",
            )
    return text


def _parse_source(raw: Any, *, prefix: str) -> SourceAmount:
    if not isinstance(raw, dict):
        raise LoadError(f"{prefix} must be a mapping", code="invalid_run")
    role = raw.get("source_role")
    if role not in _ALLOWED_ROLES:
        raise LoadError(
            f"{prefix}.source_role must be one of {sorted(_ALLOWED_ROLES)} (got {role!r})",
            code="invalid_source_role",
        )
    source_id = raw.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise LoadError(f"{prefix}.source_id is required", code="invalid_run")
    amount = _parse_decimal(raw.get("amount"), field_name=f"{prefix}.amount")
    period = _parse_period(raw.get("period"), prefix=prefix)
    collected_at = _parse_dt(raw.get("collected_at"), field_name=f"{prefix}.collected_at")
    evidence_ref = _validate_evidence_ref(raw.get("evidence_ref"), prefix=prefix)
    provenance = raw.get("provenance")
    if provenance not in _ALLOWED_PROVENANCE:
        raise LoadError(
            f"{prefix}.provenance must be one of {sorted(_ALLOWED_PROVENANCE)} "
            f"(got {provenance!r})",
            code="invalid_provenance",
        )
    ib = raw.get("inclusion_basis")
    if ib is not None and (not isinstance(ib, str) or not ib.strip()):
        raise LoadError(f"{prefix}.inclusion_basis must be a non-empty string when set")
    return SourceAmount(
        source_role=str(role),
        source_id=source_id.strip(),
        amount=amount,
        period=period,
        collected_at=collected_at,
        evidence_ref=evidence_ref,
        provenance=str(provenance),
        inclusion_basis=ib.strip() if isinstance(ib, str) else None,
    )


def _parse_run(raw: dict[str, Any]) -> RunDocument:
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise LoadError(
            f"schema_version must be 1 (got {schema_version!r})",
            code="unsupported_schema",
        )
    run_id = raw.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise LoadError("run_id is required", code="invalid_run")
    currency = raw.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise LoadError("currency is required (run-level)", code="invalid_currency")
    currency = currency.strip().upper()

    tol_raw = raw.get("tolerance")
    if not isinstance(tol_raw, dict):
        raise LoadError("tolerance mapping is required", code="invalid_run")
    relative = _parse_decimal(tol_raw.get("relative"), field_name="tolerance.relative")
    absolute = _parse_decimal(tol_raw.get("absolute"), field_name="tolerance.absolute")
    if relative < 0 or absolute < 0:
        raise LoadError("tolerance values must be non-negative", code="invalid_run")

    roles_raw = raw.get("required_source_roles")
    if roles_raw is None:
        required_roles = tuple(sorted(CORE_SOURCE_ROLES))
    else:
        if not isinstance(roles_raw, list) or not roles_raw:
            raise LoadError(
                "required_source_roles must be a non-empty list when present",
                code="invalid_run",
            )
        required_roles = tuple(str(r) for r in roles_raw)
        missing_core = CORE_SOURCE_ROLES - set(required_roles)
        if missing_core:
            raise LoadError(
                "required_source_roles for DoD #15 mode must include "
                f"{sorted(CORE_SOURCE_ROLES)} (missing {sorted(missing_core)})",
                code="missing_required_roles",
            )
        extras = set(required_roles) - _ALLOWED_ROLES
        if extras:
            raise LoadError(
                f"unknown required_source_roles: {sorted(extras)}",
                code="invalid_source_role",
            )

    groups_raw = raw.get("groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        raise LoadError("groups must be a non-empty list", code="invalid_run")

    groups: list[Group] = []
    for i, graw in enumerate(groups_raw):
        prefix = f"groups[{i}]"
        if not isinstance(graw, dict):
            raise LoadError(f"{prefix} must be a mapping", code="invalid_run")
        gid = graw.get("id")
        if not isinstance(gid, str) or not gid.strip():
            raise LoadError(f"{prefix}.id is required", code="invalid_run")
        scope = graw.get("comparison_scope_id")
        if not isinstance(scope, str) or not scope.strip():
            raise LoadError(f"{prefix}.comparison_scope_id is required", code="invalid_run")
        ib = graw.get("inclusion_basis")
        if not isinstance(ib, str) or not ib.strip():
            raise LoadError(f"{prefix}.inclusion_basis is required narrative", code="invalid_run")
        sources_raw = graw.get("sources")
        if not isinstance(sources_raw, list) or not sources_raw:
            raise LoadError(f"{prefix}.sources must be a non-empty list", code="invalid_run")
        sources = tuple(
            _parse_source(s, prefix=f"{prefix}.sources[{j}]") for j, s in enumerate(sources_raw)
        )
        # Custom additive only — cannot substitute for core roles.
        groups.append(
            Group(
                id=gid.strip(),
                comparison_scope_id=scope.strip(),
                inclusion_basis=ib.strip(),
                sources=sources,
            )
        )

    return RunDocument(
        schema_version=1,
        run_id=run_id.strip(),
        currency=currency,
        tolerance=Tolerance(relative=relative, absolute=absolute),
        required_source_roles=required_roles,
        groups=tuple(groups),
    )


def _role_map(group: Group) -> dict[str, SourceAmount]:
    """Map role -> source; custom roles use source_id-qualified keys for extras."""
    by_role: dict[str, SourceAmount] = {}
    for src in group.sources:
        if src.source_role in CORE_SOURCE_ROLES:
            if src.source_role in by_role:
                raise LoadError(
                    f"group {group.id!r}: duplicate source_role {src.source_role!r}",
                    code="duplicate_role",
                )
            by_role[src.source_role] = src
        # custom roles are not used for DoD pair matrix
    return by_role


def _reconcile_group(
    group: Group,
    run: RunDocument,
) -> tuple[GroupResult, str | None]:
    try:
        by_role = _role_map(group)
    except LoadError as exc:
        return (
            GroupResult(
                group_id=group.id,
                comparison_scope_id=group.comparison_scope_id,
                status="invalid",
                detail=str(exc),
            ),
            str(exc),
        )

    missing = [r for r in run.required_source_roles if r in CORE_SOURCE_ROLES and r not in by_role]
    if missing:
        msg = f"group {group.id!r}: missing required source roles {missing}"
        return (
            GroupResult(
                group_id=group.id,
                comparison_scope_id=group.comparison_scope_id,
                status="invalid",
                detail=msg,
            ),
            msg,
        )

    required_sources = [by_role[r] for r in sorted(CORE_SOURCE_ROLES)]

    # Period equality (exact bounds)
    p0 = required_sources[0].period
    for src in required_sources[1:]:
        if src.period.start != p0.start or src.period.end != p0.end:
            msg = (
                f"group {group.id!r}: period bounds must be exactly equal across "
                f"required sources ([start, end) UTC half-open)"
            )
            return (
                GroupResult(
                    group_id=group.id,
                    comparison_scope_id=group.comparison_scope_id,
                    status="invalid",
                    detail=msg,
                ),
                msg,
            )

    amounts = [s.amount for s in required_sources]
    if all(a == 0 for a in amounts):
        msg = f"group {group.id!r}: unproven_zero_cost_group"
        return (
            GroupResult(
                group_id=group.id,
                comparison_scope_id=group.comparison_scope_id,
                status="unproven_zero_cost_group",
                detail=msg,
            ),
            msg,
        )

    pairs: list[PairReport] = []
    all_within = True
    # Named pairs: provider↔litellm, litellm↔langfuse, provider↔langfuse
    named_pairs = (
        ("provider", "litellm"),
        ("litellm", "langfuse"),
        ("provider", "langfuse"),
    )
    for left, right in named_pairs:
        a = by_role[left].amount
        b = by_role[right].amount
        within, diff, limit, rel = pair_within(
            a,
            b,
            relative=run.tolerance.relative,
            absolute=run.tolerance.absolute,
        )
        if not within:
            all_within = False
        pairs.append(
            PairReport(
                left_role=left,
                right_role=right,
                left_amount=format(a, "f"),
                right_amount=format(b, "f"),
                difference=format(diff, "f"),
                limit=format(limit, "f"),
                relative_delta=format(rel, "f") if rel is not None else None,
                within=within,
            )
        )

    # Internal max-min invariant (same pass/fail under DOC′ + non-negative)
    lo, hi = min(amounts), max(amounts)
    range_within, _, _, _ = pair_within(
        lo,
        hi,
        relative=run.tolerance.relative,
        absolute=run.tolerance.absolute,
    )
    if range_within != all_within:
        # Should not happen under DOC′; surface as invalid if it does.
        msg = f"group {group.id!r}: internal range/pair invariant mismatch"
        return (
            GroupResult(
                group_id=group.id,
                comparison_scope_id=group.comparison_scope_id,
                status="invalid",
                pairs=pairs,
                detail=msg,
            ),
            msg,
        )

    return (
        GroupResult(
            group_id=group.id,
            comparison_scope_id=group.comparison_scope_id,
            status="within" if all_within else "outside",
            pairs=pairs,
        ),
        None,
    )

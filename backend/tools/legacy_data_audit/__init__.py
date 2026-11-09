"""Offline synthetic metadata proposals. No application, DB or storage imports."""

import json
import re


MAX_BYTES = 1_048_576
MAX_RECORDS = 1000
_FIELDS = {
    "id", "kind", "stored_scope", "historical_scope", "scope_evidence",
    "current_user_org", "origin", "consent", "consent_audit_bound", "inputs",
    "artifact", "share", "deleted",
}
_ENUMS = {
    "kind": {"membership", "source_check", "researcher_profile", "report", "schedule"},
    "scope_evidence": {"unknown", "creation_record"},
    "origin": {"unknown", "native", "migration_0012", "migration_0013"},
    "consent": {"unknown", "recipient_accepted"},
    "artifact": {"none", "original_pdf", "annotated_pdf", "cached_pdf", "unknown"},
    "share": {"none", "active", "expired", "revoked", "expiry_unknown"},
}


class AuditInputError(ValueError):
    """Static error text deliberately never includes input, keys or paths."""

    def __init__(self):
        super().__init__("Invalid synthetic metadata input.")


def _alias(value):
    return type(value) is str and re.fullmatch(r"syn-[1-9][0-9]{0,5}", value) is not None


def _validate(data):
    if (type(data) is not dict or set(data) != {"schema_version", "synthetic", "records"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["synthetic"] is not True or type(data["records"]) is not list
            or not 1 <= len(data["records"]) <= MAX_RECORDS):
        raise AuditInputError()
    seen = set()
    for row in data["records"]:
        if type(row) is not dict or set(row) != _FIELDS:
            raise AuditInputError()
        for field, values in _ENUMS.items():
            if type(row[field]) is not str or row[field] not in values:
                raise AuditInputError()
        if not _alias(row["id"]) or row["id"] in seen:
            raise AuditInputError()
        seen.add(row["id"])
        for field in ("stored_scope", "historical_scope", "current_user_org"):
            if row[field] is not None and not _alias(row[field]):
                raise AuditInputError()
        if any(type(row[field]) is not bool for field in ("consent_audit_bound", "deleted")):
            raise AuditInputError()
        inputs = row["inputs"]
        if (type(inputs) is not list or len(inputs) > 25
                or any(not _alias(value) for value in inputs)
                or len(set(inputs)) != len(inputs)
                or (row["kind"] != "report" and inputs)):
            raise AuditInputError()
    return data


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditInputError()
        result[key] = value
    return result


def _reject_constant(_value):
    raise AuditInputError()


def load_synthetic(text):
    """Strict bounded JSON; rejects duplicate keys and non-finite constants."""
    try:
        if type(text) is not str or len(text.encode("utf-8")) > MAX_BYTES:
            raise AuditInputError()
        return _validate(json.loads(text, object_pairs_hook=_unique_object,
                                    parse_constant=_reject_constant))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise AuditInputError() from None


def _base_reasons(row):
    reasons = set()
    if row["scope_evidence"] != "creation_record":
        reasons.add("scope_unproven")
    elif row["stored_scope"] != row["historical_scope"]:
        reasons.add("scope_conflict")
    if row["origin"] in {"migration_0012", "migration_0013"}:
        reasons.add("backfill_not_provenance")
    elif row["origin"] == "unknown":
        reasons.add("origin_unproven")
    if row["kind"] == "membership":
        if row["stored_scope"] is None:
            reasons.add("membership_scope_missing")
        if row["consent"] != "recipient_accepted" or not row["consent_audit_bound"]:
            reasons.add("consent_unproven")
    if row["kind"] == "schedule":
        reasons.add("schedule_original_scope_unproven")
    if row["deleted"]:
        reasons.add("deleted_record_hold")
    if row["artifact"] == "unknown":
        reasons.add("artifact_provenance_unproven")
    if row["share"] == "expiry_unknown":
        reasons.add("share_expiry_unproven")
    elif row["share"] == "active":
        reasons.add("active_share_authorization_review")
    return reasons


def classify(data):
    """Return review proposals, never authorization or an executable write plan."""
    _validate(data)
    rows = data["records"]
    by_id = {row["id"]: row for row in rows}
    results = []
    for index, row in enumerate(rows, 1):
        reasons = _base_reasons(row)
        if row["kind"] == "report":
            if not row["inputs"]:
                reasons.add("report_inputs_unproven")
            for alias in row["inputs"]:
                source = by_id.get(alias)
                # Only base resource inputs are allowed. Report cycles/nesting,
                # missing FKs and deleted sources must never grant clearance.
                if (source is None or source["kind"] not in {"source_check", "researcher_profile"}
                        or source["deleted"]):
                    reasons.add("input_missing_deleted_or_invalid")
                    continue
                if source["stored_scope"] != row["stored_scope"]:
                    reasons.add("input_scope_conflict")
                if _base_reasons(source):
                    reasons.add("input_provenance_unproven")
        actions = {"manual_review"}
        if reasons:
            actions.update({"quarantine_review", "explicit_mapping_review"})
            if row["kind"] == "membership":
                actions.add("recipient_reconsent_review")
        if row["kind"] == "schedule":
            actions.add("keep_scheduling_disabled")
        if row["artifact"] != "none":
            actions.add("artifact_hold_review")
        if row["share"] != "none":
            actions.add("share_disable_review")
        results.append({
            "ordinal": index,
            "classification": "quarantine_proposed" if reasons else "consistent_metadata_review_only",
            "reasons": sorted(reasons),
            "proposed_actions": sorted(actions),
        })
    return {
        "schema_version": 1,
        "mode": "synthetic_offline_proposals_only",
        "production_audit_performed": False,
        "records": results,
    }

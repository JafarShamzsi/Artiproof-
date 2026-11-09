"""Bounded stdlib metric plumbing for fictional fixtures, not fraud inference."""

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
import re
import sys

MAX_BYTES = 1_048_576
MAX_ROWS = 5_000
MAX_DEPTH = 8
VERSION = "cite-eval-v1"
POS = "confirmed_manipulation"
NEG = "confirmed_nonmanipulation"
LABELS = (POS, NEG, "other_retraction", "anomaly", "unknown")
METRICS = ("selective_accuracy", "precision", "recall", "false_positive_rate",
           "false_discovery_proportion", "precision_at_budget")
FIELDS = {"schema_version", "synthetic_only", "as_of", "model_version",
          "config_version", "label_version", "evidence_version", "labels_complete",
          "review_budget", "rows"}
TOKEN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}\Z")
FICTIONAL_ID = re.compile(r"fictional-[a-z0-9-]{1,54}\Z")


def _object(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError("object has missing or unsupported fields")


def _validate(document):
    _object(document, FIELDS)
    if document["schema_version"] != VERSION or document["synthetic_only"] is not True:
        raise ValueError("only cite-eval-v1 synthetic fixtures are supported")
    if type(document["labels_complete"]) is not bool:
        raise ValueError("labels_complete must be boolean")
    budget = document["review_budget"]
    if type(budget) is not int or not 1 <= budget <= MAX_ROWS:
        raise ValueError("review_budget must be an integer in [1, 5000]")
    for key in ("model_version", "config_version", "label_version", "evidence_version"):
        value = document[key]
        if type(value) is not str or not TOKEN.fullmatch(value):
            raise ValueError("version identifiers must be bounded ASCII tokens")
    as_of = document["as_of"]
    if type(as_of) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError("as_of must be an ISO calendar date")
    date.fromisoformat(as_of)
    rows = document["rows"]
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError("rows must be a list of at most 5000 fictional cases")
    seen = set()
    for row in rows:
        _object(row, {"id", "label", "score", "decision"})
        identifier = row["id"]
        if type(identifier) is not str or not FICTIONAL_ID.fullmatch(identifier):
            raise ValueError("case IDs must be bounded fictional- identifiers")
        if identifier in seen:
            raise ValueError("duplicate fictional case ID")
        seen.add(identifier)
        if type(row["label"]) is not str or row["label"] not in LABELS:
            raise ValueError("unsupported case label")
        if document["labels_complete"] and row["label"] not in (POS, NEG):
            raise ValueError("complete labels cannot include unknown binary outcomes")
        decision = row["decision"]
        if type(decision) is not str or decision not in ("review", "dismiss", "abstain"):
            raise ValueError("decision must be review, dismiss or abstain")
        score = row["score"]
        if decision == "abstain":
            if score is not None:
                raise ValueError("abstention requires null score")
        elif type(score) not in (int, float) or not 0 <= score <= 1 or not math.isfinite(score):
            raise ValueError("decided cases require a finite score in [0, 1]")


def _ratio(numerator, denominator, reason=None):
    if reason or denominator == 0:
        return {"value": None, "numerator": numerator, "denominator": denominator,
                "unavailable_reason": reason or "zero_denominator", "wilson95_iid": None}
    p = numerator / denominator
    z = 1.959963984540054
    z2 = z * z
    scale = 1 + z2 / denominator
    center = (p + z2 / (2 * denominator)) / scale
    half = z * math.sqrt(p * (1 - p) / denominator + z2 / (4 * denominator**2)) / scale
    return {"value": p, "numerator": numerator, "denominator": denominator,
            "unavailable_reason": None,
            "wilson95_iid": [0.0 if numerator == 0 else max(0.0, center - half),
                             1.0 if numerator == denominator else min(1.0, center + half)]}


def evaluate(document):
    """Validate before counting; unknown outcomes are never negative outcomes.

    Complete-cohort recall includes known positive abstentions as missed capture.
    P@B is descriptive queue yield only, requiring B selected binary-known cases.
    """
    _validate(document)
    rows = document["rows"]
    canonical = dict(document, rows=sorted(rows, key=lambda r: r["id"]))
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("canonical input exceeds byte bound")
    counts = dict(tp=0, fp=0, tn=0, fn=0)
    labels = Counter(r["label"] for r in rows)
    decisions = Counter(r["decision"] for r in rows)
    abstained_labels = Counter(r["label"] for r in rows if r["decision"] == "abstain")
    for row in rows:
        if row["decision"] == "abstain" or row["label"] not in (POS, NEG):
            continue
        predicted = row["decision"] == "review"
        actual = row["label"] == POS
        key = ("tp" if actual else "fp") if predicted else ("fn" if actual else "tn")
        counts[key] += 1
    tp, fp, tn, fn = (counts[k] for k in ("tp", "fp", "tn", "fn"))
    decided = decisions["review"] + decisions["dismiss"]
    reason = None if document["labels_complete"] else "labels_incomplete"
    metrics = {
        "selective_accuracy": _ratio(tp + tn, decided, reason),
        "precision": _ratio(tp, tp + fp, reason),
        "recall": _ratio(tp, labels[POS], reason),
        # FPR uses all known negatives, including negative abstentions.
        "false_positive_rate": _ratio(fp, labels[NEG], reason),
        "false_discovery_proportion": _ratio(fp, tp + fp, reason),
    }
    budget = document["review_budget"]
    candidates = sorted((r for r in rows if r["decision"] == "review"),
                        key=lambda r: (-r["score"], r["id"]))
    selected = candidates[:budget]
    unknown_selected = sum(r["label"] not in (POS, NEG) for r in selected)
    queue_reason = ("budget_unfilled" if len(selected) < budget else
                    "selected_labels_unknown" if unknown_selected else None)
    metrics["precision_at_budget"] = _ratio(sum(r["label"] == POS for r in selected), budget, queue_reason)
    return {
        "schema_version": VERSION, "purpose": "synthetic_metric_plumbing_only",
        "input_sha256": hashlib.sha256(encoded).hexdigest(),
        "versions": {k: document[k] for k in ("as_of", "model_version", "config_version",
                                              "label_version", "evidence_version")},
        "labels_complete": document["labels_complete"],
        "coverage": {"total": len(rows), "decided": decided, "abstained": decisions["abstain"],
                     "abstained_positive": abstained_labels[POS],
                     "abstained_negative": abstained_labels[NEG],
                     "abstained_unknown": sum(abstained_labels[k] for k in LABELS if k not in (POS, NEG)),
                     "decision_fraction": decided / len(rows) if rows else None,
                     "binary_known": labels[POS] + labels[NEG],
                     "label_counts": {key: labels[key] for key in LABELS}},
        "known_decided_confusion": counts,
        "review": {"budget": budget, "candidate_count": len(candidates), "selected_count": len(selected),
                   "selected_ids": [r["id"] for r in selected], "unknown_selected": unknown_selected,
                   "unfilled_slots": budget - len(selected), "deferred_candidates": len(candidates) - len(selected)},
        "metrics": metrics,
        "limits": ["Fictional inputs only; no scientific accuracy or misconduct inference.",
                   "Known-decided counts are descriptive, not complete-population confusion.",
                   "Wilson intervals assume independent binomial cases; not network-valid uncertainty.",
                   "Versions and labels_complete are supplied assertions, not audited provenance."],
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("nonfinite JSON number")


def parse_input(raw):
    """Bound byte count and nesting before recursive JSON decoding."""
    if len(raw) > MAX_BYTES:
        raise ValueError("input exceeds 1048576 bytes")
    text = raw.decode("utf-8")
    depth = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("input nesting exceeds 8")
        elif char in "]}":
            depth -= 1
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-metric", choices=METRICS, action="append", default=[],
                        help="exit 2 instead of emitting a report if this metric is unavailable")
    args = parser.parse_args(argv)
    try:
        document = parse_input(sys.stdin.buffer.read(MAX_BYTES + 1))
        result = evaluate(document)
        for name in args.require_metric:
            if result["metrics"][name]["value"] is None:
                raise ValueError("required metric unavailable: " + name)
        output = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(output.encode("utf-8")) > MAX_BYTES:
            raise ValueError("output exceeds byte bound")
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        # Never echo untrusted input or JSON decoder snippets into errors.
        error = "invalid synthetic input or required metric unavailable"
        print(json.dumps({"error": error}), file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

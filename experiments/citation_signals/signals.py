"""Bounded, offline, stdlib-only observable graph features. No adjudication."""

import argparse
import calendar
from collections import defaultdict
from datetime import date
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sys

VERSION = "citation-signals/1"
MAX_BYTES = 1024 * 1024
MAX_MOTIFS = 128
TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z", re.ASCII)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected):
    require(type(value) is dict and set(value) == set(expected.split()),
            "object fields must be exactly: " + expected)


def token(value):
    require(type(value) is str and TOKEN.fullmatch(value) is not None, "invalid opaque ID")
    return value


def items(value, limit):
    require(type(value) is list and len(value) <= limit, "array bound/type invalid")
    return value


def day(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value),
            "expected YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    require(1900 <= parsed.year <= 2100, "dates must be in 1900..2100")
    return parsed


def interval(value):
    fields(value, "precision value")
    precision, text = value["precision"], value["value"]
    require(type(precision) is str, "invalid date precision")
    if precision == "unknown":
        require(text is None, "unknown date must be null")
        return None
    if precision == "day":
        return day(text), day(text)
    require(type(text) is str, "invalid publication date")
    if precision == "month":
        require(re.fullmatch(r"[0-9]{4}-[0-9]{2}", text), "expected YYYY-MM")
        first = day(text + "-01")
        return first, date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    require(precision == "year" and re.fullmatch(r"[0-9]{4}", text), "invalid precision/date")
    return day(text + "-01-01"), day(text + "-12-31")


def canonical(value):
    """All contract arrays are unordered assertion sets, not sequences."""
    if type(value) is dict:
        return {key: canonical(val) for key, val in sorted(value.items())}
    if type(value) is list:
        return sorted((canonical(val) for val in value), key=encoded)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def loads(raw):
    """Strict bounded JSON, including key and lexical nesting checks."""
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, "input exceeds 1 MiB or is not bytes")
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            require(depth <= 12, "JSON nesting exceeds 12")
        elif char in (93, 125):
            depth -= 1

    def pairs(entries):
        obj = {}
        for key, value in entries:
            require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj

    def invalid_constant(_):
        raise ValueError("nonfinite JSON number")

    def invalid_float(_):
        raise ValueError("fixture contract permits integer numbers only")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=invalid_constant, parse_float=invalid_float)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding/nesting") from exc


def validate(data):
    fields(data, "version window authors works runs references")
    require(type(data["version"]) is int and data["version"] == 1, "unsupported fixture version")
    window = data["window"]
    fields(window, "start end as_of")
    start, end, as_of = (day(window[key]) for key in ("start", "end", "as_of"))
    require(start < end <= as_of and (end - start).days <= 3660, "invalid/boundless window")
    authors, works, runs, refs = {}, {}, {}, {}
    identifiers = defaultdict(list)
    for author in items(data["authors"], 64):
        fields(author, "id status resolution_version identifiers")
        aid = token(author["id"])
        require(aid not in authors, "duplicate author ID")
        require(author["status"] in ("resolved", "ambiguous", "unknown"), "invalid identity status")
        token(author["resolution_version"])
        aliases = [token(alias) for alias in items(author["identifiers"], 8)]
        require(len(set(aliases)) == len(aliases), "duplicate identifier")
        for alias in aliases:
            identifiers[alias].append(aid)
        authors[aid] = author
    for group in identifiers.values():
        require(len(group) == 1 or all(authors[aid]["status"] != "resolved" for aid in group),
                "resolved identifier collision; mark all affected identities ambiguous")
    dates = {}
    assertion_ids = set()
    for work in items(data["works"], 128):
        fields(work, "id kind published authorships")
        wid = token(work["id"])
        require(wid not in works, "duplicate work ID")
        require(work["kind"] in ("research", "review"), "invalid work kind")
        dates[wid] = interval(work["published"])
        require(dates[wid] is None or dates[wid][0] <= as_of, "certainly future publication")
        seen = set()
        for assertion in items(work["authorships"], 8):
            fields(assertion, "author_id assertion_id resolution_version")
            aid = token(assertion["author_id"])
            require(aid in authors and aid not in seen, "dangling/duplicate authorship")
            sid = token(assertion["assertion_id"])
            require(sid not in assertion_ids, "duplicate authorship assertion ID")
            assertion_ids.add(sid)
            require(assertion["resolution_version"] == authors[aid]["resolution_version"],
                    "authorship identity version mismatch")
            seen.add(aid)
        works[wid] = work
    for run in items(data["runs"], 32):
        fields(run, "id provider lineage as_of direction truncated work_limit reference_limit")
        rid = token(run["id"])
        require(rid not in runs, "duplicate run ID")
        token(run["provider"])
        token(run["lineage"])
        require(day(run["as_of"]) <= as_of, "future collection run")
        require(run["direction"] in ("incoming", "outgoing", "both"), "invalid collection direction")
        require(type(run["truncated"]) is bool, "truncated must be boolean")
        for key, maximum in (("work_limit", 128), ("reference_limit", 512)):
            require(type(run[key]) is int and 1 <= run[key] <= maximum, "invalid collection limit")
        runs[rid] = run
    source_ids = {}
    per_run_works, per_run_refs = defaultdict(set), defaultdict(set)
    for ref in items(data["references"], 512):
        fields(ref, "id citing cited run source_evidence_id observed_on")
        eid = token(ref["id"])
        source_id = token(ref["source_evidence_id"])
        citing, cited, rid = (token(ref[key]) for key in ("citing", "cited", "run"))
        require(citing in works and cited in works and rid in runs, "dangling reference")
        require(citing != cited, "self-work reference invalid")
        observed = day(ref["observed_on"])
        require(observed <= day(runs[rid]["as_of"]), "future observation relative to run")
        for wid in (citing, cited):
            require(dates[wid] is None or dates[wid][0] <= observed,
                    "observation certainly predates publication")
        if dates[citing] and dates[cited]:
            require(dates[cited][0] <= dates[citing][1], "certainly impossible citation chronology")
        require(eid not in refs or refs[eid] == ref, "conflicting reference assertion ID")
        source_key = rid, source_id
        require(source_key not in source_ids or source_ids[source_key] == (citing, cited),
                "source evidence reused for different work pair")
        source_ids[source_key] = citing, cited
        refs[eid] = ref
        per_run_works[rid].update((citing, cited))
        per_run_refs[rid].add(source_id)
    for rid, run in runs.items():
        require(len(per_run_works[rid]) <= run["work_limit"] and
                len(per_run_refs[rid]) <= run["reference_limit"], "collection limits contradicted")
    normalized = dict(data, references=list(refs.values()))
    return normalized, authors, works, runs, dates, start, end, as_of


def analyze(data):
    data, authors, works, runs, dates, start, end, as_of = validate(data)
    groups = defaultdict(list)
    for ref in data["references"]:
        groups[ref["citing"], ref["cited"]].append(ref)
    resolved = {
        wid: sorted(a["author_id"] for a in work["authorships"])
        for wid, work in works.items()
        if work["authorships"] and all(authors[a["author_id"]]["status"] == "resolved"
                                      for a in work["authorships"])
    }
    coauthored = defaultdict(list)
    for wid, aids in resolved.items():
        if dates[wid] and dates[wid][1] <= as_of:
            for pair in combinations(aids, 2):
                coauthored[pair].append(wid)

    mass, supports = defaultdict(Fraction), defaultdict(set)
    self_mass = coauthor_mass = Fraction(0)
    self_support, coauthor_support, overlap_support = set(), set(), set()
    coauthor_inventory_support = set()
    evidence, abstentions, outside = [], [], []
    eligible = 0
    for (citing, cited), assertions in sorted(groups.items()):
        src_date, dst_date = dates[citing], dates[cited]
        reason = None
        if not src_date or not dst_date:
            reason = "date_unknown"
        elif src_date[1] < start or src_date[0] >= end:
            reason = "outside_window"
        elif src_date[0] < start or src_date[1] >= end:
            reason = "window_ambiguous"
        elif src_date[1] > as_of or dst_date[1] > src_date[0]:
            reason = "chronology_ambiguous"
        elif not any(day(ref["observed_on"]) >= max(src_date[1], dst_date[1])
                     for ref in assertions):
            reason = "observation_ambiguous"
        elif citing not in resolved or cited not in resolved:
            reason = "identity_unknown_or_ambiguous"
        record = {"work_pair": [citing, cited], "eligible": reason is None,
                  "reason": reason, "assertions": canonical(assertions),
                  "projection_supporting_assertion_ids": sorted(
                      ref["id"] for ref in assertions
                      if reason is None and day(ref["observed_on"]) >= max(src_date[1], dst_date[1])),
                  "lineages": sorted({runs[ref["run"]]["lineage"] for ref in assertions})}
        evidence.append(record)
        work_pair = (citing, cited)
        if reason:
            entry = {"work_pair": list(work_pair), "reason": reason}
            (outside if reason == "outside_window" else abstentions).append(entry)
            continue
        eligible += 1
        source, target = resolved[citing], resolved[cited]
        if set(source) & set(target):
            overlap_support.add(work_pair)
        weight = Fraction(1, len(source) * len(target))
        for a in source:
            for b in target:
                mass[a, b] += weight
                supports[a, b].add(work_pair)
                if a == b:
                    self_mass += weight
                    self_support.add(work_pair)
                else:
                    prior = [wid for wid in coauthored[tuple(sorted((a, b)))]
                             if dates[wid][1] <= src_date[0]]
                    if prior:
                        coauthor_mass += weight
                        coauthor_support.add(work_pair)
                        coauthor_inventory_support.update(prior)

    def work_paths(paths):
        return [list(pair) for pair in sorted(paths)]

    def distinct_witnesses(edges):
        # Small bipartite matching: <=3 author arcs, <=512 work-pair options.
        # Prevent a single multi-author paper edge from fabricating a cycle.
        matched = {}

        def assign(index, visited):
            for pair in sorted(supports.get(edges[index], ())):
                if pair not in visited:
                    visited.add(pair)
                    if pair not in matched or assign(matched[pair], visited):
                        matched[pair] = index
                        return True
            return False

        if not all(assign(index, set()) for index in range(len(edges))):
            return None
        by_index = {index: pair for pair, index in matched.items()}
        return [list(by_index[index]) for index in range(len(edges))]

    arcs = [{"authors": [a, b], "mass": str(value), "work_pairs": work_paths(supports[a, b])}
            for (a, b), value in sorted(mass.items())]
    two_way = []
    for a, b in combinations(sorted(authors), 2):
        witnesses = distinct_witnesses(((a, b), (b, a)))
        if witnesses:
            two_way.append({"authors": [a, b], "forward_mass": str(mass[a, b]),
                            "reverse_mass": str(mass[b, a]),
                            "two_way_mass": str(mass[a, b] + mass[b, a]),
                            "balanced_mass": str(2 * min(mass[a, b], mass[b, a])),
                            "work_pairs": work_paths(supports[a, b] | supports[b, a]),
                            "distinct_work_pair_witnesses": witnesses})
    cycles = []
    motifs_truncated = False
    for a, b, c in combinations(sorted(authors), 3):
        for path in ((a, b, c), (a, c, b)):
            edges = list(zip(path, path[1:] + path[:1]))
            if all(mass.get(edge, 0) for edge in edges):
                witnesses = distinct_witnesses(edges)
                if not witnesses:
                    continue
                if len(cycles) == MAX_MOTIFS:
                    motifs_truncated = True
                    break
                cycles.append({"authors": list(path), "evidence_author_arcs": [list(e) for e in edges],
                               "distinct_work_pair_witnesses": witnesses})
        if motifs_truncated:
            break
    concentration = []
    for author in sorted(authors):
        outgoing = {b: value for (a, b), value in mass.items() if a == author}
        denominator = sum(outgoing.values(), Fraction(0))
        if denominator:
            concentration.append({
                "author": author, "observed_outgoing_mass": str(denominator),
                "recipients": [{"author": b, "mass": str(value),
                                "share": str(value / denominator),
                                "work_pairs": work_paths(supports[author, b])}
                               for b, value in sorted(outgoing.items())]})
    features = {
        "author_edges": arcs,
        "self_citation": {"mass": str(self_mass), "denominator_work_pairs": eligible,
                          "share": str(self_mass / eligible) if eligible else None,
                          "work_pairs": work_paths(self_support)},
        "coauthor_citation": {"nonself_mass": str(coauthor_mass),
                              "denominator_work_pairs": eligible,
                              "work_pairs": work_paths(coauthor_support),
                              "coauthored_work_support": sorted(coauthor_inventory_support)},
        "shared_author_overlap": {"work_pair_count": len(overlap_support),
                                 "denominator_work_pairs": eligible,
                                 "work_pairs": work_paths(overlap_support)},
        "reciprocity": {"status": "signal_observed" if two_way else "insufficient_evidence",
                        "pairs": two_way, "absence_established": None},
        "motifs": {"status": "signal_observed" if cycles else "insufficient_evidence",
                   "directed_three_author_cycles": cycles, "enumeration_truncated": motifs_truncated,
                   "absence_established": None, "group_closure": "unavailable"},
        "concentration": concentration,
        "temporal_burst": {"status": "unavailable", "reason": "no_time_series_or_cohort_baseline"},
    }
    return {
        "experiment_version": VERSION, "fixture_version": 1,
        "input_sha256": digest(canonical(data)), "features_sha256": digest(features),
        "window": data["window"], "projection": "fractional_1_over_source_authors_times_target_authors",
        "fraud_verdict": "not_assessed",
        "candidate_annotation": "signal_observed" if eligible else "insufficient_evidence",
        "counts": {"observed_work_pairs": len(groups), "eligible_work_pairs": eligible,
                   "reference_assertions": len(data["references"]),
                   "abstained_work_pairs": len(abstentions), "outside_window_work_pairs": len(outside)},
        "coverage": {"runs": canonical(data["runs"]),
                     "population_denominator": None, "absence_established": None,
                     "limitation": "Observed sample only; limits and direction do not establish population completeness."},
        "identity_assertions": canonical(data["authors"]),
        "work_assertions": canonical(data["works"]),
        "paper_evidence": evidence, "abstentions": abstentions, "outside_window": outside,
        **features,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="synthetic v1 JSON fixture")
    args = parser.parse_args(argv)
    try:
        with args.fixture.open("rb") as handle:
            data = loads(handle.read(MAX_BYTES + 1))
        result = analyze(data)
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print("Invalid fixture: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

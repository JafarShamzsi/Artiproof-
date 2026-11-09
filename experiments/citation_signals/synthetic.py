"""Fixed fictional controls and replay artifacts, entirely offline."""

import argparse
import copy
import json
from pathlib import Path

import signals


ROOT = Path(__file__).resolve().parent


def graph(author_ids, work_specs, references):
    """Specs: (work ID, author IDs, day); references: (citing ID, cited ID)."""
    return {
        "version": 1,
        "window": {"start": "2020-01-01", "end": "2024-01-01", "as_of": "2024-02-01"},
        "authors": [{"id": aid, "status": "resolved", "resolution_version": "v1",
                     "identifiers": ["fictional:" + aid]} for aid in author_ids],
        "works": [{"id": wid, "kind": "research",
                   "published": {"precision": "day", "value": published},
                   "authorships": [{"author_id": aid, "assertion_id": "au:" + wid + ":" + aid,
                                    "resolution_version": "v1"} for aid in aids]}
                  for wid, aids, published in work_specs],
        "runs": [{"id": "run1", "provider": "fictional-provider", "lineage": "fictional-upstream",
                  "as_of": "2024-02-01", "direction": "both", "truncated": False,
                  "work_limit": 128, "reference_limit": 512}],
        "references": [{"id": "e" + str(i), "citing": citing, "cited": cited, "run": "run1",
                        "source_evidence_id": "source:" + str(i), "observed_on": "2024-01-01"}
                       for i, (citing, cited) in enumerate(references)],
    }


def cases():
    reciprocal = graph("AB", [("a0", "A", "2020-01-01"), ("b0", "B", "2020-02-01"),
                              ("a1", "A", "2022-01-01"), ("b1", "B", "2023-01-01")],
                       [("a1", "b0"), ("b1", "a0")])
    result = {"reciprocal_authors": reciprocal}
    result["legitimate_high_self_citation"] = graph(
        "A", [("a0", "A", "2020-01-01")] +
        [("a" + str(i), "A", f"202{i}-01-01") for i in range(1, 4)],
        [("a" + str(i), "a0") for i in range(1, 4)])
    result["legitimate_coauthor_team"] = graph(
        "AB", [("team0", "AB", "2020-01-01"), ("team1", "AB", "2022-01-01")],
        [("team1", "team0")])
    result["legitimate_small_field"] = graph(
        "ABC", [(aid + "0", aid, "2020-01-01") for aid in "ABC"] +
        [(aid + "1", aid, "2022-01-01") for aid in "ABC"],
        [("A1", "B0"), ("B1", "C0"), ("C1", "A0")])
    # The graph is intentionally identical: graph features cannot determine intent.
    result["artificial_directed_cycle"] = copy.deepcopy(result["legitimate_small_field"])
    donor = copy.deepcopy(reciprocal)
    donor["references"] = donor["references"][:1]
    result["asymmetric_donor_recipient"] = donor
    incoming = copy.deepcopy(donor)
    incoming["runs"][0].update(direction="incoming", truncated=True)
    result["incomplete_incoming_only"] = incoming
    mirrored = copy.deepcopy(reciprocal)
    mirrored["runs"].append(dict(mirrored["runs"][0], id="run2", provider="fictional-mirror"))
    mirrored["references"].append(dict(mirrored["references"][0], id="e-mirror", run="run2"))
    result["duplicate_provider_mirror"] = mirrored
    for name in ("identity_split_ambiguity", "identity_collision_ambiguity"):
        ambiguous = copy.deepcopy(reciprocal)
        for author in ambiguous["authors"]:
            author["status"] = "ambiguous"
            author["resolution_version"] = "pending-split-v2"
        for work in ambiguous["works"]:
            for assertion in work["authorships"]:
                assertion["resolution_version"] = "pending-split-v2"
        if name == "identity_collision_ambiguity":
            ambiguous["authors"][1]["identifiers"] = ambiguous["authors"][0]["identifiers"][:]
        result[name] = ambiguous
    review = graph("RABCDEFGH", [(aid + "0", aid, "2020-01-01") for aid in "ABCDEFGH"] +
                   [("review", "R", "2023-01-01")], [("review", aid + "0") for aid in "ABCDEFGH"])
    review["works"][-1]["kind"] = "review"
    result["legitimate_review_high_degree"] = review
    missing = copy.deepcopy(reciprocal)
    missing["works"][2]["published"] = {"precision": "unknown", "value": None}
    result["missing_dates"] = missing
    boundary = copy.deepcopy(reciprocal)
    boundary["window"]["start"] = "2022-01-01"
    boundary["window"]["end"] = "2023-01-01"
    result["window_boundaries"] = boundary
    coarse = copy.deepcopy(boundary)
    coarse["window"]["start"] = "2022-06-01"
    coarse["works"][2]["published"] = {"precision": "year", "value": "2022"}
    result["ambiguous_year_boundary"] = coarse
    future = copy.deepcopy(reciprocal)
    future["references"][0]["observed_on"] = "2025-01-01"
    result["invalid_future_observation"] = future
    collision = copy.deepcopy(reciprocal)
    collision["authors"][1]["identifiers"] = collision["authors"][0]["identifiers"][:]
    result["invalid_resolved_collision"] = collision
    return result


def artifacts():
    output = {}
    for name, data in sorted(cases().items()):
        output["fixtures/" + name + ".json"] = data
        try:
            analyzed = signals.analyze(data)
        except ValueError as exc:
            analyzed = {"expected_exit_code": 2, "error": str(exc)}
        output["outputs/" + name + ".json"] = analyzed
    return {name: json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"
            for name, data in output.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed replay, do not write")
    args = parser.parse_args()
    mismatches = []
    for name, expected in artifacts().items():
        path = ROOT / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                mismatches.append(name)
        else:
            path.parent.mkdir(exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    if mismatches:
        print("Replay mismatches: " + ", ".join(mismatches))
        return 1
    print("Verified" if args.check else "Wrote", len(artifacts()), "deterministic synthetic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

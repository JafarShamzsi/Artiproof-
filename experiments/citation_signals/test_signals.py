"""Synthetic plumbing tests, not scientific detector validation."""

import copy
import json
from fractions import Fraction
import random
import subprocess
import sys
import unittest

import signals
import synthetic


def fixture():
    def work(wid, aid, day):
        return {"id": wid, "kind": "research",
                "published": {"precision": "day", "value": day},
                "authorships": [{"author_id": aid, "assertion_id": "au:" + wid,
                                 "resolution_version": "v1"}]}

    return {
        "version": 1,
        "window": {"start": "2020-01-01", "end": "2024-01-01", "as_of": "2024-02-01"},
        "authors": [{"id": a, "status": "resolved", "resolution_version": "v1",
                     "identifiers": ["synthetic:" + a]} for a in ("A", "B")],
        "works": [work("a0", "A", "2020-01-01"), work("b0", "B", "2020-02-01"),
                  work("a1", "A", "2022-01-01"), work("b1", "B", "2023-01-01")],
        "runs": [{"id": "r1", "provider": "fictional", "lineage": "upstream1",
                  "as_of": "2024-02-01", "direction": "both", "truncated": False,
                  "work_limit": 128, "reference_limit": 512}],
        "references": [{"id": "e1", "citing": "a1", "cited": "b0", "run": "r1",
                        "source_evidence_id": "s1", "observed_on": "2024-01-01"},
                       {"id": "e2", "citing": "b1", "cited": "a0", "run": "r1",
                        "source_evidence_id": "s2", "observed_on": "2024-01-01"}],
    }


class SignalsTests(unittest.TestCase):
    def test_single_team_edge_is_not_reciprocal_author_activity(self):
        data = fixture()
        data["references"] = data["references"][:1]
        for index in (1, 2):
            work = data["works"][index]
            work["authorships"] = [
                {"author_id": aid, "assertion_id": "au:" + work["id"] + aid,
                 "resolution_version": "v1"} for aid in ("A", "B")]
        out = signals.analyze(data)
        self.assertEqual(out["reciprocity"]["pairs"], [])
        self.assertEqual(out["self_citation"]["mass"], "1/2")
        self.assertEqual(out["coauthor_citation"]["nonself_mass"], "1/2")
        self.assertEqual(out["shared_author_overlap"]["work_pair_count"], 1)
        self.assertEqual(sum(Fraction(e["mass"]) for e in out["author_edges"]), 1)

    def test_single_consortium_edge_is_not_three_paper_motif(self):
        data = fixture()
        data["authors"].append(dict(data["authors"][0], id="C", identifiers=["synthetic:C"]))
        data["references"] = data["references"][:1]
        for index in (1, 2):
            work = data["works"][index]
            work["authorships"] = [
                {"author_id": aid, "assertion_id": "au:" + work["id"] + aid,
                 "resolution_version": "v1"} for aid in ("A", "B", "C")]
        out = signals.analyze(data)
        self.assertEqual(out["motifs"]["directed_three_author_cycles"], [])

    def test_directed_paper_evidence_precedes_author_reciprocity(self):
        out = signals.analyze(fixture())
        self.assertEqual(out["counts"]["observed_work_pairs"], 2)
        self.assertEqual(out["reciprocity"]["pairs"][0]["authors"], ["A", "B"])
        self.assertEqual(out["reciprocity"]["pairs"][0]["two_way_mass"], "2")
        self.assertEqual(out["fraud_verdict"], "not_assessed")

    def test_provider_mirror_does_not_add_mass(self):
        data = fixture()
        original = signals.analyze(data)
        run = dict(data["runs"][0], id="r2", provider="mirror")
        data["runs"].append(run)
        data["references"].append(dict(data["references"][0], id="e3", run="r2"))
        out = signals.analyze(data)
        self.assertEqual(out["counts"]["observed_work_pairs"], 2)
        self.assertEqual(out["features_sha256"], original["features_sha256"])
        self.assertEqual(len(out["paper_evidence"][0]["assertions"]), 2)

    def test_coarse_boundary_abstains(self):
        data = fixture()
        data["window"]["start"] = "2022-06-01"
        data["works"][2]["published"] = {"precision": "year", "value": "2022"}
        out = signals.analyze(data)
        self.assertEqual(out["abstentions"][0]["reason"], "window_ambiguous")
        self.assertEqual(out["counts"]["eligible_work_pairs"], 1)

    def test_future_observation_rejected(self):
        data = fixture()
        data["references"][0]["observed_on"] = "2025-01-01"
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_input_unknown_fields_rejected(self):
        data = fixture()
        data["provider_count"] = 10000
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_missing_dates_preserves_raw_edge_but_abstains(self):
        data = fixture()
        data["works"][2]["published"] = {"precision": "unknown", "value": None}
        out = signals.analyze(data)
        self.assertEqual(out["counts"]["observed_work_pairs"], 2)
        self.assertEqual(out["counts"]["eligible_work_pairs"], 1)
        self.assertEqual(out["abstentions"][0]["reason"], "date_unknown")

    def test_incoming_only_cannot_establish_absence(self):
        data = fixture()
        data["references"] = data["references"][:1]
        data["runs"][0].update(direction="incoming", truncated=True)
        out = signals.analyze(data)
        self.assertEqual(out["reciprocity"]["status"], "insufficient_evidence")
        self.assertIsNone(out["motifs"]["absence_established"])
        self.assertEqual(out["temporal_burst"]["status"], "unavailable")

    def test_resolved_identifier_collision_rejected(self):
        data = fixture()
        data["authors"][1]["identifiers"] = data["authors"][0]["identifiers"][:]
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_permutation_and_exact_duplicate_invariance(self):
        data = fixture()
        original = signals.analyze(data)
        for key in ("authors", "works", "runs", "references"):
            data[key].reverse()
        data["references"].append(copy.deepcopy(data["references"][0]))
        self.assertEqual(signals.analyze(data), original)

    def test_many_seeded_permutations_preserve_exact_output(self):
        original = fixture()
        expected = signals.analyze(original)
        rng = random.Random(5802)
        for _ in range(30):
            data = copy.deepcopy(original)
            for key in ("authors", "works", "runs", "references"):
                rng.shuffle(data[key])
            for work in data["works"]:
                rng.shuffle(work["authorships"])
            self.assertEqual(signals.analyze(data), expected)

    def test_changed_edge_changes_both_digests(self):
        data = fixture()
        original = signals.analyze(data)
        data["references"].pop()
        changed = signals.analyze(data)
        self.assertNotEqual(changed["input_sha256"], original["input_sha256"])
        self.assertNotEqual(changed["features_sha256"], original["features_sha256"])

    def test_mirrored_provenance_changes_input_digest_only(self):
        fixtures = synthetic.cases()
        original = signals.analyze(fixtures["reciprocal_authors"])
        mirrored = signals.analyze(fixtures["duplicate_provider_mirror"])
        self.assertNotEqual(original["input_sha256"], mirrored["input_sha256"])
        self.assertEqual(original["features_sha256"], mirrored["features_sha256"])
        self.assertEqual(mirrored["paper_evidence"][0]["lineages"], ["fictional-upstream"])

    def test_high_self_control_has_no_fraud_verdict(self):
        out = signals.analyze(synthetic.cases()["legitimate_high_self_citation"])
        self.assertEqual(out["self_citation"]["mass"], "3")
        self.assertEqual(out["self_citation"]["share"], "1")
        self.assertEqual(out["coauthor_citation"]["nonself_mass"], "0")
        self.assertEqual(out["fraud_verdict"], "not_assessed")

    def test_legitimate_and_artificial_cycle_are_indistinguishable(self):
        cases = synthetic.cases()
        legitimate = signals.analyze(cases["legitimate_small_field"])
        artificial = signals.analyze(cases["artificial_directed_cycle"])
        self.assertEqual(legitimate, artificial)
        cycles = legitimate["motifs"]["directed_three_author_cycles"]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0]["authors"], ["A", "B", "C"])
        self.assertEqual(len({tuple(p) for p in cycles[0]["distinct_work_pair_witnesses"]}), 3)

    def test_missing_one_cycle_edge_does_not_fabricate_motif(self):
        data = synthetic.cases()["artificial_directed_cycle"]
        data["references"].pop()
        out = signals.analyze(data)
        self.assertEqual(out["motifs"]["directed_three_author_cycles"], [])
        self.assertIsNone(out["motifs"]["absence_established"])

    def test_donor_is_asymmetric_not_reciprocal(self):
        out = signals.analyze(synthetic.cases()["asymmetric_donor_recipient"])
        self.assertEqual(out["reciprocity"]["pairs"], [])
        self.assertEqual(out["author_edges"], [{"authors": ["A", "B"], "mass": "1",
                                                "work_pairs": [["a1", "b0"]]}])

    def test_review_degree_and_concentration_are_not_burst(self):
        out = signals.analyze(synthetic.cases()["legitimate_review_high_degree"])
        self.assertEqual(out["counts"]["eligible_work_pairs"], 8)
        self.assertEqual(out["concentration"][0]["observed_outgoing_mass"], "8")
        self.assertEqual(len(out["concentration"][0]["recipients"]), 8)
        self.assertTrue(all(row["share"] == "1/8" for row in out["concentration"][0]["recipients"]))
        self.assertEqual(out["temporal_burst"]["status"], "unavailable")

    def test_split_and_collision_abstain_without_erasing_papers(self):
        for name in ("identity_split_ambiguity", "identity_collision_ambiguity"):
            with self.subTest(name=name):
                out = signals.analyze(synthetic.cases()[name])
                self.assertEqual(out["counts"]["observed_work_pairs"], 2)
                self.assertEqual(out["counts"]["eligible_work_pairs"], 0)
                self.assertEqual(out["candidate_annotation"], "insufficient_evidence")
                self.assertIsNone(out["self_citation"]["share"])

    def test_start_included_end_excluded(self):
        out = signals.analyze(synthetic.cases()["window_boundaries"])
        self.assertEqual(out["counts"]["eligible_work_pairs"], 1)
        self.assertEqual(out["outside_window"], [{"work_pair": ["b1", "a0"], "reason": "outside_window"}])

    def test_empty_evidence_is_not_clearance(self):
        data = fixture()
        data["references"] = []
        out = signals.analyze(data)
        self.assertIsNone(out["self_citation"]["share"])
        self.assertEqual(out["candidate_annotation"], "insufficient_evidence")
        self.assertEqual(out["fraud_verdict"], "not_assessed")

    def test_empty_authorship_abstains(self):
        data = fixture()
        data["works"][2]["authorships"] = []
        out = signals.analyze(data)
        self.assertEqual(out["abstentions"][0]["reason"], "identity_unknown_or_ambiguous")

    def test_fractional_projection_conserves_mass(self):
        data = synthetic.graph("ABCDEF", [("old", "ABC", "2020-01-01"),
                                             ("new", "DEF", "2022-01-01")], [("new", "old")])
        out = signals.analyze(data)
        self.assertEqual(len(out["author_edges"]), 9)
        self.assertEqual({arc["mass"] for arc in out["author_edges"]}, {"1/9"})
        self.assertEqual(sum(Fraction(a["mass"]) for a in out["author_edges"]), 1)

    def test_future_coauthorship_is_not_prior_overlap(self):
        data = fixture()
        data["references"] = data["references"][:1]
        data["works"].append(synthetic.graph("AB", [("later-team", "AB", "2023-01-01")], [])["works"][0])
        out = signals.analyze(data)
        self.assertEqual(out["coauthor_citation"]["nonself_mass"], "0")

    def test_possible_but_ambiguous_chronology_abstains(self):
        data = fixture()
        data["works"][1]["published"] = {"precision": "year", "value": "2022"}
        out = signals.analyze(data)
        self.assertEqual(out["abstentions"][0]["reason"], "chronology_ambiguous")

    def test_certainly_impossible_chronology_rejected(self):
        data = fixture()
        data["works"][1]["published"]["value"] = "2023-01-01"
        with self.assertRaisesRegex(ValueError, "impossible citation"):
            signals.analyze(data)

    def test_observation_before_publication_rejected(self):
        data = fixture()
        data["references"][0]["observed_on"] = "2021-01-01"
        with self.assertRaisesRegex(ValueError, "predates publication"):
            signals.analyze(data)

    def test_coarse_observation_order_abstains_not_guesses(self):
        data = fixture()
        data["works"][2]["published"] = {"precision": "year", "value": "2022"}
        data["references"][0]["observed_on"] = "2022-06-01"
        out = signals.analyze(data)
        self.assertEqual(out["abstentions"][0]["reason"], "observation_ambiguous")

    def test_later_observation_can_support_ambiguous_earlier_assertion(self):
        data = fixture()
        data["works"][2]["published"] = {"precision": "year", "value": "2022"}
        data["references"][0]["observed_on"] = "2022-06-01"
        data["references"].append(dict(data["references"][0], id="later", source_evidence_id="later",
                                       observed_on="2023-01-01"))
        out = signals.analyze(data)
        self.assertEqual(out["counts"]["eligible_work_pairs"], 2)
        self.assertEqual(len(out["paper_evidence"][0]["assertions"]), 2)
        self.assertEqual(out["paper_evidence"][0].get("projection_supporting_assertion_ids"), ["later"])

    def test_invalid_json_duplicate_keys_and_nonfinite_rejected(self):
        for raw in (b'{"version":1,"version":1}', b'NaN', b'Infinity', b'-Infinity',
                    b'1e999', b'{"unused":1e999}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                signals.loads(raw)

    def test_feature_digest_preserves_directional_array_order(self):
        self.assertNotEqual(signals.digest({"authors": ["A", "B"]}),
                            signals.digest({"authors": ["B", "A"]}))

    def test_input_byte_and_depth_bounds(self):
        for raw in (b" " * (signals.MAX_BYTES + 1), b"[" * 13 + b"0" + b"]" * 13):
            with self.assertRaises(ValueError):
                signals.loads(raw)
        self.assertEqual(signals.loads(b'{"quoted":"[[[[[[[[[[[[[[[[[[[[[["}')["quoted"], "[" * 22)

    def test_nested_unknown_fields_rejected(self):
        for key in ("authors", "works", "runs", "references"):
            data = fixture()
            data[key][0]["surprise"] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_schema_types_and_boundaries_rejected(self):
        mutations = [
            ("version", True), ("version", 1.0), ("version", 2),
            ("authors", None), ("references", {}), ("window", []),
        ]
        for key, value in mutations:
            data = fixture()
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_authorship_and_identifier_bounds(self):
        data = fixture()
        data["works"][0]["authorships"] *= 9
        with self.assertRaises(ValueError):
            signals.analyze(data)
        data = fixture()
        data["authors"][0]["identifiers"] = ["id:" + str(i) for i in range(9)]
        with self.assertRaises(ValueError):
            signals.analyze(data)
        data["authors"][0]["identifiers"] = ["duplicate", "duplicate"]
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_entity_and_assertion_bounds(self):
        for key, limit in (("authors", 64), ("works", 128), ("runs", 32), ("references", 512)):
            data = fixture()
            data[key] = [copy.deepcopy(data[key][0]) for _ in range(limit + 1)]
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_collection_limit_type_and_contradictions(self):
        for key, value in (("work_limit", True), ("reference_limit", 0),
                           ("reference_limit", float("nan")), ("work_limit", 1),
                           ("reference_limit", 1), ("truncated", 0), ("direction", "unknown")):
            data = fixture()
            data["runs"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_dangling_references_and_self_work_rejected(self):
        for key, value in (("citing", "missing"), ("cited", "missing"), ("run", "missing"), ("cited", "a1")):
            data = fixture()
            data["references"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_conflicting_assertion_and_source_ids_rejected(self):
        for key in ("id", "source_evidence_id"):
            data = fixture()
            data["references"][1][key] = data["references"][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_duplicate_entity_ids_rejected(self):
        for key in ("authors", "works", "runs"):
            data = fixture()
            data[key].append(copy.deepcopy(data[key][0]))
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_authorship_version_dangling_duplicate_rejected(self):
        for key, value in (("author_id", "missing"), ("resolution_version", "old"),
                           ("assertion_id", "not an id")):
            data = fixture()
            data["works"][0]["authorships"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)
        data = fixture()
        data["works"][0]["authorships"] *= 2
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_invalid_dates_and_window_rejected(self):
        for value in ("2022-02-29", "2022-2-01", "1800-01-01", None, 2022):
            data = fixture()
            data["works"][0]["published"]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                signals.analyze(data)
        for key, value in (("start", "2024-01-01"), ("end", "2025-01-01"), ("start", "1900-01-01")):
            data = fixture()
            data["window"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                signals.analyze(data)

    def test_future_run_and_publication_rejected(self):
        data = fixture()
        data["runs"][0]["as_of"] = "2025-01-01"
        with self.assertRaises(ValueError):
            signals.analyze(data)
        data = fixture()
        data["works"][0]["published"]["value"] = "2025-01-01"
        with self.assertRaises(ValueError):
            signals.analyze(data)

    def test_month_leap_year_and_day_same_time_precision(self):
        self.assertEqual(signals.interval({"precision": "month", "value": "2020-02"})[1].isoformat(),
                         "2020-02-29")
        data = fixture()
        data["works"][1]["published"]["value"] = "2022-01-01"
        self.assertEqual(signals.analyze(data)["counts"]["eligible_work_pairs"], 2)

    def test_motif_output_is_bounded_and_explicit(self):
        aids = "ABCDEFGHI"
        data = synthetic.graph(aids, [(a + "0", a, "2020-01-01") for a in aids] +
                               [(a + "1", a, "2022-01-01") for a in aids],
                               [(a + "1", b + "0") for a in aids for b in aids if a != b])
        out = signals.analyze(data)
        self.assertEqual(len(out["motifs"]["directed_three_author_cycles"]), signals.MAX_MOTIFS)
        self.assertTrue(out["motifs"]["enumeration_truncated"])

    def test_committed_fixture_outputs_replay_exactly(self):
        for name, expected in synthetic.artifacts().items():
            with self.subTest(name=name):
                self.assertEqual((synthetic.ROOT / name).read_text(encoding="utf-8"), expected)

    def test_cli_success_and_invalid_fixture_exit_codes(self):
        for name, code in (("reciprocal_authors", 0), ("invalid_future_observation", 2),
                           ("invalid_resolved_collision", 2), ("does-not-exist", 2)):
            command = [sys.executable, "-B", str(synthetic.ROOT / "signals.py"),
                       str(synthetic.ROOT / "fixtures" / (name + ".json"))]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            with self.subTest(name=name):
                self.assertEqual(result.returncode, code, result.stderr)
                if code == 0:
                    self.assertEqual(json.loads(result.stdout)["fraud_verdict"], "not_assessed")
                else:
                    self.assertEqual(result.stdout, "")
                    self.assertIn("Invalid fixture:", result.stderr)

    def test_every_published_case_cli_matches_committed_output(self):
        for name in synthetic.cases():
            command = [sys.executable, "-B", str(synthetic.ROOT / "signals.py"),
                       str(synthetic.ROOT / "fixtures" / (name + ".json"))]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            expected = json.loads((synthetic.ROOT / "outputs" / (name + ".json")).read_text(encoding="utf-8"))
            with self.subTest(name=name):
                if name.startswith("invalid_"):
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr.strip(), "Invalid fixture: " + expected["error"])
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), expected)

    def test_complete_and_partial_samples_never_certify_absence(self):
        for name in ("asymmetric_donor_recipient", "incomplete_incoming_only"):
            out = signals.analyze(synthetic.cases()[name])
            with self.subTest(name=name):
                self.assertIsNone(out["coverage"]["population_denominator"])
                self.assertIsNone(out["reciprocity"]["absence_established"])
                self.assertEqual(out["motifs"]["group_closure"], "unavailable")


if __name__ == "__main__":
    unittest.main()

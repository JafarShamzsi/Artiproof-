"""Fictional metric plumbing only, never scientific detector validation."""

import copy
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import unittest

from evaluate import evaluate
from verify_math import references


def row(identifier, label, score, decision):
    return {"id": "fictional-" + identifier, "label": label,
            "score": score, "decision": decision}


POS = "confirmed_manipulation"
NEG = "confirmed_nonmanipulation"


def fixture():
    return {
        "schema_version": "cite-eval-v1", "synthetic_only": True,
        "as_of": "2026-11-08", "model_version": "fictional-model-v1",
        "config_version": "fictional-config-v1", "label_version": "fictional-label-v1",
        "evidence_version": "fictional-evidence-v1", "labels_complete": True,
        "review_budget": 3,
        "rows": [row("a", POS, 0.9, "review"), row("b", NEG, 0.8, "review"),
                 row("c", POS, 0.8, "review"), row("d", NEG, 0.4, "dismiss"),
                 row("e", POS, 0.2, "dismiss"), row("f", POS, None, "abstain")],
    }


class MetricTests(unittest.TestCase):
    def test_confusion_and_precision_budget(self):
        result = evaluate(fixture())
        self.assertEqual(result["known_decided_confusion"], {"tp": 2, "fp": 1, "tn": 1, "fn": 1})
        self.assertEqual(result["metrics"]["precision_at_budget"]["value"], float(Fraction(2, 3)))
        self.assertEqual(result["metrics"]["precision"]["value"], float(Fraction(2, 3)))
        self.assertEqual(result["metrics"]["recall"]["value"], float(Fraction(2, 4)))
        self.assertEqual(result["metrics"]["selective_accuracy"]["value"], float(Fraction(3, 5)))
        self.assertEqual(result["coverage"]["decision_fraction"], float(Fraction(5, 6)))
        self.assertEqual(result["review"]["selected_ids"], ["fictional-a", "fictional-b", "fictional-c"])

    def test_stable_ties_and_permutation_digest(self):
        doc = fixture()
        doc["review_budget"] = 2
        expected = evaluate(doc)
        for permutation in itertools.permutations(doc["rows"][:3]):
            changed = copy.deepcopy(doc)
            changed["rows"][:3] = permutation
            self.assertEqual(evaluate(changed), expected)
        self.assertEqual(expected["review"]["selected_ids"], ["fictional-a", "fictional-b"])
        self.assertEqual(expected["metrics"]["precision_at_budget"]["value"], 0.5)

    def test_empty(self):
        doc = fixture()
        doc["rows"] = []
        result = evaluate(doc)
        self.assertIsNone(result["coverage"]["decision_fraction"])
        self.assertTrue(all(m["value"] is None for m in result["metrics"].values()))

    def test_unknowns_never_become_negatives(self):
        for label in ("unknown", "anomaly", "other_retraction"):
            with self.subTest(label=label):
                doc = fixture()
                doc["labels_complete"] = False
                doc["rows"] = [row("u", label, 0.99, "review")]
                result = evaluate(doc)
                self.assertEqual(result["known_decided_confusion"], dict(tp=0, fp=0, tn=0, fn=0))
                self.assertTrue(all(m["value"] is None for m in result["metrics"].values()))
                self.assertEqual(result["review"]["unknown_selected"], 1)

    def test_incomplete_refuses_population_metrics_but_not_known_queue_yield(self):
        doc = fixture()
        doc["labels_complete"] = False
        result = evaluate(doc)
        self.assertIsNone(result["metrics"]["recall"]["value"])
        self.assertIsNone(result["metrics"]["selective_accuracy"]["value"])
        self.assertAlmostEqual(result["metrics"]["precision_at_budget"]["value"], 2 / 3)

    def test_unknown_outside_queue_does_not_contaminate_queue_or_enable_recall(self):
        doc = fixture()
        doc["labels_complete"] = False
        doc["rows"].append(row("u", "unknown", 0.01, "dismiss"))
        result = evaluate(doc)
        self.assertIsNone(result["metrics"]["recall"]["value"])
        self.assertAlmostEqual(result["metrics"]["precision_at_budget"]["value"], 2 / 3)

    def test_all_abstain_and_positive_abstain_is_not_negative(self):
        doc = fixture()
        doc["rows"] = [row("p", POS, None, "abstain"), row("n", NEG, None, "abstain")]
        result = evaluate(doc)
        self.assertEqual(result["coverage"]["decision_fraction"], 0)
        self.assertIsNone(result["metrics"]["selective_accuracy"]["value"])
        self.assertEqual(result["metrics"]["recall"]["value"], 0)
        self.assertEqual(result["known_decided_confusion"]["fn"], 0)

    def test_zero_denominators(self):
        doc = fixture()
        doc["rows"] = [row("n", NEG, 0, "dismiss")]
        result = evaluate(doc)
        for name in ("precision", "recall", "false_discovery_proportion", "precision_at_budget"):
            self.assertIsNone(result["metrics"][name]["value"])
        self.assertEqual(result["metrics"]["false_positive_rate"]["value"], 0)

    def test_budget_not_silently_shrunk(self):
        doc = fixture()
        doc["review_budget"] = 4
        result = evaluate(doc)
        self.assertIsNone(result["metrics"]["precision_at_budget"]["value"])
        self.assertEqual(result["review"]["selected_count"], 3)
        self.assertEqual(result["review"]["unfilled_slots"], 1)

    def test_no_clearance_from_high_accuracy_low_base_rate(self):
        doc = fixture()
        doc["rows"] = [row(str(i), NEG, 0.1, "dismiss") for i in range(99)]
        doc["rows"].append(row("positive", POS, 0.1, "dismiss"))
        result = evaluate(doc)
        self.assertEqual(result["metrics"]["selective_accuracy"]["value"], float(Fraction(99, 100)))
        self.assertEqual(result["metrics"]["recall"]["value"], 0)
        self.assertIsNone(result["metrics"]["precision"]["value"])

    def test_digest_changes_for_labels_config_and_decisions(self):
        original = evaluate(fixture())["input_sha256"]
        for field, value in (("config_version", "fictional-v2"), ("as_of", "2026-11-07")):
            doc = fixture()
            doc[field] = value
            self.assertNotEqual(evaluate(doc)["input_sha256"], original)
        doc = fixture()
        doc["rows"][0]["label"] = NEG
        self.assertNotEqual(evaluate(doc)["input_sha256"], original)

    def test_wilson_interval_fixed_reference(self):
        interval = evaluate(fixture())["metrics"]["precision"]["wilson95_iid"]
        self.assertAlmostEqual(interval[0], 0.2076596008020477)
        self.assertAlmostEqual(interval[1], 0.9385080552796037)

    def test_exhaustive_three_case_conservation_and_fraction_oracle(self):
        # 216 label/decision combinations; independent rational arithmetic oracle.
        for labels in itertools.product((POS, NEG), repeat=3):
            for decisions in itertools.product(("review", "dismiss", "abstain"), repeat=3):
                doc = fixture()
                doc["review_budget"] = 1
                doc["rows"] = [row(str(i), label, None if decision == "abstain" else 0.5, decision)
                               for i, (label, decision) in enumerate(zip(labels, decisions))]
                result = evaluate(doc)
                cells = result["known_decided_confusion"]
                abstained = decisions.count("abstain")
                self.assertEqual(sum(cells.values()) + abstained, 3)
                expected_tp = sum(label == POS and decision == "review"
                                  for label, decision in zip(labels, decisions))
                expected_positives = labels.count(POS)
                metric = result["metrics"]["recall"]
                if expected_positives:
                    self.assertEqual(metric["value"], float(Fraction(expected_tp, expected_positives)))
                else:
                    self.assertIsNone(metric["value"])
                for metric in result["metrics"].values():
                    if metric["value"] is not None:
                        self.assertTrue(0 <= metric["wilson95_iid"][0] <= metric["value"]
                                        <= metric["wilson95_iid"][1] <= 1)

    def test_maximum_valid_rows_have_bounded_finite_output(self):
        doc = fixture()
        doc["review_budget"] = 5000
        doc["rows"] = [row(str(i), POS if i % 2 else NEG, 1, "review") for i in range(5000)]
        result = evaluate(doc)
        self.assertEqual(result["metrics"]["precision_at_budget"]["value"], 0.5)
        self.assertLess(len(json.dumps(result, allow_nan=False)), 1048576)

    def test_fictional_fixture_matches_contract(self):
        path = Path(__file__).with_name("fixtures") / "complete.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), fixture())

    def test_independent_math_reference(self):
        result = references()
        self.assertEqual(result.get("precision_at_budget_fraction"), "2/3")
        self.assertEqual(result["illustrative_ppv_fraction"], "10/121")
        self.assertEqual(result["illustrative_expected_true_alerts"], "90")
        self.assertEqual(result["illustrative_expected_false_alerts"], "999")
        self.assertAlmostEqual(float(result["wilson95_precision"][0]),
                               evaluate(fixture())["metrics"]["precision"]["wilson95_iid"][0])

    def test_abstained_labels_reported_separately(self):
        result = evaluate(fixture())
        self.assertEqual(result["coverage"].get("abstained_positive"), 1)
        self.assertEqual(result["coverage"]["abstained_negative"], 0)
        self.assertEqual(result["coverage"]["abstained_unknown"], 0)


class ValidationTests(unittest.TestCase):
    def test_invalid_probabilities_and_types(self):
        for score in (-0.1, 1.1, math.nan, math.inf, -math.inf, True, "0.9", None, 10**400):
            with self.subTest(score=str(score)[:20]):
                doc = fixture()
                doc["rows"][0]["score"] = score
                with self.assertRaises(ValueError):
                    evaluate(doc)

    def test_invalid_schema_and_inconsistent_labels(self):
        for field, value in (("schema_version", "v0"), ("synthetic_only", False),
                             ("review_budget", 0), ("review_budget", True),
                             ("review_budget", 5001), ("as_of", "2026-02-30"),
                             ("labels_complete", "yes"), ("model_version", "")):
            with self.subTest(field=field, value=value):
                doc = fixture()
                doc[field] = value
                with self.assertRaises(ValueError):
                    evaluate(doc)
        doc = fixture()
        doc["rows"][0]["label"] = "unknown"
        with self.assertRaises(ValueError):
            evaluate(doc)

    def test_duplicate_and_unknown_fields_and_bounds(self):
        for transform in (
            lambda d: d["rows"].append(copy.deepcopy(d["rows"][0])),
            lambda d: d.update(extra=1),
            lambda d: d["rows"][0].update(extra=1),
            lambda d: d["rows"][0].update(id="real-person"),
            lambda d: d["rows"][0].update(label=False),
            lambda d: d["rows"][0].update(decision="fraud"),
            lambda d: d["rows"][-1].update(score=0.2),
            lambda d: d.update(rows=d["rows"] * 834),
            lambda d: d.pop("evidence_version"),
        ):
            doc = fixture()
            transform(doc)
            with self.assertRaises(ValueError):
                evaluate(doc)


class CliTests(unittest.TestCase):
    def run_cli(self, text, *args):
        return subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("evaluate.py")), *args],
                              input=text, capture_output=True, text=True, timeout=10)

    def test_valid_cli_and_required_unavailable(self):
        result = self.run_cli(json.dumps(fixture()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), evaluate(fixture()))
        doc = fixture()
        doc["labels_complete"] = False
        result = self.run_cli(json.dumps(doc), "--require-metric", "recall")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("unavailable", json.loads(result.stderr)["error"])

    def test_strict_json_and_bounded_errors(self):
        valid = json.dumps(fixture())
        for text in ('{"a":1,"a":2}', valid.replace('0.9', 'NaN', 1),
                     valid.replace('0.9', '1e999', 1), '[', '[]',
                     '[' * 20 + '0' + ']' * 20, ' ' * (1048576 + 1),
                     valid.replace('"score": 0.9', '"score": 0.9, "score": 0.2', 1)):
            with self.subTest(prefix=text[:30]):
                result = self.run_cli(text)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertLess(len(result.stderr), 512)
                self.assertIn("error", json.loads(result.stderr))

    def test_invalid_utf8_is_rejected_without_echo(self):
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("evaluate.py"))],
                                input=b"\xff\xfe", capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn("error", json.loads(result.stderr))

    def test_fixture_reports_are_reproducible_and_incomplete_refuses_all(self):
        fixture_dir = Path(__file__).with_name("fixtures")
        for path in sorted(fixture_dir.glob("*.json")):
            text = path.read_text(encoding="utf-8")
            first = self.run_cli(text)
            second = self.run_cli(text)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, second.stdout)
            result = json.loads(first.stdout)
            self.assertEqual(result, evaluate(json.loads(text)))
            if path.stem == "incomplete":
                self.assertTrue(all(m["value"] is None for m in result["metrics"].values()))


if __name__ == "__main__":
    unittest.main()

"""Synthetic-only regressions; runnable with unittest without app/conftest imports."""

import copy
from contextlib import ExitStack
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools.legacy_data_audit import AuditInputError, classify, load_synthetic
from tools.legacy_data_audit.__main__ import main


FIXTURE = Path(__file__).parent / "fixtures/legacy_data_audit/upgrade.json"


def record(**overrides):
    row = {
        "id": "syn-1", "kind": "source_check", "stored_scope": "syn-10",
        "historical_scope": "syn-10", "scope_evidence": "creation_record",
        "current_user_org": "syn-99", "origin": "native",
        "consent": "unknown", "consent_audit_bound": False,
        "inputs": [], "artifact": "none", "share": "none", "deleted": False,
    }
    row.update(overrides)
    return row


def document(*rows):
    return {"schema_version": 1, "synthetic": True, "records": list(rows)}


class LegacyDataAuditTests(unittest.TestCase):
    def test_unknown_provenance_quarantined_not_current_pointer_inferred(self):
        result = classify(document(record(scope_evidence="unknown", historical_scope=None)))
        self.assertEqual(result["records"][0]["classification"], "quarantine_proposed")
        self.assertIn("scope_unproven", result["records"][0]["reasons"])

    def test_current_pointer_cannot_change_classification(self):
        a = document(record())
        b = copy.deepcopy(a)
        b["records"][0]["current_user_org"] = None
        self.assertEqual(classify(a), classify(b))

    def test_migration0012_cannot_prove_scope_even_with_matching_pointer(self):
        row = record(origin="migration_0012", current_user_org="syn-10")
        self.assertIn("backfill_not_provenance", classify(document(row))["records"][0]["reasons"])

    def test_migration0013_requires_reconsent_even_with_inviter_or_role_claim(self):
        row = record(kind="membership", origin="migration_0013",
                     consent="recipient_accepted", consent_audit_bound=True)
        result = classify(document(row))["records"][0]
        self.assertEqual(result["classification"], "quarantine_proposed")
        self.assertIn("recipient_reconsent_review", result["proposed_actions"])

    def test_acceptance_label_without_bound_audit_is_not_consent(self):
        row = record(kind="membership", consent="recipient_accepted")
        self.assertIn("consent_unproven", classify(document(row))["records"][0]["reasons"])

    def test_bound_recipient_acceptance_still_needs_manual_review(self):
        row = record(kind="membership", consent="recipient_accepted", consent_audit_bound=True)
        result = classify(document(row))["records"][0]
        self.assertEqual(result["classification"], "consistent_metadata_review_only")
        self.assertEqual(result["proposed_actions"], ["manual_review"])

    def test_misstamped_scope_never_automatically_restamped(self):
        result = classify(document(record(stored_scope="syn-20")))["records"][0]
        self.assertIn("scope_conflict", result["reasons"])
        self.assertNotIn("new_scope", result)
        self.assertIn("explicit_mapping_review", result["proposed_actions"])

    def test_known_personal_scope_is_not_unknown(self):
        result = classify(document(record(stored_scope=None, historical_scope=None)))
        self.assertEqual(result["records"][0]["classification"], "consistent_metadata_review_only")

    def test_report_scope_must_match_all_inputs(self):
        a = record()
        b = record(id="syn-2", stored_scope=None, historical_scope=None)
        report = record(id="syn-3", kind="report", inputs=["syn-1", "syn-2"])
        result = classify(document(a, b, report))["records"][2]
        self.assertIn("input_scope_conflict", result["reasons"])

    def test_missing_deleted_and_wrong_kind_inputs_fail_closed(self):
        for rows in (
            [record(kind="report", inputs=["syn-2"])],
            [record(kind="report", inputs=["syn-2"]), record(id="syn-2", deleted=True)],
            [record(kind="report", inputs=["syn-2"]), record(id="syn-2", kind="membership")],
            [record(kind="report", inputs=["syn-1"])],
        ):
            with self.subTest(rows=rows):
                self.assertEqual(classify(document(*rows))["records"][0]["classification"],
                                 "quarantine_proposed")

    def test_report_inherits_ambiguous_input_even_if_scope_matches(self):
        result = classify(document(
            record(scope_evidence="unknown"),
            record(id="syn-2", kind="report", inputs=["syn-1"]),
        ))["records"][1]
        self.assertIn("input_provenance_unproven", result["reasons"])

    def test_inputless_legacy_summary_and_schedule_remain_blocked(self):
        for kind in ("report", "schedule"):
            with self.subTest(kind=kind):
                result = classify(document(record(kind=kind)))["records"][0]
                self.assertEqual(result["classification"], "quarantine_proposed")

    def test_cache_and_share_disposition_are_proposals_not_deletions(self):
        result = classify(document(record(artifact="cached_pdf", share="expiry_unknown")))["records"][0]
        self.assertIn("artifact_hold_review", result["proposed_actions"])
        self.assertIn("share_disable_review", result["proposed_actions"])
        self.assertIn("share_expiry_unproven", result["reasons"])

    def test_upgrade_fixture_exact_classifications(self):
        data = load_synthetic(FIXTURE.read_text(encoding="utf-8"))
        result = classify(data)
        self.assertEqual([r["classification"] for r in result["records"]],
                         ["quarantine_proposed"] * 5 + ["consistent_metadata_review_only"])
        self.assertEqual(result["mode"], "synthetic_offline_proposals_only")
        self.assertFalse(result["production_audit_performed"])

    def test_input_not_mutated_and_output_deterministic(self):
        data = document(record())
        before = copy.deepcopy(data)
        self.assertEqual(classify(data), classify(data))
        self.assertEqual(data, before)
        self.assertNotIn("syn-", json.dumps(classify(data)))

    def test_customer_text_tokens_paths_and_unknown_fields_rejected_without_echo(self):
        for field in ("title", "input_content", "share_token", "email", "pdf_path", "token", "annotations"):
            with self.subTest(field=field):
                data = document(record(**{field: "CUSTOMER_SECRET_SENTINEL"}))
                with self.assertRaises(AuditInputError) as caught:
                    classify(data)
                self.assertNotIn("CUSTOMER_SECRET_SENTINEL", str(caught.exception))
                self.assertNotIn(field, str(caught.exception))

    def test_invalid_shapes_types_enums_and_aliases_rejected(self):
        cases = [None, [], {}, document(record(id="real-customer-id")),
                 document(record(stored_scope="bearer-secret")), document(record(kind=[])),
                 document(record(deleted=1)), document(record(inputs="syn-2")),
                 document(record(origin="future")), document(record(consent_audit_bound="yes")),
                 document(record(artifact="/private/file.pdf")), document(record(share="token")),
                 document(record(inputs=["syn-2", "syn-2"])),
                 document(record(), record()), document(record(kind="membership", inputs=["syn-2"])),
                 document(record(scope_evidence="creation_record", historical_scope=42)),
                 {**document(record()), "synthetic": False},
                 {**document(record()), "schema_version": True},
                 {**document(record()), "extra": "secret"}]
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(AuditInputError):
                    classify(data)

    def test_duplicate_json_keys_nonfinite_and_oversize_rejected(self):
        for text in ('{"synthetic":true,"synthetic":false}', '{"x": NaN}',
                     '{"x": Infinity}', 'not-json SECRET', ' ' * 1_048_577):
            with self.subTest(text=text[:40]):
                with self.assertRaises(AuditInputError) as caught:
                    load_synthetic(text)
                self.assertNotIn("SECRET", str(caught.exception))

    def test_no_network_database_or_application_imports(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            classify(document(record()))
        for path in (Path(__file__).parents[1] / "tools/legacy_data_audit").glob("*.py"):
            import ast
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imports.append(node.module.split(".")[0])
            self.assertLessEqual(set(imports), {"argparse", "json", "re", "sys", "pathlib"})

    def test_cli_has_no_apply_database_or_output_write_mode(self):
        root = Path(__file__).parents[1]
        for args in (["--apply"], ["--database-url", "SECRET"], []):
            result = subprocess.run([sys.executable, "-B", "-m", "tools.legacy_data_audit", *args],
                                    cwd=root, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("SECRET", result.stdout + result.stderr)

    def test_cli_fixture_success_is_metadata_only(self):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "tools.legacy_data_audit", "--synthetic-input", str(FIXTURE.resolve())],
            cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), classify(json.loads(FIXTURE.read_text())))

    def test_report_resolution_does_not_depend_on_inventory_order(self):
        rows = [record(), record(id="syn-2", kind="report", inputs=["syn-1"])]
        for ordered in (rows, rows[::-1]):
            result = classify(document(*ordered))
            self.assertTrue(all(r["classification"] == "consistent_metadata_review_only"
                                for r in result["records"]))

    def test_resource_and_input_bounds(self):
        for data in (document(), document(*[record(id=f"syn-{n}") for n in range(1, 1002)]),
                     document(record(kind="report", inputs=[f"syn-{n}" for n in range(1, 27)]))):
            with self.subTest(count=len(data["records"])):
                with self.assertRaises(AuditInputError):
                    classify(data)

    def test_unknown_origin_deleted_unknown_artifact_and_null_membership_hold(self):
        for overrides, reason in (({"origin": "unknown"}, "origin_unproven"),
                                  ({"deleted": True}, "deleted_record_hold"),
                                  ({"artifact": "unknown"}, "artifact_provenance_unproven"),
                                  ({"kind": "membership", "stored_scope": None}, "membership_scope_missing")):
            with self.subTest(reason=reason):
                self.assertIn(reason, classify(document(record(**overrides)))["records"][0]["reasons"])

    def test_cli_never_echoes_rejected_content_and_opens_only_for_read(self):
        for raw in (b'{"SECRET_SENTINEL": "token"}', b'\xff', b' ' * 1_048_577):
            with self.subTest(length=len(raw)):
                out, err = io.StringIO(), io.StringIO()
                with patch.object(sys, "argv", ["audit", "--synthetic-input", "synthetic.json"]), \
                        patch("pathlib.Path.is_file", return_value=True), \
                        patch("pathlib.Path.is_symlink", return_value=False), \
                        patch("pathlib.Path.open", return_value=io.BytesIO(raw)) as opened, \
                        patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
                    self.assertEqual(main(), 2)
                opened.assert_called_once_with("rb")
                self.assertEqual(out.getvalue(), "")
                self.assertEqual(err.getvalue(), "Invalid synthetic metadata input.\n")

    def test_cli_missing_or_non_json_file_errors_are_static(self):
        for name in ("SECRET_SENTINEL.json", "SECRET_SENTINEL.env"):
            with self.subTest(name=name):
                out, err = io.StringIO(), io.StringIO()
                with patch.object(sys, "argv", ["audit", "--synthetic-input", name]), \
                        patch("pathlib.Path.is_file", return_value=False), \
                        patch("pathlib.Path.is_symlink", return_value=False), \
                        patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
                    self.assertEqual(main(), 2)
                self.assertNotIn("SECRET_SENTINEL", out.getvalue() + err.getvalue())

    def test_cli_remote_paths_rejected_before_any_filesystem_probe(self):
        for name in ("//server/share/synthetic.json", r"\\server\share\synthetic.json",
                     "https://example.invalid/synthetic.json"):
            with self.subTest(name=name):
                with patch.object(sys, "argv", ["audit", "--synthetic-input", name]), \
                        patch("pathlib.Path.is_file", side_effect=AssertionError("remote probe")), \
                        patch("pathlib.Path.is_symlink", side_effect=AssertionError("remote probe")), \
                        patch.object(sys, "stderr", io.StringIO()):
                    self.assertEqual(main(), 2)

    def test_cli_mixed_separator_unc_and_device_paths_forbid_all_io(self):
        # Invented spellings only. Never probe a real UNC or device path.
        prefixes = ("//", "\\\\", "/\\", "\\/")
        tails = ("server.invalid/share/synthetic.json",
                 "?/UNC/server.invalid/share/synthetic.json",
                 "./UNC/server.invalid/share/synthetic.json",
                 "?/C:/synthetic.json", "./C:/synthetic.json")
        for prefix in prefixes:
            for tail in tails:
                for separator in ("/", "\\"):
                    name = prefix + tail.replace("/", separator)
                    with self.subTest(name=name):
                        out, err = io.StringIO(), io.StringIO()
                        forbidden = (
                            "pathlib.Path.is_symlink", "pathlib.Path.is_file",
                            "pathlib.Path.open", "pathlib.Path.stat", "pathlib.Path.lstat",
                            "pathlib.Path.resolve", "builtins.open", "io.open",
                            "os.open", "os.stat", "os.lstat", "socket.socket",
                        )
                        with ExitStack() as stack:
                            # Python 3.12 gettext may stat local translation files
                            # while constructing argparse. Keep only localization
                            # pure, without relaxing any filesystem prohibition.
                            stack.enter_context(patch("argparse._", side_effect=lambda message: message))
                            stack.enter_context(patch.object(sys, "argv", ["audit", "--synthetic-input", name]))
                            stack.enter_context(patch.object(sys, "stdout", out))
                            stack.enter_context(patch.object(sys, "stderr", err))
                            probes = [stack.enter_context(patch(target, side_effect=AssertionError("I/O forbidden")))
                                      for target in forbidden]
                            self.assertEqual(main(), 2)
                            for probe in probes:
                                probe.assert_not_called()
                        self.assertEqual(out.getvalue(), "")
                        self.assertEqual(err.getvalue(), "Invalid synthetic metadata input.\n")

    def test_cli_ordinary_local_separator_spellings_still_read_synthetic_input(self):
        raw = json.dumps(document(record())).encode("utf-8")
        names = ("synthetic.json", "./fixtures/synthetic.json", "fixtures\\synthetic.json",
                 "C:/synthetic/fixture.json", "C:\\synthetic\\fixture.json",
                 "/local/synthetic/fixture.json")
        for name in names:
            with self.subTest(name=name):
                out, err = io.StringIO(), io.StringIO()
                with patch.object(sys, "argv", ["audit", "--synthetic-input", name]), \
                        patch("pathlib.Path.is_symlink", return_value=False), \
                        patch("pathlib.Path.is_file", return_value=True), \
                        patch("pathlib.Path.open", return_value=io.BytesIO(raw)) as opened, \
                        patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
                    self.assertEqual(main(), 0)
                opened.assert_called_once_with("rb")
                self.assertEqual(json.loads(out.getvalue()), classify(document(record())))
                self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

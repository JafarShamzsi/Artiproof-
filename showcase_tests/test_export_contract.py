"""Publication boundary regressions; no services or secrets required."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ExportContract(unittest.TestCase):
    def test_artifact_ignores_do_not_hide_application_routes(self):
        lines = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertNotIn('reports/', lines)
        self.assertIn('/reports/', lines)

    def test_sanitization_keeps_explicit_cors_binding(self):
        code = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
        self.assertIn('cors_regex = settings.CORS_ORIGIN_REGEX or None', code)

    def test_no_private_operational_material(self):
        for name in ('AGENTS.md', '.agents', 'PROMPTS', 'docs', 'scripts',
                     'docker-compose.yml', 'backend/railway.toml',
                     'backend/app/cli/migrate_artifacts.py'):
            self.assertFalse((ROOT / name).exists(), name)

    def test_source_only_ci(self):
        workflows = list((ROOT / '.github/workflows').glob('*'))
        self.assertEqual([p.name for p in workflows], ['showcase-ci.yml'])
        code = workflows[0].read_text(encoding='utf-8')
        for forbidden in ('secrets.', 'deployments:', 'packages:', 'id-token:',
                          'pull_request_target', 'repository_dispatch',
                          'upload-artifact', 'docker push', 'ssh '):
            self.assertNotIn(forbidden, code)
        self.assertIn('contents: read', code)
        for check in ('npm run lint', 'tsc --noEmit', 'test:unit', 'build -- --webpack',
                      'test_analysis_runs_integration.py'):
            self.assertIn(check, code)

    def test_fonts_keep_copyright_and_license(self):
        for family in ('fraunces', 'inter', 'jetbrainsmono', 'newsreader'):
            text = (ROOT / f'frontend/src/app/fonts/{family}-OFL.txt').read_text(encoding='utf-8')
            self.assertIn('Copyright', text)
            self.assertIn('SIL OPEN FONT LICENSE', text)

    def test_no_automatic_parent_dotenv_loading(self):
        code = (ROOT / 'backend/app/config.py').read_text(encoding='utf-8')
        self.assertIn('"env_file": None', code)

    def test_review_identity_is_explicit(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('not\nthe production service', text)
        self.assertIn('No application-wide license grant', text)


if __name__ == '__main__':
    unittest.main()

# SECURITY-02: Preserve derived-report tenant scope

Manager-confirmed scope for a bounded run, device axel-windows, base b475587255e27aab730fdb9a4fa3c8529f6a3ba9. Worktree D:/Developer/ArtiProof-worktrees/security-02, branch agent/security-02/report-scope. Read manager AGENTS.md and live GitHub issue/comments before editing. This lane depends on SECURITY-01's original slice but must not edit its live worktree.

## Findings to reproduce and close

- backend/app/routers/reports.py:428 assigns every generated report to current_user.organization_id even when inputs are personal/previous-org data accessible through direct ownership. This transfers visibility to the new org's admins.
- backend/app/tasks/scheduled_reports.py:134 selects checks by user_id without org scope and stamps the current org at line 193. Switching/joining orgs can disclose prior history through derived reports.

## Exclusive writable scope

backend/app/routers/reports.py, backend/app/routers/report_schedules.py, backend/app/tasks/scheduled_reports.py, new backend/tests/test_report_scope_security.py and backend/tests/test_report_scope_integration.py, docs/REPORT-SCOPE-SECURITY.md. Read any non-secret callers/models; request scope expansion if needed. Do NOT edit org/auth/admin/general ownership helpers, CI, dependencies, existing security-01 tests or frontend. No migrations without manager approval; don't solve unclear historical schedule scope by retroactively assigning current org.

## Acceptance

1. Failing regression first for personal-to-new-org and org-A-to-org-B derived reports. Scope must remain bound to inputs, with authorization rechecked; reject mixed-scope comparison/institutional audit unless separately authorized transfer exists (none is approved here). Cover source/researcher/comparison/audit branches and report read authorization.
2. Existing schedule rows without durable original scope must fail closed. Smallest pilot-safe option is disable unsafe scheduling creation/execution explicitly rather than inventing scope from mutable user pointers; document impact and safe re-enable criteria. No silent success or claiming a sent summary when disabled.
3. PostgreSQL integration tests use disposable fixtures and demonstrate isolation. If services unavailable locally, report skips, do not pretend mocked tests establish database guarantees. CI inclusion coordinated by manager/CI-01, not this lane.
4. Inspect cached/export/share readers for scope consequences; do not expand to all privacy lifecycle work. Audit-only fixtures; no secrets/.env/customer data or live-provider calls.

Use an isolated environment; do not mutate shared audit venv. Run affected and full backend unit suites; relevant lint. Commit ONLY allowed paths using authorized repository author, [SECURITY-02] subject and Agent-Tag: SECURITY-02, Device-Tag: axel-windows trailers. Push assigned branch, create draft PR with base/dependency, exact SHA, commands/results, incomplete acceptance and rollback. Refs issue (no automatic closure). Read back remote state. Never merge, deploy, force-push or modify main. End bounded run with actual outcomes and unresolved scope, not indefinite polling.

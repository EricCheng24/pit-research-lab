# Contributing a small change

Use this path: feature branch → pull request (PR) → hosted checks (CI) →
human review → later authorized merge. Keep one task small. Run commands from
the repository root, one at a time; **stop on any failure** in every block below.

## Where to work

- `src/pit_research_lab/`: Python package, CLI and database infrastructure.
- `tests/unit/`: self-contained tests; no Docker needed.
- `tests/integration/database/`: tests against real Test PostgreSQL.
- `docs/`: explanations and development guides.
- `scripts/`: operator tools; `scripts/database.py` guards DB identity and ownership.
- `.github/`: GitHub configuration; `.github/workflows/ci.yml` runs **Quality**
  and **PostgreSQL Integration**.

PIT research contracts, finance modules and TWSE adapters are future work.
Agree on scope. DB, migrations, deletion/cleanup, permissions,
credentials/tokens, CI/rulesets, architecture and future PIT eligibility need
explicit Technical Lead authorization and review, with focused independent
review as needed. Ordinary docs or isolated unit corrections need scope and
self-review plus observed CI; there is no blanket second-approver requirement.

## Branch, edit and submit

Run `git status --short --branch`. If dirty or unclear, stop and reconcile with
the owner. With a clean worktree and permission, update `main` by fast-forward
(moving forward without combining divergent histories), then branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c docs/clarify-testing
```

Choose a descriptive name for your task. If update fails or the branch exists,
ask for help. Never reset, discard, overwrite others' work, force-push or
silently pull over changes.

Edit and check as below. Examine `git diff` and `git status --short`; stage only
intended paths with `git add <path>`. Inspect `git diff --cached` and run
`git diff --cached --check`, then commit and push using your branch name:

```bash
git commit -m "docs: clarify testing instructions"
git push -u origin docs/clarify-testing
```

Open a GitHub PR to `main`. Answer **What changed?**, **How was it tested?**, and
**Anything reviewers should know?** (allows “None”). Reported local tests are
distinct from observed hosted results. Wait for **Quality** and **PostgreSQL
Integration** to both finish **completed/success on the latest commit**. Failed,
canceled, skipped or neutral results are not accepted. Push fixes to the same
branch; inspect fresh results each time.

The template is guidance, not branch protection. CAP-F1-4 is
**COMPLETE / ACCEPTED / FROZEN**; PR #4 is historically merged.
P1-C3-01 remains an **ACCEPTED HISTORICAL PROCESS EXCEPTION**, not retroactive
proof of the historical exact-SHA final approval. A prior read-only inspection
observed the active `main-required-ci` Ruleset; that time-scoped evidence does not
certify future settings. Current settings and new-PR template UI behavior are
**NOT CHECKED** here; the required latest CI checks above remain the merge policy.
Merge only when separately permitted; prefer approved squash merge if available
(one contribution commit).

## Local checks first

Use Python **3.12** and `uv sync --locked --python 3.12`, then `make check` if Make
is available. The Makefile declares `.POSIX:`; GNU Make is not mandatory and this
does not claim every Make implementation was natively tested.
This Docker-free gate checks lock/lint/format/types and fast tests;
real DB tests are excluded. Without Make, run these equivalents in order:

```bash
uv lock --check
uv run --locked ruff check src tests scripts migrations
uv run --locked ruff format --check src tests scripts migrations
uv run --locked mypy src/pit_research_lab
uv run --locked pytest -q -m 'not integration'
```

For packaging/CI work when warranted, also run `make build` (or `uv build`).
See the [testing guide](testing.md) for test conventions.

## DB work: approved Test setup only

Read the [database guide](database.md). The lead allocates a unique namespace
and non-overlapping approved Dev/Test port pair. Configure **once per checkout**;
retain `.env.dev.local`/`.env.test.local`. Never rerun setup over them, edit/print
them as a shortcut, or share contents. With configured, authorized Test, run:

```bash
make db-test-preflight
make db-test-up
make db-test-probe
make test-all
```

Without Make, the equivalents are:

```bash
uv run --locked python scripts/database.py preflight test
uv run --locked python scripts/database.py up test
uv run --locked python scripts/database.py probe test
uv run --locked pytest -q -m 'not integration'
uv run --locked pytest -q -m integration
```

Both pytest passes are mandatory and serial; stop on either failure. No Dev
runtime is needed. Never overlap lifecycle/tests on one target. Cleanup/destruction
needs explicit authorization and the guarded helper. Never operate on another
checkout's or unrelated resources, including Survivor OS.

## If a check is red

Find the first failing job/step/test; use the matching local command.

- Lint, formatting, type, unit/pytest or build failure: fix the scoped cause.
- Missing Test config, Docker access or service: confirm setup/prerequisites;
  use the guarded Test sequence only when authorized.
- Ownership, identity, role or credential refusal: stop, retain resources and
  ask the lead for focused diagnosis. Never loosen guards or reset storage.
- Hosted runner/tool mismatch: report step/version; ask the lead for focused help.

Never bypass red CI, remove checks or change secrets to get green. Share redacted
test names, commands and nonsecret summaries only. Do not paste
`.env` contents, passwords, DSNs (connection URLs), raw Compose JSON, Docker
environments or large private logs. Green CI checks engineering behavior, not
scientific validity. Codex can explain files/errors and propose bounded edits;
the author must understand and check its output, diff and actual test results.

## Two paper examples

**Docs:** `docs/clarify-testing` edits one sentence in `docs/development/testing.md`;
run `make check`, review, commit/push and open a PR. After an actual passing run,
sample answers: “Clarified the fast-test command.” / “Local `make check` passed.” /
“None”. Inspect both latest hosted jobs, self-review scope, await merge permission.

**DB test:** lead-approved `test/database-transaction-case` adds one assertion in
`tests/integration/database/test_transactions.py`. With pre-existing approved
Test configuration, run preflight → up → probe → `make test-all` above. Stop on
refusal; report actual results, commit/push/open PR, request lead scope review
and inspect both hosted jobs before a later authorized merge. Both examples
are paper scenarios, not executed runs.

Low-RAM machines should run Docker-free checks first. CAP-F1-5A Environment Doctor
is **COMPLETE / ACCEPTED**. Contributor adoption (Layer B) and Windows WSL2/native
macOS ARM64/8 GB observations (Layer C) remain **NON-BLOCKING / CONTINUOUS**, including
F1-5C/F1-6; no contributor completion quorum is required. Missing native evidence
is not a mandatory engineering failure; real safety/Core defects still need review.

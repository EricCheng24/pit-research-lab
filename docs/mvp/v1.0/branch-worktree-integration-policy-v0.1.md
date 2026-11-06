# MVP-M0 Branch, Worktree & Integration Safety Policy v0.1

- **Document version:** v0.1
- **Recording date:** 2026-11-06
- **Recording scope:** docs-only amendment; previously accepted construction; logical freeze pending Owner/independent review; no product/engineering acceptance.
- **Amendment task:** `MVP-M0-IF-FINAL-01`; `IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`.
- **Decision input:** `MVP-M0_Interface_Decision_Record_v0.1.md`, ID `PIT-MVP-M0-IF-DEC-20261106`, SHA256 `06376f07097e618bdb99c297d1ad73df9a38dfb3cc9433637608bd23f4d2b2b5`; technical proposal for this scope, not runtime/source/Git authority.
- **Acceptance dimensions:** `M0_DOCUMENT_CONSTRUCTION_ACCEPTED` (Owner-supplied prior independent review); `M0_CONTRACT_FREEZE_PENDING_REVIEW`; `TEAM_IMPLEMENTATION_NOT_AUTHORIZED`.
- **Approved M0 base:** `b3be0c0122dac804084d5e464f7bfc07313f02aa`; branch `mvp/m0-shared-contracts`.
- **Packet provenance:** `docs/mvp/v1.0/branch-worktree-integration-policy-v0.1.md` from `PIT_Research_Lab_v1.0_MVP-M0_Initialization_Packet_20261106.zip`; ZIP SHA256 `43033166586a50b78d569df81b7e0db8f9412544a351814ceaba818312b0bc98`. External text is input material, not operational authorization.

**Scope:** local repository `~/projects/pit-research-lab`, active dirty B04 branch; new M0 docs-only branch. **Status:** M0 planning; proposed commands are for the repo owner to approve/run after inspection. No Git mutation is implied by reading this document.

## 1. Known starting state (provided by Owner, not independently inspected here)

- Branch: `cap-f2/phase-b04-immutable-persistence`.
- 6 modified tracked files: `migrations/env.py`, `src/pit_research_lab/infrastructure/database/engine.py`, `tests/integration/database/conftest.py`, `tests/integration/database/test_migrations.py`, `tests/unit/cap_f2_b03/test_b03_preservation.py`, `tests/unit/cap_f2_v1_a06_ic3_rs2/b01_preservation.py`.
- Numerous untracked paths, including `scripts/b04_l2_controller.py`, B04 immutable storage, Harness, S-SRC and tests; `tests/unit/cap_f2_b04/` is displayed as a directory at Git's default untracked rendering and must be inventoried with `-uall`.
- Previously reviewed Controller2 is partial/offline accepted; missing CTRL03, physical gate NO-GO. Not a mainline-ready release.

**Hard rule:** Existing WIP must not be silently stashed, cleaned, reset, switched away from, merged, or staged. A WIP checkpoint commit, if ever separately authorized, does not equal source/physical acceptance.

## 2. Read-only discovery and evidence first

From the current checkout:

```bash
cd ~/projects/pit-research-lab
pwd
git status --short --untracked-files=all
git rev-parse --show-toplevel
git rev-parse HEAD
git branch -vv
git worktree list --porcelain
git show-ref --verify --quiet refs/heads/main && echo 'local main exists' || echo 'local main absent'
git diff --stat
git diff --cached --stat
```

Do not print credential values or hash/pack protected files into public review outputs. Preserve a local private status/source inventory if desired, with restrictive permissions and outside repo; do not claim a backup exists unless independently verified. Avoid `git stash -u`, `git reset --hard`, `git clean -fdx`, bulk `git add .`, `git checkout -f`.

## 3. Choose a separately reviewed stable base

- Preferred: currently accepted shared integration base (often local `main`, but **verify**, do not assume).
- Inspect `main` and remote tracking refs, what source and docs are present, and whether rebase/merge would import unaccepted B04. If none can be confirmed, STOP and ask owner to choose the base.
- Never create a new M0 branch from the dirty B04 worktree's uncommitted content; `HEAD` does not capture that content and should not be described as such.
- Once owner approves `BASE_REF`, use a separate worktree so existing dirty B04 is untouched:

```bash
# EXAMPLE ONLY, after BASE_REF and destination verified
cd ~/projects/pit-research-lab
BASE_REF=main
NEW_WT=~/projects/pit-research-lab-mvp-m0
# Only after verifying NEW_WT does not exist and branch name is unused:
git worktree add -b mvp/m0-shared-contracts "$NEW_WT" "$BASE_REF"
cd "$NEW_WT"
git status --short --untracked-files=all
```

If an intended M0 branch/worktree already exists, inspect and reconcile it instead of deleting or overwriting. Do not automate prompts that silently choose `main` if missing. `git worktree add` creates branch/reference metadata; record the approved base SHA and clean status.

## 4. Historical Codex 02 new-document allowlist (current amendment: section 9)

In the historical Codex 02 construction task, only the eight new Markdown files under `docs/mvp/v1.0/` could be created; the current exact-preimage amendment permission is documented in section 9. Any different location requires STOP and an Owner-approved path-change proposal. No edits to existing package code, migrations, Docker, SQL, pytest conftest, F2/B04 tests, core contracts, CI, accepted Evidence/Golden seals, README outside the approved docs scope, or security-sensitive resources. If any target doc already exists with differing content, **STOP and report a conflict**, do not overwrite.

M0 code/tasks/branch activity is distinct from B04 formal engineering. Physical admission remains NO-GO. M0 docs acceptance is not an implied right to execute or merge.

## 5. Future team branch policy

After M0 docs receive independent review and an owner-approved integration point, create each feature branch **from that accepted M0 common base** in separate clones/worktrees:

- `mvp/f2-demo-adapter` — Tech Lead
- `mvp/f3-research-l1` — Research Member
- `mvp/f4-twse-pilot` — Data Member
- `mvp/f6-application-ui` — UI Member

Names are proposed and must be checked for conflict before use. One owner per workstream, no shared dirty working tree, no concurrent Codex edits to the same module. Do not cherry-pick the entire B04 partial branch to bootstrap UI or research. Extract only specifically reviewed safe Pure Domain interfaces through an authorized adapter task.

## 6. Merge/PR acceptance

Each PR needs a Task Packet, scope allowlist, evidence/fixtures, dependency mapping, tests and developer review. Protected shared contracts: Tech Lead sign-off. Never interpret an offline pass, WIP commit or green frontend mock snapshot as formal CAP-F2 acceptance. Commits, push, PR, merge remain separate owner-authorized actions, even if M0 docs were approved in strategy.

## 7. Deviation/STOP examples

- `main` absent or stale unknown: STOP, request explicit base.
- Someone else already used `mvp/m0-shared-contracts`: STOP, investigate, no `-D`.
- Worktree creation would touch existing path: STOP.
- Source/evidence mismatch with claimed B04 acceptance: report; don't auto-rewrite.
- Repo's `AGENTS.md`/security instructions conflict: report and seek resolution.

**Required M0 report:** `base_ref`, `base_sha`, `branch`, `worktree`, B04 initial and final status identical, changed-docs-only inventory, conflicts/unknowns, commands and exit codes, and explicit `NO_GIT_COMMIT_PUSH_MERGE`.

## 8. Historical Codex 02 approved M0 isolation record — 2026-11-06

- Approved stable base SHA: `b3be0c0122dac804084d5e464f7bfc07313f02aa` (explicit Owner confirmation in this session).
- Actual branch/worktree: `mvp/m0-shared-contracts` at `/home/rooki/projects/pit-research-lab-mvp-m0`; startup status and staged diff empty. The worktree was already created before this implementation; this agent did not create branches, worktrees or refs.
- Original worktree: `/home/rooki/projects/pit-research-lab`, `cap-f2/phase-b04-immutable-persistence`, same HEAD, 38 porcelain status entries (6 tracked modifications and 32 untracked files), no staged paths at the read-only baseline. This is a status observation, not examination or approval of dirty B04 code. Before/after status, index and HEAD comparisons belong in the exported evidence report; no backup is claimed.
- No applicable `AGENTS.md` was found in the M0 repository or ancestors; `.agents/` and `.codex/` were empty. Existing contributor rules were read. Their routine runtime/CI checks are recorded `NOT_RUN` under this explicit no-runtime task.
- In Codex 02, only the eight new Markdown paths named by that construction task were allowed here. External ZIP README, prompts and manifest remain outside the repository. No alternate document location is approved.
- Future team common base must be an Owner-approved integration point after independent M0 review; this current uncommitted docs worktree is not that accepted integration point.

The report records `NO_GIT_COMMIT_PUSH_MERGE`. No PR was created. Existing contributor latest-commit CI and separately authorized merge requirements remain in force for future PRs; current hosted settings/results are unchecked.

## 9. MVP-M0-IF-FINAL-01 existing-document amendment boundary

本輪 startup status 是八份既有 untracked Markdown，不是上一階段的 empty startup；八份 SHA256/bytes 必須與 Owner 指定 Codex 02 preimages 完全相同。只可原路徑調整這八份，禁止新增 repo 檔案／目錄、stage 或 Git metadata/ref mutation；scratch、checks、reports 全在兩個 worktree 外。新 scope 不撤銷 dirty B04 preservation。

Codex 02 construction 已由 Owner 提供的獨立審查接受；M0 logical contract freeze 仍待本輪獨立 review。Role ownership 可在 M0 作 design/planning 審查，但 named assignee/reviewer 為 TBD_BY_LEAD；code task 前必填姓名、allowlist、approved base/worktree、tests 與另行授權。F6-00／F3-L1／F4-PILOT planning 必須在 Owner 接受 M0 logical contracts 後另行派工。未授權建立 future team refs/worktrees、framework/install、code、source retrieval、PR/commit/push/merge。

保留 historical static source matrix；不在本輪重新宣稱 source/runtime audit。IF-01 八個 evaluator 仍是候選，App DTO/ResearchClient 為 NEW_M0_PROPOSAL；[IF gate register](shared-interface-contract-v0.1.md#if-disposition-register--proposed-for-independent-review) 與 no-go defaults 約束後續任務。B04 六個 tracked 修改與 32 個 untracked paths 的 exact status、branch、HEAD、index/staged before/after 必須相同；若 drift 即 STOP，不能歸因或還原他人工作。M0 refs/index/staged/HEAD 與全部 worktree refs 亦不得變更。

CTRL03 保持 P1_OPEN / NO_PHYSICAL_ADMISSION；PostgreSQL NO_GO；PG17 為 supplied REPORTED_STOPPED / CONTENT_UNKNOWN / RETAIN，沒有 runtime query 或新授權。Source36/Controller2 歷史來源不給 app admission；Formal Golden 110/154 obligations 不變。NO_GIT_COMMIT_PUSH_MERGE；runtime/source/physical tests 均 NOT_RUN。

Related M0 records: [Rebaseline](academic-mvp-rebaseline-v0.1.md), [Shared contract](shared-interface-contract-v0.1.md), [Acceptance matrix](m0-acceptance-matrix-v0.1.md).

# Platform capabilities and evidence

This page records bounded evidence, not a universal support guarantee. The source
reference is accepted CAP-F1-5A main
`9e31d8fe9989a0c13478f50082ca2dfc87d430d4`. F1-5A is **COMPLETE / ACCEPTED**.
The onboarding package needs independent review and Lead acceptance; full Layer A
and integrated handoff remain separate F1-5C concerns. Later Gate status belongs
in dated reports, not inferred from this matrix.

## Status and evidence are different

Apply a status to a specific platform, capability, workflow and revision:

| Status | Meaning |
| --- | --- |
| `VERIFIED` | Traceable direct execution establishes the named workflow on that platform. |
| `PARTIALLY VERIFIED` | Direct evidence establishes only the stated subset. |
| `NOT VERIFIED` | No qualifying direct execution for the claim; source/manifests/mocks may exist. |
| `BLOCKED` | A concrete observed obstacle prevents the named capability; record cause, owner and bounded next action. Unattempted tests are not blocked. |

| Evidence type | What it establishes |
| --- | --- |
| `SOURCE_INSPECTED` | Source/command/manifest text was read; not execution success. |
| `STATIC_VALIDATION` | Documentation links, commands and claims were statically checked. |
| `SIMULATED_TEST` | Controlled fixture/mocked logic, including Doctor's WSL2/Darwin classifiers; not a physical-device run. |
| `HOSTED_LINUX` | Ubuntu-hosted execution, limited to its workflow/revision. |
| `NATIVE_EXECUTION` | Direct execution on the identified native platform. |
| `HISTORICAL_ACCEPTANCE` | Previously accepted outcomes, with their date/revision/scope. |
| `NOT CHECKED` | Observation not performed, including unvisited external links or fresh remote state. |

Doctor's `PASS`/`WARN`/`FAIL`/`NOT CHECKED` describe diagnostic properties, not
platform certification. A command printed in a guide has no `LOCAL_EXECUTION`
evidence. Ubuntu results cannot become macOS/WSL2 native results.

## Capability matrix and provenance

Historical accepted Ubuntu x86_64 results at the SHA above are **Quality** and
**real guarded PostgreSQL Integration**, GitHub Actions
[run 38401011335](https://github.com/EricCheng24/pit-research-lab/actions/runs/38401011335).
The Lead supplied the accepted outcomes. Source `.github/workflows/ci.yml` selects
Ubuntu 24.04, Python 3.12.13 x64 and uv 0.11.29. This is **HOSTED_LINUX — HISTORICAL**
and **HISTORICAL_ACCEPTANCE**; no fresh run or live GitHub check was performed for
this documentation package. External links are unvisited / NOT CHECKED here.

Historical WSL2 subsets below come from approved Requirements v1.0's 2026-10-13
snapshot (§7.2): earlier Core development and F1-3/F1-4 guarded operations. They
prove neither Windows edition/hardware nor a fresh F1-5B guide bootstrap.

| Platform / capability | Status | Evidence and limit |
| --- | --- | --- |
| Ubuntu hosted x86_64 Quality at reference SHA | VERIFIED, historical scope | Accepted run 38401011335; no new local/native run. |
| Ubuntu hosted x86_64 real guarded PostgreSQL Integration at reference SHA | VERIFIED, historical scope | Same accepted run; not another OS or workstation proof. |
| Doctor classifier/safety logic versus native execution | NOT VERIFIED for native execution | Accepted deterministic logic tests: SIMULATED_TEST, including mocked Darwin/WSL2; source review is not new test execution. |
| WSL2 Core historical development subset | PARTIALLY VERIFIED, historical | Requirements snapshot; no fresh Doctor/clean-checkout proof. |
| WSL2 guarded DB historical subset | PARTIALLY VERIFIED, historical | Earlier F1-3/F1-4 operations; not the new guide sequence. |
| WSL2 complete new Core guide: Doctor → sync → quality | NOT VERIFIED | Targeted workflow; no current clean-checkout native experiment. |
| WSL2 new prerequisite diagnosis → guarded Test guide | NOT VERIFIED | Historical DB subset is not complete new-guide execution. |
| Native macOS ARM64 complete Core guide | NOT VERIFIED | Source intent/artifacts only. |
| Native macOS ARM64 Doctor | NOT VERIFIED | Darwin process logic/mocks are not native execution. |
| Native macOS ARM64 locked sync | NOT VERIFIED | ARM64 wheel availability is insufficient. |
| Native macOS ARM64 quality checks | NOT VERIFIED | No native Make-free/check execution. |
| Native macOS ARM64 CLI/build | NOT VERIFIED | No native smoke/build execution. |
| Native macOS ARM64 guarded Test PostgreSQL | NOT VERIFIED | Darwin operator branch exists; no native DB run. |
| ARM64 PostgreSQL image runtime | NOT VERIFIED | Accepted image pin/multi-platform intent is not runtime proof. |
| Physical 8 GB Windows/WSL2, Docker-free mode | NOT VERIFIED | No memory/disk/OOM measurements. |
| Physical 8 GB Windows/WSL2, Test-only mode | NOT VERIFIED | No mode-specific measurements. |
| Physical 8 GB Apple Silicon, Docker-free mode | NOT VERIFIED | No measurements. |
| Physical 8 GB Apple Silicon, Test-only mode | NOT VERIFIED | No measurements. |

## Lightweight 8 GB design path

Start with the [Docker-free hub](onboarding.md), then attempt Test-only work only
with separate operator approval and sufficient observed resources. Dev need not
run. Avoid concurrent Dev/Test on constrained devices, and never overlap target
lifecycle/integration operations. No heavy ML/frontend/data prerequisites exist.

Keep the accepted image, Compose, target/port, pool, timeout and retention policies
in the [DB manual](database.md). Existing settings include bounded connections,
64 MB shared_buffers, max_connections 20, 128 MiB shared memory and bounded logs.
These are settings, not total-host/container memory measurements or guarantees.
**8 GB is a design target; actual memory/disk/swap/OOM sufficiency is NOT VERIFIED.**
No universal free-disk/RAM minimum, performance promise or swap/VM/Desktop tuning
is prescribed. If storage or memory pressure interrupts work, pause new actions,
retain files/resources and seek scoped help; do not prune or weaken guards.

## Optional adoption and native records

Layer A engineering/document correctness is mandatory. Layer B contributor
adoption and Layer C direct WSL2/macOS/8 GB experiments are **NON-BLOCKING /
CONTINUOUS**, including F1-5C/F1-6. No member completion quorum or initial setup is
required for acceptance. A discovered mandatory safety/Core defect is escalated
on its substance; missing devices or slow adoption are not such defects.

Use these compact templates in separately authorized dated evidence records.
They do not trigger experiments, DB permission or automated collection.

| Optional Layer B adoption field | Record |
| --- | --- |
| Contributor / package | Alias, source/package SHA, date, platform class. |
| Progress | NOT STARTED / IN PROGRESS / COMPLETED; Core progress; Test can be not requested. |
| Observations | Exact bounded steps, actual exit/test counts if run, redacted failure category and reproducibility. |
| Follow-up | Disposition, limitation, next action and owner; no quorum. |

| Optional Layer C platform field | Record |
| --- | --- |
| Evidence identity | Evidence ID/date/reviewer; exact source and onboarding package SHA. |
| Platform | OS/process/interpreter architecture; Python/uv versions; relevant Docker/Compose/image versions. No unique device IDs. |
| Initial state / scope | Fresh or preconfigured; bounded exact steps; separate Test authorization reference when applicable. |
| Results | Actual exits/nonempty test counts and nonsecret summary; evidence type and status per capability. |
| Resources, if measured | Mode (Docker-free/Test-only), total/available RAM, memory pressure/OOM and disk observations; no invented thresholds. |
| Follow-up | Specific observed obstacle, limitation, safe next action, owner and reviewer. |

Share no `.env` contents, DSNs/passwords/tokens, raw Compose JSON, Docker
environments, private user/network paths, serial numbers or unrelated logs.
Update a capability to BLOCKED only for an observed obstacle; describe the bounded
cause and owner. Native execution can update its own row, never substitute for
another platform or automatically close engineering acceptance.

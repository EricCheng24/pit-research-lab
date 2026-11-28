# F4 D1 synthetic foundation

D1 stores only the two compiled fictional CSV profiles. The entry point has no HTTP transport, real-file profile, or positive IF-07 or PIT classification. `acquire` returns a refusal before opening any config, socket or database. OD-01/OD-02 remain `NOT_GRANTED`. Future official CSV acquisition and OpenAPI acquisition are separate review candidates and have no executable path here.

## Provisioning and trust

Use the IMP01 Owner WSL runtime handoff from the review bundle. The handoff supplies the exact patch pins, private root creation and assigned port arguments, and copies the unchanged pinned F1 lifecycle helper, Compose files and bootstrap into each external target root. This checkout and the external roots must use native Linux filesystems. Python 3.12.13, the existing locked runtime/dev tools, Docker Compose v2 and the local pinned PG 17.11 image are prerequisites. In-image 17.11 clients are used for backup/restore by the Owner. There are no package or image installs in the run.

Everything uses exact numeric loopback, allocated ports, a dedicated `f4d1…` namespace and instance marker, and distinct credentials and volumes. The F1 helper checks translated bootstrap mounts, project labels and ownership, the Windows listener and reserved ranges, and local publication and port availability. A read-only client/version observation does not establish a reachable verified target. No ordinary application client receives daemon access or provisioning credentials.

The external F1 config is private to the local provisioner. Separate D1 0600 files supply exactly one of the admin, migrator, custodian, publisher or reader credentials per selection. D1 rechecks database marker, owner, role attributes, schema ownership and privileges on every new connection. Routine file inputs and profile pins go in the custodian config only. Named task actors are controlled by the Owner. The F1 app has no F4 write grants. The custodian credential can read for replay and scope checks, with no direct writes. The Publisher is a separate, Owner-controlled trusted fixture process with its own secret. Do not give this secret to routine custodian/reader sessions or a worker. Publisher can append only to fixture data tables and cannot write profile authority or mutate existing data. It validates the pinned artifact and exact parser projection inside the custody/SQL lock protocol. Child inserts must match the immutable projection, and a deferred constraint requires all classified rows, expected children and custody receipt at commit. Typed SQL values and their byte digests must agree. Reader inspection and export are unverified diagnostics labelled UNQUALIFIED_FOUNDATION. The reader has SELECT on scoped views only and receives neither the CAS root on their operating-system account nor another role's secret. The local custody owner and trusted provisioning/maintenance programs can see private storage. PostgreSQL superusers and OS administrators are outside this trust boundary.

A single trusted custody lock covers raw publish, recovery, backup and maintenance. The lock order is filesystem before SQL. The database uses bounded statement and lock timeouts. Backup takes database SHARE table locks on the fixed D1 data allowlist; INSERT, UPDATE, DELETE and conflicting DDL cannot race that snapshot even through direct SQL. Only the generated identity advances the observation sequence through the Publisher's table insert. There is no separate writer grant on the sequence. Ordinary app/reader sessions cannot issue D1 writes, and the custodian cannot grant itself authority. Do not issue out-of-band administrative writes while the runtime is running.

PostgreSQL 17 checks explicit `SHARE ROW EXCLUSIVE` locks against a stricter privilege set than the Publisher's `SELECT, INSERT` grants. The verified migrator owns the attempt table and the zero-argument `public.f4_d1_lock_attempt()` function. The function runs as that owner with `search_path = pg_catalog`, locks only `public.f4_d1_attempt` in that mode and returns void. The migration revokes PUBLIC execution in the same transaction. The Publisher gets only EXECUTE on this function with normal fixture grants. Restore-only initialization verifies execution is closed, and restore opens the grant only after complete reconciliation.

Import takes the custody lock before a Publisher transaction begins. Both intent and finalization take the attempt lock as their first F4 SQL operation, before reading profile state, existing attempts or issuer context. Each SQL lock lasts through its own commit or rollback. Recovery reads the existing intent and activity in separate read-only sessions under custody, closes those transactions, and uses the same Publisher finalization lock for a recovered or refused terminal receipt. Existing terminal recovery only reads the sealed receipt and verifies any blob. Profile changes and maintenance take custody and acquire the common table list beginning with attempt. Backup uses SHARE, and restore reconciliation uses ACCESS EXCLUSIVE. The self-conflicting attempt lock serializes Publisher transactions and conflicts with backup SHARE. SHARE also conflicts with the ROW EXCLUSIVE lock that PostgreSQL takes for a direct INSERT, including an insert by the trusted Publisher that never calls the function. All of these checks remain subject to the connection's five-second lock and fifteen-second statement timeouts.

## Operator commands

The Owner handoff drives the full walkthrough on separately verified private roots. In a guarded WSL session, the following commands describe the same product interface. Set the variables to the exact private target files or fixed container IDs recorded by that handoff. No environment DSN, credential argument, URL or service discovery is accepted.

```bash
cd /home/rooki/projects/pit-research-lab-f4-d1
export PYTHONPATH="$PWD/src"
PY=/home/rooki/projects/pit-research-lab-mvp/.venv/bin/python
guarded_source=/tmp/REPLACE_WITH_VERIFIED_OWNER_TARGET
guarded_restore=/tmp/REPLACE_WITH_DIFFERENT_VERIFIED_OWNER_TARGET
expires=$("$PY" -c 'from datetime import UTC, datetime, timedelta; from pit_research_lab.mvp.f4.d1_profile import timestamp; print(timestamp(datetime.now(UTC)+timedelta(days=1)))')
"$PY" -m pit_research_lab.mvp.f4.d1 init --config "$guarded_source/migrator.json" \
  --admin-config "$guarded_source/admin.json" --custodian-config "$guarded_source/custodian.json" \
  --reader-config "$guarded_source/reader.json" --publisher-config "$guarded_source/publisher.json" \
  --profiles-until "$expires"
"$PY" -m pit_research_lab.mvp.f4.d1 schema-current --config "$guarded_source/migrator.json"
issuer_attempt=$("$PY" -c 'from uuid import uuid4; print(uuid4())')
revenue_attempt=$("$PY" -c 'from uuid import uuid4; print(uuid4())')
"$PY" -m pit_research_lab.mvp.f4.d1 import-fixture --config "$guarded_source/custodian.json" \
  --publisher-config "$guarded_source/publisher.json" --profile fixture-issuer-v1 --file issuer_fixture.csv --attempt "$issuer_attempt"
"$PY" -m pit_research_lab.mvp.f4.d1 import-fixture --config "$guarded_source/custodian.json" \
  --publisher-config "$guarded_source/publisher.json" --profile fixture-revenue-v1 --file revenue_fixture.csv --attempt "$revenue_attempt"
"$PY" -m pit_research_lab.mvp.f4.d1 inspect --config "$guarded_source/reader.json"
"$PY" -m pit_research_lab.mvp.f4.d1 verify --config "$guarded_source/migrator.json"
"$PY" -m pit_research_lab.mvp.f4.d1 recover --config "$guarded_source/custodian.json" \
  --publisher-config "$guarded_source/publisher.json" --attempt "$revenue_attempt"
"$PY" -m pit_research_lab.mvp.f4.d1 export-inventory --config "$guarded_source/reader.json" \
  --audience LOCAL_FIXTURE_REVIEW --name fixture-export
# Repeat the actual F1 ownership and identity guards before these operations.
"$PY" -m pit_research_lab.mvp.f4.d1 backup --config "$guarded_source/migrator.json" \
  --container "$verified_source_container_id" --name fixture-backup
"$PY" -m pit_research_lab.mvp.f4.d1 init --restore-only --config "$guarded_restore/migrator.json" \
  --admin-config "$guarded_restore/admin.json" --custodian-config "$guarded_restore/custodian.json" \
  --reader-config "$guarded_restore/reader.json" --publisher-config "$guarded_restore/publisher.json"
"$PY" -m pit_research_lab.mvp.f4.d1 restore --config "$guarded_restore/migrator.json" \
  --container "$verified_restore_container_id" --bundle "$guarded_source/custody/fixture-backup"
"$PY" -m pit_research_lab.mvp.f4.d1 verify --config "$guarded_restore/migrator.json"
"$PY" -m pit_research_lab.mvp.f4.d1 inspect --config "$guarded_restore/reader.json"
```

The root Alembic history stays separate. D1 requires the approved checkout for migration discovery and revision `d1_001`. The installed package exposes the module entry point, while migration files are read from the checkout. No implicit migration, DSN override, offline SQL, downgrade or service startup. Use a temporary fixture issuance window (maximum two days) or explicit `init --revoke <profile>` under the same provisioning and migration authority.

## Content and receipt semantics

Profile and source-file hashes are pinned in the private owner selection. Required closed UTF-8 CSV headers and the fictional namespace are checked before publication. Inputs must be single-link regular files under the private input root. Row ordinals are one-based after the CSV header, and revenue field locators use the exact `amount` header. The in-scope codes `0001` and `0002` are fictional. Bind exact local namespace, stable fictional key and current observed code/name. Conflicts are withheld rather than overwritten or equated historically. Revenue is a dated month interval with explicit fictional currency, unit and basis. Signed decimals use at most 30 integral and eight fractional digits, no float conversion, and preserve numeric zero and a declared missing value separately. Original lexical fields remain available only through authorized raw custody. Report dates and accounting dates are not publication evidence.

Raw artifact SHA-256 covers exact input bytes. Profiles, subjects, versions, receipts and export manifests use domain-separated canonical compact UTF-8 JSON, with sorted keys and closed values. Semantic issuer identity is namespace/key, independent of acquisition UUID or deployment. Repeated values share an assertion version while occurrences and their observation/artifact references remain distinct. A changed value does not infer a revision or release time. Local references use `f4d1:artifact:sha256:<hex>`, `f4d1:observation:<uuid>` and `f4d1:assertion:sha256:<hex>`. Inventory/exports remain `UNQUALIFIED_FOUNDATION`. Stable references do not authorize access or application ingestion.

A pinned import appends intent before reading bytes. Linux no-clobber rename, file/directory fsync and reread synchronize original CAS bytes and the finalized stage. A separate transaction binds the terminal observation, rows, exact versions and occurrences. Use the same UUID to look up a replay. On interruption use `recover` for that exact UUID. A verified finalized stage under a current scope is eligible for recovery; absent stage closes as interrupted; tamper and revoked scope refuse. No invented time, recapture or automatic orphan deletion. Only UTC observation and process/database clock roles are asserted. Exports preserve attribution and unknown status. Trusted integrity verification reparses each verified artifact in observation ordinal order, adding only previously verified issuer occurrences to the parser context. The immutable ordering and exact compiled profile/parser reproduce the original classification without a copy of latest issuer state. The verifier compares all row decisions, typed children, canonical bytes, occurrence links and receipt binding. A digest or row count alone cannot verify provenance.

The guarded Owner-only client subprocess checks the exact full container/image IDs, runtime labels, publication, mount shape, network and in-image 17.11 version. Its fixed dump/restore commands use local PG inside the task container. Passwords cross a private stdin pipe and never appear in arguments. The same backup process retains the filesystem lock, exported database snapshot and DB locks until inventory, fixture blobs and client work are complete. The data-only archive must contain only fixed fixture table data and the identity sequence. Fresh restore starts without ordinary F4 grants. A failed/partial restore remains closed. Restore validates archive/dump digest, exact paths, CAS hashes, schema/constraint digest, recorded rows/semantic digests, sequence and unqualified inventory before releasing ordinary grants. Maintain stopped or failed fixture targets and backups privately until required receipts are secured. Existing F1 destroy-test checks are the only path for later authorized disposal of task-owned volumes.

No E1/HESP, source HTTP, downstream adapter, native replay or role in selected historical evidence originates from D1.

Remediation-1 exercised offline verifier controls only. Actual PostgreSQL migration, role denials, writer serialization and separate-target restore remain pending the reviewed Owner WSL handoff.

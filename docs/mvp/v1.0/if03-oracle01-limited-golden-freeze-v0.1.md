# IF-03 Oracle-01 limited Golden freeze preparation v0.1

Task `MVP-IF-03-ORACLE-01-FREEZE-01`；狀態 `FREEZE01_MATERIALIZED_READY_FOR_INDEPENDENT_INTEGRATION_REVIEW`。此為新fixture保存與review指引，未修訂CAN規範、沒有Codec或ReferenceEnvelope issuance。

Normative base `9ade777ac03052231088a91ef9849c5a506da184`（RATIFY-01 PR #21）；[Shared Interface](shared-interface-contract-v0.1.md) AD01-07 CAN-01..10 L455–474、AD01-08 L475–503、AD01-09 SOURCE-BYTES L505–511、AD01-11 L618–632、RT01-01..05 L666–773，以及 [UX RATIFY-01](ux-adr-01-temporal-execution-contract-v0.1.md) L129–143。RT01 overlay為後來的Owner RATIFIED_EXACT authority；ADOPT歷史proposal labels不覆蓋後來決策。

Shared Interface實測140871 bytes / SHA-256 `66bef5b0bb8240214ec8ea14c3c94c8748e2944270883c56de3ae7f27355428b` / Git blob `d028005f6ac854fc3cde965b562dba4e449159cf`；UX實測23544 bytes / SHA-256 `abb04bba20ce8640c38b2406aa662ae86ff3d6df892343b2e6d780c3073c01db` / blob `96d463c40a49d94e0b206be3851e26063fc6c581`。這些是source integrity/provenance pins，不授予source authentication。

原 authoring task `MVP-IF-03-ORACLE-01` 的immutable ZIP保留於 [fixture subtree](../../../tests/fixtures/mvp_if03/oracle01_v0_1/README.md)。ZIP實測383476 bytes、SHA-256 `b3b74b713dbd43b6ef70f32c6c666c0caf8e5ac08c27d96a2d025cda038bdd34`、409 members、408/408原manifest verified；原archive中 `PENDING_INDEPENDENT_REVIEW` 是歷史狀態，不能改寫。Owner本次chat提供已接受的Independent Review verdict `ORACLE_AUTHORING_ACCEPTED — LIMITED_GOLDEN_FREEZE_ELIGIBLE`，含8/8獨立重建與408/408 integrity；provenance=`CHAT_REVIEW_UNEXPORTED`，無外部署名certificate／精確簽署時間。FREEZE-01另做exact preservation與integration review，不重做authoring或更新archive。

兩層保存：完整原ZIP維持author/negative/resource provenance；另只promote B01..B08的24份exact `.bin`。Repository總計28個ADD-only files：本note、fixture README、FREEZE_MANIFEST、原ZIP與24 binary。原ZIP中其餘56 case不散開加入repo。新manifest是ordinary repository metadata，不是App CanonicalPayload/domain，自己hash僅記外部evidence/Git blob。

|Class|Count|Review overlay|
|---|---:|---|
|VALID_COMPLETE_DOMAIN|8|POSITIVE_BYTES_INDEPENDENTLY_REVIEWED|
|SCALAR_FRAGMENT_EXACT_BYTES|14|EXACT_FRAGMENT_REVIEWED|
|FRAMING_COMPONENT_EXACT_BYTES|4|EXACT_COMPONENT_REVIEWED|
|CONTRACT_REFUSAL_ONLY|21|DOCUMENTARY_REFUSAL_REVIEWED_NOT_EXECUTED|
|RELATIONAL_ASSERTION_ONLY|11|RELATIONAL_SPEC_REVIEWED_NOT_RUNTIME_PROVEN|
|BLOCKED_BY_RESOURCE_SCHEMA|5|BLOCKED|
|DEFERRED_TO_FUTURE_DOMAIN_ORACLE|1|DEFERRED|


八個complete domain positives僅 `SOURCE-BYTES`：profile `typed-json-candidate-v0.1`、D43、S27、P187、FRAME281；exact三fields與LP64BE依CAN-01/02/04/05。Envelope期待的length=187，只是expected evidence。raw BODY hash、FRAME domain digest、fixture-file/ZIP hash與Git blob分別標示，不能代換。

Independent Integration Reviewer須核對exact28-file allowlist、固定HEAD、24份ZIP-member→fixture直接bytes equality、fresh重建P/frame、8/8 SHA/envelope，並檢查new manifest/doc僅documentary overlay。不得執行archive scripts、Native、pytest/make/services/database或Codec，不將documentary拒絕升級為runtime pass。Git workflow待獨立integration review及另授權；目前沒有stage/commit/push/PR/merge。

已知P2：record-depth root-counting convention須澄清才可宣告full max-depth Codec conformance，未影響八組SOURCE-BYTES。NUMERIC_POLICY、TIMEZONE_RULES、F2/F3/F5/EVIDENCE Resources/parents與IF-05/IF-07仍另gate；WU04 diagnostic flags不升級，無Formal CAP-F2/B04權限或實體操作。

`NOT_NATIVE_REPLAY` / `NOT_SOURCE_AUTHENTICATION` / `NOT_PIT_ELIGIBILITY` / `NOT_F2_F3_F5_HANDOFF`。只有content integrity與framed content identity；沒有publisher authentication、PIT admission、policy read或consumer readiness。

整合審查通過與另授權Git保存後，有限accepted immutable state才可稱 `LIMITED_GOLDEN_ORACLE_FROZEN`（eight positives + reviewed exact components）；不是十domain或runtime接受。將來修正需explicit review、新version/pins並保留舊bytes，不可為了Codec通過而原地修改golden values。

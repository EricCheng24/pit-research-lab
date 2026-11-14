# IF-03 Oracle-01 bounded fixture candidate

狀態：`FREEZE_CANDIDATE_READY_FOR_REVIEW`。目前為 FREEZE-01 materialization，Independent Integration Review 尚未完成；沒有宣告 Git merged 或全域 FROZEN。

`positives/B01` 到 `positives/B08` 各只有 `raw_body.bin`、`canonical_payload.bin`、`frame.bin`。這24份binary逐byte複製自同目錄原ZIP；完整expected envelope、hex與手動derivation留在ZIP內各 `vectors/<ID>/`，不是live issued references。

原ZIP `IF03_ORACLE01_Review_Evidence.zip` 實測383476 bytes，SHA-256 `b3b74b713dbd43b6ef70f32c6c666c0caf8e5ac08c27d96a2d025cda038bdd34`；409 members（408 MANIFEST entries + MANIFEST.json）。原ZIP與內部 `PENDING_INDEPENDENT_REVIEW` metadata皆原封保存。Owner在FREEZE-01 chat提供的Independent Review verdict為 `ORACLE_AUTHORING_ACCEPTED — LIMITED_GOLDEN_FREEZE_ELIGIBLE`；記錄為 `CHAT_REVIEW_UNEXPORTED`，沒有捏造signed certificate、reviewer identity或簽署時間。新 `FREEZE_MANIFEST.json` 是獨立status overlay，不改寫舊ZIP。

|Class|Count|Review overlay|
|---|---:|---|
|VALID_COMPLETE_DOMAIN|8|POSITIVE_BYTES_INDEPENDENTLY_REVIEWED|
|SCALAR_FRAGMENT_EXACT_BYTES|14|EXACT_FRAGMENT_REVIEWED|
|FRAMING_COMPONENT_EXACT_BYTES|4|EXACT_COMPONENT_REVIEWED|
|CONTRACT_REFUSAL_ONLY|21|DOCUMENTARY_REFUSAL_REVIEWED_NOT_EXECUTED|
|RELATIONAL_ASSERTION_ONLY|11|RELATIONAL_SPEC_REVIEWED_NOT_RUNTIME_PROVEN|
|BLOCKED_BY_RESOURCE_SCHEMA|5|BLOCKED|
|DEFERRED_TO_FUTURE_DOMAIN_ORACLE|1|DEFERRED|


八個完整positive皆屬 registered `SOURCE-BYTES`；其P為187 bytes、FRAME281 bytes。D為 `PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1`（43 bytes）、schema為 `source-bytes-candidate-v0.1`（27 bytes）、profile為 `typed-json-candidate-v0.1`。P只有body_byte_length、body_sha256、canonical_profile_version；UInt64長度取raw body，body SHA取opaque raw bytes，domain digest取三個LP64BE段組成的FRAME。Envelope length是payload187。B01空body合法不代表P可空；B06 raw ff不得解碼成JSON。B04/B05不Unicode normalize。

可從原ZIP讀 `oracle_scope_register.json`、`oracle_vectors.json`、`vector_case_matrix.json`、`oracle_vector.schema.json`、`vectors/<ID>/expected.json`。例如只讀查閱J02：

```python
from pathlib import Path
from zipfile import ZipFile

archive = Path("tests/fixtures/mvp_if03/oracle01_v0_1/IF03_ORACLE01_Review_Evidence.zip")
with ZipFile(archive) as z:
    print(z.read("vectors/J02/expected.json").decode("utf-8"))
    print(z.read("vectors/J02/nfc_quoted.bin").hex())
```

不要執行任何archived author scripts。未promote的56 cases保持ZIP內可查，拒絕／relational specs未執行；不能稱64 passed conformance tests。Scalar/framing components不是完整App domain。完整Decimal/FixedRatio6、TimeRecord、F2/F3/F5/EVIDENCE domain尚缺reviewed Resource bytes/schema/parents。

獨立驗證：先核對ZIP pin、安全paths、CRC與408/408 MANIFEST；由raw body與ratified三fields自己組P，字節排序與LP64BE使用byte length；逐byte比較ZIP members和direct fixtures，再重算FRAME SHA並核對expected fields。對所有24 binary要求bytes equality，不能只信SHA。FREEZE_MANIFEST是普通JSON repository metadata，沒有App-domain digest，也不含自己SHA；自己的hash由外部integration evidence記錄。

P2：record-depth root-counting convention須澄清才能宣告完整max-depth Codec conformance；八個positive不受影響。IF-05/IF-07、Native Replay、Codec、F2/F3/F5 consumers與Formal CAP-F2均未獲驗收。

限制：`NOT_NATIVE_REPLAY` / `NOT_SOURCE_AUTHENTICATION` / `NOT_PIT_ELIGIBILITY` / `NOT_F2_F3_F5_HANDOFF`。

整合審查通過並經另授權Git workflow後，有限接受才可稱 `LIMITED_GOLDEN_ORACLE_FROZEN`。原ZIP/B bytes採append-only versioning；dispute需新review/version/pin，禁止原地修expected bytes以配合Codec。

Contract/source/provenance見 [limited freeze note](../../../../docs/mvp/v1.0/if03-oracle01-limited-golden-freeze-v0.1.md)。

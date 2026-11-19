# F3-L1 bounded synthetic research runtime v0.1

This is a separately named non-IF03 research experiment, pending independent
review. It grants no App ELIGIBLE state, source authentication, rights or shared
resource issuance. Legacy four-cutoff RV, DENIED/WITHHELD and domain guards are
unchanged. F5 policies, execution, costs and portfolios are outside this runtime.

## Pinned inputs and information boundary

`tests/fixtures/mvp_f3_l1/revenue_growth_panel_v0_1.json` has SHA-256
`8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d`.
The generator uses fixed independent revenue/price Random streams (17/17001),
common daily price shocks and issuer innovations unrelated to revenue. It never
imports the experiment. Bytes were frozen before estimating/scoring. Five
fictitious issuers, 26 reference months, daily session marks, closures, one early
close, a no-session week, one unknown revenue and one original/revised declaration
are included. No price/return is constructed to obtain a desired coefficient.

The F2-owned `research_panel` loader validates fixed original bytes and translates
declarations into the existing synthetic-notice-v1 domain schema. It actually
calls S1/S2/S3 through `evaluate_asof`, including correction notices. Original
publication <= modeled public delivery < decision is required. The exact Native
publication witness in this adapter is the *modeled public delivery declaration*,
not accounting period end, effective time, acquisition or empirical publication
proof. Source-version selection uses declaration-exists markers, never financial
amounts. A selected KNOWN amount then undergoes its own real S1/S2 value binding;
unavailable declarations remain distinct states without a numeric revenue value.
Safe receipts are local content hashes of actual invocation summaries, not Native
reconstruction/IF03 refs. Private raw/evaluator graphs never enter predictions.

The latest available declared reference month and its immediate predecessor form
growth Rm/Rm-1 minus 1. No older convenient pair fallback or imputation. Detached
frozen observations are issued/checked with a process-local integrity seal; that
seal is excluded from semantic bytes. This protects cooperative API use, not
malicious Python with filesystem/reflection privileges. F3 fit/predict accept no
raw panel, source/audit graph or caller-certified eligibility Boolean.

## Fixed protocol

H0: beta=0; H1: beta!=0 in r=alpha+beta*g+error. One OLS intercept/regressor,
train-only centering, descriptive association/OOS assessment. No IID p-values,
CI, rejection of H0, causal, actual TWSE or profitability claim.

96 populated weekly cutoffs derive from declared sessions at 18:00 +08:00;
no-session weeks are not ticks. Horizon is 20 subsequent sessions, using the
latest available start close. Prices are positive unadjusted synthetic marks.
The target becomes available at the maximum of both price-availability times
and 18:00 on the session after the end mark. Outcome reads use inclusive as-of
time (S2 strict comparison is preserved by a separate next-second outcome context).
Labels with availability <= semantic fit are legal; outcome end alone is not.

F1: history t0..47, fit t48 session 17:00, predict t48..71.
F2: history t0..71, fit t72 session 17:00, predict t72..95.
Whole-time issuer assignment, maturity selection and outcome-end purging before
the first test start mark determine actual membership, not a hard-coded purge.
Minimum per fold: 40 training cutoffs/180 rows/3 issuers/nonzero growth variance;
20 scored test cutoffs/80 rows. Invalid declared members reject before fit. Each
fit remains frozen throughout its block. No tuning, seed/window search or
validation-driven method selection. Fold 2 may use now-mature earlier outcomes.
The orchestrator first prepares F1 then F2 (training, fit, label-free prediction,
seal), validates both configured batches, and only then scores F1 followed by F2.
No OOS scorer entry occurs before both seals; any preparation failure prevents
all scoring. This does not prohibit mature historical training-label reads at
F2's own fit cutoff. Scoring cutoff is 2026-02-28T23:59:59+08:00. Wall-clock
execution is separate from semantic clocks. This ordering hardens the capability
boundary; it does not assert that the earlier per-fold loop leaked labels into fit.

All ratios/OLS/residual sums use Fraction. Research numbers are reduced signed
numerator/positive denominator decimal strings, <=4096 digits each, no plus,
leading zeros, negative zero, JSON floats/NaN/Infinity. Display uses Decimal
precision 50, 12 places, ROUND_HALF_EVEN and normalized zero. RMSE is a display
sqrt of exact MSE. MAE/MSE/signed error and training-mean-baseline improvement
are reported per fold and aggregated from residual sums, not average ratios.
Residual variance/range, within-issuer adjacent residual products and actual
overlapping-window pair counts are descriptive dependence diagnostics. Price-mark
tuples contain source ref, version ref, source digest and availability in that order.
Zero baseline SSE is NOT_COMPUTABLE. Weekly overlapping outcomes, common shocks
and repeated monthly releases invalidate an IID interpretation of row count.

## Evidence and replay

`F3_L1_RESEARCH_*_V0.1` envelopes contain only schema/non_if03/payload.
Spec, bindings/safe qualification receipts, folds/training, states, sealed
predictions, scoring targets, result, proposed research handoff and evidence
are deterministic content. Artifact refs hash exact envelope bytes; local
record IDs hash their documented integer/string JSON payloads. They are distinct
from IF03 IDs. Fraction fields have their own closed two-key grammar. Attempt
UUID/wall times/durations/completed stages/first failure are a separate envelope.
The base Git HEAD is labeled separately from actual worktree source/test/doc/lock
hashes. A live experiment does not attest pytest execution. Changes to semantic
inputs/config/code/runtime invalidate identity; output path does not.

From the project root using an existing Python 3.12 environment:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/pit-mvp-f3-l1/venv/bin/python -B -m pit_research_lab.mvp.f3_l1.cli --output-dir /tmp/pit-mvp-f3-l1/run-a
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/pit-mvp-f3-l1/venv/bin/python -B -m pit_research_lab.mvp.f3_l1.cli --output-dir /tmp/pit-mvp-f3-l1/run-b
cmp /tmp/pit-mvp-f3-l1/run-a/evidence.json /tmp/pit-mvp-f3-l1/run-b/evidence.json
```

Use fresh absolute directories outside the checkout. Each process reloads pinned
inputs and independently qualifies, fits, predicts, scores and checks evidence.
All deterministic artifacts must match; attempts must have different UUIDs.
`verify_directory` reconciles on-disk content and internal refs before SUCCEEDED.
Failures preserve only actually completed stages and the first safe reason.
An unfavorable predictive outcome remains a successful execution.

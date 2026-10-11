# Research-first architecture boundary

This is a future target architecture. F1-0 implements only an installable,
pure-Python package and its smoke test; no contracts or domain layers exist yet.

The generic PIT/research foundation will define reusable research contracts and
infrastructure for availability, snapshots, provenance, and reproducible
experiments. Its identity and interfaces must remain independent of a market,
data provider, or finance-specific method.

Finance and quantamental implementations will build on that foundation with
domain-specific data interpretation, features, and research methods. Those
semantics belong in the domain implementation rather than generic contracts.

A TWSE v1 adapter will map exchange/provider-specific inputs into the relevant
contracts. TWSE is a future application of the foundation, not the package
identity or an implicit dependency of generic research infrastructure.

The intended dependency direction is from adapters and domain implementations
toward generic contracts. Generic code must not depend on finance or TWSE code.
The repository is standalone, with no Survivor OS runtime dependency or copied
historical sources. Packaging success establishes no actual PIT guarantees.

See the [bootstrap scope and deferred milestones](../../CAP-F1-0-Repository-Initialization-Requirements.md#5-explicit-non-goals--defer-to-stage)
and [local verification commands](../../README.md#local-setup-and-verification).

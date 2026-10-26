# Release orchestration (release)
> ⛔ Operating instruction: this file is the **human-readable projection** of the release policy. The machine source is `protocol/release_policy.json` (validated against `protocol/schema/release.schema.json`); the machine-checked preflight is check38's `release_gate` sub-scan. Read it and run it.
> 最后更新：2026-10-11 (last updated)

## Reproducible artifacts and provenance

The npm release no longer ends with an unarchived tarball produced by an ad-hoc `npm pack`. A tag
or an explicit attestation run calls `packaging/npm/tools/build_release.py`, builds the same tree
twice, compares every byte, and emits the deterministic tarball, CycloneDX 1.6 and SPDX 3.0
JSON-LD SBOMs, payload manifest, `SHA256SUMS`, release metadata, and a GitHub OIDC
build-provenance attestation. The publish job consumes the tarball from that build job, and the
GitHub Release ships the same tarball, SBOMs, checksums, and metadata.

Consumer commands, supplier policy, and the threat model are in
[supply-chain-security.md](../supply-chain-security.md). The workflow has the hosted build and
authenticated provenance capabilities needed for SLSA Build L2; an L2 evidence claim exists only
for a concrete tag/attestation run that successfully produced and stored the attestation.

## What this solves

Release steps used to live in four places — `nf release` (preflight), the former golden-master snapshot script (retired 2026-10-11), `scripts/bump_verify.sh` (version relabeling) and a manual checklist — while the **order** and the **preconditions** existed only in prose. Two mechanisms from top-tier peers were adopted: **config-as-contract** (policy in `protocol/release_policy.json` + its JSON Schema, like release-please's `$schema` pattern) and **change collection** (`changes/unreleased/*.md`, like changesets).

```bash
python scripts/nf.py release --plan          # ordered plan (command / output / criterion)
python scripts/nf.py release --plan --json   # machine-readable plan
python scripts/nf.py release                 # preflight (= verify + coverage + e2e + report freshness)
python scripts/nf.py release --json          # deterministic evidence manifest (read-only)
python scripts/nf.py release --freeze --apply --by <approver> --note "<wave note>"
                                             # run the freeze chain in order (default is a dry run)
```

## Freeze chain

The order must not be reversed (see `decisions/ADR-0000-决策记录外置到私有仓.md` and the PO-9000 postmortem template): content frozen → conformance report recomputed → content-bound approval → protocol receipts re-signed.

1. `python scripts/nf.py conformance --write` (produces `protocol/conformance_report.json`, must be `conformant`)
2. `nf approve protocol/conformance_report.json --by <approver> --note <note>` (content-bound; invalidated the moment the object changes)
3. `python scripts/nf.py receipts --scope protocol --write` (protocol receipt root + derived faces refreshed)

Receipts must run **last**, after all content changes; otherwise the root covers stale bytes. After changing library content also run `nf library receipts --write`.

## Version faces

Three registrations must not dangle (recompute rules live in `core/quality_baseline.py` and in VERSION-MATRIX's own two-way check):

| Face | Source | Action at release |
|---|---|---|
| `CHANGELOG.md` | latest section `## [X.Y.Z]` | flip "unreleased" to released and record the PASS baseline |
| `docs/meta/VERSION-MATRIX.md` | version × plan × capability row | add a row (version / date-status / plan / capability) |
| `README.md` version block | the "current" row | move the current row to the new version |

`bash verify.sh` is the single gate entry; the expected `PASS` value is a declaration (`quality_baseline.EXPECTED_*`) and is not hand-written here.

## Golden Master (retired)

The former mechanism (tag-time snapshot `.release-frozen/<tag>/sha256.manifest`) was **retired by the author on 2026-10-11**: 77 of its 156 digest lines had gone stale (protocol files changed, the manifest was never recomputed), no gate consumed it, and it once leaked into the npm payload. Both the frozen directory and its generator script are removed from the repository and from the payload exclusion list (the path face no longer carries that directory name). If a reproducible tag-time snapshot is ever needed again, it must ship with a **freshness gate** (a manifest without a judge is exactly the anti-pattern this document warns about).

## Change entries

When a change lands, add one entry under `changes/unreleased/` (`type:` + `note:`, vocabulary identical to `CONTRIBUTING §1`). At release, `nf changelog` **generates** the version section (deterministic; every bullet traces back to an entry or a conventional commit), then `--write` inserts it into the CHANGELOG and archives the entries under `changes/<version>/`:

```bash
python scripts/nf.py changelog --version X.Y.Z --date YYYY-MM-DD          # preview (native equivalent of a release PR)
python scripts/nf.py changelog --version X.Y.Z --date YYYY-MM-DD --write  # insert + archive
```

Rules and rationale: `changes/README.md`; the judge is check38's `release_gate` sub-scan.

## Boundaries (not claimed)

- This mechanism does **not** replace `verify.sh`: a green gate is a precondition, not a quality claim.
- The plan is **orchestration**, not proof: `--apply` only calls the existing commands in order and adds no write semantics.
- `git tag` is performed by a human (this mechanism only gives the command and the criterion) — tagging is irreversible and stays out of the automated surface.

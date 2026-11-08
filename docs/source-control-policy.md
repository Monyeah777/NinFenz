# Source Control Policy

This repository uses GitHub as its Source Control System. The canonical repository
identity is `https://github.com/Monyeah777/NinFenz`; `main` is the protected default
branch and `refs/tags/v*` identifies release tags.

## Protected References

- `main` rejects force pushes and deletion, requires linear history, requires the
  configured status checks, requires conversation resolution, and applies protections
  to administrators.
- Version tags match `refs/tags/v*`. The active tag ruleset rejects deletion, forced
  movement, and updates.
- Pull requests use GitHub's human-readable diff view. `CODEOWNERS` identifies the
  maintainer responsible for protocol, workflow, gate, and core-code changes.

The reviewed platform facts are captured in
`results/supply-chain/github-source-controls.json` and can be recollected with
`python scripts/slsa_source_readiness.py --collect`. CI validates the reviewed snapshot
offline; `--live` is an explicit maintainer action so anonymous API throttling does not
create nondeterministic pull-request failures.

## Safe Expunging

History removal is permitted only to satisfy a legal obligation, a privacy request,
or an equivalent compliance requirement. Routine mistakes are corrected with a new
revision; they do not justify rewriting history.

An expunging request must record the requester, legal basis, affected revisions and
refs, consumer impact, approval by an administrator plus a second trusted person when
one exists, and the resulting audit action. Sensitive request details may remain
private. Public logs must not preserve the expunged content.

Because Git revision ids are content-derived, rewritten descendants receive new ids.
Published artifacts and consumers pinned to old ids must be identified before any
rewrite. A history rewrite is never treated as a routine release or cleanup step.

## Attestation Boundary

SLSA Build provenance describes how an artifact was built. It is not SLSA Source
Provenance. GitHub currently does not expose the Source VSA and Source Provenance
attestations required for a nonzero SLSA Source Track claim, so this repository makes
no such claim. Current rulesets are reported as technical-control readiness only.

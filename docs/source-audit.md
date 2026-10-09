# Source audit and verification record

## Status and provenance

This is a **bounded documentation closeout**, not a completed exhaustive semantic audit or a live-account certification. The user requested the work be wrapped up. The handbook records observed implementation, examples, risks and remaining unknowns without changing bot behavior.

- Source baseline: `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`, maintained upstream `develop`.
- Daemon gitlink: `fbd0fda6ba9019c128926614f9865ba38a67b627`.
- Installed release `3.4.6` is a separate deployment and was not replaced or restarted.
- Changes in this branch are README, contributor/handbook/reference documentation and offline documentation checks only. No account credentials, service configuration or deployment files are included.

## Coverage — indexing is not reading

The [source inventory](reference/source-inventory.json) contains **568 baseline files**, including **271 Go files**. Hashes were checked against the working tree. The original README's baseline hash is retained as provenance and deliberately not compared against its rewritten content.

| Evidence | Recorded depth |
|---|---|
| Parent common/WebUI/helpers/build assets | Complete reads recorded for allocated files |
| Fleet/defender/state workers | 18 assigned files read in full |
| Brain workers/calculation helpers | 14 assigned files read in full |
| Lifecycle/configuration/Telegram | 21 assigned files read in full |
| C# daemon adapter/models/enums | 98 files indexed; targeted semantic inspection, no trustworthy per-file full-read attestation |
| Go daemon/library/parser/extractor/tests | 271 files hashed and symbol-indexed; contributor reports 33 full reads and about 20 partial reads, remainder structural/targeted inspection |

Conservatively, the normalized inventory marks **128 first-party files `read`** and **369 first-party files `indexed`**, plus binary/vendored/generated assets. A daemon contributor's aggregate full-read estimate is not enough to upgrade individual file statuses. This deliberately underclaims rather than treating machine-generated symbol lists as proof of semantic review.

The [settings catalog](reference/settings-catalog.json) has **460 entries**: **15 global** and **445 instance/profile paths**. These include leaves, containers and array schemas, so the count is not the number of independently effective options. Some entries are unused template fields or write-only compatibility fields. Consumer evidence can identify inherited containers or write sites; descriptions and fallback claims still require semantic review. This catalog is a baseline snapshot, not proof that every implementation-only option has been discovered.

## Verification performed

- C# solution Release build succeeded under .NET 10; self-contained `linux-x64` publish succeeded. Existing warnings and ImageSharp security advisories remain.
- Pure helper harness: 14 assertions passed for settings overlays, missing casts versus explicit fallback, first-character normalization, duration parsing and coordinate boundaries.
- Isolated source WebUI: `/`, `/Settings`, `/Logging`, `/Ogame` returned HTTP 200; root redirected to Settings. Settings save/read-back, log retrieval and SignalR negotiation passed.
- UI smoke ran with `Instances: []` and Telegram disabled, and verified no daemon child process or account actions. Live service identity and deployed configuration hashes were unchanged.
- The published-source UI smoke used the release daemon solely as a prerequisite file; it did not start it and is not daemon interoperability evidence.
- Documentation checks validate local links and heading/source-line targets, JSON snippets, template path coverage, referenced source files and baseline hashes. They do not execute game workflows or prove every prose statement.
- Parent independently corrected interval-unit, missing-setting, fleet-speed, storage arithmetic, structural-integrity, static-state and other mistakes; see [targeted review](reference/parent-review.md).

## Reproducible offline checks

From the repository root after initializing the pinned submodule:

```sh
python3 -m unittest discover -s tools -p test_check_docs.py -v
python3 tools/check_docs.py --allow-incomplete-audit
git diff --check
```

The bounded checker must retain `exhaustive_source_audit_complete: false` while the documented gaps remain. It still fails for broken links, absent settings coverage or changed source hashes.

```sh
python3 tools/check_docs.py
```

The strict command intentionally fails on incompletely reviewed first-party files. This is an honest outstanding acceptance criterion, not a hidden green exhaustive audit. A regression test verifies that strict mode fails and the explicit bounded mode preserves the incomplete-audit flag.

## Known blockers and risks — not fixed here

- Pinned `go build ./cmd/ogamed-tbot` fails because the imported internal `buildqueue` package is absent. Its entrypoint also references a hardcoded Windows template path. A shallow clone cannot establish that this code never existed anywhere in upstream history.
- Stock `cmd/ogamed` also fails at this snapshot on missing defender identifiers. Other compiling Go packages are not substitutes for the required daemon target.
- Workflows select an older .NET version than the source requires.
- WebUI file editing lacks built-in authentication. The Telegram handler has no inbound chat/user authorization filter. Daemon network exposure, credentials in process arguments, cookies and certificate-validation behavior need separate security work before public use.
- No live OGame account login, fleet dispatch, cancellation, build, purchase, abandonment or destructive integration tests were performed. No claim of ban safety or reliable fleet preservation is made.
- Remaining semantic work includes per-model Go review, extractor/parser version behavior, tests, wrapper tails and a deeper independent review of the generated settings/API tables. No upstream PR or merge is submitted automatically.

## Findings and evidence

- [Fleet findings](reference/fleet-findings.md)
- [Brain findings](reference/brain-findings.md)
- [Configuration/lifecycle findings](reference/config-lifecycle-findings.md)
- [Daemon findings and depth ledger](reference/daemon-findings.md)
- [Parent review and corrections](reference/parent-review.md)

The original read manifests are preserved beside those findings. Original contributor notes can predate parent corrections; use the current handbook and this status record for final claims.

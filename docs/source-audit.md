# Source audit and verification record

## Status and provenance

**The pinned first-party source review is complete.** The original bounded handbook was published before the user requested completion of the remaining semantic audit. That resumed work is now reconciled into the handbook, with explicit read evidence and independent parent verification. This is source-review completion, **not** a claim of complete daemon buildability, live-account compatibility, bug freedom or production readiness.

- Source baseline: `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`, maintained upstream `develop`.
- Daemon gitlink: `fbd0fda6ba9019c128926614f9865ba38a67b627`.
- Installed release `3.4.6` is a separate deployment and was not replaced or restarted.
- Changes are README, contributor/handbook/reference documentation and offline verification tooling. Production sources, live configuration, credentials and deployment files are unchanged.

## Coverage — indexing is not reading

The [source inventory](reference/source-inventory.json) contains **568 baseline files**: **497 first-party files now marked `read`**, **zero incomplete first-party files**, and 71 binary/vendored/generated assets retained as indexed/excluded from semantic-source completion. All **271 Go files** are covered. The original README baseline hash is retained as provenance rather than compared against the rewritten README.

| Evidence | Recorded depth |
|---|---|
| Common/WebUI/helpers/build assets | Complete reads recorded in original parent allocation |
| Fleet/defender/state | 18 assigned files read in full |
| Brain/calculation helpers | 14 assigned files read in full |
| Lifecycle/configuration/Telegram | 21 assigned files read in full |
| C# daemon adapter/models/enums/project | All 98 directly read by parent; [direct evidence](reference/audit-parent-direct.json), [findings](reference/audit-parent-direct.md) |
| Go constants | Full parent read in the direct evidence above |
| Go command/integration/support packages | 21 files / 6,072 lines directly read by parent; [ledger](reference/audit-go-integration.json), [findings](reference/audit-go-integration.md) |
| Go models/simulator/utilities | 169 files / 13,420 lines read by a parent-model worker; [ledger](reference/audit-models.json), [findings](reference/audit-models.md) |
| Go wrapper/parser/extractors/tests | 80 files / 25,374 lines read by a second parent-model worker; [ledger](reference/audit-go-surface.json), [findings](reference/audit-go-surface.md) |

The resumed work supplies **369 explicit full-read attestations**, each checked against actual source hashes, line counts, complete ranges and substantive semantic notes. Parent review independently sampled high-impact conclusions, reran safe tests and exercised real-library characterization harnesses before promoting worker evidence. Canceled local workers' partial outputs were not accepted as proof. Indexing, fixture execution and complete semantic reading remain distinct evidence levels. Raw sample assets exercised by tests are not automatically counted as manually read source.

The [settings catalog](reference/settings-catalog.json) retains **460 entries**: **15 global** and **445 instance/profile paths**. These include containers and array schemas, not 460 independently effective switches. Template compatibility fields, write-only fields and inherited consumers are identified separately. A complete read of the pinned baseline does not promise every future or dynamically constructed setting is captured by a static catalog.

## Independently observed verification

| Check | Actual result and boundary |
|---|---|
| Strict documentation checker | 568 inventoried, 497 read, zero incomplete first-party files, zero errors; `exhaustive_source_audit_complete: true` |
| Python checker/evidence regressions | 14 tests passed; compilation passed |
| C# Release solution build | Exit 0, 217 existing warnings, zero errors; cached dependencies, no restore |
| C# adapter/model harness | 13 assertions passed using in-memory HTTP; no daemon initialization or account/network actions |
| Go integration harness | 11 assertions passed, including the TLS flag mismatch, fingerprint panics and canceled task admission |
| Go model harness | 50 assertions passed, including simulator input loss, formula ordering, raw JSON units and pointer semantics |
| Go model/helper packages | 181 passing test/subtest events; simulator has no upstream tests |
| Existing device/HTTP/backoff tests | Four tests passed; taskRunner compiled but has zero active tests |
| Parser/extractor packages, host timezone | **Exit 1: 314 passed, one failed** (`v11_15_0/TestExtractEspionageReport`) |
| Same parser/extractor packages with explicit `TZ=America/Los_Angeles` | Exit 0: 315 passed; timezone workaround is not a source fix |
| Constructor-free wrapper allowlist | 18 tests passed; constructor/background machinery tests intentionally excluded |
| Pinned TBot daemon build | **Still fails**: missing internal buildqueue package; offline lookup refusal is not a substitute implementation |
| Stock daemon build | **Still fails**: undefined defenderFlags / wireDefender |
| Installed service | Active, same PID 1167; root UI HTTP 200 after redirect to Settings; no restart or deployed-file edits |

Go checks used project-local Go 1.27.2 with process-local `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off`. Local module replacement and exact CLI dependency v3.1.1 were verified. The wrapper allowlist and timezone-sensitive fixture are detailed in the surface audit. **There is no unqualified whole-suite pass.** Characterizations preserve and demonstrate existing defects; they are not fixes or live-game certification.

Earlier independent checks also built a self-contained Linux C# publish, exercised 14 settings/helper assertions, and ran an isolated account-free WebUI smoke over Settings/Logging/Ogame, settings roundtrip and SignalR. That smoke used a release daemon only as an unstarted prerequisite file; it does not prove interoperability with a source-built daemon.

## Reproducible safe commands

From the repository root with pinned submodule and dependencies available:

```sh
python3 -m compileall -q tools
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/check_docs.py
dotnet run --project tools/adapter-smoke/AdapterSmoke.csproj --configuration Release
(cd tools/go-smoke && go run -mod=readonly .)
(cd tools/go-smoke && go run -mod=readonly ./models)
git diff --check
```

The strict checker is now expected to pass. `--allow-incomplete-audit` remains a deliberate bounded-review option for future partial work, not a way to bypass broken links, changed source hashes or invalid attestations. A regression test still proves that an incompletely reviewed fixture fails strict mode and retains an incomplete flag when explicitly allowed.

Normal restore/run commands may contact dependency sources when caches are absent. See [development](development.md) and individual audit pages for cached-only commands, exact package selection, timeout and timezone requirements. Do not broaden the allowlist into unreviewed account/network tests.

## Remaining implementation blockers and risks — not repaired

- TBot daemon imports absent buildqueue code and references a hardcoded Windows template path. The shallow clone establishes absence at the pin, not all upstream history.
- Stock daemon is also unbuildable. C# build/publish and library tests do not establish a reproducible complete source bundle.
- The CLI TLS flag is declared as a string but read as a boolean; explicit true reads false in the pinned parser. Transport-specific TLS behavior differs across device, proxy and chat clients.
- Action retries can replay mutations; 5xx, malformed payloads, error envelopes and post-action lookups do not reliably distinguish failure from an already-completed action. Manual-mode/cache/transport concurrency is not certified.
- The public simulator omits Reaper/Pathfinder/Crawler inputs; C# and Go price/time/fuel/storage helpers have materially different behavior. See the detailed formula audit rather than assuming game-rule accuracy.
- WebUI configuration editing lacks built-in authentication; Telegram lacks an inbound user/chat authorization filter. Credentials in arguments, cookies, parser brittleness and stale CI/Docker settings require separate hardening work.
- The host-timezone espionage fixture still fails. Existing dependency warnings/advisories remain; no fresh dependency-security approval is claimed.
- No real login, fleet action, cancellation, build, purchase, abandonment, messaging/solver call or live protocol integration was performed. No ban-safety or fleet-preservation guarantee is made. No upstream PR or merge is automatic.

## Historical evidence

Original [fleet](reference/fleet-findings.md), [Brain](reference/brain-findings.md), [configuration/lifecycle](reference/config-lifecycle-findings.md), [daemon](reference/daemon-findings.md) and [parent correction](reference/parent-review.md) records remain available. Their indexing/partial-depth statements describe the original bounded closeout and can predate resumed corrections. The current inventory and resumed ledgers above are authoritative for final coverage. Read evidence is auditable attestation, not machine proof of understanding or complete defect discovery.

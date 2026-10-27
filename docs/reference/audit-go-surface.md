# Direct Go surface semantic audit

## Result and boundaries

**Complete assigned source review:80/80 files,25374/25374 lines.** This is an implementation audit, not a daemon deployment or game-protocol compatibility certificate. The machine-readable [ledger](audit-go-surface.json) records every exact path, SHA-256, line count, full read range, role, substantive behavior notes, findings and test-safety classification. Progress was persisted after each bounded reading batch; indexing and hash validation were not counted as reading.

- Source baseline: `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`.
- OGame pin: `fbd0fda6ba9019c128926614f9865ba38a67b627`.
- Branch: `docs/comprehensive-handbook`; root HEAD observed during tests: `c82835e8ade1493062ed792817842d9402c7ac43` (concurrent documentation work may advance it). All80 assigned source hashes still match the manifests.
- Assignments: `documentation-work/resume-audit/{wrapper-parser,extractors}-assigned.json` outside the source repository. The42 wrapper/parser files cover10991 lines;38 extractor files cover14383 lines.
- Long files were read through their actual ends: wrapper/ogame.go4763, v6/extracts.go2523, v6/extractor_test.go2548. This includes delegation tails, overrides, embedded fixture expectations and commented-out tests. Raw sample HTML/JSON files outside the80 assigned paths were exercised by fixture tests, not separately claimed as manually read in full.
- No production behavior, runtime/test source, shared documentation or source inventory was edited. No wrapper constructor/login, account credentials, game actions, daemon start, install, service restart, additional worker or local-model endpoint was invoked.
- The [parent integration audit](audit-go-integration.md) separately covers command/bootstrap/build blockers, manual-mode shared maps/timers, the CLI enable-tls StringFlag/Bool mismatch and the discarded discovery call. Its11 in-memory characterizations are not this worker's tests. The taskRunner package has zero active tests, not a passing concurrency suite.

## High-impact findings

Severity denotes potential impact of existing behavior, not a claim that a live exploit or game failure was reproduced. Unless a test is explicitly cited, findings below are static conclusions from complete source reads. No bugs were fixed by this audit.

### GS01 — Mutation retries and ambiguous action outcomes (high)

pageContent replays its callback for both GET and POST; payload alteration and URL construction happen before retry. Postprocessing is outside retry. A fleet action can succeed before subsequent lookup fails; a returned error is not proof that no action occurred.

**Documentation/operator implication:** Describe up to10 callback attempts, not10 guaranteed HTTP retries or idempotency; reconcile state before repeating mutations.

Sources: [`ogame/pkg/wrapper/ogame.go:1024–1085`](../../ogame/pkg/wrapper/ogame.go#L1024-L1085); [`ogame/pkg/wrapper/ogame.go:1226–1263`](../../ogame/pkg/wrapper/ogame.go#L1226-L1263); [`ogame/pkg/wrapper/ogame.go:3422–3675`](../../ogame/pkg/wrapper/ogame.go#L3422-L3675).

### GS02 — HTTP5xx can be empty success (high)

execRequest returns empty bytes and nil error for HTTP>=500. Only page-specific logout heuristics can turn that into retryable ErrNotLogged; generic Ajax/mutation paths can propagate empty success.

**Documentation/operator implication:** Transport status, parser success and domain success are distinct; do not promise retry on every5xx.

Sources: [`ogame/pkg/wrapper/ogame.go:943–999`](../../ogame/pkg/wrapper/ogame.go#L943-L999).

### GS03 — Chat TLS bypass differs from proxy TLS handling (high)

Chat polling and websocket skip certificate verification using their own clients. getTransport overwrites helper TLS config with caller config even nil, so proxy helper InsecureSkipVerify initializers alone do not prove actual insecure TLS on the final proxy transport.

**Documentation/operator implication:** Qualify TLS/proxy warnings by transport; chat does not use the configured device/proxy client.

Sources: [`ogame/pkg/wrapper/ogame.go:480–545`](../../ogame/pkg/wrapper/ogame.go#L480-L545); [`ogame/pkg/wrapper/ogame.go:565–607`](../../ogame/pkg/wrapper/ogame.go#L565-L607).

### GS04 — v13 branches fall through to legacy requests (high)

cancelFleet sends v13 recall POST then extracts legacy recall token and GETs. getGalaxyPage parses v13 fetchSolarSystemData into a local value that is discarded before legacy fetchGalaxyContent.

**Documentation/operator implication:** Document implementation branches, not exclusive version-specific protocol compatibility; live v13 interoperability is unverified.

Sources: [`ogame/pkg/wrapper/ogame.go:1655–1682`](../../ogame/pkg/wrapper/ogame.go#L1655-L1682); [`ogame/pkg/wrapper/ogame.go:2711–2757`](../../ogame/pkg/wrapper/ogame.go#L2711-L2757).

### GS05 — Message helper ignores limits and failures (high)

getMessages always asks page1, ignores maxPage/fetch/unmarshal/extractor errors, asserts each message as string, and returns nil error. Wrong JSON message element types panic; failed/missing content can appear empty.

**Documentation/operator implication:** Do not describe full message pagination or a complete empty mailbox; modern summaries return page count1.

Sources: [`ogame/pkg/wrapper/ogame.go:3750–3767`](../../ogame/pkg/wrapper/ogame.go#L3750-L3767); [`ogame/pkg/extractor/v11_15_0/extracts.go:18–135`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L18-L135).

### GS06 — Malformed ship form fields can panic (high)

SendFleet/CheckFleet/JumpGate split ships strings and index second element without length check after accepting a valid ship ID.

**Documentation/operator implication:** Valid-ID-only ships values are unsafe malformed input, not reliably HTTP400; handler/network execution was not needed for this static finding.

Sources: [`ogame/pkg/wrapper/handlers.go:924–955`](../../ogame/pkg/wrapper/handlers.go#L924-L955); [`ogame/pkg/wrapper/handlers.go:1049–1085`](../../ogame/pkg/wrapper/handlers.go#L1049-L1085); [`ogame/pkg/wrapper/handlers.go:1540–1580`](../../ogame/pkg/wrapper/handlers.go#L1540-L1580).

### GS07 — API status/envelope and payload ambiguities (medium)

CancelFleetHandler wraps error as SuccessResp Result; SetUserAgent returns HTTP200 with Code400 error envelope. PageContentHandler puts raw []byte into JSON Result, whose standard encoding is base64, not a plain HTML string.

**Documentation/operator implication:** Reconcile daemon-api set-user-agent, cancel failure and page-content payload descriptions; inspect envelope and domain state as well as HTTP status.

Sources: [`ogame/pkg/wrapper/handlers.go:20–36`](../../ogame/pkg/wrapper/handlers.go#L20-L36); [`ogame/pkg/wrapper/handlers.go:68–93`](../../ogame/pkg/wrapper/handlers.go#L68-L93); [`ogame/pkg/wrapper/handlers.go:309–315`](../../ogame/pkg/wrapper/handlers.go#L309-L315).

### GS08 — HEAD proxy is not a cached-header read (medium)

GetStaticHEADHandler delegates HeadersForPage, which issues an upstream HEAD. Empty response headers cause424; errors400. Static GET buffers upstream bytes and always emits200.

**Documentation/operator implication:** Replace cached-header wording with upstream request semantics and avoid upstream status-preservation claims.

Sources: [`ogame/pkg/wrapper/handlers.go:1255–1299`](../../ogame/pkg/wrapper/handlers.go#L1255-L1299); [`ogame/pkg/wrapper/handlers.go:1329–1350`](../../ogame/pkg/wrapper/handlers.go#L1329-L1350); [`ogame/pkg/wrapper/ogame.go:1938–1972`](../../ogame/pkg/wrapper/ogame.go#L1938-L1972).

### GS09 — Cache and transaction boundaries are narrower than thread-safe labels (medium)

Cached research/lifeform/alliance values can trigger requests on misses and have no TTL. Planet LF methods bypass prioritized public methods. Prioritize nesting requires balanced Done on same handle; raw OGame.Done is no-op and SetInitiator returns nil.

**Documentation/operator implication:** No blanket serialization, freshness, cancellation safety or pure cache-get guarantee. Task runner has zero active tests per parent; selected tests here are not concurrency validation.

Sources: [`ogame/pkg/wrapper/ogame.go:423–470`](../../ogame/pkg/wrapper/ogame.go#L423-L470); [`ogame/pkg/wrapper/ogame.go:2808–2855`](../../ogame/pkg/wrapper/ogame.go#L2808-L2855); [`ogame/pkg/wrapper/planet.go:156–165`](../../ogame/pkg/wrapper/planet.go#L156-L165); [`ogame/pkg/wrapper/prioritize.go:33–75`](../../ogame/pkg/wrapper/prioritize.go#L33-L75); [`ogame/pkg/wrapper/ogame_public_interface.go:109–116`](../../ogame/pkg/wrapper/ogame_public_interface.go#L109-L116).

### GS10 — Login is stateful, fallible and version-selected (medium)

Cookie reuse searches persistent cookies by name. Part2 sets login state before serverData completes; part3 cache/chat setup precedes final completion. Version thresholds end at v7, below7 yields nil; invalid-version callers keep v12 fallback.

**Documentation/operator implication:** Distinguish cookie reuse, credentials fallback, state transition and completed login; version selection is not compatibility certification.

Sources: [`ogame/pkg/wrapper/ogame_login.go:48–158`](../../ogame/pkg/wrapper/ogame_login.go#L48-L158); [`ogame/pkg/wrapper/ogame_login.go:189–318`](../../ogame/pkg/wrapper/ogame_login.go#L189-L318); [`ogame/pkg/wrapper/ogame_login.go:320–327`](../../ogame/pkg/wrapper/ogame_login.go#L320-L327).

### GS11 — Typed pages do not universally validate schema (medium)

Only a subset of full page constructors validates markers. Many adapters pass raw bytes/empty DOM to extractors; resource and level selectors often return zero or empty success on missing fields.

**Documentation/operator implication:** Typed page construction and nil extraction error are not proof that expected schema/game state exists.

Sources: [`ogame/pkg/parser/parser.go:123–217`](../../ogame/pkg/parser/parser.go#L123-L217); [`ogame/pkg/parser/fullPage.go:1–99`](../../ogame/pkg/parser/fullPage.go#L1-L99); [`ogame/pkg/extractor/v9/extracts.go:361–398`](../../ogame/pkg/extractor/v9/extracts.go#L361-L398).

### GS12 — Embedding is not virtual method dispatch (medium)

v6 byte ExtractPreferences calls v6 doc receiver; v11 overrides only doc method. Similar inherited byte adapters keep ancestor implementation unless redefined. v6 interface satisfaction includes explicit panic stubs.

**Documentation/operator implication:** Describe per-method byte/doc overrides, not all versions magically inheriting latest schema behavior; unsupported newer methods may panic.

Sources: [`ogame/pkg/extractor/v6/extractor.go:432–437`](../../ogame/pkg/extractor/v6/extractor.go#L432-L437); [`ogame/pkg/extractor/v6/extractor.go:682–685`](../../ogame/pkg/extractor/v6/extractor.go#L682-L685); [`ogame/pkg/extractor/v11/extractor.go:50–53`](../../ogame/pkg/extractor/v11/extractor.go#L50-L53); [`ogame/pkg/extractor/v6/extractor.go:980–1116`](../../ogame/pkg/extractor/v6/extractor.go#L980-L1116).

### GS13 — Tech JSON misassigns PlasmaTerraformer (medium)

v7.1 tech JSON maps PlasmaTerraformer to Num11112 (the PlanetaryShield building field) rather than a11212 research field.

**Documentation/operator implication:** Do not assert every lifeform numeric-ID mapping is correct; later HTML LF research parser separately uses11212.

Sources: [`ogame/pkg/extractor/v71/extracts.go:294–294`](../../ogame/pkg/extractor/v71/extracts.go#L294-L294); [`ogame/pkg/extractor/v71/extracts.go:500–500`](../../ogame/pkg/extractor/v71/extracts.go#L500-L500); [`ogame/pkg/extractor/v71/extracts.go:551–551`](../../ogame/pkg/extractor/v71/extracts.go#L551-L551).

### GS14 — Malformed extractor schemas can panic or silently zero (high)

Unchecked construction ID/level regexes, relocation type assertions, P16 first-planet indexing, fixed LF slot indexing and percent regex indexing have no malformed-input guard. String galaxy numeric conversion ignores ParseFloat errors.

**Documentation/operator implication:** Document schema brittleness and silent fallback separately from explicit error paths; fixture success does not establish hostile-input resilience.

Sources: [`ogame/pkg/extractor/v9/extracts.go:20–44`](../../ogame/pkg/extractor/v9/extracts.go#L20-L44); [`ogame/pkg/extractor/v9/extracts.go:863–876`](../../ogame/pkg/extractor/v9/extracts.go#L863-L876); [`ogame/pkg/extractor/v10/extracts.go:99–111`](../../ogame/pkg/extractor/v10/extracts.go#L99-L111); [`ogame/pkg/extractor/v10/extracts.go:208–241`](../../ogame/pkg/extractor/v10/extracts.go#L208-L241); [`ogame/pkg/extractor/v11_13_0/extracts.go:29–37`](../../ogame/pkg/extractor/v11_13_0/extracts.go#L29-L37); [`ogame/pkg/extractor/v11_15_0/extracts.go:123–129`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L123-L129).

### GS15 — Modern nested message JSON errors are swallowed (medium)

Spy detail accepts nonzero ID then ignores nested buildings/research/fleet/defense JSON errors despite HasInformation flags, and expedition/combat parse errors also become defaults. Missing phalanx refresh token is empty string nil.

**Documentation/operator implication:** Unknown/missing/invalid fields are not always distinguishable from numeric zero or absent units.

Sources: [`ogame/pkg/extractor/v11_15_0/extracts.go:138–390`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L138-L390); [`ogame/pkg/extractor/v11_15_0/extracts.go:393–456`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L393-L456); [`ogame/pkg/extractor/v11_15_0/extracts.go:595–601`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L595-L601).

### GS16 — Timezone-sensitive fixture fails in host timezone (medium)

TestExtractEspionageReport v11.15 expects14:20:42 in time.Local. On host CDT actual is16:20:42; TZ=America/Los_Angeles makes the full reviewed parser/extractor suite pass. This is environment dependence, not a source fix.

**Documentation/operator implication:** Publish both failed native-zone run and passing explicit-Pacific run; never report unqualified full-suite success.

Sources: [`ogame/pkg/extractor/v11_15_0/extractor_test.go:13–19`](../../ogame/pkg/extractor/v11_15_0/extractor_test.go#L13-L19); [`ogame/pkg/extractor/v11_15_0/extracts.go:158–160`](../../ogame/pkg/extractor/v11_15_0/extracts.go#L158-L160).

## Version dispatch and inheritance contract

Login chooses extractors in descending thresholds: **12.0,11.15,11.13,11.9,11.0,10.4,10.0,9.0,8.7.4,8.0,7.1,7.0**. A valid version below7 returns nil; invalid-version handling outside that helper retains the preselected v12 fallback. v6 remains an embedded implementation/test target, not the dispatch fallback. See [`ogame/pkg/wrapper/ogame_login.go:206–305`](../../ogame/pkg/wrapper/ogame_login.go#L206-L305).

| Layer | Principal local changes; unspecified methods remain ancestors |
|---|---|
| v6 | Legacy HTML selectors, sessions/celestials/queues/galaxy/reports/empire/trader; unsupported newer methods include panic stubs |
| v7 | Technology spans, class/crawler/new ships, flat resource JSON, marketplace and message schemas |
| v7.1 | Nested resource/tech JSON, richer reports/ACS attacks, IPM/production/highscore/DM items/buffs/mobile/recall |
| v8 | Advice-bar vacation/attack block and changed espionage activity selector |
| v8.7.4 | Double-quoted trader/buff tokens, inventory/resources/multiplier JS schemas |
| v9 | Lifeform queues/species buildings/research/slots/artefacts/discoveries, technology details envelope, tooltip resources |
| v10 | Typed galaxy JSON and custom numeric/object-or-list decoders |
| v10.4 | Shared double-quoted general/upgrade/teardown token regex |
| v11 | window.token cancellations, changed lifeform icon/preferences language/jumpgate selectors |
| v11.9 | Production queue, combat footer and auction time/item-ref selectors |
| v11.13 | time[data-end] constructions, new ship countdown, movement timers/data attributes |
| v11.15 | Raw message-data attributes/nested JSON, lifeform bonuses/alliance class/phalanx refresh token |
| v12 | OGameClock, highscore row IDs and onboarding chapters |

This table summarizes local adapters, not universal functionality per version. Go embedding is static method promotion; an inherited byte adapter calls its own concrete receiver's doc implementation unless explicitly redefined. JSON/HTML shape mismatches may error, panic or silently return zero/partial state depending on the method. See GS11–GS15 and per-file notes in the ledger.

## Executed offline verification

Toolchain: project-local `documentation-work/toolchains/go/bin/go`, observed **go1.27.2 linux/amd64**. Commands ran from `/home/kelsier/Projects/TBot/source/ogame`, with `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off`, `-count=1` and explicit `-timeout=90s`. Test source and initialization hooks were reviewed first: parser/extractor tests use local files, goquery and pure extraction; no module init/TestMain hooks were found. Wrapper execution used only the explicit pure allowlist below.

| Run | Actual outcome | Evidence |
|---|---|---|
| Host timezone parser + all extractor packages | Exit1;314 passed,1 failed; no test skips | `surface-tests-local.log` |
| Explicit America/Los_Angeles parser + all extractor packages | Exit0;315 passed,0 failed | `surface-tests-pacific.log` |
| Pure wrapper allowlist | Exit0;18 passed,0 failed | `surface-wrapper-pure.log` |

Counts are parsed top-level test-result events, not estimated symbols. Extractor root, v10 and v104 packages have **no test files**; their package skip events are not tests. Logs are stored under `/home/kelsier/Projects/TBot/documentation-work/resume-audit/`; commands, exits, individual failed test and package outcomes are also recorded in the JSON ledger.

The host-zone failure is `v11_15_0/TestExtractEspionageReport`, extractor_test.go:19: expected `2024-05-23 14:20:42 -0500 CDT`, actual `2024-05-23 16:20:42 -0500 CDT`. The test constructs a hardcoded hour with time.Local, while extraction converts a server-zone instant to local time. Running in the fixture's implicit Pacific environment passes; this records environment dependence, not a production change or an unqualified host-suite success.

### Reproduce safely

```sh
cd /home/kelsier/Projects/TBot/source/ogame
GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off /home/kelsier/Projects/TBot/documentation-work/toolchains/go/bin/go test -json -count=1 -timeout=90s ./pkg/parser ./pkg/extractor/...
TZ=America/Los_Angeles GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off /home/kelsier/Projects/TBot/documentation-work/toolchains/go/bin/go test -json -count=1 -timeout=90s ./pkg/parser ./pkg/extractor/...
GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off /home/kelsier/Projects/TBot/documentation-work/toolchains/go/bin/go test -json -count=1 -timeout=90s ./pkg/wrapper -run '^Test(MoonID_Celestial|Fields_HasFieldAvailable|Temperature_Mean|Planet_String|ConvertIntoCoordinate|ProductionRatio|EnergyNeeded|EnergyProduced|ExtractCargoCapacity|GalaxyDistance|FlightSystemDistance|SystemDistance|PlanetDistance|Distance|CalcFlightTime|FixAttackEvents|Version|SanitizeServerVersion)$'
```

Excluded from wrapper execution: `TestWrapper`, `TestOGame_GetCachedCelestial` and `TestOGame_GetCachedCelestials` instantiate NewNoLogin and start constructor background machinery. `TestExtractFleetsFromEventList` is empty/commented and was deliberately not counted as meaningful verification. Likewise commented v6 notification/resource assertions and the v7.1 researcher report block do not establish coverage. Existing fixture tests commonly discard file/extraction errors; malformed or missing fixture inputs can panic instead of yielding a clean assertion.

**Not verified:** complete daemon builds (parent documents missing buildqueue and stock defender identifiers), live accounts/login/token renewal/chat/proxy behavior, v13 compatibility, action idempotency, race/concurrency correctness, malformed-input fuzz resilience, or production deployment. These commands intentionally exclude constructors and live network behavior; passing them cannot prove those properties.

## Shared-document reconciliation handoff

The following discrepancies were observed against daemon.md and daemon-api.md; shared files are owned by the parent and were not edited here. Source evidence is in the linked finding:

- `docs/daemon-api.md` — **set-user-agent**: HTTP200, Status error/Code400 deprecated; not HTTP400. (GS07).
- `docs/daemon-api.md` — **page-content payload**: Raw []byte in SuccessResp Result encodes as base64 JSON string; not plain HTML string. (GS07).
- `docs/daemon-api.md` — **cancel-fleet failure**: error object is Result in HTTP200 ok envelope; success Result nil does not explain failure handling. (GS07).
- `docs/daemon-api.md` — **check-fleet purity**: No fleet send, but builder/cache lookups can fetch network state; not universally pure computation. (GS09).
- `docs/daemon-api.md` — **static HEAD**: Fresh upstream HEAD request;424 indicates empty returned headers, not missing cached headers. (GS08).
- `docs/daemon.md` — **transport TLS and retry**: Final proxy TLS config overrides insecure helper initializer, whereas chat independently skips verification. Retries do not make mutations idempotent or every5xx retryable. (GS01/GS02/GS03).
- `docs/daemon.md` — **version and cache**: Highest extractor is v12; v13 action branches can fall through. Cache misses may fetch; inherited byte adapters may bypass later doc overrides. (GS04/GS09/GS12).

Model descriptions should distinguish byte-slice/base64 JSON payloads, zero-value versus unknown pointer fields, duration/countdown/epoch fields, permissive numeric decoders and partial-success semantics. The audit describes actual extraction behavior; it does not certify all numeric-ID mappings or client model interoperability.

## Complete source coverage index

All rows below have `status=read`, exact SHA-256 and `read_ranges=[[1,lines]]` in the JSON. The index is navigation, not a substitute for the semantic notes. Path links resolve to the vendored submodule at the pin above.

| Source | Lines | Role |
|---|---:|---|
| [ogame/pkg/extractor/extractor.go](../../ogame/pkg/extractor/extractor.go) | 593 | Extractor capability interfaces and version conformance |
| [ogame/pkg/extractor/v10/extractor.go](../../ogame/pkg/extractor/v10/extractor.go) | 21 | JSON galaxy version adapter |
| [ogame/pkg/extractor/v10/extracts.go](../../ogame/pkg/extractor/v10/extracts.go) | 312 | Typed JSON galaxy decoding |
| [ogame/pkg/extractor/v104/extractor.go](../../ogame/pkg/extractor/v104/extractor.go) | 30 | v10.4 token adapters |
| [ogame/pkg/extractor/v104/extracts.go](../../ogame/pkg/extractor/v104/extracts.go) | 23 | Double-quoted token schema |
| [ogame/pkg/extractor/v11/extractor.go](../../ogame/pkg/extractor/v11/extractor.go) | 53 | v11 resource/cancel/lifeform/preferences overrides |
| [ogame/pkg/extractor/v11/extractor_test.go](../../ogame/pkg/extractor/v11/extractor_test.go) | 31 | Offline galaxy/cancel fixtures |
| [ogame/pkg/extractor/v11/extracts.go](../../ogame/pkg/extractor/v11/extracts.go) | 146 | v11 cancellation tokens and preferences language |
| [ogame/pkg/extractor/v11_13_0/extractor.go](../../ogame/pkg/extractor/v11_13_0/extractor.go) | 63 | v11.13 timers and fleets overrides |
| [ogame/pkg/extractor/v11_13_0/extractor_test.go](../../ogame/pkg/extractor/v11_13_0/extractor_test.go) | 75 | Offline timer and fleet fixtures |
| [ogame/pkg/extractor/v11_13_0/extracts.go](../../ogame/pkg/extractor/v11_13_0/extracts.go) | 166 | HTML time attributes and movement counters |
| [ogame/pkg/extractor/v11_15_0/extractor.go](../../ogame/pkg/extractor/v11_15_0/extractor.go) | 107 | v11.15 message/report/bonus/class adapters |
| [ogame/pkg/extractor/v11_15_0/extractor_test.go](../../ogame/pkg/extractor/v11_15_0/extractor_test.go) | 83 | Offline modern message/bonus fixtures |
| [ogame/pkg/extractor/v11_15_0/extracts.go](../../ogame/pkg/extractor/v11_15_0/extracts.go) | 602 | Raw-message attributes and lifeform bonuses |
| [ogame/pkg/extractor/v11_9_0/extractor.go](../../ogame/pkg/extractor/v11_9_0/extractor.go) | 58 | v11.9 production/combat/auction adapters |
| [ogame/pkg/extractor/v11_9_0/extractor_test.go](../../ogame/pkg/extractor/v11_9_0/extractor_test.go) | 37 | Offline v11.9 fixture suite |
| [ogame/pkg/extractor/v11_9_0/extracts.go](../../ogame/pkg/extractor/v11_9_0/extracts.go) | 182 | v11.9 message footer, production and auction markup |
| [ogame/pkg/extractor/v12_0_0/extractor.go](../../ogame/pkg/extractor/v12_0_0/extractor.go) | 68 | v12 clock/highscore/chapter overrides |
| [ogame/pkg/extractor/v12_0_0/extractor_test.go](../../ogame/pkg/extractor/v12_0_0/extractor_test.go) | 55 | Offline v12 fixtures |
| [ogame/pkg/extractor/v12_0_0/extracts.go](../../ogame/pkg/extractor/v12_0_0/extracts.go) | 123 | v12 markup and onboarding chapter extraction |
| [ogame/pkg/extractor/v6/extractor.go](../../ogame/pkg/extractor/v6/extractor.go) | 1116 | Base extractor state, adapters and unsupported-method stubs |
| [ogame/pkg/extractor/v6/extractor_test.go](../../ogame/pkg/extractor/v6/extractor_test.go) | 2548 | Full legacy extractor fixture suite |
| [ogame/pkg/extractor/v6/extracts.go](../../ogame/pkg/extractor/v6/extracts.go) | 2523 | Legacy full-page, fleet, report, empire and action extraction |
| [ogame/pkg/extractor/v7/extractor.go](../../ogame/pkg/extractor/v7/extractor.go) | 263 | v7 overrides embedding v6 |
| [ogame/pkg/extractor/v7/extractor_test.go](../../ogame/pkg/extractor/v7/extractor_test.go) | 321 | Offline v7 extractor fixture suite |
| [ogame/pkg/extractor/v7/extracts.go](../../ogame/pkg/extractor/v7/extracts.go) | 756 | v7 technology lists, JSON resources and message/construction parsing |
| [ogame/pkg/extractor/v71/extractor.go](../../ogame/pkg/extractor/v71/extractor.go) | 213 | v7.1 overrides embedding v7 |
| [ogame/pkg/extractor/v71/extractor_test.go](../../ogame/pkg/extractor/v71/extractor_test.go) | 351 | Offline v7.1 regression fixtures |
| [ogame/pkg/extractor/v71/extracts.go](../../ogame/pkg/extractor/v71/extracts.go) | 1362 | v7.1 resources/tech schema, report, attack and item extraction |
| [ogame/pkg/extractor/v8/extractor.go](../../ogame/pkg/extractor/v8/extractor.go) | 62 | v8 overrides embedding v7.1 |
| [ogame/pkg/extractor/v8/extractor_test.go](../../ogame/pkg/extractor/v8/extractor_test.go) | 32 | Offline v8 regression fixtures |
| [ogame/pkg/extractor/v8/extracts.go](../../ogame/pkg/extractor/v8/extracts.go) | 351 | v8 advice and espionage report selectors |
| [ogame/pkg/extractor/v874/extractor.go](../../ogame/pkg/extractor/v874/extractor.go) | 55 | v8.7.4 adapters |
| [ogame/pkg/extractor/v874/extractor_test.go](../../ogame/pkg/extractor/v874/extractor_test.go) | 20 | Offline trader fixtures |
| [ogame/pkg/extractor/v874/extracts.go](../../ogame/pkg/extractor/v874/extracts.go) | 152 | Trader and item JS schema update |
| [ogame/pkg/extractor/v9/extractor.go](../../ogame/pkg/extractor/v9/extractor.go) | 210 | Lifeform-era extraction adapters |
| [ogame/pkg/extractor/v9/extractor_test.go](../../ogame/pkg/extractor/v9/extractor_test.go) | 282 | Offline v9 lifeform fixtures |
| [ogame/pkg/extractor/v9/extracts.go](../../ogame/pkg/extractor/v9/extracts.go) | 938 | Lifeform structures, queues and resource/tooltips |
| [ogame/pkg/parser/allianceOverviewTabAjaxPage.go](../../ogame/pkg/parser/allianceOverviewTabAjaxPage.go) | 25 | Alliance component JSON shape |
| [ogame/pkg/parser/defensesPage.go](../../ogame/pkg/parser/defensesPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/eventListAjaxPage.go](../../ogame/pkg/parser/eventListAjaxPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/facilitiesPage.go](../../ogame/pkg/parser/facilitiesPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/fetchTechsAjaxPage.go](../../ogame/pkg/parser/fetchTechsAjaxPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/fleetDispatchPage.go](../../ogame/pkg/parser/fleetDispatchPage.go) | 15 | Typed page/extractor adapter |
| [ogame/pkg/parser/fullPage.go](../../ogame/pkg/parser/fullPage.go) | 99 | Shared full-page extraction facade |
| [ogame/pkg/parser/fullPage_test.go](../../ogame/pkg/parser/fullPage_test.go) | 34 | Offline celestial selector fixture test |
| [ogame/pkg/parser/jumpGateAjaxPage.go](../../ogame/pkg/parser/jumpGateAjaxPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/lfBonusesPage.go](../../ogame/pkg/parser/lfBonusesPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/lfbuildingsPage.go](../../ogame/pkg/parser/lfbuildingsPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/lftechsPage.go](../../ogame/pkg/parser/lftechsPage.go) | 15 | Typed page/extractor adapter |
| [ogame/pkg/parser/missileAttackLayerAjaxPage.go](../../ogame/pkg/parser/missileAttackLayerAjaxPage.go) | 5 | Typed page/extractor adapter |
| [ogame/pkg/parser/movementPage.go](../../ogame/pkg/parser/movementPage.go) | 15 | Typed page/extractor adapter |
| [ogame/pkg/parser/overviewPage.go](../../ogame/pkg/parser/overviewPage.go) | 33 | Typed page/extractor adapter |
| [ogame/pkg/parser/parser.go](../../ogame/pkg/parser/parser.go) | 217 | Generic typed page dispatch and lazy HTML document |
| [ogame/pkg/parser/parser_test.go](../../ogame/pkg/parser/parser_test.go) | 34 | Offline parser fixture tests |
| [ogame/pkg/parser/phalanxAjaxPage.go](../../ogame/pkg/parser/phalanxAjaxPage.go) | 11 | Typed page/extractor adapter |
| [ogame/pkg/parser/preferencesPage.go](../../ogame/pkg/parser/preferencesPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/researchPage.go](../../ogame/pkg/parser/researchPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/resourcesSettingsPage.go](../../ogame/pkg/parser/resourcesSettingsPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/parser/rocketlayerAjaxPage.go](../../ogame/pkg/parser/rocketlayerAjaxPage.go) | 5 | Typed page/extractor adapter |
| [ogame/pkg/parser/shipyardPage.go](../../ogame/pkg/parser/shipyardPage.go) | 11 | Typed page/extractor adapter |
| [ogame/pkg/parser/suppliesPage.go](../../ogame/pkg/parser/suppliesPage.go) | 7 | Typed page/extractor adapter |
| [ogame/pkg/wrapper/fetcher.go](../../ogame/pkg/wrapper/fetcher.go) | 137 | Typed game page request mapping |
| [ogame/pkg/wrapper/fleetBuilder.go](../../ogame/pkg/wrapper/fleetBuilder.go) | 322 | Fluent fleet sending and estimate builder |
| [ogame/pkg/wrapper/handlers.go](../../ogame/pkg/wrapper/handlers.go) | 1704 | Echo HTTP envelope, parameter validation and proxy adapters |
| [ogame/pkg/wrapper/interfaces.go](../../ogame/pkg/wrapper/interfaces.go) | 256 | Wrapper, Prioritizable and Celestial API contracts |
| [ogame/pkg/wrapper/log.go](../../ogame/pkg/wrapper/log.go) | 66 | Wrapper logger and quiet switch |
| [ogame/pkg/wrapper/moon.go](../../ogame/pkg/wrapper/moon.go) | 154 | Moon-bound wrapper conveniences |
| [ogame/pkg/wrapper/moon_test.go](../../ogame/pkg/wrapper/moon_test.go) | 12 | Pure moon ID conversion test |
| [ogame/pkg/wrapper/ogame.go](../../ogame/pkg/wrapper/ogame.go) | 4763 | Wrapper core state, transport, retry, cache and account actions |
| [ogame/pkg/wrapper/ogame_login.go](../../ogame/pkg/wrapper/ogame_login.go) | 327 | Login token/cookie fallback, extractor dispatch and chat startup |
| [ogame/pkg/wrapper/ogame_public_interface.go](../../ogame/pkg/wrapper/ogame_public_interface.go) | 976 | Public wrapper routing and direct cache/config methods |
| [ogame/pkg/wrapper/ogame_test.go](../../ogame/pkg/wrapper/ogame_test.go) | 350 | Wrapper offline calculations, sample parsing and constructor tests |
| [ogame/pkg/wrapper/planet.go](../../ogame/pkg/wrapper/planet.go) | 169 | Planet-bound wrapper conveniences |
| [ogame/pkg/wrapper/planet_test.go](../../ogame/pkg/wrapper/planet_test.go) | 22 | Pure planet/model helper tests |
| [ogame/pkg/wrapper/prioritize.go](../../ogame/pkg/wrapper/prioritize.go) | 928 | Serialized action handle and nested transaction counter |
| [ogame/pkg/wrapper/shipsInfos.go](../../ogame/pkg/wrapper/shipsInfos.go) | 56 | Wrapper-aware ship calculations |
| [ogame/pkg/wrapper/utils.go](../../ogame/pkg/wrapper/utils.go) | 71 | Coordinate/celestial conversion and mission speed selection |
| [ogame/pkg/wrapper/utils_test.go](../../ogame/pkg/wrapper/utils_test.go) | 17 | Pure coordinate conversion tests |
| [ogame/pkg/wrapper/wrapper.go](../../ogame/pkg/wrapper/wrapper.go) | 65 | Per-request wrapper options |

Coverage was programmatically checked against both assignments:80 unique paths,25374 lines, no missing/extra files, exact hashes and full ranges. Source-review completion does not imply completion of the parent handbook or unqualified test-suite success.

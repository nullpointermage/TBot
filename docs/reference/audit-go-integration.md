# Direct parent audit: Go integration and support packages

## Scope and evidence

The parent read all **21 Go files / 6,072 lines** in the original integration assignment: both daemon entrypoints, the C bridge and CLI, fork handlers/extractors/solver, device fingerprinting, Gameforge client/solvers, HTTP client, task runner and their tests. The [ledger](audit-go-integration.json) records exact pinned-source hashes, complete ranges and substantive per-file notes. Together with the [98-file C# review](audit-parent-direct.md), this completes the original integration assignment, **not the whole Go audit**.

No production implementation or submodule files were changed. Startup, authentication, accounts, fleet actions, purchases and hosted solver/messaging calls were deliberately not invoked. Offline fixtures demonstrate existing defects; a passing characterization does not mean those defects were repaired.

## Source-proven findings

All paths below are relative to the pinned `ogame` submodule.

| Finding | Source | Verification / significance |
|---|---|---|
| **The TLS flag is not reliably enabling TLS** | `cmd/ogamed-tbot/main.go:130–146,246,522–527`; same declaration/read in stock main | Declared as `StringFlag` but read with `Bool`. An offline probe using the exact pinned urfave/cli version shows `--enable-tls=true` is stored as string `true` while `Bool` returns false. Do not advertise this flag as a working encryption boundary. No daemon/server was launched. |
| Optional Basic auth needs both fields | `cmd/ogamed-tbot/main.go:361–371` | Source only. Supplying just one field leaves middleware disabled. The daemon also registers state-changing GETs; method names are not safety guarantees. |
| Manual mode has unsynchronized shared state and incomplete timer cancellation | `cmd/ogamed-tbot/handlers.go:18–37,63–118,321–329` | Shared maps have no local lock; stopping the timer does not notify the goroutine waiting on its channel. The timer starts before acquiring the named transaction. These are source observations, not a reproduced concurrency test or reliable pause/resume guarantee. |
| Browser proxy can conceal upstream failures | `cmd/ogamed-tbot/handlers.go:78–88,102–118,145–190` | Page errors are discarded; page/static endpoints return HTTP 200 after fetching rather than preserving upstream status. Static data is buffered, not streamed. It advertises gzip/deflate/br but the custom client explicitly decodes only gzip. |
| Discovery-count endpoint makes an extra call | `cmd/ogamed-tbot/handlers.go:390–434` | Calls `GetAvailableDiscoveries()` before validating the planet, discards that result/error, then calls again with options. System-discovery handler parses position but passes only galaxy/system (`:343–385`). No discovery action/request was executed. |
| Fork lifeform parser is a partial positional projection | `cmd/ogamed-tbot/extracts.go:14–27,59–126` | Handles only ships and cost/time categories, reads positional text children, ignores float parse failures, and rounds to thousandths before converting percent to fraction. Empty/mismatched markup can quietly produce zero/empty maps. |
| Stored fingerprint is an array, not a named-property JSON object | `pkg/device/device.go:222–244,495–538` | Custom marshaler emits version-dependent positional arrays. Files are written with mode 0644 under directories created with 0755 (`:371–391`); ordinary file permissions are not a secret store. No real profile was loaded or written. |
| Malformed fingerprints can panic; legacy V8 roundtrip is inconsistent | `pkg/device/device.go:1029–1116,1119–1275` | Offline fixtures reproduce empty/short-array indexing panics, empty encrypt/decrypt panics, and rejection of V8 marshaler output by its parser. Existing encryption-only fixture tests do not cover that struct roundtrip. |
| Fresh device choice tables are incomplete | `pkg/device/device.go:247–329,599–936` | Some OS/browser combinations require explicitly supplied values that random defaults cannot populate. A selectable CLI OS/browser is not proof fresh construction succeeds for every combination. A successfully loaded persisted fingerprint bypasses fresh generation and wins over changed flags. |
| Gameforge response validation is uneven | `pkg/gameforge/gameforge.go:235–246,613–667,995–1016` | In-memory fixtures show an HTTP 500 account response with `[]` is accepted, and an HTTP 201 login body `null` panics on the subsequent token dereference. No actual credentials or lobby requests were used. |
| Account-selection helper does not itself reject blocked accounts | `pkg/gameforge/gameforge.go:1243–1264` | It maps `ba` to `yu`, matches exact server/language and optional player ID, but does not inspect `Blocked`. A higher wrapper must apply that policy; do not attribute it to this helper. |
| Extra library account operations are not daemon features | `pkg/gameforge/gameforge.go:251–328,1095–1230` | Registration, validation, adding accounts, redeeming, gifting/revoking and sitting-code creation exist in the library. This is not evidence that TBot exposes or safely invokes all of them. Revocation hardcodes language `en` and omits response-body close (`:1153–1170`). Not exercised. |
| Hosted solver answer bounds are not enforced | `pkg/gameforge/solvers/solvers.go:83–136`; fork `cmd/ogamed-tbot/tbot-solver.go:38–67` | In-memory Ninja response with answer 99 is returned successfully. The fork adapter has the same unchecked answer projection. External adapters use `http.DefaultClient` and caller context, not the custom client's timeout automatically. No solver service was contacted. |
| Library human solvers have distinct boundaries | `pkg/gameforge/solvers/solvers.go:22–81,139–167`; `discord.go:23–76,116–145` | Manual writes files and blocks on stdin without observing context; Telegram matches MessageID without an explicit user/chat match; Discord does not bind callbacks to a specific message/channel/user. No real messaging, file-writing solver or interactive prompt was invoked. |
| Task runner does not establish unconditional cancellation/serialization safety | `pkg/taskRunner/taskRunner.go:69–123` | In-memory pre-canceled-context fixture still receives a newly created task. Enqueue lacks a cancellation select. The scheduler waits for callers' done channels; two admission goroutines are not a dedicated worker executing arbitrary code. |
| Queue overview is not total outstanding work | `pkg/taskRunner/taskRunner.go:126–152`; `priorityQueue.go:22–35` | Snapshot counts heap items, not the currently executing task or channel buffers. Equal priorities have no explicit FIFO tiebreaker. |
| HTTP transport swap is not isolation for ordinary concurrent requests | `pkg/httpclient/client.go:118–168` | Writers lock transport changes, but ordinary requests do not acquire that mutex. Offline fixture proves temporary transport use/restoration only, not race freedom. |
| C and CLI targets have a narrower/older contract | `cmd/c/main.go`; `cmd/cli/main.go` | C bridge uses one global bot, narrows values to `C.int`, allocates C strings and includes empty/commented TODO exports. CLI ignores some errors and indexes the first planet without checking length. Neither was launched; compiling a target does not prove account operations or C ABI interoperability. |

## Offline verification

From the repository root, after initializing the pinned submodule and obtaining dependencies:

```sh
(cd tools/go-smoke && go run -mod=readonly .)
(cd ogame && go test -timeout 20s ./pkg/device ./pkg/httpclient ./pkg/exponentialBackoff ./pkg/taskRunner)
```

**Observed with project-local Go 1.27.2:**

- **11 characterization assertions passed** in the [Go harness](../../tools/go-smoke/main.go), using the real local library through the [module replacement](../../tools/go-smoke/go.mod). Every request is intercepted in memory; it does not construct a persistent device or start a daemon/socket/account session.
- **Four existing Go tests passed:** one device fixture, two HTTP-client fixtures and one fake-clock backoff test. The task-runner package compiled but has **zero active tests**: its demonstration test is commented out. Do not count that package as a passing concurrency suite.
- Runs used `GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off` with cached dependencies. Those environment values were process-local, not global shell changes. They disable fetching/checksum-server lookup, not source review or pin checking. Normal commands above may access dependency sources when caches are missing.
- The separate [C# harness](../../tools/adapter-smoke/Program.cs) and Python evidence/checker tests remain distinct verification layers. None proves working daemon compilation, login, game-version compatibility, ban safety or fleet preservation.

The pinned daemon build blockers remain unchanged. Remaining wrapper/model/extractor findings must be reviewed separately; this ledger is not a substitute for those reads.

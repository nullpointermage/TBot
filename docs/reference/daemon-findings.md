# daemon-integration findings & read-coverage ledger (final)

Status: CLOSED for this engagement (wrap-up per parent; no further audit expansion).
No source, submodule, branch or runtime state was modified; only files under
`/home/kelsier/Projects/TBot/documentation-work/` were written.

## Deliverables produced

- `docs/daemon.md` — daemon target/build/flags/env, process model, login/session/storage/device/
    proxy/captcha/version-dispatch, transport & retry, risks. Build blocker documented (§1–2).
- `docs/daemon-api.md` — full implemented HTTP surface (route tables, params, errors, effects),
    fork-vs-stock matrix, client-side quirks.
- `docs/infrastructure-models.md` — every assigned C# model/enum: shape, consumer, units,
    transport-only marks, known bugs.
- `daemon-integration-read.json` — 98 assigned C# files: path, sha256, line count, types,
    public members (script-extracted, verified 98/98).
- `ogame-read.json` — 271 tracked `.go` files (submodule-relative paths): path, sha256, lines,
    funcs/types/consts/vars (verified 271/271 vs `git ls-files '*.go'`).

## Build verification (read-only, toolchain `documentation-work/toolchains/go/bin/go`, go1.27.2)

- `go build ./cmd/ogamed-tbot` FAIL: missing `cmd/ogamed-tbot/buildqueue` package
    (imported main.go:12; never committed — `git log --all -- …buildqueue` empty; clone shallow
    depth=1, but pin fbd0fda == upstream `refs/heads/develop-ogamed-tbot` tip per `git ls-remote`,
    so nothing newer exists at the pin).
- `go build ./cmd/ogamed` FAIL: `defenderFlags` (main.go:162), `wireDefender` (:266) undefined;
    no definition anywhere in tree.
- `go build ./pkg/...` and root package OK; `./cmd/c`, `./cmd/cli` OK (network for deps).
- Runtime blocker #2 (even if buildqueue existed): `cmd/ogamed-tbot/main.go start()` reads
    `D:\TBot\develop-ogamed-tbot\cmd\ogamed-tbot\buildqueue\build_queue.gohtml` — hardcoded
    Windows path -> `log.Fatal` on Linux. buildqueue would provide
    `NewBoltStore(<user>-<universe>-<lang>-queues.db)` + `NewHandler(bot,tmpl,store)` and routes
    `GET /build-queue`, `POST /build-queue/queue[/ :uid]`, `PUT/DELETE /build-queue/queue`,
    `POST /build-queue/execute`.
- Env-var quirks: `OGAMED_DEVICHEIGHT` (sic) for `--device-height`; `--tls-key-file`←
    `OGAMED_TLS_CERTFILE` and `--tls-cert-file`←`OGAMED_TLS_KEYFILE` (swapped); `--enable-tls`
    StringFlag parsed via `c.Bool`; `--nja-api-key`←`NJA_API_KEY` selects the obot.de solver.
- Basic auth only when BOTH `--basic-auth-username/-password` set (constant-time compare); daemon
    binds `0.0.0.0` per TBot's hardcoded arg while the C# client targets 127.0.0.1.
- Single global bot instance despite `botMap` plumbing; `AddNewAccount()` (Chrome/144 hardcoded
    UA) unreachable from routes; version/commit/date need `-ldflags`, else `0.0.0/""/""`.

## Honest read-coverage matrix (Go: 271 files / 45,236 lines)

| Area | Files | Depth |
|---|---|---|
| all `cmd/*` mains + ogamed-tbot helpers | 8 | full line-by-line |
| `pkg/wrapper` core: ogame.go, ogame_login.go, handlers.go, interfaces.go, fetcher.go, wrapper.go, log.go, utils.go, shipsInfos.go; prioritize.go (head+pattern), fleetBuilder.go (head+signatures) | 12 | full / near-full; prioritize tail & fleetBuilder tail are same-pattern begin/done wrappers verified via symbol manifest |
| `pkg/wrapper/ogame_public_interface.go`, `moon.go`, `planet.go` | 3 | signatures + spot checks (thin delegation) |
| `pkg/wrapper/*_test.go` | 6 | not read (fixtures; in manifest) |
| `pkg/httpclient`, `pkg/exponentialBackoff`, `pkg/taskRunner/*`, `pkg/device/device.go` core (fingerprint random tables pattern-verified), `pkg/gameforge/gameforge.go`, `solvers/solvers.go` | 9 | full / core sections |
| `pkg/gameforge/solvers/discord.go` | 1 | signature-level (unused by daemons) |
| `pkg/ogame/*` | 167 | manifest + targeted reads (`attackEvent.go`, json-tag survey); structs mirror documented C# models; per-file semantic read NOT performed |
| `pkg/extractor/*` | 43 | dispatch (`getExtractorFor`) fully read; per-version extract bodies not read (HTML selector variants) |
| `pkg/parser/*` | 25 | call-site usage + manifest only |
| `pkg/utils`, `pkg/simulator`, root `ogame.go` | 3 | manifest / header only |

**Precise claim:** all 271 files hashed + symbol-indexed; 33 read line-by-line in full, ~20 in
large part, remainder verified structurally with targeted reads. No tests run; no live game
calls; only `git ls-remote`/`go build` compile checks.

## Open items handed to parent

1. Parent owns build evidence: the two failing daemon targets; fixing requires adding files
    (buildqueue pkg / defender helpers) — intentionally not done.
2. Evidence JSON manifests are machine-generated; re-verify any sha256 (`sha256sum`) before
    trusting in the publish pipeline.
3. Code bugs reported only (docs/infrastructure-models.md §7, docs/daemon.md §6): SetUserAgent
    400-stub, GetTbotIP relative-Uri bug, send-ipm route/param mismatch, Defences.Remove,
    Ships.GetMovableShips mutation, Celestials.DeepSpace 4-vs-3, Settings.EconomySpeed int vs
    "x8" string, ServerData missing FleetIgnore* fields, dead `_cookiesPath`.
4. Resume points if ever reopened: pkg/ogame per-model audit, extractor per-version diffs,
    wrapper tests, prioritize.go tail, discord solver.

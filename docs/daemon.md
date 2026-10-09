# Daemon (ogamed / ogamed-tbot) — Integration Handbook

Scope: the Go daemon submodule pinned at `ogame fbd0fda6ba9019c128926614f9865ba38a67b627`
(upstream `github.com/alaingilbert/ogame`, branch `develop-ogamed-tbot`; the pin **is** that branch's
tip, verified via `git ls-remote`), how TBot launches and talks to it, and every operational
property that can be asserted from source. The complete HTTP surface is in
[`daemon-api.md`](daemon-api.md); the C# models are in [`infrastructure-models.md`](infrastructure-models.md).

All paths below are submodule-relative (`ogame/...`) unless prefixed `TBot.Ogame.Infrastructure/`.

---

## 1. Executable targets

`go.mod`: module `github.com/alaingilbert/ogame`, `go 1.23.0`, `toolchain go1.23.1`.

| Target | Source | Status at pin fbd0fda | Notes |
|---|---|---|---|
| `./cmd/ogamed-tbot` | `cmd/ogamed-tbot/{main,handlers,extracts,LfBonuses,tbot-solver}.go` | **BUILD FAILS** — see §2 | the TBot fork daemon; intended production target |
| `./cmd/ogamed` | `cmd/ogamed/main.go` | **BUILD FAILS** (`defenderFlags` undefined main.go:162, `wireDefender` :266; no definition exists anywhere in the tree) | upstream stock daemon with a half-landed "defender" feature |
| `./cmd/c` | `cmd/c/main.go` | builds | cgo-shared-library export of a subset of wrapper ops (`//export OGame`, `SendFleet`, …); `main(){}` — build with `go build -buildmode=c-shared` for a real artifact |
| `./cmd/cli` | `cmd/cli/main.go` | builds | interactive ishell demo (`Planet`, `Planets`, `Player`, `IsUnderAttack`, `GetResources`); env `UNIVERSE/USERNAME/PASSWORD/LANGUAGE` |
| `./pkg/...`, root package `ogame` | — | build OK | library only |

Verified with the read-only toolchain `documentation-work/toolchains/go/bin/go` (go1.27.2
linux/amd64); `go build ./pkg/...` and the root package compile clean, both daemon cmds fail as
described. The submodule working tree is clean at the pin (no untracked buildqueue dir); the clone
is depth-1 (`git rev-list --count HEAD` = 1), no tags fetched locally.

### 2. Build blocker, honestly stated

`cmd/ogamed-tbot/main.go:12` imports `github.com/alaingilbert/ogame/cmd/ogamed-tbot/buildqueue`,
but no `buildqueue` directory is tracked or present:

```
cmd/ogamed-tbot/main.go:12:2: no required module provides package
  github.com/alaingilbert/ogame/cmd/ogamed-tbot/buildqueue
```

`git log --all -- cmd/ogamed-tbot/buildqueue` is empty in this shallow clone. This establishes that the package is missing at the pinned snapshot, not that it never existed in all upstream history. What the daemon needs from
it (from the sole use site, `main.go:491–509`):

- `buildqueue.NewBoltStore(name)` — bbolt-backed persistence, filename `<username>-<universe>-<language>-queues.db`
- `buildqueue.NewHandler(bot, tmplString, store)` — HTTP handlers `.Page/.QueueAdd/.QueueRemove/.QueueReorder/.QueueClear/.Execute`
- a Go html/template `build_queue.gohtml` read from **`D:\TBot\develop-ogamed-tbot\cmd\ogamed-tbot\buildqueue\build_queue.gohtml`** — a hardcoded Windows path (`os.ReadFile` + `log.Fatal` in `start()`), which would also break Linux runtime even if the package existed.

Routes it would have registered: `GET /build-queue`, `POST /build-queue/queue`,
`POST /build-queue/queue/:uid` (remove), `PUT /build-queue/queue` (reorder),
`DELETE /build-queue/queue` (clear), `POST /build-queue/execute`.

**Consequences for the parent's build:** `go build ./cmd/ogamed-tbot` cannot succeed at the pin
without adding files/deps — out of scope here (no code changes made). The **deployed 3.4.6-era
daemon binary** may be used only as an isolated, UI-only smoke-test companion (prerequisite file
next to the TBot publish output); it must not be documented as "the build of develop
fbd0fda". `cmd/ogamed` is also broken at this snapshot (missing `defenderFlags`/`wireDefender`), so there is no second buildable daemon target here; only the
library and `cmd/c`/`cmd/cli` compile.

Version stamping: `version="0.0.0"`, `commit=""`, `date=""` are plain vars — real values require
`-ldflags` at build time; `/` (HomeHandler) echoes whatever was injected.

## 3. Process model & how TBot launches it

`TBot.Ogame.Infrastructure/OgameService.cs`:

- `Initialize(...)` spawns `ogamed` / `ogamed.exe` (resolved by `GetExecutableName()` via
  `RuntimeInformation.IsOSPlatform`; expected **next to the app**: `AppContext.BaseDirectory`,
  checked by `ValidatePrerequisites()`) with (`ExecuteOgamedExecutable`, line ~86):
  `--universe="…" --username=… --password=… --device-name=… --language=… --auto-login=false --port=<port> --host=0.0.0.0`
  plus conditionally `--nja-api-key`, `--proxy*`, `--lobby=lobby-pioneers`,
  `--basic-auth-username/-password`, and every `--device-*` knob present on the `Device` record.
  Note `--host=0.0.0.0` is hardcoded in the args while the C# client talks to `http://127.0.0.1:port`.
- Basic auth header is pre-set on the `HttpClient` when both `Credentials.BasicAuthUsername/Password` are non-empty (matches the daemon's optional `middleware.BasicAuth`).
- `Timeout = 60 s`; all calls go through `GetAsync/PostAsync` → Polly `HandleTransientHttpError().WaitAndRetryAsync(3, 2^n s)` (≈1 s, 2 s, 4 s backoff) → `ManageResponse<T>` which deserializes the envelope `OgamedResponse {Status,Code,Message,Result}` and unwraps `Result` (JObject/JArray → `T`), throwing `OgamedException` when `Status != "ok"`.
- Process lifecycle: stdout/stderr piped into `ILoggerService` tagged `LogSender.OGameD`; on exit,
  if runtime > 500 ms and not a deliberate kill, `RerunOgamed()` restarts the daemon after 1 s
  (auto-respawn loop); a <500 ms life or `_mustKill` surfaces `OnError`. `KillOgamedExecutable`
  kills + disposes. Credentials (incl. password) ride **in the process command line** — visible in
  `ps`/proc; that is the designed transport, not a secret store.
- `_cookiesPath` field exists but is never assigned/used in this class.

## 4. Daemon runtime behaviour (from `cmd/ogamed-tbot/main.go` + `pkg/wrapper`)

- Single global `*wrapper.OGame` bot stored in echo context (`ctx.Set("bot", …)`); `botMap` and
  `manualModeTimeout` maps exist but hold only the `"tx"`/`"timeout"` keys — this is a **single-account
  daemon** despite the map plumbing. `AddNewAccount()` exists but is not wired to any route.
- All state mutations are serialized through `wrapper`'s task runner (`pkg/taskRunner`): one worker,
  priority heap (`Low<Normal<Important<Critical`); every public `Prioritize` method is
  `begin(name)/defer done()` around the real call — the HTTP handlers therefore queue behind each
  other, and `GET /tasks` (`TasksHandler`) reports the heap (`TasksOverview` counts per priority).
- "Manual mode": `POST /bot/toggle-manual-mode` flips a 30 s named lock (`BeginNamed("manual mode")`);
  while held, `GET/POST /game/index.php` proxy the browser's own requests through the same lock
  (timer reset per request) and the HTML gets a fixed-position "Manual mode (on/off)" button +
  cookie-banner stripping + gameforge-hostname→request-host rewrite (`replaceHostnameWithRegxp`).
- TLS: `--enable-tls` → `e.StartTLS(host:port, tlsCertFile, tlsKeyFile)`; defaults `~/.ogame/key.pem`,
  `~/.ogame/cert.pem`. **Naming trap:** flag `--tls-key-file` reads env `OGAMED_TLS_CERTFILE` and
  `--tls-cert-file` reads `OGAMED_TLS_KEYFILE` (swapped suffixes in source). `--enable-tls` is
  declared `StringFlag` but parsed with `c.Bool` (works for "true"/"false"/"").
- CORS on by default (`cors-enabled`, env `CORS_ENABLED`).
- Device typo: `--device-height` persists via env **`OGAMED_DEVICHEIGHT`** (sic, missing E).
- `GET /cdn/*`, `/assets/css/*`, `/headerCache/*`, `/favicon.ico`, `/game/sw.js`, `GET /api/*`,
  `HEAD /api/*` proxy static/game content from the game server through the daemon (AntiGame support);
  `*.xml` responses get the hostname rewrite, `HEAD /api/*` mirrors upstream headers and answers
  `424 Failed Dependency` when the bot has no cached headers.
- Chat/auctioneer: on login the daemon dials the game's socket.io (`wss://<host>:<port>/socket.io/`,
  EIO=4) with TLS verification disabled, joins `chat` and `auctioneer namespaces, authorizes chat
  with the cached `ogameSession`, and dispatches `ChatMsg`/auctioneer events to registered callbacks
  (none registered by the HTTP daemon itself; reconnect loop = exponential backoff capped 60 s).

## 5. Login, session, storage, device, proxy, captcha

### 5.1 Login chain (`pkg/wrapper/ogame_login.go`, `pkg/gameforge/gameforge.go`)

1. `postSessions`: `GET <lobby>.<platform>.gameforge.com/config/configuration.js` → scrape
   `gameEnvironmentId` + `platformGameId`; then `POST
   https://spark-web.gameforge.com/api/v2/authProviders/mauth/sessions` with JSON
   `{blackbox:"tra:<x>", gameEnvironmentId, gameId, gfLang:"en", identity:<email>, locale:"en-GB", password}`;
   headers `Content-Type: application/json`, optional `gf-challenge-id`, and when `--otp/OTPSecret`
   set: `tnt-2fa-code: <TOTP>` (pquerna/otp) + `tnt-installation-id:""`.
   `201` → `{token,...}` (bearer). `409`+`gf-challenge-id` header → `CaptchaRequiredError`.
   Non-201 bodies mapped to `ErrOTPRequired`/`ErrOTPInvalid`/`ErrBadCredentials`; 403 `Forbidden`; 5xx passthrough.
2. `loginPart1`: `GET /api/users/me/accounts` + `GET /api/servers` (lobby host) → match
   server by `name==universe && language==lang` (`FindAccount`; `ba`↔`yu` aliasing); blocked
   accounts → `AccountBlockedError{BannedReason}`; no match → `ErrAccountNotFound`.
3. `loginPart2`: fetch `https://s<n>-<lang>.ogame.gameforge.com/api/serverData.xml` into `ServerData`
   (see infrastructure-models.md); sets `serverURL`, sanitizes lang (`yu→ba`) and version
   (regex `\d+\.\d+\.\d+`).
4. `loginPart3`: `POST /api/users/me/loginLink` (blackbox + account ids) → `GET` the link
   (`/game/lobbylogin.php?id=…&token=…`) through the **login proxy transport** if configured →
   parse overview page: `ogameSession` (empty ⇒ `ErrBadCredentials`), server timezone →
   `cache.location`, **version-dispatched extractor** (§6), preferences page, chat connect,
   v11 intro bypass. Cookie jar saved to disk after success.
5. Re-login paths: `LoginWithExistingCookies` reuses bearer (`gf-token-production` cookie or
   memory) + `PHPSESSID` and skips the credentials POST when both work; `withRetry` (below)
   triggers it automatically on `ErrNotLogged`. Manual logout writes the logout page then
   `softLogout` (stops chat, clears logged-in atom). `wrapLogin` = `loginWithBearerToken("","")`.

### 5.2 Retry / error policy (`OGame.pageContent`, `withRetry`)

- Every page fetch: `preRequestChecks` (ctx, enabled, logged-in, serverURL) → optional `Delay`
  → `execRequest` (gzip Accept-Encoding; `X-Requested-With` for ajax; POST =
  `application/x-www-form-urlencoded`) → `detectLoggedOut` heuristics per page →
  `processResponseHTML` cache/token update.
- Retry: **10 attempts**, exponential backoff 1→2→4… capped **60 s** (`pkg/exponentialBackoff`);
  on `ErrNotLogged` re-login via cookies; terminal on parent-ctx done, bot disabled, logged-out-manually,
  or login errors (`ErrAccountNotFound`, `AccountBlockedError`, `ErrBadCredentials`,
  `ErrOTPRequired`, `ErrOTPInvalid`); other errors keep retrying until the 10 budget is spent
  (`failed to execute callback: %w`). `SkipRetry` option opts out per call.
- `execRequest` returns `[]byte{}` (no error) for HTTP ≥500 after logging "bad status".
- Not-logged HTML snapshots: last 20 kept under `~/.ogame/not_logged/not_logged_<page>_<ts>.html`.
- C# side adds its **own** 3× transient retry (Polly) on top — worst case a single user call can
  hit the game server ~30× after backoffs.

### 5.3 Storage layout (all under `$HOME`)

| Path | Writer | Content |
|---|---|---|
| `~/.ogame/storage/<device-name>/fingerprint` | `device.FilePersistor` | JSON `JsFingerprint` (plain JSON on disk; the *submitted* form is the obfuscated "blackbox", see below) |
| `~/.ogame/storage/<device-name>/cookies` | `orirawlings/persistent-cookiejar` | persistent cookie jar (`PersistSessionCookies: true`); **contains the gf-token bearer and PHPSESSID in clear** |
| `~/.ogame/not_logged/*.html` | wrapper on login loss | diagnostics, max 20 |
| `<cwd>-queues.db` (intended) | buildqueue bbolt | build queues, per user-universe-lang |

The fingerprint is a fabricated browser identity: `ConstantVersion:12`, UA, browser/engine, vendor,
WebGL string, canvas/webgl/audio hashes (random 64-hex), screen metrics, timezone/language
validated against hardcoded lists, `XVec` rotated per `GetBlackbox()` call. `GetBlackbox()` also
fetches `https://gameforge.com/tra/game1.js` for the `Date` header + RTT, then serializes the
fingerprint as a positional array and encodes it with the custom `EncryptBlackbox` cumulative-sum
pseudo-base64 ("blackbox", prefix `tra:`); versions 8/9/11/12 have distinct array layouts
(`ParseBlackboxV8/9/11/12`). The daemon's HTTP API exposes none of this; it is internal to login.

### 5.4 Device fingerprint flags (daemon)

`--device-name` (storage key), `--device-system` (`Android|Windows|MacOSX|Linux|iOS`, lowercased in
main, default windows), `--device-browser` (`chrome|opera|safari|edge|firefox`, default chrome),
`--device-memory` 8, `--device-concurrency` 16, `--device-color` 16, `--device-width` 1900,
`--device-height` 900, `--device-timezone` Europe/Berlin, `--device-lang` "en-US,en",
`--device-user-agent` (Chrome 150 Win10 default in ogamed-tbot; the *HTTP client* UA comes from the
**persisted** fingerprint, so a fresh device dir gets the builder UA, an existing one keeps the old).
Stock `cmd/ogamed` hardcodes Windows/Chrome/144 UA + America/Los_Angeles and only exposes
`--device-name`. Unspecified numeric/randomized fields are filled from per-OS choice tables in
`pkg/device/device.go`. If `~/.ogame/storage/<name>/fingerprint` exists it wins over flags
except UA is re-synced from it.

### 5.5 Proxy

`--proxy <host:port>` `--proxy-username --proxy-password --proxy-type socks5|http (default socks5)
--proxy-login-only`. Implementation: socks5 via `golang.org/x/net/proxy` dialer; http via
`http.Transport{Proxy: ProxyURL}` + `Proxy-Authorization` basic when creds given. All transports
set `TLSClientConfig` — default `InsecureSkipVerify:true`, replaced by the `TLSConfig` param when
provided (not reachable from CLI flags). `loginOnly=true` ⇒ proxy used only for lobby auth chain
(`loginProxyTransport`: sessions, loginLink, support page, `GET /bot/ip`); otherwise the transport
is installed on the shared client for **all** game traffic. `GET /bot/ip` calls
`https://jsonip.com/` through the login-proxy transport (same egress as login).

### 5.6 Captcha

Gameforge image-drop challenge (`challenge.gameforge.com`, `image-drop-challenge.gameforge.com`;
`GET .../challenge/<id>`, `.../<id>/en-GB`, `/text`, `/drag-icons`, answer `POST {"answer":0..3}`).
Three solvers exist:

| Solver | Trigger | Transport |
|---|---|---|
| built-in HTTP endpoints | `GET /bot/captcha` (HTML form) / `GET /bot/captcha/challenge` (JSON `{ID,Question b64,Icons b64}`) + `POST /bot/captcha/solve` (`challenge_id`,`answer`) | human solves; solve endpoint re-logins and 307-redirects `/` |
| `TbotSolver` (ogamed-tbot) | `--nja-api-key` / env `NJA_API_KEY` set | `POST https://solver.obot.de/api/v1/captcha/solve` multipart `question`/`icons`, header `OBOT_API_KEY`, resp `{"answer":int}` |
| `NinjaSolver` (stock, `pkg/gameforge/solvers`) | same flag on ogamed | `POST https://www.ogame.ninja/api/v1/captcha/solve`, header `NJA_API_KEY` |
| `TelegramSolver` | library only | photos + inline keyboard to a chat |
| `ManualSolver` | library only | writes `question.png`/`icons.png` cwd, stdin answer |

Auto-solve budget: `maxCaptchaRetries` default 3 per `Gameforge.Login` invocation; without a solver
the `CaptchaRequiredError` propagates (login fails). TBot's `GetCaptchaChallenge`/`SolveCaptcha`
use the JSON endpoints — i.e. TBot can act as the solver when no API key is configured.

### 5.7 Game-version dispatch

`loginPart3` → `getExtractorFor(version)` picks the HTML parser:

`≥12.0.0 → v12_0_0; ≥11.15.0 → v11_15_0; ≥11.13.0; ≥11.9.0; ≥11.0.0; ≥10.4.0; ≥10.0.0; ≥9.0.0;
≥8.7.4; ≥8.0.0; ≥7.1.0; else v7` (packages `pkg/extractor/v*`; default pre-parse extractor is
v12_0_0). Version sanitized to `X.Y.Z`. `<13.0.0` vs `≥13.0.0` also switches *behaviour* in
`getAttacks` (eventlist JSON vs component ajax), `galaxyInfos`/`getGalaxyPage`
(`fetchGalaxyContent` vs `fetchSolarSystemData`), `cancelFleet` (extra tokenized recall path),
`fetchResources` (resourcesbar POST vs fetchResources page). The extractor also receives
`SetLanguage`, `SetLocation(server tz)`, `SetLifeformEnabled`.

## 6. What TBot actually exercises (cross-reference)

Every `IOgameService` member maps to exactly one daemon route (full table in daemon-api.md §Routes;
mapping list in `OgameService.cs` — e.g. `GetLFBonuses → GET /bot/lfbonuses`,
`AbandonCelestial → GET /bot/celestials/:id/abandon`,
`GetPositionsAvailableForDiscoveryFleet → POST /bot/planets/:id/get-system-available-discovery`).
Notable mismatches found while auditing:

- `SendFleet` posts a `food` field the handler ignores, builds `ships` via reflection over
  `Ships` properties parsed as `Buildables` — any Ships property not in the enum is silently dropped;
  `speed` is `decimal` → string (daemon validates 0–10).
- `SetUserAgent` hits `POST /bot/set-user-agent`, whose handler is a **stub returning
  `400 deprecated`** → `OgamedException` on every call.
- `POST /bot/planets/:id/send-ipm`: handler reads `:ipmAmount` and `:type` path params that the
  registered route does not contain ⇒ the endpoint always answers `400 invalid ipmAmount`. TBot
  has no IPM wrapper, so this is latent, not user-visible.
- `GetTbotIP()` calls `GET https://jsonip.com` **through the daemon client with a relative-URI
  helper**, i.e. `new Uri("https://jsonip.com", UriKind.Relative)` against base
  `http://127.0.0.1:port/` — resolves to `http://127.0.0.1:<port>/jsonip.com`, which the daemon
  does not serve. Latent bug in `OgameService.GetTbotIP`.
- `Phalanx`/`SendDiscovery`/`Abandon`/`BuyOfferOfTheDay` treat HTTP 400/OgamedException as
  domain outcomes (already-bought, no fleet, …) — the daemon's error envelope is part of the contract.

## 7. Windows / Linux / network / credential risk notes (evidence-based)

- **Windows-only path** in ogamed-tbot `start()` (`D:\TBot\...gohtml`) — see §2; on Linux the
  process would `log.Fatal` after the echo routes are registered but before `Serve`, even if
  buildqueue existed.
- **Linux**: binary name `ogamed` (no ext) must sit in `AppContext.BaseDirectory`; the daemon binds
  `0.0.0.0` — the API (incl. basic-auth-optional state-changing routes) is exposed on all
  interfaces; without basic auth anyone on the LAN can drive the account.
- **Credentials**: account password in argv; bearer token + session cookies plaintext under
  `~/.ogame`; TLS verification disabled by default for all upstream HTTPS (`InsecureSkipVerify`)
  — MitM-visible credentials/cookies on hostile networks; proxy mode also skips verify unless a
  `TLSConfig` is injected programmatically (not possible via flags).
- **Rate limiting**: client has `SetMaxRPS` support but nothing calls it ⇒ unthrottled; the only
  pacing is retry backoff and per-bot serialization.
- **Auto-respawn**: `OgameService` restarts the daemon indefinitely on crash (>500 ms uptime);
  a misconfigured daemon → tight restart loop with 1 s delay, each restart re-runs login.
- **Fingerprint stability**: `~/.ogame/storage/<name>` persists per device-name; reusing a name
  after flag changes keeps the old fingerprint (only UA re-synced) — gameforge blackbox deltas
  (`CalcDeltaMs`, rotated XVec) are recomputed per login.
- The daemon is **not** the stock upstream `ogamed`: the tbot fork adds
  `alliance-class`, `planets/:id/lifeform-bonuses`, `expedition-messages`, `toggle-manual-mode`,
  `lfbonuses`, raw `/game/index.php` pass-through with UI injection, static/CDN proxying, and the
  (missing) buildqueue UI; stock ogamed instead has `check-fleet` (FleetBuilder flight-time/fuel
  preview) and a `defender` wire-up that the fork drops. Do not assume route parity in either
  direction; the compatibility matrix is in daemon-api.md §3.

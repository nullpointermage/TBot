# ogamed / ogamed-tbot — HTTP API reference (as implemented at pin fbd0fda)

Derived line-by-line from `cmd/ogamed-tbot/main.go` (route table), `pkg/wrapper/handlers.go`,
`cmd/ogamed-tbot/handlers.go`, and the `Prioritizable`/`Wrapper` implementations in
`pkg/wrapper/{ogame.go,prioritize.go,ogame_public_interface.go}`. Every route below is
**implemented** in the pinned tree; the "TBot uses" column marks what
`TBot.Ogame.Infrastructure/OgameService.cs` calls. Endpoints marked *(tbot)* are fork-only;
*(stock)* exist only in `cmd/ogamed` and are absent from the tbot binary.

## 0. Conventions

- Envelope (handlers.go `APIResp`): success `{"Status":"ok","Code":200,"Result":<payload>}`,
  error `{"Status":"error","Code":<int>,"Message":"…"}`. HTTP status does **not** universally mirror `Code`: the deprecated user-agent handler returns HTTP200 with Code400, and cancel-fleet can wrap an error inside an `ok` envelope. Check transport, envelope and domain outcome separately.
- Auth: none by default; optional HTTP Basic when `--basic-auth-username` **and**
  `--basic-auth-password` are both set (constant-time compare). The C# client sends Basic
  whenever both credential fields are non-empty.
- Content: responses are JSON except the page-proxy endpoints (`/game/*`, `/cdn/*`, …) and
  `GET /bot/captcha` (HTML).
- Params: path params parsed with `utils.ParseI64` → `400 invalid …` on failure; body params are
  `application/x-www-form-urlencoded` (`PostFormValue`/`ParseForm`). Booleans/ids are strings.
- Prioritized wrapper calls use the task runner, but this is not unconditional serialization or cancellation safety for all daemon paths (see daemon.md §4 and [direct Go review](reference/audit-go-integration.md)). Manual-mode shared maps and transport swaps have separate boundaries. `Result` payloads are described in infrastructure-models.md; some specialized endpoints return a bare boolean or HTML instead.

## 1. Route table

### Meta / session

| Method & path | Handler | Params → Result | Effects / notes | TBot |
|---|---|---|---|---|
| GET `/` | `HomeHandler` | – → `{version,commit,date}` | ldflags-injected; `0.0.0/""/""` if unset | – |
| GET `/tasks` | `TasksHandler` | – → `TasksOverview{Low,Normal,Important,Critical,Total}` | heap snapshot | – |
| GET `/bot/login` | `LoginHandler` | – → `null` | `LoginWithExistingCookies`; 400 on `ErrBadCredentials`, else 500 w/ message | `Login()` |
| GET `/bot/logout` | `LogoutHandler` | – → `null` | logout page + cookie save + softLogout | `Logout()` |
| GET `/bot/username` | – | → string | configured username | `GetUsername()` |
| GET `/bot/universe-name` | – | → string | configured universe (not resolved name) | `GetServerName()` |
| GET `/bot/language` | – | → string | post-login sanitized lang | `GetServerLanguage()` |
| GET `/bot/server-url` | – | → string `https://sNN-cc.ogame.gameforge.com` | | `GetServerUrl()` |
| GET `/bot/server` | – | → `gameforge.Server` | includes `Settings` | `GetServerInfo()` |
| GET `/bot/server-data` | – | → `ServerData` (cache) | raw serverData.xml content | `GetServerData()` |
| GET `/bot/server/speed` | – | → int | `serverData.Speed` | `GetServerSpeed()` |
| GET `/bot/server/speed-fleet` | – | → int | `serverData.SpeedFleet` | `GetServerFleetSpeed()` |
| GET `/bot/server/version` | – | → string | game version, drives extractor dispatch | `GetServerVersion()` |
| GET `/bot/server/time` | – | → RFC3339 time | server tz; errors swallowed (zero time on failure) | `GetServerTime()` |
| GET `/bot/ip` | `GetPublicIPHandler` | → string | `https://jsonip.com` via login-proxy transport; 500 on fail | `GetOgamedIP()` |
| POST `/bot/set-user-agent` | `SetUserAgentHandler` | – | **stub: HTTP200 with Status=error, Code400, Message=deprecated** | `SetUserAgent()` (fails) |
| POST `/bot/page-content` | `PageContentHandler` | form: any `page=…` vals → `Result`: base64-encoded raw page bytes | raw page fetch through bot (retry+cache) | – |
| GET `/bot/is-under-attack` | – | → bool | attack eventlist scan | `IsUnderAttack()` |
| GET `/bot/is-vacation-mode` | – | → bool | cached flag | `IsVacationMode()` |
| GET `/bot/user-infos` | – | → `UserInfos` | errors ignored → zero-value on parse fail | `GetUserInfo()` |
| GET `/bot/character-class` | – | → int enum | cached | `GetUserClass()` |
| GET `/bot/has-commander` / `has-admiral` / `has-engineer` / `has-geologist` / `has-technocrat` | – | → bool | cached flags | `GetStaff()` (5 calls) |
| GET `/bot/alliance-class` *(tbot)* | `GetAllianceClassHandler` | → int enum | cached/lazy fetch | `GetAllianceClass()` |

### Empire / celestials

| Method & path | Result | Notes | TBot |
|---|---|---|---|
| GET `/bot/empire/type/:typeID` | empire JSON (`planets` array w/ per-level html) | typeID 0=planets 1=moons, else 400 | `GetEmpirePlanets/Moons` |
| GET `/bot/planets` | `[]Planet` | cached from last full page | `GetPlanets()` |
| GET `/bot/planets/:planetID` | `Planet` | 500 if unknown | `GetPlanet` |
| GET `/bot/planets/:galaxy/:system/:position` | `Planet` by coords | | – |
| GET `/bot/planets/:id/is-under-attack` | bool | per-celestial option | – |
| GET `/bot/planets/:id/resources-details` | `ResourcesDetails` | | `GetResourcesProduction` |
| GET/POST `/bot/planets/:id/resource-settings` | get: `ResourceSettings`; post: form `metalMine,crystalMine,deuteriumSynthesizer,solarPlant,fusionReactor,solarSatellite,crawler` → null | post validates each; 400 `ErrInvalidPlanetID` | (get only) `GetResourceSettings` |
| GET `/bot/planets/:id/resources-buildings` | `ResourcesBuildings` | | `GetBuildings` |
| GET `/bot/planets/:id/lifeform-buildings` | `LfBuildings` | | `GetLFBuildings` |
| GET `/bot/planets/:id/lifeform-techs` | `LfResearches` | | `GetLFTechs` |
| GET `/bot/planets/:id/lifeform-bonuses` *(tbot)* | `LfBonuses` | forces `cp=planet`, parses page inline | – |
| GET `/bot/lfbonuses` *(tbot)* | `LfBonuses` | cached variant `bot.GetLfBonuses()` | `GetLFBonuses()` |
| GET `/bot/planets/:id/defence` | `DefensesInfos` | | `GetDefences` |
| GET `/bot/planets/:id/ships` | `ShipsInfos` | | `GetShips` |
| GET `/bot/planets/:id/facilities` | `Facilities` | | `GetFacilities` |
| GET `/bot/planets/:id/production` | `[]Quantifiable` + hidden total | shipyard queue | `GetProductions` |
| GET `/bot/planets/:id/constructions` | `{BuildingID,BuildingCountdown,ResearchID,ResearchCountdown,LF…}` seconds | | `GetConstructions` |
| GET `/bot/planets/:id/resources` | `Resources` (incl. Population/Food) | | `GetResources` |
| GET `/bot/celestials/:id/techs` | `{supplies,facilities,ships,defenses,researches,lfbuildings,lfResearches}` | fetchTechs ajax | `GetTechs` |
| GET `/bot/celestials/:id/items` | `[]Item` | buffactivation ajax | – |
| GET `/bot/celestials/:id/items/:itemRef/activate` | null | activate + refresh | – |
| GET `/bot/celestials/:id/abandon` | `{CelestialID,Result:"succeed"}` | irreversible abandon; 400 when still present | `AbandonCelestial` |
| GET `/bot/moons` / `/bot/moons/:id` / `/bot/moons/:g/:s/:p` | `[]Moon`/`Moon` | | `GetMoons/Moon` |
| GET `/bot/moons/:id/phalanx/:g/:s/:p` | `[]PhalanxFleet` | 3 upstream calls; 400 no phalanx/range/deut | `Phalanx` |
| POST `/bot/moons/:id/jump-gate` | `{success:bool,rechargeCountdown:int}`; form `moonDestination`, repeatable `ships=<id>,<n>` | | `JumpGate` |

### Building / research

| Method & path | Body/params | Effects | TBot |
|---|---|---|---|
| POST `/bot/planets/:id/build/:ogameID/:nbr` | path only | generic build (any id class) | – |
| POST `/bot/planets/:id/build/cancelable/:ogameID` | | building/tech/lf only | `BuildCancelable×3` |
| POST `/bot/planets/:id/build/production/:ogameID/:nbr` | | ships/defences | `BuildMilitary` |
| POST `/bot/planets/:id/build/building/:ogameID` | | | `BuildConstruction` |
| POST `/bot/planets/:id/build/technology/:ogameID` | | | `BuildTechnology` |
| POST `/bot/planets/:id/build/defence/:ogameID/:nbr` | | | `BuildDefences` |
| POST `/bot/planets/:id/build/ships/:ogameID/:nbr` | | | `BuildShips` |
| POST `/bot/planets/:id/teardown/:ogameID` | | tear down building (checks button enabled) | – |
| POST `/bot/planets/:id/cancel-building` / `cancel-research` | | cancel current queue entry | `CancelConstruction/CancelResearch` |

All build errors surface as `500` with the upstream message (`failed to build : … (code)`).

### Fleet

| Method & path | Body | Result/Errors | TBot |
|---|---|---|---|
| GET `/bot/fleets` | – | `[]Fleet` (slots dropped) | `GetFleets` |
| GET `/bot/fleets/slots` | – | `Slots{InUse,Total,ExpInUse,ExpTotal,…}` | `GetSlots` |
| POST `/bot/fleets/:fleetID/cancel` | – | null; version≥13 does tokenized recall first | `CancelFleet` |
| POST `/bot/planets/:id/send-fleet` | repeatable `ships=<id>,<n>` (must be `ID.IsShip()`), `speed` 0–10 (default 10), `galaxy,system,position,type,mission,metal,crystal,deuterium`, optional `duration,union` | `Fleet` on success; enumerated 400s: `ErrInvalidPlanetID,ErrNoShipSelected,ErrUninhabitedPlanet,ErrNoDebrisField,ErrPlayerInVacationMode,ErrAdminOrGM,ErrNoAstrophysics,ErrNoobProtection,ErrPlayerTooStrong,ErrNoMoonAvailable,ErrNoRecyclerAvailable,ErrNoEventsRunning,ErrPlanetAlreadyReservedForRelocation`; other → 500 | `SendFleet` |
| POST `/bot/planets/:id/check-fleet` *(stock only)* | same as send-fleet | `{origin,destination,flightTime,fuel,resources,cargo,cargoUsed,ships,mission,speed}` — FleetBuilder estimate, no send; cache misses can fetch upstream state | – |
| POST `/bot/planets/:id/send-discovery` | `galaxy,system,position` | `true`; 400 with reason | `SendDiscovery` |
| POST `/bot/planets/:id/get-system-available-discovery` *(tbot)* | `galaxy,system[,position]` | `[]Coordinate` (only `canSend==true` positions) | `GetPositionsAvailableForDiscoveryFleet` |
| GET `/bot/planets/:id/get-available-discoveries` *(tbot)* | – | int count; handler makes and discards an extra call before planet validation, then calls with options | `GetAvailableDiscoveries` |
| GET `/bot/attacks` | – | `[]AttackEvent` | `GetAttacks` |
| POST `/bot/planets/:id/send-ipm` | form `galaxy,system,position,priority` | **broken**: handler wants path `:ipmAmount`,`:type` not in route → always `400 invalid ipmAmount` | – |
| GET `/bot/galaxy-infos/:galaxy/:system` | – | `SystemInfos`; `ErrNotEnoughDeuterium` when empty | `GetGalaxyInfo` |

### Messages / reports / market

| Method & path | Result | Notes | TBot |
|---|---|---|---|
| GET `/bot/espionage-report` | `[]EspionageReportSummary` | tab 20 page 1 only | `GetEspionageReports` |
| GET `/bot/espionage-report/:msgid` | `EspionageReport` | | `GetEspionageReport(msgId)` |
| GET `/bot/espionage-report/:g/:s/:p` | `EspionageReport` | scans summaries → detail | `GetEspionageReport(coord)` |
| POST `/bot/delete-report/:messageID` | null | flagDeleted | `DeleteReport` |
| POST `/bot/delete-all-espionage-reports` | null | tab 20 | `DeleteAllEspionageReports` |
| POST `/bot/delete-all-reports/:tabIndex` | null | tabIndex 20–24 (espionage/combat/expedition/union/other) | – |
| POST `/bot/send-message` | form `playerID,message` → null | `400 invalid parameters` passthrough | `SendMessage` |
| GET `/bot/get-auction` | `Auction` | | `GetCurrentAuction` |
| POST `/bot/do-auction` | `"<celestialID>"="m:c:d"` repeatable | bid; `error:true` → 500 msg | `DoAuction` |
| GET `/bot/price/:ogameID/:nbr` | `Price{...}` | static price table incl. lfBonuses discount | `GetPrice×3` |
| GET `/bot/requirements/:ogameID` | `[]Requirement` | static table | – |
| GET `/bot/buy-offer-of-the-day` | null | 400 when already bought/failed | `BuyOfferOfTheDay` |
| GET `/bot/expedition-messages` *(tbot)* | expedition message row HTML | tab 22 page 1 | – |

### Captcha

| Method & path | Result | Notes | TBot |
|---|---|---|---|
| GET `/bot/captcha` | HTML `<img>` question+icons + answer form | performs a full login attempt first; "no captcha found" when none | – |
| GET `/bot/captcha/challenge` | `{ID,Question:b64png,Icons:b64png}` (empty struct when none) | same login-triggered flow | `GetCaptchaChallenge` |
| POST `/bot/captcha/solve` | 307 → `/` | form `challenge_id`,`answer`; errors only logged | `SolveCaptcha` |

### Page proxy / static (browser-facing; used by manual mode & AntiGame)

| Method & path | Behaviour |
|---|---|
| GET `/game/index.php` *(tbot)* | proxy GET; manual-mode aware; injects manual-mode button; strips cookie banner; rewrites gameforge host → request host |
| POST `/game/index.php` *(tbot)* | same for POST w/ form passthrough |
| GET `/game/allianceInfo.php` | alliance page HTML, cookie-banner stripped |
| GET `/cdn/*`, `/assets/css/*`, `/headerCache/*`, `/favicon.ico`, `/game/sw.js`, `/api/*` | buffer content from game server; `*.xml` host-rewritten; content-type sniffed/overridden; fork replies HTTP200 rather than preserving upstream status |
| HEAD `/api/*` | fresh upstream HEAD and mirror returned headers; `424` when returned headers are empty |
| *(stock only)* GET/POST `/game/index.php` | same proxy minus manual-mode/UI injection |

### buildqueue *(tbot — blocked, see daemon.md §2)*

`GET /build-queue` (HTML page), `POST /build-queue/queue`, `POST /build-queue/queue/:uid`,
`PUT /build-queue/queue`, `DELETE /build-queue/queue`, `POST /build-queue/execute` — registered in
`main.go` but the package providing `h` does not exist in the pin; runtime also needs the Windows
template path. Documented for completeness; **not reachable** in the pinned build.

## 2. Handler-level quirks worth knowing when writing clients

1. `ConstructionsBeingBuiltHandler` returns countdown **seconds** as int64 (0 when idle).
2. `GetEmpireHandler` rejects `typeID>1`; `Celestials` enum in C# is 1-based — the client passes
   the route constant, not the enum.
3. `CancelFleetHandler` returns HTTP200 with `SuccessResp(bot.CancelFleet(...))`: nil Result on success, but an error object can also appear inside the `ok` Result. This is not a reliable failure envelope or cancellation confirmation.
4. `CelestialAbandonHandler` 400s with `"Celestial could not be deleted"` when the celestial still
   resolves after abandon. This can be an ambiguous action outcome: inspect/reconcile actual state before any retry; an HTTP status alone does not make abandonment safe to repeat.
5. `GetMoonHandler` answers 400 `invalid moon id` for both parse failure *and* unknown id.
6. `GetAttacks` ≥13.0.0 path parses `content.eventlist` HTML embedded in JSON; fleet-time fields
   are epoch seconds; the C# `AttackerFleet` maps by field name (no json tags on the Go side).
7. `DoAuctionHandler` requires strict `m:c:d` (`Sscanf %d:%d:%d`, n==3).
8. `PageContentHandler` ignores fetch errors and JSON-encodes raw bytes as base64 (or null for nil bytes), not plain HTML. HTTP200 does not establish fetch success.
9. `ServerTimeHandler` swallows errors → zero time.

### C# adapter edge cases verified offline

The harness in [tools/adapter-smoke](../tools/adapter-smoke/Program.cs) intercepts every HTTP call in memory and never initializes a daemon. It confirms malformed HTTP200 responses can raise `NullReferenceException`, an `ok` envelope can mask HTTP400, already-accepted offer error envelopes become Unknown, and an officer lookup failure discards earlier flags. The adapter applies the same transient-error retry policy to POSTs as GETs, without idempotency keys; do not infer safe action retries from this table. These are characterization tests of the existing implementation, not fixes.

## 3. Fork vs stock capability matrix

| Capability | ogamed-tbot (fork) | cmd/ogamed (stock) |
|---|---|---|
| device flags | full set (os/browser/mem/screen/tz/lang/UA) | name only (hardcoded Win/Chrome profile) |
| `playerid`/`bearer` bootstrap flags | absent (Params fields exist) | present via `defenderFlags` (build broken) |
| alliance-class, lfbonuses, expedition-messages, manual-mode, game proxy+UI, lifeform-bonuses | yes | no |
| check-fleet, defender wire (`wireDefender`), send-ipm working path | no / no / broken | yes / yes(uncommitted) / same broken route args |
| buildqueue UI | referenced, package missing | absent |
| captcha auto-solver | obot.de (`TbotSolver`) | ogame.ninja (`NinjaSolver`) |

Both binaries share `pkg/wrapper` entirely; the wrapper's full `Prioritizable`/`Wrapper` surface
(interfaces.go, 130+ methods — marketplace, officers, preferences, chapters, highscore, DM items,
lf-research slots, unions, sitting/gifting codes …) is larger than either daemon exposes via HTTP;
unexposed methods are reachable only from Go clients (`cmd/cli`, `cmd/c`, library use) and are
listed in `docs/reference/ogame-read.json` under `pkg/wrapper/interfaces.go`.

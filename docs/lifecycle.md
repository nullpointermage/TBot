# Lifecycle reference

All facts below are from `TBot/Program.cs`, `TBot/Services/InstanceManager.cs`,
`TBot/Services/TBotMain.cs`, `TBot/Services/SettingsFileWatcher.cs`,
`TBot/Services/CmdLineArgsService.cs`, `TBot.Common/Settings/SettingsService.cs` and the worker
infra (`WorkerBase`, `CelestialWorkerBase`, `WorkerFactory`) at commit `35b4ce0`.

## 1. Process startup (`Program.MainAsync`)

1. `WebApp.GetServiceCollection()` registers: `ILoggerService<>`, scoped `CalculationService`,
   `OgameService`, `TBotMain`, `TBotOgamedBridge`, `FleetScheduler`, `WorkerFactory`,
   `TelegramMessenger`, `InstanceManager`. `ConsoleHelpers.SetTitle()`.
2. `CmdLineArgsService.DoParse(args)` (see §7). `--help` prints help and `Environment.Exit(0)`.
3. Settings path = `<AppContext.BaseDirectory>/settings.json`, overridden by `--settings=`
   (made absolute). `SettingsService.GlobalSettingsPath` is set (also used by WebUI).
4. Log path = `<current working dir>/log`, overridden by `--log=`; `ConfigureLogging(logPath)`.
5. `WebApp.Build()` builds the container. Note: `WebApp.GetServiceCollection` already reads
   `settings.json` for `WebUI.Urls` (`TBot.WebUI/Program.cs:36-39`) — the WebUI URL list is
   effective from this read.
6. Context validation: `ogameService.ValidatePrerequisites()` (ogamed binary present) else
   `Environment.Exit(-1)`; then the settings file must exist else log error + `Exit(-1)`.
7. `_instanceManager.OnSettingsChanged()` — the main instance bootstrap (§2). This call is
   `async void`-style fire-from-main; the process then waits on CTRL+C.
8. WebUI: global settings re-read; if `WebUI.Enable` is truthy → `WebApp.Main(cts.Token)` starts
   Kestrel with the URLs from `WebUI.Urls`.
9. CTRL+C handler: logs `CTRL+C pressed!`, cancels `cts`, completes the wait task; then
   `_instanceManager.DisposeAsync()` and log `Goodbye!`.

## 2. Instance manager (`InstanceManager.OnSettingsChanged`)

Guarded by a static `SemaphoreSlim(1,1)` (`instancesSem`) — reloads serialize process-wide.

- Reads the global settings file via `SettingsService.GetSettings` (dynamic `ConfigObject`).
- `InitializeTelegramMessenger()`: if `TelegramMessenger.Active` → construct singleton
  `TelegramMessenger(logger, calculationService, TelegramMessenger.API, TelegramMessenger.ChatId,
  TelegramMessenger.Logging)` and `await TelegramBot()` (starts polling). Then
  `TelegramAutoPing.Active && EveryHours present` → `StartAutoPing(max(EveryHours,1))`.
  If the messenger gets disabled on a later reload: `TelegramBotDisable()` + remove from all
  instances + `logger.RemoveTelegramLogger()`.
- Instance topology:
  - No `Instances` key → **single-instance mode** (`SettingsVersion.AllInOne`): the main settings
    file itself is one instance, alias `MAIN`, unless a instance with the same settings path is
    already running (then kept, alias unchanged).
  - `Instances` present → **multi-instance**: entries `{Settings, Alias}`; `Settings` resolved
    relative to the global settings file's directory; duplicates (same resolved path) deduped,
    first alias wins; already-running instances only get their alias updated. Count logged.
- Deinit pass: every previously-running instance whose settings path is not in the new set is
  `DisposeAsync`ed (awaited via `Task.WhenAll`).
- Init pass: for each new instance `StartTBotMain(path, alias)` is *started* (not awaited) and the
  loop then sleeps a **random 30–60 s** between launches (`Thread.Sleep`). Results awaited
  afterwards; `MissingConfigurationException`, `AccountInVacationModeException`,
  `UnableToLoginException` per instance are caught, logged via the stats line and the instance is
  simply not added (comment: "for now, let's keep old behaviour" — there is no fail-hard setting).
- The instance list is swapped atomically; stats logged
  `Instances stats: Initialized N - Deinitialized M`.
- First run also arms `SettingsFileWatcher(OnSettingsChanged, globalSettingsPath)` (§4).

`TBotInstance_OnError`: on instance error event, the instance is removed from the list and
disposed (`InvalidOperationException` swallowed).

## 3. Instance initialization (`TBotMain.Init`) and per-instance settings

1. `InstanceSettingsPath`/`InstanceAlias` stored; `InstanceSettings = GetSettings(path)`
   (dynamic). A **profile merge is NOT applied here** — profiles only via Telegram `/profile`.
2. `InitializeOgame()`:
   - `General.Host` (default `localhost`) / `General.Port` (default `"8080"`, `int.Parse`);
     port must be free else `Exception("Port ... is not available")` → instance fails.
   - Proxy (only if `General.Proxy.Enabled && Address != ""`): type lower-cased; `https`→`http`;
     bare `host:port` gets `http://` prefix; only `socks5`/`http` accepted (else warning +
     "Press enter to continue" — note this can block on a headless run!); username/password
     passed when non-empty. `General.Proxy.LoginOnly` is NOT copied (see findings).
   - `ogameService.Initialize(credentials, device, proxy, host, port, CaptchaAPIKey)`;
     credentials from `Credentials.*` (Universe FirstCharToUpper, Language lower-cased,
     LobbyPioneers bool, BasicAuth pair), device fingerprint from `Credentials.DeviceConf.*`.
     Cookies file: `cookies<Credentials.Email>.txt` next to the binary.
   - random `AFewSeconds` delay.
3. `ogameService.Login()`; on `OgamedException` or `HttpRequestException` → `ResolveCaptcha()`
   (fetch challenge, solve via `OgameCaptchaSolver.GetCapctchaSolution` MD5-hash table with
   random 0..3 fallback, `SolveCaptcha`, delay, re-login). Captcha table: static
   image/text MD5 dictionaries in `OgameCaptchaSolver.cs` (~1.4 k lines).
4. `loggedIn = true`; `InitUserData()` (serverInfo/serverData/userInfo/staff/allianceClass via
   bridge; player name/class/rank/points logged).
5. Vacation mode check → logout + `AccountInVacationModeException`.
6. `telegramMessenger?.AddTbotInstance(this, bridge)` — instance becomes command target
   (index = position in messenger list).
7. `userData.celestials/researches/...` loaded; **if the account has exactly ONE celestial**,
   `EditSettings(thatCelestial)` rewrites the instance JSON (Brain.Transports.Origin,
   AutoResearch.Target, AutoRepatriate.Target[0], Expeditions[0], AutoDiscovery[0],
   AutoColonize.Origin) and settings are re-read — single-planet accounts get their config
   auto-pointed at that planet.
8. `InitializeSleepMode()` → `StopSleepMode(false)` + `SleepModeTimer` due 0, period infinite
   (§6). `settingsWatcher = new SettingsFileWatcher(OnSettingsChanged, InstanceSettingsPath)`.

Failure semantics: any exception during init propagates to `InstanceManager` (instance dropped,
logged). `DisposeAsync` (§8) is the mirror image.

## 4. Settings reload & file watchers

Two independent watchers exist:

- **Global**: `InstanceManager`'s `SettingsFileWatcher` on the *global* settings file path.
  Fires `OnSettingsChanged` → full instance topology re-evaluation (§2): removed instances
  deinit, new ones init, aliases update. PhysicalFileProvider watch on the file name in its
  directory; on change: semaphore-guarded `_watchFunc()` then re-arm `initWatch()`.
- **Per instance**: `TBotMain.settingsWatcher` on the instance settings path.
  `OnSettingsChanged` (guarded by `_settingsReloadSemaphore`, dedupe via `_lastReloadFinished`):
  1. `cts.Cancel()` + stop every worker (`StopWorker`, awaited).
  2. `InstanceSettings = GetSettings(InstanceSettingsPath)` (plain file, **profiles cleared** —
     a file save discards any `/profile` overlay).
  3. `cts = new()`; `HandleSleepModeAsync(null)` re-evaluates features per sleep state
     ("If wakeUp, then all features will be restored"); `_lastReloadFinished = now`.

Note `EditSettings` (Telegram `/recall`, `/minexpecargo`, `/editsettings`) writes the instance
JSON via `SettingsService.WriteSettings` (per-path `AsyncReaderWriterLock`,
`Encoding.Default`) — the write itself triggers the watcher → full worker restart cycle.

## 5. Profiles (`/profile`)

- `ListProfiles`: lists `*.json` in `<instance dir>/profiles` (Telegram + log).
- `LoadProfile(names)`: each name → `profiles/<name>.json` (trimmed); any missing → abort with
  Telegram message. Workers stopped, then
  `InstanceSettings = GetMergedSettings(InstanceSettingsPath, profilePaths)` — base file +
  overlays in given order, arrays replaced, nulls ignored. `userData.runningProfiles = names`.
  On JSON error → Telegram `Invalid JSON format`; other errors → `Error loading profile`.
  Finally, if cancellation was requested, `cts` is recreated and `HandleSleepModeAsync(null)`
  restores features.
- `ResetProfile`: same stop cycle, then plain `GetSettings(InstanceSettingsPath)` and
  `runningProfiles = []`.
- `ListRunningProfiles`: from `userData.runningProfiles`.
- The merge is **in-memory only**; the file on disk is never rewritten by profile loads.

## 6. Sleep mode, wake, ghost sleep, fleet-save hooks

- `SleepModeTimer` → `HandleSleepModeAsync` state machine over `SleepMode.GoToSleep` /
  `SleepMode.WakeUp` (server time, `DateTime.TryParse`): six comparison branches (comments
  `YES YES YES` …) decide sleep-now / wake-at / delay-to-next-day; every re-arm adds
  `AMinuteOrTwo` jitter; invalid config ⇒ `WakeUpAsync(null)` (features on).
- `GoToSleepAsync`: if `PreventIfThereAreFleets` and fleets would return inside the window
  (deploy arrivals, other missions' `BackIn`; Discovery skipped) → postpone (`SleepModeTimer`
  change) + optional Telegram. Otherwise: `SleepMode.AutoFleetSave.Active` ⇒ fleet-save every
  celestial (`OnlyMoons` filter, ordered by fleet points desc, per-celestial errors logged and
  skipped); Telegram notify if `SleepMode.TelegramMessenger.Active`; `userData.isSleeping=true`;
  then `InitializeFeatures()` — features restart under sleep rules.
- `WakeUpAsync`: Telegram notify (if enabled), re-login ogamed if `isSleeping`, features restart.
- `SleepNow(WakeUpTime)` (Telegram `/sleep`): arms `TelegramSleepModeTimer` (one-shot,
  `WakeUpNow`) → disposes timer, `isSleeping=false`, `Bot woke up!`, `InitializeFeatures()`.
  While `TelegramSleepModeTimer` exists, `HandleSleepModeAsync` returns early (schedule paused).
- `TelegramCancelGhostSleep`: disposes `GhostSleepTimer`, `telegramUserData.Mission=None`.
- `LogoutOnSleep`: documented in settings but **dead** (commented-out blocks) — the bot never
  logs out on sleep in current code.
- Errors in any sleep handler: log + re-arm `SleepModeTimer` `AMinuteOrTwo` + `CheckCelestials()`.

## 7. Timers inventory (per instance `timers` dict)

| Key | Armed by | Purpose |
|---|---|---|
| `SleepModeTimer` | `InitializeSleepMode` / state machine | sleep schedule; one-shot re-arms |
| `TelegramSleepModeTimer` | `/sleep` | one-shot wake |
| `GhostSleepTimer` | FleetScheduler ghost-sleep path | cancelable via `/cancelghostsleep` |
| `TelegramAuctionSubscription` | `/subscribeauction` | one-shot next-auction notify (endtime+5 min, min 5 min) |

Worker scheduling: `AsyncTimer` per worker; `ChangeWorkerPeriod` clamps to `int.MaxValue` ms.
Worker due-times per feature: see `docs/configuration/features.md`.
AutoPing (`TelegramMessenger`): separate timer, first ping at next rounded hour, then every
`TelegramAutoPing.EveryHours` h; `/stopautoping`, `/startautoping` control it (`pingHours`
persists after stop).

## 8. Shutdown

- Process: CTRL+C → `InstanceManager.DisposeAsync()` → per instance `TbotInstanceData.Deinitialize()`
  = `TBotMain.DisposeAsync()` + `ServiceScope.Dispose()`; list cleared; `Goodbye!`.
- `TBotMain.DisposeAsync`: stop settings watcher; remove from Telegram messenger; stop all
  workers (`StopWorker` each, awaited) — which also stops celestial sub-workers; dispose all
  entries in `timers`; if logged in → `ogameService.Logout()`; `KillOgamedExecutable()`.
- `TelegramMessenger.TelegramBotDisable` (config off): remove messenger refs from instances,
  cancel polling `cts`, await receiving task (OperationCanceledException swallowed), dispose,
  `_logger.RemoveTelegramLogger()`.
- `SettingsFileWatcher.deinitWatch` only disposes the change callback (provider not disposed).

## 9. CLI arguments (`CmdLineArgsService`)

| Arg | Effect |
|---|---|
| `--help` | print help, exit 0. Checked **before** anything else; `printHelp` flag. |
| `--settings=<path>` | global settings file path (matched by `Contains("--settings")`, value after first `=`; a bare `--settings` is ignored — value must be non-empty). `Path.GetFullPath`. |
| `--log=<path>` | log directory. Same parsing. |

Parsing quirks: `Contains` (not prefix/startswith) matching, first `=` splits, only `=value`
(2 parts) accepted; unknown args silently ignored; last occurrence wins.

## 10. Exceptions (assigned models)

- `MissingConfigurationException` — instance settings file missing (`StartTBotMain`).
- `AccountInVacationModeException` — vacation detected after login; instance dropped, ogamed
  logged out first.
- `UnableToLoginException` — login failed incl. after captcha recovery.
- All three are caught per-instance in `InstanceManager` (instance skipped, process continues).
- `IntervalType` enum (LessThanASecond … AboutAnHour) maps to fixed ms ranges in
  `RandomizeHelper.CalcRandomInterval` — note `AboutAnHour` upper bound is 42 000 000 ms
  (11.7 h), likely a typo for 4 200 000; documented as-is.

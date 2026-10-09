# Architecture and code map

This is an implementation map of the audited `develop` source. Follow the linked feature/reference guides for exact account behavior. No account actions are implied by the architecture diagram.

```text
settings.json + instance_settings.json + selected profile overlays
                     |
          SettingsService / file watchers
                     |
              InstanceManager
                     |
              TBotMain (per account)
                /              \
       WorkerFactory        Telegram controls
              |
      workers and celestial workers
              |
    TBotOgamedBridge / FleetScheduler
              |
          IOgameService
              |
     ogamed-tbot HTTP process
              |
          OGame services

C# logs -> console/text/CSV + SignalR -> WebUI
                              \-> optional Telegram logging
WebUI Settings -> JSON writes -> file watcher -> runtime changes
WebUI Ogame -> iframe -> daemon's manual game reverse proxy
```

## Projects and boundaries

| Component | Responsibilities | Primary entry points |
|---|---|---|
| `TBot` | Executable, dependency registration, account lifecycle, workers, scheduling, Telegram, calculation helpers | [Program](../TBot/Program.cs), [TBotMain](../TBot/Services/TBotMain.cs), [InstanceManager](../TBot/Services/InstanceManager.cs) |
| `TBot.Common` | Shared dynamic JSON settings, read/write coordination, logging/sinks/formatters | [SettingsService](../TBot.Common/Settings/SettingsService.cs), [LoggerService](../TBot.Common/Logging/LoggerService.cs) |
| `TBot.Ogame.Infrastructure` | C# HTTP adapter, game-data models, enums and transport exceptions | [OgameService](../TBot.Ogame.Infrastructure/OgameService.cs), [IOgameService](../TBot.Ogame.Infrastructure/IOgameService.cs) |
| `TBot.WebUI` | Integrated Razor pages, JSON editing, CSV log queries, SignalR hosting, game iframe | [WebApp](../TBot.WebUI/Program.cs), [interfaces](interfaces.md) |
| `ogame` submodule | Separate Go implementation: login/session/device state, daemon API, game HTTP/reverse proxy, extractors and fixtures/tests | [Daemon](daemon.md), [API](daemon-api.md) |

The solution builds four C# projects. The Go daemon is not a C# project and must be packaged separately. The WebUI is a library in the executable's host; there is no separate React/Vite frontend build.

## Dependency registration and lifetime

`Program.MainAsync` obtains the WebUI service collection and registers generic logging as singleton plus scoped calculation, HTTP service, main account, bridge, scheduler, worker factory, Telegram and instance-manager interfaces. Account initialization obtains a scope from the scope factory, so account state should not be treated as one global worker object.

`SettingsService` exposes static global settings/log paths. Instance manager and some account coordination/model state also use static members; scoped DI therefore does not imply that every field is account-isolated. Read [lifecycle](lifecycle.md) and [fleet coordination](features/fleet-operations.md) before changing concurrency.

## Configuration is dynamic, not a validated schema

The pipeline is:

1. Read JSON with per-path reader/writer locking.
2. Deserialize to `ExpandoObject`.
3. Normalize the **first character** of each property name to uppercase via `JsonNetAdapter`.
4. Convert to `ConfigObject` for dynamic access.
5. Return `NullExceptionPreventer` on a missing dynamic member.

Missing-member casts can return false,0,null or empty typed arrays. `IsSettingSet` and `GetSetting` provide a separate presence/fallback path. Do not infer a required field's operational default from the adapter's cast alone.

Overlays use Newtonsoft `MergeArrayHandling.Replace` and `MergeNullValueHandling.Ignore`. Nested values merge; later overlays can override earlier ones. A nonempty overlay list is assumed in `GetMergedSettingsFromContents`. The [configuration guide](configuration/README.md) explains where profile selection occurs and which file watchers are active.

`ConfigObject` implements only a subset of the dictionary contract: `CopyTo`, removal by key/value pair and `IsReadOnly` throw `NotImplementedException`. Avoid designing extensions as if it were a fully general dictionary.

## Worker and scheduler model

Worker interfaces and base classes distinguish general callbacks from per-celestial work. The factory wires actual implemented worker classes to account/bridge/scheduler state. A configuration section's presence alone does not start a worker: feature enablement, parent gates, sleep/attack/slot/resource conditions and timers all matter.

- [Fleet operations](features/fleet-operations.md): expeditions, farming, harvesting, discovery, colonization, fleet saves, slot/priority coordination and target state.
- [Defender](features/defender.md): incoming attacks and configured reactions.
- [Brain](features/brain.md): construction/research/logistics/daily-offer/jump-gate decisions.
- [Calculations](calculations.md): costs, ship capacity/speed/flight time, lifeform modifiers and investment decisions.

`FleetScheduler` is not a generic cron service: it coordinates real fleet operations and return/recall information. `TBotOgamedBridge` refreshes/caches account data and connects state queries with the HTTP adapter. Source and model references are in those guides.

## Timer semantics that affect behavior

[`AsyncTimer`](../TBot/Includes/AsyncTimer.cs) owns a linked cancellation source and a task. It waits `DueTime`, awaits the callback, then waits `Period`; its loop repeats the due-time wait on every iteration, not only once at startup. Callback execution is awaited rather than overlapped by that timer.

- Start stops a previous scheduled action first.
- Due time must not be negative; period permits `Timeout.InfiniteTimeSpan`.
- Timings are clamped to at most one day; the helper preserves infinite periods.
- Infinite period exits after the callback; normal periods repeat.
- `ChangePeriod` permits shortening or an allowed increase, then disables further increases until the callback cycle resets that allowance.
- Changing timing fields does not cancel a currently outstanding `Task.Delay` automatically.
- Stop cancels and awaits the scheduled action. Exceptions other than cancellation are not globally swallowed by the timer.

These details make “every X seconds” an approximation unless the callback/due-time behavior is included.

## Utility behaviors and caveats

| Utility | Actual behavior | Consequence |
|---|---|---|
| `FormattingHelper.ParseDurationFromString` | Optional1–2-digit h/m/s groups, start-anchored regex without end anchor; returns seconds. The character classes include a literal pipe. | Trailing text can be accepted and unmatched text can yield0; do not describe it as strict duration validation. |
| `GeneralHelper.ShouldSleep` | Compares supplied time/sleep/wakeup values and handles their relative order, including crossing-midnight-style ordering. | Caller construction of dates/times matters; it is not an independent timezone scheduler. |
| `GeneralHelper.ClampSystem` | Bounds to1..499. | Not derived from live universe dimensions. |
| `GeneralHelper.WrapSystem` | Above499 resets to1; below1 resets to499. | Not mathematical modulo for arbitrarily large offsets. |
| `RandomizeHelper.CalcRandomInterval(int,int)` | Converts minutes to milliseconds and uses `Random.Next`. | Upper bound is exclusive; inconsistent/overflowing bounds can fail. |
| `CalcRandomIntervalSecToMs` | Converts seconds to milliseconds before random selection. | Different units despite similar names. |
| `IntervalType.AboutAnHour` | Literal range3,000,000..42,000,000 milliseconds. | The label is not a reliable bound; the large upper constant is documented as written, not silently fixed. |
| `Extensions.Shuffle` | Orders by random integers. | Not an explicit Fisher–Yates implementation or deterministic seeded shuffle. |
| `CelestialComparer` | Equality/hash by celestial ID. | Coordinate checks are separate methods; do not substitute one identity rule for another. |
| `ConsoleHelpers.PlayAlarm` | Three console beeps with blocking sleeps. | Sound depends on the platform/terminal and is not guaranteed to reach desktop speakers. |
| `Optional<T>` | Tracks presence after `Set`; `Get` returns the field without enforcing presence. | Callers must check `IsPresent` where absence matters. |

Sources: [helpers](../TBot/Helpers/FormattingHelper.cs), [GeneralHelper](../TBot/Helpers/GeneralHelper.cs), [RandomizeHelper](../TBot/Helpers/RandomizeHelper.cs), [extensions](../TBot/Includes/Extensions.cs), [Optional](../TBot/Includes/Optional.cs).

## Logging and frontend assets

Logging publishes console, text, CSV and optional Telegram output while the SignalR sink sends live objects. The browser joins today's live stream, queries older CSV pages, and formats timestamps with browser locale. See [interfaces](interfaces.md) for retention and filtering caveats.

Static assets are embedded through `TBot.WebUI.csproj`. Some standalone assets are dormant: the current settings editor uses `JsonEditor`, not the separately included `JSONedtr` implementation. The service worker registers a no-op fetch listener, so manifest presence does not establish offline functionality.

## Extension points for contributors

1. Identify the account-changing operation and its existing `IOgameService` method/model before adding another transport path.
2. Define exact configuration keys, units, omission behavior and parent/worker gates; do not rely on dynamic zero/null accidentally.
3. Wire the worker through the factory and lifecycle controls, including cancellation and reload handling.
4. Reuse fleet-slot coordination and transport/resource calculation paths instead of bypassing them.
5. Add focused offline tests and update the configuration entry, feature guide and source coverage record.
6. For daemon changes, update the pinned gitlink deliberately after verification; root C# changes do not automatically publish Go changes.
7. Keep side-effecting API/Telegram actions clearly distinguished from information-only commands.

There is no claim here that these extension points have a complete automated regression suite. Build success, pure helper probes and account-free WebUI checks are the verified baseline; live game and cross-platform acceptance need their own tests.

# Defender — operator reference

Source of truth: `TBot/Workers/DefenderWorker.cs` at repo commit `35b4ce0` (Go submodule `fbd0fda`). Line anchors like `DefenderWorker.cs#L62` refer to that file. Everything below is read from code; where the example config (`TBot/instance_settings.json`) disagrees with in-code fallbacks, both are stated. No claim here is about ban safety — the code simply does what is described.

Related reading: [fleet-operations.md](fleet-operations.md) (fleet scheduling, slots, `AutoFleetSave`, recall logic).

## 1. What it is

`DefenderWorker` (internal class, [DefenderWorker.cs#L21](../../TBot/Workers/DefenderWorker.cs#L21)) polls the attack overview and, when an enemy fleet is inbound, runs a fixed pipeline per attack: dedupe → whitelists/heuristics → notifications → optional spy/message → optional scheduled fleetsave, then recalls the saved fleet once the attacker disappears. It is an account-level worker (not per-celestial) driven by `WorkerBase`'s rescheduling timer.

Identity and wiring:

| Concern | Value | Source |
|---|---|---|
| Feature enum | `Feature.Defender` | [DefenderWorker.cs#L114](../../TBot/Workers/DefenderWorker.cs#L114) |
| Log sender | `LogSender.Defender` | [DefenderWorker.cs#L118](../../TBot/Workers/DefenderWorker.cs#L118) |
| Enable check | `(bool) InstanceSettings.Defender.Active` (any exception → disabled) | [DefenderWorker.cs#L104](../../TBot/Workers/DefenderWorker.cs#L104) |
| Factory | `WorkerFactory.InitializeWorker`, case `Feature.Defender` | [WorkerFactory.cs#L43](../../TBot/Workers/WorkerFactory.cs#L43) |
| Worker name | `"Defender"` (thread name `alias6` + name, ≤16 chars) | [DefenderWorker.cs#L111](../../TBot/Workers/DefenderWorker.cs#L111), [WorkerBase.cs#L69](../../TBot/Workers/WorkerBase.cs#L69) |

`WorkerBase.ExecutionWrapper` ([WorkerBase.cs#L153](../../TBot/Workers/WorkerBase.cs#L153)) ends the worker (period → infinite) whenever `UserData.isSleeping` is true or `Defender.Active` flips off; the next `InitializeFeature` restarts it.

## 2. Main loop

`Execute()` ([DefenderWorker.cs#L62](../../TBot/Workers/DefenderWorker.cs#L62)):

1. `FakeActivity()` — see §3.
2. `_tbotInstance.UserData.fleets = await _fleetScheduler.UpdateFleets()` (shared fleet cache refresh, [DefenderWorker.cs#L67](../../TBot/Workers/DefenderWorker.cs#L67)).
3. `await _ogameService.IsUnderAttack()` — the gate for everything else.
4. Under attack:
   - `Defender.Alarm.Active` → `ConsoleHelpers.PlayAlarm()` on a background task ([L71](../../TBot/Workers/DefenderWorker.cs#L71)).
   - `_tbotInstance.UserData.attacks = await _ogameService.GetAttacks()` then `HandleAttack(attack)` for each ([L74-77](../../TBot/Workers/DefenderWorker.cs#L74)).
   - `CheckForFleetsToRecall(attacks)` ([L78](../../TBot/Workers/DefenderWorker.cs#L78)).
5. Not under attack: log "Your empire is safe" and `CheckForFleetsToRecall(new List<AttackerFleet>())` — an empty list reads as "no attacker", which is what arms recalls ([L79-82](../../TBot/Workers/DefenderWorker.cs#L79)).
6. Reschedule: `interval = RandomizeHelper.CalcRandomInterval(CheckIntervalMin, CheckIntervalMax)`; if `<= 0` → `IntervalType.SomeSeconds` (20–50 s). **Unit: `CalcRandomInterval(int,int)` treats its arguments as minutes (`min * 60 * 1000`, [RandomizeHelper.cs#L27](../../TBot/Helpers/RandomizeHelper.cs#L27))**, so `CheckIntervalMin/Max` are minutes, not seconds. Example config `1..22` → every 1–22 min.
7. `await _tbotOgameBridge.CheckCelestials()` — detects gained/lost planets and re-seeds `BrainAutoMine` on growth ([TBotOgamedBridge.cs#L320](../../TBot/Workers/TBotOgamedBridge.cs#L320)).

Error path ([L91-99](../../TBot/Workers/DefenderWorker.cs#L91)): log at Warning, retry after `IntervalType.AFewSeconds` (5–15 s). A persistent ogamed outage therefore tightens the loop to seconds, unlike the healthy cadence.

## 3. `FakeActivity` — home/random touch

[DefenderWorker.cs#L123](../../TBot/Workers/DefenderWorker.cs#L123). If `Defender.RandomActivity` is false, resolves the celestial matching `Defender.Home.Galaxy/System/Position/Type` (config path `Defender.Home.*`, `Type` parsed via `Enum.Parse<Celestials>`) and issues an `UpdatePlanet(..., UpdateTypes.Defences)`; if no celestial matches (`ID == 0`) nothing happens. If `RandomActivity` is true, a random entry of `UserData.celestials` gets the same defences refresh. The refresh doubles as a keep-alive on the ogamed session; failures are silent (no try/catch needed — `UpdatePlanet` swallows exceptions internally, [TBotOgamedBridge.cs#L123](../../TBot/Workers/TBotOgamedBridge.cs#L123)).

## 4. `HandleAttack` pipeline

[DefenderWorker.cs#L153](../../TBot/Workers/DefenderWorker.cs#L153). Ordered gates; each `return` skips all later steps for that attack:

1. **Dedup**: static `ConcurrentDictionary<int, DateTime> _handledAttackIds` with 60-min TTL (`_handledAttackTtl`, [L22-23](../../TBot/Workers/DefenderWorker.cs#L22)). Expired entries are pruned each pass; an attack ID seen within the TTL is logged "already handled recently" and skipped ([L160-168](../../TBot/Workers/DefenderWorker.cs#L160)). Consequence: the *first* observation of an attack wins; a later cycle with better data (e.g. ships now visible) will not re-run the heuristics for 60 min.
2. **Account not loaded**: if `UserData.celestials` is empty, reschedule the whole worker by `IntervalType.SomeSeconds` and bail ([L170-178](../../TBot/Workers/DefenderWorker.cs#L170)).
3. **Target lookup**: `attackedCelestial = celestials.Unique().FirstOrDefault(planet => planet.HasCoords(attack.Destination))`; missing → warn and skip. Then `UpdatePlanet(..., UpdateTypes.Ships)` always, plus `UpdateTypes.Resources` when `Defender.IgnoreAttackIfIHave.Active` ([L180-191](../../TBot/Workers/DefenderWorker.cs#L180)).
4. **Whitelist**: `Defender.WhiteList` accepted as `long[]`, `int[]`, `IEnumerable<long>`, `IEnumerable<int>`; anything else logs "unsupported type" and behaves as empty ([L194-206](../../TBot/Workers/DefenderWorker.cs#L194)). If `attack.AttackerID` matches any entry → "attacker X whitelisted", skip. The example config uses `[0, 100000, 100003, 100004]`; a `0` entry is meaningful — attacker ID 0 (unknown) is whitelisted.
5. **Missile attacks** (`attack.MissionType == Missions.MissileAttack`): notify via `Defender.TelegramMessenger.Active`, then unless `DefendFromMissiles` is explicitly `false` (missing key counts as enabled — the check is `!IsSettingSet(...) || (IsSettingSet && true)`, [L224-227](../../TBot/Workers/DefenderWorker.cs#L224)):
   - If the target is a moon, defence is mounted from the planet at the same coords ([L229-236](../../TBot/Workers/DefenderWorker.cs#L229)).
   - Requires `Facilities.MissileSilo >= 2`; else log only.
   - If no production ongoing: `availableSpace = MissileSilo - AntiBallisticMissiles - 2 * InterplanetaryMissiles` and builds that many `AntiBallisticMissiles` when > 0 ([L246-251](../../TBot/Workers/DefenderWorker.cs#L246)). **Caveat: resources are fetched but never checked** — `BuildDefences` is called directly; insufficient resources surface as a failed build inside the service.
   - Returns; missile attacks never trigger fleetsave/spy/message paths.
6. **Fleet-composition heuristics** — only when `fleetCompositionKnown = attack.Ships != null && EspionageTechnology >= 8` ([L266](../../TBot/Workers/DefenderWorker.cs#L266)):
   - `Defender.IgnoreProbes` && `attack.IsOnlyProbes()` → skip (spy missions get a distinct log line).
   - `Defender.IgnoreWeakAttack` && `attack.Ships.GetFleetPoints() < attackedCelestial.Ships.GetFleetPoints() / (int)Defender.WeakAttackRatio` → "weak attack", skip ([L277-283](../../TBot/Workers/DefenderWorker.cs#L277)). Division is integer; `WeakAttackRatio` 0 would throw `DivideByZeroException` inside the surrounding try and be logged as a composition-check failure (the catch at [L301](../../TBot/Workers/DefenderWorker.cs#L301) swallows to a warning and continues to §"not worth it"/fleetsave — the attack is then treated as a threat).
   - Unknown composition: logged, heuristics skipped, attack treated as a threat ([L284-286](../../TBot/Workers/DefenderWorker.cs#L284)).
7. **`IgnoreAttackIfIHave`** ([L287-300](../../TBot/Workers/DefenderWorker.cs#L287)): active when `Defender.IgnoreAttackIfIHave.Active`. Skips the attack ("it's not worth it") only if **both** `attackedCelestial.Resources.TotalResources < MinResourcesToSave` **and** `fleetPoints * 1000 < MinFleetToSave`. **Unit quirk: fleet points are multiplied by 1000** before comparison, so `MinFleetToSave` is in "points × 1000" units — with the example `20000000` that is 20,000 fleet points. If composition is unknown, the setting is deliberately ignored and the fleetsave proceeds ("to be safe").
8. **Telegram notification**: `Defender.TelegramMessenger.Active` → attacker name/ID/destination/arrival, plus composition one second later ([L305-311](../../TBot/Workers/DefenderWorker.cs#L305)).
9. **`SpyAttacker`** ([L318-338](../../TBot/Workers/DefenderWorker.cs#L318)): refreshes slots; if the *attacked* celestial has probes, sends `Defender.SpyAttacker.Probes` espionage probes from the attacked celestial to `attack.Origin` at `Speeds.HundredPercent` via `FleetScheduler.SendFleet`. The fleet is looked up in `UserData.fleets` to log the arrival time; a null lookup logs "send may have failed or list not updated yet". The probe count is **not** re-checked against `MinCargosToKeep`-style reserves and can zero out the celestial's probes.
10. **`MessageAttacker`** ([L340-361](../../TBot/Workers/DefenderWorker.cs#L340)): picks a random entry of `Defender.MessageAttacker.Messages` (`Enumerable.Shuffle().First()`) and `SendMessage(attack.AttackerID, message)`; skipped when `AttackerID == 0`.
11. **`Autofleet`** ([L363-370](../../TBot/Workers/DefenderWorker.cs#L363)): `Defender.Autofleet.Active` → `ScheduleFleetSave(attackedCelestial, attack)` (§5). Note the config nests Telegram under `Autofleet.TelegramMessenger` in the example, but the code only ever reads top-level `Defender.TelegramMessenger` — the nested copy is inert.

## 5. Scheduled fleetsave (advanced guard)

Instead of saving instantly, `ScheduleFleetSave` ([DefenderWorker.cs#L383](../../TBot/Workers/DefenderWorker.cs#L383)) parks a timer per celestial:

- `bufferSeconds = Random 30..60`; `sendDelay = max(0, arriveIn - buffer)` — fleet leaves 30–60 s before impact.
- State lives in static `ConcurrentDictionary<int, ScheduledFleetSave> _scheduledFleetSaves` keyed by celestial ID (`ScheduledAtUtc`, `ApproxArrivalUtc`, linked `CancellationTokenSource`).
- `AddOrUpdate` semantics ([L398-413](../../TBot/Workers/DefenderWorker.cs#L398)): a *new* schedule is created only if none exists, or if the new attack's `ApproxArrivalUtc` is **strictly earlier** than the one currently driving the schedule. A later attack leaves the existing schedule untouched (its CTS is disposed). This is the "reschedule earlier only" guard documented in the XML doc comment.
- `RunScheduledFleetSave` ([L431](../../TBot/Workers/DefenderWorker.cs#L431)) waits until `ScheduledAtUtc`, then computes `minFlightTime = remainingSeconds + 30% + random-seconds` and calls `FleetScheduler.AutoFleetSave(celestial, isSleepTimeFleetSave:false, minFlightTime)` — i.e. the fleet must stay away at least until ~1.3× the remaining attack time, so it returns *after* the attacker would have hit. The destination search itself is `FleetScheduler.GetFleetSaveDestination` (see [fleet-operations.md §4](fleet-operations.md)).
- New outbound fleets are detected by diffing fleet IDs before/after plus origin match, and recorded in static `_awaySavedFleets[celestialID]` for recall. If none detected: "recall tracking skipped" — the save happened but recall will not be automatic ([L456-463](../../TBot/Workers/DefenderWorker.cs#L456)).
- `finally` removes the dictionary entry only if it still points at *this* instance (`TryRemove(KeyValuePair)`), so a superseding schedule is never clobbered; the CTS is disposed ([L469-474](../../TBot/Workers/DefenderWorker.cs#L469)).
- Cancellation paths: superseded by an earlier attack, worker token cancelled (shutdown) → `TaskCanceledException` logged at Information.

Because all state containers are `static`, they survive worker restarts within the process. Account instances in the same process share them; separate TBot processes do not.

## 6. Automatic recall

`CheckForFleetsToRecall` ([DefenderWorker.cs#L483](../../TBot/Workers/DefenderWorker.cs#L483)) runs every cycle for every celestial with tracked away-fleets:

- Attacker still targeting the celestial (any current attack whose `Destination` matches) → cancel any pending recall ("attacker is back").
- Otherwise `ScheduleFleetRecall` ([L511](../../TBot/Workers/DefenderWorker.cs#L511)): single pending recall per celestial (`_scheduledRecalls`), firing after a random **30–90 s** delay so a fresh attack can cancel it.
- `RunScheduledRecall` ([L530](../../TBot/Workers/DefenderWorker.cs#L530)) re-checks `GetAttacks()` immediately before firing; new attack → abort (recall entry removed by `finally`, fleets stay tracked? — no: the abort returns *before* `TryRemove` of `_awaySavedFleets` at [L547](../../TBot/Workers/DefenderWorker.cs#L547), so the fleets remain tracked and a later quiet cycle recalls them).
- Each tracked fleet is recalled via `FleetScheduler.CancelFleet` unless it is gone or already `ReturnFlight`. `CancelFleet` itself contains an additional attack-aware delay (`[RECALL-CHECK]`/`[RECALL-BLOCKED]` logic, [FleetScheduler.cs#L601-643](../../TBot/Workers/FleetScheduler.cs#L601)) that postpones a recall whose return trip would land before the last incoming attack; its Telegram notification is gated on `Defender.TelegramMessenger.Active` even though the delay logic is not.

## 7. Static state summary

| Container | Key | Value | Purpose |
|---|---|---|---|
| `_handledAttackIds` | attack ID | seen `DateTime` | 60-min dedupe of `HandleAttack` |
| `_scheduledFleetSaves` | celestial ID | `ScheduledFleetSave` | at most one pending fleetsave per celestial |
| `_awaySavedFleets` | celestial ID | `List<int>` fleet IDs | fleets away on defensive save, for recall |
| `_scheduledRecalls` | celestial ID | `ScheduledRecall` | at most one pending recall per celestial |

## 8. Configuration reference (`Defender.*`)

Values in the last column come from `TBot/instance_settings.json` (an example, not a default — the loader is schemaless, see §9).

| Path | Type / unit | Effect | Example |
|---|---|---|---|
| `Active` | bool | enables the worker | `true` |
| `CheckIntervalMin` / `CheckIntervalMax` | int, **minutes** | randomized poll interval; `<=0` → 20–50 s | `1` / `22` |
| `RandomActivity` | bool | fake-activity target: random celestial vs `Home` | `true` |
| `Home.Galaxy/System/Position/Type` | int/int/int/string(`Celestials`) | fixed fake-activity celestial | `1:1:1 Planet` |
| `Alarm.Active` | bool | local `ConsoleHelpers.PlayAlarm()` on detection | `true` |
| `TelegramMessenger.Active` | bool | Telegram attack/recall notices (also gates `CancelFleet` recall notices) | `false` |
| `WhiteList` | int[]/long[] | attacker IDs to ignore entirely; `0` = unknown attacker | `[0,100000,...]` |
| `IgnoreProbes` | bool | skip probe-only fleets (needs known composition) | `true` |
| `IgnoreWeakAttack` | bool | skip attacks below ratio (needs known composition) | `false` |
| `WeakAttackRatio` | int, divisor | attacker fleet points must be ≥ `myPoints / ratio`; **0 divides by zero** (caught, treated as threat) | `3` |
| `IgnoreAttackIfIHave.Active` | bool | enable worth-it check | `false` |
| `IgnoreAttackIfIHave.MinResourcesToSave` | long, resources | skip if both resource and fleet thresholds fail | `2000000` |
| `IgnoreAttackIfIHave.MinFleetToSave` | long, **points×1000** | compared against `fleetPoints * 1000` | `20000000` |
| `DefendFromMissiles` | bool (default true when absent) | build ABMs into silo space on IPM attack | `true` |
| `Autofleet.Active` | bool | scheduled defensive fleetsave | `true` |
| `SpyAttacker.Active` / `.Probes` | bool / int | counter-spy the attacker's origin from the attacked celestial | `true` / `20` |
| `MessageAttacker.Active` / `.Messages` | bool / string[] | random in-game message to attacker | `false` / `["hey",...]` |
| `Autofleet.TelegramMessenger.Active` | **inert** — code reads top-level `Defender.TelegramMessenger` only | — | `false` |

Keys consulted elsewhere but documented in [fleet-operations.md](fleet-operations.md): `General.SlotsToLeaveFree`, `SleepMode.*` (used by `AutoFleetSave`/`SendFleet` sleep gates), `Expeditions.IgnoreSleep`.

## 9. Settings-loader semantics (why "missing key" behaviour matters)

Settings are dynamic: `SettingsService.GetSettings` deserializes JSON into `ExpandoObject` → `ConfigObject` ([SettingsService.cs#L28](../../TBot.Common/Settings/SettingsService.cs#L28)); key casing is normalized to first-letter-upper by `JsonNetAdapter.Transform`. Any missing member returns a `NullExceptionPreventer` whose casts yield `false`/`0`/`null` ([SettingsService.cs#L301](../../TBot.Common/Settings/SettingsService.cs#L301)). Practical consequences:

- `(bool) Settings.Defender.Foo` on a missing key is `false`, and the surrounding `try/catch` in `IsWorkerEnabledBySettings` is belt-and-braces.
- Explicit `SettingsService.IsSettingSet(...)`/`GetSetting(...)` checks exist only where the code uses them; everywhere else a missing key silently behaves as the `NullExceptionPreventer` default. There is **no schema validation** of `Defender.*` — a typo like `CheckintervalMin` is a missing key, not an error (the `Transform` only uppercases the *first* letter, so `CheckintervalMin` ≠ `CheckIntervalMin`).
- `DefendFromMissiles` and the `WhiteList` type-tolerance are the only "absent means enabled/empty" special cases noted above.

## 10. Unknowns / caveats

- **Dedupe vs evolving attacks**: the 60-min `HandleAttack` dedupe keys on `attack.ID`; if the game re-issues the same ID with a changed fleet after a probe reveal, the update is ignored for the TTL. Verified in code; runtime impact not measured.
- **`MinFleetToSave` ×1000 scaling** is intentional-looking but undocumented outside this file; mis-tuning by 1000× is easy.
- **`WeakAttackRatio = 0`** division: the exception is caught by the outer `catch` at [L301](../../TBot/Workers/DefenderWorker.cs#L301) which logs and *continues* past the heuristics block — the attack then hits the `IgnoreAttackIfIHave`/fleetsave path. Not a crash, but the skip-heuristics silently disable.
- **ABM build has no resource gate** (§4.5) — relies on `BuildDefences` failing gracefully.
- **`_handledAttackIds` is never persisted**; restart re-handles recently seen attacks (fresh Telegram messages, re-scheduled saves). The 60-min TTL only bounds the in-memory set.
- **Static state and multiple instances**: all four containers are `static readonly`; two instances in one process share them keyed by celestial/attack ID — collision impact untested; no isolation guarantee.
- Nothing in this file sends fleets except through `FleetScheduler.SendFleet`/`AutoFleetSave`/`CancelFleet`; their gating (sleep windows, `SlotsToLeaveFree`, fuel) applies unchanged — see [fleet-operations.md §4–5](fleet-operations.md).

# Fleet operations — operator reference

Covers the fleet-sending workers and their shared substrate, as of commit `35b4ce0` (Go submodule `fbd0fda`). Line anchors are into the linked file. Companion page: [defender.md](defender.md).

Rule of thumb used throughout: **`RandomizeHelper.CalcRandomInterval(int min, int max)` interprets its arguments as MINUTES (`min * 60 * 1000`, [RandomizeHelper.cs#L27](../../TBot/Helpers/RandomizeHelper.cs#L27)); `CalcRandomIntervalSecToMs(min, max)` interprets seconds ([L34](../../TBot/Helpers/RandomizeHelper.cs#L34)); `CalcRandomInterval(IntervalType)` returns milliseconds directly ([L10](../../TBot/Helpers/RandomizeHelper.cs#L10)).** Several configs mix these; per-key units are listed in the tables.

## 1. Worker lifecycle substrate

- `WorkerBase` ([WorkerBase.cs](../../TBot/Workers/WorkerBase.cs)): every feature worker. `ExecutionWrapper` ([L153](../../TBot/Workers/WorkerBase.cs#L153)) ends the worker when `UserData.isSleeping` or `IsWorkerEnabledBySettings()` is false; otherwise `WaitWorker()` → `Execute()` → `ReleaseWorker()` on a one-shot `SemaphoreSlim`. `ChangeWorkerPeriod(ms)` re-arms the `AsyncTimer` — every worker sets its own next-run delay at the end of `Execute` (self-scheduling loop, not a fixed cron).
- `EndExecution()` ([L144](../../TBot/Workers/WorkerBase.cs#L144)) sets period to infinite; the factory (`WorkerFactory.InitializeWorker`, [WorkerFactory.cs#L37](../../TBot/Workers/WorkerFactory.cs#L37)) returns the existing instance for a `Feature`, so a stopped worker only runs again after an explicit `InitializeFeature`/start (e.g. Telegram `/startautofarm`, or `CheckCelestials` re-seeding `BrainAutoMine` on planet gain, [TBotOgamedBridge.cs#L329](../../TBot/Workers/TBotOgamedBridge.cs#L329)).
- `CelestialWorkerBase` ([CelestialWorkerBase.cs](../../TBot/Workers/CelestialWorkerBase.cs)) is the per-celestial variant used only by Brain mine/research workers; the workers in this document are all account-level `WorkerBase` subclasses.
- `WorkerFactory` shares one `SemaphoreSlim _brain` across all `IsBrain` features ([WorkerFactory.cs#L35](../../TBot/Workers/WorkerFactory.cs#L35), [L107](../../TBot/Workers/WorkerFactory.cs#L107)) — Brain workers serialize with each other; `Defender/Expeditions/Harvest/Colonize/AutoFarm/AutoDiscovery` do not participate.
- `ITBotOgamedBridge` / `TBotOgamedBridge` ([TBotOgamedBridge.cs](../../TBot/Workers/TBotOgamedBridge.cs)) is the data layer: `UpdatePlanet(celestial, UpdateTypes.X)` maps 1:1 onto `IOgameService` getters ([L45-129](../../TBot/Workers/TBotOgamedBridge.cs#L45)); every failure is logged and the *stale* celestial returned — callers never see a hard error from an update. `GetDateTime()` prefers server time, falls back to local clock ([L28](../../TBot/Workers/TBotOgamedBridge.cs#L28)). `CheckCelestials()` ([L320](../../TBot/Workers/TBotOgamedBridge.cs#L320)) diffs celestial counts, refreshes `UserData.celestials` deduplicated, and returns whether the set changed.

## 2. `FleetScheduler.SendFleet` — the single gate every fleet passes

[WorkerBase → FleetScheduler.cs#L441](../../TBot/Workers/FleetScheduler.cs#L441). `SendFleet(origin, ships, destination, mission, speed, payload = null, playerClass = NoClass, force = false)` returns `int`: a positive fleet ID, or a `SendFleetCode` ([SendFleetCode.cs](../../TBot.Ogame.Infrastructure/Enums/SendFleetCode.cs)): `GenericError = 0`, `AfterSleepTime = -1`, `NotEnoughSlots = -2`, `QuickerToWaitForProduction = -3`, `NotEnoughRessources = -4`.

Validation/gating order:

1. No movable ships → `GenericError`; expedition with probes-only → `GenericError`; origin == destination → `GenericError`.
2. Destination bounds: galaxy `1..serverData.Galaxies`, position `1..17` (16 = deep space accepted despite the message), system `1..serverData.Systems` with donut-galaxy wraparound ([L459-474](../../TBot/Workers/FleetScheduler.cs#L459)).
3. `speed` must be in `CalculationService.GetValidSpeedsForClass(playerClass)` ([L476](../../TBot/Workers/FleetScheduler.cs#L476)). Its General-specific finer grid is commented out at this baseline; all classes receive the same 10%-step list.
4. Flight time: `CalcFleetPrediction` on one-way `Time`; full trip = `2×time`, plus 3600 s hold for expeditions, round-up via `MidpointRounding.ToPositiveInfinity` ([L500-505](../../TBot/Workers/FleetScheduler.cs#L500)).
5. Fuel: origin deuterium (refreshed) ≥ predicted fuel; plus fuel *capacity* of the ships ≥ fuel (hyperspace tech, class, `serverData.ProbeCargo`) ([L513-531](../../TBot/Workers/FleetScheduler.cs#L513)).
6. **Sleep gate** ([L533-563](../../TBot/Workers/FleetScheduler.cs#L533)), unless `force`: when `SleepMode.Active` and `GoToSleep`/`WakeUp` parse —
   - `GeneralHelper.ShouldSleep(now, ...)` ([GeneralHelper.cs#L9](../../TBot/Helpers/GeneralHelper.cs#L9)) → `AfterSleepTime`;
   - return time inside tonight's sleep window → `AfterSleepTime`;
   - exception: `Missions.Expedition` with `Expeditions.IgnoreSleep` bypasses the return-window check only (the `ShouldSleep` immediate check still applies).
7. Slots: `UserData.slots = UpdateSlots()`; `Free == 0` → `NotEnoughSlots`; `Free > General.SlotsToLeaveFree || force` → send; else `NotEnoughSlots` ([L564-598](../../TBot/Workers/FleetScheduler.cs#L564)). Negative payload components are clamped to 0 (`Food` included for lifeforms).
8. Success appends the new fleet to `UserData.fleets` and refreshes slots again.

`SendFleet` never retries; callers implement their own retry/wait loops (§4.2, §6).

### 2.1 `CancelFleet` and recall protection

[CancelFleet, FleetScheduler.cs#L601](../../TBot/Workers/FleetScheduler.cs#L601): before recalling, if under attack it finds the *last* attack on the fleet's origin; if `currentFleet.ArriveIn * 2` (estimated return) < that attack's `ArriveIn`, the recall `Timer` is rescheduled to `attack.ArriveIn - estimatedReturn + 30%` (min 60 s) and a Telegram notice is sent — but only if `Defender.TelegramMessenger.Active` ([L631](../../TBot/Workers/FleetScheduler.cs#L631)). The actual recall path delays a few random seconds, calls `ogameService.CancelFleet`, refreshes fleets, and reports the new `BackTime`. `RetireFleet` ([L683](../../TBot/Workers/FleetScheduler.cs#L683)) is the `Timer` callback wrapper used by `AutoFleetSave`' recall timer.

### 2.2 Timer registry

`FleetScheduler` keeps named one-shot `Timer`s under `_timersLock`: `GhostSleepTimer` (delayed ghosting, §3) and `RecallTimer-<fleetId>` (deferred recalls). `ReplaceTimer`/`DisposeAndRemoveTimer` dispose-then-replace; exceptions on dispose are swallowed ([L48-64](../../TBot/Workers/FleetScheduler.cs#L48)).

## 3. `AutoFleetSave` and ghosting

[AutoFleetSave, FleetScheduler.cs#L153](../../TBot/Workers/FleetScheduler.cs#L153). Signature: `(celestial, isSleepTimeFleetSave = false, minDuration = 0 /*seconds*/, WaitFleetsReturn = false, TelegramMission = None, fromTelegram = false, saveall = false)`.

- **`WaitFleetsReturn` path (ghosting)**: computes when the last non-discovery fleet returns (`BackIn` max + random seconds); if positive and no `GhostSleepTimer` exists, it *stops* the feature list `Colonize, BrainAutoRepatriate, BrainAutoMine, BrainAutoResearch, BrainLifeformAutoMine, BrainLifeformAutoResearch, AutoFarm, Harvest, Expeditions, AutoDiscovery` ([L172-188](../../TBot/Workers/FleetScheduler.cs#L172) — note `BrainAutoMine` listed twice, harmless), sets `NextWakeUpTime`, and arms `GhostSleepTimer` → `GhostandSleepAfterFleetsReturn(All)` which fleetsaves (all celestials/moons when `saveall`) then `SleepNow(NextWakeUpTime)`. Interval 0 → ghost immediately. A already-planned timer → "try /cancelghostsleep".
- **Fleetsave path**: refreshes ships/resources; no movable ships or zero deuterium → skip with message. `payload` = current resources minus `SleepMode.AutoFleetSave.DeutToLeave` (when > 0).
  - `isSleepTimeFleetSave` derives `minDuration` from `SleepMode.WakeUp` (next occurrence; unparseable → abort) — the fleet must be gone until wake-up.
  - Mission fallback chain, each tried via `GetFleetSaveDestination` + cheapest-fuel-first (`OrderBy(Fuel).ThenBy(Duration <= minDuration)` — the `ThenBy` on a bool is a stable no-op-ish tiebreak):
    1. `SleepMode.AutoFleetSave.DefaultMission` (parsed; fallback log + `Harvest`); explicit `TelegramMission` overrides.
    2. If nothing sent: **`Deploy`** (regardless of the `mission == Harvest ? Deploy : Harvest` line at [L298](../../TBot/Workers/FleetScheduler.cs#L298) — the next statement hard-assigns `Missions.Deploy`).
    3. `Colonize` — only if a colony ship exists on the origin.
    4. `Spy` — only if probes exist.
    5. `Transport`.
  - Last resort: if the origin has a moon and no `GhostSleepTimer`, `TelegramSwitch(speed:10)` (moon↔planet shuttle, [L391-396](../../TBot/Workers/FleetScheduler.cs#L391)).
  - Nothing found → "you gonna get hit" warning.
- **`Recall`** ([L405-423](../../TBot/Workers/FleetScheduler.cs#L405)): `SleepMode.AutoFleetSave.Recall` && success → schedule `RetireFleet` at `minDuration/2` + 1–2 min (min-bounded only by the fallback). Recall respects the §2.1 attack check. Without recall, the fleet rides the full return.
- **Destination search** `GetFleetSaveDestination` ([L732](../../TBot/Workers/FleetScheduler.cs#L732)) per mission:
  - `Transport`: foreign planets ±5 systems (skip Vacation/Administrator/Banned/StrongPlayer), first speed whose `Duration ≥ minFlightTime/2` and `Fuel ≤ maxDeuterium`.
  - `Spy`: position 16 of ±5 systems, same duration/fuel rule; needs probes.
  - `Colonize`: empty slots 1–15 ±5 systems; needs colony ship.
  - `Harvest`: known debris fields ±5 systems; needs recyclers.
  - `Deploy`: own moons first, else any other own celestial; duration gate is `≥ minFlightTime` (not halved) — deploy is one-way so the full `minDuration` must be covered by a single leg.
  - Speeds iterate the class's list; first qualifying speed per destination wins.
- `CheckFuel` ([L720](../../TBot/Workers/FleetScheduler.cs#L720)) re-validates deuterium and capacity per candidate.

### 3.1 Repatriation & miner transports (same class, for completeness)

- `Collect()`/`CollectImpl` ([L1249](../../TBot/Workers/FleetScheduler.cs#L1249), [L1336](../../TBot/Workers/FleetScheduler.cs#L1336)): sends resources from every celestial to `Brain.AutoRepatriate.Target` (parsed list; `TargetAssociateMoon` → mirrored moon/planet; `Exclude`, `ExcludeMoons`, `RandomOrder`, `SkipIfIncomingTransport`, `MinimumResources`, `LeaveDeut.DeutToLeave`/`.OnlyOnMoons`, `CargoType` default `SmallCargo`). Returns `RepatriateCode` Success/Stop(`AfterSleepTime`)/Delay(`NotEnoughSlots`)/Failure.
- `CollectDeut(minAmount)` ([L1253](../../TBot/Workers/FleetScheduler.cs#L1253)): deuterium-only variant to the *single* `Brain.AutoRepatriate.Target` coords, `LargeCargo`/`AutoRepatriate.CargoType`.
- `HandleMinerTransport` (two overloads, [L941](../../TBot/Workers/FleetScheduler.cs#L941), [L1092](../../TBot/Workers/FleetScheduler.cs#L1092)): Brain transport sizing — `Brain.Transports.CargoType` (default `SmallCargo`), `Brain.Transports.DeutToLeaveOnMoons`, optional `RoundResources`, `DoMultipleTransportIsNotEnoughShipButSamePosition` (same-position partial send), "quicker to wait for production" skip (`SendFleetCode.QuickerToWaitForProduction`), and chain-loading the next building's cost while `flightTime*2 ≥ buildTime`. Details are Brain-domain; listed here because the slot accounting of `Missions.Transport` feeds every worker's priority table.

## 4. Fleet-slot priority algorithm

Every worker in this doc builds the same `List<RankSlotsPriority>` (Brain, Expeditions, AutoFarm, Colonize, AutoDiscovery, Harvest) and calls `CalcSlotsPriority(feature, ..., General.SlotsToLeaveFree)` ([CalculationService.cs#L4867](../../TBot/Includes/CalculationService.cs#L4867)):

- `RankSlotsPriority(feature, rank, active, maxSlots, slotsUsed)` — rank < 1 becomes `int.MinValue` = "no rank" ([RankSlotsPriority.cs#L11](../../TBot.Ogame.Infrastructure/Models/RankSlotsPriority.cs#L11)).
- With a rank: `available = slots.Total − SlotsToLeaveFree − Σ MaxSlots of *higher-priority* (lower rank) active features − Σ SlotsUsed of lower-priority active + used of inactive`; result clamped ≥ 0, then `min(available, MaxSlots − SlotsUsed)`; **the winner's own `MaxSlots` is mutated** down to `available` when larger ([L4919-4921](../../TBot/Includes/CalculationService.cs#L4919)).
- Rank ≤ 0: plain `slots.Free − SlotsToLeaveFree`.
- Per-feature `MaxSlots` sources in the shared table: Brain → `Brain.Transports.MaxSlots`; Expeditions → `slots.ExpTotal`; AutoFarm → `AutoFarm.MaxSlots`; Colonize → `AutoColonize.IntensiveResearch.MaxSlots` if IntensiveResearch active else **1**; AutoDiscovery/Harvest → their `MaxSlots`. Ranks: `General.SlotPriorityLevel.{Brain,Expeditions,AutoFarm,Colonize,AutoDiscovery,AutoHarvest}`; a rank of 0/unset means "no priority, use what's left" — the example sets `AutoHarvest: 99, AutoDiscovery: 10` etc.
- `AutoFarm` additionally pre-checks `freeSlots <= AutoFarm.SlotsToLeaveFree` at cycle start and aborts ([AutoFarmWorker.cs#L396](../../TBot/Workers/AutoFarmWorker.cs#L396)); `AutoDiscovery` checks `slots.Free <= General.SlotsToLeaveFree` per position ([AutoDiscoveryWorker.cs#L197](../../TBot/Workers/AutoDiscoveryWorker.cs#L197)).

## 5. Expeditions (`ExpeditionsWorker`)

[ExpeditionsWorker.cs](../../TBot/Workers/ExpeditionsWorker.cs). Enable: `Expeditions.Active`; the worker *also* hard-requires `researches.Astrophysics > 0`, else idles ~30 min (`AboutHalfAnHour`) ([L71-79](../../TBot/Workers/ExpeditionsWorker.cs#L71)).

Cycle:

1. Slot budget: `MaxSlots = slots.Total − General.SlotsToLeaveFree`. With `WaitForAllExpeditions`: send only when `ExpInUse == 0` (then all `ExpTotal`, else 0). Otherwise `expsToSend = min(ExpFree, Free)`. `WaitForMajorityOfExpeditions` zeroes the batch unless `expsToSend ≥ round(ExpTotal/2, ToZero) + 1`. Clamp to `MaxSlots`; ≤ 0 → idle ~5 min.
2. Origins: `Expeditions.Origin` list (coords + `Type`) resolved against `UserData.celestials` (**`.Single` — a bad entry throws** and falls into the catch that refreshes all celestials and picks the moon-first, largest-fleet celestial, [L182-201](../../TBot/Workers/ExpeditionsWorker.cs#L182)); no config → same largest-fleet pick. `Expeditions.RandomizeOrder` shuffles.
3. Per-origin cap: `Expeditions.MaxExpeditionsPerOrigin` (default **1** when the key is absent — `!= null` check at [L240](../../TBot/Workers/ExpeditionsWorker.cs#L240)); active expeditions counted by origin coords via `CountActiveExpeditionsFromOrigin` ([L52](../../TBot/Workers/ExpeditionsWorker.cs#L52)); remaining capacity distributed round-robin (`originExps` loop, [L277-297](../../TBot/Workers/ExpeditionsWorker.cs#L277)); total clamped to Σcapacity.
4. Fleet composition, per origin:
   - `ManualShips.Active`: exact `Ships` struct from `Expeditions.ManualShips.Ships.*` (constructor order: LF, HF, Cruiser, Battleship, BC, Bomber, Destroyer, RIP, SC, LC, Colony, Recycler, Probe, _, _, Reaper, Pathfinder — two unnamed zeros are `Star Gazer`-era slots); requires `HasAtLeast(fleet, expsToSendFromThisOrigin)` on the *live* origin.
   - else `PrimaryShip` (parse fail → `LargeCargo`; `Null` → skip origin) minus `PrimaryToKeep` (when > 0), sized by `CalcFullExpeditionShips(..., expsToSendFromThisOrigin, ...)`.
5. Destination: position 16 deep space. `SplitExpeditionsBetweenSystems.Active` → random system within `Range`, grown until `exps > range*2`, deduplicated within the pass via `syslist`, wrapped by `GeneralHelper.WrapSystem` ([L394-415](../../TBot/Workers/ExpeditionsWorker.cs#L394)); else the origin's own system.
6. `Expeditions.FuelToCarry > 0` → payload deuterium. Per send: re-check `ExpFree`; `SendFleet(..., Missions.Expedition, Speeds.HundredPercent, payload)`; `AfterSleepTime` → stop feature; `NotEnoughSlots` → delay. Between sends, wait `CalcRandomIntervalSecToMs(MinWaitNextFleet, MaxWaitNextFleet)` — **seconds** (example 5–15 s), swapped if inverted ([L464-475](../../TBot/Workers/ExpeditionsWorker.cs#L464)).
7. Next wakeup: no fleets or (free exp slots and neither Wait flag) → ~5 min; else soonest/most-distant (`WaitForAllExpeditions` → `OrderByDescending(BackIn)`) expedition `BackIn` + `SecToMs(MinWaitNextRound, MaxWaitNextRound)` (**seconds**; example 30–300 s).
8. `delay` path (slots vanished mid-run): next check = soonest fleet `BackIn` + random seconds, fallback `CalcRandomInterval(CheckIntervalMin, CheckIntervalMax)` — **minutes** (example unset in file; keys exist).

Config: `Expeditions.Active, IgnoreSleep, MinWaitNextFleet/MaxWaitNextFleet (s), PrimaryShip, PrimaryToKeep, ManualShips{Active,Ships{...}}, WaitForAllExpeditions, WaitForMajorityOfExpeditions, MinWaitNextRound/MaxWaitNextRound (s), SplitExpeditionsBetweenSystems{Active,Range}, RandomizeOrder, FuelToCarry, MaxExpeditionsPerOrigin, Origin[], CheckIntervalMin/Max (min, fallback paths only)`.
Example-only keys with **no reader at this commit**: `MinPrimaryToSend`, `SecondaryShip`, `MinSecondaryToSend`, `SecondaryToPrimaryRatio` — grep shows no consumption in `ExpeditionsWorker`; treat as dead config.

## 6. AutoFarm (`AutoFarmWorker`)

[AutoFarmWorker.cs](../../TBot/Workers/AutoFarmWorker.cs). The largest worker; two phases per cycle: **probe scan** then **attack**.

State files (per instance alias, under `AppDomain.BaseDirectory/data/`):

- `autofarm_blacklist_<alias>.json` — `AutoFarmBlacklist` ([Model/AutoFarmBlacklist.cs](../../TBot/Model/AutoFarmBlacklist.cs)): entries `{Coordinate, Reason, BlacklistedAt, ExpiresAt}`; `BlacklistReason ∈ {HasFleet, HasDefense, LowResources, ManuallyAdded}`; expiry checked on every read; whole-file rewrite on change; load failure → empty list.
- `autofarm_successful_<alias>.json` — `AutoFarmSuccessfulTargets` ([Model/AutoFarmSuccessfulTargets.cs](../../TBot/Model/AutoFarmSuccessfulTargets.cs)): `{Coordinate "g:s:p", FirstAttacked, LastAttacked, TimesAttacked, TotalLootCollected, AverageLoot}`; write-behind (60 s or 20 records), cap 5000 entries, 30-day stale purge, `.errors.log` sidecar; **written on every successful attack send** (`RecordAttack`, [AutoFarmWorker.cs#L1078](../../TBot/Workers/AutoFarmWorker.cs#L1078)) but never *read* by the pipeline at this commit — it is a statistics ledger (API: `GetTarget/GetAllTargets/GetTotalLootCollected`).
- `shared_farm_state.json` — `SharedFarmState` ([Model/SharedFarmState.cs](../../TBot/Model/SharedFarmState.cs)): cross-process coordination (heartbeats 5-min TTL, scan reservations 8 h, attack claims until `ReturnsAt` or 2 h unsent, named mutex `Global\TBot_SharedFarmState_Mutex` with `Local\` fallback, atomic `*Atomic` helpers). **Caveat: no file other than its own references `SharedFarmState` at this commit — the multi-instance farm coordination is dormant; only the blacklist/successes files are live.** Verify before relying on it.

### 6.1 Probe phase

1. `PruneOldReports` ([L59](../../TBot/Workers/AutoFarmWorker.cs#L59)): targets `AttackSent` or with report older than `KeepReportFor` **minutes** → reset to `ProbesPending`, report cleared.
2. Probe census per celestial (`GetCelestialProbes`, [L71](../../TBot/Workers/AutoFarmWorker.cs#L71)).
3. **Scan-range plan** ([L412-460](../../TBot/Workers/AutoFarmWorker.cs#L412)): `AutoFarm.ScanRange` entries `{Galaxy, StartSystem, EndSystem}`, ordered by galaxy then start. A *global spacing* scheme spreads instances: `minSpacing = 499` systems; `numSlotsGlobal = max(1, totalSystems/499)`; `globalSlotIndex = |hash(InstanceAlias)| % numSlotsGlobal`; start offset = index×499. Resume state persists in `UserData.autoFarmLastRangeIndex/Galaxy/System` (in-memory per session). First-ever run starts at the global-offset system within the matching galaxy's range.
4. Per system: `ShouldExcludeSystem` (Exclude entries **without** `Position` key), `GetScannedTargetsFromGalaxy` ([L98](../../TBot/Workers/AutoFarmWorker.cs#L98)): inactive, non-admin, non-banned, non-vacation planets; 5 retries on galaxy-page/503 errors with `retry*3 s` backoff; on the 4th retry with `serverData.Systems == 0` it **kills and reruns ogamed** ([L124-143](../../TBot/Workers/AutoFarmWorker.cs#L124)); finally drops targets that already have an inbound `Missions.Attack`.
5. `ExcludeMoons == false` → moons of scanned planets appended (`AddMoons`, [L193](../../TBot/Workers/AutoFarmWorker.cs#L193); the moon reuses the planet's coordinate object with `Type` overwritten — copies, does not mutate the original list element).
6. Per target: `MinimumPlayerRank` (when set and ≠ 0) requires player rank ≤ configured; moons inherit the planet's rank via galaxy lookup. `ShouldExcludePlanet` (Exclude entries **with** `Position`). `GetFarmTarget` ([L221](../../TBot/Workers/AutoFarmWorker.cs#L221)): blacklist check first (`AutoFarm.Blacklist.Active`), dedupe (`CheckDuplicatesAndGetExisting` keeps first of duplicates), `Idle→ProbesPending`, `NotSuitable` with report → skip, `ProbesSent/AttackPending` → skip.
7. Probe count: `NumProbes`, ×3 in `ProbesRequired`, ×9 in `FailedProbesRequired` (`GetNeededProbes`, [L256](../../TBot/Workers/AutoFarmWorker.cs#L256)).
8. Origin: `AutoFarm.Origin` list else all celestials; ordered moons-first then nearest (`OrderByDescending(Type==Moon)` — true sorts first in descending, so **moons preferred**); `GetBestOrigin` ([L282](../../TBot/Workers/AutoFarmWorker.cs#L282)) picks the first with enough probes; else waits for returning spy fleets when `freeSlots <= SlotsToLeaveFree`; else considers building probes (`Shipyard/Nanite` construction or existing probe production blocks; cost check via `CalcPrice`). Waits happen inline (`Task.Delay`), up to the returned fleet's `BackIn`.
9. Send: `WaitForFreeSlots` loop (soonest fleet `BackIn` + <1 s; throws if none returning); up to 5 retries on `NotEnoughSlots` ("another worker took the slot"); `AfterSleepTime` ends the worker (`stop`). Success → `farmTargets.State = ProbesSent`, `numProbed++`.
10. `TargetsProbedBeforeAttack` (≠0) caps probes per cycle, remembering the exact resume position; position exhaustion resets the cursor; a completed full scan resets it to 0 and — with `StopAfterFullScan` — stops the worker until manually restarted ([L720-742](../../TBot/Workers/AutoFarmWorker.cs#L720), [L1097-1099](../../TBot/Workers/AutoFarmWorker.cs#L1097)).

### 6.2 Report processing (`AutoFarmProcessRecords`, [L1133](../../TBot/Workers/AutoFarmWorker.cs#L1133))

For every espionage summary (non-`Action`): expired per `KeepReportFor` → delete; matched target or (inactive && galaxy re-lookup) → evaluate:

- Older than current knowledge → delete, skip.
- Loot gate by `PreferedResource` (**sic** — the setting and code both spell it with one 'r'; `""` = total) against `MinimumResources`.
- Missing fleet/defense info → escalate `ProbesRequired → FailedProbesRequired → NotSuitable` (next cycle sends ×3/×9 probes).
- `report.IsDefenceless(isUsingProbes)` (`isUsingProbes` = `CargoType==EspionageProbe && serverData.ProbeCargo==1`) → `AttackPending`.
- Defenses present → `NotSuitable` + blacklist `HasDefense` for `Blacklist.ResetAfterHours` (default **48** via `GetSetting`).
- Loot under threshold → `NotSuitable` + blacklist `LowResources` when below `Blacklist.MinimumResourcesToNotBlacklist` (default **500000**).
- Unmatched reports processed only with `ProcessAllReports` (read from `AutoFarm` **or** `AutoFarm.Blacklist`) — lets manually made espionages enter the pipeline.
- Finishes with `DeleteAllEspionageReports`, 3 retries on 503.

### 6.3 Attack phase

1. Slot budget: shared priority table → `MaxSlots` (§4).
2. Targets: `AttackPending` sorted by loot of `PreferedResource` (fallback total). None → return.
3. Cargo ship: `CargoType` (parse-fail → `LargeCargo`; `Null` → abort; `EspionageProbe` requires `serverData.ProbeCargo == 1`).
4. Per target: `numCargo = CalcShipNumberForPayload(loot)` `+ CargoSurplusPercentage%` (when > 0). Origin search: moons-first/distance-sorted celestials needing `amount ≥ numCargo + MinCargosToKeep`, fuel, `MaxFlightTime` (0/absent = unlimited; else **seconds**). Speed: `MinLootFuelRatio > 0` → `CalcOptimalFarmSpeed(loot, ratio, maxFlightTime default 86400 s)` ([ICalculationService.cs#L58](../../TBot/Includes/ICalculationService.cs#L58)); else/if 0 → `FleetSpeed/10` (config in percent; validated for class; invalid → 100%); else 100%.
5. No fully-stocked origin → fallback path allows building: `BuildCargos` → build deficit (or max affordable via `CalcMaxBuildableNumber`) and wait production; requires `available − MinCargosToKeep ≥ MinCargosToSend`; then `numCargo = available − MinCargosToKeep` (**note: the surplus-adjusted count is replaced by "everything above reserve"**).
6. Slot wait: same loop as probes but bounded by `MaxWaitTime` (**seconds**; `interval > MaxWaitTime*1000` → stop cycle) ([L996-1013](../../TBot/Workers/AutoFarmWorker.cs#L996)); gate `slotUsed(Attack) < MaxSlots` and `slots.Free > AutoFarm.SlotsToLeaveFree`; ships re-read; deficit vs `numCargo` re-checked with capacity (`CalcFleetCapacity`) — smaller fleet only sent if it still carries the full loot.
7. `SendFleet(..., Missions.Attack, speed)`; success → `RecordAttack` + `AttackSent`; `AfterSleepTime` → stop.
8. Next run: soonest-returning attack `BackIn` + random seconds; no attacks → `CalcRandomInterval(CheckIntervalMin, CheckIntervalMax)` — **minutes** (example 30–60 → 30–60 min? no: 30–60 **minutes**; the example's intent may have been seconds — see caveats).

### 6.4 AutoFarm config table

| Path | Unit / notes |
|---|---|
| `Active` | master switch (also gates `IsWorkerEnabledBySettings`) |
| `ScanRange[] {Galaxy,StartSystem,EndSystem}` | galaxies/systems to farm; ordered; global 499-system instance spacing |
| `Exclude[] {Galaxy,System[,Position]}` | `Position` key presence switches system- vs planet-level exclude |
| `ExcludeMoons` | true = planets only |
| `MinimumPlayerRank` | 0/absent = disabled |
| `TargetsProbedBeforeAttack` | 0/absent = unlimited probes per cycle |
| `StopAfterFullScan` | stop worker after a complete pass |
| `NumProbes` | base probe count; ×3 / ×9 escalations |
| `BuildProbes`, `BuildCargos` | allow shipyard fills |
| `Origin[]` | restrict launch celestials; empty = all |
| `KeepReportFor` | **minutes** |
| `SlotsToLeaveFree` | per-feature reserve (checked *in addition to* priority alg) |
| `MaxSlots` | priority-alg ceiling |
| `PreferedResource` | `Metal/Crystal/Deuterium/""`; typo is canonical |
| `MinimumResources` | loot gate |
| `CargoType` | any `Buildables`; probe-cargo caveat above |
| `MinCargosToKeep`, `MinCargosToSend` | reserves per origin |
| `CargoSurplusPercentage` | % extra cargos |
| `MinLootFuelRatio` | fuel-per-loot optimality; **in-code default when absent: 0.0001** ([L836](../../TBot/Workers/AutoFarmWorker.cs#L836)); example 0.5 |
| `FleetSpeed` | percent, `/10` → speed enum; invalid → 100% |
| `MaxFlightTime` | **seconds**; 0/absent = unlimited (optimal-speed path defaults 86400 s) |
| `MaxWaitTime` | **seconds**; slot-wait ceiling in attack phase |
| `CheckIntervalMin/Max` | **minutes** (idle fallback) |
| `Blacklist.{Active,ResetAfterHours (h, default 48),MinimumResourcesToNotBlacklist (default 500000),ProcessAllReports}` | see §6.2 |
| `ProcessAllReports` (feature level) | process foreign espionages |

## 7. Harvest (`HarvestWorker`)

[HarvestWorker.cs](../../TBot/Workers/HarvestWorker.cs). Enable `AutoHarvest.Active`. Per cycle:

1. For every planet (and its moon, if present): collect candidate destinations into `dic` —
   - `HarvestOwnDF`: own debris at the planet's coords if `≥ MinimumResourcesOwnDF`; origin prefers moon recyclers (`≥ RecyclersNeeded`, else any) then planet recyclers.
   - `HarvestDeepSpace`: position 16; if `Expeditions.SplitExpeditionsBetweenSystems.Active`, the ±`Range` system band (wrapped) else own system; `ExpeditionDebris ≥ MinimumResourcesDeepSpace`; origin prefers moon pathfinders then planet pathfinders. **Reads `Expeditions.*` — Harvest depends on the Expeditions config block even when Expeditions is disabled.**
   - Destinations already covered by an active `Missions.Harvest` fleet are skipped; `dic` dedupes by coords.
2. Slot budget via shared priority table (`AutoHarvest` rank `General.SlotPriorityLevel.AutoHarvest`, example 99 = lowest); `dic` trimmed to `MaxSlots` (arbitrary dictionary order — not priority-ranked).
3. Sends: position 16 → pathfinders (`CalcShipNumberForPayload` capped by available); planet debris → recyclers, both at 100% via `SendFleet`; `AfterSleepTime` stop, `NotEnoughSlots` delay.
4. Next run: soonest harvest fleet `BackIn`, else `CalcRandomInterval(AutoHarvest.CheckIntervalMin, Max)` — **minutes** (example 30–60).

Config: `AutoHarvest.{Active, HarvestOwnDF, HarvestDeepSpace, MinimumResourcesOwnDF, MinimumResourcesDeepSpace, MaxSlots, CheckIntervalMin, CheckIntervalMax}`. **No per-feature `SlotsToLeaveFree`** — global only. Debris freshness is whatever the galaxy view returns; there is no re-validation between collection and send beyond the fleet-dup check.

## 8. AutoDiscovery (`AutoDiscoveryWorker`)

[AutoDiscoveryWorker.cs](../../TBot/Workers/AutoDiscoveryWorker.cs). Enable `AutoDiscovery.Active`.

- **Blacklist**: in-memory `UserData.discoveryBlackList` (`Dictionary<Coordinate,DateTime>`, custom `CoordinateComparer` including `Type`); `EnsureBlacklistInitialized` repairs a wrong-comparer dictionary keeping the furthest expiry ([L73-94](../../TBot/Workers/AutoDiscoveryWorker.cs#L73)); entries expire by timestamp; **not persisted** — restart clears it.
- **Origins**: `AutoDiscovery.Origin[]` resolved against fresh `GetCelestials()`; unresolved entries warn; none → stop worker ([L344-348](../../TBot/Workers/AutoDiscoveryWorker.cs#L344)).
- **Cursor**: per-origin `OriginCursor{System,NextPosition}` walks position 1..15, then `AdvanceSystem` wraps at `serverData.Systems`; in-memory only, resets on restart to the origin's own system ([L156-178](../../TBot/Workers/AutoDiscoveryWorker.cs#L156)).
- **Send loop** (`ProcessOneSystemForOrigin`, [L180](../../TBot/Workers/AutoDiscoveryWorker.cs#L180)): respects `General.SlotsToLeaveFree` (hard stop when `Free <=`), global attempt cap `MaxGlobalAttempts = 600`; per position: blacklist skip → `ogameService.SendDiscovery(origin, dest)`; **both success and failure blacklist the position for 7 days** ([L208-216](../../TBot/Workers/AutoDiscoveryWorker.cs#L208)) — a failed send is not retried until expiry. Slots refreshed after each send.
- Budget: shared priority table → `fleetsToSend`; 0 → delay. `GetAvailableDiscoveries(origin)` gates per origin.
- Next run: soonest discovery fleet `BackIn` + random seconds, else `CalcRandomInterval(AutoDiscovery.CheckIntervalMin, Max)` — **minutes**.
- `SleepMode.Active` + `ShouldSleep` → stop feature until re-enabled; `UserData.isSleeping` likewise.

Config: `AutoDiscovery.{Active, Origin[], MaxSlots, CheckIntervalMin/Max (min)}`. Example keys `MaxFailures`, `RandomizeDestination` have **no reader in this worker** at this commit (dead config; `MaxFailures` may be consumed elsewhere — unverified).

## 9. Colonize / Abandon / IntensiveResearch (`ColonizeWorker`)

[ColonizeWorker.cs](../../TBot/Workers/ColonizeWorker.cs). Enable split in two: `AutoColonize.Abandon.Active` gates abandoning; `AutoColonize.Active` gates colonizing. `Execute` runs abandon first, then colonize, then reschedules.

### 9.1 Abandon

- **Fast watcher** ([L370-433](../../TBot/Workers/ColonizeWorker.cs#L370)): `EnsureAbandonWatcherRunning` starts a background loop (idempotent) that sleeps until the next inbound `Missions.Colonize` fleet lands (`ArriveIn` + random seconds; 20 s idle poll otherwise) and then runs `CheckAndAbandonUnfitPlanets` — so a bad planet is dropped seconds after colonization instead of waiting the (minutes) Execute period. Stops with the worker token; re-checked enabled-state each pass.
- **Check** (`CheckAndAbandonUnfitPlanets`, [L440](../../TBot/Workers/ColonizeWorker.cs#L440)): guarded by `SemaphoreSlim _abandonLock` with `WaitAsync(0)` — concurrent passes are *skipped*, not queued. For each planet with `Fields.Built == 0` (freshly colonized only): `CalculationService.ShouldAbandon(planet, fieldsTotal, tempMax, fieldsSettings{Total = Abandon.MinFields}, temperatures{Min/Max = Abandon.Min/MaxTemperatureAcceptable})` → `ogameService.AbandonCelestial`. **Only brand-new planets are ever abandoned**; an existing planet that fails the criteria is kept. Settings can flip off mid-check (re-checked per planet).

### 9.2 Colonize

1. `maxPlanets = CalcMaxPlanets(researches)` (astrophysics-driven); `currentPlanets` = owned planets; `slotsToLeaveFree = AutoColonize.SlotsToLeaveFree ?? 0` (**nullable — absent key = 0**, unlike most numeric settings); proceed only if `current + slotsToLeaveFree < maxPlanets`.
2. Slot budget via shared priority table; Colonize `MaxSlots` = `IntensiveResearch.MaxSlots` when active else 1 (§4) — without IntensiveResearch at most **one** colonize fleet is attributable to the feature per the priority algebra, though the explicit in-flight check below is the operative gate.
3. In-flight gate ([L124-132](../../TBot/Workers/ColonizeWorker.cs#L124)): normal mode waits while `colonize-fleets-not-returning ≥ maxPlanets − current`; IntensiveResearch mode waits while **any** colonize fleet is outbound (one at a time). Wait = soonest `ArriveIn` + <5 s.
4. Origin: **single** `AutoColonize.Origin{Galaxy,System,Position,Type}`; `.Single(...)` — misconfiguration throws → error path reschedules by `CheckIntervalMin/Max` (**minutes**).
5. `neededColonizers = maxPlanets − current − slotsToLeaveFree`; if the origin lacks them: production-aware logic — if colony ships are already being built, wait for the queue; else build `needed − owned` when `Shipyard ≥ 4 && ImpulseDrive ≥ 3` and resources suffice; else log requirements. `interval` accumulates production times.
6. Target selection from `AutoColonize.Target[] {Galaxy,StartSystem,EndSystem,StartPosition,EndPosition,MaxPlanets}`:
   - Skip ranges already at `MaxPlanets` owned fitting planets (`CountPlanetsInRange` with `Abandon.MinFields`, temp window).
   - Cartesian systems×positions filtered by `IsAstrophysicsPositionValid` (position 9 needs astrophysics etc.), not owned, empty in galaxy scan.
   - `RandomPosition` → shuffled; then IntensiveResearch takes `MaxSlots` candidates, normal mode `maxPlanets − current`; final order by flight time from origin.
   - Per target: skip if a colonize fleet already inbound there; `SendFleet(1 ColonyShip, Missions.Colonize, 100%)`; `AfterSleepTime` stop; `NotEnoughSlots` → delay to soonest fleet.
   - **Inter-send wait** ([L261-280](../../TBot/Workers/ColonizeWorker.cs#L261)): `IntensiveResearch.Min/MaxWaitNextFleet` — a random wait (**seconds**, via `CalcRandomIntervalSecToMs`) is applied only when the *next* target's flight time is within `MaxWaitNextFleet` (seconds) of the current one; the initializer `var rndWaitTimeMs = 0; //(int) ...` at [L269](../../TBot/Workers/ColonizeWorker.cs#L269) is commented-out dead text, the conditional assignment below is live. In non-IntensiveResearch mode these keys are still read ([L261](../../TBot/Workers/ColonizeWorker.cs#L261) — outside the `Active` check? no: read unconditionally within the send loop) — **they apply in both modes**; negative mins clamp to 0, max < 1 clamps to 1.
7. Reschedule: production wait, or next-colonize `ArriveIn`, or `CheckIntervalMin/Max` minutes; `≤0` → 1–2 min.

### 9.3 IntensiveResearch semantics summary

`AutoColonize.IntensiveResearch.{Active,MaxSlots,MinWaitNextFleet,MaxWaitNextFleet}`: when active, colonization is single-flight (any outbound blocks a new one), candidate list expands to `MaxSlots`, waits use the Min/Max pair. `MaxSlots` also feeds the shared priority table (Colonize row) in *all* modes via the ternary at [AutoFarmWorker.cs#L783](../../TBot/Workers/AutoFarmWorker.cs#L783) et al.

## 10. Cross-feature interactions (map)

- **Slots** are the global contention point: `General.SlotsToLeaveFree` + per-feature `MaxSlots`/ranks (§4); `SendFleet` is the final arbiter and returns `NotEnoughSlots` which every worker treats as "delay".
- **Sleep**: `SleepMode.Active/GoToSleep/WakeUp` gate `SendFleet` (§2.6); `WorkerBase` ends workers while `isSleeping`; `AutoFleetSave(isSleepTimeFleetSave)` + `GhostSleepTimer` coordinate the transition; `Expeditions.IgnoreSleep` punches a hole for expeditions only.
- **Defender ↔ FleetScheduler**: defender fleetsaves are `AutoFleetSave(minFlightTime = remaining×1.3)`; recalls route through `CancelFleet`'s attack-aware delay; defender Telegram gates appear inside scheduler code ([FleetScheduler.cs#L631](../../TBot/Workers/FleetScheduler.cs#L631), [L659](../../TBot/Workers/FleetScheduler.cs#L659)).
- **Colonize ↔ Brain**: `CheckCelestials` fires `InitializeFeature(BrainAutoMine)` on planet gain ([TBotOgamedBridge.cs#L329](../../TBot/Workers/TBotOgamedBridge.cs#L329)); abandon frees slots for the next colonization within seconds.
- **Harvest ↔ Expeditions**: deep-space harvest range reuses `Expeditions.SplitExpeditionsBetweenSystems.Range`.
- **AutoFarm ↔ ogamed**: galaxy-scan 503 handling restarts the ogamed process ([AutoFarmWorker.cs#L124](../../TBot/Workers/AutoFarmWorker.cs#L124)) — affects every worker sharing the process-wide ogamed instance.
- **Shared `UserData` mutation**: `UserData.fleets/celestials/slots` are overwritten wholesale by many workers; `FleetScheduler` guards `UserData.fleets = ...` with `_fleetLock` in `CancelFleet` ([L651](../../TBot/Workers/FleetScheduler.cs#L651)), but that does not synchronize all writers. Race impact has not been measured; do not assume timer-based scheduling makes it safe.

## 11. Known code caveats (verified at `35b4ce0`)

1. `AutoFleetSave` mission fallback: dead `mission == Harvest ? ...` expression, `Deploy` always follows ([FleetScheduler.cs#L298-299](../../TBot/Workers/FleetScheduler.cs#L298)).
2. `GhostSleepTimer` feature-stop list contains `BrainAutoMine` twice ([L174-180](../../TBot/Workers/FleetScheduler.cs#L174)).
3. AutoFarm logs slot warnings under `LogSender.FleetScheduler` ([AutoFarmWorker.cs#L398](../../TBot/Workers/AutoFarmWorker.cs#L398)).
4. `CalcSlotsPriority` mutates the passed `RankSlotsPriority.MaxSlots` — repeated calls in one process see the reduced value ([CalculationService.cs#L4921](../../TBot/Includes/CalculationService.cs#L4921)).
5. Mixed interval units per key — see tables; the risky pairs are `MaxWaitTime` (s) vs `CheckInterval*` (min) inside AutoFarm, and Colonize's `CheckInterval*` (min) vs `IntensiveResearch.*WaitNextFleet` (s).
6. `SharedFarmState` and parts of `Expeditions`/`AutoDiscovery` example config are unwired at this commit (§5, §8, §6 intro).
7. `SpiesCrash`/`SpyCrash` ([FleetScheduler.cs#L82](../../TBot/Workers/FleetScheduler.cs#L82)) deliberately sends a single probe as a *sacrificial* attack to generate debris — Telegram-driven, unrelated to Defender.
8. `AutoFarmSuccessfulTargets` is write-only in the live path (statistics; exposed via API only if something calls `GetTarget` — none found in `TBot/` at this commit).

## 12. Uncertainty register

- `CalcFullExpeditionShips`, `CalcOptimalFarmSpeed`, `CalcSlotsPriority` internals live in `TBot/Includes/CalculationService.cs` (~5k lines) and were consulted only at the call sites documented; their exact heuristics are **not** restated here.
- `Missions`/`CharacterClass`/`Speeds` enum precise values (submodule `TBot.Ogame.Infrastructure`) were not re-derived; `Speeds.HundredPercent`'s numeric value is not asserted anywhere in this doc.
- Runtime behaviour under concurrency (two workers racing `UserData.fleets`) is inferred from code, not measured.
- `instance_settings.json` values quoted are the repo example, not defaults: the loader has no schema, so *absent key* semantics (`NullExceptionPreventer` → `false/0/null`, [SettingsService.cs#L301](../../TBot.Common/Settings/SettingsService.cs#L301)) always apply — an omitted `SlotsToLeaveFree` behaves as 0, an omitted `MaxSlots` as 0 (**which zeroes the feature's budget in the priority algorithm** — configure it explicitly).

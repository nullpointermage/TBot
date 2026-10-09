# Fleet/Defender documentation — evidence & findings

Work record for `docs/features/fleet-operations.md` and `docs/features/defender.md`.
Inventory of every file read in full (path, sha256, line count, symbols): `fleet-read.json` (same directory).
Repo: `/home/kelsier/Projects/TBot/source`, HEAD `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`, submodule `ogame` `fbd0fda6ba9019c128926614f9865ba38a67b627` (both verified via `git log`/`git submodule status`).

## Coverage

All 18 files in `fleet-files.json` read end-to-end (7,144 lines total). Supporting sources consulted for cross-references only: `TBot.Common/Settings/SettingsService.cs` (dynamic settings + `NullExceptionPreventer` defaults), `TBot/Helpers/RandomizeHelper.cs` (interval units), `TBot/Helpers/GeneralHelper.cs` (`ShouldSleep/ClampSystem/WrapSystem`), `TBot/Includes/CalculationService.cs` (`CalcSlotsPriority` L4867–4930), `TBot.Ogame.Infrastructure/Models/RankSlotsPriority.cs`, `Enums/FarmState.cs`, `Enums/SendFleetCode.cs`, `TBot/Models/IntervalType.cs`, `TBot/instance_settings.json` (example values).

## Key findings encoded into the docs

1. **Interval units are heterogeneous and trap-prone.** `CalcRandomInterval(int,int)` = minutes→ms; `CalcRandomIntervalSecToMs` = seconds→ms; `IntervalType` overloads = ms. Defender/AutoFarm-Harvest-Discovery-Colonize `CheckInterval*` are **minutes**; AutoFarm `MaxWaitTime`/`MaxFlightTime` and Expeditions `Min/MaxWaitNext*` are **seconds**; AutoFarm `KeepReportFor` is minutes. Documented per key.
2. **`SharedFarmState` is dormant** — zero references outside its own file at this commit; multi-instance farm coordination (claims/scans/mutex) exists but is unwired. Only `AutoFarmBlacklist` and `AutoFarmSuccessfulTargets` files are live, and the successes ledger is write-only in the live path.
3. **`AutoFarmSuccessfulTargets.RecordAttack` fires on every successful attack send** (AutoFarmWorker L1078) — 60 s/20-change write-behind, 5k cap, 30-day prune, `.errors.log` sidecar.
4. **Defender static state**: 4 `ConcurrentDictionary`s (dedupe 60 min TTL; per-celestial scheduled saves replaced only by earlier arrivals; away-fleets; pending recalls 30–90 s). `MinFleetToSave` compared against `fleetPoints*1000`; `WeakAttackRatio=0` divides by zero but is caught; ABM restock has no resource check; nested `Autofleet.TelegramMessenger` config is inert (top-level key is the live one).
5. **Defender fleetsave scheduling**: send at T-minus 30–60 s, `minFlightTime = remaining×1.3 + jitter`, recall only when the attacker disappears, with a fresh-attack re-check and FleetScheduler-side `[RECALL-BLOCKED]` postponement.
6. **Slot priority algebra** (`CalcSlotsPriority`): rank-sorted reservation; mutates the winner's `MaxSlots`; absent `MaxSlots` keys behave as 0 and zero the feature budget — flagged for operators.
7. **Colonize**: abandon touches only `Fields.Built == 0` planets; background watcher lands-check is idempotent and lock-guarded (`WaitAsync(0)` skip); `SlotsToLeaveFree` is nullable (absent = 0, unlike the global `NullExceptionPreventer` int default — same result, different mechanism); IntensiveResearch forces single-flight colonization; `Min/MaxWaitNextFleet` apply in both modes and are seconds.
8. **Expeditions**: `MaxExpeditionsPerOrigin` defaults to 1 when the key is absent; `MinPrimaryToSend/Secondary*` example keys have no reader (dead config); astrophysics > 0 hard requirement; origin parse uses `.Single` (throws on dupes).
9. **AutoFarm global scan spacing**: 499-system inter-instance slotting hashed on `InstanceAlias`; resume cursor in-memory only; ogamed kill+restart on 4th retry with broken `serverData.Systems`.
10. **FleetScheduler**: mission fallback chain hard-codes `Deploy` after the preferred mission (dead ternary L298); `Deploy` destination gate uses full `minFlightTime` (others half); expedition flight time +3600 s hold; `GhostSleepTimer` stops a feature list (with a duplicated `BrainAutoMine` entry); `CancelFleet` attack-aware recall postponement gated Telegram-wise on `Defender.TelegramMessenger`.

## Interface classification

- **Public API surface (in-repo consumers verified)**: `IFleetScheduler` methods used by all workers (`SendFleet/CancelFleet/UpdateFleets/AutoFleetSave/Collect*/HandleMinerTransport*`); `ITBotOgamedBridge` (data reads; never throws to callers); `IWorkerFactory` (`InitializeWorker` per `Feature`, brain semaphore sharing).
- **Internal/state classes**: `DefenderWorker` (+3 private state classes), `ScheduledFleetSave/ScheduledRecall`, `SpyOriginResult`, `OriginCursor`, `DiscoveryRunContext`, `CoordinateComparer` — private or internal, no external contract.
- **Persistence files** (runtime data, not config): `data/autofarm_blacklist_<alias>.json`, `data/autofarm_successful_<alias>.json`, `data/shared_farm_state.json` (dormant), plus `autofarm_successful_targets.errors.log`.
- **Unknowns**: numeric values of `Speeds.*`/`Missions.*` enums (submodule); internals of `CalcFullExpeditionShips`/`CalcOptimalFarmSpeed`; `MaxFailures`/`RandomizeDestination` consumers outside the assigned file set; runtime concurrency behaviour (inferred, not measured). No in-game actions were performed; no source/config files modified beyond the two docs and the two evidence files listed above.

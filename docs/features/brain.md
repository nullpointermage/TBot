# Brain workers — feature reference (`TBot/Workers/Brain` + `TBot/Includes/CalculationService`)

Source of truth: commit `35b4ce08b57bf2900d5b3d3b449a3f26f168270b` (branch `docs/comprehensive-handbook`), submodule `TBot.Ogame.Infrastructure` @ `fbd0fda6ba9019c128926614f9865ba38a67b627`.
All `file:line` references below are exact at that commit. Read evidence (sha256 per file, symbol lists):
`docs/reference/brain-read.json`, findings: `docs/reference/brain-findings.md`.

The 14 audited files (8 831 lines, all read in full):

| File | Lines | Role |
|---|---|---|
| `TBot/Includes/CalculationService.cs` | 5068 | All game-math helpers (see [calculations.md](../calculations.md)) |
| `TBot/Includes/ICalculationService.cs` | 162 | Interface (the contract every worker consumes) |
| `TBot/Workers/Brain/AutoMineWorker.cs` | 157 | Planet/moon dispatcher for mining |
| `TBot/Workers/Brain/AutoMineCelestialWorker.cs` | 803 | Per-celestial build executor + transports |
| `TBot/Workers/Brain/AutoResearchWorker.cs` | 535 | Research executor + transports |
| `TBot/Workers/Brain/LifeformsAutoMineWorker.cs` | 183 | Lifeform-building dispatcher |
| `TBot/Workers/Brain/LifeformsAutoMineCelestialWorker.cs` | 523 | Per-planet LF build executor + transports |
| `TBot/Workers/Brain/LifeformsAutoResearchWorker.cs` | 132 | LF-tech dispatcher |
| `TBot/Workers/Brain/LifeformsAutoResearchCelestialWorker.cs` | 491 | Per-planet LF-tech executor + transports |
| `TBot/Workers/Brain/AutoCargoWorker.cs` | 169 | Cargo-ship top-up |
| `TBot/Workers/Brain/AutoDefenceWorker.cs` | 157 | Defence top-up |
| `TBot/Workers/Brain/AutoRepatriateWorker.cs` | 76 | Fleet recall scheduler |
| `TBot/Workers/Brain/AutoFleetJumpGateWorker.cs` | 307 | Jump-gate fleet redistribution |
| `TBot/Workers/Brain/BuyOfferOfTheDayWorker.cs` | 68 | Daily-offer buyer |

---

## 1. Common skeleton

Every Brain worker derives from `WorkerBase` (or `CelestialWorkerBase` for per-celestial executors) and implements:

- `IsWorkerEnabledBySettings()` — the gate. Always `Brain.Active && <feature>.Active` cast to `bool` inside `try/catch`, returning `false` on any exception
  (e.g. `AutoMineWorker.cs:40-46`). Consequence: a malformed settings object silently disables the feature, it never throws at startup.
- `GetWorkerName()` / `GetFeature()` / `GetLogSender()` — identity used by logging and by the slot-priority table (`Feature.BrainAutoMine`,
  `BrainAutoResearch`, `BrainLifeformAutoMine`, `BrainLifeformAutoResearch`, `BrainAutobuildCargo`, `BrainAutobuildDefence`,
  `BrainAutoRepatriate`, `BrainAutoFleepJumpGate` ← note the *Fleep* misspelling, `BrainOfferOfTheDay`).
- `Execute()` — one pass; rescheduling happens at the end via `ChangeWorkerPeriod(intervalMs)`.

Recurring behaviours:

- **Random order.** Dispatcher workers honour `<feature>.RandomOrder` by `Enumerable.Shuffle(...)` (AutoMineWorker.cs:137, AutoCargoWorker.cs:43,
  AutoDefenceWorker.cs:54). AutoMine shuffles *after* sorting planets by DOIR, so `RandomOrder=true` discards the DOIR priority.
- **Exclude lists.** `ParseCelestialsList(dynamic, celestials)` (CalculationService.cs:4736-4758) maps settings entries `{Galaxy,System,Position,Type}`
  onto known celestials; unknown entries are dropped silently. Checked with `celestialsToExclude.Has(celestial)`.
- **Sleep mode.** The common worker wrapper ends execution while `_tbotInstance.UserData.isSleeping`; worker-local guards add further protection. Do not rely on a worker continuing its normal cadence during sleep.
- **Always `CheckCelestials()` in `finally`** unless sleeping — a bridge re-sync after every pass.
- **Interval fallback.** Whenever a computed interval is `<= 0` it is replaced by `RandomizeHelper.CalcRandomInterval(IntervalType.SomeSeconds)`
  (e.g. AutoCargoWorker.cs:141-142).

### 1.1 Slot priority (shared fleet-slot budget)

`CalcSlotsPriority(Feature, rankSlotsPriority, slots, fleets, slotsToLeaveFree)` (CalculationService.cs:4867-4931) is used identically by
AutoMineCelestialWorker.cs:307-341, AutoResearchWorker.cs:182-216, LifeformsAutoMineCelestialWorker.cs:187-221 and
LifeformsAutoResearchCelestialWorker.cs:197-231 before any transport is sent:

1. A `RankSlotsPriority` list is built with rank = `General.SlotPriorityLevel.<Feature>`:
   `Brain` (feature-specific `MaxSlots` = `Brain.Transports.MaxSlots`, used = #transports), `Expeditions` (ExpTotal/ExpInUse), `AutoFarm`,
   `Colonize` (`IntensiveResearch.MaxSlots` if that sub-flag is on, else 1), `AutoDiscovery`, `Harvest`.
2. If the feature's rank `> 0`: available = `slots.Total − SlotsToLeaveFree − Σ MaxSlots of higher-ranked active features − Σ used of lower-ranked − other missions`
   (missions other than Transport/Expedition/Spy/Attack/Colonize/Discovery/Harvest), clamped at 0, then `min(available, MaxSlots − SlotsUsed)`.
3. Rank `0` → simply `slots.Free − SlotsToLeaveFree`.
4. `0` ⇒ log (`Transports.MaxSlots is set to 0, you should increase it` when rank>0 and max is 0) and **delay** the pass
   (AutoMineCelestialWorker.cs:544-553).

### 1.2 Transport pipeline (shared by all four build/research executors)

When the chosen build/research is not affordable, and both `<feature>.Transports.Active` and `Brain.Transports.Active` are true:

1. Refresh slots + fleets; compute `MaxSlots` via §1.1; bail out with *delay* if 0.
2. Skip if `IsThereTransportTowardsCelestial` already true (CalculationService.cs:4632-4646: inbound non-return Transport with resources).
3. **Stage 1 — same-coordinates neighbour** (`Brain.Transports.CheckMoonOrPlanetFirst`): if the target is a planet with a moon (or vice versa),
   try that neighbour as origin: if it holds `missingResources` and enough `Brain.Transports.CargoType` ships → one `SendFleet(..., Missions.Transport, Speeds.HundredPercent, ...)`
   (AutoMineCelestialWorker.cs:353-410). Not enough ships + `DoMultipleTransportIsNotEnoughShipButSamePosition` → send what fits
   (`CalcMaxTransportableResources`, CalculationService.cs:571-585); otherwise warn and fall through.
4. **Stage 2 — multiple origins** (`Brain.Transports.MultipleOrigins.Active`): build a `TransportSettings` and call
   `CalcMultipleOrigin(...)` (CalculationService.cs:4933-5066) which
   - requires `missing ≥ MultipleOrigins.MinimumResourcesToSend`,
   - filters `Exclude` list, `OnlyFromMoons`, nonzero resources,
   - orders by distance (`PriorityToProximityOverQuantity`) or by resources descending,
   - may redirect destination to the moon (`SendToTheMoonIfPossible`) when the moon has ships or the planet has none,
   - excludes origins already sending a transport, honours `DeutToLeaveOnMoons` and `RoundResources`,
   - returns a list of `{origin → resources}` or empty.
   The worker then sends one fleet per entry, but **aborts** (delay) if `entries > MaxSlots` (AutoMineCelestialWorker.cs:470-474).
5. **Stage 3 — single configured origin**: `Brain.Transloads.Origin` — actually `Brain.Transports.Origin.{Galaxy,System,Position,Type}` —
   via `_fleetScheduler.HandleMinerTransport(...)` (AutoMineCelestialWorker.cs:524; research variant passes `Buildables.Null`,
   AutoResearchWorker.cs:393; LF-mine variant passes the LF buildable + maxes, LifeformsAutoMineCelestialWorker.cs:390).
6. `SendFleetCode.AfterSleepTime` → `stop=true` (worker ends); `NotEnoughSlots` → `delay=true`.
   On success the next wake-up is the transport's `ArriveIn` + jitter (AutoMineCelestialWorker.cs:644-647).

### 1.3 DOIR bookkeeping (shared ROI memory)

`UserData.lastDOIR` / `UserData.nextDOIR` implement a hysteresis used by AutoMine, AutoResearch priorities and crawler decisions:

- While a mine is being built or is unaffordable, its DOIR is recorded into `lastDOIR` (max) / `nextDOIR` (min)
  (AutoMineCelestialWorker.cs:183-186, 249-254, 293-298; AutoMineWorker.cs:114-121).
- When a build starts or a pass ends with `lastDOIR >= nextDOIR`, `nextDOIR` is reset to 0 (AutoMineCelestialWorker.cs:633-635, 671-673).
- AutoResearch's PrioritizePlasma/Astro branches require `plasmaDOIR/astroDOIR <= UserData.lastDOIR` — i.e. research only outranks mines while
  mines are the slower payback (AutoResearchWorker.cs:114-137).

---

## 2. AutoMine / AutoMineCelestial (Brain.AutoMine)

**Dispatcher** (`AutoMineWorker.cs`): builds `Buildings/Facilities` max tables and `AutoMinerSettings` from settings (:63-96, note it never sets
`BuildSolarSatellites`, and the constructed `maxLunarFacilities`/`autoMinerSettings` are *not* passed on — the celestial worker rebuilds its own).
For every planet it refreshes buildings/LFbonuses, computes the next mine and tracks the minimal DOIR into `nextDOIR` (:105-121); planets on which
`AutoColonize.Abandon.Active` and `ShouldAbandon` say so are dropped (:122-132). Remaining planets are sorted by `CalcNextDaysOfInvestmentReturn`
ascending (:134), **moons are appended after all planets** (:135) and then each celestial (maybe shuffled) gets a short-lived
`BrainCelestialAutoMine` worker started sequentially (:137-146).

**Executor** (`AutoMineCelestialWorker.AutoMineCelestial`, :114-679) — decision order:

1. **Refresh** 12 update kinds (Fast, Resources, ResourcesProduction, ResourceSettings, Buildings, Facilities, Constructions, Productions, Ships,
   LFBonuses, LFBuildings, second Fast) plus a global `UpdateCelestials` (:125-137).
2. **Crawlers first** (:138-154) — all must hold: `BuildCrawlers` setting unset-or-true (checked via `SettingsService.IsSettingSet`, the only
   optional key in this worker), celestial is a planet, `Resources.Energy >= 0`, player class `Collector`, `Shipyard >= 5`,
   researches `CombustionDrive >= 4 && ArmourTechnology >= 4 && LaserTechnology >= 4`, no crawler production running, shipyard/nanite not
   upgrading, `Ships.Crawler < CalcMaxCrawlers` and `CalcOptimalCrawlers > Ships.Crawler`. Then build `CalcOptimalCrawlers − current` crawlers
   as *ships*.
3. Otherwise: bail if `Fields.Free == 0` (:156); respect abandon rules (:160-169); if any building is under construction, record its mine-DOIR into
   `lastDOIR` and **schedule wake-up at `BuildingCountdown`** (:170-189).
4. Choose the buildable — planets: `GetNextBuildingToBuild` (:192); moons: `GetNextLunarFacilityToBuild` (:195). Level via `GetNextLevel`
   (solar-satellite special case, CalculationService.cs:3079-3100).
5. **Terraformer energy fallback** (:211-225): if the terraformer's energy cost exceeds current production and `BuildSolarSatellites` is set, the
   buildable switches to `CalcNeededSolarSatellites(...)` solar satellites; without the flag the pass stops.
6. **Execute** (:227-291): satellites/crawlers → `BuildShips` (only if no production running, else `delayProduction`); everything else →
   `BuildConstruction`; success is *verified* by re-reading Constructions/Productions and comparing levels.
7. **Unaffordable** → transport pipeline (§1.2); nothing to send → return.
8. **Nothing to build** (:556-590): if the planet has all facilities and (all maxed mines **or** `nextDOIR > MaxDaysOfInvestmentReturn`), log the
   exact raising advice (`rise Brain.AutoMine.MaxDaysOfInvestmentReturn to at least X` / `rise ... mines max levels`) and **stop the per-celestial
   worker** permanently (`EndExecution`).

**Timer** (`CalcAutoMineTimer`, :680-801): with a chosen but unaffordable buildable the wake-up is the *minimum* of

- production time of the missing resources (per-resource seconds = missing / hourly-production/3600, only when storage allows and production is
  nonzero, :719-742),
- next incoming fleet with resources (`GetIncomingFleetsWithResources`, CalculationService.cs:4672-4678),
- next returning expedition to this celestial **and** to the configured transport origin (+1-2 min jitter) (:752-780),

else the plain `CheckIntervalMin..Max` random. `Fields.Free == 0` ⇒ `long.MaxValue` (idle). Final result always gets `SomeSeconds` jitter, and
`DoMultipleTransportIsNotEnoughShipButSamePosition` can override with a same-position transport's `BackIn` (:651-663).

### 2.1 What gets chosen on a planet — exact order

`GetNextBuildingToBuild` (CalculationService.cs:4111-4127), first non-null wins:

1. `ShouldBuildTerraformer` — energy tech ≥ 12 **and** exactly 1 free field and level ≤ max (:4329-4340).
2. `ShouldBuildEnergySource` (energy balance `< 0`, :3178-3183) → `GetNextEnergySourceToBuild` (:3185-3203): SolarPlant up to max →
   FusionReactor if `DeuteriumSynthesizer >= 5` → SolarSatellite if `buildSolarSatellites` and Shipyard ≥ 1 → else Shipyard (Robotics ≥ 2) →
   RoboticsFactory.
3. `GetNextDepositToBuild` (:4129-4151) — suppressed entirely while the planet is still "starting"
   (`MetalMine<13 && CrystalMine<12 && DeuteriumSynthesizer<10 && SolarPlant<13 && FusionReactor<5 && Robotics<5 && Shipyard<5 && Lab<5`);
   else DeuteriumTank → CrystalStorage → MetalStorage per `ShouldBuild*Storage` (capacity < `DepositHours` × hourly production, or storage full
   when `BuildDepositIfFull`).
4. `GetNextFacilityToBuild` (:4152-4173) — `PrioritizeRobotsAndNanites` shortcut (Robotics < 10, or Nanite if Robotics ≥ 10 ∧ ComputerTech ≥ 10 ∧
   idle ∧ no LF building); then SpaceDock → Nanite → Robotics → Shipyard → ResearchLab (only while no research running) → MissileSilo, each via
   `ShouldBuildX` = *level ≤ max ∧ (cheaper than next mine ∨ `force`) ∧ prerequisite* (Shipyard needs Robotics ≥ 2; SpaceDock needs Shipyard ≥ 2 ∧
   energy; Silo needs Shipyard ≥ 1; Nanite needs Robotics ≥ 10 ∧ ComputerTech ≥ 10 ∧ cheaper-or-faster).
5. `GetNextMineToBuild` — start-optimisation (`MetalMine ≤ CrystalMine+2`, `CrystalMine ≤ Deuterium+2` below 10/7/5) then **cheapest
   `ConvertedDeuterium`** among mines under their maxes, gated by `MaxDaysOfInvestmentReturn` (:3254-3292).
6. `GetNextFacilityToBuild(force:true)` — same as 4 but ignores the cheaper-than-mine test.

Moons (`GetNextLunarFacilityToBuild`, :4183-4197): LunarBase (1 free field) → RoboticsFactory (free > 1) → JumpGate (level ≤ max ∧ LunarBase ≥ 1 ∧
HyperspaceTech ≥ 7 ∧ free > 1) → SensorPhalanx (base ≥ 1 ∧ free > 1) → Shipyard.

### 2.2 AutoMine settings keys (exact spelling, including the misspelling)

| Key (`Brain.AutoMine.*`) | Used at | Fallback if absent |
|---|---|---|
| `Active`, `CheckIntervalMin/Max` (minutes) | worker gate; :598,649 | branch-dependent retry/jitter; configure bounds explicitly |
| `MaxMetalMine`, `MaxCrystalMine`, `MaxDeuteriumSynthetizer` *(sic — misspelling of Synthesizer, matches enum? no: enum is `DeuteriumSynthesizer`)* | :63-66 | – |
| `MaxSolarPlant`, `MaxFusionReactor`, `MaxMetalStorage`, `MaxCrystalStorage`, `MaxDeuteriumTank` | :67-71 | – |
| `MaxRoboticsFactory`, `MaxShipyard`, `MaxResearchLab`, `MaxMissileSilo`, `MaxNaniteFactory`, `MaxTerraformer`, `MaxSpaceDock` | :74-80 | – |
| `MaxLunarBase`, `MaxLunarRoboticsFactory`, `MaxSensorPhalanx`, `MaxJumpGate`, `MaxLunarShipyard` | :83-87 | – |
| `OptimizeForStart`, `PrioritizeRobotsAndNanites`, `MaxDaysOfInvestmentReturn` (float), `DepositHours`, `BuildDepositIfFull`, `DeutToLeaveOnMoons`, `BuildSolarSatellites` | :89-93, celestial :86-94 | explicit casts overwrite object initializers; missing bool/int keys cast to false/0, unsupported casts can fail |
| `BuildCrawlers` | :139 | **true** when key missing (`IsSettingSet` check) |
| `RandomOrder`, `Exclude` | :137, dispatcher :106 | order as listed / no exclusions |

Abandon thresholds come from **`AutoColonize.Abandon.{Active,MinFields,MinTemperatureAcceptable,MaxTemperatureAcceptable}`** — outside the Brain
section (:96-103).

---

## 3. AutoResearch (Brain.AutoResearch)

`AutoResearchWorker.cs` — single global worker (no per-celestial children).

1. Refresh researches, celestials, LFbonuses (:43-45).
2. **Target planet**: `Brain.AutoResearch.Target.{Galaxy,System,Position}` matched as a *planet*; on any mismatch **falls back to the planet with the
   highest Research Lab** (:47-72, warning logged). Guard: lab 0 ⇒ skip; research running ⇒ wake at `ResearchCountdown`; lab upgrading ⇒ skip (:74-88).
3. **Priority ladder** — only evaluated when any `Prioritize*` flag is set (:99-144). It refreshes *all* planets (Facilities+Buildings+LFBonuses) and:
   - **Plasma**: `PrioritizePlasmaTechnology ∧ lastDOIR > 0 ∧ plasmaDOIR ≤ lastDOIR ∧ plasmaDOIR ≤ Brain.AutoMine.MaxDaysOfInvestmentReturn ∧
     MaxPlasmaTechnology ≥ current+1 ∧ lab ≥ 4 ∧ Energy ≥ 8 ∧ Laser ≥ 10 ∧ Ion ≥ 5`. Note lines 121-123 join the last three conditions with the
     bitwise `&` on a bool expression — functionally the same as `&&` here, but flagged in the findings.
   - **Energy tech**: `PrioritizeEnergyTechnology ∧ ShouldResearchEnergyTech(all planets, maxEnergyTech)` (CalculationService.cs:4420-4442: needs at
     least one fusion reactor; compares average-fusion+1-level cost efficiency vs energy-tech level efficiency).
   - **Astrophysics**: `PrioritizeAstrophysics ∧ lastDOIR > 0 ∧ MaxAstrophysics ≥ next parity level ∧ astroDOIR ≤ Brain.AutoMine.MaxDaysOfInvestmentReturn ∧
     astroDOIR ≤ lastDOIR ∧ lab ≥ 3 ∧ Espionage ≥ 4 ∧ Impulse ≥ 3`. The parity rule (:131) means the *pair* of levels that yields a planet is bought
     as one decision (mirrored in `CalcNextAstroDOIR`, CalculationService.cs:3411-3414).
   - Otherwise: `GetNextResearchToBuild`.
4. **IRN override** (:146-162): if `PrioritizeIntergalacticResearchNetwork` and the chosen research isn't IRN and lab ≥ 10 ∧ Computer ≥ 8 ∧
   Hyperspace ≥ 8 ∧ max not reached ⇒ compare `CalcProductionTime` of the chosen research vs IRN **using cumulative lab levels
   (`CalcCumulativeLabLevel`: best `IntergalacticResearchNetwork+1` planet labs, CalculationService.cs:2343-2358) and `SpeedResearch`**; IRN wins if
   strictly faster.
5. **Execute**: `BuildCancelable(celestial, research)` when `Resources.IsEnoughFor(CalcPrice(research, level, LFBonuses))` (:169-176).
6. Unaffordable ⇒ same transport pipeline with feature `BrainAutoResearch` (:179-424).
7. **Timer** (:429-512): research countdown; transport arrival; lab-upgrade countdown; incoming-fleet arrival; **fallback quirk**: the *delay* branch
   reads `InstanceSettings.AutoResearch.CheckIntervalMin/Max` — the top-level `AutoResearch` section, **not** `Brain.AutoResearch` (:442). Normal path
   uses `Brain.AutoResearch.CheckIntervalMin/Max` (:455,488).

### 3.1 `GetNextResearchToBuild` gates (CalculationService.cs:4444-4630)

- First: if `ShouldBuildResearchLab(celestial, 12, ...)` (lab cheaper than next mine) and not `ForceResearchWhateverTheLabLevel` ⇒ return Null with
  log "Research Lab need to be upgraded first".
- `OptimizeForStart` chain (fixed order, each with its own lab/dependency guard): Computer < 6 (if Astro > 1) → Energy == 0 → Combustion < 2 →
  Espionage < 4 (lab ≥ 3) → Impulse < 3 (lab ≥ 2) → Computer < 1 → Astro == 0 (lab ≥ 3 ∧ Esp ≥ 4 ∧ Imp ≥ 3) → Energy 1-2 → Shielding < 2 (lab > 5) →
  Combustion 2-5 → optionally Computer < 10 when `prioritizeRobotsAndNanitesOnNewPlanets`.
  **Quirk:** the Combustion 2-5 branch compares against `maxComputerTechnology` instead of `maxCombustionDrive` (:4469).
- `EnsureExpoSlots`: if `CalcMaxExpeditions(Astro, isDiscoverer, hasAdmiral) + 1 > slots.Total` ⇒ Computer Technology (:4475-4476;
  `CalcMaxExpeditions = ⌊√Astro⌋ + 2 discoverer + 1 admiral`, :4763-4770).
- Then cheapest-`ConvertedDeuterium` over the 16 researches whose gates pass (lab level and prerequisite techs, :4478-4620). Max-level caps come
  1:1 from `Brain.AutoResearch.Max<Technology>` keys.

### 3.2 AutoResearch settings keys

`Active`, `Target.{Galaxy,System,Position}`, `CheckIntervalMin/Max`, `PrioritizeAstrophysics`, `PrioritizePlasmaTechnology`,
`PrioritizeEnergyTechnology`, `PrioritizeIntergalacticResearchNetwork`, `OptimizeForStart`, `EnsureExpoSlots`,
`ForceResearchWhateverTheLabLevel`, `Max{EnergyTechnology,LaserTechnology,IonTechnology,HyperspaceTechnology,PlasmaTechnology,CombustionDrive,ImpulseDrive,HyperspaceDrive,EspionageTechnology,ComputerTechnology,Astrophysics,IntergalacticResearchNetwork,WeaponsTechnology,ShieldingTechnology,ArmourTechnology}`,
`Transports.Active`; plus `Brain.AutoMine.PrioritizeRobotsAndNanites` is forwarded into the chooser (:140,143) and
`Brain.AutoMine.MaxDaysOfInvestmentReturn` gates the plasma/astro branches.

---

## 4. LifeformsAutoMine / …Celestial (Brain.LifeformAutoMine)

**Dispatcher** (`LifeformsAutoMineWorker.cs`): per planet — refresh Buildings/LFBuildings/Resources/ResourcesProduction; skip planets whose
`Buildings.CrystalMine < Brain.LifeformAutoMine.StartFromCrystalMineLvl` (:79-82); build the per-lifeform `maxLFBuildings` map from
`MaxBasePopulationBuilding/MaxBaseFoodBuilding/MaxBaseTechBuilding/MaxT2Building/MaxT3Building/MaxBuilding6..12` (:91-150; mapping table in
§4.2); keep the planet only if `GetNextLFBuildingToBuild(...) != None` (:151-159); dispatch `BrainCelestialLifeformAutoMine` workers.
Cosmetic bug: `_calculationService` assigned twice in the ctor (:33-34).

**Executor** (`LifeformsAutoMineCelestialWorker.cs:81-521`):

1. `preventTechBuilding = Constructions.LFResearchCountdown > 0` (:107-110) — while an LF research runs, tech buildings are excluded from choice.
2. Rebuild the same max-map (lifeform-agnostic this time, :112-124).
3. Skip+delay if an LF building **or** Robotics/Nanite is under construction (:126-132).
4. `GetNextLFBuildingToBuild(celestial, maxLFBuildings, preventIfMoreExpensiveThanNextMine, preventTechBuilding)` (:135).
5. If the chosen building is a tech building *and* an LF research is running ⇒ delay until the research ends (:141-153) — duplicate protection of step 1.
6. Cost = `CalcPrice(buildable, level, costReduction, 0, popReduction)` with `CalcLFBuildingsResourcesCostBonus` /
   `CalcLFBuildingsPopulationCostBonus` (Rocktal: Megalith level %, CalculationService.cs:3794-3816). affordability via `Resources.IsBuildable`;
   distinct message when only **population** is missing (:179-182).
7. Unaffordable ⇒ transport pipeline; `HandleMinerTransport(origin, celestial, destination, cost, buildable, maxLFBuildings, preventIfMoreExpensiveThanNextMine)` in stage 3 (:390).
8. Nothing to build ⇒ `stop` (worker ends) with hint to raise the maxes (:422-425).
9. Timer: LF-building countdown; `SendFleetCode.QuickerToWaitForProduction` triggers the same resource-accumulation estimate as AutoMine (:461-492,
   duplicated code); transport arrival; `CheckIntervalMin/Max`.

### 4.1 `GetNextLFBuildingToBuild` choice logic (CalculationService.cs:3590-3684)

Moons and `LFtype == None` ⇒ None. Candidate set, then **cheapest `ConvertedDeuterium` wins**:

- food building when `IsStarving()` (unconditional if energy suffices) or `WillStarve()` (as candidate) — energy gate: current production ≥ cost energy;
- population building when `IsThereFoodForMore()` or `IsFull()`;
- tech building when `isUnlocked` (requirement table, :3481-3588) and not `preventTechBuilding`;
- T2/T3 buildings when `Population.NeedsMoreT2/T3(CalcLFBuildingPopulationTechCapBonus)` — Kaelesh: `2 × PsionicModulator` level, :3818-3828 —
  and living space ≥ cost population and current population ≥ cost population;
- always: `GetLeastExpensiveLFBuilding` (cheapest unlocked *other* building respecting maxes/energy/living-space, :3855-3887);
- fallback pair food+population if the candidate set ended empty (:3660-3667).
`preventIfMoreExpensiveThanNextMine` post-check: if the winner costs more than the planet's next mine (computed with hardcoded 100/100/100 maxes and
`optimizeForStart:false`, :3673-3682) ⇒ None.

### 4.2 Lifeform building → settings mapping

| Slot | Humans | Rocktal | Mechas | Kaelesh | Setting |
|---|---|---|---|---|---|
| Population | ResidentialSector | MeditationEnclave | AssemblyLine | Sanctuary | `MaxBasePopulationBuilding` |
| Food | BiosphereFarm | CrystalFarm | FusionCellFactory | AntimatterCondenser | `MaxBaseFoodBuilding` |
| Tech | ResearchCentre | RuneTechnologium | RoboticsResearchCentre | VortexChamber | `MaxBaseTechBuilding` |
| T2 | AcademyOfSciences | RuneForge | UpdateNetwork | HallsOfRealisation | `MaxT2Building` |
| T3 | NeuroCalibrationCentre | Oriktorium | QuantumComputerCentre | ForumOfTranscendence | `MaxT3Building` |
| 6-12 | see `GetOtherBuildings` (CalculationService.cs:3756-3792) | | | | `MaxBuilding6` … `MaxBuilding12` |

Other keys: `StartFromCrystalMineLvl`, `PreventIfMoreExpensiveThanNextMine`, `Transports.Active`, `CheckIntervalMin/Max`, `Exclude`, and shared
`Brain.Transports.*`.

## 5. LifeformsAutoResearch / …Celestial (Brain.LifeformAutoResearch)

**Dispatcher** (`LifeformsAutoResearchWorker.cs`): per planet refresh LFBuildings/LFTechs/Resources; skip `LFtype == None`; candidate =
`GetNextLFTechToBuild(cel, maxLFTechs)` then **cheaper-substitution** `GetLessExpensiveLFTechToBuild` (:94-102); dispatch
`BrainCelestialLifeformAutoResearch`.

**Executor** (`LifeformsAutoResearchCelestialWorker.cs`):

- **Defaults via `SettingsService.IsSettingSet`** (:108-126): `MaxResearchLevel` defaults to **1** when absent; every `MaxTechsNN` defaults to
  `MaxResearchLevel`. The dispatcher does *not* apply these defaults (it reads the keys raw, :62-79) — a missing key there yields 0 and disables the
  group; only the celestial worker is defensive.
- Skip+delay while `Constructions.LFResearchID != 0` (:149-154).
- Same choose→substitute-cheaper→`CalcPrice`→`IsEnoughFor`→`BuildCancelable` flow (:155-190); verification via `LFTechs` level.
- Unaffordable ⇒ transport pipeline (feature `BrainLifeformAutoResearch`), stage 3 `HandleMinerTransport(..., LFBuildables.None)` (:400).
- Nothing to research ⇒ stop. Timer mirrors the mine variant with `LifeformAutoResearch.CheckIntervalMin/Max` (:456,466).

`GetNextLFTechToBuild` (CalculationService.cs:4068-4084) iterates `Enum.GetValues<LFTechno>()` **in declaration order** and returns the first tech with
`level ≥ 1` (unresearched-from-zero techs are never picked — documented intent in the TODO comment) under its `MaxTechsNN` cap.
`GetLessExpensiveLFTechToBuild` (:4086-4109) then swaps in any researched tech whose next level is cheaper.

`MaxTechsNN` group membership (identical in both workers, e.g. :62-79 / :129-146): the 60 LF techs are grouped 4-per-key by tier
(`MaxTechs11`=tier1#1 … `MaxTechs36`=tier6#4); the exact mapping is the chained assignments quoted above.

---

## 6. AutoCargo (Brain.AutoCargo)

`AutoCargoWorker.cs` — per celestial:

1. Skip excluded; refresh Fast; optional `SkipIfIncomingTransport` check (:52-55).
2. Skip if shipyard *productions* exist, or shipyard/nanite **building** under upgrade (:57-71) — cargo building would be queued behind them.
3. Refresh Ships/Resources/LFBonuses; compute fleet capacity (`CalcFleetCapacity` with hyperspace tech, LF cargo bonuses, player class, `ProbeCargo`) (:77).
4. `ExcludeMoons` skip (:78-81).
5. `CargoType` parse — **fallback `SmallCargo`** with warning on any parse failure (:83-87).
6. Needed count:
   - `LimitToCapacity` ∧ capacity < resources ⇒ `ceil((resources − capacity) / oneShipCapacity)` using the *same* bonus pipeline (:88-93);
   - else `MaxCargosToKeep − owned` (:95).
7. Clamp to `MaxCargosToBuild`, then to keep-limit after adding (:97-102); if unaffordable ⇒ `CalcMaxBuildableNumber` (per-resource minimum,
   CalculationService.cs:3010-3030); build via `BuildShips` (:104-119).
8. Timer: `CheckIntervalMin/Max` (**minutes**, converted to milliseconds by `RandomizeHelper.CalcRandomInterval`) + jitter.

Keys: `Active`, `CheckIntervalMin/Max`, `Exclude`, `RandomOrder`, `SkipIfIncomingTransport`, `LimitToCapacity`, `CargoType` (string; parsed
case-insensitive into `Buildables`), `MaxCargosToKeep`, `MaxCargosToBuild`, `ExcludeMoons`.

## 7. AutoDefence (Brain.AutoDefence)

`AutoDefenceWorker.cs` — same skeleton as AutoCargo with defences:

- Target = `DefenceToReach.{RocketLauncher,LightLaser,HeavyLaser,GaussCannon,IonCannon,PlasmaTurret,AntiBallisticMissiles,InterplanetaryMissiles}`
  (long counts) + `SmallShieldDome`/`LargeShieldDome` as **bools mapped to 1/0** (:42-53).
- `defencesToBuild = needed.Difference(current)`; if unaffordable ⇒ greedy `CalcmaxDefencesBuildable` (round-robin one-of-each while resources last,
  CalculationService.cs:3032-3053) (:94-98).
- Build via `BuildDefences` per type (:104-111). Same production/upgrade guards and `ExcludeMoons` as AutoCargo; `CheckIntervalMin/Max`.

## 8. AutoRepatriate (Brain.AutoRepatriate)

`AutoRepatriateWorker.cs` — thin scheduler around `_fleetScheduler.CollectImpl(false)` (:33):

- `RepatriateCode.Stop` ⇒ `EndExecution()` (feature disabled until restart) (:34-36);
- `RepatriateCode.Delay` ⇒ next wake = soonest fleet `BackIn` (s) × 1000 + `SomeSeconds` jitter (:39-43);
- otherwise `CheckIntervalMin/Max` (ms). Sleep mode: whole pass skipped, no reschedule change (:32).

The actual recall rules live in the FleetScheduler (outside this audit); the worker only owns the cadence and the two `RepatriateCode` branchings.

## 9. AutoFleetJumpGate (Brain.AutoFleepJumpGate — misspelled section name)

`AutoFleetJumpGateWorker.cs`:

1. Target moon from `Target.{Galaxy,System,Position}`; **return silently if not found** (:39-54) — next wake is the default interval via
   `SetDefaultWorkerPeriod`.
2. Validate the target's `Facilities.JumpGate > 0` after a Facilities refresh (:58-74).
3. Jumpable set: all combat+cargo ships **excluding** SolarSatellite/Crawler (:81-97).
4. `MinimumAmountOfShipsToBeLeftOnMoon.*` per-type floors, applied as `min(current, floor)` for the *points* calculation (:138-144) and
   `max(0, current − floor)` for the actual send (:186-192).
5. A moon qualifies when `teleportablePoints = ships.GetFleetPoints() − left.GetFleetPoints() ≥ MinimumAmountOfShipPointsToTeleport` (:147-158).
6. Pairing (:172-178): richest moon → target; then remaining qualifiers pairwise `(1→2), (3→4), …` — note **the last odd moon is dropped** and an
   even count pairs all but index 0.
7. Each jump: `IOgameService.JumpGate(origin, dest, ships)`; `RechargeCountdown` (s) of the *successful* jumps is tracked as the max (:200-208);
   5-15 s delay between jumps (:223-228).
8. Timer (:236-255): if any jump succeeded ⇒ `max(rechargeMs, random(CheckIntervalMin..Max))` and when recharge dominates add **2-5 minutes** jitter
   (comment says minutes; `CalcRandomInterval(2,5)`); else default interval. `RunFromTelegramAsync` (:294-305) re-runs `Execute()` on demand
   (manual `/fleetjumpgate`).

## 10. BuyOfferOfTheDay (Brain.BuyOfferOfTheDay)

`BuyOfferOfTheDayWorker.cs` — calls `IOgameService.BuyOfferOfTheDay()` once per pass and logs one of
`OfferOfTheDayBougth` *(sic)* / `OfferOfTheDayAlreadyBought` / error (:29-37); reschedules on `CheckIntervalMin/Max`. No preconditions, no retry
logic, no resource check — the "already bought" outcome is treated as success.

---

## 11. Cross-cutting scheduling effects (read this before tuning two features at once)

- **Slots.** Every transport consumes a fleet slot; the rank table (§1.1) makes `General.SlotPriorityLevel.*` a hard budget — a higher-ranked
  feature's `MaxSlots` is *reserved* even when idle, and `General.SlotsToLeaveFree` is subtracted for ranked features only.
- **Transports are global.** `Brain.Transports.*` (not per-feature) governs cargo type, `DeutToLeaveOnMoons`, rounding, moon redirection,
  multiple origins. `IsThereTransportTowardsCelestial` dedupes: while any transport is inbound to a celestial, *all* four executors skip new ones —
  including across features (AutoMine will not stack on AutoResearch's transport and vice versa).
- **DOIR memory is shared.** `UserData.lastDOIR/nextDOIR` are written by AutoMine passes and *read* by AutoResearch's plasma/astro gates; running
  AutoResearch without AutoMine leaves `lastDOIR = 0`, which disables both priority branches (`lastDOIR > 0` required).
- **Worker lifetime.** Celestial workers `EndExecution()` when maxed/abandon-candidate; the dispatcher initializes/starts their worker each eligible pass, so "stop" means
  *until the next dispatcher run*, not forever — except AutoRepatriate, whose `Stop` ends the feature worker itself.
- **Sleep mode** stops normal worker execution through the common wrapper; wake-up/start logic must re-enable the workers. The bridge's `GetDateTime` prefers server time and falls back to local time.

## 12. Configuration fragment (illustrative, not a complete runnable configuration)

`CheckIntervalMin/Max` below are **minutes**, not milliseconds. Start from the full instance template, review every feature and merge only the keys you intend to enable. Omitted caps/targets do not acquire safe defaults automatically; this abbreviated fragment must not replace the full configuration. Misspellings are literal.

```jsonc
{
  "Brain": {
    "Active": true,
    "AutoMine": {
      "Active": true, "CheckIntervalMin": 1, "CheckIntervalMax": 3,
      "MaxDeuteriumSynthetizer": 40,          // literal misspelling in code
      "MaxDaysOfInvestmentReturn": 30.0,
      "BuildCrawlers": true,                   // optional key: defaults true
      "BuildSolarSatellites": true,
      "Exclude": [ { "Galaxy": 2, "System": 3, "Position": 4, "Type": "Planet" } ]
    },
    "AutoResearch": { "Active": true, "Target": { "Galaxy": 1, "System": 1, "Position": 1 },
                      "PrioritizePlasmaTechnology": true, "MaxPlasmaTechnology": 15 },
    "LifeformAutoMine":   { "Active": true, "MaxBasePopulationBuilding": 40, "MaxBuilding12": 10,
                            "PreventIfMoreExpensiveThanNextMine": true },
    "LifeformAutoResearch": { "Active": true, "MaxResearchLevel": 5, "MaxTechs11": 8 },
    "AutoCargo":   { "Active": true, "CargoType": "LargeCargo", "LimitToCapacity": true, "MaxCargosToKeep": 300 },
    "AutoDefence": { "Active": true, "DefenceToReach": { "RocketLauncher": 500, "SmallShieldDome": true } },
    "AutoRepatriate": { "Active": true, "CheckIntervalMin": 1, "CheckIntervalMax": 5 },
    "AutoFleepJumpGate": {   // literal misspelling of "Fleet" throughout
      "Active": true, "Target": { "Galaxy": 1, "System": 2, "Position": 3 },
      "MinimumAmountOfShipPointsToTeleport": 100000,
      "MinimumAmountOfShipsToBeLeftOnMoon": { "LightFighter": 100 } },
    "BuyOfferOfTheDay": { "Active": true, "CheckIntervalMin": 60, "CheckIntervalMax": 120 },
    "Transports": {
      "Active": true, "CargoType": "LargeCargo", "MaxSlots": 3,
      "CheckMoonOrPlanetFirst": true, "SendToTheMoonIfPossible": true,
      "DoMultipleTransportIsNotEnoughShipButSamePosition": true,
      "DeutToLeaveOnMoons": 10000, "RoundResources": true,
      "Origin": { "Galaxy": 1, "System": 1, "Position": 1, "Type": "Planet" },
      "MultipleOrigins": { "Active": true, "OnlyFromMoons": false,
                           "MinimumResourcesToSend": 50000, "PriorityToProximityOverQuantity": true,
                           "Exclude": [] }
    }
  },
  "General": { "SlotsToLeaveFree": 0,
               "SlotPriorityLevel": { "Brain": 1, "Expeditions": 2, "AutoFarm": 3, "Colonize": 4, "AutoDiscovery": 5, "AutoHarvest": 6 } }
}
```

**Example vs runtime fallback distinction.** Missing members return a nestable `NullExceptionPreventer`, not an immediate missing-object exception. Its supported bool/int/long/string casts yield false/0/0/null, and supported array casts yield empty arrays; unsupported casts or subsequent method calls can still fail. Feature gates therefore normally become false when omitted, while missing numeric caps can become zero. Explicit fallbacks include `CargoType` parse → `SmallCargo`, `Brain.AutoMine.BuildCrawlers` unset → `true`, and celestial-worker `LifeformAutoResearch.MaxResearchLevel/MaxTechsNN` unset → 1 / `MaxResearchLevel` (LifeformsAutoResearchCelestialWorker.cs:108-126). Configure the exact spellings, including `MaxDeuteriumSynthetizer` and `AutoFleepJumpGate`.

## 13. Code inconsistencies needing parent attention

See `docs/reference/brain-findings.md` for the full list with line refs; headline items: deut production computed from `CrystalMine` in two
overloads, unused `bonusProd` in the deut formula, `AutoResearch` delay interval read from the wrong settings section, AutoMineWorker building
settings objects it never passes on, `combustion vs maxComputerTechnology` mix-up, LF research `&` vs `&&`, duplicated LF-celestial blocks, jump-gate
odd-moon drop, and `CalcFleetSpeed` returning 0 for empty fleets.

# CalculationService — formula & helper reference

Source: `TBot/Includes/CalculationService.cs` @ `35b4ce08b57bf2900d5b3d3b449a3f26f168270b` (5 068 lines, read in full; sha256 in
`docs/reference/brain-read.json`). Interface: `TBot/Includes/ICalculationService.cs`. Companion feature doc: [features/brain.md](features/brain.md).

Conventions used throughout:

- **Levels are 1-based** in cost/time formulas (`level − 1` exponents); production formulas use the plain level.
- **`ConvertedDeuterium`** — the universal comparison currency — is defined in the Ogame.Infrastructure model, *not* here:
  `TBot.Ogame.Infrastructure/Models/Resources.cs:27-35` ⇒ `round↑(Metal/2.5 + Crystal/1.5 + Deuterium)`. This is why mine-ROI math divides metal
  production by 2.5 and crystal by 1.5.
- **Times**: internal seconds; `CalcProductionTime` returns seconds (hour-formula × 3600). Worker intervals are milliseconds.
- **Rounding** is explicit almost everywhere: `MidpointRounding.ToPositiveInfinity` (⌆) for costs, `ToZero` for floors, plain `Round` (banker's) in
  production. Deviations are flagged.

---

## 1. Ships

### 1.1 Capacity — `CalcShipCapacity` (:35-96 and cargo-bonus overload :98-161)

`capacity = baseCargo × (bonus + 100) / 100` where `bonus = hyperspaceTech × ServerData.CargoHyperspaceTechMultiplier` **plus** class bonus:
Collector +25 (small/large cargo), General +20 (recycler) / +25 (pathfinder). Probe cargo is the `probeCargo` argument (0 default).

The second overload adds a per-ship LF cargo bonus (`float`, percent-ish fraction from `LFBonuses.GetShipCargoBonus`):

```
totalBonus = round2( round⌆(bonus/100) + round⌆buildableCargoBonus ) − 0.01
capacity   = floor(baseCargo + baseCargo × totalBonus)
```

The `− 0.01` guards against floating-point overshoot; `MidpointRounding.ToZero` truncates. `Buildables` without a case (facilities, defences,
researches) return **0**.

Fleet aggregates: `CalcFleetCapacity` (:167-183) sums per-type capacity × count via reflection over `Ships` properties
(`Enum.TryParse<Buildables>(prop.Name)` — property name must equal enum name). `CalcFleetFuelCapacity` (:185-197, :163-165) is the same without LF
bonuses — it exists for "how much fits ignoring cargo-bonus overrides".

### 1.2 Speed — `CalcShipSpeed` (:208-316)

```
speed = baseSpeed×lfBonus + baseSpeed×(bonus+10)/10        # :314, rounded ToZero
```

`bonus` starts as the driving-research level and is replaced per case; base speeds (and drive swaps):

| Ship | base | drive/bonus notes |
|---|---|---|
| SmallCargo | 5000 | Impulse ≥ 5 ⇒ 10000 & bonus = 2×impulse; Collector +10; ally Trader +1 |
| LargeCargo | 7500 | Collector +10; Trader +1 |
| LightFighter | 12500 | combustion |
| HeavyFighter | 10000 | 2×impulse |
| Cruiser | 15000 | 2×impulse |
| Battleship | 10000 | 3×hyperspace |
| ColonyShip | 2500 | 2×impulse |
| Recycler | 2000 | Impulse ≥ 17 ⇒ 4000/2×imp; Hyp ≥ 15 ⇒ 6000/3×hyp |
| EspionageProbe | 100000000 | – |
| Bomber | 4000 | 2×imp; Hyp ≥ 8 ⇒ 5000/3×hyp |
| Destroyer 5000, Deathstar 100, Battlecruiser 10000, Reaper 7000, Pathfinder 12000 | | 3×hyperspace |

General adds +10 to `bonus` on all combat ships. **Quirk:** because `bonus+10` scales, a General's +10 is +100 % of one drive level, and `lfBonus`
multiplies only the base term. Empty/non-ship ⇒ 0.

`CalcSlowestSpeed` (:322-339) skips `SolarSatellite`/`Crawler` and returns `int.MaxValue` for an empty fleet; **`CalcFleetSpeed` (:345-359) initialises
`minSpeed = 0` and only lowers it, so it returns 0 for fleets whose calculated ship speeds are nonnegative**, not just empty fleets. Unlike `CalcSlowestSpeed`, this implementation never selects a positive minimum.

### 1..3 Consumption — `CalcShipConsumption` (:366-434)

Base per ship (SmallCargo 10 ×2 if Impulse ≥ 5; LargeCargo 50; LF 20; HF 75; Cruiser 300; Battleship 500; Colony 1000; Recycler 300 ×3 if Hyp ≥ 15
else ×2 if Impulse ≥ 17; Probe 1; Bomber 700; Destroyer 1000; Deathstar 1; BC 250; Reaper 1100; Pathfinder 300). Then

```
fuel = deuteriumSaveFactor × base × (1 − lfConsumptionBonus)
General ⇒ fuel /= 2 ; round; min 1
```

**Quirk:** Bomber's hyperspace upgrade is `baseConsumption *= 3 / 2` — integer division ⇒ ×1, i.e. **no change** (:404). The server-wide
`ServerData.GlobalDeuteriumSaveFactor` enters here (:363).

### 1.4 Flight time / fuel / prediction

`CalcFlightTime` (:436-454): mission ⇒ fleet-speed class —
`Attack|FederalAttack|Destroy|Spy|Harvest → SpeedFleetWar`; `FederalDefense → SpeedFleetHolding`; *everything else* → `SpeedFleetPeaceful` (the fuel
variant at :457-461 has the same sets in different order).

```
t = round( ((35000/speedEnum) × sqrt(10×distance / slowestSpeed) + 10) / fleetSpeedClass )     [seconds]
```

`CalcFuelConsumption` (:465-483), per ship type:

```
tempSpeed = 35000 / (flightTime×fleetSpeedClass − 10) × sqrt(10×distance / shipSpeed)
fuel_t   = Σ  consumption × qty × distance / 35000 × (tempSpeed/10 + 1)²
total    = 1 + round(fuel_t)
```

`CalcFleetPrediction` (:485-496) bundles both into `FleetPrediction { Time, Fuel }`.
`CalcOptimalFarmSpeed` (:548-569): try `GetValidSpeedsForClass` (:498-546 — currently the *same* 100…10 % list for every class; the General-specific
finer grid is commented out) under constraints `fuel < loot.ConvertedDeuterium × ratio` and `time < maxFlightTime`; pick the **highest** passing speed, else
100 %. Here `loot` means `loot.ConvertedDeuterium`, not raw deuterium alone. Note the strict `<` comparisons and that `speedEnum` is the engine's speed value, not a human percentage.

### 1.5 Distance — `CalcDistance` (:707-747)

Same coordinates ⇒ **5**. Planet distance `1000 + 5×|Δpos|`; system `2700 + 95×Δ` (donut-wrapped by `systemsNumber`); galaxy `20000×Δ` (donut-wrapped).
Non-donut variants drop the wrap. `galaxiesNumber/systemsNumber/donut*` come from `ServerData` in the convenience overload.

### 1.6 Expedition helpers

- `CalcIdealExpeditionShips` (:591-634): payload cap from `ServerData.TopScore` tiers — <10 k ⇒ 40 000; <100 k ⇒ 500 k; <1 M ⇒ 1.2 M; <5 M ⇒ 1.8 M;
  <25 M ⇒ 2.4 M; <50 M ⇒ 3 M; <75 M ⇒ 3.6 M; <100 M ⇒ 4.2 M; else 5 M. Discoverer ⇒ ×`ecoSpeed`×3, else ×2; plus
  `(1 + expeditionResourcesBonus)`. Ships needed = ⌆cap / single-ship capacity (with LF cargo bonus lookup by enum int).
- `CalcExpeditionShips` (:659-673): if owned primary ships < ideal×expeditions ⇒ per-expedition share `floor(owned/expeditions)`.
- `CalcFullExpeditionShips` (:690-705): +1 probe, +1 `CalcMilitaryShipForExpedition` (:636-657 — priority Reaper→Destroyer→Bomber→Battlecruiser→
  Battleship→Pathfinder→Cruiser→HF→LF, needs ≥ expeditions of that type, else `Null`), +1 pathfinder if none yet.
- `MayAddShipToExpedition` (:679-688): owned ≥ expeditions.
- `CalcMaxExpeditions` (:4763-4770): `⌊√astrophysics⌋ (ToZero) + 2·discoverer + 1·admiral`.

### 1.7 Transport maths

- `CalcMaxTransportableResources` (:571-585): if total ≤ capacity ⇒ everything minus `deutToLeave`; else fill Deut (−reserved) → Crystal → Metal in
  that order. **Returns raw `resources` (with deut *not* reduced) in the final else-branch — only reachable when the earlier arms are inconsistent.**
- `CalcShipNumberForPayload` (:587-589): `⌆payload.TotalResources / capacity`.
- `CalcMultipleOrigin` (:4933-5066): see features/brain.md §1.2 for the control flow; numeric core is repeated
  `CalcShipNumberForPayload` vs `Ships.GetAmount(TransportSettings.CargoType)` comparisons and `CalcMaxTransportableResources` fallbacks, plus
  `DeutToLeaveOnMoons` via `Difference(new Resources(0,0,deutToLeave))` (leaves metal/crystal untouched) and optional `Round()`.

---

## 2. Resource production (per hour)

All three follow the same shape (:774-905); `baseProd` is multiplied by `speedFactor` first and returned as-is for level 0.

**Metal** (:774-809): base 30, position bonus 6:+17 %, 7:+23 %, 8:+35 %, 9:+23 %, 10:+17 %.

```
prod        = round(baseProd × level × 1.1^level)
plasma      = round(prod × 0.01  × plasmaTech)          # metal
geologist   = round(prod × 0.10)   staff = round(prod × 0.02)
collector   = round(prod × 0.25)
crawlerProd = round(prod × crawlers × 0.003)
bonusProd   = round(prod × metalLFBonus / 100)
result      = round( (prod+plasma+geo+staff+class+bonus) × ratio  +  crawlerProd × crawlerRatio )
```

**Crystal** (:827-877): base 20, position 1:+30, 2:+20, 3:+10 %; plasma coefficient **0.0066**; rest identical.

**Deuterium** (:878-905): level 0 ⇒ 0; base 10.

```
prod = round(10·speed × level × 1.1^level × (1.36 − 0.004×tempAverage))
plasma coefficient 0.0033 ; …
result = round( (prod+plasma+geo+staff+class+deuteriumLFBonus) × ratio + crawlerProd×crawlerRatio )
```

**Two quirks to know before trusting deut numbers:**

1. :904 adds **`deuteriumLFBonus` (a percentage) as absolute units** — the correctly computed `bonusProd` (:900-903) is dead. With bonus 25 the
   error depends on the computed production and the bonus; it is not a fixed offset across mine levels.
2. The `Buildings`/`Planet` overloads pass **`buildings.CrystalMine`** as the level (:912, :920) — presumably meant `DeuteriumSynthesizer`. Hence
   `CalcPlanetHourlyProduction` (:923-930) and every `ShouldBuild*Storage` deut figure follow the *crystal-mine* level, while `CalcROI`/
   `CalcDaysOfInvestmentReturn` use the true synth level — the two families disagree whenever the levels differ.

`CalcPlanetHourlyProduction` = the three planet-level functions (:923-930). `CalcDaysOfInvestmentReturn`-family conversions: metal `/2.5`, crystal
`/1.5` — matching `ConvertedDeuterium` weights.

**Energy** (:749-772): SolarPlant `round(20·L·1.1^L·ratio)`; FusionReactor `round(30·L·(1.05+0.01·energyTech)^L·ratio)`; then sequentially
`+round(prod·0.10)` engineer, `+round(prod·0.02)` staff, `+round(prod·0.10)` Collector (each on the accumulated value).

**Solar satellites** (:3201-3222): per-sat output `round((tempAverage+160)/6 + 0.1·…)` — base `(T+160)/6`, +10 % Collector, +10 % engineer,
+2 % full staff, summed then rounded. `CalcNeededSolarSatellites` = ⌆(`|energy deficit|` / per-sat), deficit = `planet.Resources.Energy` when negative
or the explicit `requiredEnergy`.

**`GetSolarSatelliteOutput`/`GetProductionEnergyDelta`/`GetRequiredEnergyDelta`** (:3055-3077): deltas are next-minus-current of the formulas above;
mines' energy *need* delta comes from `CalcPrice(...).Energy` differences (only mines, :3055-3065).

### 2.1 Storage — `CalcDepositCapacity` (:3141-3143)

```
capacity = 5000 × (long)(2.5 × e^((20 * level) / 33))
```

The exponent uses **integer division**, and the `(long)` cast truncates the factor before multiplying by 5000. Both differ from a continuous real-valued exponential formula. `ShouldBuildMetal/CrystalStorage/
DeuteriumTank` (:3145-3176): build when `capacity < hours × hourlyProduction` (default `hours=12`) or, with `forceIfFull`, when stored ≥ capacity;
always gated by `nextLevel ≤ maxLevel`.

---

## 3. Prices

### 3.1 Classic (`CalcPrice(Buildables, level, LFBonuses)`, :932-1244)

Per-case table; the recurring shapes:

- Mines/solar/fusion: `base × factor^(level−1)` with ⌆ — MetalMine 60/15 ×1.5, CrystalMine 48/24 ×1.6, DeuteriumSynthesizer 225/75 ×1.5,
  SolarPlant 75/30 ×1.5, FusionReactor 900/360/180 ×1.8. Energy need = `⌆10·L·1.1^L` (mines; **20·L·1.1^L for the synth**, :955).
- Storages ×2^level; Robotics/Shipyard/Lab/Silo/Nanite/LunarBase/Phalanx/JumpGate/AllianceDepot/Terraformer ×2^(L−1); SpaceDock ×5^(L−1) metal/deut
  and ×2.5^(L−1) energy.
- Defences/ships: `unitCost × level` (linear!) — e.g. RocketLauncher 2000·L metal.
- Researches: ×2^(L−1) except Astrophysics ×1.75^(L−1) and Graviton energy 300 k×2^(L−1).
- LF cost-reduction block (:1230-1241): if `LFBonuses.CostTimeBonusesInt` has the buildable's int key, `reduction = …Cost` and every resource is
  scaled `×(1−reduction)`. **The `if/else if` has two identical conditions** — the second branch is unreachable (harmless but flagged).

`StructuralIntegrity` (used by production time) is **metal plus crystal cost** (`Resources.StructuralIntegrity`, defined on the model at lines 43–46).

### 3.2 Lifeform buildings / techs

`CalcPrice(LFBuildables, …)` (:1246-1726) and `CalcPrice(LFTechno, …)` (:1728-2318) are giant per-item base/factor tables feeding:

```
CalcLFPrice   (:2320)  resources = ⌆(1 − costReduction/100) × base × level × factor^(level−1)
CalcLFEnergy  (:2324)  energy    = round((1 − energyCostReduction/100) × base × level × factor^level)     # note ^level, not level−1
CalcLFPop     (:2328)  population= ⌆(1 − populationCostReduction/100) × base × factor^(level−1)            # no ×level
```

`costReduction` inputs: Rocktal `Megalith` level (percent) for both resource and population reductions
(`CalcLFBuildingsResourcesCostBonus`/`…PopulationCostBonus`, :3794-3816); Kaelesh `PsionicModulator` gives `2×level` to the population *tech cap check*
only (:3818-3828). All three reducers default 0.

### 3.3 Max buildable

`CalcMaxBuildableNumber` (:3010-3030): min over resources of `⌊resource / unitCost⌋` (ToZero), `long.MaxValue`→0 for free items.
`CalcmaxDefencesBuildable` (:3032-3053): greedy round-robin — repeatedly buy 1 of each still-needed type while affordable.

---

## 4. Production (build) times

### 4.1 Classic — `CalcProductionTime(Buildables,…)` (:2364-2467)

```
buildings/facilities/moons:  h = SI / (2500 × (1+Robotics) × speed × 2^Nanites)
ships/defences:              h = SI / (2500 × (1+Shipyard) × speed × 2^Nanites)
researches:                  h = SI / (1000 × (1+cumulativeLabLevel) × speed)
                             discoverer ⇒ ×3/4 ; technocrat ⇒ ×3/4 (sequential)
return round↑(h × 3600)  [seconds]
```

`SI = CalcPrice(buildable, level).StructuralIntegrity`. Default `facilities` when null: Robotics 0, Nanites 0, Shipyard 1, Lab 1 (:2365-2372).
`cumulativeLabLevel == 0` falls back to the local lab. `CalcCumulativeLabLevel` (:2343-2358) = sum of the best `IRN+1` *planet* labs (null-safe ⇒ 0).
The research branch is used with `ServerData.SpeedResearch` by AutoResearch's IRN check.

### 4.2 Lifeform — `CalcLFTime` (:2995-3008), two overloads

```
LFBuildings: t = floor( level × baseTime × factor^level )
             t = round( t / ((robots+1) × 2^nanites) )        # nanites default 1 in the signature!
             t = round( (1 − speedReduction/100) × t / speed )
LFTechno:    t = floor( level × baseTime × factor^level )
             t = floor( (1 − 0.01×speedReduction) × t ) ; floor(t / speed)
```

`speedReduction` for buildings = Rocktal `Megalith` level (:2482-2488); the LFTechno path receives 0 from the public overload unless a caller passes
the reduction. Base times/factors are per-item in `CalcProductionTime(LFBuildables…)` (:2490-2688) / `(LFTechno…)` (:2696-2988) — e.g. ResidentialSector
1.21/40 s, ResearchCentre 1.25/16000 s, RoboticsResearchCentre 1.25/16000 s, VortexChamber 1.25/16000 s.

---

## 5. Investment return (ROI) family — the Brain's ranking core

All use `ConvertedDeuterium` costs and `/2.5`, `/1.5` production weights:

- **`CalcROI`** (:3294-3325): `(ΔhourlyProd_converted) / cost` — hourly, no ×24.
- **`CalcDaysOfInvestmentReturn`** (:3327-3357): `cost / ΔdailyProdConverted` where Δ uses level+1; non-mine ⇒ `float.MaxValue`.
- **`CalcNextDaysOfInvestmentReturn`** (:3359-3379): min of the three mine-DOIRs, `NaN ⇒ MaxValue` per term.
- **`CalcNextPlasmaTechDOIR`** (:3381-3405): `(plasma level+1 cost) / Σ_planets ΔdailyConverted`.
- **`CalcNextAstroDOIR`** (:3407-3445): cost = next astro level, **plus the following level too when current Astro is odd** (a pair = one planet);
  plus the sum `1..avgLevel` of mine costs at the *average* mine levels across planets; benefit = `dailyConverted / planets.Count` (one more
  average planet). `Δ = benefit`.

`GetNextMineToBuild` (full-context variant :3254-3292) picks the cheapest mine by …`ConvertedDeuterium` **cost**, *not* by DOIR — but gates the result
behind `maxDaysOfInvestmentReturn ≥ DOIR(best)`; the 3-arg legacy variant (:3224-3252) has no DOIR gate. Start-optimisation override:
`MetalMine ≤ CrystalMine+2`, `CrystalMine ≤ Deuterium+2` while below 10/7/5.

**Crawlers** (:4788-4817): max = `8 × (M+C+D levels)`, ×1.1 effective (**8.8×**) when Collector ∧ Geologist. `CalcOptimalCrawlers` scores every count
`current..max` by `cost(next−current crawlers) / ΔdailyConverted` **with `crawlerRatio = 1.5F` hard-coded** in the production calls (:4803-4804) and
keeps the cheapest count whose ratio ≤ mine-DOIR; returns `chosen − current`.

**`ShouldResearchEnergyTech`** (:4420-4442): needs ≥1 fusion planet; compares
`energyTechEnergy(level+1 @avgFusion)/energyTechCost` ≥ `fusionEnergy(avg+1 summed?)…` precisely: `fusionCost = ⌆fusion+1 cost × #fusionPlanets`,
`fusionRatio = fusionEnergy(avg+1)/fusionCost` vs `energyTechRatio = energy@avgFusion,tech+1 / techCost`; buy tech when `techRatio ≥ fusionRatio`.

---

## 6. Research selection — `GetNextResearchToBuild` (:4444-4630)

Order: lab-first gate → `optimizeForStart` ladder → expo-slot guard → cheapest-of-eligible. Eligibility = lab level ∧ prerequisite techs ∧ cap:

| Research | Lab ≥ | Prerequisites | Default cap (param) |
|---|---|---|---|
| Energy | 1 | – | 20 |
| Laser | 1 | Energy 2 | 12 |
| Ion | 4 | Energy 4 ∧ Laser 5 | 5 |
| HyperspaceTech | 7 | Energy 5 ∧ Shielding 5 | 20 |
| Plasma | 4 | Energy 8 ∧ Laser 10 ∧ Ion 5 | 20 |
| Combustion | 1 | Energy 1 | 19 |
| Impulse | 2 | Energy 1 | 17 |
| HyperspaceDrive | 7 | HyperspaceTech 3 | 15 |
| Espionage | 3 | – | 8 |
| Computer | 1 | – | 20 |
| Astrophysics | 3 | Espionage 4 ∧ Impulse 3 | 23 |
| IRN | 10 | Computer 8 ∧ HypTech 8 | 12 |
| Weapons | 4 | – | 25 |
| Shielding | 6 | Energy 3 | 25 |
| Armour | 2 | – | 25 |
| Graviton | 12 | level 0 ∧ spare energy ≥ cost | – |

Graviton energy check compares `ResourcesProduction.Energy.CurrentProduction` against `CalcPrice(Graviton, next).Energy` (:4611-4618).
Quirk: start-optimisation's second Combustion branch caps by `maxComputerTechnology` (:4469).

Related: `CalcMaxPlanets` (:4772-4778) `⌊(Astro+3)/2⌋`-ish — precisely `roundToZero((float)(astro+3)/2)` — and `IsAstrophysicsPositionValid`
(:4780-4786) position windows 8:1-15, 6-7:2-14, 4-5:3-13, 1-3:4-12, else all. `ShouldAbandon` (:4819-4824): fields < `MinFields` **or** max-temp
outside `[MinTemperatureAcceptable, MaxTemperatureAcceptable]`.

---

## 7. Lifeform population/food model (:3880-4066)

```
livingSpace(L)      = floor( base_L × factor_L^level × (level+1) × (1+bonus) )      # Residential 210/1.21, Meditation 150/1.216,
                                                                                     # Assembly 500/1.205, Sanctuary 250/1.21
foodProduction(F)   = floor( base_F × factor_F^level × (level+1) × (1+bonus) )      # Biosphere 10/1.14, CrystalFarm 6/1.14,
                                                                                     # FusionCell 23/1.12, AntimatterCondenser 12/1.14
foodConsumption(P)  = floor( base_P × 1.15^level × (level+1) × (1+bonus) )          # Residential 9, Meditation 5, Assembly 22, Sanctuary 11
satisfied           = floor( foodProduction / foodConsumption × livingSpace )
```

Bonuses (`Calc*Bonus`, :3917-4048): Humans food +0.05/BiotechLab level, living +0.015/Skyscraper, consumption −? no — consumption bonus *adds*
0.01/FoodSilo (it scales consumption **up** in the formula `×(1+bonus)`, :4027 — despite the name it is a consumption increase factor);
Mechas food +0.02/MicrochipAssemblyLine, living +0.02/ProductionAssemblyHall; Kaelesh living +0.02/ChrysalisAccelerator, consumption
+0.01/AntimatterConvector. Rocktal: none.

Population gating predicates (`planet.ResourcesProduction.Population.*` — model side, not in this file) used by `GetNextLFBuildingToBuild`:
`IsStarving/WillStarve/IsThereFoodForMore/IsFull/NeedsMoreT2/NeedsMoreT3(capBonus)`.

LF building **unlock requirements** (`GetLFBuildingRequirements`, :3481-3573): per-lifeform prerequisite chains (e.g. Humans ResearchCentre =
Residential 21 ∧ Biosphere 22; Rocktal AdvancedRecyclingPlant = 10 buildings incl. MineralResearchCentre 5). `isUnlocked` (:3575-3588) ⇒ true when the
table is empty (base buildings).

`GetNextLFTechToBuild` / `GetLessExpensiveLFTechToBuild` (:4068-4109): only techs with stored level ≥ 1 are ever considered; iteration is enum-order;
substitution keeps the cheapest next level under the caps.

---

## 8. Facility decision predicates (cheaper-than-next-mine family)

`ShouldBuildRoboticFactory/Shipyard/ResearchLab/MissileSilo/Nanites/SpaceDock` (:4199-4379) share the pattern
`nextLevel ≤ max ∧ (myCost < nextMineCost ∨ force) ∧ extra` where `nextMineCost` comes from `GetNextMineToBuild` with the *passed* mine caps and
`optimizeForStart`; extras: Shipyard←Robotics ≥ 2; SpaceDock←Shipyard ≥ 2 ∧ energy covers cost; Silo←Shipyard ≥ 1; Nanite←Robotics ≥ 10 ∧ Computer ≥ 10 ∧
(`cheaper ∨ myTime < mineTime`) ∧ no LF building queued ∧ (caller also requires `Productions.Count == 0`); Robotics on planets also blocks while an LF
building is queued (:4200-4203). On moons, Robotics/Shipyard reduce to `Fields.Free > 1`.

`ShouldBuildTerraformer` (:4329-4340): `EnergyTechnology ≥ 12 ∧ Fields.Free == 1 ∧ level ≤ max`.
Lunar: `ShouldBuildLunarBase` free == 1; `ShouldBuildSensorPhalanx` base ≥ 1 ∧ free > 1; `ShouldBuildJumpGate` base ≥ 1 ∧ HypTech ≥ 7 ∧ free > 1
(:4381-4418).

`GetNextEnergySourceToBuild` (:3185-3203) and deposit/facility ordering: see features/brain.md §2.1.

---

## 9. Fleet-bookkeeping helpers

- `IsThereTransportTowardsCelestial` (:4632-4646): inbound (non-return) Transport with resources to the exact coordinates incl. type.
  `AreThereIncomingResources` (:4648-4655) is the same via `IsSame`.
- `GetIncomingFleets` (:4657-4670): **union** of (a) inbound Transport/Deploy to the celestial and (b) *any* returning fleet whose origin is the
  celestial — ordered by `ArriveIn`/`BackIn` respectively. `GetIncomingFleetsWithResources` filters `TotalResources > 0`.
- `GetFirstReturningExpedition` (:4680-4689): expeditions with `Origin == coord`, min `BackIn`.
- `GetFirst/LastReturningEspionage`, `GetMissionsInProgress` (:4691-4734): trivial filters; the coordinate variant returns null-safe lists.
- `ParseCelestialsList` (:4736-4758): settings→entity join, keeps only IDs ≠ 0.
- `CalcSlotsPriority`: see features/brain.md §1.1 (:4867-4931). Note `rankSlotsPriority.Single(f => f.Feature == feature)` **throws** on duplicates.
- `CalcShipNumberForPayload` ⌆; `CalcMaxTransportableResources` §1.7.

## 10. Enumeration / misc

- `CalcMaxCrawlers` (:4788-4793), `CalcOptimalCrawlers` (:4795-4817) — §5.
- `CountPlanetsInRange` (:4826-4847), `IsThereMoonHere` (:4849-4865, sentinel `ID == 0`).
- `GetNextLevel` family (:3079-3139): reflection over `Buildings` then `Facilities`; **SolarSatellite on a `Planet` returns the needed-satellite count,
  not level+1**; researches/LF variants analogous (`LFTechs.GetLevel`).
- `GetMaxBuildings/GetMaxFacilities/GetMaxLunarFacilities` (:3447-3479): struct constructors from ints — note `GetMaxFacilities` has no lunar fields
  and vice versa; the *lunar* `Facilities` overload maps `RoboticsFactory→MaxLunarRoboticsFactory`, `Shipyard→MaxLunarShipyard` (caller-side, e.g.
  AutoMineCelestialWorker.cs:79-88).
- `ShouldBuildEnergySource` = `ResourcesProduction.Energy.Available < 0` (:3178-3183).
- `GetValidSpeedsForClass` — 100…10 % steps for all classes (:498-546).

## 11. Where the numbers are consumed (traceability)

| Consumer | Functions relied upon |
|---|---|
| AutoMineCelestial choice | `GetNextBuildingToBuild` → `ShouldBuild*` → `CalcPrice`, `CalcDaysOfInvestmentReturn`, `CalcProductionTime` |
| Transport sizing | `CalcShipNumberForPayload`, `CalcMaxTransportableResources`, `CalcFleetCapacity` |
| Timers | `CalcProductionTime`, `GetIncomingFleets(WithResources)`, `GetFirstReturningExpedition` |
| AutoResearch priorities | `CalcNextPlasmaTechDOIR`, `CalcNextAstroDOIR`, `ShouldResearchEnergyTech`, `CalcCumulativeLabLevel`, `CalcProductionTime(SpeedResearch)` |
| Crawlers | `CalcMaxCrawlers`, `CalcOptimalCrawlers`, `CalcPlanetHourlyProduction` |
| AutoCargo/Defence | `CalcFleetCapacity`, `CalcShipCapacity`, `CalcPrice`, `CalcMaxBuildableNumber`, `CalcmaxDefencesBuildable` |
| LF mine/research | `GetNextLFBuildingToBuild`, `GetNextLFTechToBuild`, `GetLessExpensiveLFTechToBuild`, `CalcPrice(LF*)`, LF cost-bonus helpers |
| Jump gate | none from this service (raw `Ships.GetFleetPoints`) |

## 12. Numerical quirks & suspected bugs (verify before refactoring)

1. **Deut from CrystalMine** in `CalcDeuteriumProduction(Buildings…)`/:912 and `(Planet…)`/:920 — vs `DeuteriumSynthesizer` in the int-overload
   callers; inconsistent hourly-deut between code paths.
2. **Dead `bonusProd`** in the same function: `:904` adds `deuteriumLFBonus` (percent) as absolute units.
3. **Bomber `× 3/2`** integer division ⇒ no-op (:404).
4. **`CalcFleetSpeed` starts at 0 and only lowers it**, so positive-speed fleets also return 0 (:345), unlike `CalcSlowestSpeed` (:322).
5. **Duplicate if-condition** in `CalcPrice` LF-reduction block (:1232/:1235) — dead `else`.
6. **Start-optimisation Combustion capped by `maxComputerTechnology`** (:4469).
7. **`CalcMaxBuildableNumber` uses unit cost at level 1** — correct for ships/defences (linear), wrong for anything exponential (not used for those).
8. **`CalcDepositCapacity` uses integer division in the exponent and truncates before ×5000** (:3142); do not substitute the continuous formula when explaining its output.
9. **`CalcDeuteriumProduction` level-0 returns 0 but metal/crystal return `baseProd`** — asymmetry is intended (mines produce at level 0? no:
   metal/crystal `level==0 ⇒ baseProd×speed`, deut ⇒ 0) — keep in mind when diffing production sums.
10. **`CalcMultipleOrigin` final else returns unreserved-deut resources** (:583) — unreachable in practice, noted for completeness.

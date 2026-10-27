# Direct Go model, simulator and utility audit

## Scope and evidence

- TBot baseline: `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`.
- Pinned `ogame` submodule: `fbd0fda6ba9019c128926614f9865ba38a67b627`.
- Assignment: `documentation-work/resume-audit/models-assigned.json` outside the source repository. Its original 170 paths were filtered against the current inventory at audit start. `ogame/pkg/ogame/constants.go` was already `read` and was not re-audited in this lane.
- **Completed: 169 files / 13,420 lines; partial: 0; remaining: 0.** Distribution: model package 166 files / 11,867 lines; simulator 1 / 1,253; utility package 2 / 300.
- Every assigned source file was read in actual line-numbered full-content batches, including tests and literal constructor/localization tables. No source batch was truncated. SHA-256 and line counts matched the assignment. Symbol indexing was not substituted for reading.
- [Machine-readable ledger](audit-models.json) records each path, actual hash, full range `[1,last]`, semantic role, substantive behavior, findings and test safety. These are checkable attestations, not a claim that range validation proves comprehension.
- Progress and executable evidence are outside the repository at `/home/kelsier/Projects/TBot/documentation-work/resume-audit/`. No runtime implementation, README, shared handbook page or shared inventory was changed by this lane. No commits or pushes.

Existing [calculations](../calculations.md), [infrastructure models](../infrastructure-models.md) and [daemon](../daemon.md) pages were read for comparison, not used as authority for Go behavior. The calculation page documents **C#**, not the Go model. Differences below are additions/boundary corrections, not instructions to replace the C# implementation's documented formulas with Go formulas. C# source verification belongs to the separate parent audit.

All source citations refer to the pinned submodule. Bare Go filenames resolve under `ogame/pkg/ogame/`; utility-package and simulator files are explicitly qualified, and subsequent `:line` citations retain that section's named file. Metadata/calculation methods are not proof that a build, flight, purchase, recall or other real game operation is valid or safe.

## 1. Pricing and construction corrections (M01–M04, M06–M08)

Notation: `trunc` is Go float-to-integer truncation; `round` is `math.Round` (ties away from zero); bonus inputs are fractions unless explicitly described otherwise. Levels/counts, speed multipliers and reductions are generally **not validated** by these helpers. A nil bonus map can be read safely and contributes zero, but writing it panics.

### Classic prices

`ogame/pkg/ogame/baseLevelable.go:15–26` constructs M/C/D/E using:

```text
raw = trunc(baseCost * increaseFactor^(level-1))
net = raw - trunc(raw * perIDCostBonus)
```

Population, food and dark matter are not retained. For ordinary nonnegative costs and reductions, subtracting a truncated reduction is not the same rounding order as truncating the final discounted value. Level zero is not rejected: metal mine level zero costs 40 metal / 10 crystal in the characterization, rather than returning an invalid-level error.

- **Astrophysics:** nearest 100 first, then the same `SubPercent`; `astrophysics.go:22–33`. Level 9 is 351900 / 703700 / 351900. It does not follow the C# page's generic ceiling rule.
- **Graviton:** base energy 300000, **factor 3**, not the C# calculator's factor 2 (`gravitonTechnology.go:7–14`). Level 2 energy 900000 was executed offline. The generic availability check only requires energy 300000, without a requested-level argument (`base.go:56–58`).
- **Space dock:** M/D factor 5, energy factor 2.5, each with exponent `level-1`, truncation then discount (`spaceDock.go:22–33`).
- **Ship/defence quantities:** multiply M/C/D unit price by count, then apply the per-ID cost fraction (`baseDefender.go:61–65`). No positivity/count limits are enforced here, including maximum-one domes.
- **Energy consumption is separate:** mine `GetPrice` returns no energy component; `EnergyConsumption` computes it. Do not infer Go energy consumption from a C# price object's `Energy` field (`metalMine.go:20–29`, `crystalMine.go:20–29`, `deuteriumSynthesizer.go:20–27`).

### Classic times and teardown

`baseBuilding.go:27–41`:

```text
seconds = (discountedMetal + discountedCrystal) * 3600
          / (2500 * (1+robots) * universeSpeed * 2^nanites)
if level <= 5 and object != NaniteFactory:
    seconds *= 2/(8-level)
duration = floor(max(1, seconds)) seconds
return duration * (1-perIDDurationBonus)
```

The early-level multiplier is missing from a generic shared C#/Go time explanation. Reduction is **after** flooring and the one-second minimum; the final duration can be subsecond, zero or negative. A 25% reduction of the one-second minimum yielded **750 ms**, not one second. Discounts are not clamped. Precisely, each duration-reduction path returns `time.Duration(float64(dur)-float64(dur)*bonus)`: `dur` is the integer nanosecond representation, the arithmetic is float64, and conversion back truncates fractional nanoseconds. Multiplication by `(1-bonus)` in the displayed formulas is algebraic shorthand, not a promise of bit-identical floating evaluation.

`baseDefender.go:45–52` instead uses **undiscounted unit StructuralIntegrity**, floors a minimum-one-second unit duration, multiplies by count, then applies duration bonus. It does not recalculate duration from the cost-discounted quantity price. Zero count yields zero; negative counts can yield negative duration.

`baseTechnology.go:15–30` uses `(M+C)*3600/(1000*(1+lab)*speed)`, sequential `*.75` for Technocrat and Discoverer, then the same minimum/floor/reduction ordering. The caller supplies speed and lab aggregation: this method does not discover other planets or compute IRN levels. Zero-value `Facilities` supplies lab/yard zero, unlike C# calculator null-fallback defaults described in calculations.md.

**Embedded receiver boundary:** `BaseTechnology.TechnologyConstructionTime` invokes its embedded generic `GetPrice`, not dynamic dispatch into `astrophysics.GetPrice`. Thus direct astrophysics quotations use nearest-100 rounding while inherited duration uses the generic truncated price (`astrophysics.go:22–33`; `baseTechnology.go:16`; `baseLevelable.go:15–26`). The same static embedding principle matters when adding future overrides.

Teardown computes `trunc(floor(base*factor^(level-1)) * (1-.04*IonTechnology))`; Ion levels above 25 can produce negative prices (`baseBuilding.go:14–24`). Lunar base and terraformer return an all-zero price to represent **cannot deconstruct**, not a free authorized operation (`lunarBase.go:17–20`, `terraformer.go:17–20`). Satellites also have a zero compatibility stub.

### Lifeform formulas are separate implementations

`lfBuildings.go:305–336`:

```text
building M/C/D = trunc(base * level * resourceFactor^(level-1))
building E     = trunc(base * level * energyFactor^(level-1))
building pop   = trunc(base * populationFactor^(level-1))
seconds        = level * durationBase * durationFactor^level
                 / ((1+robots) * 2^nanites * universeSpeed)
duration       = floor(max(1,seconds)) seconds * (1-perIDDurationBonus)
```

**GetPrice ignores the entire `LfBonuses` argument.** No automatic Megalith reduction is applied here. Building energy uses exponent **level-1**, not the C# `CalcLFEnergy` exponent `level`. Biosphere level 2 energy 16 was executed offline. Inherited teardown is still the generic building formula, not a lifeform-specific inverse calculation.

`lfResearches.go:473–499`:

```text
research M/C/D = trunc(base * level * factor^(level-1)
                      * (1-PlanetLfResearchCostTimeBonus.Cost))
seconds        = level * durationBase * durationFactor^level / universeSpeed
duration       = floor(max(1,seconds)) seconds * (1-perIDDurationBonus)
```

There is no lab, robot, nanite, class or Technocrat effect in LF research time. **PlanetLfResearchCostTimeBonus.Duration is ignored**; the per-ID duration map is used instead. Per-ID cost bonuses are ignored for LF research price. The planet cost fraction is applied before truncation, unlike classic `SubPercent` ordering. Envoys level 2 at speed 8 stayed 360 seconds with a 50% planet duration bonus and became 180 seconds with a 50% per-ID duration bonus; both executed.

The 48 LF building and 72 LF research definitions were read in full. Constructors specify prices, duration curves and prerequisite metadata; names such as Megalith, Robot Assistants or Supercomputer do **not** implement their advertised game effects automatically. All LF research constructor requirement maps are empty. Model availability has no active-lifeform, selected-slot or population-capacity validation (`lfResearches.go:507–1657`; `base.go:26–106`).

## 2. Ship speed, cargo and fuel (M05, M14–M15)

### Cargo — `baseShip.go:16–32`

```text
cargo = base + trunc(base * LFcargo)
             + trunc(base * hyperspaceTech * multiplier)
Collector small/large cargo: +trunc(base*.25)
General recycler:           +trunc(base*.20)
Probe raids disabled:       return 0 immediately
```

The explicit hyperspace multiplier is a fraction (e.g. `.05`), not the XML/C# percentage integer. There is **no General pathfinder cargo bonus** in this Go method; zero-tech General pathfinder remained 10000. Separate truncation explains the probe test: base 5, hyperspace 14, multiplier .05 gives 8, not rounded 9 (`espionageProbe_test.go:16–19`).

### Speed — `baseShip.go:54–96`

Start with base speed and add base-scaled bonuses: drive `.1*combustion`, `.2*impulse` or `.3*hyperspace`, plus LF speed. Trader adds `.1*base` only to small/large cargo. Collector adds one base speed to small/large cargo; General adds one base speed to recycler/combat ships **except Deathstar**. Round the final speed.

Thresholds:

- Small cargo impulse >=5: base 10000, impulse drive.
- Bomber hyperspace >=8: base 5000, hyperspace drive.
- Recycler hyperspace >=15 takes precedence: base remains 2000 internally, whole result multiplied by 3. Otherwise impulse >=17 multiplies the whole result by 2. LF/class bonuses are inside that multiplier, not applied afterwards.

A speed quotation does not test build availability: the reaper test deliberately calculates speed as Discoverer even though only General can build it (`reaper_test.go:8–12`; `base.go:59–62`).

### Fuel — `baseShip.go:36–50`

```text
baseFuel *= 2 for small cargo impulse>=5
baseFuel *= 3 for recycler hyperspace>=15,
         else 2 for recycler impulse>=17
f = fleetDeutSaveFactor * baseFuel
lf = f * signedLFFuelConsumption
if General: f /= 2
fuel = max(trunc(f + lf), 1)
```

Positive LF fuel fractions **increase** consumption. Negative fractions reduce it. The LF term uses the amount **before** General halving, so it is not equivalent to applying LF reduction and then halving everything. Large cargo with General and LF `+.1` consumed 30, not 27 or 28. The existing negative-LF test yields 24 from a 25-unit discounted base (`largeCargo_test.go:24–28`). Bomber has no hyperspace fuel adjustment in this Go implementation. Even the stationary crawler's base fuel zero is exposed as minimum 1 by the generic fuel getter; do not send it as a flyable unit.

### Fleet DTO operations

`ships.go:30–229` distinguishes mutation, positivity and flyability:

- `ToPtr` returns a pointer to a **copy**. `FromQuantifiables` returns a new DTO, ignores its receiver and uses last duplicate-ID assignment.
- `Set`, `Add`, `Sub`, `AddShips`, `SubShips` mutate pointer receivers. `Set` permits negative counts. `Add` propagates an incoming `-1` send-all sentinel; ordinary sums clamp to zero. `Sub` clamps and does not preserve the sentinel.
- `Iter` / `Each` include only **positive** counts, including satellites/crawlers. Thus `HasShips`, `IsEmpty`, `CountShips`, cargo and fleet-cost/value calculations ignore `-1` but do not mean “flyable fleet.”
- `IterFlyable`, `EachFlyable`, `ToQuantifiables`, `Speed` exclude satellites/crawlers. Empty/nonflyable-only fleet speed is **math.MaxInt64**, ID zero, not speed zero.
- `Has` ignores requested counts <=0: `Has({SmallCargo:-1})` is true even with no ships. `Get(any)` accepts a typed `ID` or `Ship`, not an ordinary int.
- Combat stat sums iterate the full registered ship list and can include negative counts, unlike positive-only quantity iteration (`ships.go:232–253`).

Satellite is a ship deliberately made to satisfy `Building`: `GetLevel` always zero; `DeconstructionPrice` zero; **BuildingConstructionTime panics**. Its ordinary `ConstructionTime` follows the shipyard/defender path (`solarSatellite.go:39–50`, `objs.go:250–275`). An entry in `Buildings` is not a guarantee that every building-only method is usable.

## 3. Resource and production semantics (M06, M09)

`resources.go:72–189` is not interchangeable with C# `Resources`:

| Operation | Exact Go behavior |
|---|---|
| `Total` | M+C+D only |
| `Value` | M+2C+3D; not `ConvertedDeuterium` |
| `Add`, `Mul` | new M/C/D-only value; discard E/DM/population/food |
| `Sub` | clamp each M/C/D difference at zero; discard other fields |
| `SubPercent` | retain M/C/D/E only, subtract truncated reduction; discard DM/population/food |
| `Div` | minimum integer quotient for strictly positive M/C/D prices; free price returns architecture `math.MaxInt` |
| `CanAfford`, `Gte`, `Lte` | compare only M/C/D; ignore energy and other fields |
| `CanAfford2` / `Gte2` | optionally add population; still ignore energy/food/DM |
| `FitsIn` | ceil(Total/cargo), but cargo zero returns **0**, not an error or impossibility sentinel |

All arithmetic methods above are value receivers; assignments are required to retain results. `ResourcesDetails.Available` is different: it copies all seven available amounts (`resources.go:58–68`). Resource-detail population `Hungry` and `GrowthRate` are float64 (`resources.go:36–44`), unlike the C# table's long fields.

The simple Go production helpers do not include position, officers, crawler, LF production or class bonuses:

```text
Metal/hour   = trunc(30*speed*(1+.01*plasma)*L*1.1^L*ratio*global +30*speed)
Crystal/hour = trunc(20*speed*(1+.0066*plasma)*L*1.1^L*ratio*global +15*speed)
Deut/hour    = round(10*speed*(1+.0033*plasma)*L*1.1^L
                    *(1.36-.004*avgTemp)*ratio*global)
Solar energy = floor(20*L*1.1^L)
Fusion energy= round(30*L*(1.05+.01*energyTech)^L)
Fusion fuel/h= abs(floor(-10*speed*L*1.1^L*ratio))
```

Sources: `metalMine.go:20–29`, `crystalMine.go:20–29`, `deuteriumSynthesizer.go:20–27`, `solarPlant.go:20–22`, `fusionReactor.go:21–31`. Basic metal/crystal income is outside the ratio/global multiplier; crystal basic income here is **15**, not 20. Mine energy consumption is ceil(10*L*1.1^L), or 20 for deuterium. Production at zero mine level keeps basic metal/crystal, but deuterium is zero.

Satellite energy first rounds mean temperature away from zero, truncates `(mean+160)/6` **per satellite**, multiplies by count, then adds rounded 10% Collector bonus on aggregate (`temperature.go:11–13`, `solarSatellite.go:31–36`). Engineer/staff arguments do not exist in this helper.

Storage capacity is `5000 * trunc(2.5*e^(20*float64(L)/33))` (`storageBuilding.go:12–13`). The exponent uses **floating division**, unlike the integer division in the documented C# calculator. Capacity levels 0..5 are 10000, 20000, 40000, 75000, 140000, 255000; truncation happens before multiplication by 5000.

## 4. JSON, defaults, pointers and availability (M10–M13, M16–M17)

### Raw model shape is not the entire HTTP adapter contract

Unless a field has a tag or a type has custom marshaling, Go JSON exports the declared exported field name, includes zero values, emits nil pointers/maps/slices as null, and keeps numeric aliases numeric even when they implement `String`. Anonymous embeddings flatten fields. Do not copy C# constructor defaults into Go zero-value DTO descriptions.

| Source | Wire/presence boundary |
|---|---|
| `constructions.go:5–16`; `technologyDetails.go:5–10` | Raw `Construction` has ID/Countdown/Level and four nested slots; `TechnologyDetails` has ProductionDuration. `time.Duration` is a numeric **nanosecond** count in default JSON. Two seconds serialized as 2000000000. A daemon handler may deliberately project these to different, flattened seconds fields; the C# construction table describes that separate contract, not raw marshaling. |
| `planetInfos.go:68–87` | SystemInfos custom marshaler includes only Galaxy, System, 15 Planets and ExpeditionDebris. Relocations, Events and OverlayToken are omitted despite exported fields. No matching custom unmarshal restores private galaxy/system/planets; JSON roundtrip loses those. |
| `planetInfos.go:47–64` | SetPlanet uses unchecked zero-based index; Position uses 1..15 and returns nil outside it. Each calls the callback exactly 15 times, including empty/nil positions. Returned planet pointers alias original objects. |
| `techs.go:4–11` | ResourcesBuildings and ShipsInfos both promote SolarSatellite at equal depth. Default JSON omits that ambiguous key entirely; it does not select or sum a copy. Verified offline with counts 3 and 4. Other multi-embedded methods can also be ambiguous. |
| `planet.go:4–40` | Planet.Moon nullable; GetMoon returns the same pointer. Planet.GetType/Moon.GetType return fixed type constants even if the stored Coordinate.Type disagrees. No consistency check. |
| `chatMsg.go:6–18`; `ogame.go:280–299` | Chat and minifleet use explicit camelCase/lowercase tags; not the general PascalCase rule. Chat Date is raw int64, not a time.Time. |
| `item.go:4–35` | canBeActivated is unexported and absent from JSON; commented-out item properties are not implemented API fields. |
| `lfBonuses.go:3–50` | Numeric-string ID keys in two maps. Constructor initializes those maps only. The actual resource group contains only ResourcesExpedition; class group only Characterclasses3; misc only PhalanxRange. Broader C# fields are not evidence the Go parser fills them. |
| `dmCost.go:20–28` | String includes both action tokens. Do not call it a secret-free diagnostic; DTO display does not purchase anything. |

AttackEvent.Ships is a nullable pointer (`attackEvent.go:9–22`); Fleet.Ships is a value struct (`fleet.go:8–24`). Missing/unknown incoming intelligence is not the same representation as a known zero count. Neither String output is a substitute for the complete serialized DTO.

### Espionage intelligence and plunder

`espionageReport.go:9–92` flattens embedded Resources and stores optional scanned counts/levels as `*int64`. Section flags and individual nullable fields are separate information channels.

Conversion helpers (`:95–200`) return nil when the corresponding section flag is false. When true, they allocate a fresh DTO and dereference every nil individual field to zero. Thus raw null-vs-zero is lost in the helper result.

`IsDefenceless` (`:230–235`) requires both fleet and defence information flags; then it checks no positive ship counts and no counted ship-firing defences. **All nil individual fields with both flags true are accepted as defenceless.** Domes, ABM and IPM do not block this predicate; probes, satellites and crawlers do block it because HasShips includes stationary/civil ships. There is no `isUsingProbes` argument, unlike the C# helper described in infrastructure-models.md.

`defence.go:33–58` distinguishes two concepts: CountShipDefenses excludes both missiles **and both domes**; AttackableValue includes domes but excludes missiles. Aggregated weapon/shield/SI iterate the full Defenses list, including missile metadata (`:61–81`). These are not interchangeable threat/value functions.

Plunder (`espionageReport.go:204–224`): default .5; inactive Discoverer .75; bandit 1 overrides other flags; active starlord .75. HonorableTarget and IsLongInactive alone do not change it. Loot truncates only M/C/D and returns a new Resources; no cargo-limit allocation occurs here.

### Lazy adapters and mutation

- Facilities, Researches, ResourcesBuildings and LfBuildings `.Lazy()` capture **value snapshots**, not live links to a mutated original (`facilities.go:50–53`, `researches.go:72–75`, `resourcesBuildings.go:44–47`, `lfBuildings.go:188–191`). Explicit `Lazy*` callback types evaluate their callback on every getter; no memoization or nil callback protection.
- LfResearches has 72 pointer-valued fields. Its value snapshot retains pointers to the same pointees: changing `*getter()` affects the original pointee, but reassigning an original field later does not change the lazy snapshot (`lfResearches.go:120–285`). Getters/ByID do not allocate defensive copies. Unknown research ID returns nil, unlike classic ByID zero.
- `LfResearchDetails.AvailableSlot` returns the first Allowed slot (1-based), ignoring Locked, TechID and Level; zero if none (`lfResearches.go:439–462`). “Allowed” is not a complete research-validity decision.
- `Objs.ByID` and `GetShip` return shared registered pointers/interfaces, unknown nil. The registry, exported object fields, maps and category slices are mutable, not immutable constants (`objs.go:192–247`). `Base.GetRequirements` and rapidfire getters return the original maps (`base.go:20–22`, `baseDefender.go:34–41`).
- No global synchronization or deep-copy guarantee is added by these model helpers. A read-only caller should avoid mutating shared metadata accidentally.

### Availability is a narrow metadata predicate

`base.go:26–106` rejects nonplanet/nonmoon types, selected planet-only facilities/mines on moons, lunar facilities on planets, and classic research on moons. Graviton requires fixed 300000 energy; reaper/pathfinder/crawler construction is class-gated General/Discoverer/Collector.

Direct prerequisite levels are checked against the supplied DTO interfaces. **Only classic research objects on planets recursively expand prerequisites.** Defences/ships/buildings can be available based on owned direct prerequisites without rechecking the entire historical unlock chain (see lab-zero light-laser test, `lightLaser_test.go:9–12`). There is no visited/cycle guard; corrupted mutable metadata can cause unbounded traversal or nil-object dereference.

LF research is not `ID.IsTech()` (`id.go:500–518`, `608–613`), so the classic moon-tech exclusion does not automatically exclude LF research. LF constructors with empty requirements can therefore pass this predicate without slot/population checks. Likewise LF building GetLevel inherits a function that only handles resource buildings/facilities, and LF research GetLevel inherits classic Researches.ByID: neither retrieves LF DTO levels through that interface (`baseBuilding.go:50–56`, `baseTechnology.go:39–40`). Use the LF DTO's ByID instead.

`Slots.IsAllSlotsInUse` tests **equality**, not >= (`slots.go:11–13`). Zero-value 0/0 slots block every mission; an overfull 3/2 counter is not blocked by the main-slot arm. `Fleet.IsCancellable` is only `!ReturnFlight && !InDeepSpace && Mission!=MissileAttack`; even a zero fleet passes (`fleet.go:26–33`). Neither predicate is remote authorization.

### Coordinates, identity and rounding

`coordinate.go:17–103` constructors do not validate bounds. Coordinates compare lexicographically by galaxy/system/position/type, so planet and moon at the same position differ. Planet/Moon/Debris conversion methods return copies. Zero coordinate is all four fields zero, not C# default 1:1:1 Planet.

`ParseCoord` (`utils.go:16–46`) accepts optional uppercase P/M/D and 1–3 decimal digits per axis, defaults Planet, and independently permits opening/closing brackets. It accepts `[999:999:999` without a closing bracket and does not restrict position to 1..15 or 16. Invalid input returns zero coordinate plus error; DoParse discards that error; MustParse panics. Syntax acceptance is not universe validation.

`ID.IsSet` is nonzero (negative counts as set), whereas FleetID.IsSet is >0 (`id.go:14–16`, `fleetid.go:15–17`). `Speed` is float64 engine units, 10=100%, .5=5%; Int/Int64 truncate half-steps (`ogame.go:21–84`). Type String formatting is not JSON string encoding.

## 5. Simulator limits and formula contract (M19)

**Do not document this as a complete or authoritative current-game combat simulator.** Source: `ogame/pkg/simulator/simulator.go`, all 1253 lines read. It is account-free computation, not a game action.

### Public inputs silently lose supported-looking data

`Attacker` and `Defender` embed full ShipsInfos, but public Simulate copies only the older selected counts (`:1081–1149`). **Reaper, Pathfinder and Crawler are never copied for either side.** Attacker satellites and all defences are forced zero. Missiles are absent from the combat model. A reaper-only attacker against empty defence was a 100% draw; one large cargo against a reaper-only defender was a 100% attacker win. These deterministic characterization outcomes prove input loss, not combat balance.

Defender Metal/Crystal/Deuterium are unused for loot. There are no LF bonuses, classes, ACS participants, server rapidfire toggle, defence repair factor, reaper debris collection or deuterium-debris setting. Config's Workers/IsLogging fields are not accepted by the exported Simulate API (`:953–1007`, `:1219–1223`); actual simulations run serially, logging forced false (`:1151–1158`).

### Combat internals

- Separate internal 25-unit IDs and hardcoded price/stat/rapidfire tables (`:16–42`, `:109–490`), not the shared ogame registry. Probe shield/weapon **1** here versus integer **0** in `espionageProbe.go:12–13`. Simulator reaper rapidfire omits battlecruiser, though model reaper metadata specifies 7 (`:469–483`; `reaper.go:18`).
- Each CombatUnit is one packed uint64: 5 ID bits, 18 shield bits, **22 hull bits**. Setters shift values without masking/validation. Declared armour36/shield42 maximum constants are not enforced (`:49–85`). High research can spill fields/corrupt packed state; no claim of correctness beyond these representational limits.
- Hull starts `(M+C)/10*(1+.1*armour)`, shield/weapon base times `(1+.1*research)`, truncated to uint64 (`:549–566`). Counts narrow int64 to int. Allocation is per unit, not per ship type; negative/huge counts are unvalidated and can panic or exhaust memory (`:1050–1077`, `:1097–1149`).
- Six rounds max. Attacker fires, defender fires, then destroyed units removed and shields restored (`:923–950`). Destroyed defenders still fire in that round. Dead targets can still be selected before removal. Rapidfire is checked before target liveness (`:765–780`).
- Bounce condition is weapon <1% of **current remaining shield**. Shield absorbs damage first; hull persists between rounds. If surviving hull is <=70% of initial, explosion probability is `1-hullFraction` (`:665–690`, `:725–762`). Rapidfire continuation probability `(rf-1)/rf` uses `dice<=chance` (`:693–722`).
- Uses global math/rand and source calls rand.Seed(time.Now().UnixNano()) per side salvo (`:765–766`). No supplied RNG/seed or reproducibility API. Exact rand.Seed behavior is toolchain-dependent; do not promise reproducibility from this call.

### Results and defaults

Losses use full hardcoded M/C/D price. Debris uses **only ship M/C**, multiplied by FleetToDebris and truncated **per destroyed unit**; no defence or deut debris (`:834–869`). Moonchance is integer min((M+C)/100000,20) per run (`:894–897`).

Public aggregation (`:1174–1196`) rounds win/draw percentages independently, so their sum need not be exactly100; rounds are rounded mean, losses/debris/moonchance truncated mean. Recycler estimate is ceil(mean M+C debris /20000), fixed base capacity without research/class/LF. Logs remain empty through this API.

**Simulations has no positive default or validation.** Zero/negative values skip the loop and divide by the invalid count during aggregation. Do not advertise a sensible zero-config result. No upstream tests exist in this package; successful `go test` compiles it but cannot by itself verify combat correctness.

## 6. Utility and localization boundaries (M18)

`ogame/pkg/utils/utils.go`:

- ParseInt removes every `.` and `,`, trims whitespace, then parses signed decimal; it is a thousands-separator parser, not locale decimal parsing (`:16–20`). DoParseI64 suppresses errors; bad syntax generally yields zero while overflow can yield strconv's saturated limit (`:45–51`). ToInt assumes raw digit bytes and performs no validation (`:23–27`).
- GetNbr **mutates** the supplied DOM by removing span.level children; GetNbrShips checks title attributes and returns0 on no regex match (`:77–95`). No HTTP request is made by either helper.
- Random integer bounds are inclusive and swapped if inverted; RandFloat is upper-exclusive in the ordinary case. RandMs scales endpoints to durations before choosing nanoseconds, so it is not restricted to whole millisecond samples. Empty RandChoice panics. Span/endpoint arithmetic is not overflow-guarded (`:119–160`).
- Count2 counts yielded **pairs**, not quantity values; Any2 empty=false, All empty=true (`:163–188`). Ternary takes normally evaluated Go arguments, not lazy branches.
- **RoundThousandth floors**, despite its “nearest” comment: floor(n*1000)/1000; -1.2341 became -1.235 (`:208–210`).
- Find/FindIdx return a pointer to the range **copy**, not the original slice slot; modifying it leaves the slot unchanged. No match nil/-1. Ptr/I64Ptr copy values, Deref nil=>zero, Default nil=>fallback but retains nonnil zero (`:223–251`).

Localized lookup (`ogame/pkg/ogame/utils.go:49–747`) normalizes NFD, removes combining marks, recomposes NFC, strips characters outside an explicit whitelist, lowercases, then uses finite maps. Unknown ship/defence returns NoID0 without error. Whitelisting strips characters such as ß/ł/ø/æ rather than transliterating them; literal map keys reflect those removals. Some locale entries resolve through shared keys in another locale. Translation coverage is finite, not a promise of support for every label/version. Resource-name predicates differ: exact membership of exported mutable strings, with **no** case/accent normalization (`:66–87`).

The full 730-line model utility test file was read, including its explicit multilingual assertion corpus. It covers expected labels and several invalid inputs, not arbitrary normalization/range correctness. It contains no network calls.

## 7. Executed offline verification

Toolchain actually used: **go1.27.2 linux/amd64**, project-local binary. No toolchain/package installation, credentials, live accounts, real network calls, clients, daemons, services, Sparks or game actions. Only local Go build cache and two checked-in HTML samples were used. Both local fixtures were confirmed present before tests: `ogame/samples/unversioned/deathstar_price.html` and `mrd_price.html`. Package source/init/import surfaces were inspected first; all package Go files are within this assignment plus already-read constants.go.

Run from `/home/kelsier/Projects/TBot/source/ogame`:

```sh
GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  /home/kelsier/Projects/TBot/documentation-work/toolchains/go/bin/go \
  test -count=1 -json ./pkg/ogame ./pkg/utils ./pkg/simulator \
  > /home/kelsier/Projects/TBot/documentation-work/resume-audit/models-offline-tests.jsonl 2>&1
```

**Observed exit0.** Parsed JSON events: **181 passing test/subtest events**, zero failures/skipped tests: 176 in pkg/ogame and 5 in pkg/utils. pkg/simulator compiled and reports **[no test files]**; its package skip event is not a skipped test and is not claimed as unit-test coverage. The source group contains 53 test files.

The parent reviewed the standalone account-free harness, checked a reproducible copy into [tools/go-smoke/models/main.go](../../tools/go-smoke/models/main.go), and independently reran all 50 assertions. The worker's original copy/log remain outside the repository. Portable reproduction from the repository root:

```sh
(cd tools/go-smoke && GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  go run -mod=readonly ./models)
```

**Observed exit0: `ALL 50 CHARACTERIZATIONS PASSED`.** Includes ignored simulator reapers, cost/time fractional ordering, raw duration JSON, Techs ambiguous field omission, system custom JSON loss, pointer/snapshot aliasing, section-flag nil collapse, slot equality, signed sentinel handling, zero cargo and malformed-but-accepted coordinates. Simulator cases were intentionally tiny and deterministic through input omission, not probabilistic claims about win rates.

Evidence validator was run against every filtered assignment row with `read_evidence` set to this lane's ledger, **without changing inventory**:

```python
import importlib.util, json
from pathlib import Path
root = Path('/home/kelsier/Projects/TBot/source')
spec = importlib.util.spec_from_file_location('audit_evidence', root/'tools/audit_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ledger = json.loads((root/'docs/reference/audit-models.json').read_text())
errors = [error for row in ledger['entries']
          for error in module.validate_read_evidence(root, {
              **row, 'read_evidence': 'docs/reference/audit-models.json'})]
assert not errors, errors
assert len(ledger['entries']) == 169
assert sum(row['lines'] for row in ledger['entries']) == 13420
```

**Observed:** expected/completed files169/169, lines13420/13420, missing[], extra[], duplicates0, validator_errors[]. Receipt: `/home/kelsier/Projects/TBot/documentation-work/resume-audit/models-evidence-validation.json`. Parent integration can attach this ledger as read_evidence and upgrade inventory under its own ownership after review. The ledger is not proof of live server compatibility, complete simulator fidelity or uncovered edge-case correctness.

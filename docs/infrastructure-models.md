# TBot.Ogame.Infrastructure — models & enums reference

Every type in the assigned file list (`documentation-work/daemon-integration-files.json`, 98 files:
97 `.cs` + the csproj), with purpose, shape, consumer and units. **All types here are
data-carrying DTO/domain models; none contain transport logic** — transport lives exclusively in
`OgameService.cs`. "Transport-only" marks types whose sole role is the HTTP exchange with ogamed.
JSON binding is Newtonsoft with default name matching; the Go counterparts serialize exported
fields without tags, so C# property names deliberately mirror Go field names.

Source refs: `TBot.Ogame.Infrastructure/Models/<Name>.cs` etc. Full symbol/hash manifest:
`docs/reference/daemon-integration-read.json`.

## 1. Transport & lifecycle

| Type | Shape | Consumer / notes |
|---|---|---|
| `OgamedResponse` | `string Status; int Code; string Message; dynamic Result` | **Transport-only envelope** for every daemon response; `ManageResponse<T>` unwraps `Result`, throws `OgamedException` when `Status!="ok"` |
| `OgamedException` (Exceptions/) | `Exception` + ctors incl. serialization ctor | thrown by `ManageResponse`; caught & domain-interpreted in `SendFleet` ("no ships to send"), `JumpGate`, `BuyOfferOfTheDay`, `AbandonCelestial`, `SendDiscovery`, `Phalanx` |
| `Credentials` | `Universe,Username,Password,Language:string; IsLobbyProners→IsLobbyPioneers:bool; BasicAuthUsername,BasicAuthPassword:string` | input to `Initialize`; becomes daemon argv (password in process cmdline, see daemon.md §7) |
| `Device` | `Name,System,Browser,UserAgent:string; Memory,Concurrency,Color,Width,Height:int; Timezone,Lang:string` | 1:1 with daemon `--device-*` flags; zero/empty fields are omitted from argv |
| `ProxySettings` | `Enabled:bool(false); Address,Type,Username,Password:string; LoginOnly:bool` | only `socks5`/`http` types are forwarded; ctor defaults `Enabled=false` |
| `CaptchaChallenge` | `Id,Icons,Question:string` | maps `GET /bot/captcha/challenge` (`{ID,Question b64,Icons b64}`); empty object returned on any error |
| `LoginResult` | `Success:bool; Error:string` | **Currently unused** by `OgameService` (no member returns it) — kept for callers/tests |

## 2. Server / account snapshot

| Type | Shape | Units / notes |
|---|---|---|
| `Server` | `Language:string; Number:int; Name:string; PlayerCount,PlayersOnline:int; Opened,StartDate:DateTime; EndDate:DateTime?; ServerClosed,Prefered,SignupClosed:bool; Settings:Settings` | from `GET /bot/server` (gameforge lobby record) |
| `ServerData` | ~40 fields mirroring `serverData.xml` — `Name,Number,Language,Timezone,TimezoneOffset,Domain,Version:string; Speed,SpeedFleet,SpeedFleetPeaceful,SpeedFleetWar,SpeedFleetHolding,Galaxies,Systems:int; ACS,RapidFire,DefToTF,DonutGalaxy,DonutSystem,WfEnabled,FleetIgnore*:bool; DebrisFactor,DebrisFactorDef,RepairFactor,TopScore,GlobalDeuteriumSaveFactor:float; NewbieProtectionLimit/High, BonusFields, Wf*, Bashlimit, ProbeCargo, ResearchDurationDivisor, DarkMatterNewAcount(sic), CargoHyperspaceTechMultiplier:int` + computed `SpeedResearch = Speed*ResearchDurationDivisor` | from `GET /bot/server-data`; ints are universe speed **multipliers** (e.g. 6×), factors are ratios 0–1. Note: Go adds `SpeedFleet` deprecation fallback and `FleetIgnoreEmpty/InactiveSystems` — absent from the C# copy |
| `Settings` | `AKS,WreckField,EspionageProbeRaids:bool; FleetSpeed,EconomySpeed,PlanetFields,UniverseSize,PremiumValidationGift,DebrisFieldFactorShips/Defence:int; ServerLabel,ServerCategory:string` | nested in `Server.Settings`; **`EconomySpeed` is `int` here but `any` (int-or-"x8" string) in Go** — string values would fail `int` binding |
| `UserInfo` | `PlayerID:int; PlayerName:string; Points,Rank,Total,HonourPoints:long; Class:CharacterClass` | `GET /bot/user-infos`; points/rank are server ranking units |
| `Staff` | `Commander,Admiral,Engineer,Geologist,Technocrat:bool` (all false ctor) | composed by `GetStaff()` from five bool endpoints, not a single route |
| `Player` | `ID:int; Name:string; Rank:int; IsBandit,IsStarlord:bool` | galaxy-scan player block |
| `Alliance` | `ID,Rank,Member:int; Name:string` | galaxy-scan alliance block |

## 3. Celestials & scans

| Type | Shape | Notes |
|---|---|---|
| `Celestial` | `ID:int; Img,Name:string; Diameter,Activity:int; Coordinate; Fields; Resources; Ships; Defences; Buildings; LFtype:LFTypes; LFBuildings; LFTechs; LFBonuses; Facilities; Productions:List<Production>; Constructions; ResourceSettings; ResourcesProduction; Debris; Researches` + reflection helpers `GetLevel/SetLevel`, `HasProduction/HasConstruction/HasCoords` | base for Planet/Moon and the hand-parsed empire entries; `ID` is the game celestial id (planet ids even, moons odd+1 convention) |
| `Planet : Celestial` | + `Administrator,Inactive,Vacation,StrongPlayer,Newbie,HonorableTarget,Banned:bool; Player; Alliance; Temperature; Moon:Moon` + `HasMines/HasFacilities(ignoreSpaceDock=true)` | galaxy scan & `GET /bot/planets/:id` |
| `Moon : Celestial` | + `HasLunarFacilities(Facilities)` | |
| `Coordinate` | `Galaxy,System,Position:int; Type:Celestials` + `FromString("g:s p planet|moon")`, `IsSame`, `ToString "[P|M|DF|DS:g:s:p]"` | **defaults 1:1:1 Planet**; regex requires 1-digit galaxy — `[12:...]` inputs throw |
| `Fields` | `Built,Total:int; Free⇒Total-Built` | empire path parses from strings |
| `Temperature` | `Min,Max:int; Average⇒(Min+Max)/2` | degrees; drives solar satellite / fusion math |
| `Debris`, `ExpeditionDebris` | `Metal,Crystal,Deuterium:long` + `RecyclersNeeded`/`PathfindersNeeded:int` + `Resources⇒` projection | units: resources; needed = ship counts |
| `GalaxyInfo` | `Galaxy,System:int; Planets:List<Planet>; AvailableMissions:List<Missions>; ExpeditionDebris` | `GET /bot/galaxy-infos/:g/:s` |
| `Abandon` | `CelestialID:int; Result:string` | `GET /bot/celestials/:id/abandon` → `"succeed"` check |

## 3b. Constructions / production / slots

| Type | Shape | Units |
|---|---|---|
| `Constructions` | `BuildingID,BuildingCountdown,ResearchID,ResearchCountdown,LFBuildingID,LFBuildingCountdown,LFResearchID,LFResearchCountdown:int` | ids = `Buildables`/`LF*` enum ints; countdown **seconds**; 0 = idle |
| `Production` | `ID:int; Nbr:int` | shipyard/defence queue rows |
| `Resource` | `Available,StorageCapacity,CurrentProduction:long` | units: resource units & units/hour |
| `ResourcesProduction` | `Metal,Crystal,Deuterium:Resource; Food:Food; Population:Population; Energy:Energy; Darkmatter:Darkmatter` | `GET /bot/planets/:id/resources-details` |
| `Energy` | `Available,CurrentProduction,Consumption:long` | energy units; can be negative in production math |
| `Food` | `Available,StorageCapacity,Overproduction,ConsumedIn,TimeTillFoodRunsOut:long` | lifeform economy; seconds for the timer |
| `Population` | `Available,T2Lifeforms,T3Lifeforms,LivingSpace,Satisfied,Hungry,GrowthRate,BunkerSpace:long` + `IsFull/IsStarving/WillStarve/NeedsMoreT2/T3(bonus)` — caps hardcoded 11,000,000 / 448,000,000 adjusted by bonus % | lifeform population units |
| `Darkmatter` | `Available,Purchased,Found:long` | dark matter units |
| `Slots` | `InUse,Total,ExpInUse,ExpTotal:int; Free,ExpFree` | fleet slots / expedition slots |
| `ResourceSettings` | `MetalMine,CrystalMine,DeuteriumSynthesizer,SolarPlant,FusionReactor,SolarSatellite,Crawler:float` + `Ratio` (avg of first 3 /100), `CrawlerRatio` | **percent 0–100** as stored; ratio helpers divide by 100. NB the daemon POST expects the same 0–100 ints |

## 4. Fleets & attacks

| Type | Shape | Notes |
|---|---|---|
| `Fleet` | `Mission:Missions; ReturnFlight,InDeepSpace:bool; ID:int; Resources; Origin,Destination:Coordinate; Ships:Ships; StartTime,ArrivalTime:DateTime; BackTime:DateTime?; ArriveIn,BackIn?:int(seconds); UnionID:int?; TargetPlanetID:int` | `GET /bot/fleets`, send-fleet result, phalanx rows |
| `AttackerFleet` | `ID:int; MissionType:Missions; Origin,Destination:Coordinate; DestinationName:string; ArrivalTime:DateTime; ArriveIn:int; AttackerName:string; AttackerID,UnionID,Missiles:int; Ships:Ships` + `IsOnlyProbes()` | maps Go `AttackEvent` (no json tags → name mapping); **`ArriveIn` seconds; `ArrivalTime` server-tz instant as serialized by Go `time.Time`** |
| `FleetHypotesis` | `Origin:Celestial; Destination:Coordinate; Ships; Mission:Missions; Speed:decimal; Duration,Fuel:long` | local planning type (TBot sim) — **not** a daemon payload |
| `FleetPrediction` | `Time,Fuel:long` | local planning |
| `FleetSchedule : FleetHypotesis` | + `Payload:Resources; Departure,Arrival,Comeback,SendAt,RecallAt,ReturnAt:DateTime` | local planning |
| `JumpGateResult` | `[JsonProperty success]Success:bool; [JsonProperty rechargeCountdown]RechargeCountdown:long; [JsonIgnore]Error:string` | the only explicitly-tagged model; `Error` is client-side |
| `TransportSettings` / `MultipleOrigins` | transport-policy knobs (`Active,CargoType:Buildables,DeutToLeave,RoundResources,SendToTheMoonIfPossible,Origin,MaxSlots,CheckMoonOrPlanetFirst,DoMultipleTransport…,MultipleOrigin{OnlyFromMoons,MinimumResourcesToSend,PriorityToProximityOverQuantity,Exclude}`) | **TBot-internal** — never serialized to the daemon |

## 5. Forces & economy

| Type | Shape | Notes |
|---|---|---|
| `Ships` | 17 `long` props: `LightFighter…Pathfinder` (202–219 ids via `Buildables`) + `IsEmpty/IsOnlyProbes/GetFleetPoints(hardcoded points table)/HasMovableFleet/GetMovableShips(mutates!)/Add/Remove/GetAmount/SetAmount/HasAtLeast` | counts; `GetMovableShips` returns `this` after zeroing satellite/crawler — mutates the original instance |
| `Defences` | 10 `long` props `RocketLauncher…InterplanetaryMissiles` + `IsEmpty/GetDefencePoints(hardcoded /10)/GetDefenceCost(hardcoded cost table)/Add/Remove(buggy: compares instead of subtract clamp)/GetAmount/SetAmount/HasAtLeast/Sum/Difference/GetDefenceTypesWithAmount` | counts; `Remove` sets value not `val-quantity` — **known quirk** |
| `Defenses : Defences` | empty alias (Go spells it `DefensesInfos`) | |
| `Buildings` (=alias `Supplies`) | 9 int props `MetalMine…DeuteriumTank` + `GetLevel/SetLevel` | levels |
| `Facilities` | 11 int props `RoboticsFactory…JumpGate` | levels |
| `Researches` | 16 int props `EnergyTechnology…GravitonTechnology` | levels |
| `LFBuildings` | `LifeformType:int` + 47 int props across Humans/Rocktal/Mechas/Kaelesh + `GetLevel/SetLevel` | ids 111xx–141xx |
| `LFTechs` | 69 `int?` props + big nullable ctor defaulting 0 + `GetLevel/SetLevel` | ids 112xx–142xx |
| `LFBonuses` | `LfResourceBonuses,CharacterClassesBonuses,MiscBonuses,Production,Expeditions,Dens,Moons,Crawlers` (float groups), `LfShipBonuses:Dictionary<string,LFBonusesShip>`, `CostTimeBonuses:Dictionary<string,LFBonusesBase>` + `*Int` dict projections, plus 7 float scalars (`PhalanxRange,RecallRefund,FleetSlots,Explorations,SpaceDock,PlanetSize,InactivesLoot`) and legacy `Ships/Defenses/Buildings/...` dicts; `GetShip{Cargo,Speed,Consumption}Bonus` | **percentages as fractions** (Go parses `1.056% → 0.01056`); dictionaries keyed by id-as-string because Go map keys marshal as strings |
| `LFBonusesBase` | `Cost,Duration:float` | fractions |
| `LFBonusesShip` | `ID:int; StructuralIntegrity,ShieldPower,WeaponPower,Speed,CargoCapacity,FuelConsumption:float` | fractions |
| `Resources` | `Metal,Crystal,Deuterium,Population,Food,Energy,Darkmatter:long` + `ConvertedDeuterium(metalRatio 2.5, crystal 1.5)`, `TotalResources`, `StructuralIntegrity=Metal+Crystal`, `IsEnoughFor/IsEmpty/Sum/Difference/Round(1000)/IsBuildable/FromString "M:…"`, `TransportableResources/LFBuildingCostResources` formatters | trade conversion `ToPositiveInfinity` rounding |
| `Auction` | `HasFinished:bool; Endtime,NumBids,CurrentBid,AlreadyBid,MinimumBid,DeficitBid,HighestBidderUserID:int; HighestBidder,CurrentItem,CurrentItemLong,Token:string; Inventory:int; ResourceMultiplier:AuctionResourceMultiplier; Resources:Dictionary<string,AuctionResourcesValue>` + `TotalResourcesOffered`, `ToString/GetTimeString` | seconds for `Endtime` |
| `AuctionResourceMultiplier` | `Metal=1.0f,Crystal=1.5f,Deuterium=3.0f,Honor=100` | **doc defaults, not server data** — overwritten when bound |
| `AuctionResourcesValue` | `imageFileName:string; input,output:AuctionInputOutput; isMoon:bool; [name]Name:string; otherPlanetId:int?` | |
| `AuctionInputOutput` | `metal,crystal,deuterium:long` (JsonProperties, default 10) + `TotalResources` | |
| `EspionageReport` | resources longs; `ID,CounterEspionage,LastActivity:int; Username,APIKey:string; CharacterClass,AllianceClass:enum; Has*Information,HonorableTarget,IsBandit/Starlord/Inactive/LongInactive:bool`; nullable `int?` buildings/research, `long?` fleet/defence columns; `Coordinate; Type:EspionageReportType; Date:DateTime` + `IsDefenceless(isUsingProbes)`, `PlunderRatio(class)` (0.5/0.75/1.0 table), `Loot(class)`, `HasCoords` | nullability == "info not scanned"; `CounterEmergency`→`CounterEspionage` percent |
| `EspionageReportSummary` | `ID:int; Type:EspionageReportType; From:string; Target:Coordinate; LootPercentage:float` | list view |
| `BuildTask` | `Celestial; Buildable:Buildables; Level:int; Price:Resources` | internal queue item |
| `RankSlotsPriority` | `Rank:int(int.MinValue sentinel); Active:bool; MaxSlots,SlotsUsed:int; Feature:Feature; HasPriorityOn` | internal feature gating |
| `AutoMinerSettings` | ctor defaults `OptimizeForStart=true, PrioritizeRobotsAndNanites=false, MaxDaysOfInvestmentReturn=36500, DepositHours=6, BuildDepositIfFull=false, DeutToLeaveOnMoons=1000000, BuildSolarSatellites=true` | **internal config defaults — not daemon values** |
| `FarmTarget` | `Celestial; State:FarmState; Report:EspionageResearch→EspionageReport` + `HasCoords` | internal farming FSM |

## 6. Enums (`Enums/`)

| Enum | Values (meaning) |
|---|---|
| `Buildables` | the master id table: buildings 1–44, storages/dens 22–27, facilities 14/15/21/31/33/34/36/41–44, defences 401–408, missiles 502/503, ships 202–219, researches 106–199, `Null=0`; drives argv `build/*` routes and `Ships`/`Defences` reflection by name |
| `LFBuildables` / `LFTechno` / `HumansBuildables` / `RocktalBuildables` / `MechasBuildables` / `KaeleshBuildables` | lifeform ids 11101–14112 / 11201–14218 + per-lifeform subsets (`None=0`) |
| `LFTypes` | `None0,Humans1,Rocktal2,Mechas3,Kaelesh4` |
| `Missions` | `None0 Attack1 FederalAttack2 Transport3 Deploy4 FederalDefense5 Spy6 Colonize7 Harvest8 Destroy9 MissileAttack10 Expedition15 Trade16 Discovery18` — route `mission=` param |
| `Celestials` | `Planet1 Debris2 Moon3 DeepSpace4` (**1-based**, Go `CelestialType` is 0/1/2/3 — the `type=` form field uses the Go numbering via `(int)destination.Type`… **mismatch risk**: C# Moon=3 vs Go MoonType=3 ✓, Planet 1 vs 1 ✓, Debris 2 ✓, DeepSpace 4 vs 3 — only `DeepSpace` diverges) |
| `CharacterClass` | `NoClass0 Collector1 General2 Discoverer3` |
| `AllianceClass` | `NoClass0 Warrior1 Trader2 Researcher3` |
| `EspionageReportType` | `Action0 Report1` |
| `FarmState` | `Idle,ProbesPending,ProbesSent,ProbesRequired,FailedProbesRequired,AttackPending,AttackSent,NotSuitable` |
| `Feature` / `Features` | feature ids 1–16 + 101–103 celestial-scoped; `Features.AllFeatures` static list (16 entries) used for gating |
| `Speeds` | `static class` of decimal constants `FivePercent=0.5M … HundredPercent=10M` + `GetGeneralSpeedsList()` (integer steps only; `.5` half-steps commented out) — matches daemon `speed` 0–10 validation |
| `SendFleetCode` | `GenericError0 AfterSleepTime-1 NotEnoughSlots-2 QuickerToWaitForProduction-3 NotEnoughRessources-4` (internal result codes) |
| `RepatriateCode` | `Success1 Stop0 Failure-1 Delay-2` |
| `OfferOfTheDayStatus` | `OfferOfTheDayBougth(sic),OfferOfTheDayAlreadyBought,OfferOfTheDayUnknown` |
| `SettingsVersion` | `AllInOne0 MultipleInstances1 Invalid-1` |
| `UpdateTypes` | `Fast,Techs,Full,Resources,Buildings,LFBuildings,LFTechs,LFBonuses,Ships,Facilities,Defences,Productions,Constructions,ResourceSettings,ResourcesProduction,Debris` — cache-invalidation selector, TBot-internal |

## 7. Known inconsistencies (found, not fixed — no source changes)

1. `OgameService.SetUserAgent` → daemon stub `400 deprecated` (always throws). `LoginResult` unused.
2. `OgameService.GetTbotIP` builds `https://jsonip.com` as a *relative* Uri against
   `http://127.0.0.1:port/` → wrong URL `http://127.0.0.1:port/jsonip.com`.
3. Daemon `POST .../send-ipm` route/handler param mismatch → always 400 (no C# caller today).
4. `Defences.Remove` doesn't subtract (sets clamped current value).
5. `Ships.GetMovableShips` mutates the instance it is called on.
6. `Celestials.DeepSpace=4` vs Go `DeepSpaceType=3` — only affects deep-space coordinates.
7. `Settings.EconomySpeed` typed `int` while upstream may emit `"x8"` strings.
8. `ServerData` C# copy lacks `FleetIgnoreEmptySystems/FleetIgnoreInactiveSystems/SpeedFleet`
   handling the Go side applies — fleet-time skip logic not observable from C#.
9. `_cookiesPath` field in `OgameService` is dead.

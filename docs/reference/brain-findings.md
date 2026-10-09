# Brain documentation — findings, inconsistencies, unknowns

Task evidence companion. Commit audited: `35b4ce08b57bf2900d5b3d3b449a3f26f168270b`
(branch `docs/comprehensive-handbook`), submodule `fbd0fda6ba9019c128926614f9865ba38a67b627`.
Per-file sha256/lines/symbols: `brain-read.json` (14/14 files, 8 831 lines, all read in full — including all 5 068 lines of
`CalculationService.cs` and every worker).

Deliverables produced (only these two files written in the repo):
- `docs/features/brain.md`
- `docs/calculations.md`

## A. Coverage checklist (task requirements → where documented)

| Requirement | Location |
|---|---|
| mining (mines/facilities/moons/crawlers/abandon) | features/brain.md §2, calculations.md §5-6,8 |
| energy (plants/fusion/satellites/energy tech) | features/brain.md §2.1; calculations.md §2, §6 |
| storage / deposits | features/brain.md §2.1; calculations.md §2.1 |
| robots/nanites/terraformer/lunar choices | features/brain.md §2.1; calculations.md §8 |
| investments / ROI / DOIR | features/brain.md §1.3, §3; calculations.md §5 |
| lifeform buildings, research, bonuses, limits | features/brain.md §4-5; calculations.md §3.2, §7 |
| normal research progression/priorities | features/brain.md §3.1; calculations.md §6 |
| cargo | features/brain.md §6; calculations.md §1, §3.3 |
| defence | features/brain.md §7; calculations.md §3.1, §3.3 |
| repatriation | features/brain.md §8 |
| jump gate | features/brain.md §9 |
| offer-of-the-day | features/brain.md §10 |
| transports & shared scheduling effects | features/brain.md §1.1-1.2, §11 |
| gating/order/fallbacks/units, config keys incl. misspellings | features/brain.md §1, §2.2, §12; calculations.md header |

## B. Exact code inconsistencies / bugs needing parent attention

All line numbers at `35b4ce0`. Ordered by likely user-visible impact.

1. **Deuterium production computed from the crystal-mine level.**
   `CalculationService.cs:912` and `:920` pass `buildings.CrystalMine` / `planet.Buildings.CrystalMine` into
   `CalcDeuteriumProduction(int level, …)` — almost certainly meant `DeuteriumSynthesizer`. Affects `CalcPlanetHourlyProduction`,
   `ShouldBuild*Storage`, and the AutoMine facility-cost/energy reasoning, while `CalcROI`/`CalcDaysOfInvestmentReturn`/`CalcNext*DOIR` use the true
   synth level ⇒ the two families disagree whenever mine levels differ. Needs a decision (fix vs document).
2. **Dead `bonusProd` / wrong term in deut result.** `:900-903` compute `bonusProd = round(prod × deuteriumLFBonus/100)` but `:904` adds the raw
   percentage `deuteriumLFBonus` instead ⇒ LF deut bonus mis-sized (units vs percent) in the planet-level production.
3. **AutoResearch delay interval reads the wrong settings section.** `AutoResearchWorker.cs:442` falls back to
   `InstanceSettings.AutoResearch.CheckIntervalMin/Max` (top-level `AutoResearch`, used by the legacy AutoResearch feature) instead of
   `Brain.AutoResearch.CheckIntervalMin/Max` used everywhere else (:455,:488). Wrong section ⇒ surprising cadence or NRE-safe 0→`SomeSeconds`.
4. **AutoMineWorker builds settings it never uses.** `AutoMineWorker.cs:82-96` constructs `maxLunarFacilities` and `autoMinerSettings`
   (`BuildSolarSatellites` not set there either) but the per-celestial workers rebuild their own from settings
   (`AutoMineCelestialWorker.cs:60-101`); dispatcher values are dead except… none. Maintenance trap: editing dispatcher maxes does nothing.
5. **`GetNextResearchToBuild` start-optimisation caps Combustion 2-5 by `maxComputerTechnology`.** `CalculationService.cs:4469` — should be
   `maxCombustionDrive`; with default 20/19 mostly harmless, with custom caps wrong.
6. **Bitwise `&` between bool conditions** in the plasma priority gate, `AutoResearchWorker.cs:121-123` — same truth table here, but one operand is
   a bool expression chain; flagged as style/robustness.
7. **Bomber consumption upgrade is a no-op:** `baseConsumption *= 3 / 2` — integer division ⇒ ×1 (`CalculationService.cs:404`).
8. **`CalcFleetSpeed` returns 0 for an empty fleet** (`minSpeed` init 0, `:345-359`) while `CalcSlowestSpeed` returns `int.MaxValue` (`:322-339`) —
   asymmetric empty-case semantics; flight-time division would use 0 speed if ever fed an empty fleet (callers currently never do).
9. **Duplicate identical `if` in `CalcPrice` LF-reduction** (`:1232` / `:1235`) — second branch unreachable.
10. **`CalcDepositCapacity` truncates the factor before ×5000** (`:3142`) — storages ~smaller than the literal formula; intentional? document or fix.
11. **`CalcDeuteriumProduction` level-0 ⇒ 0 but metal/crystal level-0 ⇒ baseProd** (`:879` vs `:784/:835`) — asymmetry to keep in mind in diffs.
12. **Jump-gate pairing drops the last odd moon** (`AutoFleetJumpGateWorker.cs:176-178`: `i=1; i+1<count; i+=2` pairs 1→2,3→4…; if a 3rd qualifier
    exists alone it waits for the next pass) — presumably intended load-spreading, worth confirming.
13. **LifeformsAutoMineWorker duplicated assignment** `_calculationService = calculationService;` twice (`:33-34`) — cosmetic.
14. **`CalcSlotsPriority` uses `Single()`** (`:4881`) — a duplicated `Feature` entry in any caller's rank list throws inside the worker's try/catch
    ⇒ pass abort; callers currently build unique lists.
15. **`CalcMaxTransportableResources` final else returns `resources` un-reserving deut** (`:583`) — unreachable in current call shapes; latent.
16. **LF-research defaults asymmetry**: `LifeformsAutoResearchCelestialWorker.cs:108-126` defaults `MaxResearchLevel→1`, `MaxTechsNN→MaxResearchLevel`
    via `IsSettingSet`, but the dispatcher (`LifeformsAutoResearchWorker.cs:62-79`) reads raw — a missing key yields 0 there and silently disables a
    tech group in the *dispatcher's* pre-check while the celestial worker would have used the fallback. Config half-applied = confusing logs.
17. **`GetNextLFTechToBuild` never researches a tech from level 0** (TODO in code, `CalculationService.cs:4069-4076`) — documented behaviour, but
    users must level a tech once manually per planet (per-planet LFTechs).
18. **`CalcShipCapacity` int overload vs float bonus overload** — the int one (`:35-96`) ignores LF cargo bonuses entirely;
    `CalcFleetFuelCapacity` uses it (`:185-197`) so fuel-capacity differs from real capacity when LF bonuses exist.

## C. Non-ordered observations (behaviour, not bugs)

- `Brain.AutoFleepJumpGate` / `Feature.BrainAutoFleepJumpGate` / `LogSender.AutoFleepJumpGate` — *Fleep* misspelling is consistent across code;
  settings section must be spelled `AutoFleepJumpGate`.
- `MaxDeuteriumSynthetizer` (settings + many params) vs enum `DeuteriumSynthesizer` — both spellings intentional in different places.
- `OfferOfTheDayBougth` status enum misspelling surfaces in logs only.
- `CalcOptimalCrawlers` hard-codes `crawlerRatio = 1.5F` (crawler over-performance factor) — not configurable.
- `AutoMineWorker` sorts by DOIR then optional `RandomOrder` shuffle discards that order by design?
- All workers' gating is exception-swallowing (`catch → false`): malformed settings silently disable features (documented §1).
- `CalcProductionTime(LFBuildables…)` nanites default = **1** in the private `CalcLFTime` signature (`:3002`) — a planet with 0 nanites gets
  slightly faster LF times than truth if the default path is hit (public path always passes real values).

## D. Unknowns / not verified here (outside the 14 assigned files)

- `TBot.Ogame.Infrastructure` model internals (`Resources` flags `IsBuildable/IsEnoughFor/Round`, `Population.*` predicates
  `IsStarving/WillStarve/NeedsMoreT2/T3`, `Ships.GetFleetPoints`, `LFBonuses.Get*Bonus` semantics — percent vs fraction) were only traced where
  called; `ConvertedDeuterium` was verified (`Resources.cs:27-35`, metal/2.5 + crystal/1.5 + deut, ⌆). Bonus semantics inferred from usage sites
  (`×(1−bonus)` consumption, `×bonus` speed term) — flagged in calculations.md §1.2/§1.3.
- `FleetScheduler.CollectImpl` / `HandleMinerTransport` / `SendFleet` codes (`RepatriateCode`, `SendFleetCode`) — consumed, not audited (fleet
  workstream). Same for `ITBotOgamedBridge.UpdatePlanet(UpdateTypes.*)` refresh semantics.
- Settings *serialization* (default config file) not audited here — the docs list keys as read in code; `config-lifecycle-files.json` owners should
  cross-check defaults.
- Runtime behaviour (no bot executed, no game calls) — per task constraints; everything above is static reading of the pinned commit.

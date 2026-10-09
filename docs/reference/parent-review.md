# Parent verification and closeout review

Scope: documentation/tooling only, source baseline 35b4ce08b57bf2900d5b3d3b449a3f26f168270b and pinned Go gitlink fbd0fda6ba9019c128926614f9865ba38a67b627. The user requested closeout without expanding the audit. Unfinished/unverified coverage must remain explicit rather than being marked read or complete.

## Directly checked and corrected

- Brain interval configuration: RandomizeHelper.cs:27–31 interprets integer bounds in minutes and returns milliseconds. AutoMineCelestialWorker.cs:598/649, AutoCargoWorker.cs:140 and AutoRepatriateWorker.cs:38 call this overload. Removed millisecond configuration claims and overflow-prone illustrative interval values.
- Missing settings: SettingsService.cs:301–359 returns a nestable NullExceptionPreventer; supported casts yield false/zero/null/empty arrays. Missing object nesting alone does not throw. Replaced contrary Brain guide text and incorrect reliance on AutoMinerSettings initializers overwritten by explicit property casts.
- Fleet speeds: CalculationService.cs:498–546 comments out the General-specific grid. Corrected the fleet guide's claim that the active implementation supplies additional General speeds.
- CalcFleetSpeed: CalculationService.cs:345–359 starts its minimum at zero and only lowers it. Corrected the claim that positive-speed fleets otherwise return their slowest ship speed.
- Flight time: CalculationService.cs:445–453 divides by the universe speed before rounding. Corrected parentheses and distinguished speed enum values from human percentages.
- Farm fuel constraint: CalculationService.cs:548–564 uses loot.ConvertedDeuterium, not raw loot.Deuterium.
- Storage: CalculationService.cs:3141–3143 uses integer division in the exponent as well as a long cast before multiplication. Documented both rather than a continuous exponential approximation.
- Structural integrity: TBot.Ogame.Infrastructure/Models/Resources.cs:43–46 returns metal plus crystal, not metal alone.
- Missile defence: DefenderWorker.cs:224–227 reads the exact key DefendFromMissiles. Corrected a prose spelling mismatch.
- Defender static state: state is shared by account instances within a process, not between separate processes. Removed contrary summary text.
- Removed unmeasured claims that timer-driven UserData races are benign, and clarified sleep gating and incomplete illustrative configuration.
- Fixed Brain's relative calculation-guide link.

## Re-executed verification

- Source UI smoke passed: root redirect and Settings/Logging/Ogame return HTTP 200; isolated settings write/read roundtrip passes; SignalR advertises WebSockets/SSE/LongPolling; no daemon child or account actions; live service/config identities unchanged.
- Pure-helper harness passed all 14 assertions covering overlays, absent-value casts, explicit fallback, first-character key normalization, duration parsing and system boundaries. Existing ImageSharp advisories remain and were not changed.
- Documentation checker unit tests: 4 pass. Link validation cannot be called complete until the final lifecycle/configuration/daemon pages and source-audit record are present.

This review is an independent targeted verification, not a claim that every statement or live account workflow has been tested.

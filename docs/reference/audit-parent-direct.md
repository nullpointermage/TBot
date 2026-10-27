# Direct parent audit: C# infrastructure and Go constants

## Scope

The parent directly read all 98 `TBot.Ogame.Infrastructure` source/project files and the complete pinned Go `pkg/ogame/constants.go`. The [per-file ledger](audit-parent-direct.json) records hashes, line counts, full read ranges and semantic notes. This does **not** complete the remaining Go audit. Canceled workers' partial claims are not automatically promoted to completed review.

No implementation, live configuration, service, account or Spark changes were made. New executable code is an **offline characterization harness**, not a bot behavior fix.

## Confirmed adapter defects and documentation corrections

| Finding | Evidence | Verification |
|---|---|---|
| Retry delays are 2/4/8 seconds, not 1/2/4 | `OgameService.cs:274–276`, `Math.Pow(2,retryCount)` for three Polly retries | Source and computed sequence; no real delayed retry/request executed |
| `RerunOgamed` discards its newly returned Process | `OgameService.cs:200–224` | Source; no daemon started to reproduce process behavior |
| Startup failure calls `Environment.Exit(0)` | `OgameService.cs:179–182` | Source; deliberately not executed |
| Absolute public-IP URL cannot be constructed as a relative URI | `OgameService.cs:279–289,340–343` | In-memory harness: UriFormatException before transport, not a request to a malformed localhost URL |
| Already-accepted offer envelope becomes Unknown | `OgameService.cs:235–272,814–827` | In-memory HTTP400 error envelope throws OgamedException, not the HttpRequestException caught as AlreadyBought |
| Malformed HTTP200 can escape as NullReferenceException | `OgameService.cs:235–272` | Reproduced with an in-memory non-JSON response |
| An ok envelope can mask HTTP400 | `OgameService.cs:252–271` | Reproduced; the status is not universally enforced before unwrapping |
| A later officer lookup failure erases earlier successful flags | `OgameService.cs:800–812` | Reproduced: commander=true followed by failed admiral lookup returns a fresh all-false Staff |
| Action POSTs share transient-error retries with GETs | `OgameService.cs:274–304` | Source; no action retries executed, no idempotency or reconciliation added |

## Confirmed model behavior and documentation corrections

- `Ships.Remove` (`Ships.cs:147–158`) and `Defences.Remove` (`Defences.cs:87–98`) leave an adequate current quantity unchanged rather than subtracting. The ship case is reproduced offline.
- `Ships.HasMovableFleet` (`Ships.cs:127–129`) merely negates IsEmpty: stationary-only ships count as movable. `GetMovableShips` (`:131–136`) returns the same reference and zeroes satellites/crawlers in the caller's original inventory. Both reproduced.
- `Ships.HasAtLeast` (`:178–185`) and `Defences.HasAtLeast` (`Defences.cs:118–125`) multiply **owned** counts by `times`, not requested counts. Defense behavior reproduced; do not rely on the method name as the batch-availability specification.
- `EspionageReport.IsDefenceless` (`EspionageReport.cs:115–163`) requires both information flags and **null** combat fields. An explicitly present zero is not equivalent to null. Both cases reproduced. Other code must preserve the daemon's nullable-field contract before interpreting the result.
- `Coordinate.FromString` (`Coordinate.cs:26–45`) is an unanchored one-digit-galaxy regex. It can accept the last digit of a multi-digit galaxy embedded in a larger string, rather than reject it. Reproduced with a synthetic string.
- `Resources.Round` (`Resources.cs:104–110`) divides by its argument but always multiplies by1000. Reproduced with a non-default divisor. Sum/Difference/Round also project only metal/crystal/deuterium, dropping other resource fields.
- C# `LFBuildings` has LifeformType plus **48 building properties**; `LFTechs` has **72 nullable level properties**, not the previous 47/69 claims. Counted from property declarations after complete reads.
- Go `constants.go:143–145` declares PlanetType1, DebrisType2, MoonType3 and **no DeepSpaceType**. Removed the invented Go DeepSpaceType=3 comparison. Deep-space position16 must not be confused with a named celestial-type constant.
- Debris recycler/pathfinder requirement fields are long. ServerData.Number is int and SpeedFleet exists. Removed fabricated identifier aliases and corrected the coordinate input format.
- `LFBonuses` contains both legacy and new dictionaries. Ship helper methods only consult the legacy string-key projection; the projection allocates a dictionary on each access and can reject duplicate parsed integer keys. This is not proof every populated new-schema bonus influences calculations.
- `Celestial.SetLFType` returns a local value without assigning the LFtype property; `LFTechs.GetLevel` handles null whereas the Celestial LF overload casts directly. These source observations were not dynamically exercised.

## Reproducible safe harness

```sh
dotnet restore tools/adapter-smoke/AdapterSmoke.csproj
dotnet run --project tools/adapter-smoke/AdapterSmoke.csproj --configuration Release --no-restore
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

The C# harness injects a synthetic `HttpMessageHandler`, does not call Initialize, and never launches a daemon or network request. **13 characterization assertions passed** against the unmodified source. They encode existing quirks/defects, not desired corrected behavior. When a separate behavior fix is made, deliberately update the corresponding characterization and documentation.

The observed run restored solely from the already-present local NuGet cache with `--source "$HOME/.nuget/packages" -p:NuGetAudit=false --ignore-failed-sources`. Disabling network-based audit was confined to that offline restore; it does not resolve or dismiss existing dependency advisories. The normal restore command above can contact package/audit sources and may require network access.

The Python checker suite currently has **14 tests**, including explicit evidence validation for stale hashes, incomplete/gapped ranges, duplicate/malformed attestations, missing semantic notes and paths escaping the repository. Read coverage is an auditable attestation, not machine proof of semantic understanding; findings still need review.

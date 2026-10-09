# Config/lifecycle/Telegram — findings, gaps and uncertainties

Honest caveats from the docs pass on commit `35b4ce0` (branch `docs/comprehensive-handback`→
`docs/comprehensive-handbook`), submodule `fbd0fda`. Every item was verified by reading the cited
code; nothing here is inferred from names alone.

## Verified inconsistencies / dead keys (template vs code)

1. **`AutoFarm.Exclude[]` uses key `Planet`, code reads `Position`**
   `AutoFarmWorker.cs:84-95` (system exclusion) and `:179-190` (planet exclusion) test
   `exclude.Keys == "Position"`. The shipped template entry
   `{"Galaxy":1,"System":1,"Planet":1}` has no `Position` ⇒ it is treated as a *system-level*
   exclusion of system 1:1, not of position 1. Rename the key to `Position` for per-planet excludes.
2. **`General.Proxy.LoginOnly` never populated.** `TBotMain.InitializeOgame` builds `ProxySettings`
   with Enabled/Address/Type/Username/Password only; `OgameService.cs:120` would emit
   `--proxy-login-only=true` — unreachable from settings. Effective value always `false`.
3. **`Expeditions.MinPrimaryToSend` is write-only.** `/minexpecargo` and `EditSettings` write it,
   but no worker reads it (grep over all consumers). Changing it currently has no effect.
4. **`Expeditions.SecondaryShip`, `MinSecondaryToSend`, `SecondaryToPrimaryRatio`: zero consumers**
   (template value `Null` for SecondaryShip). Dead template keys.
5. **`General.CustomTitle`, `WebUI.MaxLogsToShow`: zero consumers** in code and views.
6. **`SleepMode.LogoutOnSleep`: dead.** All three usage sites are inside commented
   `/* remove? */` blocks (`TBotMain.cs:1255-1265, 1478-1488, 1523-1533`). Key absent from the
   shipped `instance_settings.json` too; no catalog row for that reason.
7. **`Brain.AutoFleepJumpGate.Target` shape mismatch.** Template ships a 1-element array;
   `AutoFleetJumpGateWorker.cs:39-41` reads `.Target.Galaxy` scalar-style. With the array the
   dynamic cast relies on `ConfigObject`/array dynamic behaviour — keep exactly ONE element, or
   convert to an object, to be safe. Same scalar-read pattern in
   `TBotMain.TelegramBidAuctionMinimum` for `Brain.AutoRepatriate.Target` (there the array is
   read properly elsewhere in FleetScheduler — mixed access styles on the same key).
8. **`BrainAutoFleepJumpGate` spelling**: the enum member and the settings key really are
   `AutoFleep...` (typo present in both code and template; consistent, so it works).
9. **`AutoFarm.PreferedResource`** — single-'r' spelling is the real key.
10. **`RandomizeHelper.CalcRandomInterval(IntervalType.AboutAnHour)`** returns up to
    42 000 000 ms (11.7 h) — `3000000, 42000000` looks like a missing zero (`4 200 000`).
    Documented as-is in lifecycle §10.

## Behavioural caveats (not bugs, but surprising)

- **No Telegram auth/chat filter**: any chat that can see the bot can command it; `ChatId` is
  outbound-only. See docs/telegram.md.
- **Substring command matching** (`Contains`) — messages that merely contain a command token are
  interpreted as commands.
- **Proxy fallback blocks on stdin**: unsupported proxy type logs `Press enter to continue`
  (`TBotMain.cs:187-188`) — hangs headless runs.
- **Single-celestial accounts get their JSON rewritten** at init (`TBotMain.Init`,
  `celestials.Count == 1` → `EditSettings`), pointing Brain/Expeditions/... origins at it.
- **Editing the instance file clears loaded profiles** (plain `GetSettings` on reload);
  `/profile load` state is in-memory only.
- **Instance start spacing**: random 30–60 s `Thread.Sleep` between instance inits
  (`InstanceManager.cs:152-156`).
- **Settings writes use `Encoding.Default`** (`SettingsService.WriteSettings`) while reads use
  `File.ReadAllTextAsync` (UTF-8 default) — non-ASCII in settings may round-trip differently.
- **`JsonNetAdapter` upper-cases only the FIRST character** of each key (parent-confirmed; also
  visible in `FirstCharToUpper` usage). Dynamic member access beyond char 1 is case-sensitive.
- **Merged-settings overlay order**: `overlayJson.First()` ⇒ at least one overlay required;
  overlays merged into each other in order, then into base; arrays REPLACED, nulls IGNORED
  (`GetMergedSettingsFromContents`). Explicit `GetSetting(..., def)` fallbacks are distinct from
  the implicit NullExceptionPreventer defaults — both are recorded per-row in the catalog.
- **`/ghostto` vs help text**: the handler case is `/ghostto`; `/help` documents `/ghostmoons`
  with the `/ghostto` example and the command list contains a duplicated `/startautodiscovery`
  entry — cosmetic, quoted verbatim in docs/telegram.md.
- **`/editsettings` requires target sections to exist** in the instance JSON (direct `JObject`
  indexers); malformed section → exception, file untouched.
- **Defender `WhiteList` semantics** (`0` first element) follow DefenderWorker's player-id
  comparison; not re-derived from game rules here.

## Coverage statement

- `settings-catalog.json`: 460 entries (15 global + 460-ish instance paths incl. containers and
  `[]` schemas); **0 entries without description, 0 without consumer or write-site evidence**.
- `instance.md` contains a row for **every** catalog path (verified programmatically by
  `emit_docs.py`; 0 missing). Same for `global.md` (15/15).
- Description provenance: exact per-path notes where behaviour is distinctive; wildcard inherit
  (`Max*`, `*Ships.*`) and container-inherit otherwise — each row's `notes` marks
  `[meta via ...]` / `inherited from ...` so inherited rows are identifiable.
- **Not covered / out of scope**: ogame submodule internals; WebUI UI behaviour beyond settings
  consumption; runtime verification against a live account (none performed; docs are static
  analysis of `35b4ce0` only).

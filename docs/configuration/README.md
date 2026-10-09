# Configuration & lifecycle documentation

Scope: complete settings, lifecycle and Telegram reference generated from actual code at
commit `35b4ce0` (branch `docs/comprehensive-handbook`), ogame submodule `fbd0fda`.

| Document | Contents |
|---|---|
| [global.md](global.md) | `TBot/settings.json` — global/Process-wide settings, all 15 paths, per-path consumers |
| [instance.md](instance.md) | `TBot/instance_settings.json` + `TBot/profiles/*.json` — all 445 paths (leaves, containers, array schemas), per-path consumers and absent-key fallbacks |
| [features.md](features.md) | Feature ↔ worker ↔ settings-section map, slot budget, due-time/interval semantics |
| [../lifecycle.md](../lifecycle.md) | Process startup, instance init, settings reload/watchers, profiles, sleep, timers, shutdown, CLI args, exceptions |
| [../telegram.md](../telegram.md) | Telegram bot: auth, chat filtering, every command with arguments/behaviour/side effects |

Machine-readable catalog: [settings-catalog.json](../reference/settings-catalog.json)
— one entry per path with `type`, `example` (from template), `template_sources`,
`description`, `fallback` (runtime value when the key is absent), `notes`, and `consumers`
(`{file, symbol}`; `symbol` is the dotted access chain, a write site, or `X (inherited)` when the
consumer dereferences an ancestor container).

Key semantics (apply to every settings row):

- Parsing: `SettingsService.GetSettings` → JSON → `ExpandoObject` → `JsonNetAdapter.Transform`
  (upper-cases FIRST character of each key only) → `ConfigObject` (dynamic).
- Missing member: `NullExceptionPreventer`; casts give `null`/`false`/`0`/empty-array. Note that a
  missing *container* quietly yields defaults for all of its children — mis-spelling a section is
  silent. `IsSettingSet` checks are used only at a handful of call sites; everything else casts
  blindly, which is why the per-row **If absent** column matters.
- Overlay merge (`GetMergedSettingsFromContents`): `JsonMergeSettings` with
  `MergeArrayHandling.Replace` and `MergeNullValueHandling.Ignore`; `overlayJson.First()` — at
  least one overlay required; overlays merge into each other first, then into the base.
- `CheckIntervalMin/Max` are minutes unless a row says otherwise
  (`RandomizeHelper.CalcRandomInterval(int,int)` = `rand.Next(min*60_000, max*60_000)`).

These tables are a baseline snapshot. Keep the tables and published catalog synchronized when making a documentation correction, then run `python3 tools/check_docs.py --allow-incomplete-audit` from the repository root. The original local generation scripts are not a public regeneration interface.

Known gaps and caveats: [configuration findings](../reference/config-lifecycle-findings.md) and [audit status](../source-audit.md). Catalog consumer entries can describe inherited-container or write-site evidence; they are not all method names or proof that a template key influences runtime behavior.

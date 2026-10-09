# Telegram interface reference

Source: `TBot/Services/TelegramMessenger.cs` (1426 lines) + command implementations in
`TBot/Services/TBotMain.cs` / `FleetScheduler`. Commit `35b4ce0`.

## Bot lifecycle, auth and chat filtering

- One `TelegramMessenger` singleton per process, built by `InstanceManager` iff
  global `TelegramMessenger.Active` (token `TelegramMessenger.API`, chat `TelegramMessenger.ChatId`).
- `TelegramBot()` starts `Client.ReceiveAsync(HandleUpdateAsync, HandleErrorAsync, receiverOptions, ct)`
  with `AllowedUpdates = Empty` (all types), `DropPendingUpdates = false`.
- **Auth / filtering reality**: there is *no* user or chat allow-list. Any `Update` of type
  `Message` is processed; the handler never compares `update.Message.Chat.Id` with
  `ChatId`. Anyone who can talk to the bot in any shared chat can drive it (including fleet
  commands). `TelegramMessenger.ChatId` is only the destination of outgoing messages.
- `/command@botname` suffix is stripped (only when the message is a single token).
- Matching: `core_cmds`/`commands` lists use `message.Text.ToLower().Contains(cmd)` — substring
  semantics, so e.g. text containing "…/ping" matches; the *first* token (`args[0]`) selects the
  switch case. Lower-casing means `/GetInfo` works, but `Buildables`/mission args are matched with
  `Enum.TryParse` ignoreCase in most, exact-case in `/editsettings` feature arg.
- Concurrency: each command runs `currInstance.WaitFeature()` (acquires every feature semaphore,
  deduped) then the action, `finally releaseFeature()` — commands serialize against worker runs.
  Errors mapped to Telegram replies: `ApiRequestException`, `FormatException`,
  `NullReferenceException`, `OperationCanceledException`, generic.
- `SendTyping`: `chataction typing` loop every 3 s while a command is processed.
- Logging: `TelegramMessenger.Logging` mirrors log entries into the chat (Serilog sink);
  `/loglevel`, `/setloglevel` manage level at runtime (`LogEventLevel`).
- Disable path: config off on reload → `TelegramBotDisable()` (see lifecycle §8).

## Core commands (process-wide, no instance needed)

| Command | Arguments | Behaviour |
|---|---|---|
| `/setmain` | `<index>` | select managed instance by index; index bounds-checked |
| `/getmain` | – | print managed index + `Player@Universe` |
| `/getmainstats` | – | per-feature `Running:` bool for the selected instance (SleepMode always true) |
| `/listinstances` | – | all instances with indexes |
| `/loglevel` | – | telegram log sink state+level |
| `/setloglevel` | `Debug\|Information\|Warning\|Error` | re-add sink + set level (Enum.TryParse ignoreCase) |
| `/ping` | – | `Pong` |
| `/stopautoping` / `/startautoping` | – | stop/start auto-ping timer (period persists) |
| `/help` | – | the built-in help text (quoted verbatim in code; minor typos included) |

## Instance commands (require `/setmain` first; else "Select an instance with /setmain !")

Fleets & combat:

| Command | Arguments | Behaviour / side effects |
|---|---|---|
| `/getfleets` | – | outgoing (non-return) fleets: id, origin, dest, mission, ETA |
| `/cancel` | `<fleetId>` | recall one fleet by id (TelegramRetireFleet) |
| `/cancelmission` | `<Missions>` | recall every fleet of that mission |
| `/attacked` | – | `TelegramIsUnderAttack` → yes/no text |
| `/spycrash` | `auto \| g:s:p` | crash a probe to create DF (FleetScheduler.SpyCrash); target planet type forced |
| `/phalanx` | `<moon g:s:p> <target g:s:p>` | phalanx scan; origin must be own moon; per-fleet report |
| `/deploy` | `g:s:p moon\|planet <speed 1..10>` | deploy ALL ships+resources from current celestial |
| `/jumpgate` | `g:s:p auto\|full` | jump-gate ships from current moon; `auto` keeps only cargo needed for resources (LF bonus aware), `full` everything; target must be own moon |
| `/fleetjumpgate` | – | run `AutoFleetJumpGateWorker.RunFromTelegramAsync` immediately |
| `/switch` | `<speed 1..10>` | fleetsave-style swap current celestial ↔ its moon/planet (deploy); also used internally by autofleetsave with `attacked` param |
| `/recall` | `true\|false` | **writes** `SleepMode.AutoFleetSave.Recall` into the instance JSON (triggers reload) |

Economy / builders:

| Command | Arguments | Behaviour |
|---|---|---|
| `/build` | `<Buildables> [count]` | per planet: skip if shipyard/nanite busy; count = max affordable if absent; defences vs ships path |
| `/collect` / `/collectall` | – | harvest via FleetScheduler.Collect (all: no MinimumResources) |
| `/collectdeut` | `<minAmount int>` | deuterium-only harvest |
| `/minexpecargo` | `<int>` | **writes** `Expeditions.MinPrimaryToSend` (currently not read back by any worker — see findings) |
| `/getcurrentauction` | – | current auction state incl. offered resources |
| `/bidauction` | none → min-bid logic; or `<celestialId> M:x C:y D:z` | bid resources; min-bid path uses `Brain.AutoRepatriate.Target` as preferred source (scalar-access caveat, see findings) |
| `/subscribeauction` | – | one-shot timer; notifies when next auction starts |

Feature toggles (start/stop pairs, exact tokens):
`/startexpe` `/stopexpe` (Expeditions), `/startautomine` `/stopautomine` (BrainAutoMine),
`/startautoresearch` `/stopautoresearch`, `/startlifeformautomine` `/stoplifeformautomine`,
`/startlifeformautoresearch` `/stoplifeformautoresearch`, `/startdefender` `/stopdefender`,
`/startautofarm` `/stopautofarm` (AutoFarm), `/startautodiscovery` `/stopautodiscovery`
(AutoDiscovery). All: `StopFeature`/`InitializeFeature` + confirmation message.
`/stopautofleet...` does not exist; `BrainAutoFleepJumpGate` has **no** telegram toggle (only
`/fleetjumpgate`).

State & settings:

| Command | Arguments | Behaviour |
|---|---|---|
| `/getinfo` | none \| `<celestialId>` \| `g:s:p moon\|planet` | resources+ships of celestial (default: current) |
| `/getcelestials` | – | id/name/coords list |
| `/celestial` | `g:s:p moon\|planet` | set telegram "current celestial" (validated own celestial); no file write |
| `/editsettings` | `g:s:p moon\|planet [AutoMine\|AutoResearch\|AutoRepatriate\|Expeditions\|Colonize]` | **writes** the JSON: Brain.Transports.Origin (+AutoResearch.Target etc. per feature; arrays: element 0) then reload warning. Without feature arg updates ALL. |
| `/sleep` | `<duration>` e.g. `4h3m`, `3m50s` | arm TelegramSleepModeTimer (FormattingHelper.ParseDurationFromString) |
| `/wakeup` | – | WakeUpNow: clear timer, isSleeping=false, features on |
| `/cancelghostsleep` | – | cancel pending ghost sleep (else hint to `/wakeup`) |
| `/msg` | `<text>` | send IG message to every current attacker (dedup by id) |
| `/profile` | `ls` \| `ls-r` \| `load <n1> [n2..]` \| `reset` | profile list/running/merge-load/reset; writes nothing to disk; see lifecycle §5 |

Ghost family (fleet-save; duration parsed by `FormattingHelper.ParseDurationFromString`):

| Command | Behaviour |
|---|---|
| `/ghost <dur>` | fleetsave current celestial, mission None, no sleep |
| `/ghostto <dur> <Mission>` | idem with mission (Harvest/Deploy/Transport/Spy/Colonize) — note help text says `/ghostto`, command list has `/ghost` variant; the handler case is literally `case "/ghostto":` while `/help` documents `/ghostmoons` differently — see findings for the `/ghost`+mission vs `/ghostsleep` overlap |
| `/ghostmoons <dur> <Mission>` | fleetsave every moon, random AFewSeconds gaps |
| `/ghostsleep <dur> <Mission>` | fleetsave current celestial then `/sleep`-style: sets `telegramUserData.CurrentCelestialToSave`+`Mission` and passes sleep flag to AutoFleetSave |
| `/ghostsleepall <dur> <Mission>` | idem but `allCelestials=true` (extra flag on AutoFleetSave) |
| `/cancelghostsleep` | see above |

## Command → settings writes (audit trail)

| Command | Written path |
|---|---|
| `/recall t\|f` | `SleepMode.AutoFleetSave.Recall` |
| `/minexpecargo n` | `Expeditions.MinPrimaryToSend` |
| `/editsettings … AutoMine` | `Brain.Transports.Origin.*` |
| `/editsettings … AutoResearch` | `Brain.AutoResearch.Target.*` + `Brain.Transports.Origin.*` |
| `/editsettings … AutoRepatriate` | `Brain.AutoRepatriate.Target[0].*` |
| `/editsettings … Expeditions` | `Expeditions.Origin[0].*` |
| `/editsettings … AutoDiscovery` | `AutoDiscovery.Origin[0].*` |
| `/editsettings … Colonize` | `AutoColonize.Origin.*` (Type forced `Planet`) |
| (no arg) `/editsettings g:s:p type` | all of the above |

Every write goes through `TBotMain.EditSettings` → `WriteSettings` → file watcher → full worker
restart. `EditSettings` delays 500 ms and requires the target JSON sections to exist (direct
indexer access — a missing section throws and the command fails after the write is partially
applied? No: the JObject is modified in memory and serialized once at the end; a missing section
throws before `WriteSettings`, so the file is untouched).

## Unsafe / side-effectful operations worth knowing

- `/deploy`, `/switch`, `/jumpgate`, ghost family, `/cancel*`: move real fleets; `/sleep`,
  `/wakeup`, profile loads and any `/editsettings`-family write restart all workers.
- `/msg` sends in-game messages to other players (rate-limited only by per-attacker dedup).
- `/bidauction` spends resources; min-bid path can drain a planet up to the required points.
- No confirmation prompts anywhere: every command acts immediately.

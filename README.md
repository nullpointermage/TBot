# TBot — source-based operator and contributor handbook

TBot automates OGame account operations through a C# worker runtime, an integrated WebUI and a separate `ogamed-tbot` HTTP daemon. This fork extends the original TBot implementation. The behavior described here comes from the audited **`develop` source**, not assumptions carried over from the original README.

> **Account and security warning:** OGame's rules prohibit botting. This software cannot guarantee account safety or protection from bans, lost fleets or unwanted account actions. The current WebUI can read/write configuration without its own authentication. Keep it local or behind a deliberately authenticated access boundary.

## Which version does this documentation describe?

- TBot source baseline: [`35b4ce08b57bf2900d5b3d3b449a3f26f168270b`](https://github.com/0xE232FE/TBot/tree/35b4ce08b57bf2900d5b3d3b449a3f26f168270b), from upstream `develop`.
- Pinned daemon submodule: [`fbd0fda6ba9019c128926614f9865ba38a67b627`](https://github.com/0xE232FE/ogame.mod/tree/fbd0fda6ba9019c128926614f9865ba38a67b627).
- **Source requires .NET 10**, despite historical documentation mentioning .NET 6 and tracked workflows requesting .NET 9.
- Upstream's default `master` branch is older than this `develop` baseline. Release tags, assembly versions and source commits are different identifiers.
- Source-level behavior is **not** proof of validation against a live account or every OGame version.

See the [source-audit record](docs/source-audit.md) for coverage, reproducible checks and known limitations. Released packages may represent a different snapshot.

## Handbook

| Goal | Guide |
|---|---|
| Install/run without accidentally starting accounts | [Operations and safe first boot](docs/operations.md) |
| Understand every setting, units, examples, defaults and profiles | [Configuration reference](docs/configuration/README.md) |
| Understand account startup, reloads, sleep and shutdown | [Lifecycle](docs/lifecycle.md) |
| Configure fleets, farming, harvesting, discovery and colonization | [Fleet operations](docs/features/fleet-operations.md) |
| Understand incoming-attack handling and defensive actions | [Defender](docs/features/defender.md) |
| Configure mines, research, lifeforms, transports and other Brain workers | [Brain](docs/features/brain.md) |
| Understand fleet/cost/production/investment calculations | [Calculation reference](docs/calculations.md) |
| Use Settings/Logging/Ogame and understand exposure limits | [WebUI and interfaces](docs/interfaces.md) |
| Use Telegram commands and identify account-changing actions | [Telegram](docs/telegram.md) |
| Understand daemon flags/environment and HTTP operations | [Daemon](docs/daemon.md), [API](docs/daemon-api.md) |
| Extend or contribute to the project | [Architecture](docs/architecture.md), [Development](docs/development.md), [Contributing](CONTRIBUTING.md) |
| Understand game-data objects and enums | [Infrastructure models](docs/infrastructure-models.md) |

## Safe first boot with a published package

Use a native package and its **matching daemon** from [the maintained upstream fork's releases](https://github.com/0xE232FE/TBot/releases), not an old original-project release URL. Pick the correct platform, verify the asset digest when available, extract it and locate the actual application directory; archives can contain `publish/<platform>/`.

Before launching, edit the global `settings.json` beside the executable to an account-free configuration:

```json
{
  "TelegramMessenger": {
    "Active": false,
    "API": "",
    "ChatId": ""
  },
  "WebUI": {
    "Enable": true,
    "Urls": "http://127.0.0.1:9090",
    "MaxLogsToShow": 2000
  },
  "Instances": []
}
```

From that directory, on Linux/macOS:

```sh
chmod +x TBot ogamed
./TBot --settings=./settings.json --log=./log
```

On Windows use `TBot.exe`, the same supported switches and matching `ogamed.exe`. Open **http://127.0.0.1:9090/**; it redirects to Settings. `Instances: []` means no accounts initialize. The daemon executable must still exist as a startup prerequisite.

`MaxLogsToShow` is a template field, not a verified active control of the viewer's row cap; see [interfaces](docs/interfaces.md). Change the port if it is occupied.

**Do not add an instance before reviewing its entire configuration.** Bundled examples enable account-changing features and contain placeholder coordinates. Listed instances initialize automatically, including after a reload. This fork does not provide TBot++'s verified `--api-only` mode.

For credentials, multiple accounts, device identity, profiles and storage, follow [operations](docs/operations.md) and [configuration](docs/configuration/README.md). Keep real credentials out of tracked files, issues and chat.

## Implemented capability map

The guides explain exact gates and limitations. This table is not a promise that all capabilities run together or work without account-specific configuration.

| Area | Implementation | Guide |
|---|---|---|
| Multiple accounts | Global instance list, per-account configuration, initialization/removal and reload watchers | [Lifecycle](docs/lifecycle.md) |
| Profiles | Base configuration and ordered JSON overlays | [Configuration](docs/configuration/README.md) |
| Defender | Attack polling, configured probe/missile/weak-attack rules, fleet saving, alarms, notifications and attacker interactions | [Defender](docs/features/defender.md) |
| Expeditions | Origin/ship selection, capacity limits, slots/returns and configured sleep behavior | [Fleet operations](docs/features/fleet-operations.md) |
| Farming | Range scans, reports, profitability, shared targets and blacklist/success state | [Fleet operations](docs/features/fleet-operations.md) |
| Harvesting | Own/expedition debris targets, ship and minimum-resource constraints | [Fleet operations](docs/features/fleet-operations.md) |
| Discovery | Discovery missions, available positions, failure and slot scheduling | [Fleet operations](docs/features/fleet-operations.md) |
| Colonization | Position/range search and colony-ship dispatch; optional abandonment/intensive search can be destructive | [Fleet operations](docs/features/fleet-operations.md) |
| Mining/facilities | Planetary/lunar construction, energy/field/resource gates and investment limits | [Brain](docs/features/brain.md) |
| Research | Normal research priorities, targets and progression | [Brain](docs/features/brain.md) |
| Lifeforms | Lifeform buildings and selected technologies with separate limits/transports | [Brain](docs/features/brain.md) |
| Cargo/defenses | Configured cargo and defense construction | [Brain](docs/features/brain.md) |
| Resource logistics | Construction/research transports and resource/deuterium repatriation | [Brain](docs/features/brain.md), [Fleet operations](docs/features/fleet-operations.md) |
| Jump gates/offers | Configured gate transfers and daily-offer purchasing | [Brain](docs/features/brain.md) |
| Sleep/fleet saving | Scheduled/manual sleep, wakeup, saves/recalls and worker-specific exceptions | [Lifecycle](docs/lifecycle.md), [Fleet operations](docs/features/fleet-operations.md) |
| Telegram | Status, account selection, worker controls and account-changing commands | [Telegram](docs/telegram.md) |
| WebUI/logging | JSON editor, persisted/live filtered logs and embedded manual game proxy | [Interfaces](docs/interfaces.md) |
| Daemon | Login/device/storage, HTTP/SOCKS5 proxy, game reverse proxy and REST operations | [Daemon](docs/daemon.md) |

Names such as `AutoFleepJumpGate` and `LifeformAutoMine` are compatibility identifiers. Use exact keys from the reference instead of “correcting” their spelling.

## Build from current source

```sh
git clone --branch develop --recurse-submodules https://github.com/0xE232FE/TBot.git
cd TBot
dotnet build TBot.sln --configuration Release
```

**Known blocker:** the pinned daemon's `cmd/ogamed-tbot` target imports a missing `buildqueue` package. The complete current source bundle is not reproducibly buildable without addressing that defect. The C# build and Linux publish succeeded independently. [Development](docs/development.md) documents exact commands, warnings, platform mappings and stale CI/Docker recipes without hiding this distinction.

## Configuration principles

- Template values are examples, not universal defaults. The reference distinguishes explicit fallbacks, requiredness and missing-value casts.
- Profiles replace arrays rather than appending coordinates/targets. Later overlays can override earlier values.
- Missing dynamic values can cast to zero/false/null; these are not necessarily sensible operational defaults.
- The WebUI edits raw JSON, not a complete evaluated/merged view or validated account configuration.
- Slot reservations and priorities coordinate competing workers; understand them before enabling multiple features.
- Saving a global instance entry can initiate login; saving a feature flag can start actions. Review changes first.
- Manual gameplay can race automated workers; the iframe is not exclusive control.

## Contributions and attribution

This code descends from [ogame-tbot/TBot](https://github.com/ogame-tbot/TBot), with development in [0xE232FE/TBot](https://github.com/0xE232FE/TBot), and uses Alain Gilbert's tooling through [ogame.mod](https://github.com/0xE232FE/ogame.mod). Existing contributor attribution and dependency notices remain applicable. Project metadata references MIT, while dependencies carry separate notices; this documentation does not introduce a new license or resolve missing root-license paperwork.

The original project's [Discord community](https://discord.gg/NZSaY4aQ7J) and [support link](https://www.paypal.com/donate/?hosted_button_id=2QXP4KAKZRGL4) are retained for attribution, not as verification of current fork behavior.

Corrections should cite source and state how they were verified. Behavior fixes should add focused tests and update the reference. Never submit private account data as a reproduction case. See [CONTRIBUTING](CONTRIBUTING.md).

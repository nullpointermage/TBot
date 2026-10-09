# Building and contributing from source

This page documents the audited `develop` tree, not the historical README or a promise that every release artifact matches it. See [source audit](source-audit.md) for revision and verification scope.

## Prerequisites determined from source

- **.NET 10 SDK**: every C# project currently targets `net10.0`. A .NET 6 or 9 SDK alone cannot build this tree. For framework-dependent execution, both .NET and ASP.NET Core shared runtimes must satisfy the target; a self-contained publish carries the runtime but still needs compatible native OS libraries.
- **Go** for the daemon: the pinned [`ogame/go.mod`](../ogame/go.mod) declares `go 1.23.0` and `toolchain go1.23.1`. Use a compatible supported toolchain; a newer version is not automatically equivalent, so record it in build reports.
- Git with submodule support, access to NuGet/Go dependency sources, and sufficient disk for build/publish output.
- No npm install is required for the current WebUI: Razor views and static JavaScript/CSS are in the repository, with static assets embedded in `TBot.WebUI`.

Sources: [solution](../TBot.sln), [TBot project](../TBot/TBot.csproj), [WebUI project](../TBot.WebUI/TBot.WebUI.csproj), [Common project](../TBot.Common/TBot.Common.csproj), [Infrastructure project](../TBot.Ogame.Infrastructure/TBot.Ogame.Infrastructure.csproj).

## Clone the maintained code line

```sh
git clone --branch develop --recurse-submodules https://github.com/0xE232FE/TBot.git
cd TBot
git rev-parse HEAD
git submodule status
```

For your contribution fork, substitute its URL and retain `0xE232FE/TBot` as `upstream`. Do not assume the default branch is the latest implementation: at the audit baseline, upstream `master` is older than `develop`.

If already cloned:

```sh
git submodule update --init --recursive
```

The gitlink pins the daemon revision. `.gitmodules`' branch selector is used for explicit remote updates; it does **not** replace the pinned revision on ordinary submodule initialization. Avoid `git submodule update --remote` during reproducible verification.

## Build the C# solution

From the repository root:

```sh
dotnet restore TBot.sln
dotnet build TBot.sln --configuration Release --no-incremental
```

The entry point is `Tbot.Program` in the `TBot` executable project. `TBot.WebUI` is an integrated library, not a separate frontend server to start on its own. Project references include the common settings/logging library and the OGame infrastructure adapter.

**Observed:** the audited source built with .NET SDK10.0.111, with zero errors and existing warnings. Warnings include nullable-reference/compiler diagnostics and NuGet advisories for ImageSharp. A successful compilation is not a security approval or a game-account test.

## Publish a Linux x86-64 bundle

```sh
dotnet publish TBot/TBot.csproj --configuration Release \
  --runtime linux-x64 --self-contained true \
  -p:PublishSingleFile=true --output publish/linux-x64
```

The publish copies `settings.json`, `instance_settings.json` and profile files. These are upstream examples, **not a safe account configuration**. Review and disable unwanted automation before launching. The executable's settings location is based on `AppContext.BaseDirectory`, unless `--settings=` is provided; logs default to `log` under the current working directory.

**Observed:** a self-contained Linux publish of the audited C# source succeeded. The daemon is a separate build and is not implicitly included by `dotnet publish`.

## Build the matching daemon: current blocker

The repository's release scripts intend this command:

```sh
(cd ogame && go build -o ../publish/linux-x64/ogamed ./cmd/ogamed-tbot)
```

**At the pinned daemon revision this command fails:** `cmd/ogamed-tbot/main.go` imports `github.com/alaingilbert/ogame/cmd/ogamed-tbot/buildqueue`, but the pinned tree does not contain that package. This was observed with Go1.27.2. Do not fix it by an unexplained `go get` or silently swapping in a different daemon; the imported path is part of the same module, and compatibility depends on the intended implementation.

Until the source defect is resolved, this guide does not claim a complete reproducible TBot+daemon build from the current tree. A published release contains its own matching daemon and is a separate deployment option. See [daemon details](daemon.md).

For a complete bundle, both executable files must be in the same application directory and executable on Unix:

```sh
chmod +x publish/linux-x64/TBot publish/linux-x64/ogamed
```

The permission command is applicable only after both files actually exist.

## Other publish targets

The tracked workflows enumerate these mappings. They describe intended packaging, not fresh validation on every platform.

| .NET runtime identifier | Go target | Daemon filename |
|---|---|---|
| `win-x64` | `GOOS=windows GOARCH=amd64` | `ogamed.exe` |
| `win-x86` | `GOOS=windows GOARCH=386` | `ogamed.exe` |
| `linux-x64` | `GOOS=linux GOARCH=amd64` | `ogamed` |
| `linux-arm` | `GOOS=linux GOARCH=arm GOARM=7` | `ogamed` |
| `linux-arm64` | `GOOS=linux GOARCH=arm64` | `ogamed` |
| `osx-x64` | `GOOS=darwin GOARCH=amd64` | `ogamed` |
| `osx-arm64` | `GOOS=darwin GOARCH=arm64` | `ogamed` |

Native dependencies and CGO settings may constrain cross-compilation. Do not advertise a target as working merely because a workflow names it.

## Existing automation is stale

- [Snapshot workflow](../.github/workflows/snapshot.yml): pushes/PRs for `develop` and `newbb`, .NET9.0.x setup, Go~1.23.0, packaging and old artifact actions.
- [Release workflow](../.github/workflows/release.yml): every pushed tag, .NET9.0.x setup, Go~1.23.0, per-platform publishing and a **draft** release. Version metadata is overridden from `git describe`/the selected tag.
- **Mismatch:** both workflows request .NET9 while the projects target .NET10. Their existing configuration is not evidence that current CI succeeds.
- [Dockerfile](../Docker/Dockerfile): starts from ASP.NET6.0, downloads the original project's `v0.3.4`, uses historical metadata and a build-time default password. It is **not a container recipe for this audited fork**. Do not use it as a current quickstart or expose its ports publicly.
- Project/assembly version strings still say3.3.9; source revision, release tag and assembly metadata are distinct identifiers. Use exact git commits to identify the implementation.

These discrepancies are documented, not repaired by this documentation-only contribution.

## Verification without touching an account

Safe checks include:

1. Build/publish into a new directory, never over an active deployment.
2. Run `TBot --help` from that output.
3. Supply a temporary global configuration with `Instances: []`, disabled Telegram and a loopback-only free WebUI port.
4. Provide an actual daemon executable as the prerequisite file; with no instances it must not be launched. If a release daemon is used for this UI-only check, record that fact and do not claim source-daemon interoperability.
5. Verify the Settings, Logging and Ogame pages, the settings-read endpoint, and `/realTimeLog` negotiation.
6. Stop the temporary process and verify the production process/configuration were unchanged.

There is no C# test project in the audited solution. `dotnet test` returning without tests is not a passing feature suite. The Go submodule contains tests; inspect their network/account requirements before running them. Pure settings/helper probes can verify overlay semantics, missing-value casts and duration parsing without login.

## Contribution rules

Read [CONTRIBUTING](../CONTRIBUTING.md). Keep code changes, dependency upgrades, safety fixes and documentation refreshes reviewable as separate contributions. Never commit live settings, cookies, tokens, passwords, account fixtures or private logs. A generated publish directory is ignored by the existing `.gitignore`, but the tracked example JSON files are not secret storage.

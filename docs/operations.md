# Operations, deployment and safe first boot

This guide follows the audited fork's code. It replaces historical advice to expose wide port ranges or delete all `.ogame` storage. It is not a guarantee that the bot is permitted by OGame or that a configured fleet-save is safe for every account.

## Release, source and daemon identity

Choose one of two explicit paths:

- **Published bundle:** obtain the platform archive from `0xE232FE/TBot` releases and use the daemon packaged with it. Record release tag and digest. A fork created for contributions does not automatically inherit release assets.
- **Source build:** use `develop` and its exact daemon gitlink. Current .NET10 compilation/publish succeeds, but the pinned `ogamed-tbot` target has a missing `buildqueue` import. See [development](development.md); do not silently substitute a daemon and call the complete source build verified.

Do not identify a deployment only by its assembly version: the project file retains older metadata and release workflows can override it.

## Account-free startup

1. Extract/publish to a new application directory, separate from any active deployment.
2. Ensure the native TBot and daemon executables are present. On Unix grant execute permission.
3. Configure global `settings.json` beside the executable with a present, empty `Instances` array, disabled Telegram and `WebUI.Enable=true`/loopback URL. Omitting `Instances` invokes the legacy single-account path; it is not equivalent to `[]`.
4. Use a free WebUI port. Account daemon ports must be different from the WebUI and from each other.
5. Run TBot from the application directory with the supported `--settings=` and `--log=` options.
6. Verify `/Settings`, `/Logging`, `/Ogame`; no accounts means an empty Ogame selector and no account workers. Startup still checks for a daemon executable.

A safe complete global example is in [README](../README.md). There is no established `--api-only`, `--web`, `--headless` or `--no-browser` flag in this fork's `CmdLineArgsService`; do not import command-line switches from TBot++.

## Configure the first account deliberately

The two main files serve different purposes:

- `settings.json`: shared WebUI/Telegram configuration and instance list.
- instance JSON: credentials, device identity, proxy/daemon connection and automation sections.

Prepare account files **outside tracked source templates**. Stop the production process while preparing the first configuration if you do not want a save/reload to initialize an account immediately.

1. Copy the example to a deployment-specific file and review every setting. Example coordinates, ship counts, limits and active flags are not your account's values.
2. Enter credentials locally, not in GitHub/chat. `Credentials.Universe`, `Email`, `Password` and `Language` feed daemon login. Read the [credential/device reference](configuration/instance.md) for their exact semantics.
3. Choose a unique `DeviceConf.Name` for unrelated account/session identities. Read [daemon storage](daemon.md) before reusing or deleting identity files.
4. Set a distinct available daemon port and a host reachable by the C# adapter. Review the listen-address caveat below: this field does not by itself restrict daemon exposure.
5. Start with account-changing feature groups disabled: Defender actions, Brain features, Expeditions, AutoFarm, AutoHarvest, AutoColonize/Abandon, AutoDiscovery and sleep fleet saves. Also review selected profiles, which can override your base configuration.
6. Add the account to global `Instances` only when ready to initialize it:

```json
{
  "Alias": "My account",
  "Settings": "my-account.json"
}
```

This object is one entry inside `Instances`, not a standalone global settings file. The runtime resolves its settings path relative to the global file. The WebUI has additional executable-directory assumptions; keep files colocated unless you have tested that layout.

**Adding an instance can initiate login immediately.** This fork has no separately verified “configured but stopped” instance lifecycle switch equivalent to TBot++'s Cockpit. Enabling feature groups can perform real account actions. Review [lifecycle](lifecycle.md), [fleet operations](features/fleet-operations.md) and [Brain](features/brain.md) before enabling them.

## Profiles and reloads

Profiles are JSON overlays, not independent bot executables. Their selected order matters; array values replace earlier arrays and null overlays are ignored. The repository includes example profiles, but none is a universal safe preset. See [configuration](configuration/README.md) for the selector and all profile keys.

File watchers react to persisted configuration changes. Saving from the WebUI is not merely changing text: it can add/remove accounts and start/stop/reconfigure workers. A raw editor view is not an effective merged-settings view. Keep a private known-good deployment copy and check logs after reload.

## Network exposure: two different listeners

| Surface | Source of address/port | Risk |
|---|---|---|
| C# WebUI | `WebUI.Urls` | Settings/Logging are not protected by a configured WebUI authentication scheme. |
| Go daemon | Started by `OgameService.ExecuteOgamedExecutable`; port comes from instance configuration, launch string includes `--host=0.0.0.0` | `General.Host=127.0.0.1` sets the adapter target but does not fix that forced listen address. |

`Credentials.BasicAuth` protects the daemon when configured; it does not authenticate the C# Settings editor. `UseAuthorization`, HSTS, host headers and HTTPS redirection are not substitutes for a configured login boundary.

For a local installation, constrain both listeners to loopback. Because the adapter supplies all-interface binding, a deployment can use a clearly documented daemon-launch wrapper that removes both forms of the `--host` argument and appends `--host=127.0.0.1`, while preserving the original daemon separately. Test the actual resulting socket. Alternatively use a deliberate network namespace/firewall policy. This handbook does not change the runtime's launch string.

For remote access, prefer an SSH tunnel to a loopback listener or a reviewed authenticated reverse proxy. Do not follow historical advice to open an unauthenticated range to every IP. Remember that an iframe URL containing `localhost` resolves on the browser's machine; remote WebUI access and daemon reverse-proxy access are separate problems.

## Filesystem and credentials

- Configuration and session/cookie storage can contain recoverable credentials. Use restrictive permissions and private backups.
- Account passwords and optional authentication/proxy credentials are supplied to the daemon's process arguments by the adapter. Command-line visibility and accidental process/log capture are security concerns, not solved by JSON file permissions alone.
- WebUI file APIs combine requested names with the executable directory without a containment allowlist. Run the application with access only to files it actually needs. Do not expose the editor to untrusted operators.
- Logs can include account/operational data and exception details. Redact them before contribution.
- Do not wipe the user's entire `.ogame` directory on a routine update. Determine the daemon's identity/storage path and preserve unrelated sessions first.
- An isolated application HOME can keep bot storage separate from existing user sessions. On self-contained .NET bundles, explicitly select a writable extraction directory with `DOTNET_BUNDLE_EXTRACT_BASE_DIR` when sandboxing.

## Running as a Linux user service

Example only: replace the application path and prepare the writable HOME/log directories before use. This is not an upstream-provided service file or power-loss validation.

```ini
[Unit]
Description=TBot local account runtime
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/Apps/TBot
ExecStart=%h/Apps/TBot/TBot --settings=%h/Apps/TBot/settings.json --log=%h/Apps/TBot/log
Environment=PATH=/usr/bin:/bin
Environment=HOME=%h/Apps/TBot/private-home
Environment=DOTNET_BUNDLE_EXTRACT_BASE_DIR=%h/Apps/TBot/bundle-cache
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=default.target
```

The application's directory may need to be in PATH because the adapter starts `ogamed` by name; add it to this service's PATH deliberately. Do not alter every terminal's environment to fix a service. Additional filesystem/network sandboxing must be tested with your storage/layout and daemon startup.

Typical management commands after installing your own unit:

```sh
systemd-analyze --user verify ~/.config/systemd/user/tbot.service
systemctl --user daemon-reload
systemctl --user start tbot.service
systemctl --user status tbot.service
journalctl --user -u tbot.service -f
systemctl --user stop tbot.service
```

Enable autostart only after acceptance. Account entries persist and initialize on startup; a service restart is not necessarily an account-free action. User-session startup, lingering after logout and hardware power-on after an outage are separate properties.

## Updating without losing account state

1. Record actual source/release identity, daemon identity, selected profiles, paths and enabled features.
2. Back up deployment configuration, storage and private logs securely; do not copy them into a public fork.
3. Prepare the new version separately and read code/config changes. Verify builds and account-free UI first.
4. Reconcile changed settings and path semantics; do not overwrite private files with newly copied examples.
5. Stop the existing runtime through its own manager before switching files or ports. Ensure its daemon processes are also gone.
6. Start one coordinated runtime and inspect logs/daemon listeners/account state.
7. Keep the old executable/daemon/configuration available for rollback until acceptance.

No update routine should silently enable example features, delete unrelated session state or claim a successful login solely from an active process.

## Troubleshooting by observed layer

| Symptom | Check |
|---|---|
| Native executable refuses to launch | Platform/architecture, execute permissions, native libraries and runtime/bundle extraction path. |
| Source build reports framework mismatch | Current projects target.NET10; README/workflow.NET6/.NET9 guidance is stale. |
| Go build cannot find `buildqueue` | Known pinned-submodule source defect; see [development](development.md). |
| “ogamed not found” at startup | Correct companion filename beside the executable and startup prerequisite check. |
| Daemon cannot be executed later | PATH/current working directory, permission and platform match; file presence alone is insufficient. |
| UI root has no body | Follow the normal302 redirect to Settings. |
| Ogame selector is empty | No configured instances; distinguish it from frontend failure. |
| Credentials/config edits seem ignored | Wrong raw file, overlay precedence, executable/global directory mismatch, watcher/log errors. |
| Logs page empty | Correct date, CSV filename, permissions, server/browser timezones and filters; read helper can suppress CSV exceptions. |
| Live logs fail | SignalR negotiation, browser network/console, CDN script availability, proxy transport handling. |
| Hostname/port works locally but iframe fails remotely | Client-side address resolution, HTTP/HTTPS mixed content and separate daemon access. |
| Worker is idle | Parent/feature enablement, sleep/attack/slot/resource/queue gates and next scheduled timer; see feature-specific guide. |
| Account context/login fails | Credentials/community/universe, correct daemon/API, device/storage/proxy state and specific log error. Do not retry destructively. |
| Settings save reports success then runtime misbehaves | JSON syntax passed, not complete schema/account-safety validation. Restore a reviewed private configuration. |

## Verification limits

The contribution verifies source build/publish, pure settings/helper behavior and account-free WebUI/API operation. It does not validate live login, every OGame version, fleet safety, ban avoidance, every operating system, source-daemon interoperability or reboot recovery. Keep those claims separate from code-derived documentation.

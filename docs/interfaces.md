# WebUI and operator-facing interfaces

The audited fork has a small integrated ASP.NET Core/Razor WebUI: **Settings**, **Logging** and **Ogame**. It is not TBot++'s Cockpit/Instances/Combat control plane, and those screens or `/api/config/*` routes must not be assumed to exist here.

Sources: [WebApp](../TBot.WebUI/Program.cs), [layout](../TBot.WebUI/Views/Shared/_Layout.cshtml), [controllers](../TBot.WebUI/Controllers/SettingsController.cs), [browser settings code](../TBot.WebUI/wwwroot/js/settings.js).

## Hosting and routing

`WebApp.Build` reads `WebUI.Urls` and passes comma-separated, trimmed values to `UseUrls`. `Program` later uses `WebUI.Enable` to decide whether to run the web host; disabling the UI is not a separate account-free mode. The normal MVC route is `{controller=Home}/{action=Index}/{id?}`.

| Interface | Input | Result and behavior | Source |
|---|---|---|---|
| `/` or `/Home/Index` | none | Redirect to `/Settings`; an initial302 is normal. | `HomeController.Index` |
| `GET /Settings` | none | JSON-file editor with the global file basename and every configured instance's `Settings` path. | `SettingsController.Index/GetFileNames` |
| `GET /Settings/GetFileContent` | `fileName` | `{ "data": "raw JSON text" }`; reads relative to the executable directory, not an arbitrary selected global-settings directory. | `SettingsController.GetFileContent` |
| `POST /Settings/SaveFileContent` | form fields `fileName`, `content` | Parses JSON, writes formatted text, returns `{ "success": true }` or `{ "success": false, "error": "..." }`. JSON validity is checked, **not the complete bot-setting schema or operational safety**. | `SettingsController.SaveFileContent` |
| `/Logging` | optional `date` in `dd/MM/yyyy` | Log viewer; view's date input is `yyyy-MM-dd`. | `LoggingController.Index` |
| `/Logging/GetLogs` | `date` in `yyyy-MM-dd`; optional `lastTime`, `search`, `logSender`, `logLevel` | `{ "content": [...], "hasMoreData": boolean }` for persisted CSV entries. Details below. | `LoggingController.GetLogs` |
| `/realTimeLog` | SignalR protocol | Live log hub; negotiate with `POST /realTimeLog/negotiate?negotiateVersion=1`, then connect with a negotiated transport. | `WebApp.Main`, `WebHub` |
| `/Ogame` | none | Instance selector and iframe whose URL is `http://General.Host:General.Port/game/index.php`. It embeds the **daemon's** reverse-proxy endpoint. | `OgameController.Index/GetInstancesList` |
| `/Home/Error` | optional framework request ID | Generic production error page, including request identifier. | `HomeController.Error` |

For methods with no `[HttpGet]`/`[HttpPost]` attribute, the table describes their normal browser usage, not a guarantee that other HTTP methods are rejected. Static assets are served from the embedded `wwwroot` manifest.

## Editing settings

1. Settings opens the first listed file automatically.
2. Selecting another file reads its current contents into `JsonEditor`.
3. Editing the browser is not persistence until **Save** is clicked.
4. **Reload current file** reads the file again and can discard unsaved browser changes.
5. Save posts the entire JSON document. File watchers may then initialize/remove accounts or change active features. It is not a harmless text-only operation once accounts are configured.

The file list is derived from configuration, but the read/write actions do not enforce that the requested `fileName` is one of those listed. They use `Path.Combine` without containment/allowlist checks. Treat access to this UI as access to the process's filesystem permissions. The contribution documents this limitation; it does not silently repair it.

**Path caveat:** if `--settings=/some/other/directory/settings.json` is used, the UI lists that file's basename but still reads/writes under the executable directory. The runtime resolves instance settings relative to the global settings file; `OgameController` uses the executable directory. Keep configuration with the executable unless you have specifically tested your alternative layout.

Profile overlays are not separately listed by `GetFileNames` merely because they are under `profiles/`; see [configuration reference](configuration/README.md) for their runtime selection semantics.

## Log filtering and pagination

[`LoggingController`](../TBot.WebUI/Controllers/LoggingController.cs) reads `TBotYYYYMMDD.csv` from `SettingsService.LogsPath`, using invariant-culture CSV parsing and file sharing suitable for an active writer.

- `search`: case-insensitive substring search in the message.
- `logSender`: case-insensitive exact sender match; empty or `All` means no sender filter.
- `logLevel`: threshold mapping `Trace=0`, `Debug=1`, `Information=2`, `Warning=3`, `Error=4`; unknown values map to0 on the server.
- `lastTime`: only entries strictly older than the parsed timestamp; malformed input may fail the request.
- Order: descending position within the day's CSV, not a freshly sorted global multi-file timeline.
- Page: take100 entries, then include additional entries with the last selected timestamp so that a timestamp group is not split. Responses can therefore exceed100 rows.
- `hasMoreData` compares the returned size against the filtered available rows; it is not a separate cursor.
- Missing or unreadable CSV can produce an empty result because the CSV read helper catches errors.
- File-size rolled CSV siblings are not enumerated by this controller: the day-base filename is selected directly.

[`logging.js`](../TBot.WebUI/wwwroot/js/logging.js) loads history, supports sender/severity/date/search controls and adds a **Load more logs** action. Search is debounced for one second. Live SignalR is connected only when viewing today; it has automatic reconnection plus a5-second retry on initial failure.

Live messages arrive as `SendLogAsObject`, containing timestamp, level, message, exception and enriched properties such as `LogSender`. Browser rows use `.text(...)`, not raw message HTML. The visible timestamp uses the browser's `toLocaleString`, so format/timezone follow that browser, not a dedicated12-hour setting.

`WebUI.MaxLogsToShow` appears in the template but the current browser code initializes its visible cap from history/page size, starting at100. Do not infer that changing the template field configures this behavior. Serilog's `Verbose`/`Fatal` names also do not line up perfectly with the viewer's `Trace`/`Error` mapping; do not treat the thresholds as a comprehensive structured log taxonomy.

## Persisted logs and retention

[`LoggerService.GetDefaultConfiguration`](../TBot.Common/Logging/LoggerService.cs) provides:

- console output enriched with managed thread ID, sender, severity and emoji properties;
- `TBot.log`, daily and size rolling,10 MiB file-size limit and10 retained files;
- `TBot.csv`, daily and size rolling, the same size limit, CSV header `type,sender,datetime,message`;
- live SignalR delivery to all clients unless configured targets/exclusions are provided at the sink level;
- optional Telegram logging controlled by the application services.

CSV timestamps are generated with `DateTime.Now` and invariant culture. The CSV formatter writes the message template and prefixes exception text where present; it is not an arbitrary structured-event archive. CSV retention is not explicitly set in that call, so do not equate it to the text log's explicit10-file limit.

The sink creates live IDs independently. No durable replay position is shared across the websocket and CSV beyond the viewer's own reconstructed ordering. Logs can contain operational/account data: protect them and redact them before attaching to an issue.

## Ogame iframe and manual play

The selector enumerates configured accounts, obtains the instance's raw `General.Host`/`General.Port` and points the iframe at the daemon's `/game/index.php` reverse proxy. No configured instances means an empty selector; it does not mean the WebUI failed.

Manual game actions inside the iframe still affect the real account. The bot may continue acting independently. A remote browser resolves `localhost` or `127.0.0.1` on **the client machine**, not the bot server, and HTTPS parent pages may block an HTTP iframe. Do not solve those issues by exposing an unauthenticated daemon publicly; use deliberate authenticated access/tunneling.

## Authentication and exposure boundaries

`UseAuthorization()` is present, but the audited WebUI has no configured authentication scheme, controller authorization attributes or its own login flow. The daemon's `Credentials.BasicAuth` is a different boundary and does **not** protect these Settings/Logging endpoints. Settings contain plaintext account credentials and may be shown by the editor.

Keep the WebUI loopback-only or behind an explicitly authenticated access layer. Do not assume `AllowedHosts: "*"`, HSTS or HTTPS redirection provides authentication. Production error handling reduces diagnostic detail; enabling Development can expose additional information.

The Settings save action has no visible anti-forgery enforcement. Only grant access to trusted operators and do not expose it to untrusted origins/users. This is source-observed risk documentation, not a penetration test or a complete security audit.

## Assets, external dependencies and apparent offline support

- Embedded local assets include Bootstrap, jQuery, CSS, images and configuration-editor code.
- The Settings view additionally loads jQuery from `code.jquery.com` with an integrity attribute.
- The Logging view loads SignalR6.0.1 from `cdnjs.cloudflare.com`.
- A manifest enables standalone-display metadata and icons.
- `serviceWorker.js` merely registers a fetch listener that returns immediately. There is **no implemented offline cache/replay behavior** there.
- `JSONedtr.js` and its CSS are present but the current Settings view uses `jquery.json-editor.min.js` and `JsonEditor`; presence in the tree does not make every editor active.
- Template Home/Privacy views remain in the tree; Home redirects to Settings and the actual controller has no Privacy action. They are not documented as working bot features.

## Other control surfaces

- [TBot lifecycle/CLI](lifecycle.md): supported switches, startup and reload behavior.
- [Telegram](telegram.md): command authorization, exact grammar, account selection and actions.
- [Daemon API](daemon-api.md): underlying HTTP endpoints and side effects. These are not WebUI controller routes.

# Contributing to TBot

This documentation effort is based on the implementation in `0xE232FE/TBot`'s **develop** branch. The original README/wiki, the older default master branch, assembly metadata and published release tags are not interchangeable sources of behavior.

## Start from the correct code line

1. Fork the maintained repository under your own GitHub account.
2. Clone your fork's `develop` branch with submodules.
3. Add `https://github.com/0xE232FE/TBot.git` as `upstream`.
4. Create a focused branch from the intended upstream branch; identify that base explicitly in the PR.
5. Initialize the pinned daemon with `git submodule update --init --recursive`, not an implicit remote update.

Example, replacing `YOUR_ACCOUNT` with your account:

```sh
git clone --branch develop --recurse-submodules https://github.com/YOUR_ACCOUNT/TBot.git
cd TBot
git remote add upstream https://github.com/0xE232FE/TBot.git
git switch -c docs/my-correction
```

Use separate directories for source/contribution work and live deployment. Never publish deployment passwords, cookies, device storage or account logs.

## Documentation changes

Treat actual source as the authority and make it easy for another contributor to verify a claim.

For every changed setting/feature explanation:

- preserve the exact identifier, including historical misspellings;
- identify the consumer method/file and parent/worker gates;
- distinguish a template example from an explicit code fallback, missing-value cast and required field;
- give type/units/ranges where established, and say when the implementation does not validate a value;
- describe effects, scheduling, interactions and failure behavior, not just a promotional feature name;
- explain whether an action persists settings, changes the account, changes runtime-only state or only reads information;
- update the relevant handbook/reference entry and navigation links;
- record what was verified dynamically versus only derived from code.

Use [configuration](docs/configuration/README.md), [feature guides](docs/features/brain.md), [interfaces](docs/interfaces.md) and [source audit](docs/source-audit.md). Avoid putting every reference table into one unreviewable README: the root README is the orientation/quickstart, while the handbook carries exhaustive detail.

## Behavior changes

Keep runtime changes separate from broad documentation cleanup where practical. A change should contain:

1. A reproducible problem statement with redacted/synthetic account-independent inputs.
2. A test showing the intended behavior or regression.
3. The smallest justified implementation change in its owning component.
4. Configuration/feature/API documentation changes for altered behavior.
5. Exact build/test commands, toolchain versions and observed results.
6. Compatibility notes for existing configurations, profiles, daemon versions and operating systems.

Do not bypass the fleet scheduler, resource calculation or existing HTTP adapter casually. New worker behavior needs cancellation/reload/sleep/attack/slot interactions to be understood. Keep contributions focused on the bot behavior being changed.

## Source style and dependencies

Follow the existing [EditorConfig](.editorconfig): UTF-8, tabs, final newlines and the repository's C# brace/spacing conventions. Match nearby namespace/interface naming patterns rather than doing a whole-tree formatting sweep.

Review dependency upgrades individually, including their actual advisories/changelog and transitive effects. Do not hide existing warnings by disabling audits or broad compiler diagnostics. The current ImageSharp advisories and stale workflow framework selection are documented baseline issues, not proof that a docs change introduced them.

Keep model/enum/API changes coordinated between `TBot.Ogame.Infrastructure` and the Go daemon. Root source changes do not update the submodule; a daemon change must be committed in its own repository and the root gitlink updated deliberately.

## Verification expectations

Follow [development](docs/development.md). At minimum:

```sh
dotnet build TBot.sln --configuration Release
python3 tools/check_docs.py
```

The strict checker now passes for the completed pinned baseline: all 497 first-party files have read coverage and zero remain incomplete. `--allow-incomplete-audit` remains an explicit option for a future bounded partial review; it must still fail on broken links, stale source hashes or invalid read evidence, and must retain an incomplete flag when gaps exist. See the audit record for evidence and runtime/test limitations.

The documentation checker covers reference/links/snippets/source inventory; it is not a game-safety test or a substitute for semantic review. Source hashes/reference coverage must be intentionally refreshed when audited implementation files change.

The audited C# solution has no test project. Do not claim a passing C# feature suite from `dotnet test` finding nothing. Pure helper/settings tests and account-free WebUI smoke checks are possible without game login. Go tests need inspection for network/account requirements; do not run arbitrary live integration tests against someone else's credentials.

Current pinned `ogamed-tbot` compilation is blocked by a missing internal `buildqueue` package. A good PR records that baseline honestly rather than inventing a complete green build. CI/Docker definitions also contain stale framework/action/release choices; changes to them should be an explicit, separately verified contribution.

## PR description

Include:

- **Base:** upstream branch and source/submodule revisions used.
- **Problem:** what was wrong or undocumented.
- **Changes:** code/docs files and the behavior they describe/change.
- **Verification:** commands, exit status, warnings, account-free versus live scope, platforms actually checked.
- **Risks/limits:** remaining unknowns, migrations, destructive actions and untested paths.
- **Source evidence:** consumer methods or links supporting non-obvious claims.

Do not label a feature production-ready merely because compilation succeeds. Do not claim ban protection, secure public exposure or fleet preservation without the appropriate evidence. Leave unrelated bugs as clearly described follow-up work instead of quietly changing behavior in a documentation PR.

## Security reports and secrets

WebUI file editing and daemon listeners need deliberate access controls. See [operations](docs/operations.md) for known source-observed limitations. Use private reporting channels for issues whose reproduction includes credentials or sensitive account data; never paste those into a public issue.

Before pushing, inspect the staged diff and filenames. Tracked example JSON files are especially easy to turn into accidental credential leaks. Preserve contributor attribution and vendored license notices. The tree's project metadata references a license but does not include a root license file; do not resolve that ambiguity by silently choosing a new license in a documentation contribution.

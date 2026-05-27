# pi-less-yolo + little-coder Integration

> **⚠️ DUBIOUS — NOT YET VERIFIED**
>
> This document records the design decisions, code paths traced, and assumptions
> made during the integration of little-coder into pi-less-yolo. **Nothing in
> this document has been verified by actually running the container.** Every
> assumption listed below must be double-checked before relying on it.
>
> **Status:** Theorycraft only. No end-to-end test has been executed.

---

## 1. Goal

Run little-coder (a curated set of ~25 extensions, ~30 skills, and a bundled
pi runtime) inside pi-less-yolo's Docker container **without touching the host's
global `~/.pi/agent/`** and **without any manual setup beyond `mise run pi`**.

---

## 2. Problems Identified

### 2.1 npm Pulls from Registry, Not Local Fork

**Assumption:** `npm install -g "little-coder@1.8.1"` pulls from the npm
registry, ignoring any local changes.

**Decision:** Copy the local fork into the Docker image via `COPY
vendor/little-coder/ /little-coder-source/` then `npm install -g .`.

**⚠️ Needs Verification:**
- Does `npm install -g .` from a directory with a `package.json` install the
  package globally with the correct name (`little-coder`)?
- Does it resolve transitive dependencies (especially
  `pi-coding-agent@^0.75.3`) from the registry or from the vendored copy?
- Does the `bin/little-coder.mjs` entry point get registered as the `little-coder`
  command?

### 2.2 Entry Point Was `pi`, Not `little-coder`

**Assumption:** The original Dockerfile's entrypoint called `exec pi "$@"`,
which would run vanilla pi instead of the little-coder launcher that wires in
all extensions, applies patches, sets the system prompt, etc.

**Decision:** Changed to `exec little-coder "$@"`.

**⚠️ Needs Verification:**
- Is `little-coder` on PATH inside the container? (It should be, via the global
  npm install.)
- Does `little-coder` exit cleanly when invoked from the entrypoint?

### 2.3 Update Check Runs Before `PI_SKIP_VERSION_CHECK` Is Set

**Assumption:** The launcher sets `PI_SKIP_VERSION_CHECK=1` in step 7, but
`checkForUpdate()` runs in step 5. The env var has zero effect.

**Decision:**
- Added `PI_SKIP_VERSION_CHECK` check to `shouldSkip()` in `update-check.mjs`.
- Moved the env var set to BEFORE `checkForUpdate()` in the launcher.

**⚠️ Needs Verification:**
- Does `shouldSkip()` actually check `PI_SKIP_VERSION_CHECK`? (The original code
  only checked `LITTLE_CODER_NO_UPDATE_CHECK`.)
- Is the env var set early enough that `checkForUpdate()` sees it?

### 2.4 Playwright Might Not Install on Chainguard/Wolfi

**Assumption:** `playwright install --with-deps` expects apt/yum system
dependencies. Wolfi uses apk, which isn't a recognized distro.

**Decision:** Added graceful fallback chain:
```
--with-deps chromium → install chromium → echo warning
```

**⚠️ Needs Verification:**
- Does `npx playwright install chromium` (without `--with-deps`) work on Wolfi?
- Will the browser extension tools actually function, or will they always fall
  back to the error path?

### 2.5 `models.json` Not Accessible from pi-less-yolo Convention

**Assumption:** The `llama-cpp-provider` extension checks
`$HOME/.config/little-coder/models.json` but not `PI_CODING_AGENT_DIR/models.json`.

**Decision:** Added `PI_CODING_AGENT_DIR/models.json` to the resolution order in
`config.ts`.

**⚠️ Needs Verification:**
- Does the resolution order check `existsSync()` before returning? (A broken
  early return could skip all fallback paths.)
- Is `PI_CODING_AGENT_DIR` set at the time the extension loads?

---

## 3. Critical Design Decision: Agent Directory Isolation

### 3.1 The Problem

The host's `~/.pi/agent/` contains the user's global pi configuration:
- Extensions installed via `pi install`
- Skills in `~/.pi/agent/skills/`
- Settings in `~/.pi/agent/settings.json`
- Sessions, credentials, API keys

If this directory is mounted into the container and used as
`PI_CODING_AGENT_DIR`, then:
1. pi's `packageManager.resolve()` auto-discovers extensions from
   `~/.pi/agent/extensions/` and merges them with the bundled ones.
2. Skills from `~/.pi/agent/skills/` are auto-discovered and loaded.
3. The launcher writes `quietStartup: true` and `lastChangelogVersion` into the
   host's `settings.json`, polluting it.
4. The user's global pi (when used outside the container) would see
   `quietStartup: true` and the stamped `lastChangelogVersion`.

### 3.2 The Solution

**Assumption:** Instead of mounting `~/.pi/agent/`, we create a separate
persistent directory `~/.pi/agent-little-coder/` that acts as the "little-coder
global dir."

**Implementation:**
1. **Dockerfile:** Copies the bundled `.pi/` and `models.json` to `/pi-agent/`
   (container-local, writable). Sets `ENV PI_CODING_AGENT_DIR=/pi-agent`.
2. **_docker_flags:** Mounts `~/.pi/agent-little-coder:/pi-agent` from the host.
   Seeds the directory from `vendor/little-coder/.pi/` on first run.
3. **Launcher:** Reads `PI_CODING_AGENT_DIR` from env (now `/pi-agent`), writes
   settings to `/pi-agent/settings.json` (writable via mount).

### ⚠️ Needs Verification:

- **Does `PI_CODING_AGENT_DIR=/pi-agent` in the Dockerfile actually get passed
  to the container at runtime?** The `ENV` directive sets it at build time, but
  the `_docker_flags` script also sets it via `--env`. Do they conflict? (They
  shouldn't — `--env` overrides `ENV` at runtime.)

- **Does the launcher's `mkdirSync(agentDir, { recursive: true })` work when
  `agentDir` is a mount point?** The mount is created by Docker, not by the
  launcher. If the mount fails (e.g., `~/.pi/agent-little-coder/` doesn't exist
  on the host), Docker will auto-create it as root, potentially breaking file
  ownership.

- **Does `cp -a` preserve permissions correctly?** The seed uses `cp -a` to
  copy the bundled `.pi/` into `~/.pi/agent-little-coder/`. If the host
  directory is created by Docker as root, the cp might fail due to permissions.

- **What happens to `/pi-agent/npm-global/`?** The `.npmrc` sets
  `prefix=/pi-agent/npm-global`. When the user runs `pi install` from inside
  the container, packages are installed to `/pi-agent/npm-global/`, which is the
  mounted directory. This means installed packages persist on the host. **But:**
  if the user rebuilds the container, the mount would overwrite the container's
  `/pi-agent/` — including any installed packages. **This is likely acceptable**
  since the user's `~/.pi/agent-little-coder/npm-global/` would survive the
  rebuild. **⚠️ Needs verification.**

- **Does the llama-cpp-provider extension find `models.json` at
  `PI_CODING_AGENT_DIR/models.json`?** The extension checks this path in
  `resolveOverridePath()`. On first run, the seeded `models.json` is at
  `~/.pi/agent-little-coder/models.json`. On subsequent runs, the mount provides
  it. **⚠️ Needs verification that the extension loads AFTER `PI_CODING_AGENT_DIR`
  is set.**

---

## 4. Extension Loading

### 4.1 How Little-Coder Loads Extensions

The launcher (step 4) scans `pkgRoot/.pi/extensions/` and passes each extension's
`index.ts` as an explicit `--extension` flag to pi:

```javascript
const extArgs = [];
if (existsSync(extDir)) {
  for (const name of readdirSync(extDir).sort()) {
    const subdir = join(extDir, name);
    const idx = join(subdir, "index.ts");
    if (statSync(subdir).isDirectory() && existsSync(idx)) {
      extArgs.push("--extension", idx);
    }
  }
}
```

Then pi is invoked with `--no-extensions`, which tells pi to skip auto-discovery
of extensions from `PI_CODING_AGENT_DIR/extensions/` and `cwd/.pi/extensions/`.
Only the explicitly passed `--extension` flags are loaded.

### ⚠️ Needs Verification:

- **Are all 23 extensions discovered?** The `readdirSync` sorts alphabetically.
  If an extension's `index.ts` is in a subdirectory that doesn't match the
  expected structure, it won't be loaded.

- **Does `--no-extensions` prevent ALL auto-discovery?** The pi resource-loader
  code shows:
  ```javascript
  const extensionPaths = this.noExtensions
      ? cliEnabledExtensions
      : this.mergePaths(cliEnabledExtensions, enabledExtensions);
  ```
  When `noExtensions` is true, `enabledExtensions` (from auto-discovery) is
  completely ignored. **This is correct.** But **⚠️ needs verification** that
  `noExtensions` doesn't also prevent `additionalExtensionPaths` from being
  loaded.

- **What about extensions installed via `pi install`?** These would be listed in
  `globalSettings.packages`. With `--no-extensions`, they are NOT loaded.
  **This is the desired behavior** — the user's global extensions don't leak
  into the container.

---

## 5. Skill Loading

### 5.1 How Skills Are Loaded

The launcher does **NOT** pass `--no-skills`. This means pi's resource-loader
will auto-discover skills from:
- `PI_CODING_AGENT_DIR/skills/`
- `cwd/.pi/skills/`
- `~/.agents/skills/`
- `cwd/.agents/skills/` and ancestors

Since `PI_CODING_AGENT_DIR=/pi-agent` (mounted from `~/.pi/agent-little-coder/`),
skills would be discovered from `~/.pi/agent-little-coder/skills/`.

**The bundled little-coder skills are in `skills/` at the package root, NOT in
`.pi/skills/`.** They are NOT loaded through auto-discovery.

### ⚠️ Needs Verification:

- **Are the little-coder bundled skills loaded at all?** The `skills/` directory
  contains markdown files like `bash.md`, `browser_click.md`, etc. These are NOT
  in `.pi/skills/` and are NOT passed via `--skill` flags. **They may not be
  loaded.** If they're meant to be used, the launcher needs to pass `--skill`
  flags for each one, or they need to be in `.pi/skills/`.

- **Would host skills from `~/.pi/agent/skills/` be loaded?** No — because
  `PI_CODING_AGENT_DIR` points to `~/.pi/agent-little-coder/`, not
  `~/.pi/agent/`. The host's skills directory is never mounted. **This is
  correct.**

- **Would skills from `~/.agents/skills/` be loaded?** This is a separate
  directory that the resource-loader checks independently of
  `PI_CODING_AGENT_DIR`. If the user has skills there, they WOULD be loaded.
  **⚠️ Needs verification whether this is desired.**

---

## 6. Settings Persistence

### 6.1 What the Launcher Writes

The launcher (step 8) reads `PI_CODING_AGENT_DIR/settings.json`, then writes:
1. `quietStartup: true` — suppresses the [Extensions]/[Skills]/[Prompts] inventory
2. `lastChangelogVersion: <bundled pi version>` — suppresses pi's "What's New"

### ⚠️ Needs Verification:

- **Does the launcher successfully write to `/pi-agent/settings.json`?** The
  mount is from the host's `~/.pi/agent-little-coder/`. If the directory doesn't
  exist on the host, Docker auto-creates it as root, and the container's
  non-root user can't write to it. **The `_docker_flags` script creates the
  directory with `mkdir -p`, so it should be owned by the user.** **⚠️ Needs
  verification that `mkdir -p` in the mise task creates the directory with the
  correct ownership.**

- **Does `quietStartup: true` in the bundled `settings.json` make the launcher's
  write redundant?** The bundled `settings.json` already has `quietStartup: true`.
  The launcher reads the file, sees `quietStartup` is already `true`, and doesn't
  mutate it. **This means the write is a no-op on first run.** On subsequent
  runs, if the user removes `quietStartup: true`, the launcher would re-add it.
  **This is correct behavior.**

- **Does `lastChangelogVersion` suppress the changelog correctly?** The launcher
  writes the bundled pi version. Pi checks `lastChangelogVersion` against its
  bundled changelog entries and only shows entries strictly newer than the stored
  version. **⚠️ Needs verification that the bundled pi version in the container
  matches the version in `lastChangelogVersion`.**

---

## 7. Build Context and `.dockerignore`

### 7.1 What's Excluded

The `.dockerignore` excludes:
- `.git` directories (both root and nested)
- `node_modules` (both root and nested)
- `*.log`, `.env`, `.env.*`
- mise files

### ⚠️ Needs Verification:

- **Is the build context small enough?** The vendor/little-coder/ directory is
  ~3.3MB. Excluding `node_modules` and `.git` keeps it small. **⚠️ Needs
  verification that the actual build context size is acceptable.**

- **Does `.gitignore` at the repo root affect Docker build context?** No —
  `.gitignore` is for Git, not Docker. The `.dockerignore` is what Docker uses.
  **This is correct.**

---

## 8. Update Check Behavior

### 8.1 The Flow

1. Launcher resolves the package root and reads the version from `package.json`.
2. `checkForUpdate(currentVersion)` is called.
3. `shouldSkip()` checks `PI_SKIP_VERSION_CHECK` and `LITTLE_CODER_NO_UPDATE_CHECK`.
4. If not skipped, it fetches the latest version from npm and prompts the user.

### ⚠️ Needs Verification:

- **Does `checkForUpdate()` actually check `PI_SKIP_VERSION_CHECK`?** The original
  `shouldSkip()` only checked `LITTLE_CODER_NO_UPDATE_CHECK`. The fix added
  `PI_SKIP_VERSION_CHECK` to `shouldSkip()`. **⚠️ Needs verification that the
  fix was applied correctly and that `shouldSkip()` is called from the right
  place.**

- **Is the env var set before `checkForUpdate()` runs?** The launcher sets
  `PI_SKIP_VERSION_CHECK=1` in the launcher code. **⚠️ Needs verification that
  this happens before `checkForUpdate()` is called.** (The original code set it
  in step 7, after `checkForUpdate()` in step 5.)

- **Does `PI_SKIP_VERSION_CHECK` affect anything other than the update banner?**
  The comment says it's a "surgical pi switch" that gates the "Update Available"
  banner. **⚠️ Needs verification that it doesn't affect other network-dependent
  startup paths.**

---

## 9. Network and Local Models

### 9.1 `PI_LOCAL_MODELS=1`

When set, the container uses `--network=host`, making local model servers
(Ollama, LM Studio, vLLM) reachable at their native localhost URLs.

### ⚠️ Needs Verification:

- **Does `--network=host` work on all platforms?** On Linux, yes. On macOS with
  Docker Desktop, `--network=host` uses the Docker Desktop VM network, not the
  Mac's network. localhost services on the Mac are NOT reachable. **The comment
  in `_docker_flags` mentions this.** **⚠️ Needs verification on the user's
  specific platform.**

- **Does the llama-cpp-provider extension correctly resolve localhost URLs?**
  The extension reads `baseUrl` from `models.json`. If the URL is
  `http://localhost:8080`, it would resolve to the host's localhost (with
  `--network=host`). **⚠️ Needs verification that the extension handles
  localhost URLs correctly.**

---

## 10. SSH Agent Forwarding

### 10.1 `PI_SSH_AGENT=1`

When set, the container forwards the host's SSH agent socket and mounts
`~/.ssh/known_hosts` and `~/.ssh/config` read-only.

### ⚠️ Needs Verification:

- **Does SSH work inside the container?** The container has `openssh-client`
  installed. The runtime user has a `/etc/passwd` entry. **⚠️ Needs verification
  that SSH authentication works.**

- **Does `known_hosts` mounting work with the non-root UID?** The container
  user is `--user $(id -u):$(id -g)`. The `known_hosts` file is mounted read-only.
  **⚠️ Needs verification that the non-root user can read the mounted file.**

---

## 11. Miscellaneous

### 11.1 `mise` Version Pinning

The Dockerfile pins `MISE_VERSION=2026.5.6`. This is a specific version that may
not be available on the npm registry or may have changed.

**⚠️ Needs Verification:** Is `2026.5.6` a valid mise version?

### 11.2 Node.js Version

The launcher checks for Node.js >= 22.19.0. The Dockerfile uses
`cgr.dev/chainguard/node:latest-dev`, which should have a recent Node version.

**⚠️ Needs Verification:** Does `chainguard/node:latest-dev` have Node >= 22.19.0?

### 11.3 Python Version

The Dockerfile installs Python 3.14.4 via `uv`. This is a very new version that
may have compatibility issues with some tools.

**⚠️ Needs Verification:** Is Python 3.14.4 stable enough for the intended use
cases?

### 11.4 Chainguard/Wolfi Package Availability

The Dockerfile uses `apk add` to install packages. Some packages may not be
available in the Wolfi repository.

**⚠️ Needs Verification:** Are all required packages (curl, ca-certificates, git,
openssh-client, tmux) available in the Chainguard/Wolfi repository?

---

## 12. Summary of Unverified Assumptions

| # | Assumption | Impact if Wrong |
|---|-----------|-----------------|
| 1 | `npm install -g .` installs `little-coder` globally with correct entry point | Container runs `pi` instead of `little-coder` |
| 2 | `shouldSkip()` checks `PI_SKIP_VERSION_CHECK` | Update prompt appears on every run |
| 3 | `PI_CODING_AGENT_DIR` is set before extension loading | Extensions may not find `models.json` |
| 4 | `~/.pi/agent-little-coder/` is created with correct ownership | Launcher can't write settings |
| 5 | Bundled skills in `skills/` are loaded (via `--skill` flags or otherwise) | Skills are missing from the session |
| 6 | `--no-extensions` doesn't prevent `additionalExtensionPaths` loading | Additional extensions may not load |
| 7 | `cp -a` preserves permissions for the seed operation | First-run seed fails |
| 8 | `PI_LOCAL_MODELS=1` works on the user's platform | Local model servers unreachable |
| 9 | Chainguard/Wolfi has all required packages | Docker build fails |
| 10 | Node.js >= 22.19.0 in `chainguard/node:latest-dev` | Launcher exits with version error |
| 11 | `playwright install chromium` works on Wolfi | Browser tools fail silently |
| 12 | `lastChangelogVersion` suppresses pi's changelog correctly | Changelog appears on every run |

---

## 13. Recommended Verification Steps

1. **Build the image:** `./build-container.sh`
2. **Run health check:** `mise run pi:health`
3. **Run a simple test:** `mise run pi -- "Hello, world"`
4. **Verify extensions load:** Check the TUI for the expected extensions
5. **Verify skills load:** Check the TUI for the expected skills
6. **Verify settings write:** Check `~/.pi/agent-little-coder/settings.json`
7. **Verify models load:** Check that the llama-cpp-provider finds `models.json`
8. **Verify no host pollution:** Check that `~/.pi/agent/` is untouched

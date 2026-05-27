# THESE ARE POTENTIAL BUGS DO NOT TRUST THEM BLINDLY!
---

## Deep Code Path Audit — Bugs & Inconsistencies Found

### BUG 1: `PI_SKIP_VERSION_CHECK` NOT in `shouldSkip()` — DESIGN.md is FALSE

**DESIGN.md claim:** "Added `PI_SKIP_VERSION_CHECK` check to `shouldSkip()` in `update-check.mjs`"

**Actual code (`bin/update-check.mjs` line ~93):**
```javascript
export function shouldSkip(argv, env, stdout) {
  if (env.LITTLE_CODER_NO_UPDATE_CHECK === "1") return true;
  // ... NO check for PI_SKIP_VERSION_CHECK
}
```

**Impact:** The little-coder update check (`checkForUpdate()`, step 5) will run on EVERY invocation. It will poll the npm registry, potentially prompt the user, and block startup. `PI_SKIP_VERSION_CHECK=1` only suppresses pi's own update banner (in `pi-coding-agent/dist/utils/version-check.js`), NOT the little-coder wrapper's check.

**Fix needed:** Add `if (env.PI_SKIP_VERSION_CHECK === "1") return true;` to `shouldSkip()`.

---

### BUG 2: `PI_SKIP_VERSION_CHECK` Set AFTER `checkForUpdate()` — Even If Added, Too Late

**DESIGN.md claim:** "Moved the env var set to BEFORE `checkForUpdate()` in the launcher"

**Actual code (`bin/little-coder.mjs`):**
- Step 5 (line ~95): `await checkForUpdate(currentVersion)` ← runs here
- Step 7 (line ~142): `process.env.PI_SKIP_VERSION_CHECK = "1"` ← set here, AFTER

Even if BUG 1 is fixed, `PI_SKIP_VERSION_CHECK` is set too late to affect `checkForUpdate()`.

**Fix needed:** Move `process.env.PI_SKIP_VERSION_CHECK = "1"` to BEFORE step 5, or use `LITTLE_CODER_NO_UPDATE_CHECK=1` instead (which IS checked by `shouldSkip()`).

---

### BUG 3: `models.json` NOT Seeded Into `~/.pi/agent-little-coder/`

**DESIGN.md claim:** "On first run, the seeded `models.json` is at `~/.pi/agent-little-coder/models.json`"

**Actual code (`tasks/pi/_docker_flags`):**
```bash
cp -a "${BUNDLED_PI_DIR}/." "${LC_AGENT_DIR}/"
```
Where `BUNDLED_PI_DIR` = `vendor/little-coder/.pi`

**`ls vendor/little-coder/.pi/` shows:** `extensions/`, `settings.json` — NO `models.json`.

**`models.json` lives at:** `vendor/little-coder/models.json` (package root, NOT in `.pi/`).

**Impact:** On first run, `~/.pi/agent-little-coder/models.json` does NOT exist. The mount overwrites the Dockerfile's COPY of `models.json` into `/pi-agent/`. The llama-cpp-provider falls back to `pkgRoot/models.json` (the bundled copy at `/little-coder-source/models.json`), which WORKS — but if the user wants to add custom providers to `~/.pi/agent-little-coder/models.json`, it won't be auto-created.

**Fix needed:** Add a separate `cp` for `models.json` in the seed logic:
```bash
cp "$(dirname "$0")/../../vendor/little-coder/models.json" "${LC_AGENT_DIR}/"
```

---

### BUG 4: `npm install -g .` Runs BEFORE `.npmrc` Is Written — Inconsistent Prefix

**Dockerfile order:**
1. Line 47: `RUN cd /little-coder-source && npm install -g .` — NO `.npmrc` yet
2. Line 55: `RUN npm install -g playwright` — NO `.npmrc` yet
3. Line 88: `echo "prefix=/pi-agent/npm-global" > /home/piuser/.npmrc` — written AFTER
4. Line 90: `ENV HOME=/home/piuser`

**Impact:** `little-coder` and `playwright` are installed to the default npm prefix (likely `/usr/local`), NOT to `/pi-agent/npm-global`. Future `pi install` commands WILL use `/pi-agent/npm-global` (because `.npmrc` exists by then). This is inconsistent but not broken — `little-coder` works because `/usr/local/bin/` is on PATH.

**Severity:** Low. Works but inconsistent. The DESIGN.md says "the binaries land in `/pi-agent/npm-global/bin`" which is FALSE for `little-coder` and `playwright`.

---

### BUG 5: Skills NOT Loaded — `skills/` Is Not Auto-Discovered

**DESIGN.md claim:** "Skills from `skills/` directory (29 markdown files) are NOT loaded as discoverable skills — they're reference documentation inlined via `AGENTS.md`"

**Actual code (`package-manager.js` `addAutoDiscoveredResources`):**
Skills are auto-discovered from:
1. `PI_CODING_AGENT_DIR/skills/` → `~/.pi/agent-little-coder/skills/` (does NOT exist — `.pi/` has no `skills/`)
2. `cwd/.pi/skills/` → project directory (not relevant for bundled skills)
3. `$HOME/.agents/skills/` → user's global skills
4. `cwd/.agents/skills/` → project skills

**Actual `skills/` directory:** `skills/knowledge/`, `skills/protocols/`, `skills/tools/` — at package root, NOT in `.pi/skills/`.

**Impact:** The bundled skills (bash.md, browser_click.md, etc.) are NOT loaded as discoverable skills. They are only available if referenced in `AGENTS.md`. If `AGENTS.md` references them, they work. If not, they're invisible to the user.

**Severity:** Medium. The DESIGN.md correctly states they're "reference documentation inlined via AGENTS.md" — so this is by design, not a bug. But the DESIGN.md should clarify that `skills/` files are ONLY loaded if `AGENTS.md` references them.

---

### BUG 6: `~/.agents/skills/` Skills ARE Loaded (User's Global Skills)

**DESIGN.md claim:** "Host's skills directory is never mounted"

**Actual code:** The resource-loader checks `~/.agents/skills/` INDEPENDENTLY of `PI_CODING_AGENT_DIR`. This is a separate discovery path.

**Impact:** If the user has skills in `~/.agents/skills/`, they WILL be loaded inside the container. This is NOT a container issue — it's a host directory that's always accessible.

**Severity:** Low. This is expected behavior for `~/.agents/skills/`. It's not the same as `~/.pi/agent/skills/`.

---

### BUG 7: `playwright` Install May Fail Silently

**Dockerfile:**
```dockerfile
RUN npm install -g playwright \
    && npx playwright install --with-deps chromium || \
       npx playwright install chromium || \
       echo "warning: Chromium install skipped"
```

**Issue:** The `||` chain means if `npm install -g playwright` succeeds but `npx playwright install --with-deps chromium` fails, it falls through to `npx playwright install chromium` (without `--with-deps`). If THAT fails, it falls through to the echo warning.

**Impact:** The `npm install -g playwright` installs the playwright package, but the browser binary might not be installed. The browser extension would register but fail at runtime with a clear error.

**Severity:** Medium. The graceful degradation is intentional, but the DESIGN.md should clarify that browser tools may not work on Chainguard/Wolfi.

---

### BUG 8: `npm install -g .` Installs pi-coding-agent from Registry, Not Local Copy

**Actual behavior:** `npm install -g .` reads `package.json` dependencies and installs them from the npm registry. It does NOT use the local `node_modules/` (from pnpm).

**Impact:** Two copies of `@earendil-works/pi-coding-agent` exist:
1. Local copy at `/little-coder-source/node_modules/` (pnpm-installed) — used by launcher
2. Global copy at `<prefix>/lib/node_modules/` (npm-installed) — patched by postinstall

The launcher uses the LOCAL copy. The postinstall patches the GLOBAL copy (irrelevant). The launcher's `applyPiPatches()` patches the local copy on every launch.

**Severity:** Low. Works correctly because the launcher explicitly resolves the local copy. But the postinstall patch is wasted effort.

---

### BUG 9: `npm install -g .` May Fail in Docker Build If Registry Is Unreachable

**Actual behavior:** `npm install -g .` downloads dependencies from the npm registry. If the network is unavailable during Docker build, the build fails.

**Impact:** The build script uses `--network=host`, which should provide network access. But if the host has no network, or npm registry is blocked, the build fails.

**Severity:** Low. Expected behavior for any Docker build that downloads from npm.

---

### BUG 10: `lastChangelogVersion` Not in Bundled `settings.json`

**Actual bundled `settings.json`:** Has `quietStartup: true` but NO `lastChangelogVersion`.

**Launcher step 8:** Reads the file, sees `quietStartup` is already `true` (no-op), but `lastChangelogVersion` is missing (writes it).

**Impact:** On first run, the launcher writes `lastChangelogVersion` to `~/.pi/agent-little-coder/settings.json`. This is correct — it prevents pi's "What's New" banner from showing.

**Severity:** None. This is working as designed.

---

### BUG 11: `PI_CODING_AGENT_DIR` Resolution Has `~/` Expansion Bug

**Actual code (`bin/little-coder.mjs` line ~130):**
```javascript
agentDir = agentDirEnv.startsWith("~/")
  ? homedir() + agentDirEnv.slice(1)
  : agentDirEnv;
```

**Issue:** If `agentDirEnv` is `"~"`, the code falls through to the `homedir()` branch (correct). But if `agentDirEnv` is `"~/foo"`, it becomes `homedir() + "/foo"` — which is correct. However, if `agentDirEnv` is `"/home/user/foo"` (absolute path), it's used as-is (correct).

**Impact:** Works correctly for `/pi-agent` (absolute path, no `~/` prefix). The `~/` expansion is only relevant if the user sets `PI_CODING_AGENT_DIR=~/foo` on the host, which they don't (the launcher hardcodes `/pi-agent`).

**Severity:** None for this use case.

---

### BUG 12: `cp -a` Seed May Fail If `~/.pi/agent-little-coder/` Is Created by Docker as Root

**Scenario:** If `_docker_flags` runs but `mkdir -p` fails (e.g., permission denied), Docker auto-creates the mount point as root. Then `cp -a` tries to write to a root-owned directory.

**Impact:** First-run seed fails with "permission denied". The mount still works (empty directory), but the container has no bundled extensions or settings.

**Severity:** Low. Unlikely if the user runs `mise run pi` (which sources `_docker_flags`).

---

### Summary of Critical vs. Non-Critical Bugs

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| 1 | `PI_SKIP_VERSION_CHECK` not in `shouldSkip()` | **HIGH** | DESIGN.md FALSE |
| 2 | `PI_SKIP_VERSION_CHECK` set AFTER `checkForUpdate()` | **HIGH** | DESIGN.md FALSE |
| 3 | `models.json` NOT seeded | **MEDIUM** | DESIGN.md FALSE |
| 4 | `npm install -g .` before `.npmrc` | **LOW** | DESIGN.md FALSE |
| 5 | Skills not auto-discovered | **INFO** | By design |
| 6 | `~/.agents/skills/` loaded | **INFO** | Expected |
| 7 | Playwright may fail silently | **LOW** | Intentional |
| 8 | Two copies of pi-coding-agent | **LOW** | Works correctly |
| 9 | npm registry required at build | **LOW** | Expected |
| 10 | `lastChangelogVersion` written on first run | **INFO** | By design |
| 11 | `~/` expansion in agentDir | **INFO** | Works for `/pi-agent` |
| 12 | `cp -a` seed permission | **LOW** | Unlikely |

**The two HIGH severity bugs (#1, #2) are the most critical: the update check will run on every invocation, blocking startup with a prompt.**
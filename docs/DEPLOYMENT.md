# PERCH — running and shipping it

Four ways to run PERCH, from "I'm working on it" to "someone else installs it". Everything below is
Windows 10/11, x64 — the OS layer (UI Automation, global hotkeys, WebView2, Windows OCR) is Windows by
design.

| | For | What you get |
|---|---|---|
| **1. From source** | development | `python -m app`, live code, the browser mock for UI work |
| **2. Portable build** | trying it on another machine, USB stick | a `PERCH` folder with `PERCH.exe`, no install |
| **3. Installer** | normal users | `PERCH-Setup-<version>.exe`: Start menu, uninstaller, start-at-sign-in |
| **4. CI release** | publishing | tag a version, GitHub builds 2 and 3 and attaches them to a release |

---

## What every machine needs

| | Why | How |
|---|---|---|
| **WebView2 Runtime** | the window is WebView2 (the Edge engine) | preinstalled on Windows 11. Windows 10: Microsoft's *Evergreen Bootstrapper* |
| **Ollama** | local models: answers and memory search | [ollama.com](https://ollama.com) — then leave it running |
| **Two models** | `qwen2.5:3b` answers, `nomic-embed-text` finds memories | PERCH's **Home → Setup** has a *Download* button for each; or `ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text` |
| An OCR language | reading screenshots on-device | Windows Settings → Time & language → Language → add a language with OCR (English has it) |

Nothing else. Without Ollama PERCH still opens and routes, ranks and gates — it just cannot generate,
and says so in a banner. Without `nomic-embed-text` it falls back to a keyword embedder and warns that
recall is degraded. **Home → Setup** checks all of this and says how to fix each item.

---

## 1. From source

```bash
pip install -r requirements.txt
python -m app seed          # optional: a small demo memory
python -m app               # tray icon + shortcuts
python -m app open          # ... and open the full view
```

`run_perch.pyw` does the same with no console window (logs: `%USERPROFILE%\.perch\logs\perch.log`).

**Working on the UI:** the frontend runs in a normal browser against a fake backend.

```bash
python -m http.server 5178 --directory app/ui/web
```

Then open `http://127.0.0.1:5178/index.html?mock&mode=expanded`. Useful parameters: `view=memory`,
`ctx=screenshot|plain|empty`, `setup=todo` (shows a missing model on Home).

## 2. Portable build

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

`dist\PERCH\` is the whole app — copy the folder anywhere and run `PERCH.exe`. The script also writes
`dist\PERCH-portable-<version>.zip`. It is a *one-folder* build on purpose: a one-file exe unpacks
itself to a temp directory on every launch, which is slow for something that starts at sign-in and
upsets antivirus heuristics far more often.

`PERCH.exe` accepts the same arguments as `python -m app`: `PERCH.exe open`, `PERCH.exe eval e3`, …
(output goes to the log, since the exe has no console).

## 3. Installer

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`), then
run the same `build.ps1` — it finds `ISCC.exe` and writes `dist\PERCH-Setup-<version>.exe`.

The installer:

- installs **per user**, into `%LOCALAPPDATA%\Programs\PERCH` — **no admin rights**, no UAC prompt
- adds **PERCH** to the Start menu (and optionally the desktop)
- optionally **starts PERCH at sign-in**, using the same registry value the Settings toggle writes, so
  the two never disagree
- installs over an older version in place; your memory is untouched
- **uninstalls cleanly** from *Settings → Apps* — and leaves `%USERPROFILE%\.perch` alone, because that
  folder is your memory, not the program. Delete it yourself if you want it gone.

## 4. CI release

`.github/workflows/release.yml` builds on GitHub's Windows machines:

```bash
git tag v0.8.0
git push origin v0.8.0
```

The workflow installs dependencies, **runs the test suite** (a release is never built from a red
suite), builds the portable zip and the installer, and attaches both to the GitHub release for the tag.
*Actions → Build Windows release → Run workflow* builds without publishing.

---

## Before handing it to other people

- **Code signing.** An unsigned installer triggers Windows SmartScreen (*"Windows protected your
  PC"* → *More info → Run anyway*). To avoid it, sign `dist\PERCH\PERCH.exe` and the Setup exe with
  `signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a <file>` using a code-signing
  certificate, before and after running Inno Setup respectively. SmartScreen reputation also builds
  up with downloads over time.
- **Bump the version** in `app/config.py` (`APP_VERSION`) — the build, the installer name and the
  About screen all read it.
- **Refit the floors if you change the embedding model**: `python -m app eval e3`. The floors in
  `app/memory/classes.py` were fitted for `nomic-embed-text`; the index re-embeds itself on a model
  change, but the floors do not refit themselves.

## Configuration

Environment variables, for power users and CI. The Settings screen covers the everyday ones and shows
when a value is pinned by the environment.

| Variable | Default | |
|---|---|---|
| `PERCH_HOME` | `%USERPROFILE%\.perch` | where memory, conversations, logs and settings live |
| `PERCH_OLLAMA` | `http://127.0.0.1:11434` | Ollama's address (use 127.0.0.1, not localhost — see config.py) |
| `PERCH_LOCAL_MODEL` | `qwen2.5:3b` | the answer model |
| `PERCH_EMBED_MODEL` | `nomic-embed-text` | the memory-search model |
| `PERCH_NUM_CTX` | `8192` | the context window requested from Ollama |
| `PERCH_API_BASE`, `PERCH_API_KEY`, `PERCH_API_MODEL` | — | an OpenAI-compatible cloud route |
| `PERCH_ROUTE` | `auto` | `auto`, `local` or `cloud` |
| `PERCH_PRIVATE_DEFAULT` | `0` | `1` = every request private unless switched off |
| `PERCH_HOTKEY_SELECTION` / `_SCREENSHOT` / `_PLAIN` | `ctrl+alt+j` / `k` / `g` | global shortcuts |
| `PERCH_DEBUG` | — | `1` opens WebView2 dev tools |

## Troubleshooting

| Symptom | Look at |
|---|---|
| No tray icon after launch | `%USERPROFILE%\.perch\logs\perch.log` |
| "PERCH is already running" | it is — look in the tray (the ^ arrow). One instance at a time, by design |
| A shortcut does nothing | another app owns it. **Home → Setup → Global shortcuts** names which; `python -m app hotkeys` lists free ones |
| Answers are stubbed | Ollama isn't running. Start it, then **Home → Re-check** |
| "Fallback embeddings" banner | `nomic-embed-text` isn't installed — **Home → Setup → Download** |
| Window is blank | WebView2 Runtime missing (Windows 10) |

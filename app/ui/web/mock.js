"use strict";
/*
 * A fake bridge for developing the UI in a plain browser: open
 * index.html?mock (add &mode=expanded, &view=memory, &ctx=screenshot|plain|empty).
 * Loaded only when there is no pywebview -- never in the app.
 */
(function () {
  const params = new URLSearchParams(location.search);
  const classes = [
    { name: "identity", holds: "who you are, how you want answers written, standing instructions", floor: 0.2, private: false, cap: 40 },
    { name: "project", holds: "bounded work: purpose, stack, decisions, problems, timeline, results", floor: 0.3, private: false, cap: 400 },
    { name: "academic", holds: "institution, semester, subjects, formats, deadlines, conventions", floor: 0.3, private: false, cap: 400 },
    { name: "career", holds: "roles, skills, applications, interviews, targets", floor: 0.3, private: false, cap: 400 },
    { name: "health", holds: "conditions, medications, allergies, appointments, reports", floor: 0.42, private: true, cap: 200 },
    { name: "personal", holds: "relationships, preferences, finances, travel, home, commitments", floor: 0.38, private: true, cap: 400 },
  ];
  let memory = [
    { id: "i1", cls: "identity", title: "Who I am and how I want answers written", body: "Final-year Computer Engineering student at PES Modern College of Engineering, Pune. Writes plainly and dislikes padding. Prefers British spelling.", tags: ["voice", "style"], updated: "2026-09-07", uses: 4, source: "manual", private: false },
    { id: "p1", cls: "project", title: "Async context bug in the capture worker", body: "The panel froze whenever a model call took more than a second, because the request ran on the tkinter main thread. Fixed by moving the pipeline into a worker thread.", tags: ["perch", "bug", "threading"], updated: "2026-09-02", uses: 2, source: "import", platform: "claude", private: false },
    { id: "p2", cls: "project", title: "Selection capture falls back to the clipboard", body: "UI Automation cannot read the selection in every app — Electron apps often do not implement TextPattern. The fallback is a clipboard round-trip with a sentinel.", tags: ["perch", "uiautomation"], updated: "2026-08-14", uses: 0, source: "manual", private: false },
    { id: "a1", cls: "academic", title: "College, course and campus", body: "B.E. Computer Engineering, PES Modern College of Engineering, Pune, under SPPU. Final year, semester seven. The campus shares its road with the group's medical college.", tags: ["college", "sppu"], updated: "2026-08-20", uses: 1, source: "manual", private: false },
    { id: "c1", cls: "career", title: "What I am targeting after graduation", body: "Backend and applied-ML roles. Strongest in Python, picking up Rust. Pune or remote for the first role.", tags: ["placement", "backend"], updated: "2026-08-30", uses: 0, source: "import", platform: "chatgpt", private: false },
    { id: "s1", cls: "personal", title: "Standing constraints", body: "Vegetarian. Keeps weekday evenings free for project work. Travel budget for the year is tight.", tags: ["schedule", "budget"], updated: "2026-08-10", uses: 0, source: "manual", private: true },
  ];
  const events = [];
  const counts = () => memory.reduce((a, m) => ((a[m.cls] = (a[m.cls] || 0) + 1), a), {});
  const status = () => ({
    model: { label: "qwen2.5:3b (local, 8192 tok)", id: "qwen2.5:3b", local: true, stub: false, vision: false, tools: true, window: 8192 },
    embeddings: "ollama", semantic: true, memory: memory.length, counts: counts(), warnings: [],
  });
  const ctxs = {
    selection: { kind: "selection", selection: "def run(self, req):\n    result = self._gate(req, trace, stage)\n    model = registry.select(private=decision.private)\n    # the panel still freezes when the model is slow", method: "uia", source_title: "pipeline.py — perch — Visual Studio Code", source_app: "code", app_label: "VS Code", has_host: true },
    screenshot: { kind: "screenshot", selection: "Traceback (most recent call last):\n  File \"main.py\", line 42\nConnectionRefusedError: [WinError 10061]", method: "screenshot", ocr: { chars: 96, ms: 238 }, source_title: "", app_label: "", has_host: false, thumb: "" },
    plain: { kind: "plain", has_host: true, source_title: "Inbox — Outlook", app_label: "Outlook", source_app: "olk" },
    empty: { kind: "app", has_host: false },
  };
  const trace = (q) => {
    const medical = /doctor|medic/i.test(q);
    const admitted = medical ? [] : [
      { id: "p1", cls: "project", title: "Async context bug in the capture worker", score: 0.35, floor: 0.3, private: false, reason: "score 0.35 >= cutoff 0.30" },
      { id: "i1", cls: "identity", title: "Who I am and how I want answers written", score: 0.24, floor: 0.2, private: false, reason: "score 0.24" },
    ];
    const dropped = [
      { id: "p2", cls: "project", title: "Selection capture falls back to the clipboard", score: 0.24, floor: 0.3, private: false, reason: "below class margin (0.244 < 0.300)" },
      { id: "a1", cls: "academic", title: "College, course and campus", score: medical ? 0.21 : 0.12, floor: 0.3, private: false, reason: `class below floor (${medical ? 0.21 : 0.12} < 0.30)` },
      { id: "s1", cls: "personal", title: "Standing constraints", score: 0.08, floor: 0.38, private: true, reason: "class below floor (0.080 < 0.38)" },
    ];
    const segs = [
      { kind: "system", label: "instructions", tokens: 281 },
      { kind: "selection", label: "your selection", tokens: 64 },
      ...admitted.map((a) => ({ kind: "memory", label: a.title, cls: a.cls, tokens: a.cls === "project" ? 88 : 74 })),
      { kind: "question", label: "your question", tokens: 14 },
    ];
    return {
      intent: "eligible: project, identity", eligible: medical ? ["health", "identity", "academic"] : ["project", "identity"], candidates: 7,
      admitted, dropped, rejected_classes: {}, abstained: medical, privacy: "cloud allowed", private: false,
      model: "qwen2.5:3b (local, 8192 tok)", vision: "", tools: [], ms: 1840,
      ledger: { budget: 6068, window: 8192, used: segs.reduce((a, s) => a + s.tokens, 0), segments: segs },
    };
  };
  const answer = (q) => /doctor|medic/i.test(q)
    ? "I don't have anything stored about your health, so this is general advice.\n\n- **What is it for?** Ask what the medication treats and how you'll know it's working.\n- **Side effects** — which are common, and which mean you should call.\n- **Interactions** with anything else you take, including supplements."
    : "It freezes because the model call runs **on the UI thread**, so nothing repaints until it returns.\n\nYou hit this on 16 August and fixed it the same way you should here:\n\n```python\nthreading.Thread(target=work, daemon=True).start()\n# marshal the result back\nroot.after(0, lambda: self._show(response))\n```\n\nThe rule from then still holds: *one root, one loop, and never block it.*";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function simulate(rid, q) {
    const stages = [["route", "project, identity"], ["rank", "7 candidates"], ["gate", /doctor|medic/i.test(q) ? "abstained" : "2 in, 3 out"], ["pack", "413/6068 tok"], ["model", "qwen2.5:3b"]];
    for (const [name, detail] of stages) { await sleep(180); events.push({ type: "stage", rid, name, detail }); }
    const words = answer(q).split(/(\s+)/);
    for (const w of words) { await sleep(18); events.push({ type: "token", rid, text: w }); }
    await sleep(120);
    events.push({ type: "done", rid, answer: answer(q), trace: trace(q) });
  }

  const sessions = [
    { id: "s-1", title: "why does the panel freeze when the model is slow?", created: new Date().toISOString(), updated: new Date().toISOString(), source_app: "VS Code", capture: "uia", private: false, turns: 2, preview: "It freezes because the model call runs on the UI thread…" },
    { id: "s-2", title: "rewrite this more formally", created: new Date(Date.now() - 86400000).toISOString(), updated: new Date(Date.now() - 86400000).toISOString(), source_app: "Outlook", capture: "uia", private: false, turns: 4, preview: "Dear Professor Kulkarni, I am writing to request…" },
    { id: "s-3", title: "what should I ask about the new prescription?", created: new Date(Date.now() - 4 * 86400000).toISOString(), updated: new Date(Date.now() - 4 * 86400000).toISOString(), source_app: "", capture: "none", private: true, turns: 2, preview: "I don't have anything stored about your health…" },
  ];

  let jobN = 0;
  window.pywebview = { api: {
    boot: async () => ({ version: "0.7.0", routes: ["auto", "local", "cloud"], classes,
      settings: { default_route: "auto", private_by_default: false, keep_sessions: true, keep_private_sessions: false, session_cap: 200, launch_at_login: false, remember_position: true },
      status: status(), context: params.get("ctx") === "empty" ? { kind: "app" } : ctxs[params.get("ctx") || "selection"],
      hotkeys: { selection: "Ctrl+Alt+J", screenshot: "Ctrl+Alt+K", plain: "Ctrl+Alt+G" }, ocr: "en-US" }),
    status: async () => status(),
    poll: async () => events.splice(0),
    ask: async (q) => { const rid = "r" + Date.now(); simulate(rid, q); return { ok: true, rid }; },
    confirm: async () => true, new_chat: async () => true, hide: async () => true, set_mode: async () => true,
    grip: async () => true, accent: async () => true, quit: async () => true, open_folder: async () => true, copy_text: async () => true,
    deliver: async (a) => ({ ok: true, message: a === "copy_only" ? "Copied to clipboard." : "Replaced the selection.", hidden: a !== "copy_only" }),
    sessions: async (q) => sessions.filter((s) => !q || s.title.includes(q)),
    session: async (id) => { const s = sessions.find((x) => x.id === id); return Object.assign({}, s, { selection: "", turns: [{ role: "user", text: s.title, meta: {} }, { role: "assistant", text: answer(s.title), meta: { model: "qwen2.5:3b (local, 8192 tok)", private: s.private, admitted: ["Async context bug"] } }] }); },
    session_delete: async () => true, sessions_clear: async () => 3,
    session_resume: async (id) => ({ ok: true, context: { kind: "resumed", resumed: id, has_host: false, app_label: "VS Code" }, turns: [{ role: "user", text: "why does the panel freeze?" }, { role: "assistant", text: answer("x") }] }),
    memory_overview: async () => ({ total: memory.length, counts: counts(), folder: "C:\\Users\\you\\.perch\\memory", embeddings: "ollama", semantic: true, stale: 0 }),
    memory_list: async (cls, q) => memory.filter((m) => (!cls || m.cls === cls) && (!q || (m.title + m.body).toLowerCase().includes(q.toLowerCase()))),
    memory_save: async (d) => { if (!d.title || !d.body) return { ok: false, error: "A memory needs a title and some text." }; const id = d.id || "n" + Date.now(); memory = memory.filter((m) => m.id !== id); memory.unshift(Object.assign({ id, updated: "2026-09-10", uses: 0, source: "manual" }, d, { tags: d.tags.map((t) => t.trim()).filter(Boolean) })); return { ok: true, how: d.id ? "updated" : "created" }; },
    memory_delete: async (id) => { memory = memory.filter((m) => m.id !== id); return true; }, memory_open: async () => true,
    gate_preview: async (q) => ({ ok: true, trace: trace(q), semantic: true }),
    dedupe: async () => ({ groups: [], total: memory.length }), seed_demo: async () => ({ created: 0, merged: 9, total: memory.length }),
    rebuild_index: async () => ({ ok: true, items: memory.length }),
    import_pick: async () => ({ ok: true, path: "C:\\Users\\you\\Downloads\\chatgpt-export.zip", name: "chatgpt-export.zip", count: 214, platforms: { chatgpt: 214 }, chars: 1843200, sessions: [] }),
    import_extract: async () => {
      const job = "j" + ++jobN;
      (async () => {
        for (let n = 1; n <= 6; n++) { await sleep(350); events.push({ type: "job", job, kind: "import", state: "progress", n, total: 6, label: ["Final year project planning", "Tauri vs Electron", "Hotkey bug", "UIA coverage", "Panel design", "Viva prep"][n - 1] }); }
        events.push({ type: "job", job, kind: "import", state: "done", uncalibrated: true, proposals: [
          { index: 0, cls: "project", title: "PERCH uses Tauri v2 for the shipping client", body: "Chose Tauri v2 over Electron because it idles at 30–50 MB against Electron's 150–300 MB, and PERCH is always running.", tags: ["perch", "tauri"], platform: "chatgpt", session: "Tauri vs Electron", confidence: 1, warnings: [] },
          { index: 1, cls: "project", title: "Hotkeys stalled after the first trigger", body: "Each panel ran its own mainloop, blocking the thread that drained the hotkey queue. Fixed with one root and one loop for the process lifetime.", tags: ["perch", "bug"], platform: "chatgpt", session: "Hotkey bug", confidence: 1, warnings: [] },
          { index: 2, cls: "project", title: "Electron is chosen for its client-side functionality", body: "Electron was selected for the client because of its client-side functionality.", tags: ["electron"], platform: "chatgpt", session: "Tauri vs Electron", confidence: 1, warnings: ["model labelled this 'career'; filed as 'project'"] },
        ] });
      })();
      return { ok: true, job };
    },
    import_commit: async (d) => ({ ok: true, summary: { accepted: d.filter((x) => x.keep).length, rejected: d.filter((x) => !x.keep).length, created: d.filter((x) => x.keep).map(() => "x"), merged: [] }, total: memory.length }),
    eval_saved: async () => ({ name: "E1", title: "Over-personalisation -- OP-style probe, NOT OP-Bench", ran: false, reason: "not run yet. It generates and judges ~70 answers (a few minutes on a GPU, ~15 on a CPU).", verdict: "", lines: [] }),
    eval_run: async (names) => {
      const job = "e" + ++jobN;
      (async () => {
        for (const n of names) { await sleep(700); events.push({ type: "job", job, kind: "eval", state: "result", result: { name: n.toUpperCase(), title: n, ran: n !== "e3", reason: n === "e3" ? "LongMemEval and LoCoMo are not vendored here." : "", verdict: n === "e4" ? "config C: C ours 0 3 / 3 (leaked items | useful context kept)." : "PASSED", lines: ["mock output", "line two"] } }); }
        events.push({ type: "job", job, kind: "eval", state: "done" });
      })();
      return { ok: true, job };
    },
    settings_get: async () => ({ values: { default_route: "auto", private_by_default: false, keep_sessions: true, keep_private_sessions: false, session_cap: 200, launch_at_login: false, remember_position: true }, locked: {}, login: false,
      rules: { apps: ["keepass*", "bitwarden*", "1password*"], titles: ["*confidential*", "*[private]*"], folders: [] },
      models: [{ key: "local", id: "qwen2.5:3b", local: true, window: 8192, tools: true, vision: false, stub: false }],
      hotkeys: { selection: "Ctrl+Alt+J", screenshot: "Ctrl+Alt+K", plain: "Ctrl+Alt+G" }, paths: { home: "C:\\Users\\you\\.perch" }, ocr: "en-US", embeddings: "ollama", version: "0.7.0" }),
    settings_save: async (c) => ({ ok: true, values: Object.assign({ default_route: "auto", private_by_default: false, keep_sessions: true, keep_private_sessions: false, session_cap: 200, launch_at_login: false, remember_position: true }, c), login: !!c.launch_at_login }),
    rules_save: async (r) => ({ ok: true, rules: r }),
  } };
})();

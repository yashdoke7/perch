"use strict";
/*
 * PERCH -- the app. The other half is app/ui/bridge.py.
 *
 * The page never waits on Python for anything it can draw itself, and Python
 * never reaches into the page: asking, importing and evaluating start work and
 * return at once, and progress arrives through poll(). That is the rule that
 * keeps the panel responsive while a 3B model thinks.
 */

// ================================================================ utilities

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

// replaceChildren(null) inserts the text "null". Every renderer here builds
// its children with `cond ? node : null`, the same idiom h() accepts, so
// make replaceChildren accept it too rather than filter at 30 call sites.
const nativeReplace = Element.prototype.replaceChildren;
Element.prototype.replaceChildren = function (...kids) {
  return nativeReplace.apply(this, kids.flat(Infinity).filter((c) => c != null && c !== false));
};

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (k.startsWith("aria-") || k === "role") { if (v != null) el.setAttribute(k, String(v)); continue; }
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "html") el.innerHTML = v;
      else if (k === "value") el.value = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "dataset") Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

const fmt = (n) => Number(n || 0).toLocaleString("en-GB");
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
const plural = (n, one, many) => `${fmt(n)} ${n === 1 ? one : (many || one + "s")}`;
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

function dayLabel(iso) {
  const d = new Date(iso), now = new Date();
  const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(now) - start(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return d.toLocaleDateString("en-GB", { weekday: "long" });
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}
const timeOf = (iso) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const modelShort = (label) => (label || "").replace(/\s*\((local|cloud)[^)]*\)/, " · $1");

// ================================================================ icons

const ICON = {
  ask: '<path d="M4.5 6A2.5 2.5 0 0 1 7 3.5h10A2.5 2.5 0 0 1 19.5 6v7.5A2.5 2.5 0 0 1 17 16h-6.5L6 20v-4h0a1.5 1.5 0 0 1-1.5-1.5z"/>',
  history: '<path d="M3.6 12a8.4 8.4 0 1 0 2.5-6"/><path d="M3.3 4.3V8h3.7"/><path d="M12 7.6V12l3 1.9"/>',
  memory: '<path d="M12 3.4 3.6 7.7 12 12l8.4-4.3z"/><path d="m3.6 12.2 8.4 4.3 8.4-4.3"/><path d="m3.6 16.6 8.4 4.3 8.4-4.3"/>',
  import: '<path d="M12 3.5v10.5"/><path d="m7.6 9.8 4.4 4.4 4.4-4.4"/><path d="M4 15.5v3A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5v-3"/>',
  eval: '<path d="M4.5 20V11"/><path d="M10 20V4.5"/><path d="M15.5 20v-6.5"/><path d="M21 20H3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.9 19.1l1.7-1.7M17.4 6.6l1.7-1.7"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.2 10.5V7.8a3.8 3.8 0 0 1 7.6 0v2.7"/>',
  unlock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.2 10.5V7.8a3.8 3.8 0 0 1 7.3-1.4"/>',
  expand: '<path d="M14 4h6v6"/><path d="m20 4-6.5 6.5"/><path d="M10 20H4v-6"/><path d="m4 20 6.5-6.5"/>',
  collapse: '<path d="M4.5 14H10v5.5"/><path d="M10 14 3.5 20.5"/><path d="M19.5 10H14V4.5"/><path d="M14 10l6.5-6.5"/>',
  close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  send: '<path d="M12 19V5.5"/><path d="m6.5 11 5.5-5.5 5.5 5.5"/>',
  copy: '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
  replace: '<path d="M4 7.5h11.5l-3-3"/><path d="M20 16.5H8.5l3 3"/>',
  insert: '<path d="M4 6h16"/><path d="M4 10.5h9"/><path d="M12 14v6.5"/><path d="m9 17.5 3 3 3-3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4.5 7h15"/><path d="M10 11v6M14 11v6"/><path d="m6.5 7 .9 12.2a1.9 1.9 0 0 0 1.9 1.8h5.4a1.9 1.9 0 0 0 1.9-1.8L17.5 7"/><path d="M9.5 7V4.5h5V7"/>',
  file: '<path d="M14 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8z"/><path d="M14 3.5V8h4.5"/>',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  spark: '<path d="M12 3.5 13.9 10l6.6 2-6.6 2L12 20.5 10.1 14 3.5 12l6.6-2z"/>',
  warn: '<path d="M10.3 4.3 2.9 17.4a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4M12 17v.5"/>',
  edit: '<path d="M4.5 19.5h4l10-10a2.8 2.8 0 0 0-4-4l-10 10z"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  play: '<path d="M8 5.5v13l10-6.5z"/>',
  screen: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/>',
  cursor: '<path d="M5 3.5 18.5 10l-5.8 1.6L10.1 18z"/>',
  refresh: '<path d="M20 11.5a8 8 0 1 0-2.4 5.7"/><path d="M20 4.5v7h-7"/>',
  power: '<path d="M12 3.5v8"/><path d="M6.4 6.9a7.5 7.5 0 1 0 11.2 0"/>',
};
function icon(name, cls = "") {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("class", `i ${cls}`);
  s.setAttribute("aria-hidden", "true");
  s.innerHTML = ICON[name] || "";
  return s;
}

// ================================================================ state

const S = {
  boot: null, classes: [], status: null, settings: {},
  ctx: {}, private: false, route: "auto",
  busy: false, rid: null, msgs: [], trace: null, stages: {}, caption: "",
  lastAnswer: "", why: false, view: "ask", mode: "compact",
  dismissed: new Set(),
  sess: { q: "", list: [], open: null },
  mem: { cls: "", q: "", items: [], ov: null },
  imp: { step: "pick", info: null, cls: "", job: null, progress: null, proposals: [], dec: {}, cur: 0, uncal: false, summary: null, error: "", model: "" },
  evals: { job: null, results: {}, running: new Set(), progress: "", loaded: false },
  set: null,
};
const clsOf = (name) => S.classes.find((c) => c.name === name);

let API = null;
let started = false;

// ================================================================ boot

async function start() {
  if (started || !(window.pywebview && window.pywebview.api && window.pywebview.api.boot)) return;
  started = true;
  API = window.pywebview.api;
  let boot;
  try {
    boot = await API.boot();
  } catch (e) {
    document.body.innerHTML = `<pre style="padding:16px;white-space:pre-wrap">PERCH could not reach its core:\n${String(e)}</pre>`;
    return;
  }
  S.boot = boot;
  S.classes = boot.classes;
  S.status = boot.status;
  S.settings = boot.settings || {};
  S.route = S.settings.default_route || "auto";
  S.private = !!S.settings.private_by_default;
  S.ctx = boot.context || {};

  buildNav();
  bindChrome();
  bindComposer();
  bindKeys();
  bindGrip();
  applyPrivacy();
  renderTitlebar();
  renderBanner();
  renderSideStatus();
  renderAsk();
  loop();

  const params = new URLSearchParams(location.search);
  if (params.get("mode") === "expanded") setMode("expanded", false);
  if (params.get("view")) setView(params.get("view"));
}

window.perch = { pump: () => pump(), focusComposer: () => focusComposer(), setMode: (m, tell) => setMode(m, tell) };
window.addEventListener("pywebviewready", start);
if (window.pywebview && window.pywebview.api && window.pywebview.api.boot) start();
if (!window.pywebview && /[?&]mock\b/.test(location.search)) {
  const s = document.createElement("script");
  s.src = "mock.js";
  s.onload = start;
  document.head.append(s);
}

// ================================================================ events

let pumping = false;
async function pump() {
  if (pumping || !API) return;
  pumping = true;
  try {
    const events = await API.poll();
    for (const ev of events || []) handle(ev);
  } catch (e) {
    console.error(e);
  } finally {
    pumping = false;
  }
}
function loop() {
  const hurry = S.busy || S.imp.job || S.evals.job;
  pump().finally(() => setTimeout(loop, hurry ? 60 : 280));
}

function handle(ev) {
  switch (ev.type) {
    case "open": onOpen(ev.context); break;
    case "stage": onStage(ev); break;
    case "token": onToken(ev); break;
    case "confirm": onConfirm(ev); break;
    case "confirm_timeout": closeModal(); toast("Permission request timed out, so it was refused.", "bad"); break;
    case "done": onDone(ev); break;
    case "error": onError(ev); break;
    case "delivered": toast(ev.message, ev.ok ? "" : "bad"); break;
    case "job": onJob(ev); break;
  }
}

function onOpen(ctx) {
  closeModal();
  closeDrawer();
  S.ctx = ctx || {};
  S.msgs = [];
  S.trace = null;
  S.stages = {};
  S.caption = "";
  S.lastAnswer = "";
  S.why = false;
  S.busy = false;
  S.private = !!S.settings.private_by_default;
  applyPrivacy();
  renderTitlebar();
  if (S.ctx.kind !== "app") setView("ask");
  else if (S.view === "ask") renderAsk();
  refreshStatus();
  focusComposer();
}

// ================================================================ chrome

const VIEWS = [
  ["ask", "Ask", "ask"],
  ["sessions", "Conversations", "history"],
  ["memory", "Memory", "memory"],
  ["import", "Import", "import"],
  ["eval", "Evaluate", "eval"],
  ["settings", "Settings", "settings"],
];

function buildNav() {
  $("#navList").replaceChildren(...VIEWS.map(([v, label, ic], i) =>
    h("button", { type: "button", dataset: { view: v }, onclick: () => setView(v) },
      icon(ic), h("span", { text: label }), h("kbd", { text: `Ctrl ${i + 1}` }))));
}

function bindChrome() {
  $("#routeBtn").addEventListener("click", cycleRoute);
  $("#privateBtn").addEventListener("click", togglePrivate);
  $("#modeBtn").addEventListener("click", () => setMode(S.mode === "expanded" ? "compact" : "expanded"));
  $("#closeBtn").addEventListener("click", () => API.hide());
  $("#why").addEventListener("click", () => { S.why = !S.why; renderWhy(); renderInspector(); });
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".code-copy");
    if (!b) return;
    const code = b.closest(".code").querySelector("code").textContent;
    API.copy_text(code);
    b.textContent = "Copied";
    setTimeout(() => { b.textContent = "Copy"; }, 1200);
  });
}

function setView(v) {
  if (v !== "ask" && S.mode !== "expanded") setMode("expanded");
  S.view = v;
  document.body.dataset.view = v;
  $$("#navList button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === v ? "page" : "false"));
  closeDrawer();
  ({ ask: renderAsk, sessions: loadSessions, memory: () => loadMemory(true), import: renderImport, eval: loadEval, settings: loadSettings })[v]();
  if (v === "ask") focusComposer();
}

function setMode(mode, tell = true) {
  if (mode !== "compact" && mode !== "expanded") return;
  S.mode = mode;
  document.body.classList.toggle("expanded", mode === "expanded");
  document.body.classList.toggle("compact", mode === "compact");
  if (mode === "compact" && S.view !== "ask") {
    S.view = "ask";
    document.body.dataset.view = "ask";
    closeDrawer();
  }
  $$("#navList button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === S.view ? "page" : "false"));
  renderTitlebar();
  renderAsk();
  if (tell && API) API.set_mode(mode);
}

function renderTitlebar() {
  const m = (S.status && S.status.model) || {};
  const rb = $("#routeBtn");
  const forced = S.private;
  const dot = m.stub ? "stub" : forced || S.route === "local" || (S.route === "auto" && m.local) ? "local" : "cloud";
  rb.replaceChildren(h("span", { class: `dot ${dot}` }), h("span", { text: forced ? "local only" : S.route }));
  rb.classList.toggle("forced", forced);
  rb.title = forced
    ? "Private: this request can only go to a model on this machine"
    : `Which model answers: ${S.route}. Click to switch (auto, local, cloud).`;
  const pb = $("#privateBtn");
  pb.replaceChildren(icon(S.private ? "lock" : "unlock", "sm"), h("span", { text: "Private" }));
  pb.setAttribute("aria-pressed", String(S.private));
  pb.title = S.private ? "Private: nothing leaves this machine (Ctrl+P)" : "Make this private: nothing leaves this machine (Ctrl+P)";
  const mb = $("#modeBtn");
  mb.replaceChildren(icon(S.mode === "expanded" ? "collapse" : "expand"));
  mb.title = S.mode === "expanded" ? "Back to the panel (Ctrl+E)" : "Full view: memory, conversations, import (Ctrl+E)";
  $("#closeBtn").replaceChildren(icon("close"));
}

function cycleRoute() {
  if (S.private) { toast("Private requests always stay on this machine."); return; }
  const routes = ["auto", "local", "cloud"];
  S.route = routes[(routes.indexOf(S.route) + 1) % routes.length];
  renderTitlebar();
}

function togglePrivate() {
  S.private = !S.private;
  applyPrivacy();
  renderTitlebar();
  toast(S.private ? "Private: this conversation stays on this machine" : "Private off");
}

function applyPrivacy() {
  const on = S.private || !!(S.trace && S.trace.private);
  document.body.classList.toggle("private", on);
  if (API) API.accent(on);
}

function renderBanner() {
  const b = $("#banner");
  const w = ((S.status && S.status.warnings) || []).find((x) => !S.dismissed.has(x.text));
  if (!w) { b.hidden = true; return; }
  b.hidden = false;
  b.className = "banner" + (w.level === "error" ? " error" : "");
  b.replaceChildren(
    icon("warn", "sm"),
    h("div", { class: "txt" }, h("b", { text: w.text }), " ", h("span", { class: "fix", text: w.fix })),
    w.action === "rebuild" ? h("button", { class: "btn", type: "button", onclick: rebuildIndex, text: "Rebuild" }) : null,
    h("button", { class: "icon-btn", type: "button", title: "Dismiss", onclick: () => { S.dismissed.add(w.text); renderBanner(); } }, icon("close", "sm")));
}

function renderSideStatus() {
  const st = S.status || {};
  const m = st.model || {};
  $("#sideStatus").replaceChildren(
    h("div", { class: "row" }, h("span", { class: `dot ${m.stub ? "stub" : m.local ? "local" : "cloud"}` }),
      h("span", { class: "ellipsis", text: m.stub ? "No model reachable" : `${m.id} · ${m.local ? "local" : "cloud"}` })),
    h("div", { class: "row muted" }, h("span", { class: "ellipsis", text: `${plural(st.memory || 0, "memory", "memories")} · ${st.semantic ? st.embeddings : "fallback embeddings"}` })),
    h("div", { class: "row muted" }, h("span", { text: `PERCH ${S.boot ? S.boot.version : ""}` })));
}

async function refreshStatus() {
  try {
    S.status = await API.status();
  } catch (e) { return; }
  renderBanner();
  renderSideStatus();
  renderTitlebar();
}

// ================================================================ ask view

function renderAsk() {
  renderSource();
  renderThread();
  renderDock();
  renderInspector();
}

function methodLabel(c) {
  switch (c.method) {
    case "uia": return "via UI Automation";
    case "clipboard": return "via clipboard";
    case "screenshot": return c.ocr && c.ocr.chars ? `Windows OCR · ${fmt(c.ocr.ms)} ms` : "screenshot";
    default: return c.resumed ? "earlier conversation" : c.kind === "selection" ? "nothing captured" : "";
  }
}

function renderSource() {
  const c = S.ctx || {};
  const el = $("#source");
  const show = c.kind && c.kind !== "app" && c.kind !== "plain" || (c.kind === "plain" && c.source_title);
  if (!show) { el.hidden = true; el.replaceChildren(); return; }
  el.hidden = false;
  const label = c.app_label || (c.source_app ? cap(c.source_app) : "");
  const line = h("div", { class: "src-line" },
    h("span", { class: "app-badge", text: c.kind === "screenshot" && !label ? "" : (label || "?").slice(0, 1).toUpperCase() },
      c.kind === "screenshot" && !label ? icon("screen", "xs") : null),
    label ? h("span", { class: "src-app", text: label }) : h("span", { class: "src-app", text: c.kind === "screenshot" ? "Screenshot" : c.resumed ? "Earlier conversation" : "" }),
    // Many apps title their window with just their own name ("Claude"); saying it twice is noise.
    c.source_title && c.source_title.trim().toLowerCase() !== (label || "").trim().toLowerCase()
      ? h("span", { class: "src-title", title: c.source_title, text: c.source_title }) : null,
    h("span", { class: "method", text: methodLabel(c) }));
  const parts = [line];

  if (c.kind === "screenshot") {
    const text = c.selection
      ? h("div", { class: "quote", title: "Click to expand", onclick: (e) => e.currentTarget.classList.add("open"), text: c.selection })
      : h("div", { class: "empty-note", text: (c.ocr && c.ocr.note) || "No text was found in the screenshot." });
    parts.push(h("div", { class: "shot" }, c.thumb ? h("img", { src: c.thumb, alt: "Your screenshot" }) : h("span"), text));
  } else if (c.selection) {
    parts.push(h("div", { class: "quote", title: "Click to expand", onclick: (e) => e.currentTarget.classList.add("open"), text: c.selection }));
  } else if (c.kind === "selection") {
    const key = (S.boot && S.boot.hotkeys && S.boot.hotkeys.selection) || "the shortcut";
    parts.push(h("div", { class: "warnbox" }, icon("warn", "sm"),
      h("div", { text: `No text came through from ${label || "that window"}. Ask anyway, or select the text again and press ${key}.` })));
  }
  el.replaceChildren(...parts);
}

function greeting() {
  const hr = new Date().getHours();
  return hr < 5 ? "Working late" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}

function renderWelcome() {
  const st = S.status || {};
  const c = S.ctx || {};
  if (!st.memory && c.kind !== "screenshot" && !c.selection) {
    return h("div", { class: "welcome" }, h("div", { class: "onboard" },
      h("h2", { text: "PERCH doesn't know you yet" }),
      h("p", { text: "Memory is what makes answers sound like you. It stays on this machine as plain files you can read, edit and delete — and PERCH only uses a memory when it clearly fits the question." }),
      h("div", { class: "row" },
        h("button", { class: "btn accent", type: "button", onclick: () => setView("import") }, icon("import", "sm"), "Import my AI history"),
        h("button", { class: "btn", type: "button", onclick: () => { setView("memory"); openEditor({ cls: "identity" }); } }, icon("edit", "sm"), "Write about myself")),
      h("button", { class: "btn ghost", type: "button", onclick: seedDemo, style: "justify-self:start" }, "Or try it with demo memory")));
  }
  let title, sub, ideas;
  if (c.kind === "screenshot") {
    title = "Ask about your screenshot";
    sub = c.ocr && c.ocr.chars
      ? `${plural(c.ocr.chars, "character")} read on this machine. ${st.model && st.model.vision ? "The image itself goes to the model too." : "The model sees the text, not the picture."}`
      : "No text was found. A vision model can still look at it.";
    ideas = ["What does this say?", "Explain this error", "Turn this into notes"];
  } else if (c.selection) {
    title = "Ask about the selection";
    sub = c.has_host ? `Answers can go straight back into ${c.app_label || "the window you were in"}.` : "Copy the answer when you're done.";
    ideas = ["Explain this", "Summarise this", "Rewrite this more formally", "What's wrong with this?"];
  } else {
    title = greeting();
    sub = `${plural(st.memory || 0, "memory", "memories")} on this machine. PERCH only reaches for the ones that clear their class's bar.`;
    ideas = ["What do you know about me?", "Help me write a short email", "Plan my week"];
  }
  return h("div", { class: "welcome" },
    h("h2", { text: title }), h("p", { text: sub }),
    h("div", { class: "suggest" }, ideas.map((q) => h("button", { class: "chip-btn", type: "button", text: q, onclick: () => ask(q) }))));
}

function renderThread() {
  const t = $("#thread");
  t.replaceChildren();
  if (!S.msgs.length) { t.append(renderWelcome()); return; }
  for (const m of S.msgs) t.append(renderMsg(m));
  requestAnimationFrame(() => { t.scrollTop = t.scrollHeight; });
}

function renderMsg(m) {
  if (m.role === "user") return h("div", { class: "msg user" }, h("div", { class: "bubble", text: m.text }));
  const md = h("div", { class: "md" + (m.streaming ? " streaming" : "") });
  if (m.pending) md.append(h("div", { class: "thinking", "aria-label": "Thinking" }, h("span"), h("span"), h("span")));
  else md.innerHTML = Markdown.render(m.text || "");
  m.el = md;
  const box = h("div", { class: "msg perch" + (m.error ? " error" : "") }, md);
  if (!m.streaming && m.trace) box.append(renderMeta(m.trace));
  return box;
}

function renderMeta(tr) {
  const n = tr.admitted.length;
  const openWhy = () => { if (S.mode === "compact") { S.why = true; renderWhy(); renderInspector(); } };
  return h("div", { class: "meta" },
    h("span", { class: "tag", text: modelShort(tr.model) }),
    tr.private ? h("span", { class: "tag private" }, icon("lock", "xs"), "private") : null,
    h("button", { class: "tag link", type: "button", onclick: openWhy, text: tr.abstained ? "no memory used" : `${plural(n, "memory", "memories")} used` }),
    tr.tools && tr.tools.length ? h("span", { class: "tag", text: "used " + tr.tools.map((t) => t.split("(")[0]).join(", ") }) : null,
    h("span", { text: `${(tr.ms / 1000).toFixed(1)} s` }));
}

let streamQueued = false;
function queueStream(m) {
  if (streamQueued) return;
  streamQueued = true;
  requestAnimationFrame(() => {
    streamQueued = false;
    if (!m.el) return;
    const t = $("#thread");
    const pinned = t.scrollHeight - t.scrollTop - t.clientHeight < 80;
    m.el.innerHTML = Markdown.render(m.text);
    m.el.classList.toggle("streaming", !!m.streaming);
    if (pinned) t.scrollTop = t.scrollHeight;
  });
}

function renderDock() {
  renderRail();
  renderWhy();
  renderActions();
  const c = S.ctx || {};
  $("#prompt").placeholder = c.kind === "screenshot" ? "Ask about the screenshot…"
    : c.selection ? "Ask about the selection…" : S.msgs.length ? "Follow up…" : "Ask anything…";
  $("#sendBtn").disabled = S.busy;
  $("#sendBtn").replaceChildren(icon("send"));
}

const STAGES = [["route", "Route"], ["rank", "Rank"], ["gate", "Gate"], ["pack", "Pack"], ["model", "Answer"]];

function renderRail() {
  const r = $("#rail");
  if (!S.busy && !S.trace) { r.hidden = true; return; }
  r.hidden = false;
  r.replaceChildren();
  const doneCount = STAGES.filter(([k]) => S.stages[k] != null).length;
  const active = S.busy ? STAGES[Math.min(doneCount, STAGES.length - 1)][0] : null;
  for (const [k, label] of STAGES) {
    let cls = "st";
    const st = S.stages[k];
    if (st != null) cls += k === "gate" && st === "abstained" ? " done abstain" : " done";
    if (S.busy && (k === active || (k === "model" && st != null))) cls += " active";
    r.append(h("span", { class: cls }, h("span", { class: "pip" }), label));
  }
  r.append(h("span", { class: "cap", text: S.caption || (S.trace ? `${fmt(S.trace.ms)} ms` : "") }));
}

function captionFor(name, detail) {
  switch (name) {
    case "route": return detail ? `classes: ${detail}` : "routing";
    case "gate": return detail === "abstained" ? "nothing cleared its floor" : detail;
    case "model": return detail;
    default: return detail || name;
  }
}

function renderWhy() {
  const b = $("#why");
  const tr = S.trace;
  if (!tr || S.busy || S.mode === "expanded") { b.hidden = true; return; }
  b.hidden = false;
  const L = tr.ledger || { segments: [], budget: 0 };
  const budget = L.budget || 1;
  b.replaceChildren(
    h("span", { class: "mini-ledger" }, L.segments.map((s) =>
      h("span", { class: `seg seg-${s.kind}${s.cls ? ` cls-${s.cls}` : ""}`, style: `width:${(s.tokens / budget) * 100}%` }))),
    h("span", { text: tr.abstained ? "No memory cleared its bar" : `${plural(tr.admitted.length, "memory", "memories")} used` }),
    tr.dropped.length ? h("span", { class: "muted", text: `· ${tr.dropped.length} held back` }) : null,
    h("span", { class: "go" }, S.why ? "Back to answer" : "Why this answer", icon("chev", "xs")));
}

function renderActions() {
  const a = $("#actions");
  const has = !!S.lastAnswer && !S.busy;
  const c = S.ctx || {};
  const host = !!c.has_host;
  a.replaceChildren(
    host ? h("button", { class: "btn primary", type: "button", disabled: !has, onclick: () => deliver("replace"), title: `Replace the selection in ${c.app_label || "the app"} (Ctrl+Enter)` },
      icon("replace", "sm"), "Replace", h("kbd", { text: "Ctrl ↵" })) : null,
    host ? h("button", { class: "btn", type: "button", disabled: !has, onclick: () => deliver("insert_after"), title: "Insert below the selection (Ctrl+Shift+Enter)" },
      icon("insert", "sm"), "Insert below") : null,
    h("button", { class: "btn", type: "button", disabled: !has, onclick: () => deliver("copy_only"), title: "Copy the answer (Ctrl+Shift+C)" }, icon("copy", "sm"), "Copy"),
    h("span", { class: "spacer" }),
    S.msgs.length ? h("button", { class: "btn ghost", type: "button", onclick: newChat, title: "New conversation (Ctrl+N)" }, icon("plus", "sm"), "New") : null);
}

// ---------------------------------------------------------------- inspector

function reason(it) {
  const r = it.reason || "";
  let m;
  if ((m = r.match(/class below floor \(([\d.]+) < ([\d.]+)\)/)))
    return `the best ${it.cls} match (${(+m[1]).toFixed(2)}) is under the ${it.cls} floor of ${(+m[2]).toFixed(2)}`;
  if (/below class margin/.test(r)) return `too far below the strongest ${it.cls} match to be worth the space`;
  if (/tool result needed the budget/.test(r)) return "pushed out to make room for a tool result";
  if (/no budget left/.test(r)) return "no room left in the context window";
  if ((m = r.match(/beyond max_items=(\d+)/))) return `over the ${m[1]}-memory limit`;
  return r;
}

function gateRow(it, admitted) {
  const pct = clamp(it.score, 0, 1) * 100;
  const floor = clamp(it.floor, 0, 1) * 100;
  return h("div", { class: `gate-row ${admitted ? "in" : "out"} cls-${it.cls}` },
    h("span", { class: "gdot" }),
    h("div", { style: "min-width:0" },
      h("div", { class: "gate-title" }, it.private ? icon("lock", "xs") : null, h("span", { text: it.title, title: it.title })),
      h("div", { class: "score", title: `score ${it.score.toFixed(2)} · ${it.cls} floor ${it.floor.toFixed(2)}` },
        h("div", { class: "score-fill", style: `width:${pct}%` }),
        h("div", { class: "score-floor", style: `left:${floor}%` })),
      admitted ? null : h("div", { class: "gate-why", text: reason(it) })),
    h("span", { class: "gate-score", text: it.score.toFixed(2) }));
}

function renderLedger(L) {
  const budget = L.budget || 1;
  const bar = h("div", { class: "ledger-bar", role: "img", "aria-label": `${fmt(L.used)} of ${fmt(budget)} tokens used` },
    L.segments.map((s) => h("div", {
      class: `seg seg-${s.kind}${s.cls ? ` cls-${s.cls}` : ""}`,
      style: `width:${Math.max(0.5, (s.tokens / budget) * 100)}%`,
      title: `${s.label} · ${fmt(s.tokens)} tokens`,
    })));
  const groups = [["system", "Instructions"], ["selection", "Selection"], ["history", "Conversation"], ["memory", "Memory"],
                  ["question", "Question"], ["tools", "Tool results"], ["turns", "Model working"]];
  const legend = h("div", { class: "legend" });
  for (const [kind, label] of groups) {
    const segs = L.segments.filter((s) => s.kind === kind);
    if (!segs.length) continue;
    const n = segs.reduce((a, s) => a + s.tokens, 0);
    legend.append(h("div", { class: "row" }, h("span", { class: `sw ${kind === "memory" ? "mem" : `seg-${kind}`}` }), h("span", { text: label }), h("span", { class: "n", text: fmt(n) })));
    if (kind === "memory") for (const s of segs) {
      legend.append(h("div", { class: `row sub cls-${s.cls}` }, h("span", { class: "sw cls" }), h("span", { class: "ellipsis", text: s.label }), h("span", { class: "n", text: fmt(s.tokens) })));
    }
  }
  legend.append(h("div", { class: "row" }, h("span", { class: "sw free" }), h("span", { text: "Unused" }), h("span", { class: "n", text: fmt(Math.max(0, budget - L.used)) })));
  return h("div", {}, bar, legend,
    L.window ? h("p", { class: "key-note", text: `The model gets ${fmt(L.window)} tokens. ${fmt(L.window - budget)} are kept back for its answer; memory and tool results share the rest.` }) : null);
}

function inspectorContent(tr) {
  const root = h("div", { class: "insp" });
  if (!tr) {
    root.append(h("section", {},
      h("h4", { text: "How PERCH answers" }),
      h("p", { class: "empty-note", text: "Ask something and this shows the working: which memories were used, which were held back and why, and how the model's context window was spent." }),
      h("p", { class: "empty-note", style: "margin-top:10px", text: "Every memory class has a floor. A memory is only used if it clears it — ranking is relative, injection is absolute." })));
    return root;
  }
  const L = tr.ledger || { segments: [], budget: 0, used: 0 };
  root.append(h("section", {}, h("h4", {}, "Context window", h("span", { class: "aside", text: `${fmt(L.used)} / ${fmt(L.budget)}` })), renderLedger(L)));

  const mem = h("section", {}, h("h4", {}, "Memory",
    h("span", { class: "aside", text: tr.abstained ? "none used" : `${tr.admitted.length} used · ${tr.dropped.length} held back` })));
  if (tr.abstained) {
    mem.append(h("div", { class: "callout abstain" }, h("b", { text: "Nothing cleared its floor. " }),
      "PERCH answered from general knowledge rather than reaching for the closest thing it had. That's deliberate."));
  }
  tr.admitted.forEach((it) => mem.append(gateRow(it, true)));
  tr.dropped.slice(0, 8).forEach((it) => mem.append(gateRow(it, false)));
  if (tr.dropped.length > 8) mem.append(h("p", { class: "empty-note", text: `+ ${tr.dropped.length - 8} more held back` }));
  if (!tr.admitted.length && !tr.dropped.length && !tr.abstained) mem.append(h("p", { class: "empty-note", text: "This question didn't reach for memory." }));
  if (tr.admitted.length || tr.dropped.length) mem.append(h("p", { class: "key-note" }, "The ", h("span", { class: "floor-key" }), " mark is each class's floor."));
  root.append(mem);

  const privacy = tr.private ? tr.privacy.replace(/^PRIVATE - /, "Private — ") : "Cloud allowed";
  root.append(h("section", {}, h("h4", { text: "Route" }), h("dl", { class: "kv" },
    h("dt", { text: "Model" }), h("dd", { text: tr.model }),
    h("dt", { text: "Privacy" }), h("dd", { text: privacy }),
    tr.vision ? [h("dt", { text: "Image" }), h("dd", { text: tr.vision })] : null,
    tr.tools && tr.tools.length ? [h("dt", { text: "Tools" }), h("dd", { class: "mono", text: tr.tools.join("\n") })] : null,
    h("dt", { text: "Classes" }), h("dd", { text: (tr.eligible || []).join(", ") || "—" }),
    h("dt", { text: "Time" }), h("dd", { text: `${fmt(tr.ms)} ms` }))));
  return root;
}

function renderInspector() {
  $("#inspector").replaceChildren(inspectorContent(S.trace));
  const open = S.why && S.mode === "compact" && !!S.trace;
  $("#whyDrawer").hidden = !open;
  $("#view-ask").classList.toggle("why-open", open);
  if (open) $("#whyDrawer").replaceChildren(inspectorContent(S.trace));
}

// ---------------------------------------------------------------- asking

function lastAssistant() {
  for (let i = S.msgs.length - 1; i >= 0; i--) if (S.msgs[i].role === "assistant") return S.msgs[i];
  return null;
}

async function ask(text) {
  const box = $("#prompt");
  const q = (text != null ? text : box.value).trim();
  if (!q || S.busy) return;
  box.value = "";
  autosize();
  S.why = false;
  S.msgs.push({ role: "user", text: q });
  const m = { role: "assistant", text: "", streaming: true, pending: true };
  S.msgs.push(m);
  S.busy = true;
  S.stages = {};
  S.caption = "";
  S.trace = null;
  applyPrivacy();
  renderThread();
  renderDock();
  renderInspector();
  let r;
  try {
    r = await API.ask(q, S.private, S.private ? "local" : S.route);
  } catch (e) {
    r = { ok: false, error: String(e) };
  }
  if (!r || !r.ok) {
    m.text = r && r.error === "busy" ? "Still working on the last question." : "That request could not start.";
    m.pending = m.streaming = false;
    m.error = true;
    S.busy = false;
    renderThread();
    renderDock();
    return;
  }
  S.rid = r.rid;
  pump();
}

function onStage(ev) {
  if (ev.rid !== S.rid) return;
  if (ev.name === "tool") S.caption = `calling ${ev.detail}…`;
  else {
    if (ev.name !== "pack" || S.stages.pack == null) S.stages[ev.name] = ev.detail || "";
    S.caption = captionFor(ev.name, ev.detail);
  }
  renderRail();
}

function onToken(ev) {
  if (ev.rid !== S.rid) return;
  const m = lastAssistant();
  if (!m) return;
  m.pending = false;
  m.text += ev.text;
  queueStream(m);
}

function onDone(ev) {
  if (ev.rid !== S.rid) return;
  const m = lastAssistant();
  if (m) {
    m.text = ev.answer || m.text;
    m.pending = m.streaming = false;
    m.trace = ev.trace;
  }
  S.trace = ev.trace;
  S.lastAnswer = ev.answer || "";
  S.busy = false;
  S.caption = "";
  applyPrivacy();
  renderThread();
  renderDock();
  renderInspector();
  focusComposer();
}

function onError(ev) {
  if (ev.rid !== S.rid) return;
  const m = lastAssistant();
  if (m) {
    m.text = `Something went wrong: ${ev.message}`;
    m.pending = m.streaming = false;
    m.error = true;
  }
  S.busy = false;
  renderThread();
  renderDock();
}

function onConfirm(ev) {
  openModal({
    title: "Allow PERCH to do this?", iconName: "warn",
    body: h("div", { style: "display:grid;gap:10px" }, h("p", { text: ev.warning }), h("div", { class: "call", text: ev.call })),
    actions: [
      { label: "Don't allow", onClick: () => API.confirm(ev.cid, false) },
      { label: "Allow once", kind: "accent", onClick: () => API.confirm(ev.cid, true) },
    ],
    onEsc: () => API.confirm(ev.cid, false),
  });
}

async function deliver(action) {
  if (!S.lastAnswer) { toast("Ask something first."); return; }
  if (action !== "copy_only" && !(S.ctx && S.ctx.has_host)) action = "copy_only";
  const r = await API.deliver(action);
  if (action === "copy_only") toast(r.ok ? "Copied to the clipboard" : r.message, r.ok ? "" : "bad");
}

async function newChat() {
  await API.new_chat();
  S.msgs = [];
  S.trace = null;
  S.stages = {};
  S.lastAnswer = "";
  S.why = false;
  applyPrivacy();
  renderAsk();
  focusComposer();
}

function focusComposer() {
  if (S.view !== "ask" || !$("#modal").hidden) return;
  requestAnimationFrame(() => $("#prompt").focus());
}

function autosize() {
  const p = $("#prompt");
  p.style.height = "auto";
  p.style.height = Math.min(p.scrollHeight, 140) + "px";
}

function bindComposer() {
  const p = $("#prompt");
  p.addEventListener("input", autosize);
  p.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.isComposing) {
      e.preventDefault();
      ask();
    }
  });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); ask(); });
}

// ================================================================ conversations

async function loadSessions() {
  if (!$("#sessList")) buildSessions();
  S.sess.list = await API.sessions(S.sess.q || "");
  renderSessList();
  renderSessDetail();
}

function pageHead(title, sub, ...tools) {
  return h("div", { class: "page-head" },
    h("div", {}, h("h1", { text: title }), sub ? h("p", { text: sub }) : null),
    tools.length ? h("div", { class: "tools" }, tools) : null);
}

function buildSessions() {
  $("#view-sessions").replaceChildren(h("div", { class: "page" },
    pageHead("Conversations",
      "Kept on this machine so you can pick a thread back up. PERCH never learns from them: only what you save as memory is ever recalled.",
      h("button", { class: "btn", type: "button", onclick: () => API.open_folder("sessions") }, icon("folder", "sm"), "Open folder"),
      h("button", { class: "btn danger", type: "button", onclick: clearSessions }, icon("trash", "sm"), "Clear all")),
    h("div", { class: "split" },
      h("div", { class: "list" },
        h("div", { class: "search" }, icon("search"),
          h("input", { class: "field", type: "search", placeholder: "Search conversations", value: S.sess.q,
            oninput: debounce((e) => { S.sess.q = e.target.value; loadSessions(); }, 250) })),
        h("div", { id: "sessList", class: "list" })),
      h("div", { id: "sessDetail", class: "card transcript" }))));
}

function renderSessList() {
  const list = $("#sessList");
  list.replaceChildren();
  if (!S.sess.list.length) {
    list.append(h("p", { class: "empty-note", style: "padding:10px 2px", text: S.sess.q ? "Nothing matches." : "No conversations yet. They appear here after you ask something." }));
    return;
  }
  let last = "";
  for (const s of S.sess.list) {
    const day = dayLabel(s.updated);
    if (day !== last) { list.append(h("div", { class: "day", text: day })); last = day; }
    const exchanges = Math.round(s.turns / 2);
    list.append(h("button", { class: "sess", type: "button", "aria-current": String(!!(S.sess.open && S.sess.open.id === s.id)), onclick: () => openSession(s.id) },
      h("div", { class: "t", text: s.title }),
      h("div", { class: "s" }, s.private ? icon("lock", "xs") : null,
        h("span", { text: [s.source_app, plural(exchanges, "exchange"), timeOf(s.updated)].filter(Boolean).join(" · ") })),
      s.preview ? h("div", { class: "p", text: s.preview }) : null));
  }
}

async function openSession(id) {
  S.sess.open = await API.session(id);
  renderSessList();
  renderSessDetail();
}

function renderSessDetail() {
  const d = $("#sessDetail");
  const s = S.sess.open;
  if (!s) { d.replaceChildren(h("p", { class: "empty-note", text: "Choose a conversation to read it, or pick it back up." })); return; }
  d.replaceChildren(
    h("div", { class: "head" },
      h("div", { style: "flex:1;min-width:0" }, h("h2", { text: s.title || "(untitled)" }),
        h("p", { class: "empty-note", text: [s.source_app, `${dayLabel(s.created)}, ${timeOf(s.created)}`, s.private ? "private" : ""].filter(Boolean).join(" · ") })),
      h("button", { class: "btn accent", type: "button", onclick: () => resumeSession(s.id) }, icon("ask", "sm"), "Continue"),
      h("button", { class: "btn danger", type: "button", onclick: () => deleteSession(s.id) }, icon("trash", "sm"))),
    s.selection ? h("div", { class: "quote", onclick: (e) => e.currentTarget.classList.add("open"), text: s.selection }) : null,
    s.turns.map((t) => t.role === "user"
      ? h("div", { class: "msg user" }, h("div", { class: "bubble", text: t.text }))
      : h("div", { class: "msg perch" }, h("div", { class: "md", html: Markdown.render(t.text) }),
          t.meta && t.meta.model ? h("div", { class: "meta" }, h("span", { class: "tag", text: modelShort(t.meta.model) }),
            t.meta.private ? h("span", { class: "tag private" }, icon("lock", "xs"), "private") : null,
            h("span", { class: "tag", text: t.meta.abstained ? "no memory used" : plural((t.meta.admitted || []).length, "memory", "memories") + " used" })) : null)));
}

async function resumeSession(id) {
  const r = await API.session_resume(id);
  if (!r.ok) { toast("That conversation is gone.", "bad"); return; }
  S.ctx = r.context;
  S.msgs = r.turns.map((t) => ({ role: t.role, text: t.text }));
  S.lastAnswer = (lastAssistant() || {}).text || "";
  S.trace = null;
  S.stages = {};
  setView("ask");
}

function deleteSession(id) {
  confirmDialog("Delete this conversation?", "It will be removed from this machine. There is no undo.", "Delete", async () => {
    await API.session_delete(id);
    S.sess.open = null;
    loadSessions();
  });
}

function clearSessions() {
  confirmDialog("Clear every conversation?", "All saved conversations will be deleted from this machine. Your memory is not affected.", "Clear all", async () => {
    const n = await API.sessions_clear();
    S.sess.open = null;
    toast(`${plural(n, "conversation")} deleted`);
    loadSessions();
  });
}

// ================================================================ memory

async function loadMemory(full) {
  const [ov, items] = await Promise.all([API.memory_overview(), API.memory_list(S.mem.cls, S.mem.q)]);
  S.mem.ov = ov;
  S.mem.items = items;
  if (full || !$("#memGrid")) buildMemory();
  renderMemTabs();
  renderMemNote();
  renderMemGrid();
}

function buildMemory() {
  $("#view-memory").replaceChildren(h("div", { class: "page" },
    pageHead("Memory",
      `What PERCH knows about you: one Markdown file per fact, in ${S.mem.ov.folder}. Read it, change it, delete it. A memory only reaches a prompt when it clears its class's floor.`,
      h("button", { class: "btn", type: "button", onclick: () => API.open_folder("memory") }, icon("folder", "sm"), "Open folder"),
      h("button", { class: "btn accent", type: "button", onclick: () => openEditor({ cls: S.mem.cls || "identity" }) }, icon("plus", "sm"), "New memory")),
    h("div", { class: "preview" },
      h("div", { class: "pv-head" }, icon("spark", "sm"), h("b", { text: "Test the gate" }),
        h("span", { class: "muted", text: "Type a question and see what PERCH would recall — and what it would hold back." })),
      h("input", { id: "gateQ", class: "field", type: "text", placeholder: "e.g. what should I ask the doctor about my medication?", oninput: debounce(runPreview, 350) }),
      h("div", { id: "gateRes", class: "preview-res" })),
    h("div", { id: "memTabs", class: "tabs" }),
    h("div", { id: "memNote" }),
    h("div", { class: "search", style: "margin-bottom:12px" }, icon("search"),
      h("input", { class: "field", type: "search", placeholder: "Filter by words in the title, text or tags", value: S.mem.q,
        oninput: debounce((e) => { S.mem.q = e.target.value; loadMemory(false); }, 250) })),
    h("div", { id: "memGrid", class: "mem-grid" })));
}

function renderMemTabs() {
  const counts = (S.mem.ov && S.mem.ov.counts) || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const tab = (name, label, n) => h("button", {
    class: "tab" + (name ? ` cls-${name}` : ""), type: "button", "aria-pressed": String(S.mem.cls === name),
    onclick: () => { S.mem.cls = name; loadMemory(false); },
  }, name ? h("span", { class: "sw" }) : null, label, h("span", { class: "n", text: fmt(n) }));
  $("#memTabs").replaceChildren(tab("", "All", total), S.classes.map((c) => tab(c.name, c.name, counts[c.name] || 0)));
}

function renderMemNote() {
  const c = clsOf(S.mem.cls);
  const el = $("#memNote");
  if (!c) { el.replaceChildren(); return; }
  el.replaceChildren(h("div", { class: `class-note cls-${c.name}` },
    h("span", {}, h("b", { text: c.name }), ` holds ${c.holds}.`),
    h("span", { text: `Floor ${c.floor.toFixed(2)}` }),
    c.private ? h("span", { style: "color:var(--private)" }, "Private by default: any request that uses it stays on this machine") : null,
    h("span", { text: `Up to ${c.cap} items` })));
}

function renderMemGrid() {
  const g = $("#memGrid");
  g.replaceChildren();
  if (!S.mem.items.length) {
    g.append(h("p", { class: "empty-note", text: S.mem.q ? "Nothing matches that filter." : S.mem.cls ? `No ${S.mem.cls} memories yet.` : "Memory is empty. Import your history, write something, or load the demo memory." }));
    if (!S.mem.q && !S.mem.cls) g.append(h("div", { class: "row" },
      h("button", { class: "btn accent", type: "button", onclick: () => setView("import") }, icon("import", "sm"), "Import history"),
      h("button", { class: "btn", type: "button", onclick: seedDemo }, "Load demo memory")));
    return;
  }
  for (const it of S.mem.items) {
    g.append(h("button", { class: `mem cls-${it.cls}`, type: "button", onclick: () => openEditor(it) },
      h("div", { class: "head" }, it.private ? icon("lock", "xs") : null, it.cls),
      h("div", { class: "title", text: it.title }),
      h("div", { class: "body", text: it.body }),
      it.tags.length ? h("div", { class: "tags" }, it.tags.slice(0, 5).map((t) => h("span", { class: "tag", text: t }))) : null,
      h("div", { class: "foot" }, h("span", { text: it.source === "import" ? `from ${it.platform || "import"}` : "written by you" }),
        h("span", { text: `updated ${it.updated}` }), it.uses ? h("span", { text: `used ${plural(it.uses, "time")}` }) : null)));
  }
}

async function runPreview() {
  const input = $("#gateQ");
  const box = $("#gateRes");
  if (!input || !box) return;
  const q = input.value.trim();
  if (!q) { box.replaceChildren(); return; }
  const r = await API.gate_preview(q);
  if (!r.ok || input.value.trim() !== q) return;
  const tr = r.trace;
  box.replaceChildren(
    !r.semantic ? h("div", { class: "warn-line" }, icon("warn", "xs"), "Fallback embeddings: this preview isn't representative.") : null,
    tr.abstained ? h("div", { class: "callout abstain" }, h("b", { text: "Nothing would be used. " }), "No class has a memory that clears its floor for this question.") : null,
    tr.admitted.map((it) => gateRow(it, true)),
    tr.dropped.slice(0, 5).map((it) => gateRow(it, false)),
    !tr.admitted.length && !tr.dropped.length && !tr.abstained ? h("p", { class: "empty-note", text: "This question doesn't reach for memory at all." }) : null);
}

function classHint(name) {
  const c = clsOf(name);
  if (!c) return "";
  return `${cap(c.name)} holds ${c.holds}. Floor ${c.floor.toFixed(2)}.${c.private ? " Private: any request that uses it stays on this machine." : ""}`;
}

function openEditor(item) {
  closeDrawer();
  const it = Object.assign({ id: "", cls: "identity", title: "", body: "", tags: [] }, item || {});
  const hint = h("p", { class: "empty-note", text: classHint(it.cls) });
  const clsCtl = h("div", { class: "seg-ctl" }, S.classes.map((c) => h("button", {
    type: "button", class: `cls-${c.name}`, "aria-pressed": String(c.name === it.cls),
    onclick: (e) => {
      it.cls = c.name;
      $$("button", clsCtl).forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget)));
      hint.textContent = classHint(c.name);
    },
  }, h("span", { class: "sw" }), c.name)));
  const title = h("input", { class: "field", value: it.title, placeholder: "A short, specific title" });
  const body = h("textarea", { class: "field", rows: "9", placeholder: "The fact itself: concrete detail, decisions, dates. Written the way you'd want PERCH to remember it." });
  body.value = it.body;
  const tags = h("input", { class: "field", value: (it.tags || []).join(", "), placeholder: "comma, separated, tags" });

  const save = async () => {
    const r = await API.memory_save({ id: it.id, cls: it.cls, title: title.value, body: body.value, tags: tags.value.split(",") });
    if (!r.ok) { toast(r.error, "bad"); return; }
    toast(r.how === "merged" ? "Merged into a memory you already had" : r.how === "updated" ? "Saved" : "Memory added");
    closeDrawer();
    refreshStatus();
    if (S.view === "memory") loadMemory(false);
  };

  const d = h("div", { class: "drawer", id: "drawer", role: "dialog", "aria-label": it.id ? "Edit memory" : "New memory" },
    h("div", { class: "row" }, h("h2", { text: it.id ? "Edit memory" : "New memory" }),
      h("button", { class: "icon-btn", style: "margin-left:auto", type: "button", onclick: closeDrawer, title: "Close (Esc)" }, icon("close"))),
    h("div", { class: "form-row" }, h("label", { text: "Class" }), clsCtl, hint),
    h("div", { class: "form-row" }, h("label", { text: "Title" }), title),
    h("div", { class: "form-row" }, h("label", { text: "What to remember" }), body),
    h("div", { class: "form-row" }, h("label", { text: "Tags" }), tags),
    it.id ? h("p", { class: "empty-note", text: `${it.source === "import" ? `Imported from ${it.platform || "an export"}${it.ref ? ` (“${it.ref}”)` : ""}` : "Written by you"} · updated ${it.updated} · used ${plural(it.uses || 0, "time")}` }) : null,
    h("div", { class: "row" },
      h("button", { class: "btn accent", type: "button", onclick: save }, icon("check", "sm"), "Save"),
      it.id ? h("button", { class: "btn", type: "button", onclick: () => API.memory_open(it.id) }, icon("file", "sm"), "Open file") : null,
      h("span", { style: "flex:1" }),
      it.id ? h("button", { class: "btn danger", type: "button", onclick: () => confirmDialog("Delete this memory?", `“${it.title}” will be deleted from disk. There is no undo.`, "Delete", async () => {
        await API.memory_delete(it.id);
        closeDrawer();
        toast("Deleted");
        refreshStatus();
        loadMemory(false);
      }) }, icon("trash", "sm"), "Delete") : null));
  document.body.append(d);
  (it.title ? body : title).focus();
}

function closeDrawer() {
  const d = $("#drawer");
  if (d) d.remove();
}

async function seedDemo() {
  const r = await API.seed_demo();
  toast(`Demo memory loaded: ${plural(r.created, "item")} added`);
  await refreshStatus();
  if (S.view === "memory") loadMemory(false);
  else renderAsk();
}

async function rebuildIndex() {
  toast("Rebuilding the index…");
  const r = await API.rebuild_index();
  toast(`Index rebuilt: ${plural(r.items, "item")}`);
  refreshStatus();
}

// ================================================================ import

const EXPORT_HELP = [
  ["ChatGPT", "Settings → Data Controls → Export data. You'll get an email with a .zip."],
  ["Claude", "Settings → Privacy → Export data. You'll get an email with an archive."],
  ["Gemini", "takeout.google.com → deselect all → select Gemini. Download the archive."],
];

function renderImport() {
  const I = S.imp;
  const idx = { pick: 0, class: 1, extract: 2, review: 3, done: 4 }[I.step];
  const body = { pick: importPick, class: importClass, extract: importExtract, review: importReview, done: importDone }[I.step]();
  $("#view-import").replaceChildren(h("div", { class: "page" },
    pageHead("Import your history",
      "Bring what ChatGPT, Claude or Gemini already know about you into memory you own. The export is read on this machine, and nothing is saved until you keep it."),
    h("div", { class: "steps" }, [0, 1, 2, 3].map((i) => h("div", { class: "step" + (i <= idx ? " on" : "") }))),
    body));
}

function importPick() {
  const I = S.imp;
  return h("div", {},
    h("div", { class: "export-help" }, EXPORT_HELP.map(([n, t]) => h("div", { class: "card" }, h("b", { text: n }), t))),
    h("div", { class: "drop" },
      icon("import", "lg"),
      h("div", {}, h("b", { text: "Choose the export file" }), h("p", { class: "empty-note", text: "A .zip as emailed, or the conversations .json inside it." })),
      h("button", { class: "btn accent", type: "button", onclick: async () => {
        const r = await API.import_pick();
        if (r.cancelled) return;
        if (!r.ok) { I.error = r.error; renderImport(); return; }
        I.info = r;
        I.error = "";
        I.step = "class";
        renderImport();
      } }, icon("folder", "sm"), "Choose file…"),
      I.error ? h("div", { class: "warn-line" }, icon("warn", "xs"), I.error) : null));
}

function importClass() {
  const I = S.imp;
  const info = I.info;
  const platforms = Object.entries(info.platforms).map(([p, n]) => `${n} from ${cap(p)}`).join(", ");
  const chosen = clsOf(I.cls);
  return h("div", {},
    h("div", { class: "card", style: "padding:13px 15px;display:flex;align-items:center;gap:12px;max-width:760px" },
      icon("file"), h("div", { style: "flex:1;min-width:0" }, h("b", { class: "ellipsis", text: info.name, style: "display:block" }),
        h("span", { class: "empty-note", text: `${plural(info.count, "conversation")} (${platforms}) · ${fmt(info.chars)} characters` })),
      h("button", { class: "btn ghost", type: "button", onclick: () => { I.step = "pick"; renderImport(); } }, "Change")),
    h("h3", { style: "margin:22px 0 4px;font:650 14px var(--font-display)", text: "What kind of memory is in it?" }),
    h("p", { class: "empty-note", style: "max-width:64ch", text: "One class per run, and you choose it. That's what lets PERCH decide later, reliably, when a memory belongs in an answer. Run it again for another class." }),
    h("div", { class: "class-grid" }, S.classes.map((c) => h("button", {
      class: `class-card cls-${c.name}`, type: "button", "aria-pressed": String(I.cls === c.name),
      onclick: () => { I.cls = c.name; renderImport(); },
    }, h("div", { class: "name" }, h("span", { class: "sw" }), c.name), h("div", { class: "holds", text: c.holds }),
      c.private ? h("div", { class: "lock" }, icon("lock", "xs"), "extracted on this machine only") : null))),
    h("div", { class: "row" },
      h("button", { class: "btn accent", type: "button", disabled: !I.cls, onclick: startExtract }, icon("play", "sm"), chosen ? `Find ${chosen.name} memories` : "Choose a class"),
      chosen && chosen.private ? h("span", { class: "empty-note", text: "Private class: extraction never goes to a cloud model." }) : null));
}

async function startExtract() {
  const I = S.imp;
  I.step = "extract";
  I.progress = { n: 0, total: I.info.count, label: "starting…" };
  I.error = "";
  renderImport();
  const r = await API.import_extract(I.info.path, I.cls);
  if (!r.ok) { I.error = r.error; renderImport(); return; }
  I.job = r.job;
}

function importExtract() {
  const I = S.imp;
  const p = I.progress || { n: 0, total: 1 };
  if (I.error) return h("div", { class: "card", style: "padding:16px;max-width:760px;display:grid;gap:10px" },
    h("div", { class: "warn-line" }, icon("warn", "sm"), h("b", { text: "Extraction couldn't run" })),
    h("p", { class: "empty-note", text: I.error }),
    h("div", { class: "row" }, h("button", { class: "btn", type: "button", onclick: () => { I.step = "class"; I.error = ""; renderImport(); } }, icon("back", "sm"), "Back")));
  return h("div", { class: "card", style: "padding:18px;max-width:760px;display:grid;gap:12px" },
    h("b", { text: `Reading ${plural(p.total, "conversation")} for ${I.cls} memories` }),
    h("div", { class: "progress" }, h("div", { style: `width:${p.total ? (p.n / p.total) * 100 : 0}%` })),
    h("div", { class: "empty-note ellipsis", text: `${fmt(p.n)} / ${fmt(p.total)} · ${p.label || ""}` }),
    h("p", { class: "empty-note", text: "A local model is reading each conversation. This can take a while; you can keep using PERCH." }));
}

function importReview() {
  const I = S.imp;
  const props = I.proposals;
  if (!props.length) return h("div", { class: "card", style: "padding:18px;max-width:760px;display:grid;gap:10px" },
    h("b", { text: "Nothing worth keeping was found." }),
    h("p", { class: "empty-note", text: `The model didn't find ${I.cls} memories in these conversations. Try another class.` }),
    h("div", { class: "row" }, h("button", { class: "btn", type: "button", onclick: () => { I.step = "class"; renderImport(); } }, icon("back", "sm"), "Choose another class")));

  const keep = Object.values(I.dec).filter((d) => d.keep).length;
  const decided = Object.keys(I.dec).length;
  const p = props[I.cur];
  const dec = I.dec[p.index] || {};
  const title = h("input", { class: "ttl", value: dec.title || p.title, "aria-label": "Title (editable)",
    oninput: (e) => { I.dec[p.index] = Object.assign(I.dec[p.index] || {}, { title: e.target.value }); } });

  const decide = (k) => {
    I.dec[p.index] = Object.assign(I.dec[p.index] || {}, { keep: k, title: title.value });
    const next = props.findIndex((q, i) => i > I.cur && I.dec[q.index] == null);
    I.cur = next >= 0 ? next : Math.min(I.cur + 1, props.length - 1);
    renderImport();
  };
  const bulk = (k) => { for (const q of props) if (I.dec[q.index] == null) I.dec[q.index] = { keep: k }; renderImport(); };
  S.imp.keys = { keep: () => decide(true), skip: () => decide(false), prev: () => { I.cur = Math.max(0, I.cur - 1); renderImport(); }, next: () => { I.cur = Math.min(props.length - 1, I.cur + 1); renderImport(); } };

  return h("div", { class: "deck" },
    h("div", { class: "row", style: "flex-wrap:wrap" },
      h("b", { text: `${plural(props.length, "proposal")} · ${keep} kept · ${props.length - decided} left` }),
      h("span", { class: "empty-note", text: "Nothing is saved until you press Save." })),
    I.uncal ? h("div", { class: "warn-line" }, icon("warn", "xs"), `Every item came back at confidence ${props[0].confidence.toFixed(2)}. The model isn't estimating confidence here, so ignore that number and judge each one yourself.`) : null,
    h("div", { class: "honest", style: "margin:0" }, "These are the model's paraphrases of your conversations, not quotes. Small models get details wrong and sometimes invent outcomes that were never said. That's what this review is for."),
    h("div", { class: "pips" }, props.map((q, i) => h("span", { class: [I.dec[q.index] ? (I.dec[q.index].keep ? "keep" : "skip") : "", i === I.cur ? "cur" : ""].join(" "), title: q.title }))),
    h("div", { class: `card proposal cls-${p.cls}` },
      h("div", { class: "row" }, h("span", { class: "tag cls", text: p.cls }), h("span", { class: "empty-note", text: `${I.cur + 1} of ${props.length}` }),
        dec.keep != null ? h("span", { class: "tag", text: dec.keep ? "keeping" : "skipping" }) : null),
      title,
      h("div", { class: "pbody", text: p.body }),
      h("div", { class: "meta", style: "margin:0" },
        p.tags.map((t) => h("span", { class: "tag", text: t })),
        h("span", { text: `from ${cap(p.platform || "export")}${p.session ? ` · “${p.session}”` : ""}` })),
      p.warnings.map((w) => h("div", { class: "warn-line" }, icon("warn", "xs"), w))),
    h("div", { class: "deck-nav" },
      h("button", { class: "btn", type: "button", onclick: () => decide(false), title: "Skip (S)" }, icon("close", "sm"), "Skip", h("kbd", { text: "S" })),
      h("button", { class: "btn accent", type: "button", onclick: () => decide(true), title: "Keep (K)" }, icon("check", "sm"), "Keep", h("kbd", { text: "K" })),
      h("span", { style: "flex:1" }),
      h("button", { class: "btn ghost", type: "button", onclick: () => bulk(true) }, "Keep the rest"),
      h("button", { class: "btn ghost", type: "button", onclick: () => bulk(false) }, "Skip the rest")),
    h("div", { class: "row", style: "border-top:1px solid var(--line);padding-top:14px" },
      h("button", { class: "btn primary", type: "button", disabled: !keep, onclick: commitImport }, icon("check", "sm"), keep ? `Save ${plural(keep, "memory", "memories")}` : "Nothing kept yet"),
      h("button", { class: "btn ghost", type: "button", onclick: () => confirmDialog("Discard this import?", "None of these proposals will be saved.", "Discard", () => { resetImport(); renderImport(); }) }, "Discard")));
}

async function commitImport() {
  const I = S.imp;
  const decisions = I.proposals.map((p) => ({ index: p.index, keep: !!(I.dec[p.index] && I.dec[p.index].keep), title: (I.dec[p.index] || {}).title || "" }));
  const r = await API.import_commit(decisions);
  if (!r.ok) { toast(r.error, "bad"); return; }
  I.summary = r.summary;
  I.step = "done";
  refreshStatus();
  renderImport();
}

function importDone() {
  const s = S.imp.summary || { created: [], merged: [] };
  return h("div", { class: "card", style: "padding:20px;max-width:760px;display:grid;gap:12px" },
    h("b", { style: "font:650 16px var(--font-display)", text: "Saved to your memory" }),
    h("div", { class: "stat-row" },
      h("div", { class: "stat" }, h("b", { text: fmt(s.created.length) }), h("span", { text: "new memories" })),
      h("div", { class: "stat" }, h("b", { text: fmt(s.merged.length) }), h("span", { text: "merged into ones you had" })),
      h("div", { class: "stat" }, h("b", { text: fmt(s.rejected || 0) }), h("span", { text: "skipped" }))),
    s.merged.length ? h("p", { class: "empty-note", text: "Merged means the fact was already stored, so the existing memory was updated instead of gaining a rival copy." }) : null,
    h("div", { class: "row" },
      h("button", { class: "btn accent", type: "button", onclick: () => { S.mem.cls = S.imp.cls; resetImport(); setView("memory"); } }, icon("memory", "sm"), "See them in Memory"),
      h("button", { class: "btn", type: "button", onclick: () => { resetImport(); renderImport(); } }, "Import more")));
}

function resetImport() {
  Object.assign(S.imp, { step: "pick", info: null, cls: "", job: null, progress: null, proposals: [], dec: {}, cur: 0, uncal: false, summary: null, error: "" });
}

// ================================================================ evaluation

const EVALS = [
  { name: "e1", title: "Over-personalisation", sub: "Does memory stay quiet when a question doesn't need it? An OP-style probe, not OP-Bench itself.", cost: "minutes · local model + judge" },
  { name: "e2", title: "Budget assembly (C1)", sub: "Memory and tool results sharing one context window, at three model sizes.", cost: "instant" },
  { name: "e3", title: "Retrieval quality", sub: "LongMemEval and LoCoMo.", cost: "needs datasets" },
  { name: "e4", title: "Admission gate (C2)", sub: "Leaked memories against useful context kept, with and without per-class floors.", cost: "seconds" },
  { name: "e5", title: "Privacy: zero egress", sub: "Does a private request open any connection off this machine?", cost: "seconds" },
  { name: "e6", title: "Latency", sub: "How long PERCH's own retrieval takes before the model starts.", cost: "~10 s" },
  { name: "e7", title: "UI Automation coverage", sub: "Which apps expose their selected text.", cost: "manual" },
];

async function loadEval() {
  if (!S.evals.loaded) {
    try { S.evals.results.e1 = await API.eval_saved(); } catch (e) { /* no saved run */ }
    S.evals.loaded = true;
  }
  renderEval();
}

function runEval(names) {
  if (S.evals.job) { toast("An evaluation is already running."); return; }
  names.forEach((n) => S.evals.running.add(n));
  API.eval_run(names).then((r) => { S.evals.job = r.job; renderEval(); });
  renderEval();
}

function renderEval() {
  const E = S.evals;
  $("#view-eval").replaceChildren(h("div", { class: "page" },
    pageHead("Evaluate",
      "The experiments from the architecture's evaluation plan, run on this machine. All seven are always listed, including the ones that can't run here, so the evidence isn't mistaken for complete.",
      h("button", { class: "btn accent", type: "button", disabled: !!E.job, onclick: () => runEval(["e2", "e4", "e5", "e6"]) }, icon("play", "sm"), "Run quick checks")),
    h("div", { class: "honest" }, h("b", { text: "Read these as what they are. " }),
      "Nothing here is a benchmark score unless it says it ran. E1 uses PERCH's own 24 probes and a local judge model, because OP-Bench's data hasn't been released; its result says something about PERCH, not about OP-Bench."),
    E.job ? h("div", { class: "row", style: "margin-bottom:14px" }, h("span", { class: "badge running", text: "RUNNING" }), h("span", { class: "empty-note ellipsis", text: E.progress || "" })) : null,
    h("div", { class: "eval-grid" }, EVALS.map((e) => evalCard(e)))));
}

function evalCard(e) {
  const E = S.evals;
  const r = E.results[e.name];
  const running = E.running.has(e.name);
  const badge = running ? h("span", { class: "badge running", text: "RUNNING" })
    : r ? h("span", { class: `badge ${r.ran ? "ran" : "not"}`, text: r.ran ? "RAN" : "NOT RUN" }) : null;
  const runnable = !["e3", "e7"].includes(e.name);
  return h("div", { class: "card eval" },
    h("div", { class: "top" },
      h("span", { class: "name", text: e.name.toUpperCase() }),
      h("div", { style: "flex:1;min-width:0" }, h("div", { class: "title", text: e.title }), h("div", { class: "sub", text: e.sub })),
      h("span", { class: "cost", text: e.cost }), badge,
      runnable ? h("button", { class: "btn", type: "button", disabled: !!E.job, onclick: () => {
        if (e.name === "e1") confirmDialog("Run E1 now?", "It generates and judges about 70 answers with local models — a few minutes on a GPU, closer to 15 on a CPU. You can keep using PERCH meanwhile.", "Run E1", () => runEval(["e1"]), "accent");
        else runEval([e.name]);
      } }, icon("play", "sm"), "Run") : null),
    r && r.ran && r.verdict ? h("div", { class: "verdict", text: r.verdict }) : null,
    r && !r.ran && r.reason ? h("div", { class: "reason", text: r.reason }) : null,
    r && r.lines && r.lines.length ? h("details", { class: "raw" }, h("summary", { text: "Full output" }), h("pre", { text: r.lines.join("\n") })) : null);
}

// ================================================================ jobs

function onJob(ev) {
  if (ev.kind === "import" && ev.job === S.imp.job) {
    const I = S.imp;
    if (ev.state === "start" || ev.state === "progress") {
      I.progress = { n: ev.n || 0, total: ev.total || (I.progress && I.progress.total) || 1, label: ev.label };
      if (ev.state === "start") I.model = ev.label;
    } else if (ev.state === "done") {
      I.job = null;
      I.proposals = ev.proposals || [];
      I.uncal = !!ev.uncalibrated;
      I.dec = {};
      I.cur = 0;
      I.step = "review";
    } else if (ev.state === "error") {
      I.job = null;
      I.error = ev.message;
    }
    if (S.view === "import") renderImport();
  } else if (ev.kind === "eval") {
    const E = S.evals;
    if (ev.state === "progress") E.progress = ev.label;
    else if (ev.state === "result") {
      const key = (ev.result.name || "").toLowerCase();
      E.results[key] = ev.result;
      E.running.delete(key);
    } else if (ev.state === "done") {
      E.job = null;
      E.running.clear();
      E.progress = "";
    }
    if (S.view === "eval") renderEval();
  }
}

// ================================================================ settings

async function loadSettings() {
  S.set = await API.settings_get();
  renderSettings();
}

function setRow(title, sub, control) {
  return h("div", { class: "set-row" }, h("div", { class: "txt" }, h("b", { text: title }), sub ? h("span", { text: sub }) : null), control);
}

function toggle(key, value, locked) {
  return h("button", {
    class: "switch", type: "button", role: "switch", "aria-checked": String(!!value), disabled: !!locked,
    title: locked ? `Set by the ${locked} environment variable` : "",
    onclick: async (e) => {
      const next = e.currentTarget.getAttribute("aria-checked") !== "true";
      const r = await API.settings_save({ [key]: next });
      S.settings = r.values;
      S.set.values = r.values;
      S.set.login = r.login;
      if (key === "private_by_default") { S.private = next; applyPrivacy(); renderTitlebar(); }
      renderSettings();
    },
  });
}

function renderSettings() {
  const T = S.set;
  const v = T.values;
  const locked = T.locked || {};
  const routeCtl = h("div", { class: "seg-ctl" }, ["auto", "local", "cloud"].map((r) => h("button", {
    type: "button", "aria-pressed": String(v.default_route === r), disabled: !!locked.default_route,
    onclick: async () => {
      const res = await API.settings_save({ default_route: r });
      S.settings = res.values;
      T.values = res.values;
      S.route = r;
      renderTitlebar();
      renderSettings();
    },
  }, r)));

  const ruleEditor = (key, label, placeholder, help) => {
    const list = T.rules[key] || [];
    const save = async (next) => { const r = await API.rules_save(Object.assign({}, T.rules, { [key]: next })); T.rules = r.rules; renderSettings(); };
    return h("div", { class: "rule-group" }, h("b", { text: label }),
      h("div", { class: "rule-list" },
        list.map((x) => h("span", { class: "rule" }, x, h("button", { type: "button", title: "Remove", onclick: () => save(list.filter((y) => y !== x)) }, icon("close", "xs")))),
        h("input", { class: "field rule-add", placeholder, onkeydown: (e) => {
          if (e.key === "Enter" && e.target.value.trim()) { save([...list, e.target.value.trim()]); }
        } })),
      h("p", { class: "empty-note", style: "margin-top:6px", text: help }));
  };

  const keys = T.hotkeys || {};
  $("#view-settings").replaceChildren(h("div", { class: "page" },
    pageHead("Settings", "Everything here is stored in plain files under your PERCH folder."),

    h("div", { class: "set-group" }, h("h3", { text: "Models" }), h("div", { class: "set-card" },
      setRow("Default route", locked.default_route ? `Set by ${locked.default_route}.` : "Auto uses a model on this machine when one is running, and a cloud model otherwise.", routeCtl),
      T.models.map((m) => setRow(m.stub ? "No model reachable" : m.id,
        m.stub ? "Start Ollama (ollama serve) for real answers." : `${m.local ? "On this machine" : "Cloud"} · ${fmt(m.window)}-token window`,
        h("div", { class: "row" }, h("span", { class: `dot ${m.stub ? "stub" : m.local ? "local" : "cloud"}` }),
          m.tools ? h("span", { class: "tag", text: "tools" }) : null, m.vision ? h("span", { class: "tag", text: "vision" }) : null))))),

    h("div", { class: "set-group" }, h("h3", { text: "Privacy" }), h("div", { class: "set-card" },
      setRow("Private by default", locked.private_by_default ? `Set by ${locked.private_by_default}.` : "Every request stays on this machine unless you switch Private off for it.", toggle("private_by_default", v.private_by_default, locked.private_by_default)),
      h("div", { class: "rules" },
        h("p", { class: "empty-note", text: "Private source rules decide by where the text came from, never by reading it. A match keeps the request on this machine." }),
        ruleEditor("apps", "Applications", "e.g. keepass*", "Matched against the program's name, like keepassxc or outlook."),
        ruleEditor("titles", "Window titles", "e.g. *confidential*", "Matched against the window's title, so a document name can make it private."),
        ruleEditor("folders", "Folders", "e.g. C:/Users/you/Medical", "Files inside these folders stay private.")))),

    h("div", { class: "set-group" }, h("h3", { text: "Conversations" }), h("div", { class: "set-card" },
      setRow("Keep conversations", "Saved on this machine so you can reopen them. Never used as memory.", toggle("keep_sessions", v.keep_sessions)),
      setRow("Keep private conversations too", "Off by default: a private request never left this machine, and its transcript shouldn't outlive the window unless you ask.", toggle("keep_private_sessions", v.keep_private_sessions)),
      setRow("How many to keep", "The oldest are deleted first.", h("input", { class: "field", type: "number", min: "10", max: "5000", value: String(v.session_cap), style: "width:90px",
        onchange: async (e) => { const r = await API.settings_save({ session_cap: e.target.value }); T.values = r.values; S.settings = r.values; toast("Saved"); } })))),

    h("div", { class: "set-group" }, h("h3", { text: "Window and startup" }), h("div", { class: "set-card" },
      setRow("Remember where I put the panel", "Off: the panel always opens beside the app you're in.", toggle("remember_position", v.remember_position)),
      setRow("Start PERCH when I sign in", "Runs quietly in the tray. Uses your user account's startup list, so no admin rights are needed.", toggle("launch_at_login", T.login)))),

    h("div", { class: "set-group" }, h("h3", { text: "Shortcuts" }), h("div", { class: "set-card" },
      setRow("Ask about the selection", "Reads what you've selected in the app you're in.", h("span", { class: "kbd", text: keys.selection || "not registered" })),
      setRow("Screenshot and ask", "Drag a region; its text is read on this machine.", h("span", { class: "kbd", text: keys.screenshot || "not registered" })),
      setRow("Ask anything", "Opens the panel with nothing selected.", h("span", { class: "kbd", text: keys.plain || "not registered" })),
      h("div", { class: "set-row" }, h("p", { class: "empty-note", text: "To change a shortcut, set PERCH_HOTKEY_SELECTION, PERCH_HOTKEY_SCREENSHOT or PERCH_HOTKEY_PLAIN and restart. `python -m app hotkeys` shows which combinations are free." })))),

    h("div", { class: "set-group" }, h("h3", { text: "Data" }), h("div", { class: "set-card" },
      setRow("Your PERCH folder", T.paths.home, h("button", { class: "btn", type: "button", onclick: () => API.open_folder("home") }, icon("folder", "sm"), "Open")),
      setRow("Rebuild the memory index", "Re-reads every memory file. Do this after switching embedding model.", h("button", { class: "btn", type: "button", onclick: rebuildIndex }, icon("refresh", "sm"), "Rebuild")),
      setRow("Find duplicate memories", "Near-identical memories in the same class, merged into one.", h("button", { class: "btn", type: "button", onclick: findDuplicates }, icon("search", "sm"), "Find")),
      setRow("Demo memory", "Adds a small example profile so you can see how the gate behaves.", h("button", { class: "btn", type: "button", onclick: seedDemo }, "Load")))),

    h("div", { class: "set-group" }, h("h3", { text: "About" }), h("div", { class: "set-card" },
      setRow(`PERCH ${T.version}`, `Embeddings: ${T.embeddings} · Screenshot text: ${T.ocr ? `Windows OCR (${T.ocr})` : "unavailable"}`,
        h("button", { class: "btn danger", type: "button", onclick: () => confirmDialog("Quit PERCH?", "Shortcuts stop working until you start it again.", "Quit", () => API.quit()) }, icon("power", "sm"), "Quit PERCH"))))));
}

async function findDuplicates() {
  const r = await API.dedupe(false);
  if (!r.groups.length) { toast(`No duplicates among ${plural(r.total, "memory", "memories")}`); return; }
  const n = r.groups.reduce((a, g) => a + g.remove, 0);
  openModal({
    title: `${plural(n, "duplicate")} found`, iconName: "memory",
    body: h("div", { style: "display:grid;gap:6px" },
      h("p", { text: "Each group is merged into one memory; tags are combined, nothing else is lost." }),
      h("div", { class: "call" }, r.groups.map((g) => `${g.cls}: ${g.keep}  (+${g.remove})`).join("\n"))),
    actions: [{ label: "Cancel" }, { label: "Merge", kind: "accent", onClick: async () => {
      const done = await API.dedupe(true);
      toast(`Merged. ${plural(done.total, "memory", "memories")} now.`);
      refreshStatus();
    } }],
  });
}

// ================================================================ overlays

let escHandler = null;
function openModal({ title, iconName, body, actions, onEsc }) {
  const m = $("#modal");
  const card = h("div", { class: "modal-card", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("h3", {}, iconName ? icon(iconName) : null, title), body,
    h("div", { class: "row" }, actions.map((a) => h("button", {
      class: "btn " + (a.kind || ""), type: "button", onclick: () => { closeModal(); if (a.onClick) a.onClick(); },
    }, a.label))));
  m.replaceChildren(card);
  m.hidden = false;
  escHandler = onEsc || (() => {});
  const first = card.querySelector(".row .btn");
  if (first) first.focus();
}

function closeModal() {
  const m = $("#modal");
  m.hidden = true;
  m.replaceChildren();
  escHandler = null;
}

function confirmDialog(title, text, verb, fn, kind = "danger-solid") {
  openModal({ title, body: h("p", { text }), actions: [{ label: "Cancel" }, { label: verb, kind, onClick: fn }], onEsc: () => {} });
}

let toastTimer = null;
function toast(text, kind = "") {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast" + (kind ? ` ${kind}` : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

// ================================================================ keyboard

function typing(e) {
  const t = e.target;
  return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
}

function bindKeys() {
  document.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (!$("#modal").hidden) {
      if (e.key === "Escape") { const f = escHandler; closeModal(); if (f) f(); e.preventDefault(); }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if ($("#drawer")) closeDrawer();
      else if (S.why) { S.why = false; renderWhy(); renderInspector(); }
      else API.hide();
      return;
    }
    if (e.key === "F5" || (e.ctrlKey && k === "r")) { e.preventDefault(); return; }
    if (e.ctrlKey && e.key === "Enter" && S.view === "ask") { e.preventDefault(); deliver(e.shiftKey ? "insert_after" : "replace"); return; }
    if (e.ctrlKey && e.shiftKey && k === "c" && S.view === "ask") { e.preventDefault(); deliver("copy_only"); return; }
    if (e.ctrlKey && !e.shiftKey && k === "e") { e.preventDefault(); setMode(S.mode === "expanded" ? "compact" : "expanded"); return; }
    if (e.ctrlKey && !e.shiftKey && k === "p") { e.preventDefault(); togglePrivate(); return; }
    if (e.ctrlKey && !e.shiftKey && k === "n") { e.preventDefault(); setView("ask"); newChat(); return; }
    if (e.ctrlKey && /^[1-6]$/.test(e.key)) { e.preventDefault(); setView(VIEWS[+e.key - 1][0]); return; }
    if (S.view === "import" && S.imp.step === "review" && !typing(e) && S.imp.keys) {
      if (k === "k") S.imp.keys.keep();
      else if (k === "s") S.imp.keys.skip();
      else if (e.key === "ArrowLeft") S.imp.keys.prev();
      else if (e.key === "ArrowRight") S.imp.keys.next();
    }
  });
}

function bindGrip() {
  const g = $("#grip");
  let origin = null;
  let last = 0;
  g.addEventListener("pointerdown", (e) => {
    origin = { x: e.screenX, y: e.screenY };
    g.setPointerCapture(e.pointerId);
    API.grip(0, 0, "start");
    e.preventDefault();
  });
  g.addEventListener("pointermove", (e) => {
    if (!origin) return;
    const now = performance.now();
    if (now - last < 30) return;
    last = now;
    API.grip(e.screenX - origin.x, e.screenY - origin.y, "move");
  });
  const end = (e) => {
    if (!origin) return;
    API.grip(e.screenX - origin.x, e.screenY - origin.y, "end");
    origin = null;
  };
  g.addEventListener("pointerup", end);
  g.addEventListener("pointercancel", end);
}

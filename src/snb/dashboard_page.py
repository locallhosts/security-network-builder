"""Single-page dashboard (vanilla JS, no CDN, no external requests).

All GitHub-sourced text (bios, descriptions, names) is untrusted: it is only
ever inserted with textContent / createTextNode, never innerHTML, and links are
restricted to https://github.com/.
"""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Security Network Builder</title>
<style nonce="__NONCE__">
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f6f6f4;--line:#ddd;--acc:#2a6df4}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#9a9a9a;--card:#202020;--line:#333;--acc:#6ea0ff}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:12px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:16px;margin:0 12px 0 0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:0 0 8px}
main{display:grid;grid-template-columns:minmax(380px,1fr) minmax(380px,1fr);gap:16px;padding:16px}
@media(max-width:900px){main{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover,tr.sel{background:rgba(120,120,120,.15)}
a{color:var(--acc)}input,select,button{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:4px 8px}
button{cursor:pointer}.chip{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:10px;padding:0 7px;margin:1px 2px 1px 0}
.new{background:var(--acc);color:#fff;border-radius:4px;font-size:10px;padding:0 4px;margin-left:4px}
.mut{color:var(--mut)}.bar{height:6px;background:var(--acc);border-radius:3px}svg{width:100%;height:340px;background:var(--bg);border:1px solid var(--line);border-radius:6px}
ul{margin:4px 0 8px;padding-left:18px}.grid2{display:grid;gap:16px}
</style></head><body>
<header><h1>Security Network Builder</h1>
<label>Run <select id="run"></select></label>
<label>Area <select id="domain"><option value="">All</option></select></label>
<label>Status <select id="statusf"><option value="">All</option><option value="new">New this run</option><option value="reviewing">Reviewing</option><option value="connected">Connected</option><option value="ignored">Ignored</option></select></label>
<input id="q" placeholder="Search login or repo" aria-label="Search">
<span id="meta" class="mut"></span></header>
<main>
<div class="grid2">
<section><h2>Ranking</h2><div id="table"></div></section>
<section><h2>Changes since previous run</h2><div id="diff"></div></section>
<section><h2>Organizations</h2><div id="orgs"></div></section>
</div>
<div class="grid2">
<section><h2>Relationship graph</h2><svg id="graph" viewBox="0 0 600 340" role="img" aria-label="Engineer relationship graph"></svg><div id="legend" class="mut"></div></section>
<section><h2>Engineer</h2><div id="detail" class="mut">Select an engineer in the table or graph.</div></section>
</div></main>
<script nonce="__NONCE__">
(() => {
const CSRF = "__CSRF__";
const STATUSES = ["", "new", "reviewing", "connected", "ignored"];
const $ = s => document.querySelector(s);
const safeUrl = u => (typeof u === "string" && u.startsWith("https://github.com/")) ? u : "#";
const SVGNS = "http://www.w3.org/2000/svg";
function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}
function sv(tag, attrs, text) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
const color = c => `hsl(${((c ?? 0) * 67) % 360} 60% 50%)`;
let data = null, selected = null, runsList = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

function filtered() {
  const d = $("#domain").value, s = $("#statusf").value, q = $("#q").value.trim().toLowerCase();
  return data.recommendations.filter(r =>
    (!d || r.matched_domains.includes(d)) &&
    (!s || (s === "new" ? r.is_new : r.status === s)) &&
    (!q || r.login.toLowerCase().includes(q) || r.matched_repos.some(x => (x.name || "").toLowerCase().includes(q))));
}

function renderTable() {
  const rows = filtered();
  const t = el("table", {}, el("tr", {}, ["#", "Engineer", "Score", "Areas", "Status"].map(h => el("th", {}, h))));
  rows.forEach((r, i) => {
    const login = el("td", {}, el("a", { href: safeUrl(r.url), target: "_blank", rel: "noopener noreferrer" }, "@" + r.login), r.is_new ? el("span", { class: "new" }, "new") : null);
    const st = r.status || "";
    t.append(el("tr", { class: "row" + (r.login === selected ? " sel" : ""), onclick: () => select(r.login) },
      el("td", {}, i + 1), login, el("td", {}, r.score),
      el("td", {}, r.matched_domains.map(d => el("span", { class: "chip" }, d))), el("td", { class: "mut" }, st)));
  });
  $("#table").replaceChildren(rows.length ? t : el("div", { class: "mut" }, "No engineers match the filters."));
  $("#meta").textContent = `${rows.length} of ${data.recommendations.length} shown`;
}

function renderOrgs() {
  const orgs = data.organizations.slice(0, 12);
  if (!orgs.length) return $("#orgs").replaceChildren(el("div", { class: "mut" }, "No public organization memberships found."));
  const t = el("table", {}, el("tr", {}, ["Org", "Engineers", "Total", "Areas"].map(h => el("th", {}, h))));
  orgs.forEach(o => t.append(el("tr", {},
    el("td", {}, el("a", { href: safeUrl(o.url), target: "_blank", rel: "noopener noreferrer" }, o.login)),
    el("td", {}, o.members.map(m => "@" + m).join(", ")), el("td", {}, o.total_score), el("td", { class: "mut" }, o.top_domains.join(", ")))));
  $("#orgs").replaceChildren(t);
}

function layout(nodes, edges, W, H) {
  const n = nodes.length, idx = new Map(nodes.map((nd, i) => [nd.login, i]));
  const p = nodes.map((_, i) => ({ x: W / 2 + Math.cos(2 * Math.PI * i / n) * W / 3, y: H / 2 + Math.sin(2 * Math.PI * i / n) * H / 3, vx: 0, vy: 0 }));
  for (let it = 0; it < 300; it++) {
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      let dx = p[i].x - p[j].x, dy = p[i].y - p[j].y, d2 = Math.max(dx * dx + dy * dy, 25), f = 1800 / d2, d = Math.sqrt(d2);
      p[i].vx += dx / d * f; p[i].vy += dy / d * f; p[j].vx -= dx / d * f; p[j].vy -= dy / d * f;
    }
    for (const e of edges) {
      const a = p[idx.get(e.a)], b = p[idx.get(e.b)]; if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.max(Math.sqrt(dx * dx + dy * dy), 1), f = 0.01 * (d - 70) * Math.min(e.weight, 8) / 4;
      a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
    }
    for (const q of p) {
      q.vx += (W / 2 - q.x) * 0.004; q.vy += (H / 2 - q.y) * 0.004;
      q.x = Math.min(W - 20, Math.max(20, q.x + q.vx)); q.y = Math.min(H - 20, Math.max(20, q.y + q.vy)); q.vx *= 0.8; q.vy *= 0.8;
    }
  }
  return new Map(nodes.map((nd, i) => [nd.login, p[i]]));
}

function renderGraph() {
  const g = data.graph, svg = $("#graph"); svg.replaceChildren();
  if (!g.nodes.length) return;
  const pos = layout(g.nodes, g.edges, 600, 340), vis = new Set(filtered().map(r => r.login));
  for (const e of g.edges) {
    const a = pos.get(e.a), b = pos.get(e.b); if (!a || !b) continue;
    const l = sv("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: "currentColor", "stroke-opacity": vis.has(e.a) && vis.has(e.b) ? 0.35 : 0.08, "stroke-width": Math.min(1 + e.weight / 3, 4) });
    l.append(sv("title", {}, e.reasons.join("; "))); svg.append(l);
  }
  const maxScore = Math.max(...g.nodes.map(n => n.score), 1);
  for (const nd of g.nodes) {
    const p = pos.get(nd.login), r = 5 + 11 * nd.score / maxScore;
    const c = sv("circle", { cx: p.x, cy: p.y, r, fill: color(nd.community), "fill-opacity": vis.has(nd.login) ? 0.9 : 0.2, stroke: nd.login === selected ? "currentColor" : "none", "stroke-width": 2, style: "cursor:pointer" });
    c.append(sv("title", {}, `@${nd.login}  score ${nd.score}  centrality ${nd.centrality}`));
    c.addEventListener("click", () => select(nd.login)); svg.append(c);
    if (nd.centrality >= 0.6 || nd.login === selected) svg.append(sv("text", { x: p.x + r + 3, y: p.y + 4, "font-size": 10, fill: "currentColor" }, nd.login));
  }
  $("#legend").replaceChildren(...data.graph.communities.filter(c => c.size > 1).map(c =>
    el("span", { class: "chip", style: `border-color:${color(c.id)}` }, `Community ${c.id + 1}: ${c.top_domain || "mixed"} (${c.size})`)),
    el("div", {}, "Edges: shared repos, shared orgs, overlapping areas. Node size = score."));
}

async function select(login) {
  selected = login; renderTable(); renderGraph();
  const r = data.recommendations.find(x => x.login === login); if (!r) return;
  const box = $("#detail"); box.className = "";
  const max = Math.max(...Object.values(r.breakdown), 1);
  const stSel = el("select", {}, STATUSES.map(s => { const o = el("option", { value: s }, s || "(none)"); if (s === (r.status || "")) o.selected = true; return o; }));
  const note = el("input", { placeholder: "Private note (stored locally)", maxlength: "500", value: r.note || "" });
  const msg = el("span", { class: "mut" });
  const save = el("button", { onclick: async () => {
    try {
      await api("/api/status", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF }, body: JSON.stringify({ login, status: stSel.value, note: note.value }) });
      r.status = stSel.value; r.note = note.value; msg.textContent = "Saved."; renderTable();
    } catch (e) { msg.textContent = "Error: " + e.message; }
  } }, "Save");
  const p = r.profile || {};
  box.replaceChildren(
    el("h3", { style: "margin:0" }, el("a", { href: safeUrl(r.url), target: "_blank", rel: "noopener noreferrer" }, "@" + r.login), " ", p.name || ""),
    el("div", { class: "mut" }, [p.bio, p.company, p.location].filter(Boolean).join(" · ")),
    el("p", {}, r.explanation || ""),
    el("h2", {}, "Score " + r.score),
    ...Object.entries(r.breakdown).map(([k, v]) => el("div", {}, `${k} +${v}`, el("div", { class: "bar", style: `width:${(100 * v / max).toFixed(0)}%` }))),
    el("h2", { style: "margin-top:10px" }, "Evidence"), el("ul", {}, r.evidence.map(e => el("li", {}, e))),
    el("h2", {}, "Matching repositories"), el("ul", {}, r.matched_repos.map(x => el("li", {}, el("a", { href: safeUrl(x.url), target: "_blank", rel: "noopener noreferrer" }, x.name), ` ★${x.stars}`, x.language ? ` · ${x.language}` : ""))),
    el("h2", {}, "Triage (your decision, nothing is sent to GitHub)"), el("div", {}, stSel, " ", note, " ", save, " ", msg),
    el("h2", { style: "margin-top:10px" }, "History"), el("div", { id: "hist", class: "mut" }, "Loading…"));
  try {
    const h = await api("/api/engineer/" + encodeURIComponent(login));
    $("#hist").textContent = h.history.map(x => `run ${x.run_id} (${x.created_at.slice(0, 10)}): ${x.score}`).join("  →  ") || "Only in this run.";
  } catch (e) { $("#hist").textContent = ""; }
}

async function renderDiff(id) {
  const box = $("#diff"), prev = runsList[runsList.findIndex(r => String(r.id) === String(id)) + 1];
  if (!prev) return box.replaceChildren(el("div", { class: "mut" }, "First recorded run: nothing to compare yet."));
  try {
    const d = await api(`/api/diff?base=${encodeURIComponent(prev.id)}&run=${encodeURIComponent(id)}`);
    const here = new Set(data.recommendations.map(r => r.login));
    const who = (login, text) => here.has(login)
      ? el("a", { href: "#", onclick: e => { e.preventDefault(); select(login); } }, "@" + login + text)
      : el("span", {}, "@" + login + text);
    const line = (label, items, fmt) => el("div", {}, el("b", {}, label + " "),
      items.length ? items.map((x, i) => [i ? ", " : "", fmt(x)]) : el("span", { class: "mut" }, "none"));
    box.replaceChildren(el("div", { class: "mut" }, `Run #${d.base} → #${d.run}`),
      line("New:", d.new, x => who(x.login, ` (${x.score})`)),
      line("Dropped:", d.dropped, x => who(x.login, ` (${x.score})`)),
      line("Score movers:", d.movers, m => who(m.login, ` ${m.from}→${m.to} (${m.delta > 0 ? "+" : ""}${m.delta})`)));
  } catch (e) { box.textContent = "Could not load changes: " + e.message; }
}

async function loadRun(id) {
  data = await api("/api/runs/" + id);
  const doms = [...new Set(data.recommendations.flatMap(r => r.matched_domains))].sort();
  $("#domain").replaceChildren(el("option", { value: "" }, "All"), ...doms.map(d => el("option", { value: d }, d)));
  selected = null; renderTable(); renderOrgs(); renderGraph(); renderDiff(id);
  $("#detail").className = "mut"; $("#detail").textContent = "Select an engineer in the table or graph.";
}

async function init() {
  try {
    const runs = (await api("/api/runs")).runs; runsList = runs;
    if (!runs.length) { $("#table").textContent = "No runs yet. Run: python src/main.py"; return; }
    $("#run").replaceChildren(...runs.map(r => el("option", { value: r.id }, `#${r.id} · ${r.created_at.slice(0, 16)} · ${r.count} engineers`)));
    $("#run").addEventListener("change", e => loadRun(e.target.value));
    for (const id of ["#domain", "#statusf"]) $(id).addEventListener("change", () => { renderTable(); renderGraph(); });
    $("#q").addEventListener("input", () => { renderTable(); renderGraph(); });
    await loadRun(runs[0].id);
  } catch (e) { $("#table").textContent = "Failed to load: " + e.message; }
}
init();
})();
</script></body></html>
"""

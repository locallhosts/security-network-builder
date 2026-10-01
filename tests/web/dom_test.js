// Drives the real dashboard page in jsdom against a live local server.
// Usage: node dom_test.js http://127.0.0.1:PORT/
// jsdom is a DOM, not a browser: it does not do layout, CSS, or CSP enforcement
// (CSP headers are asserted separately in tests/test_dashboard.py).
const { JSDOM } = require("jsdom");
const assert = require("assert");

const base = process.argv[2];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, label, ms = 5000) {
  const t = Date.now();
  while (Date.now() - t < ms) { if (fn()) return; await sleep(20); }
  throw new Error("timed out waiting for: " + label);
}
const fire = (w, el, type) => el.dispatchEvent(new w.Event(type, { bubbles: true }));

(async () => {
  const dom = await JSDOM.fromURL(base, {
    runScripts: "dangerously",
    pretendToBeVisual: true,
    beforeParse(w) {
      w.__pwned = 0;
      w.alert = () => { w.__pwned = 1; };
      w.fetch = (u, o) => fetch(new URL(u, base), o);   // jsdom has no fetch
    },
  });
  const w = dom.window, d = w.document, $ = (s) => d.querySelector(s), $$ = (s) => [...d.querySelectorAll(s)];
  const rows = () => $$("#table tr.row");

  // 1. Renders the latest run (run 2: alice, bob, carol)
  await until(() => rows().length > 0, "ranking table");
  assert.strictEqual(rows().length, 3, "three engineers in latest run");
  assert.strictEqual($$("#graph circle").length, 3, "one graph node per engineer");

  // 2. Hostile data is inert: shown as text, never parsed as HTML or executed
  rows().find((r) => r.textContent.includes("@alice")).click();
  await until(() => $("#detail h3"), "detail panel");
  await sleep(100);
  assert.strictEqual(w.__pwned, 0, "no payload executed");
  assert.strictEqual($$("script").length, 1, "no injected <script>");
  assert.strictEqual($$("img").length, 0, "no injected <img>");
  assert.strictEqual($$("[onerror],[onload],[onclick]").length, 0, "no injected handler attributes");
  assert.ok($("#detail").textContent.includes("<script>window.__pwned=1</script>"), "payload visible as literal text");
  assert.ok($("#detail").textContent.includes("alice/<img src=x"), "repo-name payload visible as literal text");

  // 3. Every link is restricted to github.com (javascript: URLs neutralised)
  const hrefs = $$("a[href]").map((a) => a.getAttribute("href"));
  assert.ok(hrefs.length > 3, "links rendered");
  for (const h of hrefs) assert.ok(h === "#" || h.startsWith("https://github.com/"), "unsafe href: " + h);
  assert.ok($$("a").filter((a) => a.textContent.includes("@alice")).every((a) => a.getAttribute("href") === "#"), "javascript: profile url neutralised");
  for (const a of $$('a[target="_blank"]')) assert.ok(a.rel.includes("noopener"), "external links use noopener");

  // 4. Filtering by area
  $("#domain").value = "Cloud"; fire(w, $("#domain"), "change");
  assert.strictEqual(rows().length, 1, "area filter keeps only carol");
  $("#domain").value = ""; fire(w, $("#domain"), "change");
  assert.strictEqual(rows().length, 3);
  $("#q").value = "bob"; fire(w, $("#q"), "input");
  assert.strictEqual(rows().length, 1, "search filter");
  $("#q").value = ""; fire(w, $("#q"), "input");

  // 5. 'Changes since previous run' panel
  await until(() => $("#diff").textContent.includes("Score movers"), "diff panel");
  const diff = $("#diff").textContent;
  assert.ok(diff.includes("Run #1 → #2"), diff);
  assert.ok(diff.includes("@carol"), "carol is new");
  assert.ok(diff.includes("@dave"), "dave dropped");
  assert.ok(diff.includes("+10"), "alice moved +10");

  // 6. Triage: saving a status goes through the CSRF-protected API
  rows().find((r) => r.textContent.includes("@alice")).click();
  await until(() => $("#detail select"), "triage controls");
  $("#detail select").value = "reviewing";
  $("#detail input").value = "look at the eBPF repo";
  $$("#detail button").find((b) => b.textContent === "Save").click();
  await until(() => $("#detail").textContent.includes("Saved."), "save confirmation");
  const latest = await (await fetch(new URL("/api/runs/latest", base))).json();
  const alice = latest.recommendations.find((r) => r.login === "alice");
  assert.strictEqual(alice.status, "reviewing");
  assert.strictEqual(alice.note, "look at the eBPF repo");
  assert.ok(rows().find((r) => r.textContent.includes("@alice")).textContent.includes("reviewing"), "table reflects new status");

  // 7. Switching to the first run shows dave and no previous run to diff against
  $("#run").value = "1"; fire(w, $("#run"), "change");
  await until(() => $("#diff").textContent.includes("First recorded run"), "first-run message");
  assert.ok(rows().some((r) => r.textContent.includes("@dave")));
  assert.strictEqual(w.__pwned, 0, "still nothing executed");

  console.log("DOM OK: render, XSS-inertness, link safety, filters, diff panel, triage save, run switch");
  process.exit(0);
})().catch((e) => { console.error("DOM TEST FAILED:", e.message); process.exit(1); });

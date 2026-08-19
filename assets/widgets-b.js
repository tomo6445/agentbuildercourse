/* =========================================================================
   Interactive widgets, part 2 — M6..M14 instruments.
   Registers into the same registry created by widgets.js.
   ========================================================================= */
(function () {
  "use strict";

  var W = window.BAIWidgets;
  if (!W) return;
  var el = W.el, num = W.num, money = W.money, slider = W.slider, select = W.select,
      toggles = W.toggles, readout = W.readout, verdict = W.verdict, register = W.register;

  /* =======================================================================
     M6 — what your MCP servers cost you before anyone types anything.
     ======================================================================= */

  register("mcp-budget", {
    title: "MCP tool-surface budget",
    sub: "Every connected server bills you on every turn, whether it is used or not."
  }, function (body) {
    var c = el("div", "controls");
    var servers = slider({ label: "Servers connected", min: 1, max: 30, value: 6 }, run);
    var perServer = slider({ label: "Tools per server", min: 1, max: 40, value: 9 }, run);
    var defSize = slider({ label: "Avg definition size", min: 60, max: 800, step: 10, value: 270,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var turns = slider({ label: "Turns per task", min: 1, max: 60, value: 14 }, run);
    [servers, perServer, defSize, turns].forEach(function (x) { c.appendChild(x); });
    body.appendChild(c);

    var sw = toggles([
      { key: "search", label: "tool search / dynamic discovery" },
      { key: "prune", label: "prune to task-relevant servers" },
      { key: "cache", label: "prompt caching on", on: true }
    ], run);
    body.appendChild(sw);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var t = sw.value();
      var tools = servers.value() * perServer.value();
      var raw = tools * defSize.value() + 300;

      var loaded = raw;
      var note = "all definitions resident";
      if (t.prune) { loaded = Math.round(raw * 0.35); note = "pruned to the servers this task needs"; }
      if (t.search) {
        // A search tool plus the handful it actually pulls in.
        loaded = 900 + Math.round(Math.min(tools, 8) * defSize.value());
        note = "one search tool + the definitions actually retrieved";
      }
      var perTask = loaded * turns.value();
      var billed = t.cache ? Math.round(perTask * 0.16) : perTask;

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "tools exposed", value: num(tools), tone: tools > 60 ? "warn" : "" },
        { label: "tokens/turn", value: num(loaded), tone: loaded > 10000 ? "warn" : loaded < 3000 ? "good" : "" },
        { label: "tokens/task", value: num(perTask) },
        { label: "billed after cache", value: num(billed), tone: t.cache ? "good" : "warn" },
        { label: "saved vs naive", value: raw ? Math.round((1 - loaded / raw) * 100) + "%" : "0%" }
      ]));

      var msg;
      if (loaded > 12000) {
        msg = verdict("bad", "The server ate the window",
          num(loaded) + " tokens per turn of pure tool definitions — " + note + ". Before the user has " +
          "said a word you have spent more context than most tasks need in total, and you pay it again " +
          "on every turn. This is the M6 autopsy, live.");
      } else if (tools > 40 && !t.search) {
        msg = verdict("warn", "Past the point where 'add another tool' works",
          "At " + num(tools) + " tools, selection accuracy degrades before context does. Namespacing (M2) " +
          "is the prerequisite; tool search is the fix.");
      } else {
        msg = verdict("ok", "Sustainable surface",
          num(loaded) + " tokens per turn — " + note + ". Re-measure whenever someone connects a server: " +
          "this number grows by other people's decisions.");
      }
      out.insertAdjacentHTML("beforeend", msg);
    }
    run();
  });

  /* =======================================================================
     M7 — path traversal. The same logic as the Python lab, in the browser.
     ======================================================================= */

  var ATTACKS = [
    ["notes/plan.md", "ordinary relative path"],
    ["../../etc/passwd", "classic dot-dot"],
    ["notes/../../../root/.ssh/id_rsa", "traversal after a valid-looking prefix"],
    ["..%2f..%2fetc%2fshadow", "URL-encoded separators"],
    ["%2e%2e%2f%2e%2e%2fetc/passwd", "URL-encoded dots"],
    ["/etc/passwd", "absolute path"],
    ["notes/./../../secrets.env", "single-dot padding"],
    ["notes/plan.md\u0000.txt", "null byte truncation"],
    ["....//....//etc/passwd", "doubled dots surviving one naive strip"],
    ["~/.aws/credentials", "home expansion"],
    ["notes\\..\\..\\windows\\system32", "backslash separators"],
    ["notes/plan.md ", "trailing space"]
  ];

  function naiveResolve(root, p) {
    // What people write first: strip "../" once and join.
    var cleaned = p.replace(/\.\.\//g, "");
    return root + "/" + cleaned;
  }

  function hardenedResolve(root, p) {
    // Reject, then canonicalise, then confirm containment.
    if (p.indexOf("\u0000") !== -1) return { ok: false, why: "NUL byte in path" };
    var decoded = p;
    for (var i = 0; i < 3; i++) {
      try {
        var next = decodeURIComponent(decoded);
        if (next === decoded) break;
        decoded = next;
      } catch (e) { return { ok: false, why: "undecodable percent-encoding" }; }
    }
    decoded = decoded.replace(/\\/g, "/").trim();
    if (decoded.charAt(0) === "~") return { ok: false, why: "home-relative path" };
    if (decoded.charAt(0) === "/") return { ok: false, why: "absolute path" };

    var parts = decoded.split("/");
    var stack = [];
    for (var j = 0; j < parts.length; j++) {
      var seg = parts[j];
      if (seg === "" || seg === ".") continue;
      if (seg === "..") {
        if (!stack.length) return { ok: false, why: "escapes the memory root" };
        stack.pop();
        continue;
      }
      if (/^\.{2,}$/.test(seg)) return { ok: false, why: "dot-only segment '" + seg + "'" };
      stack.push(seg);
    }
    if (!stack.length) return { ok: false, why: "resolves to the root itself" };
    return { ok: true, path: root + "/" + stack.join("/") };
  }

  register("path-traversal", {
    title: "Memory path resolver",
    sub: "Type a path the model might request. Both resolvers run; only one is safe."
  }, function (body) {
    var ROOT = "/srv/agent/memory";
    var c = el("div", "control");
    c.innerHTML = '<label>Requested path <b>root: ' + ROOT + "</b></label>" +
      '<input type="text" value="notes/../../../root/.ssh/id_rsa">';
    body.appendChild(c);
    var input = c.querySelector("input");

    var row = el("div", "switchrow");
    ATTACKS.slice(0, 6).forEach(function (a) {
      var b = el("button", "switch", a[1]);
      b.type = "button";
      b.addEventListener("click", function () { input.value = a[0]; run(); });
      row.appendChild(b);
    });
    body.appendChild(row);

    var out = el("div", "");
    body.appendChild(out);
    var suite = el("div", "");
    body.appendChild(suite);

    function run() {
      var p = input.value;
      var naive = naiveResolve(ROOT, p);
      var escaped = naive.indexOf(ROOT) !== 0 || naive.indexOf("/..") !== -1 ||
        naive.replace(ROOT + "/", "").indexOf("..") !== -1 || p.indexOf("%2e") !== -1 ||
        p.charAt(0) === "/" || p.charAt(0) === "~";
      var hard = hardenedResolve(ROOT, p);

      out.innerHTML =
        '<ul class="findings">' +
        '<li class="sev-' + (escaped ? "high" : "low") + '"><b>Naive: strip "../" and join</b>' +
        "<code>" + esc(naive) + "</code><br>" +
        (escaped ? "Outside the root, or reachable outside it. This is the bug." :
          "Happens to stay inside the root — for this input.") + "</li>" +
        '<li class="sev-' + "ok" + '"><b>Hardened: decode, canonicalise, contain</b>' +
        (hard.ok ? "<code>" + esc(hard.path) + "</code><br>Accepted."
                 : "<strong>Rejected</strong> — " + hard.why) + "</li></ul>";

      out.insertAdjacentHTML("beforeend", hard.ok
        ? verdict("ok", "Accepted", "Inside the root after canonicalisation. Note the order: reject the " +
            "undecodable, decode repeatedly, normalise separators, resolve segments, <em>then</em> check " +
            "containment. Checking containment on the raw string is the classic mistake.")
        : verdict("bad", "Rejected", hard.why + ". The model receives a clear error and can try a legal " +
            "path — rejection is not the same as crashing."));
    }

    function esc(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/\u0000/g, "\\0");
    }

    var runSuite = el("button", "btn ghost", "run the full attack suite");
    runSuite.type = "button";
    runSuite.style.marginTop = "12px";
    runSuite.addEventListener("click", function () {
      var rows = ATTACKS.map(function (a) {
        var h = hardenedResolve(ROOT, a[0]);
        var shouldPass = a[0] === "notes/plan.md" || a[0] === "notes/plan.md ";
        var correct = shouldPass ? h.ok : !h.ok;
        return '<li class="sev-' + (correct ? "ok" : "high") + '"><b>' + esc(a[0]) + "</b>" +
          a[1] + " → " + (h.ok ? "accepted" : "rejected (" + h.why + ")") +
          (correct ? "" : " <strong>— WRONG</strong>") + "</li>";
      });
      var passed = rows.filter(function (r) { return r.indexOf("sev-ok") !== -1; }).length;
      suite.innerHTML = verdict(passed === ATTACKS.length ? "ok" : "bad",
        "Attack suite: " + passed + " / " + ATTACKS.length + " handled correctly",
        "The lab version of this suite has 30 cases and your handler must block all of them.") +
        '<ul class="findings">' + rows.join("") + "</ul>";
    });
    body.appendChild(runSuite);

    input.addEventListener("input", run);
    run();
  });

  /* =======================================================================
     M8 — judge validation. Label them yourself, then meet the judge.
     ======================================================================= */

  var JUDGE_CASES = [
    { out: "Revenue grew 14% YoY to $2.1B [ref: 10-K p.34]. Margin fell 2pts on freight costs [ref: p.41].",
      human: 1, judge: 1, why: "Accurate, cited, complete. Both agree." },
    { out: "Revenue grew strongly this year and margins were affected by various factors.",
      human: 0, judge: 1, why: "No numbers, no citations — a human marks this a fail. The judge rewarded fluent, confident prose. This is verbosity/style bias, and it is the most common judge defect." },
    { out: "Revenue was $2.1B (+14%). Source: seekingalpha-summary-blog.",
      human: 0, judge: 1, why: "Right number, junk source. Unless your rubric scores source quality explicitly, the judge will not invent the standard. This is the failure that manual review famously catches." },
    { out: "I could not find margin data in the provided filings, so I have reported revenue only: $2.1B (+14%) [ref: p.34].",
      human: 1, judge: 0, why: "Correctly abstaining on missing data is good behaviour. Judges routinely mark abstention as incompleteness — you must reward it in the rubric or you will train out honesty." },
    { out: "Revenue: $2.1B. Margin: 31%. Headcount: 4,400. Offices: 12. CEO: appointed 2019. Founded: 2003.",
      human: 0, judge: 1, why: "Padded with irrelevant facts, and the margin figure is unsourced. Length read as completeness." },
    { out: "Margin fell 2pts [ref: p.41]; revenue $2.1B, +14% [ref: p.34]. Freight was the driver [ref: p.41].",
      human: 1, judge: 1, why: "Same content as case 1 in a different order. Both agree — good, because position bias would have shown up here." },
    { out: "Based on my analysis, revenue increased by approximately 14 percent year over year.",
      human: 0, judge: 0, why: "Hedged, uncited, incomplete. Both agree it fails." },
    { out: "$2.1B revenue (+14% YoY) [p.34]; gross margin 31%, down 2pts [p.41]; driver: freight [p.41]. Confidence: high.",
      human: 1, judge: 1, why: "Complete, cited, calibrated." }
  ];

  register("judge-agreement", {
    title: "Validate the judge before you trust it",
    sub: "Label all eight, then reveal. An unvalidated judge is a random number generator with good manners."
  }, function (body) {
    var labels = {};
    var revealed = false;
    var list = el("div", "");
    body.appendChild(list);

    JUDGE_CASES.forEach(function (c, i) {
      var q = el("div", "q");
      q.innerHTML = '<p class="stem"><span class="qn">' + (i + 1) + "</span>" +
        "Rubric: factual accuracy, citation to source, completeness, source quality." +
        '<br><em style="color:var(--ink-2)">' + c.out + "</em></p>";
      var row = el("div", "switchrow");
      [["1", "pass"], ["0", "fail"]].forEach(function (o) {
        var b = el("button", "switch", o[1]);
        b.type = "button";
        b.dataset.v = o[0];
        b.addEventListener("click", function () {
          if (revealed) return;
          labels[i] = +o[0];
          row.querySelectorAll(".switch").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
          b.setAttribute("aria-pressed", "true");
          paint();
        });
        row.appendChild(b);
      });
      q.appendChild(row);
      var why = el("div", "why");
      why.hidden = true;
      q.appendChild(why);
      list.appendChild(q);
    });

    var revealBtn = el("button", "btn", "reveal judge + reference labels");
    revealBtn.type = "button";
    body.appendChild(revealBtn);
    var out = el("div", "");
    body.appendChild(out);

    function paint() {
      out.innerHTML = verdict("", "Labelled",
        Object.keys(labels).length + " of " + JUDGE_CASES.length +
        ". Label all eight before revealing — pre-committing is the whole point.");
    }

    revealBtn.addEventListener("click", function () {
      revealed = true;
      var judgeVsHuman = 0, youVsHuman = 0, both1 = 0, judge1 = 0, human1 = 0;
      JUDGE_CASES.forEach(function (c, i) {
        if (c.judge === c.human) judgeVsHuman++;
        if (labels[i] === c.human) youVsHuman++;
        if (c.judge === 1) judge1++;
        if (c.human === 1) human1++;
        if (c.judge === 1 && c.human === 1) both1++;
        var q = list.children[i];
        var why = q.querySelector(".why");
        why.hidden = false;
        why.className = "why " + (c.judge === c.human ? "correct" : "wrong");
        why.innerHTML = "<strong>reference: " + (c.human ? "pass" : "fail") +
          " · judge: " + (c.judge ? "pass" : "fail") + (labels[i] !== undefined ?
          " · you: " + (labels[i] ? "pass" : "fail") : "") + "</strong><br>" + c.why;
      });
      var n = JUDGE_CASES.length;
      var raw = judgeVsHuman / n;
      // Cohen's kappa against the expected agreement of two independent labellers.
      var pe = (judge1 / n) * (human1 / n) + (1 - judge1 / n) * (1 - human1 / n);
      var kappa = pe === 1 ? 0 : (raw - pe) / (1 - pe);

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "judge vs reference", value: Math.round(raw * 100) + "%",
          tone: raw >= 0.85 ? "good" : "warn" },
        { label: "Cohen's kappa", value: kappa.toFixed(2), tone: kappa >= 0.6 ? "good" : "warn" },
        { label: "you vs reference", value: Object.keys(labels).length
            ? Math.round(youVsHuman / n * 100) + "%" : "—" },
        { label: "judge false passes", value: JUDGE_CASES.filter(function (c) {
            return c.judge === 1 && c.human === 0; }).length, tone: "warn" }
      ]));
      out.insertAdjacentHTML("beforeend", verdict(raw >= 0.85 ? "ok" : "bad",
        raw >= 0.85 ? "Usable" : "Not shippable",
        "Raw agreement of " + Math.round(raw * 100) + "% sounds fine and is not, because a judge that " +
        "passes everything scores well on a mostly-passing set. Kappa " + kappa.toFixed(2) +
        " corrects for chance. Note the direction of the errors: this judge <strong>over-passes</strong> — " +
        "fluent, padded and badly-sourced answers slip through, and honest abstention is punished. " +
        "Fix the rubric (score source quality and reward abstention explicitly), then re-measure. " +
        "Never fix it by changing the reference labels."));
    });
    paint();
  });

  /* =======================================================================
     M9 — the knee. Quality per dollar across worker counts.
     ======================================================================= */

  register("worker-knee", {
    title: "Multi-agent economics: find the knee",
    sub: "Measured shape from a wide-search task. Quality saturates; cost does not."
  }, function (body) {
    // Quality follows a saturating curve; cost is close to linear in workers.
    var DATA = [
      { w: 1, q: 0.58, c: 1.0 }, { w: 2, q: 0.70, c: 2.1 }, { w: 3, q: 0.78, c: 3.2 },
      { w: 4, q: 0.83, c: 4.4 }, { w: 5, q: 0.86, c: 5.6 }, { w: 6, q: 0.875, c: 6.9 },
      { w: 8, q: 0.89, c: 9.6 }, { w: 10, q: 0.895, c: 12.4 }, { w: 12, q: 0.897, c: 15.3 }
    ];
    var c = el("div", "controls");
    var pick = slider({ label: "Workers", min: 1, max: 12, value: 3 }, run);
    var value = slider({ label: "Value of a completed task", min: 1, max: 200, value: 20,
      fmt: function (v) { return "$" + v; } }, run);
    var unit = slider({ label: "Cost of a single-agent run", min: 1, max: 100, value: 12,
      fmt: function (v) { return "$" + (v / 100).toFixed(2); } }, run);
    [pick, value, unit].forEach(function (x) { c.appendChild(x); });
    body.appendChild(c);

    var chart = el("div", "");
    body.appendChild(chart);
    var out = el("div", "");
    body.appendChild(out);

    function nearest(w) {
      return DATA.reduce(function (a, b) {
        return Math.abs(b.w - w) < Math.abs(a.w - w) ? b : a;
      });
    }

    function run() {
      var w = pick.value();
      var d = nearest(w);
      var base = unit.value() / 100;
      var cost = base * d.c;
      var val = value.value();

      var W = 520, H = 190, pad = 34;
      var maxC = 16;
      function x(v) { return pad + (v - 1) / 11 * (W - pad * 2); }
      function yq(v) { return H - pad - (v - 0.5) / 0.45 * (H - pad * 2); }
      function yc(v) { return H - pad - v / maxC * (H - pad * 2); }

      var qline = DATA.map(function (p, i) { return (i ? "L" : "M") + x(p.w) + " " + yq(p.q); }).join(" ");
      var cline = DATA.map(function (p, i) { return (i ? "L" : "M") + x(p.w) + " " + yc(p.c); }).join(" ");

      chart.innerHTML =
        '<svg viewBox="0 0 ' + W + " " + H + '" style="width:100%;height:auto;border:1px solid var(--rule);background:var(--paper)">' +
        '<path d="' + qline + '" fill="none" stroke="var(--teal)" stroke-width="2"/>' +
        '<path d="' + cline + '" fill="none" stroke="var(--rust)" stroke-width="2" stroke-dasharray="4 3"/>' +
        '<line x1="' + x(d.w) + '" y1="' + pad + '" x2="' + x(d.w) + '" y2="' + (H - pad) +
          '" stroke="var(--ink-3)" stroke-width="1"/>' +
        '<circle cx="' + x(d.w) + '" cy="' + yq(d.q) + '" r="4" fill="var(--teal)"/>' +
        '<circle cx="' + x(d.w) + '" cy="' + yc(d.c) + '" r="4" fill="var(--rust)"/>' +
        '<text x="' + pad + '" y="' + (H - 8) + '" font-family="monospace" font-size="10" fill="var(--ink-3)">1 worker</text>' +
        '<text x="' + (W - pad - 46) + '" y="' + (H - 8) + '" font-family="monospace" font-size="10" fill="var(--ink-3)">12</text>' +
        "</svg>" +
        '<div class="legend"><span><i style="background:var(--teal)"></i>quality (rubric)</span>' +
        '<span><i style="background:var(--rust)"></i>cost multiple</span></div>';

      // Marginal quality bought by the last worker added.
      var idx = DATA.indexOf(d);
      var prev = idx > 0 ? DATA[idx - 1] : null;
      var marginalQ = prev ? d.q - prev.q : 0;
      var marginalC = prev ? (d.c - prev.c) * base : 0;
      var qPerDollar = d.q / cost;

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "quality", value: (d.q * 100).toFixed(1) + "%" },
        { label: "cost/task", value: money(cost), tone: cost > val * 0.25 ? "warn" : "good" },
        { label: "margin/task", value: money(val - cost), tone: val - cost <= 0 ? "warn" : "good" },
        { label: "quality per $", value: qPerDollar.toFixed(2) },
        { label: "last worker bought", value: prev ? "+" + (marginalQ * 100).toFixed(1) + "pt" : "—",
          tone: prev && marginalQ < 0.02 ? "warn" : "" }
      ]));

      var msg;
      if (prev && marginalQ < 0.015) {
        msg = verdict("bad", "Past the knee",
          "Worker " + d.w + " bought " + (marginalQ * 100).toFixed(1) + " points of quality for " +
          money(marginalC) + ". You are buying rounding error with real money. The knee on this curve is " +
          "around 3-4 workers, which is lower than almost everyone guesses.");
      } else if (cost > val * 0.25) {
        msg = verdict("warn", "Cost is eating the value",
          "At " + money(cost) + " per task against " + money(val) + " of value, compute is " +
          Math.round(cost / val * 100) + "% of the take. Multi-agent is a purchase; check you can afford it " +
          "before you check whether it works.");
      } else {
        msg = verdict("ok", "Defensible",
          d.w + " workers at " + money(cost) + " per task for " + (d.q * 100).toFixed(1) + "% quality. " +
          "Write the number in the Decision Log, then re-run this measurement on <em>your</em> task — " +
          "the curve shape transfers, the knee does not.");
      }
      out.insertAdjacentHTML("beforeend", msg);
    }
    run();
  });

  /* =======================================================================
     M10 — read a trace and name the failure class.
     ======================================================================= */

  var TRACES = {
    drift: {
      label: "Trace A",
      answer: "goal drift",
      spans: [
        { d: 0, w: 12, l: "model turn 1", t: "plan: summarise Q3 revenue", tok: 640 },
        { d: 12, w: 8, l: "search_docs", t: "q='Q3 revenue'", tok: 2400 },
        { d: 20, w: 10, l: "model turn 2", t: "found competitor mention", tok: 3100 },
        { d: 30, w: 9, l: "search_docs", t: "q='competitor pricing'", tok: 2900 },
        { d: 39, w: 11, l: "model turn 3", t: "competitor analysis", tok: 4200 },
        { d: 50, w: 9, l: "search_docs", t: "q='competitor market share'", tok: 3300 },
        { d: 59, w: 14, l: "model turn 4", t: "final: competitive landscape memo", tok: 5100 }
      ]
    },
    oscillation: {
      label: "Trace B",
      answer: "oscillation",
      spans: [
        { d: 0, w: 10, l: "model turn 1", t: "check inventory", tok: 600 },
        { d: 10, w: 6, l: "inventory_get", t: "sku=A1 → 'stale, verify'", tok: 900 },
        { d: 16, w: 9, l: "model turn 2", t: "verify", tok: 1200 },
        { d: 25, w: 6, l: "stock_verify", t: "sku=A1 → 'refresh inventory'", tok: 1500 },
        { d: 31, w: 9, l: "model turn 3", t: "refresh", tok: 1800 },
        { d: 40, w: 6, l: "inventory_get", t: "sku=A1 → 'stale, verify'", tok: 2100 },
        { d: 46, w: 9, l: "model turn 4", t: "verify", tok: 2400 }
      ]
    },
    truncation: {
      label: "Trace C",
      answer: "silent truncation",
      spans: [
        { d: 0, w: 11, l: "model turn 1", t: "read the contract", tok: 700 },
        { d: 11, w: 18, l: "read_file", t: "contract.pdf → 48,000 tok, returned 4,000", tok: 4000 },
        { d: 29, w: 13, l: "model turn 2", t: "summarise clauses 1-6", tok: 5100 },
        { d: 42, w: 12, l: "model turn 3", t: "answer: 'no termination clause exists'", tok: 5400 }
      ]
    }
  };

  register("trace-reader", {
    title: "Read the trace, name the failure",
    sub: "No source access. This is the M10 lab in miniature."
  }, function (body) {
    var pick = select({ label: "Trace", options: Object.keys(TRACES).map(function (k) {
      return [k, TRACES[k].label]; }) }, draw);
    var c = el("div", "controls");
    c.appendChild(pick);
    body.appendChild(c);

    var chart = el("div", "");
    body.appendChild(chart);

    var guessRow = el("div", "switchrow");
    var out = el("div", "");
    ["tool misselection", "goal drift", "oscillation", "silent truncation", "context degradation"]
      .forEach(function (name) {
        var b = el("button", "switch", name);
        b.type = "button";
        b.addEventListener("click", function () {
          var t = TRACES[pick.value()];
          var ok = name === t.answer;
          out.innerHTML = verdict(ok ? "ok" : "bad", ok ? "Correct" : "Not this one", EXPLAIN[t.answer]);
        });
        guessRow.appendChild(b);
      });
    body.appendChild(guessRow);
    body.appendChild(out);

    var EXPLAIN = {
      "goal drift": "The task was Q3 revenue. By turn 3 every query is about competitors and the final " +
        "answer is a different document than the one asked for. The signature is a <em>gradual</em> " +
        "change in tool arguments away from the original goal, with no error anywhere. Detection: " +
        "compare the final output's topic against the initial instruction, or re-state the goal in " +
        "context on every turn.",
      "oscillation": "Two tools each tell the model to go and use the other. The signature is a repeated " +
        "(tool, arguments) pair with no state change between them — here inventory_get with sku=A1 twice, " +
        "identical. Detection is cheap: hash (tool, args) per turn and trip on a repeat. The fix is in the " +
        "tool return strings, not in the loop.",
      "silent truncation": "read_file was handed 48,000 tokens and returned 4,000, with no error and no " +
        "marker. The model then answered confidently about content it never saw — 'no termination clause " +
        "exists' is false, and nothing in the trace looks like a failure. The signature is a tool result " +
        "sitting suspiciously exactly at a size limit. Tools must say when they truncated.",
      "tool misselection": "",
      "context degradation": ""
    };

    function draw() {
      var t = TRACES[pick.value()];
      out.innerHTML = "";
      var W = 560, rowH = 26, H = t.spans.length * rowH + 16;
      var maxX = Math.max.apply(null, t.spans.map(function (s) { return s.d + s.w; }));
      chart.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" style="width:100%;height:auto;' +
        'border:1px solid var(--rule);background:var(--paper)">' +
        t.spans.map(function (s, i) {
          var x = 8 + s.d / maxX * (W - 200);
          var w = Math.max(6, s.w / maxX * (W - 200));
          var y = 8 + i * rowH;
          var isTool = s.l.indexOf("model") === -1;
          return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="14" fill="' +
            (isTool ? "var(--gold)" : "var(--teal)") + '"/>' +
            '<text x="' + (x + w + 6) + '" y="' + (y + 11) + '" font-family="monospace" font-size="9.5" ' +
            'fill="var(--ink-2)">' + s.l + " · " + s.t + "</text>";
        }).join("") + "</svg>" +
        '<div class="legend"><span><i style="background:var(--teal)"></i>model turn</span>' +
        '<span><i style="background:var(--gold)"></i>tool span</span>' +
        "<span>cumulative context at final turn: " + num(t.spans[t.spans.length - 1].tok) + " tok</span></div>";
    }
    draw();
  });

  /* =======================================================================
     M11 — the lethal trifecta auditor.
     ======================================================================= */

  var CAPS = [
    { key: "files", leg: "private", label: "reads local files", danger: true },
    { key: "db", leg: "private", label: "queries the production database", danger: true },
    { key: "secrets", leg: "private", label: "process holds API keys / env vars", danger: true },
    { key: "web", leg: "untrusted", label: "fetches web pages", danger: true },
    { key: "email_in", leg: "untrusted", label: "reads incoming email / tickets", danger: true },
    { key: "memory", leg: "untrusted", label: "reads memory written in past sessions", danger: true },
    { key: "email_out", leg: "exfil", label: "sends email", danger: true },
    { key: "http", leg: "exfil", label: "makes arbitrary outbound HTTP requests", danger: true },
    { key: "git", leg: "exfil", label: "pushes to a git remote", danger: true }
  ];

  register("trifecta", {
    title: "Lethal trifecta auditor",
    sub: "Tick what your agent can do. Any two legs are manageable; all three is an exfiltration primitive."
  }, function (body) {
    var sw = toggles(CAPS.map(function (c) {
      return { key: c.key, label: c.label, danger: true };
    }), run);
    body.appendChild(sw);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var s = sw.value();
      var legs = { private: [], untrusted: [], exfil: [] };
      CAPS.forEach(function (c) { if (s[c.key]) legs[c.leg].push(c.label); });
      var present = Object.keys(legs).filter(function (k) { return legs[k].length; });

      var NAMES = {
        private: "Access to private data",
        untrusted: "Exposure to untrusted content",
        exfil: "Ability to communicate externally"
      };
      out.innerHTML = "";
      out.appendChild(readout([
        { label: "legs present", value: present.length + " / 3",
          tone: present.length === 3 ? "warn" : present.length === 2 ? "" : "good" },
        { label: "private data", value: legs.private.length ? "yes" : "no", tone: legs.private.length ? "warn" : "good" },
        { label: "untrusted input", value: legs.untrusted.length ? "yes" : "no", tone: legs.untrusted.length ? "warn" : "good" },
        { label: "egress", value: legs.exfil.length ? "yes" : "no", tone: legs.exfil.length ? "warn" : "good" }
      ]));

      var items = Object.keys(legs).map(function (k) {
        return '<li class="sev-' + (legs[k].length ? "high" : "ok") + '"><b>' + NAMES[k] + "</b>" +
          (legs[k].length ? legs[k].join(", ") : "not present") + "</li>";
      });
      out.insertAdjacentHTML("beforeend", '<ul class="findings">' + items.join("") + "</ul>");

      var msg;
      if (present.length === 3) {
        msg = verdict("bad", "Exfiltration primitive present",
          "All three legs. An attacker who can place text where your agent will read it — a web page, a " +
          "ticket, a memory file it wrote last week — can instruct it to read your private data and send " +
          "it out. No prompt fixes this; the model 'usually resisting' is not a control. Break one leg: " +
          "<strong>egress</strong> is usually the cheapest (allowlist destinations through a proxy), " +
          "<strong>untrusted content</strong> the next (summarise retrieved text instead of injecting it " +
          "raw), and <strong>private data</strong> the hardest (credential proxy, so the agent never " +
          "holds a secret).");
      } else if (present.length === 2) {
        msg = verdict("warn", "Two legs — manageable, and one connector from a breach",
          "This is a normal, shippable posture. The risk is drift: the third leg usually arrives quietly, " +
          "in a PR that adds 'just a webhook'. Write the missing leg into the threat model as a tripwire " +
          "and put it in code review.");
      } else {
        msg = verdict("ok", "Constrained",
          "Fewer than two legs. Re-audit whenever a tool, an MCP server or a memory file is added — this " +
          "audit is a reflex, not a milestone.");
      }
      out.insertAdjacentHTML("beforeend", msg);
    }
    run();
  });

  /* =======================================================================
     M12 — cost model. Prices are inputs, because prices change.
     ======================================================================= */

  register("cost-model", {
    title: "Cost model",
    sub: "Prices are editable inputs — check current rates and type them in. The arithmetic is the lesson."
  }, function (body) {
    var c1 = el("div", "controls");
    var tasks = slider({ label: "Tasks per day", min: 10, max: 100000, step: 10, value: 2000,
      fmt: function (v) { return num(v); } }, run);
    var turns = slider({ label: "Turns per task", min: 1, max: 60, value: 12 }, run);
    var stable = slider({ label: "Stable prefix (system + tools)", min: 500, max: 40000, step: 100,
      value: 6000, fmt: function (v) { return num(v) + " tok"; } }, run);
    var growth = slider({ label: "Context added per turn", min: 100, max: 8000, step: 100, value: 1400,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var outTok = slider({ label: "Output per turn", min: 50, max: 4000, step: 50, value: 350,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var workers = slider({ label: "Sub-agents per task", min: 0, max: 12, value: 0 }, run);
    [tasks, turns, stable, growth, outTok, workers].forEach(function (x) { c1.appendChild(x); });
    body.appendChild(c1);

    var c2 = el("div", "controls");
    var pin = el("div", "control");
    pin.innerHTML = "<label>Input price / Mtok <b>$</b></label><input type='number' step='0.01' value='3.00'>";
    var pout = el("div", "control");
    pout.innerHTML = "<label>Output price / Mtok <b>$</b></label><input type='number' step='0.01' value='15.00'>";
    var pcache = el("div", "control");
    pcache.innerHTML = "<label>Cache read price / Mtok <b>$</b></label><input type='number' step='0.01' value='0.30'>";
    [pin, pout, pcache].forEach(function (x) { x.querySelector("input").addEventListener("input", run); c2.appendChild(x); });
    body.appendChild(c2);

    var sw = toggles([
      { key: "cache", label: "prompt caching", on: true },
      { key: "route", label: "route cheap steps to a small model" }
    ], run);
    body.appendChild(sw);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var t = sw.value();
      var pIn = +pin.querySelector("input").value || 0;
      var pOut = +pout.querySelector("input").value || 0;
      var pCache = +pcache.querySelector("input").value || 0;

      // Input tokens per task: the stable prefix is re-sent every turn, and the
      // transcript grows, so history is a triangular number, not a linear one.
      var n = turns.value();
      var prefixTok = stable.value() * n;
      var historyTok = growth.value() * (n * (n - 1) / 2);
      var outputTok = outTok.value() * n;

      var prefixCost = t.cache
        ? (stable.value() * pIn + stable.value() * (n - 1) * pCache) / 1e6
        : prefixTok * pIn / 1e6;
      var historyCost = historyTok * pIn / 1e6;
      var outputCost = outputTok * pOut / 1e6;
      if (t.route) { outputCost *= 0.45; historyCost *= 0.8; }

      var single = prefixCost + historyCost + outputCost;
      var perTask = single * (1 + workers.value() * 0.85);

      var terms = [
        { l: "re-sent history", v: historyCost * (1 + workers.value() * 0.85), color: "#a8452c" },
        { l: "stable prefix", v: prefixCost * (1 + workers.value() * 0.85), color: "#8a6d1f" },
        { l: "output", v: outputCost * (1 + workers.value() * 0.85), color: "#1f5f5b" }
      ].sort(function (a, b) { return b.v - a.v; });
      var total = terms.reduce(function (a, b) { return a + b.v; }, 0) || 1;

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "cost / task", value: money(perTask) },
        { label: "cost / day", value: money(perTask * tasks.value()) },
        { label: "cost / month", value: money(perTask * tasks.value() * 30),
          tone: perTask * tasks.value() * 30 > 20000 ? "warn" : "" },
        { label: "input tok / task", value: num(prefixTok + historyTok) },
        { label: "dominant term", value: terms[0].l, tone: "warn" }
      ]));

      out.insertAdjacentHTML("beforeend",
        '<div class="bar-stack" style="margin-top:12px">' + terms.map(function (x) {
          return '<i style="width:' + (x.v / total * 100).toFixed(1) + "%;background:" + x.color + '"></i>';
        }).join("") + "</div>" +
        '<div class="legend">' + terms.map(function (x) {
          return "<span><i style='background:" + x.color + "'></i>" + x.l + " · " +
            Math.round(x.v / total * 100) + "%</span>";
        }).join("") + "</div>");

      var advice;
      if (terms[0].l === "re-sent history") {
        advice = "History dominates, and it grows with the <em>square</em> of turn count — turn 20 re-sends " +
          "nineteen turns of transcript. The lever is not a cheaper model, it is fewer or smaller turns: " +
          "context strategy (M3), tighter tool returns, fewer round trips.";
      } else if (terms[0].l === "stable prefix" && !t.cache) {
        advice = "A fixed prefix re-sent " + n + " times per task is the single easiest thing to cache. " +
          "Turn caching on and watch this term collapse.";
      } else if (terms[0].l === "output") {
        advice = "Output dominates, which is unusual and means your turns are short and verbose. Check " +
          "whether the model is narrating; check whether a smaller model can do the writing steps.";
      } else {
        advice = "Prefix dominates even with caching — your system prompt and tool definitions are large. " +
          "That is the M2/M6 tool-surface problem showing up on the invoice.";
      }
      out.insertAdjacentHTML("beforeend", verdict("warn", "Where the money is", advice +
        "<br><br><em>Prices above are placeholders you should replace with current published rates before " +
        "quoting any of these numbers to anyone.</em>"));
    }
    run();
  });

  /* =======================================================================
     M13 — the autonomy ladder, per action class.
     ======================================================================= */

  var RUNGS = [
    "Suggest only — human does it",
    "Approve each action",
    "Approve risky actions, auto-run the rest",
    "Act, then notify",
    "Act with undo available",
    "Fully autonomous"
  ];

  register("autonomy-ladder", {
    title: "Autonomy ladder",
    sub: "Chosen per action class, never per agent. Pick an action and see the rung it earns."
  }, function (body) {
    var c = el("div", "controls");
    var act = select({ label: "Action class", options: [
      ["read", "Read a file in the repo"],
      ["search", "Search the web"],
      ["draft", "Draft a reply for review"],
      ["commit", "Commit to a feature branch"],
      ["email", "Send an external email"],
      ["refund", "Issue a customer refund"],
      ["migrate", "Run a production database migration"],
      ["delete", "Delete a production resource"]
    ] }, run);
    var vol = slider({ label: "Actions per day", min: 1, max: 500, value: 40 }, run);
    [act, vol].forEach(function (x) { c.appendChild(x); });
    body.appendChild(c);
    var out = el("div", "");
    body.appendChild(out);

    var PROFILE = {
      read:    { rev: 3, blast: 0, rung: 5, why: "Read-only, no blast radius. Approving reads is how you train people to click yes without looking." },
      search:  { rev: 3, blast: 0, rung: 5, why: "Read-only, though remember every page fetched is untrusted input (M11)." },
      draft:   { rev: 3, blast: 0, rung: 0, why: "The output IS the deliverable for a human, so the human is in the loop by definition." },
      commit:  { rev: 2, blast: 1, rung: 4, why: "Reversible with git, on an isolated branch. Undo is cheap and real, so act-with-undo is honest." },
      email:   { rev: 0, blast: 2, rung: 1, why: "Unsendable. External parties see it. This is the classic irreversible-with-reputation-cost action." },
      refund:  { rev: 1, blast: 2, rung: 2, why: "Money moves. Reversible on paper, expensive and embarrassing in practice. Tier by amount: small refunds auto, large ones approved." },
      migrate: { rev: 0, blast: 3, rung: 1, why: "Irreversible, wide blast radius, and the failure is often silent until the next deploy. Dry-run first, always." },
      delete:  { rev: 0, blast: 3, rung: 1, why: "Irreversible and total. If it must be automated, make it a soft delete with a retention window — turn an irreversible action into a reversible one." }
    };

    function run() {
      var p = PROFILE[act.value()];
      var rung = p.rung;
      var fatigue = rung === 1 ? vol.value() : 0;
      var note = "";
      if (fatigue > 25) {
        note = "<strong>Approval fatigue is a security failure mode.</strong> " + vol.value() +
          " approvals a day is not review, it is a rubber stamp with extra steps. Batch by risk tier, " +
          "learn an allowlist from past approvals, or reduce the action volume — but do not keep asking " +
          "a question nobody is really answering.";
      }

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "recommended rung", value: rung + 1 + " / 6", tone: rung <= 1 ? "warn" : "good" },
        { label: "reversibility", value: ["none", "costly", "cheap", "n/a"][p.rev] },
        { label: "blast radius", value: ["none", "self", "customers", "production"][p.blast],
          tone: p.blast >= 2 ? "warn" : "" },
        { label: "approvals/day", value: fatigue ? num(fatigue) : "—",
          tone: fatigue > 25 ? "warn" : "" }
      ]));
      out.insertAdjacentHTML("beforeend", verdict(rung <= 1 ? "warn" : "ok",
        RUNGS[rung], p.why + (note ? "<br><br>" + note : "")));

      if (rung <= 2) {
        out.insertAdjacentHTML("beforeend",
          '<ul class="findings"><li class="sev-med"><b>What the approval prompt must show</b>' +
          "A human cannot decide from “Agent wants to run: bash”. Show the <strong>action</strong> in " +
          "concrete terms, the <strong>reason</strong> the agent believes it is needed, the " +
          "<strong>blast radius</strong> (what changes, for whom, reversibly or not), and the " +
          "<strong>alternative</strong> if they decline. Four fields. Anything less generates yes-clicks." +
          "</li></ul>");
      }
    }
    run();
  });

  /* =======================================================================
     M14 — will this skill ever get loaded?
     ======================================================================= */

  register("skill-description", {
    title: "Skill description linter",
    sub: "The description is the retrieval key. If it does not match how people ask, the skill never loads."
  }, function (body) {
    var c = el("div", "control");
    c.innerHTML = "<label>SKILL.md frontmatter description</label>" +
      "<textarea spellcheck='false' style='min-height:90px'>Helps with reports.</textarea>";
    body.appendChild(c);
    var ta = c.querySelector("textarea");

    var row = el("div", "switchrow");
    var samples = [
      ["written for humans", "Helps with reports."],
      ["better", "Generates the monthly finance report. Use when the user asks for a monthly report, " +
        "month-end close, or revenue summary. Covers pulling figures from the ledger export, applying " +
        "the house formatting, and producing the commentary section."]
    ];
    samples.forEach(function (s) {
      var b = el("button", "switch", s[0]);
      b.type = "button";
      b.addEventListener("click", function () { ta.value = s[1]; run(); });
      row.appendChild(b);
    });
    body.appendChild(row);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var d = ta.value.trim();
      var f = [];
      function add(sev, t, x) { f.push({ sev: sev, t: t, x: x }); }

      if (d.length < 25) add("high", "Far too short", "There is nothing here to match a user's phrasing against.");
      else if (d.length < 80) add("med", "Short", "Aim for two or three sentences: what it does, when to use it, what it covers.");
      if (d.length > 700) add("low", "Long", "This is loaded on every request. Move the detail into the body — that is what progressive disclosure is for.");
      if (!/use (this|it) when|when the user|when you|for when/i.test(d))
        add("high", "No trigger phrasing", "Add an explicit “Use when…” clause naming the words a user would actually type. This single sentence is the difference between 4% and 90% invocation.");
      if (!/\b(report|invoice|migration|review|deploy|test|analy|summar|format|extract|generate|audit|draft)\w*/i.test(d))
        add("med", "No concrete domain nouns", "Retrieval matches on specifics. Name the artefacts, systems and verbs involved.");
      if (/\b(I |we |our |you should|please)\b/i.test(d))
        add("low", "First or second person", "Write it in the third person, describing the capability — it is read by a retriever, not a colleague.");
      var triggerWords = (d.match(/\b\w+\b/g) || []).length;
      if (triggerWords < 12) add("med", "Very few tokens to match on", "Synonyms matter: a user who says “month-end close” should hit a skill that says “monthly report”. List both.");
      if (!f.length) add("ok", "Nothing flagged", "Now validate it the only way that counts: run the eval set and count how often the skill actually loads.");

      var score = Math.max(0, 100 - f.filter(function (x) { return x.sev === "high"; }).length * 30 -
        f.filter(function (x) { return x.sev === "med"; }).length * 14 -
        f.filter(function (x) { return x.sev === "low"; }).length * 5);

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "retrieval score", value: score, tone: score >= 80 ? "good" : score >= 50 ? "" : "warn" },
        { label: "length", value: d.length + " ch" },
        { label: "always-loaded cost", value: "~" + Math.round(d.length / 3.6) + " tok" }
      ]));
      out.insertAdjacentHTML("beforeend", '<ul class="findings">' + f.map(function (x) {
        return '<li class="sev-' + x.sev + '"><b>' + x.t + "</b>" + x.x + "</li>";
      }).join("") + "</ul>");
    }
    ta.addEventListener("input", run);
    run();
  });
})();

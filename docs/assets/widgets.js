/* =========================================================================
   Interactive widgets, part 1 — registry + M1..M4 instruments.

   A lesson page contains  <div class="widget" data-widget="NAME"
   data-config='{…}'>  and this file fills in the head and body. Every widget
   is pure client-side simulation: no API key, no network, deterministic.
   ========================================================================= */
(function () {
  "use strict";

  var REG = {};
  var META = {};

  function register(name, meta, build) {
    REG[name] = build;
    META[name] = meta;
  }

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html !== undefined) n.innerHTML = html;
    return n;
  }

  function num(n, dp) {
    if (dp === undefined) dp = 0;
    return n.toLocaleString(undefined, {
      minimumFractionDigits: dp, maximumFractionDigits: dp
    });
  }

  function money(n) {
    if (n >= 100) return "$" + num(n, 0);
    if (n >= 1) return "$" + num(n, 2);
    if (n >= 0.01) return "$" + n.toFixed(3);
    return "$" + n.toFixed(4);
  }

  /* Build a labelled range control that reports its value as it moves. */
  function slider(opts, onchange) {
    var wrap = el("div", "control");
    var id = "s" + Math.random().toString(36).slice(2, 8);
    wrap.innerHTML =
      '<label for="' + id + '">' + opts.label + '<b id="' + id + 'v"></b></label>' +
      '<input id="' + id + '" type="range" min="' + opts.min + '" max="' + opts.max +
      '" step="' + (opts.step || 1) + '" value="' + opts.value + '">';
    var input = wrap.querySelector("input");
    var out = wrap.querySelector("b");
    function paint() {
      out.textContent = (opts.fmt ? opts.fmt(+input.value) : num(+input.value));
    }
    input.addEventListener("input", function () { paint(); onchange(); });
    paint();
    wrap.value = function () { return +input.value; };
    return wrap;
  }

  function select(opts, onchange) {
    var wrap = el("div", "control");
    wrap.innerHTML = "<label>" + opts.label + "</label><select>" +
      opts.options.map(function (o) {
        return '<option value="' + o[0] + '">' + o[1] + "</option>";
      }).join("") + "</select>";
    var s = wrap.querySelector("select");
    if (opts.value) s.value = opts.value;
    s.addEventListener("change", onchange);
    wrap.value = function () { return s.value; };
    return wrap;
  }

  function toggles(items, onchange) {
    var wrap = el("div", "switchrow");
    var state = {};
    items.forEach(function (it) {
      state[it.key] = !!it.on;
      var b = el("button", "switch" + (it.danger ? " danger" : ""), it.label);
      b.type = "button";
      b.setAttribute("aria-pressed", String(!!it.on));
      b.addEventListener("click", function () {
        state[it.key] = !state[it.key];
        b.setAttribute("aria-pressed", String(state[it.key]));
        onchange();
      });
      wrap.appendChild(b);
    });
    wrap.value = function () { return state; };
    return wrap;
  }

  function readout(cells) {
    var wrap = el("div", "readout");
    cells.forEach(function (c) {
      wrap.appendChild(el("div", "cell " + (c.tone || ""),
        "<b>" + c.value + "</b><span>" + c.label + "</span>"));
    });
    return wrap;
  }

  function verdict(tone, title, body) {
    return '<div class="verdict ' + tone + '"><b>' + title + "</b>" + body + "</div>";
  }

  /* =======================================================================
     M1 — the agent loop, stepped one wire event at a time.
     ======================================================================= */

  var SCENARIOS = {
    happy: {
      label: "Happy path (parallel tools)",
      prompt: "What's the weather in Oslo and Lisbon? Then email the summary to me.",
      events: [
        { k: "user", text: "What's the weather in Oslo and Lisbon? Then email the summary to me.",
          note: "You append a user message. The messages array is now length 1. Nothing has been executed.", tin: 620, tout: 0 },
        { k: "assistant", stop: "tool_use",
          blocks: [
            { type: "text", text: "I'll check both cities." },
            { type: "tool_use", id: "toolu_01", name: "get_weather", input: { city: "Oslo" } },
            { type: "tool_use", id: "toolu_02", name: "get_weather", input: { city: "Lisbon" } }
          ],
          note: "Two tool_use blocks in ONE assistant turn. stop_reason is tool_use. The model has not called anything — it has emitted a request. Your loop must handle N blocks, not 1.", tin: 620, tout: 96 },
        { k: "exec", note: "Your executor runs both. These are independent, so run them concurrently — this is where naive loops leak latency.",
          calls: ["get_weather(city='Oslo')", "get_weather(city='Lisbon')"] },
        { k: "result", blocks: [
            { id: "toolu_01", content: "4C, light rain" },
            { id: "toolu_02", content: "19C, clear" }
          ],
          note: "Both results go back in a SINGLE user message, one tool_result block per tool_use id. Miss one id and the API rejects the turn.", tin: 760, tout: 0 },
        { k: "assistant", stop: "tool_use",
          blocks: [{ type: "tool_use", id: "toolu_03", name: "send_email",
            input: { to: "me", subject: "Weather", body: "Oslo 4C rain; Lisbon 19C clear" } }],
          note: "Turn 2. The model now has both results in context and moves to the side-effecting step. This is the block you gate on — not the read-only ones.", tin: 760, tout: 74 },
        { k: "exec", note: "A permission check belongs here, before execution, not in the prompt.",
          calls: ["send_email(to='me', …)"] },
        { k: "result", blocks: [{ id: "toolu_03", content: "sent id=msg_88" }],
          note: "Result returned. Note the message array is now 5 long and every earlier turn is re-sent on the next call.", tin: 910, tout: 0 },
        { k: "assistant", stop: "end_turn",
          blocks: [{ type: "text", text: "Oslo is 4C with light rain, Lisbon 19C and clear. I've emailed you the summary." }],
          note: "stop_reason is end_turn and there are no tool_use blocks: the loop exits. This — not a token, not a sentinel string — is your termination condition.", tin: 910, tout: 42 }
      ]
    },
    hallucinated: {
      label: "Hallucinated tool name",
      prompt: "Give me the 10-day forecast for Oslo.",
      events: [
        { k: "user", text: "Give me the 10-day forecast for Oslo.",
          note: "Only get_weather (current conditions) is registered. There is no forecast tool.", tin: 600, tout: 0 },
        { k: "assistant", stop: "tool_use",
          blocks: [{ type: "tool_use", id: "toolu_01", name: "get_forecast", input: { city: "Oslo", days: 10 } }],
          note: "The model emitted a tool that does not exist. This is an ordinary, well-formed model output — the API did not error. YOUR code must reject it.", tin: 600, tout: 58 },
        { k: "exec", err: true, note: "Executor looks up 'get_forecast' in the registry: miss. The wrong move is to raise. The right move is to return an error result the model can read.",
          calls: ["registry['get_forecast'] -> KeyError"] },
        { k: "result", err: true, blocks: [{ id: "toolu_01",
            content: "Error: unknown tool 'get_forecast'. Available: get_weather(city). No forecast data is available.", isError: true }],
          note: "is_error: true plus a message that says what IS available. An error that only says 'failed' teaches the model nothing and it will retry identically.", tin: 700, tout: 0 },
        { k: "assistant", stop: "end_turn",
          blocks: [{ type: "text", text: "I can't get a 10-day forecast — I only have current conditions. Oslo right now is 4C with light rain. Want that instead?" }],
          note: "The model recovered because the error was informative. Graceful degradation is a property of your error strings, not of the model.", tin: 700, tout: 51 }
      ]
    },
    thrash: {
      label: "Error thrash into the turn cap",
      prompt: "Look up customer 5512 and update their plan.",
      events: [
        { k: "user", text: "Look up customer 5512 and update their plan.", note: "The CRM backend is down. It will stay down for the whole run.", tin: 640, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "t1", name: "crm_lookup", input: { id: "5512" } }],
          note: "Attempt 1.", tin: 640, tout: 40 },
        { k: "result", err: true, blocks: [{ id: "t1", content: "Error: 503 upstream unavailable", isError: true }],
          note: "A transient-looking error. The model will reasonably retry.", tin: 700, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "t2", name: "crm_lookup", input: { id: "5512" } }],
          note: "Attempt 2 — identical arguments. Nothing in context tells the model that retrying is futile.", tin: 700, tout: 40 },
        { k: "result", err: true, blocks: [{ id: "t2", content: "Error: 503 upstream unavailable", isError: true }],
          note: "Same error. Cost is accruing on every turn, and every turn re-sends the whole history.", tin: 760, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "t3", name: "crm_lookup", input: { id: "5512" } }],
          note: "Attempt 3. Without a cap this continues until your bill notices.", tin: 760, tout: 40 },
        { k: "stop", note: "Turn cap reached (max_turns=3). The loop exits and returns a partial result with a reason. A cap is not a nicety: it is the only thing standing between a bad afternoon and a bad quarter.", tin: 760, tout: 0 }
      ]
    },
    oscillate: {
      label: "Oscillation (no progress)",
      prompt: "Find the cheapest flight and book it.",
      events: [
        { k: "user", text: "Find the cheapest flight and book it.", note: "Two tools: search_flights and check_price. Neither ever settles the question.", tin: 660, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "a1", name: "search_flights", input: { to: "LIS" } }], note: "Search.", tin: 660, tout: 44 },
        { k: "result", blocks: [{ id: "a1", content: "3 options, prices may be stale" }], note: "The phrase 'may be stale' invites a re-check. Tool return text steers behaviour.", tin: 730, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "a2", name: "check_price", input: { flight: "BA512" } }], note: "Check.", tin: 730, tout: 44 },
        { k: "result", blocks: [{ id: "a2", content: "price changed, re-search recommended" }], note: "And the other tool invites a re-search. The two tools point at each other.", tin: 800, tout: 0 },
        { k: "assistant", stop: "tool_use", blocks: [{ type: "tool_use", id: "a3", name: "search_flights", input: { to: "LIS" } }], note: "Search again — identical arguments to turn 1. This is the signature: a repeated (tool, args) pair with no new information between them.", tin: 800, tout: 44 },
        { k: "stop", note: "A no-progress detector fires: the same (tool, args) pair seen twice with no intervening state change. Cheaper than the turn cap and far more diagnosable.", tin: 800, tout: 0 }
      ]
    }
  };

  register("loop-sim", {
    title: "The loop, one wire event at a time",
    sub: "Step through what actually crosses the wire. Nothing here calls a model."
  }, function (body) {
    var scen = select({
      label: "Scenario",
      options: Object.keys(SCENARIOS).map(function (k) { return [k, SCENARIOS[k].label]; })
    }, reset);

    var controls = el("div", "controls");
    controls.appendChild(scen);
    body.appendChild(controls);

    var btns = el("div", "switchrow");
    var stepBtn = el("button", "switch", "step ▸");
    var allBtn = el("button", "switch", "run to end ▸▸");
    var resetBtn = el("button", "switch", "reset");
    [stepBtn, allBtn, resetBtn].forEach(function (b) { b.type = "button"; btns.appendChild(b); });
    body.appendChild(btns);

    var strip = el("div", "turnstrip");
    body.appendChild(strip);
    var noteBox = el("div", "verdict");
    body.appendChild(noteBox);
    var stats = el("div", "");
    body.appendChild(stats);

    var i = 0;

    function renderEvent(e) {
      var cls, who, meta = "";
      if (e.k === "user") { cls = "t-user"; who = "user"; }
      else if (e.k === "assistant") { cls = "t-model"; who = "assistant"; meta = "stop_reason: " + e.stop; }
      else if (e.k === "exec") { cls = e.err ? "t-err" : "t-tool"; who = "your code"; }
      else if (e.k === "result") { cls = e.err ? "t-err" : "t-tool"; who = "user (tool_result)"; }
      else { cls = "t-err"; who = "loop exit"; }

      var inner = "";
      if (e.text) inner += "<pre>" + esc(e.text) + "</pre>";
      if (e.calls) inner += e.calls.map(function (c) {
        return '<div class="blk"><pre>' + esc(c) + "</pre></div>";
      }).join("");
      if (e.blocks) {
        inner += e.blocks.map(function (b) {
          if (b.type === "text") return '<div class="blk"><pre>' + esc(b.text) + "</pre></div>";
          if (b.type === "tool_use") {
            return '<div class="blk"><pre>{"type": "tool_use", "id": "' + b.id +
              '",\n "name": "' + b.name + '",\n "input": ' + JSON.stringify(b.input) + "}</pre></div>";
          }
          return '<div class="blk"><pre>{"type": "tool_result", "tool_use_id": "' + b.id + '",' +
            (b.isError ? '\n "is_error": true,' : "") +
            '\n "content": "' + esc(b.content) + '"}</pre></div>';
        }).join("");
      }
      if (e.k === "stop") inner += "<pre>loop terminated</pre>";

      var card = el("div", "turn " + cls,
        '<div class="who"><b>' + who + "</b>" + (meta ? "<em>" + meta + "</em>" : "") + "</div>" + inner);
      return card;
    }

    function esc(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function step() {
      var s = SCENARIOS[scen.value()];
      if (i >= s.events.length) return false;
      var e = s.events[i++];
      strip.appendChild(renderEvent(e));
      strip.scrollTop = strip.scrollHeight;
      noteBox.className = "verdict " + (e.err || e.k === "stop" ? "bad" : "ok");
      noteBox.innerHTML = "<b>What your code does here</b>" + e.note;
      paintStats();
      return i < s.events.length;
    }

    function paintStats() {
      var s = SCENARIOS[scen.value()];
      var seen = s.events.slice(0, i);
      var apiCalls = seen.filter(function (e) { return e.k === "assistant"; }).length;
      var tin = seen.reduce(function (a, e) { return a + (e.k === "assistant" ? e.tin : 0); }, 0);
      var tout = seen.reduce(function (a, e) { return a + (e.tout || 0); }, 0);
      var toolRuns = seen.filter(function (e) { return e.k === "exec"; })
        .reduce(function (a, e) { return a + e.calls.length; }, 0);
      stats.innerHTML = "";
      stats.appendChild(readout([
        { label: "API calls", value: apiCalls },
        { label: "tool executions", value: toolRuns },
        { label: "input tokens (cum.)", value: num(tin) },
        { label: "output tokens", value: num(tout) },
        { label: "billed ratio in:out", value: tout ? (tin / tout).toFixed(1) + ":1" : "—",
          tone: tin / Math.max(tout, 1) > 10 ? "warn" : "" }
      ]));
    }

    function reset() {
      i = 0;
      strip.innerHTML = "";
      var s = SCENARIOS[scen.value()];
      noteBox.className = "verdict";
      noteBox.innerHTML = "<b>Ready</b>Task: <em>" + s.prompt +
        "</em> — press <strong>step</strong> to advance one event.";
      paintStats();
    }

    stepBtn.addEventListener("click", step);
    allBtn.addEventListener("click", function () { while (step()) {} });
    resetBtn.addEventListener("click", reset);
    reset();
  });

  /* =======================================================================
     M2 — tool definition linter. Real string analysis against the rubric.
     ======================================================================= */

  var SAMPLE_TOOL = JSON.stringify({
    name: "get_data",
    description: "Gets data.",
    input_schema: {
      type: "object",
      properties: {
        id: { type: "string" },
        flag: { type: "boolean" },
        format: { type: "string" }
      },
      required: ["id"]
    }
  }, null, 2);

  var GOOD_TOOL = JSON.stringify({
    name: "crm_search_customers",
    description:
      "Search the CRM for customers by name, email or account number. Use this when you " +
      "need a customer's internal ID before calling any other crm_* tool. Returns up to 20 " +
      "matches as name, email, account_number and customer_id. Returns an empty list (not " +
      "an error) when nothing matches — widen the query and retry.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Free text: a name, email address or account number." },
        status: { type: "string", enum: ["active", "churned", "trial", "any"],
          description: "Filter by account status. Use 'any' unless the user asked to narrow it." },
        limit: { type: "integer", description: "Max results, 1-20. Default 10." }
      },
      required: ["query"]
    }
  }, null, 2);

  function lintTool(def) {
    var f = [];
    function add(sev, title, detail) { f.push({ sev: sev, title: title, detail: detail }); }

    if (typeof def !== "object" || !def) {
      return [{ sev: "high", title: "Not an object", detail: "A tool definition must be a JSON object." }];
    }

    /* --- name --- */
    var name = def.name || "";
    if (!name) add("high", "No name", "Every tool needs a name the model can emit.");
    else {
      if (!/^[a-z][a-z0-9_]*$/.test(name))
        add("med", "Name is not snake_case", "<code>" + name + "</code> — mixed conventions across a tool set cost the model accuracy for nothing.");
      if (name.indexOf("_") === -1 && name.length < 12)
        add("med", "Name is not namespaced", "<code>" + name + "</code> will collide once you add a second integration. Prefix by system: <code>crm_" + name + "</code>.");
      if (/^(get|do|handle|process|manage)_?(data|thing|it|stuff|info)?$/.test(name))
        add("high", "Name says nothing", "<code>" + name + "</code> gives the model no signal about when to reach for it. Name the job, not the verb.");
    }

    /* --- description --- */
    var d = def.description || "";
    if (!d) add("high", "No description", "The description IS the prompt. Without it the model is guessing from the name.");
    else {
      if (d.length < 40)
        add("high", "Description too thin (" + d.length + " chars)", "Aim for 200-800 characters. Say what it does, when to use it, what it returns, and what happens on no-match.");
      else if (d.length < 120)
        add("med", "Description is short (" + d.length + " chars)", "Add the trigger condition — the sentence starting 'Use this when…'.");
      if (d.length > 1400)
        add("low", "Description very long (" + d.length + " chars)", "This is re-sent on every single turn. Move detail into the parameter descriptions or a skill.");
      if (!/use (this|it) when|call (this|it) when|when you need|when the user/i.test(d))
        add("med", "No trigger condition", "Nothing tells the model <em>when</em> to select this over its neighbours. Add an explicit 'Use this when…'.");
      if (!/returns?|responds? with|yields/i.test(d))
        add("med", "Return shape undocumented", "The model plans its next turn from what it expects back. Say what comes out.");
      if (name && d.toLowerCase().replace(/[^a-z]/g, "") ===
          name.replace(/_/g, "").toLowerCase() + "s")
        add("high", "Description restates the name", "Zero information added.");
      if (/\b(error|fail|empty|not found|no match)\b/i.test(d) === false)
        add("low", "No failure semantics", "Say what an empty result looks like, so the model doesn't treat 'no rows' as 'broken'.");
    }

    /* --- schema --- */
    var schema = def.input_schema || def.inputSchema || {};
    var props = schema.properties || {};
    var keys = Object.keys(props);
    if (!keys.length) {
      add("med", "No parameters declared", "If the tool truly takes none, fine. If it does, the model will invent them.");
    } else {
      keys.forEach(function (k) {
        var p = props[k] || {};
        if (!p.description)
          add("high", "Parameter <code>" + k + "</code> has no description", "Undescribed parameters are filled by guesswork — the single most common cause of malformed arguments.");
        if (/^(data|input|value|param|arg|opts|options|payload)$/.test(k))
          add("med", "Vague parameter name <code>" + k + "</code>", "Name the content, not its role in your code.");
        if (p.type === "boolean")
          add("low", "Boolean parameter <code>" + k + "</code>", "Booleans that switch behaviour are hard to select correctly. An enum with named modes is easier for the model and self-documenting.");
        if (p.type === "string" && !p.enum && /^(status|type|mode|format|kind|state|level)$/.test(k))
          add("med", "<code>" + k + "</code> is a closed set typed as free string", "Add an <code>enum</code>. This converts a class of hallucination into a schema error you never see.");
        if (/(^|_)id$/.test(k) && !(p.description || "").match(/from|obtain|retriev|search|lookup/i))
          add("med", "<code>" + k + "</code> is an opaque identifier", "Say where the model gets it (\"the customer_id returned by crm_search_customers\"), or it will invent one.");
      });
      if (keys.length > 8)
        add("med", keys.length + " parameters", "Past roughly eight, argument accuracy drops sharply. Split the tool or take a structured object.");
      if (!schema.required)
        add("low", "No <code>required</code> list", "The model cannot tell mandatory from optional, so it over-supplies or under-supplies.");
    }

    if (!f.length) add("ok", "Nothing flagged", "This passes the mechanical checks. Mechanical checks are the floor, not the ceiling — the eval set is the real judge.");
    return f;
  }

  register("tool-linter", {
    title: "Tool definition linter",
    sub: "The mechanical half of the M2 rubric. Edit the JSON; findings update live."
  }, function (body) {
    var ta = el("div", "control");
    ta.innerHTML = "<label>Tool definition (JSON)</label><textarea spellcheck='false'></textarea>";
    var text = ta.querySelector("textarea");
    text.value = SAMPLE_TOOL;
    body.appendChild(ta);

    var row = el("div", "switchrow");
    var b1 = el("button", "switch", "load flawed example");
    var b2 = el("button", "switch", "load rewritten example");
    [b1, b2].forEach(function (b) { b.type = "button"; row.appendChild(b); });
    body.appendChild(row);

    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var def, findings;
      try {
        def = JSON.parse(text.value);
      } catch (e) {
        out.innerHTML = verdict("bad", "Invalid JSON", e.message);
        return;
      }
      findings = lintTool(def);
      var high = findings.filter(function (x) { return x.sev === "high"; }).length;
      var med = findings.filter(function (x) { return x.sev === "med"; }).length;
      var score = Math.max(0, 100 - high * 18 - med * 9 -
        findings.filter(function (x) { return x.sev === "low"; }).length * 3);

      out.innerHTML = "";
      out.appendChild(readout([
        { label: "rubric score", value: score, tone: score >= 80 ? "good" : score >= 55 ? "" : "warn" },
        { label: "blocking", value: high, tone: high ? "warn" : "good" },
        { label: "should fix", value: med },
        { label: "def tokens/turn", value: "~" + num(Math.round(JSON.stringify(def).length / 3.6)) }
      ]));
      var ul = el("ul", "findings");
      findings.forEach(function (x) {
        ul.appendChild(el("li", "sev-" + x.sev, "<b>" + x.title + "</b>" + x.detail));
      });
      out.appendChild(ul);
    }

    text.addEventListener("input", run);
    b1.addEventListener("click", function () { text.value = SAMPLE_TOOL; run(); });
    b2.addEventListener("click", function () { text.value = GOOD_TOOL; run(); });
    run();
  });

  /* =======================================================================
     M3 — context budget. Where the window actually goes, and what it costs.
     ======================================================================= */

  register("context-budget", {
    title: "Context budget model",
    sub: "Move the sliders until you can predict the failure before it happens."
  }, function (body) {
    var WINDOW = 200000;
    var c = el("div", "controls");
    var sys = slider({ label: "System prompt", min: 200, max: 20000, step: 100, value: 1200,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var nTools = slider({ label: "Tools available", min: 0, max: 80, value: 12 }, run);
    var toolSize = slider({ label: "Avg tool definition", min: 60, max: 900, step: 10, value: 260,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var turns = slider({ label: "Turns elapsed", min: 1, max: 120, value: 30 }, run);
    var resSize = slider({ label: "Avg tool result", min: 100, max: 20000, step: 100, value: 2600,
      fmt: function (v) { return num(v) + " tok"; } }, run);
    var strategy = select({ label: "Long-horizon strategy", options: [
      ["none", "None — append everything"],
      ["compact", "Compaction (summarise at threshold)"],
      ["notes", "Structured note-taking"],
      ["subagent", "Sub-agent isolation"]
    ] }, run);
    [sys, nTools, toolSize, turns, resSize, strategy].forEach(function (x) { c.appendChild(x); });
    body.appendChild(c);

    var sw = toggles([
      { key: "cache", label: "prompt caching on", on: true },
      { key: "jit", label: "JIT retrieval (return ids, not payloads)", on: false }
    ], run);
    body.appendChild(sw);

    var bar = el("div", "");
    body.appendChild(bar);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var t = sw.value();
      var toolDefs = nTools.value() * toolSize.value() + (nTools.value() ? 300 : 0);
      var perTurnMsg = 180;
      var result = t.jit ? Math.round(resSize.value() * 0.18) : resSize.value();
      var st = strategy.value();

      var history, overhead = 0, label;
      if (st === "none") {
        history = turns.value() * (perTurnMsg + result);
        label = "full transcript";
      } else if (st === "compact") {
        // Summarise everything older than the last 10 turns down to ~8%.
        var recent = Math.min(turns.value(), 10);
        var older = Math.max(0, turns.value() - 10);
        history = recent * (perTurnMsg + result) + Math.round(older * (perTurnMsg + result) * 0.08);
        overhead = Math.ceil(turns.value() / 10) * 1500; // each compaction pass costs a call
        label = "recent turns + running summary";
      } else if (st === "notes") {
        var recentN = Math.min(turns.value(), 6);
        history = recentN * (perTurnMsg + result) + 900; // the notes file itself
        overhead = turns.value() * 120;
        label = "recent turns + notes file";
      } else {
        history = Math.min(turns.value(), 4) * perTurnMsg + turns.value() * 220;
        overhead = turns.value() * 2400; // sub-agent contexts, paid but not carried
        label = "orchestrator sees findings only";
      }

      var live = sys.value() + toolDefs + history;
      var pct = live / WINDOW;

      // Cost proxy: relative units, so the shape is right without asserting prices.
      var uncached = live * turns.value();
      var cached = (sys.value() + toolDefs) * turns.value() * 0.1 + history * turns.value() * 0.55;
      var relCost = (t.cache ? cached : uncached) + overhead * turns.value() * 0.2;

      var parts = [
        { label: "system", tok: sys.value(), color: "#1f5f5b" },
        { label: "tool defs", tok: toolDefs, color: "#8a6d1f" },
        { label: label, tok: history, color: "#a8452c" },
        { label: "free", tok: Math.max(0, WINDOW - live), color: "var(--paper-2)" }
      ];
      bar.innerHTML = '<div class="bar-stack">' + parts.map(function (p) {
        return '<i style="width:' + (p.tok / WINDOW * 100).toFixed(2) + "%;background:" + p.color + '"></i>';
      }).join("") + "</div>" +
        '<div class="legend">' + parts.map(function (p) {
          return "<span><i style='background:" + p.color + "'></i>" + p.label + " · " + num(p.tok) + "</span>";
        }).join("") + "</div>";

      var tone = pct > 0.6 ? "warn" : pct > 0.3 ? "" : "good";
      out.innerHTML = "";
      out.appendChild(readout([
        { label: "live context", value: num(live), tone: tone },
        { label: "of window", value: (pct * 100).toFixed(1) + "%", tone: tone },
        { label: "tool-def tax/turn", value: num(toolDefs), tone: toolDefs > 8000 ? "warn" : "" },
        { label: "relative cost", value: num(Math.round(relCost / 1000)) + "k units" },
        { label: "caching", value: t.cache ? "on" : "off", tone: t.cache ? "good" : "warn" }
      ]));

      var msg;
      if (pct > 0.7) {
        msg = verdict("bad", "Degradation zone",
          "You are past the point where recall reliably holds. Nothing will error — answers just get " +
          "worse, and the gradient is why this is dangerous. Change the strategy, not the window size.");
      } else if (toolDefs > 8000) {
        msg = verdict("warn", "Tool definitions dominate",
          "You are paying " + num(toolDefs) + " tokens before the user has said anything, on <em>every</em> turn. " +
          "This is the M6 problem arriving early: consolidate, or move to tool search.");
      } else if (st === "none" && turns.value() > 40) {
        msg = verdict("warn", "No long-horizon strategy",
          "At " + turns.value() + " turns with an append-only transcript you are re-sending the whole " +
          "history every call. Pick a strategy — the choice is a Decision Log entry, not a default.");
      } else {
        msg = verdict("ok", "Workable",
          "Live context is " + (pct * 100).toFixed(1) + "% of the window with " + label +
          ". Confirm it holds at turn 60 with the M3 benchmark before you believe it.");
      }
      out.insertAdjacentHTML("beforeend", msg);
    }
    run();
  });

  /* =======================================================================
     M4 — autonomy decision framework, as a decision procedure.
     ======================================================================= */

  var Q4 = [
    { key: "steps", q: "Can you enumerate the steps in advance?",
      a: [["yes", "Yes — I could draw the flowchart today"], ["mostly", "Mostly, with a few branches"], ["no", "No — it depends on what's found"]] },
    { key: "branch", q: "Does the next step depend on what earlier steps discovered?",
      a: [["no", "No, it's a fixed pipeline"], ["shallow", "A little — a routing decision up front"], ["deep", "Yes, deeply and repeatedly"]] },
    { key: "value", q: "What is one successful task worth?",
      a: [["low", "Cents — high volume, low stakes"], ["mid", "A dollar or two"], ["high", "Materially more than $0.50 of compute"]] },
    { key: "rev", q: "Are the actions reversible?",
      a: [["yes", "Yes, or read-only"], ["some", "Some are not"], ["no", "No — money moves, mail sends, data changes"]] },
    { key: "eval", q: "Can you tell automatically whether a run succeeded?",
      a: [["yes", "Yes — programmatic or judged"], ["partly", "Partly, with human spot checks"], ["no", "No, not really"]] },
    { key: "quality", q: "Would a second pass measurably improve the output?",
      a: [["no", "No, one pass is the answer"], ["yes", "Yes — there are clear quality criteria to iterate against"]] },
    { key: "parallel", q: "Can the work be split into independent chunks?",
      a: [["no", "No, it's inherently sequential"], ["yes", "Yes, many independent sub-questions"]] }
  ];

  register("autonomy-chooser", {
    title: "Autonomy decision framework",
    sub: "The M4 questions, applied. The output is a starting point you must defend, not an oracle."
  }, function (body) {
    var state = {};
    var form = el("div", "");
    Q4.forEach(function (q) {
      var wrap = el("div", "control");
      wrap.style.flex = "1 1 100%";
      wrap.innerHTML = "<label>" + q.q + "</label>";
      var row = el("div", "switchrow");
      q.a.forEach(function (opt) {
        var b = el("button", "switch", opt[1]);
        b.type = "button";
        b.addEventListener("click", function () {
          state[q.key] = opt[0];
          row.querySelectorAll(".switch").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
          b.setAttribute("aria-pressed", "true");
          run();
        });
        row.appendChild(b);
      });
      wrap.appendChild(row);
      form.appendChild(wrap);
    });
    body.appendChild(form);
    var out = el("div", "");
    body.appendChild(out);

    function run() {
      var answered = Object.keys(state).length;
      if (answered < Q4.length) {
        out.innerHTML = verdict("", "Incomplete",
          answered + " of " + Q4.length + " answered. All seven matter — the framework is only " +
          "useful when it can say no.");
        return;
      }
      if (state.eval === "no") {
        out.innerHTML = verdict("bad", "Do not deploy — yet",
          "You cannot tell whether a run succeeded. Everything downstream of that is guesswork: you " +
          "can't tune it, you can't catch a regression, and you won't know it broke until a user tells you. " +
          "Go build the eval set (M8). This answer overrides every other input.");
        return;
      }
      var rec, why;
      if (state.steps === "yes" && state.branch === "no") {
        rec = "Prompt chaining (workflow)";
        why = "Fixed steps, no findings-dependence. A chain is faster, cheaper, debuggable and testable per stage. Adding autonomy here buys nothing and costs latency, tokens and error surface.";
      } else if (state.branch === "shallow" && state.steps !== "no") {
        rec = "Routing (workflow)";
        why = "One classification up front, then specialised handling. In the M4 lab this beats the agent on the same task most of the time — cheaper, more predictable, and each route is separately evaluable.";
      } else if (state.parallel === "yes" && state.branch !== "deep") {
        rec = "Parallelisation — sectioning or voting (workflow)";
        why = "Independent chunks fan out. Sectioning for throughput; voting when you need confidence on a judgement call. Both keep the control flow in your code, where you can see it.";
      } else if (state.quality === "yes" && state.branch !== "deep") {
        rec = "Evaluator-optimiser (workflow)";
        why = "Clear quality criteria plus measurable improvement on a second pass is exactly this pattern's shape. Cap the iterations — the loop must terminate on a budget, not on satisfaction.";
      } else if (state.parallel === "yes" && state.branch === "deep" && state.value === "high") {
        rec = "Orchestrator-workers (multi-agent)";
        why = "Deep findings-dependence plus genuine parallelism plus value that can absorb the token multiple. Read M9 before you build it, and set the cost ceiling first.";
      } else if (state.branch === "deep" && state.value !== "low") {
        rec = "Autonomous agent (single)";
        why = "Unpredictable step count driven by environmental feedback. You're buying flexibility with latency, tokens, error surface and debuggability. That purchase is defensible here — write down the price in the Decision Log.";
      } else {
        rec = "Single model call, or a two-step chain";
        why = "The value per task doesn't support a loop, and the branching is shallow. Start with the cheapest thing that could work and let the eval set tell you when it stops working.";
      }

      var flags = [];
      if (state.rev === "no")
        flags.push("<b>Irreversible actions</b>Gate every mutating tool behind approval (M13) and give it a dry-run mode. Autonomy over irreversible actions is a product decision, not an engineering one.");
      if (state.value === "low" && rec.indexOf("Orchestrator") === 0)
        flags.push("<b>Cost mismatch</b>Multi-agent on low-value tasks is how a demo becomes an incident. Recheck the arithmetic in M9.");
      if (state.eval === "partly")
        flags.push("<b>Partial evaluability</b>Spot checks catch collapses, not drift. Budget for a real eval set before scaling traffic.");

      out.innerHTML = verdict("ok", "Recommended starting architecture",
        "<strong>" + rec + "</strong><br>" + why) +
        (flags.length ? '<ul class="findings">' + flags.map(function (x) {
          return '<li class="sev-med">' + x + "</li>";
        }).join("") + "</ul>" : "");
    }
    run();
  });

  /* ---------------- init ------------------------------------------------ */

  function init() {
    document.querySelectorAll(".widget[data-widget]").forEach(function (host) {
      var name = host.dataset.widget;
      var build = REG[name];
      var meta = META[name] || { title: name, sub: "" };
      if (!build) {
        host.innerHTML = '<div class="widget-body"><em>Widget "' + name + '" is not loaded.</em></div>';
        return;
      }
      var cfg = {};
      try { cfg = JSON.parse(host.dataset.config || "{}"); } catch (e) {}
      host.innerHTML = '<div class="widget-head"><h4>' + meta.title + "</h4>" +
        '<span class="sub">' + meta.sub + "</span></div>";
      var body = el("div", "widget-body");
      host.appendChild(body);
      try {
        build(body, cfg, host);
      } catch (e) {
        body.innerHTML = "<em>This widget failed to start: " + e.message + "</em>";
      }
    });
  }

  window.BAIWidgets = {
    init: init, register: register, el: el, num: num, money: money,
    slider: slider, select: select, toggles: toggles, readout: readout, verdict: verdict
  };
})();

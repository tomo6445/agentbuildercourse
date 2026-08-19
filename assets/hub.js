/* =========================================================================
   Hub page — renders the module grid from the data the build step inlined,
   and keeps completion state in sync with the lesson pages.
   Runs on DOMContentLoaded, so window.BAI (course.js) is already defined.
   ========================================================================= */
(function () {
  "use strict";

  function start() {
    var Store = (window.BAI && window.BAI.Store) || {
      read: function () { return { done: [], quiz: {} }; },
      isDone: function () { return false; },
      toggle: function () { return false; },
      reset: function () {}
    };

    var main = document.getElementById("main");
    var activePhase = null, coreOnly = false, query = "";

    /* ---- filter chips ---- */
    var chipWrap = document.getElementById("phasechips");
    chipWrap.innerHTML =
      '<button class="chip" data-p="all" aria-pressed="true">All</button>' +
      PHASES.map(function (p) {
        return '<button class="chip" data-p="' + p.id + '" aria-pressed="false">' +
          p.id + ". " + p.name + "</button>";
      }).join("");

    /* ---- cards ---- */
    function card(m) {
      var tags = ['<span class="tag t-hrs">' + m.hrs + "h</span>"]
        .concat(m.core ? ['<span class="tag t-core">core path</span>'] : [])
        .concat(m.tags.map(function (t) { return '<span class="tag">' + t + "</span>"; }))
        .join("");
      var learn = m.learn.length
        ? '<div class="dsec"><h4>What you learn</h4><ul>' +
          m.learn.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul></div>"
        : "";
      var labs = m.labs.length
        ? '<div class="dsec"><h4>Lab packages</h4><ul>' +
          m.labs.map(function (x) { return "<li><code>" + x + "</code></li>"; }).join("") +
          "</ul></div>"
        : "";
      return '<article class="card" data-n="' + m.n + '" data-phase="' + m.phase +
        '" data-core="' + m.core + '">' +
        '<div class="card-top">' +
        '<span class="modnum">' + m.n + "</span>" +
        '<h3><a href="' + m.href + '">' + m.title + "</a></h3>" +
        '<button class="tick" title="Mark complete" aria-label="Mark ' + m.n +
        ' complete">&#10003;</button>' +
        "</div>" +
        '<div class="card-body"><p class="one-liner">' + m.line + "</p>" +
        '<div class="tags">' + tags + "</div></div>" +
        '<div class="card-foot"><button class="expand">Detail <span>+</span></button>' +
        '<a class="start" href="' + m.href + '">Open &#8594;</a></div>' +
        '<div class="detail">' + learn + labs +
        '<div class="dsec gate"><h4>Ship gate</h4><p>' + m.gate + "</p></div></div>" +
        "</article>";
    }

    var html = "";
    PHASES.forEach(function (p) {
      var mods = MODULES.filter(function (m) { return m.phase === p.id; });
      var hrs = mods.reduce(function (a, b) { return a + b.hrs; }, 0);
      html += '<section class="phase" data-phase="' + p.id + '">' +
        '<div class="phase-head"><span class="phase-num">' + p.num.toUpperCase() + "</span>" +
        "<h2>" + p.name + "</h2>" +
        '<span class="phase-hours">' + mods.length + " modules &middot; " +
        hrs.toFixed(1) + "h</span></div>" +
        '<p class="phase-blurb">' + p.blurb + "</p>" +
        '<div class="grid">' + mods.map(card).join("") + "</div></section>";
    });

    html += '<section class="capstone"><span class="phase-num">' +
      "CAPSTONE &middot; M16 &middot; 8 HOURS OVER 2 WEEKS</span>" +
      "<h2>Ship one real thing and defend it</h2>" +
      "<p>Seven stages, in order, with the eval suite written before the agent. A hard cost " +
      "ceiling set at stage 1 and enforced in CI. A required graceful-failure demo under a fault " +
      "you didn't choose. And a scope change from the stakeholder at day 5, because that is what " +
      "actually happens.</p><div class=\"stages\">" +
      CAPSTONE_STAGES.map(function (s) {
        return '<div class="stage"><b>' + s.n + "</b><h5>" + s.t + "</h5><p>" + s.d +
          '</p><span class="wt">weight ' + s.w + "</span></div>";
      }).join("") + "</div></section>";

    html += '<section class="pillars">' + PILLARS.map(function (p) {
      return '<div class="pillar"><div class="n">' + p.n + "</div><h3>" + p.h + "</h3><p>" +
        p.p + "</p></div>";
    }).join("") + "</section>";

    main.innerHTML = html;

    /* ---- behaviour ---- */
    main.querySelectorAll(".expand").forEach(function (b) {
      b.addEventListener("click", function () {
        var c = b.closest(".card");
        var open = c.classList.toggle("open");
        b.innerHTML = open ? "Detail <span>&minus;</span>" : "Detail <span>+</span>";
      });
    });

    main.querySelectorAll(".tick").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        Store.toggle(b.closest(".card").dataset.n);
        paint();
      });
    });

    function paint() {
      var state = Store.read();
      main.querySelectorAll(".card").forEach(function (c) {
        c.classList.toggle("done", state.done.indexOf(c.dataset.n) !== -1);
      });
      var hrs = MODULES.filter(function (m) { return state.done.indexOf(m.n) !== -1; })
        .reduce(function (a, b) { return a + b.hrs; }, 0);
      var total = MODULES.reduce(function (a, b) { return a + b.hrs; }, 0);
      document.getElementById("bar").style.width = (hrs / total * 100) + "%";
      document.getElementById("ptext").textContent =
        state.done.length + " / " + MODULES.length + " · " + hrs.toFixed(1) + "h";
    }

    function filter() {
      var q = query.toLowerCase().trim();
      var any = false;
      main.querySelectorAll(".card").forEach(function (c) {
        var m = MODULES.filter(function (x) { return x.n === c.dataset.n; })[0];
        var ok = true;
        if (activePhase !== null && m.phase !== activePhase) ok = false;
        if (coreOnly && !m.core) ok = false;
        if (q) {
          var hay = (m.n + " " + m.title + " " + m.line + " " + m.tags.join(" ") + " " +
            m.learn.join(" ") + " " + m.labs.join(" ") + " " + m.gate).toLowerCase();
          if (hay.indexOf(q) === -1) ok = false;
        }
        c.classList.toggle("hidden", !ok);
        if (ok) any = true;
      });
      main.querySelectorAll(".phase").forEach(function (s) {
        s.style.display = s.querySelectorAll(".card:not(.hidden)").length ? "" : "none";
      });
      var e = main.querySelector(".empty");
      if (!any && !e) {
        e = document.createElement("div");
        e.className = "empty";
        e.textContent = "No modules match. Try a different term.";
        main.prepend(e);
      } else if (any && e) e.remove();
    }

    document.getElementById("q").addEventListener("input", function (e) {
      query = e.target.value;
      filter();
    });
    chipWrap.addEventListener("click", function (e) {
      var b = e.target.closest(".chip");
      if (!b) return;
      chipWrap.querySelectorAll(".chip").forEach(function (x) {
        x.setAttribute("aria-pressed", "false");
      });
      b.setAttribute("aria-pressed", "true");
      activePhase = b.dataset.p === "all" ? null : Number(b.dataset.p);
      filter();
    });
    document.getElementById("corebtn").addEventListener("click", function (e) {
      coreOnly = !coreOnly;
      e.currentTarget.setAttribute("aria-pressed", String(coreOnly));
      filter();
    });
    document.getElementById("resetbtn").addEventListener("click", function () {
      if (confirm("Clear all saved progress in this browser?")) {
        Store.reset();
        paint();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        main.querySelectorAll(".card.open").forEach(function (c) {
          c.classList.remove("open");
          c.querySelector(".expand").innerHTML = "Detail <span>+</span>";
        });
      }
    });
    document.addEventListener("bai:progress", paint);

    paint();
    filter();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else start();
})();

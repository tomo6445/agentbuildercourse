#!/usr/bin/env python3
"""
Build the course site.

    python3 tools/build.py            # write docs/
    python3 tools/build.py --check    # fail if docs/ is stale (used in CI)

Input : content/course.py  (structure)  +  content/mNN.md  (lesson prose)
Output: docs/index.html, docs/modules/mNN.html, docs/assets/*

No dependencies, no network. The output is committed so the site works from a
clone or from GitHub Pages without anyone running a build.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "content"))

import mdlite  # noqa: E402
import course as C  # noqa: E402

OUT = ROOT / "docs"
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"

REPO = "https://github.com/tomo6445/agentbuildercourse"
BLOB = REPO + "/blob/main/"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def phase_of(m):
    return next(p for p in C.PHASES if p["id"] == m["phase"])


def widget_html(name, config_body):
    """`::: widget NAME` + optional JSON body -> a host div the JS fills in."""
    cfg = "{}"
    body = config_body.strip()
    if body:
        try:
            cfg = json.dumps(json.loads(body))
        except json.JSONDecodeError:
            cfg = "{}"
    return (
        '<div class="widget" data-widget="%s" data-config=\'%s\'>'
        '<div class="widget-body"><em>This instrument needs JavaScript. '
        "The lesson reads fine without it.</em></div></div>"
        % (html.escape(name), html.escape(cfg, quote=False).replace("'", "&#39;"))
    )


QUIZ_RE = re.compile(r"^::: quiz\s*$(.*?)^:::\s*$", re.S | re.M)


def extract_quiz(src):
    """Pull the quiz JSON out of the markdown; return (src_without_quiz, quiz)."""
    m = QUIZ_RE.search(src)
    if not m:
        return src, None
    try:
        quiz = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise SystemExit("quiz JSON is invalid: %s" % e)
    return src[: m.start()] + src[m.end():], quiz


def toc_html(headings):
    items = []
    for level, ident, text in headings:
        cls = ' class="sub"' if level == 3 else ""
        items.append('<li%s><a href="#%s">%s</a></li>' % (cls, ident, html.escape(text)))
    if not items:
        return ""
    return (
        '<nav class="toc" aria-label="On this page"><h4>On this page</h4><ol>'
        + "".join(items)
        + "</ol></nav>"
    )


HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{root}assets/course.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9679;</text></svg>">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
"""

SCRIPTS = """<script src="{root}assets/widgets.js"></script>
<script src="{root}assets/widgets-b.js"></script>
<script src="{root}assets/course.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# lesson pages
# ---------------------------------------------------------------------------

def build_module(m, prev, nxt):
    slug = C.slug_for(m)
    src_path = CONTENT / (slug + ".md")
    if not src_path.exists():
        raise SystemExit("missing lesson source: %s" % src_path)
    src = src_path.read_text(encoding="utf-8")
    src, quiz = extract_quiz(src)
    body, headings = mdlite.render(src, widget_renderer=widget_html)

    ph = phase_of(m)
    pills = ['<span class="pill">%s</span>' % m["n"]]
    if m.get("core"):
        pills.append('<span class="pill core">core path</span>')
    pills.append('<span class="pill">%.1f h</span>' % m["hrs"])
    pills.append('<span class="pill">phase %d &middot; %s</span>' % (ph["id"], ph["name"]))

    lab_links = "".join(
        '<a class="btn ghost" href="%s%s" style="margin-right:8px">%s &#8599;</a>'
        % (BLOB, lab, lab.split("/")[-1])
        for lab in m.get("labs", [])
    )

    nav = '<nav class="prevnext">'
    if prev:
        nav += '<a href="%s.html"><span class="dir">&#8592; previous</span>' \
               '<span class="t">%s &middot; %s</span></a>' % (
                   C.slug_for(prev), prev["n"], html.escape(prev["title"]))
    else:
        nav += '<a href="../index.html"><span class="dir">&#8592; back</span>' \
               '<span class="t">Course index</span></a>'
    if nxt:
        nav += '<a class="next" href="%s.html"><span class="dir">next &#8594;</span>' \
               '<span class="t">%s &middot; %s</span></a>' % (
                   C.slug_for(nxt), nxt["n"], html.escape(nxt["title"]))
    else:
        nav += '<a class="next" href="../index.html"><span class="dir">done &#8594;</span>' \
               '<span class="t">Course index</span></a>'
    nav += "</nav>"

    page = HEAD.format(
        title="%s &middot; %s — Building AI Agents" % (m["n"], html.escape(m["title"])),
        desc=html.escape(m["line"], quote=True),
        root="../",
    )
    page += """<div class="lessonbar"><div class="lessonbar-in">
  <a class="home" href="../index.html">&#8592; all modules</a>
  <span class="crumb">%s &middot; %s</span>
  <button class="iconbtn" id="themebtn" style="margin-left:auto">dark</button>
  <div class="readbar"></div>
</div></div>

<header class="lesson-head">
  <div class="meta">%s</div>
  <h1>%s</h1>
  <p class="line">%s</p>
</header>

<div class="lesson-layout">
%s
<article class="lesson" id="main">
%s
""" % (
        ph["num"], m["n"],
        "".join(pills),
        html.escape(m["title"]),
        mdlite.inline(m["line"]),
        toc_html(headings),
        body,
    )

    if quiz:
        page += '<h2 id="knowledge-check">Knowledge check</h2><div id="quiz"></div>'

    page += """
<div class="callout c-gate"><h4>Ship gate</h4><div class="callout-body"><p>%s</p>
<p style="margin-top:9px"><code>%s</code></p></div></div>

<div class="complete-bar">
  <p>%s</p>
  %s
  <button class="btn" id="completebtn" data-module="%s">mark complete</button>
</div>
%s
</article>
</div>

<footer>
  %s &middot; %s &middot; <a href="../index.html">course index</a> &middot;
  <a href="%s">repository</a><br>
  Progress is stored in this browser only. Press <b>Esc</b> to leave a widget.
</footer>
""" % (
        mdlite.inline(m["gate"]),
        html.escape(m.get("gate_cmd", "")),
        "Lab code for this module lives in the repository:" if m.get("labs") else "",
        lab_links,
        m["n"],
        nav,
        C.COURSE["title"], C.COURSE["version"], REPO,
    )

    if quiz:
        page += "<script>window.QUIZ=%s;</script>\n" % json.dumps(
            {"id": slug, "questions": quiz}
        )
    page += SCRIPTS.format(root="../")

    (OUT / "modules" / (slug + ".html")).write_text(page, encoding="utf-8")
    return len(body)


# ---------------------------------------------------------------------------
# hub page
# ---------------------------------------------------------------------------

def build_index():
    total_h = sum(m["hrs"] for m in C.MODULES)
    n_labs = sum(len(m.get("labs", [])) for m in C.MODULES)

    page = HEAD.format(
        title="Building AI Agents — from first principles to production",
        desc=html.escape(C.COURSE["standfirst"], quote=True),
        root="",
    )
    page += """<header class="masthead">
  <div class="kicker">Interactive course &middot; %s</div>
  <h1>%s<br><em>%s</em></h1>
  <p class="standfirst">%s</p>
  <div class="facts">
    <div class="fact"><b>%d</b><span>Modules</span></div>
    <div class="fact"><b>%.1f</b><span>Hours</span></div>
    <div class="fact"><b>%d</b><span>Lab packages</span></div>
    <div class="fact"><b>%d</b><span>Ship gates</span></div>
    <div class="fact"><b>%d wk</b><span>Cohort length</span></div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-in">
    <input class="search" id="q" type="search" placeholder="search modules, labs, concepts&hellip;"
           aria-label="Search modules">
    <div class="chips" id="phasechips"></div>
    <button class="chip core" id="corebtn" aria-pressed="false">core path</button>
    <button class="iconbtn" id="themebtn">dark</button>
    <button class="iconbtn" id="resetbtn" title="Clear saved progress">reset</button>
    <div class="progwrap">
      <div class="progbar"><i id="bar"></i></div>
      <div class="progtext" id="ptext">0 / %d</div>
    </div>
  </div>
</div>

<main id="main"></main>

<footer>
  %s %s &middot; A course you can run: every lab is executable, every gate is a test.<br>
  Start at <a href="modules/m01.html">M1 — The Loop</a>, or read the
  <a href="%s">repository README</a> for the local setup.<br>
  Progress ticks are stored in this browser's local storage. Press <b>Esc</b> to collapse open modules.
</footer>

<script>
const PHASES = %s;
const MODULES = %s;
const CAPSTONE_STAGES = %s;
const PILLARS = %s;
</script>
<script src="assets/hub.js"></script>
""" % (
        C.COURSE["version"],
        C.COURSE["title"], C.COURSE["subtitle"], html.escape(C.COURSE["standfirst"]),
        len(C.MODULES), total_h, n_labs, len(C.MODULES), C.COURSE["weeks"],
        len(C.MODULES),
        C.COURSE["title"], C.COURSE["version"], REPO,
        json.dumps(C.PHASES),
        json.dumps([hub_module(m) for m in C.MODULES]),
        json.dumps(C.CAPSTONE_STAGES),
        json.dumps(C.PILLARS),
    )
    page += SCRIPTS.format(root="")
    (OUT / "index.html").write_text(page, encoding="utf-8")


def hub_module(m):
    """The subset of a module the hub page needs, plus its rendered summary."""
    slug = C.slug_for(m)
    src = (CONTENT / (slug + ".md")).read_text(encoding="utf-8")
    learn = summary_points(src)
    return {
        "n": m["n"], "phase": m["phase"], "hrs": m["hrs"], "core": bool(m.get("core")),
        "title": m["title"], "line": m["line"], "tags": m["tags"],
        "gate": m["gate"], "href": "modules/%s.html" % slug,
        "learn": learn,
        "labs": [lab.split("/")[-1] for lab in m.get("labs", [])],
    }


OBJ_RE = re.compile(r"^::: objectives\s*$(.*?)^:::\s*$", re.S | re.M)


def summary_points(src):
    """The objectives block doubles as the card's 'what you learn' list."""
    m = OBJ_RE.search(src)
    if not m:
        return []
    return [
        mdlite.inline(line.strip()[2:].strip())
        for line in m.group(1).splitlines()
        if line.strip().startswith("- ")
    ]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build(check=False):
    global OUT
    real = OUT
    target = (ROOT / ".build-check") if check else OUT
    OUT = target

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "modules").mkdir(parents=True)
    (OUT / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy2(f, OUT / "assets" / f.name)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    build_index()
    written = 0
    for i, m in enumerate(C.MODULES):
        prev = C.MODULES[i - 1] if i else None
        nxt = C.MODULES[i + 1] if i + 1 < len(C.MODULES) else None
        written += build_module(m, prev, nxt)

    OUT = real
    if check:
        differing = compare(target, real)
        shutil.rmtree(target)
        if differing:
            print("docs/ is stale. Re-run: python3 tools/build.py")
            for d in differing[:20]:
                print("  " + d)
            return 1
        print("docs/ is up to date")
        return 0

    print("built %d modules + index into %s (%d bytes of rendered lesson HTML)"
          % (len(C.MODULES), OUT.relative_to(ROOT), written))
    return 0


def compare(a, b):
    diff = []
    files_a = {p.relative_to(a) for p in a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(b) for p in b.rglob("*") if p.is_file()} if b.exists() else set()
    for f in sorted(files_a | files_b):
        pa, pb = a / f, b / f
        if not pa.exists():
            diff.append("removed: %s" % f)
        elif not pb.exists():
            diff.append("added: %s" % f)
        elif pa.read_bytes() != pb.read_bytes():
            diff.append("changed: %s" % f)
    return diff


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify docs/ matches the sources without writing")
    args = ap.parse_args()
    raise SystemExit(build(check=args.check))

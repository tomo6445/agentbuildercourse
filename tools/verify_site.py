"""Load every generated page in a real browser and assert it works."""
import sys, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path("/home/user/agentbuildercourse/docs")
fails, checks = [], 0

def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        fails.append(msg)

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"], executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console.%s: %s" % (m.type, m.text))
            if m.type == "error" else None)

    # ---- hub ----
    page.goto("file://%s/index.html" % ROOT)
    page.wait_for_timeout(400)
    check(page.locator(".card").count() == 16, "hub should render 16 cards, got %d" % page.locator(".card").count())
    check(page.locator(".stage").count() == 7, "capstone stages")
    check(page.locator(".pillar").count() == 3, "pillars")

    # search filter
    page.fill("#q", "trifecta")
    page.wait_for_timeout(200)
    vis = page.locator(".card:not(.hidden)").count()
    check(vis == 1, "search 'trifecta' should show 1 card, got %d" % vis)
    page.fill("#q", "")
    page.wait_for_timeout(200)

    # core-path filter
    page.click("#corebtn")
    page.wait_for_timeout(200)
    core = page.locator(".card:not(.hidden)").count()
    check(core == 14, "core path should show 14 modules, got %d" % core)
    page.click("#corebtn")
    page.wait_for_timeout(150)

    # progress persistence
    page.locator(".card[data-n='M1'] .tick").click()
    page.wait_for_timeout(200)
    check("1 / 16" in page.inner_text("#ptext"), "progress text after tick: %s" % page.inner_text("#ptext"))
    page.reload()
    page.wait_for_timeout(400)
    check("1 / 16" in page.inner_text("#ptext"), "progress should persist across reload")
    check(page.locator(".card[data-n='M1']").get_attribute("class").find("done") >= 0, "M1 marked done after reload")

    # theme toggle
    page.click("#themebtn")
    page.wait_for_timeout(150)
    check(page.get_attribute("html", "data-theme") == "dark", "theme toggles to dark")
    page.click("#themebtn")

    # ---- every lesson page ----
    WIDGETS = {}
    for i in range(1, 17):
        slug = "m%02d" % i
        page.goto("file://%s/modules/%s.html" % (ROOT, slug))
        page.wait_for_timeout(350)
        check(page.locator("article.lesson h2").count() >= 4,
              "%s should have several sections" % slug)
        check(page.locator(".toc a").count() >= 4, "%s TOC populated" % slug)
        check(page.locator("#quiz .q").count() == 5, "%s should have 5 quiz questions, got %d"
              % (slug, page.locator("#quiz .q").count()))
        check(page.locator(".objectives li").count() >= 4, "%s objectives" % slug)
        check(page.locator("figure.code").count() >= 1, "%s has code" % slug)
        # widgets that declared themselves must have rendered a body with content
        for w in page.locator(".widget[data-widget]").all():
            name = w.get_attribute("data-widget")
            WIDGETS[name] = WIDGETS.get(name, 0) + 1
            check(w.locator(".widget-head h4").count() == 1,
                  "%s widget %s has no head (did not initialise)" % (slug, name))
            check("not loaded" not in w.inner_text(), "%s widget %s not registered" % (slug, name))
            check("failed to start" not in w.inner_text(), "%s widget %s threw" % (slug, name))

    # ---- quiz interaction on m01 ----
    page.goto("file://%s/modules/m01.html" % ROOT)
    page.wait_for_timeout(300)
    page.locator("#quiz .q").first.locator(".opt").nth(1).click()   # correct answer for Q1
    page.wait_for_timeout(150)
    check(page.locator("#quiz .q").first.locator(".opt.correct").count() == 1, "correct answer marked")
    check("Correct" in page.locator("#quiz .q").first.locator(".why").inner_text(), "explanation shown")
    check(page.inner_text("#qscore").startswith("1 /"), "score updated: %s" % page.inner_text("#qscore"))

    # ---- widget interaction: loop simulator ----
    sim = page.locator(".widget[data-widget='loop-sim']")
    sim.locator("button:has-text('run to end')").click()
    page.wait_for_timeout(300)
    check(sim.locator(".turn").count() >= 6, "loop-sim renders turns, got %d" % sim.locator(".turn").count())
    check(sim.locator(".readout .cell").count() == 5, "loop-sim readout")

    # ---- mark complete syncs to hub ----
    page.click("#completebtn")
    page.wait_for_timeout(200)
    check(page.get_attribute("#completebtn", "aria-pressed") == "false",
          "M1 was already done from the hub, so this click should un-complete it")

    # ---- widget interaction: trifecta on m11 ----
    page.goto("file://%s/modules/m11.html" % ROOT)
    page.wait_for_timeout(300)
    tri = page.locator(".widget[data-widget='trifecta']")
    for label in ["reads local files", "fetches web pages", "sends email"]:
        tri.locator("button:has-text('%s')" % label).click()
    page.wait_for_timeout(200)
    check("exfiltration primitive" in tri.inner_text().lower(), "trifecta detects all three legs")

    # ---- path traversal suite on m07 ----
    page.goto("file://%s/modules/m07.html" % ROOT)
    page.wait_for_timeout(300)
    pt = page.locator(".widget[data-widget='path-traversal']")
    pt.locator("button:has-text('run the full attack suite')").click()
    page.wait_for_timeout(250)
    txt = pt.inner_text().lower()
    check("12 / 12 handled correctly" in txt, "path traversal suite result: %s" %
          [l for l in txt.splitlines() if "handled correctly" in l])

    browser.close()

print("widgets exercised:", ", ".join(sorted(WIDGETS)))
print("checks run:", checks)
if errors:
    print("\nJS ERRORS (%d):" % len(errors))
    for e in errors[:15]:
        print("  " + e)
if fails:
    print("\nFAILURES (%d):" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("\nAll browser checks passed.")

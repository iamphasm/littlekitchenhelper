import sys
from playwright.sync_api import sync_playwright
B = "http://127.0.0.1:8090/"
errors = []
def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond: errors.append(name)

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1200, "height": 900})
    logs = []
    pg.on("pageerror", lambda e: logs.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: logs.append(m.type + " " + m.text) if m.type == "error" else None)
    pg.goto(B)
    pg.wait_for_selector("#loginOverlay:not([hidden])")
    check("login overlay shown", True)
    pg.fill("#loginUser", "mom"); pg.fill("#loginPass", "wrong"); pg.click("#loginBtn")
    pg.wait_for_selector("#loginError:not([hidden])")
    check("wrong password error", "Feil" in pg.inner_text("#loginError"))
    pg.fill("#loginPass", "momsecret123"); pg.click("#loginBtn")
    pg.wait_for_selector("#loginOverlay", state="hidden")
    check("dashboard visible after login", pg.is_visible("#view-dashboard"))
    check("session box", "mom" in pg.inner_text("#sessionName"))

    # add member Ola (child) through the UI
    pg.click('nav button[data-view="addmember"]')
    pg.fill("#mName", "Ola"); pg.select_option("#mRole", "barn"); pg.fill("#mPass", "short")
    pg.click("#saveMemberBtn")
    check("short password rejected", "8" in pg.inner_text("#mError"))
    pg.fill("#mPass", "olasecret123"); pg.fill("#mPhone", "900"); pg.click("#saveMemberBtn")
    pg.wait_for_selector("#view-family.active")
    pg.wait_for_function("document.querySelectorAll('#familyList li').length >= 2")
    fam = pg.inner_text("#familyList")
    print(fam.replace("\n", " | "))
    check("Ola listed with numeric id", "Ola" in fam and "#" in fam)
    check("Ola has todo-list menu entry", "Ola" in pg.inner_text("#memberNav"))

    # generate (mock Anthropic: 1st full, 2nd truncated)
    pg.click('nav button[data-view="generator"]')
    pg.fill("#itemName", "torsk"); pg.fill("#itemQty", "500"); pg.click("#addBtn")
    for v in ("Mandag", "Tirsdag"):
        pg.check(f'#days input[value="{v}"]')
    pg.click("#generateBtn")
    pg.wait_for_selector("#results article.recipe")
    check("2 recipes rendered", pg.locator("#results article.recipe").count() == 2)
    pg.click("#generateBtn")
    pg.wait_for_selector("#results .status.error")
    check("truncated answer -> partial message + 1 recipe",
          pg.locator("#results article.recipe").count() == 1 and "av" in pg.inner_text("#results .status.error") or "of" in pg.inner_text("#results .status.error"))
    pg.click('nav button[data-view="recipes"]')
    titles = pg.inner_text("#historyList")
    print("history count", pg.locator("#historyList details").count(), pg.inner_text("#historyList").replace("\n"," | "))
    check("history has 3 recipes", pg.locator("#historyList details").count() == 3)

    # manual recipe
    pg.click('nav button[data-view="manual"]')
    pg.fill("#rTitle", "Manuell pannekake"); pg.fill("#rSteps", "Bland\nSteik")
    pg.click("#saveRecipeBtn")
    pg.wait_for_selector("#view-recipes.active")
    check("manual recipe saved", "Manuell pannekake" in pg.inner_text("#historyList"))

    # weekplan
    pg.click('nav button[data-view="weekplan"]')
    sel = pg.locator("#weekplanList select").first
    opt = sel.locator("option", has_text="Mock Suppe").first.get_attribute("value")
    sel.select_option(opt)
    pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_selector("#loginOverlay", state="hidden")
    pg.click('nav button[data-view="weekplan"]')
    check("weekplan persisted across reload (session restored)", pg.locator("#weekplanList select").first.input_value() == opt)

    # parent adds a task to Ola
    pg.locator("#memberNav button", has_text="Ola").click()
    pg.fill("#taskText", "Rydde rommet"); pg.click("#addTaskBtn")
    pg.wait_for_selector("#taskList li")
    check("parent task on kid list", "Rydde rommet" in pg.inner_text("#taskList"))

    # logout -> kid
    pg.click("#logoutBtn")
    pg.wait_for_selector("#loginOverlay:not([hidden])")
    pg.fill("#loginUser", "Ola"); pg.fill("#loginPass", "olasecret123"); pg.click("#loginBtn")
    pg.wait_for_selector("#loginOverlay", state="hidden")
    check("kid cannot see add member", not pg.is_visible('nav button[data-view="addmember"]'))
    pg.locator("#memberNav button", has_text="Ola").click()
    li = pg.locator("#taskList li").first
    check("kid may tick own-list task", li.locator("input").is_enabled())
    check("kid cannot delete parent's task", li.locator("button.del").count() == 0)
    li.locator("input").check(); pg.wait_for_timeout(400)
    pg.fill("#taskText", "Lekser"); pg.click("#addTaskBtn")
    pg.wait_for_function("document.querySelectorAll('#taskList li').length == 2")
    check("kid added own task, has delete", pg.locator("#taskList li button.del").count() == 1)
    pg.locator("#memberNav button", has_text="mom").click()
    check("kid cannot add to mom's list", pg.locator("#view-member .add-row").is_hidden())
    pg.click('nav button[data-view="recipes"]')
    check("kid has no delete on parent recipes / no clear-all", pg.locator("#historyList button.del").count() == 0 and pg.locator("#view-recipes .history-head button").is_hidden())
    pg.click('nav button[data-view="weekplan"]')
    check("kid weekplan read-only", pg.locator("#weekplanList select").first.is_disabled())

    # language switch + persistence
    pg.click("#langEn"); pg.wait_for_timeout(200)
    check("english UI", "Log out" in pg.inner_text("#logoutBtn"))
    pg.click("#logoutBtn"); pg.wait_for_selector("#loginOverlay:not([hidden])")
    check("login in english", "Username" in pg.inner_text("#loginForm"))
    pg.fill("#loginUser", "Ola"); pg.fill("#loginPass", "olasecret123"); pg.click("#loginBtn")
    pg.wait_for_selector("#loginOverlay", state="hidden")

    # backend down
    pg.route("**/api/**", lambda r: r.abort())
    pg.reload()
    pg.wait_for_selector("#loginDown:not([hidden])")
    check("backend-down card", pg.is_visible("#retryBtn"))
    pg.screenshot(path="/tmp/shot_down.png")
    br.close()
    print("\n".join(logs[:10]))
print("FAILED:", errors)

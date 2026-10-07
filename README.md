# Little Kitchen Helper

Family organizer in a single web page: turn what is in your freezer into a dinner plan with AI,
keep a recipe history, plan the week and give every family member a personal to-do list.

**Version:** 1.0.0 · **Backend:** [PocketBase](https://pocketbase.io) · **AI:** Anthropic Claude (called server-side) · **UI languages:** Norwegian / English

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Setup, step by step](#setup-step-by-step)
5. [Daily use](#daily-use)
6. [Roles and permissions](#roles-and-permissions)
7. [Configuration](#configuration)
8. [Security notes](#security-notes)
9. [Tests](#tests)
10. [Troubleshooting](#troubleshooting)
11. [Project layout](#project-layout)

---

## Features

### Login and session
- Username + password login (PocketBase auth, token kept in the browser).
- Session is restored on reload; automatic logout if the token is rejected.
- Log out button in the sidebar; rate-limited login (10 attempts per minute).
- Clear "cannot reach the server" screen with a retry button.

### Dashboard (start page)
- Card with the **5 most recent recipes** (updates as you create more).
- Card with the **week plan overview** (which day has which dinner).
- Card with the **freezer contents** (first 5 items).
- Statistics: number of recipes, planned days, freezer items.

### Little Kitchen Helper
- **Generate recipe** (AI)
  - Add freezer items with name, amount and unit (g, kg, pcs, pack, bag, dl, litre).
  - Choose number of people (1–20; amounts are scaled).
  - Tick which weekdays need dinner.
  - Free-text notes for wishes and allergies.
  - Previously generated dishes are sent along and **never suggested again**.
  - Output is compact JSON; if the AI answer is cut off, the complete recipes are still saved and you are told how many days were created.
  - Each recipe shows ingredients from the freezer, extra shopping items and short steps.
  - **Print / save as PDF** of the generated plan.
- **Create recipe** – enter a recipe manually (title, description, freezer ingredients, extra ingredients, steps; one item per line).
- **Recipes** – history of every recipe (AI and manual), newest first, expandable, with delete per recipe and "clear all" (parents only).
- **Week planner** – pick a recipe per weekday from a dropdown, expand to see the full recipe, print the week as PDF.

### To-do lists
- **Week calendar** – Monday to Sunday view showing the planned dinner and every member's tasks per day.
- **Personal list per family member** – created automatically when a member is added. Tasks have text, optional weekday and a done checkbox.

### Settings
- **Family** – lists all members with photo, role, numeric id (`#1`, `#2`, …), phone, email and task counts; open a member's list or remove a member (parents only, two-click confirm).
- **Add member** (parents only) – name (unique), role (parent/child), password, phone, email (optional) and photo upload (resized in the browser).

### Interface
- Left sidebar with Dashboard, To-do lists, Little Kitchen Helper and Settings groups (collapsible).
- Norwegian/English switch with flags (remembered per browser).
- Minimal, responsive design for phone, tablet and desktop; sidebar becomes a drawer on small screens.
- Rotating logo (one of three variants per page load).

---

## How it works

```
Browser (pb_public/index.html)
   │  REST + auth token
   ▼
PocketBase  ── collections: users, recipes, weekplan, todos  (SQLite, API rules)
   │  JS hook: POST /api/generate  (needs login, rate limited)
   ▼
Anthropic API   (key lives only in the server environment)
```

PocketBase serves the web page, stores the data, enforces permissions with API rules and proxies the AI call.
The freezer list is kept in the browser only.

---

## Requirements

- Linux, macOS or Windows (WSL recommended on Windows)
- Python 3.9+ (setup script uses only the standard library)
- The PocketBase binary for your OS
- An Anthropic API key

---

## Setup, step by step

> Use a normal Linux folder (for example `~/little-kitchen-helper`). Running SQLite from `/mnt/c/...` in WSL is slow and can be unreliable.

**1. Get the project**
```bash
git clone <YOUR-REPO-URL> little-kitchen-helper
cd little-kitchen-helper
```

**2. Download PocketBase**
Download the build for your system from <https://pocketbase.io/docs/> (for WSL/Linux: `linux_amd64`), unzip it and put the `pocketbase` file in this folder.
```bash
chmod +x pocketbase
./pocketbase --version
```

**3. Create the admin (superuser) account**
This account manages PocketBase itself and is used once by the setup script.
```bash
./pocketbase superuser upsert admin@example.com 'a-long-admin-password'
```

**4. Set the AI key and start the server** (keep this terminal open)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export ANTHROPIC_MODEL=claude-sonnet-4-5     # optional
./pocketbase serve --http=127.0.0.1:8090
```

**5. Create collections, rules and the first parent account** (second terminal, same folder)
```bash
python3 setup_pocketbase.py \
  --admin-email admin@example.com \
  --admin-password 'a-long-admin-password' \
  --first-user yourname \
  --first-password 'at-least-8-characters'
```
The script is idempotent: run it again after updates. Expected output: `updated users`, `updated recipes`, `updated weekplan`, `updated todos`, `updated settings`, `created parent account yourname`.

**6. Open the app**
Go to <http://127.0.0.1:8090>, log in with the parent account from step 5.

**7. Add the family**
Settings → Add member → fill in name, role, password (min. 8 characters) → Save. Each member logs in with their own name and password.

**8. Make it reachable from phones/tablets (optional)**
Start with `--http=0.0.0.0:8090` and open `http://<computer-ip>:8090` on the same network. For access over the internet, put HTTPS in front (see Security notes).

---

## Daily use

1. **Fill the freezer list** (Little Kitchen Helper → Generate recipe).
2. Set people, tick days, add notes, press **Generate**.
3. Check **Recipes** for the history; assign dinners in **Week planner**.
4. Add tasks to your list under **To-do lists**; see everything in **Week calendar**.
5. Print the plan with the print button (browser dialog → "Save as PDF").

---

## Roles and permissions

Enforced on the server (API rules), not only in the UI.

| Action | Parent (`forelder`) | Child (`barn`) |
|---|---|---|
| Log in, view recipes, plan, members, tasks | yes | yes |
| Generate / add recipes | yes | yes |
| Delete recipes | all | only own |
| Clear all recipes | yes | no |
| Edit week planner | yes | no |
| Add / remove members, change roles | yes | no |
| Add tasks | to any list | to own list only |
| Tick tasks done | any | own list |
| Edit / delete tasks | any | only tasks they created |
| Edit own profile (phone, photo, password) | yes | yes (not role) |

---

## Configuration

| Setting | Where | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | environment of `pocketbase serve` | required for AI |
| `ANTHROPIC_MODEL` | environment | `claude-sonnet-4-5` |
| `ANTHROPIC_BASE_URL` | environment (testing/proxy) | `https://api.anthropic.com` |
| Port / address | `--http=` flag | `127.0.0.1:8090` |
| Rate limits | `setup_pocketbase.py` | login 10/min, generate 6/min |
| Different API host for the page | set `window.PB_URL` before the script in `index.html` | same origin |

---

## Security notes

- Never put the Anthropic key in the HTML; it only exists in the server environment.
- Use HTTPS before exposing the app (Caddy, nginx, or `./pocketbase serve yourdomain.com`).
- Behind a reverse proxy, configure PocketBase's trusted proxy header so rate limits see real client IPs.
- Use long, unique passwords for the superuser and all members; the PocketBase admin UI is at `/_/`.
- Back up the `pb_data/` folder regularly (it holds the database and uploaded photos).

---

## Tests

Both need a running instance (see setup). The UI test also needs `pip install playwright` and a mock Anthropic server via `ANTHROPIC_BASE_URL`.

```bash
python3 test_rules.py   # API rules as parent and child
python3 test_ui.py      # end-to-end in a browser
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` from the setup script | PocketBase is not running; start step 4 first |
| `Wrong username or password` | usernames are case-insensitive, passwords are not; check step 5 |
| "AI is not set up on the server" | `ANTHROPIC_API_KEY` was not exported in the terminal that runs PocketBase |
| "Too many attempts" | rate limit hit; wait a minute |
| Only part of the days generated | the AI answer was cut off; try fewer days at a time |
| Page loads but "Cannot reach the server" | wrong address/port, or PocketBase stopped |

---

## Project layout

```
pb_public/index.html        the whole frontend (served by PocketBase)
pb_hooks/generate.pb.js     AI proxy endpoint POST /api/generate
pb_hooks/members.pb.js      assigns numeric member ids (1, 2, 3, …)
setup_pocketbase.py         collections, rules, settings, first parent
test_rules.py, test_ui.py   tests
pb_data/                    database and uploads (created at runtime, not committed)
```

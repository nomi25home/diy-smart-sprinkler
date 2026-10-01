# Claude Code Prompt — Sprinkler Control Webapp

Build a homelab webapp for controlling and monitoring a 6-zone DIY sprinkler system managed by Home Assistant. The webapp is a dashboard that gives a cleaner, mobile-friendly view of the sprinkler system than the HA Lovelace UI.

---

## What it does

- Shows the current system mode (AUTO / MANUAL / VACATION / RAIN SKIP / WINTERIZED) prominently at the top
- Shows which zone is currently active (or "Idle") and a live countdown of remaining zone time
- Shows last run time and next scheduled run time
- Buttons to **Run All Zones**, **Stop All**, **Winterize**, and **Un-winterize**
- Toggle for **Manual Mode** and **Rain Skip** (each with a confirmation step)
- **Vacation Mode**: shows a date picker + "Set Vacation" button; shows countdown when active; "End Vacation" button to cancel early
- **Zone runtime controls**: sliders (5–40 min, step 5) for each of the 6 zones, with a Save button that writes back to HA
- A **Run History** panel: last 10 runs pulled from HA's history API for `input_datetime.sprinkler_last_run`
- Auto-refreshes state every 5 seconds without a full page reload
- Works well on mobile (375px) — this is primarily used from a phone

**What it does NOT do (out of scope for v1):**
- Does not talk to the Pi directly — all control goes through HA's REST API
- Does not manage schedules (5:30 AM / 5:30 PM are hardcoded in HA automations, not here)
- Does not show zone-level history (only overall run history)
- No user auth (sits behind Authentik)

---

## Architecture to follow

Build this exactly like the `netcore-ipam` app at `/Users/mihirpatel/synced-ollama-claude-projects/netcore-ipam/`. Read that codebase fully before writing any code — it is the canonical reference for structure, patterns, and deployment.

### Stack
- **Backend:** Python 3.11, FastAPI, uvicorn, httpx (for HA REST API calls), pydantic v2
- **Frontend:** A single `app/static/index.html` — vanilla JS, no build step, no npm. CSS variables for theming, dark/light mode via `prefers-color-scheme`.
- **Container:** `Dockerfile` (python:3.11-slim), `compose.yaml` (Dockge-compatible, host network)
- **Data:** `/data/audit.jsonl` for write-action audit log. No `state.json` needed — all state comes from HA live.
- **Config:** Environment variables only; secrets in `.env`. Include `.env.example`.

### Security (copy this pattern exactly from netcore-ipam)
- **`ALLOWED_CLIENTS` middleware:** Refuse all requests (403) not from configured CIDRs. Default: `127.0.0.1/32,172.16.0.0/12`. `/healthz` is exempt.
- **Authentik username:** Read `x-authentik-username` header → include in every audit log entry.
- No scrypt unlock needed (no protected/locked rows concept).

### API design
- `GET /api/state` — returns full sprinkler snapshot (all entities below, assembled into one JSON object)
- `POST /api/run` — calls `script.sprinkler_run_all_zones`
- `POST /api/stop` — calls `script.sprinkler_stop_all`
- `POST /api/winterize` — calls `script.sprinkler_winterize`
- `POST /api/unwinterize` — turns off `input_boolean.sprinkler_winterized`
- `POST /api/manual` body `{"on": true/false}` — turns `input_boolean.sprinkler_manual_mode` on or off
- `POST /api/rain_skip` body `{"on": true/false}` — turns `input_boolean.sprinkler_rain_skip` on or off
- `POST /api/vacation` body `{"days": N}` — sets `input_number.sprinkler_vacation_days` then calls `script.sprinkler_set_vacation`; `{"days": 0}` ends vacation early by turning off `input_boolean.sprinkler_vacation_mode`
- `POST /api/zone_runtimes` body `{"zone_1": N, "zone_2": N, ..., "zone_6": N}` — sets each `input_number.sprinkler_zone_N_runtime` via `input_number/set_value`
- `GET /api/history` — returns last 10 entries from HA history for `input_datetime.sprinkler_last_run` (timestamps only, formatted)
- `GET /api/audit?limit=50` — last N audit entries
- `GET /healthz` — `{"ok": true}`
- `GET /` — serves index.html

### Audit log
Every write endpoint calls `audit(user, action, detail)` → appends to `/data/audit.jsonl`.

---

## Home Assistant connection

| Variable | Default | Description |
|---|---|---|
| `HA_URL` | `http://192.168.74.11:8123` | HA instance |
| `HA_TOKEN` | _(required, in .env)_ | Long-lived access token |
| `POLL_INTERVAL` | `5` | Seconds between background HA state refreshes |
| `ALLOWED_CLIENTS` | `127.0.0.1/32,172.16.0.0/12` | Allowed CIDRs |
| `DATA_DIR` | `/data` | Audit log location |

### HA entities to read (all via `GET /api/states/<entity_id>`)

| Entity | What it gives us |
|---|---|
| `sensor.sprinkler_mode` | Current mode string: AUTO / MANUAL / VACATION / RAIN SKIP / WINTERIZED |
| `sensor.sprinkler_active_zone` | "Zone 1" … "Zone 6" or "Idle" |
| `sensor.sprinkler_last_ran` | Human-readable last run timestamp |
| `sensor.sprinkler_next_run` | Human-readable next run time |
| `input_boolean.sprinkler_rain_skip` | on/off |
| `input_boolean.sprinkler_manual_mode` | on/off |
| `input_boolean.sprinkler_vacation_mode` | on/off |
| `input_boolean.sprinkler_winterized` | on/off |
| `input_number.sprinkler_current_zone` | 0–6 (0 = idle) |
| `input_number.sprinkler_zone_1_runtime` … `_zone_6_runtime` | Minutes per zone (5–40) |
| `input_datetime.sprinkler_vacation_until` | Date string |
| `sensor.sprinkler_zone_1_state` … `_zone_6_state` | "True" / "False" — live valve state from Pi |

### HA services to call (all via `POST /api/services/<domain>/<service>`)

| What | Domain | Service | Data |
|---|---|---|---|
| Run all zones | `script` | `sprinkler_run_all_zones` | `{}` |
| Stop all | `script` | `sprinkler_stop_all` | `{}` |
| Winterize | `script` | `sprinkler_winterize` | `{}` |
| Un-winterize | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_winterized"}` |
| Manual mode on | `input_boolean` | `turn_on` | `{"entity_id": "input_boolean.sprinkler_manual_mode"}` |
| Manual mode off | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_manual_mode"}` |
| Rain skip on | `input_boolean` | `turn_on` | `{"entity_id": "input_boolean.sprinkler_rain_skip"}` |
| Rain skip off | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_rain_skip"}` |
| Set vacation days | `input_number` | `set_value` | `{"entity_id": "input_number.sprinkler_vacation_days", "value": N}` |
| Activate vacation | `script` | `sprinkler_set_vacation` | `{}` |
| End vacation | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_vacation_mode"}` |
| Set zone N runtime | `input_number` | `set_value` | `{"entity_id": "input_number.sprinkler_zone_N_runtime", "value": N}` |

HA token goes in the `Authorization: Bearer <HA_TOKEN>` header on every call.

---

## Frontend layout (index.html)

Single page, mobile-first (375px), dark/light mode via CSS variables.

**Header** — app name "Sprinkler Control", last-updated time, manual refresh button, history button (opens audit log dialog).

**Mode card** (top, full width) — large pill showing current mode with color coding:
- AUTO → green
- MANUAL → orange
- VACATION → purple
- RAIN SKIP → grey
- WINTERIZED → steel-blue (#4a90b8)

Below the pill: active zone ("Zone 2 running" or "Idle"), last run, next run.

**Control buttons row** (2 columns):
- Run All (green) — disabled when mode is not AUTO or MANUAL, or when winterized
- Stop All (red) — always enabled when a zone is active

**Mode toggles section**:
- Manual Mode toggle switch — confirm before enabling ("Enable manual mode? Scheduled runs will be skipped.")
- Rain Skip toggle — confirm before enabling
- Winterize button — confirm dialog: "This will disable all irrigation until you un-winterize. Continue?" — when winterized = on, shows "Un-winterize System" button instead

**Vacation mode section**:
- When off: number input (1–30 days) labeled "Days away", "Set Vacation" button
- When on: shows "Vacation active — N days left (until DATE)", "End Vacation" button

**Zone runtimes section** (collapsible, collapsed by default) — 6 sliders labeled Zone 1–6, each 5–40 min, step 5. Show current value next to each slider. "Save Runtimes" button at the bottom (calls `/api/zone_runtimes` with all 6 values).

**Zone status grid** — 6 cards in a 3×2 grid showing zone number, runtime setting, and a colored dot: green if valve open (`sensor.sprinkler_zone_N_state = "True"`), grey if closed. Highlight the currently active zone card.

**Frontend patterns to follow (from netcore-ipam):**
- `async function load()` polls `/api/state` every 5 seconds, re-renders without full reload
- Modal dialogs with `<dialog>` + `dialog.showModal()` for confirmations
- Toast notifications (auto-dismiss 3 s) for success/error
- Disable button + show spinner during async actions, re-enable on completion

---

## Deployment target

| Item | Value |
|---|---|
| Host | `192.168.74.45` (DietPi LXC, Dockge) |
| Stack name | `sprinkler` |
| Stack path | `/opt/stacks/sprinkler/` |
| Port | `8097` |
| Networking | Host network |
| URL | `https://sprinkler.home.mihirfamily.com` (Caddy + Authentik, `admins` group) |
| Data volume | `/opt/stacks/sprinkler/data:/data` |

### Caddy snippet to add to `/opt/stacks/caddy/Caddyfile`
```
  @sprinkler host sprinkler.home.mihirfamily.com
  handle @sprinkler {
    route {
      import authentik
      reverse_proxy 192.168.74.45:8097
    }
  }
```

### DNS record
Add `sprinkler.home.mihirfamily.com A 192.168.74.45` in Technitium DNS-A (`192.168.74.29:5380`), zone `home.mihirfamily.com`.

### Deploy command
```bash
tar -cf - --exclude=.git . | ssh root@192.168.74.45 'mkdir -p /opt/stacks/sprinkler && tar -C /opt/stacks/sprinkler -xf -'
ssh root@192.168.74.45 'cd /opt/stacks/sprinkler && [ -f .env ] || install -m600 .env.example .env'
# Edit /opt/stacks/sprinkler/.env and set HA_TOKEN, then:
ssh root@192.168.74.45 'cd /opt/stacks/sprinkler && docker compose up -d --build'
```

---

## What to build — step by step

1. Read `/Users/mihirpatel/synced-ollama-claude-projects/netcore-ipam/app/main.py` and `app/static/index.html` fully before writing any code.
2. Create the project at `/Users/mihirpatel/synced-ollama-claude-projects/diy-smart-sprinkler/webapp/`.
3. Write `app/main.py`: env config → HA httpx client → background state-polling task (fetches all entities every `POLL_INTERVAL` s, stores in module-level `_state` dict) → FastAPI endpoints → static mount.
4. Write `app/static/index.html` per the layout above, following netcore-ipam's frontend patterns.
5. Write `Dockerfile`, `compose.yaml`, `requirements.txt`, `.env.example`, `.gitignore`.
6. Write `README.md` in the same style as netcore-ipam's README.
7. `git init && git add -A && git commit -m "Initial commit: sprinkler webapp"`.

Do not start a dev server or deploy — produce the code only. I will review and deploy manually.

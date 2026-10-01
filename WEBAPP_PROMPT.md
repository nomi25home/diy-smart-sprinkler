# Claude Code Prompt — Sprinkler Control Webapp

Build a homelab webapp for controlling and monitoring a 6-zone DIY sprinkler system. The webapp has **independent, direct communication with the Raspberry Pi relay controller** — it does not route zone commands through Home Assistant. HA and the webapp are two independent clients of the same Pi API; they coexist without interfering.

> **Status:** built and deployed. Code and README: [nomi25home/sprinkler-webapp](https://github.com/nomi25home/sprinkler-webapp). This prompt is kept for reference.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Raspberry Pi                   │
│         192.168.74.21:5050 (Flask API)          │
│   zone on/off • all-off • zone state read       │
└───────────────┬─────────────────┬───────────────┘
                │                 │
    direct HTTP │                 │ rest_command
                │                 │
  ┌─────────────▼──┐     ┌────────▼────────────┐
  │  This webapp   │     │   Home Assistant    │
  │ (FastAPI .45)  │     │  192.168.74.11:8123 │
  │                │◄────┤  mode helpers       │
  │ reads HA for:  │     │  vacation / manual  │
  │ mode, vacation,│     │  winterized, sched. │
  │ runtimes, etc. │     └─────────────────────┘
  └────────────────┘
```

**Pi** is the source of truth for valve hardware state. Both the webapp and HA talk to it directly and independently.

**Webapp → Pi (zone control):** all zone on/off/all-off commands go directly to the Pi Flask API. The webapp also sequences multi-zone runs itself, without calling HA scripts.

**Webapp → HA (mode state only):** the webapp reads HA for scheduling helpers (manual mode, vacation, winterized, rain skip, zone runtimes, vacation countdown) and writes back to those helpers for mode toggles. It does NOT call HA to fire zone relays.

**HA → Pi (independent):** HA continues to run its own 5:30 AM / 5:30 PM schedule via `rest_command` as before. The webapp does not break or replace this path.

---

## What it does

- Shows the current system mode (AUTO / MANUAL / VACATION / RAIN SKIP / WINTERIZED) derived from HA helpers
- Shows which zone is currently active (or "Idle") — read directly from Pi valve states
- Shows last run time and next scheduled run time — read from HA
- **Run All Zones** — webapp sequences zones 1–6 directly via Pi API (asyncio background task with per-zone delays from HA runtimes)
- **Stop All** — calls Pi `/alloff` directly; cancels any in-progress webapp run task
- **Winterize** — stops any running task, calls Pi `/alloff`, then sets `input_boolean.sprinkler_winterized` via HA
- **Un-winterize** — turns off `input_boolean.sprinkler_winterized` via HA
- Toggle for **Manual Mode** and **Rain Skip** (HA helpers, each with a confirmation step)
- **Vacation Mode** — reads/writes HA helpers; shows countdown when active
- **Zone runtime controls** — sliders per zone, saved back to `input_number.sprinkler_zone_N_runtime` via HA
- **Per-zone manual control** — tap to turn a single zone on/off directly via Pi (for landscaper spring startup)
- **Run history** — webapp tracks runs it initiates in `/data/runs.jsonl`; also shows last HA-initiated run from `input_datetime.sprinkler_last_run`
- Auto-refreshes every 5 seconds; mobile-first (375px)

**What it does NOT do (out of scope for v1):**
- Does not replace HA's scheduling (5:30 AM / 5:30 PM still run through HA)
- Does not show zone-level runtime history
- No user auth (sits behind Authentik)

---

## Architecture to follow

Build this exactly like the `netcore-ipam` app at `/Users/mihirpatel/synced-ollama-claude-projects/netcore-ipam/`. Read that codebase fully before writing any code — it is the canonical reference for structure, patterns, and deployment.

### Stack
- **Backend:** Python 3.11, FastAPI, uvicorn, httpx (two separate clients: Pi and HA), pydantic v2
- **Frontend:** A single `app/static/index.html` — vanilla JS, no build step, no npm. CSS variables, dark/light mode.
- **Container:** `Dockerfile` (python:3.11-slim), `compose.yaml` (Dockge-compatible, host network)
- **Data:** `/data/state.json` for active run state (current zone, start time, run_in_progress); `/data/runs.jsonl` for run history; `/data/audit.jsonl` for write-action audit log. Atomic writes via `.tmp` rename.
- **Config:** Environment variables only; secrets in `.env`. Include `.env.example`.

### Security (copy this pattern exactly from netcore-ipam)
- **`ALLOWED_CLIENTS` middleware:** Refuse all requests (403) not from configured CIDRs. Default: `127.0.0.1/32,172.16.0.0/12`. `/healthz` is exempt.
- **Authentik username:** Read `x-authentik-username` header → include in every audit log entry.

### Run sequencing
The `POST /api/run` endpoint launches an asyncio background task (`run_all_zones_task`) that:
1. Checks `_state["winterized"]` and `_state["run_in_progress"]` — abort if either is true
2. Sets `_state["run_in_progress"] = True`, `_state["current_zone"] = N` for each zone
3. For each zone 1–6: calls `POST http://PI_URL/zone/N` with body `"on"`, waits `zone_N_runtime` minutes, calls `POST http://PI_URL/zone/N` with body `"off"`
4. After all zones: calls `POST http://PI_URL/alloff` as safety, sets `_state["run_in_progress"] = False`, `_state["current_zone"] = 0`, appends to `runs.jsonl`
5. On cancellation (Stop All): calls `POST http://PI_URL/alloff`, cleans up state

Hold a `run_lock = asyncio.Lock()` to prevent concurrent runs. Store the task handle so `POST /api/stop` can cancel it.

### Background polling
Two background loops (separate asyncio tasks):
1. **Pi poll** (every `PI_POLL_INTERVAL` seconds, default 3): calls `GET http://PI_URL/zone/N` for each zone 1–6, stores results in `_state["zone_states"]`
2. **HA poll** (every `HA_POLL_INTERVAL` seconds, default 5): reads all HA entities listed below, stores in `_state["ha"]`

On errors: log warning, store `error` in state, never crash the task.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PI_URL` | `http://192.168.74.21:5050` | Pi Flask API base URL |
| `HA_URL` | `http://192.168.74.11:8123` | HA instance |
| `HA_TOKEN` | _(required, in .env)_ | HA long-lived access token |
| `PI_POLL_INTERVAL` | `3` | Seconds between Pi zone state polls |
| `HA_POLL_INTERVAL` | `5` | Seconds between HA state polls |
| `ALLOWED_CLIENTS` | `127.0.0.1/32,172.16.0.0/12` | Allowed CIDRs |
| `DATA_DIR` | `/data` | Persistent state, runs, and audit log |

---

## Pi Flask API (direct zone control)

Pi is at `192.168.74.21:5050`. All calls use plain HTTP, no auth.

| What | Method | Path | Body |
|---|---|---|---|
| Get zone state | `GET` | `/zone/N` | — |
| Zone on | `POST` | `/zone/N` | `"on"` |
| Zone off | `POST` | `/zone/N` | `"off"` |
| All off | `POST` | `/alloff` | — |

Zone state response: `{"zone": N, "state": "on" | "off"}` (confirm exact format from `raspberry-pi/server.py` in the repo before coding).

---

## HA REST API (mode state and helpers only)

HA token goes in `Authorization: Bearer <HA_TOKEN>` on every call.

### Entities to read (all via `GET /api/states/<entity_id>`)

| Entity | What it gives us |
|---|---|
| `sensor.sprinkler_mode` | Current mode: AUTO / MANUAL / VACATION / RAIN SKIP / WINTERIZED |
| `sensor.sprinkler_last_ran` | Human-readable last run timestamp (HA-initiated runs) |
| `sensor.sprinkler_next_run` | Human-readable next scheduled run |
| `input_boolean.sprinkler_rain_skip` | on/off |
| `input_boolean.sprinkler_manual_mode` | on/off |
| `input_boolean.sprinkler_vacation_mode` | on/off |
| `input_boolean.sprinkler_winterized` | on/off |
| `input_number.sprinkler_zone_1_runtime` … `_zone_6_runtime` | Per-zone runtime in minutes |
| `input_datetime.sprinkler_vacation_until` | Date string |

### Services to call (all via `POST /api/services/<domain>/<service>`)

| What | Domain | Service | Data |
|---|---|---|---|
| Winterized on | `input_boolean` | `turn_on` | `{"entity_id": "input_boolean.sprinkler_winterized"}` |
| Winterized off | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_winterized"}` |
| Manual mode on | `input_boolean` | `turn_on` | `{"entity_id": "input_boolean.sprinkler_manual_mode"}` |
| Manual mode off | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_manual_mode"}` |
| Rain skip on | `input_boolean` | `turn_on` | `{"entity_id": "input_boolean.sprinkler_rain_skip"}` |
| Rain skip off | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_rain_skip"}` |
| Set vacation days | `input_number` | `set_value` | `{"entity_id": "input_number.sprinkler_vacation_days", "value": N}` |
| Activate vacation | `script` | `sprinkler_set_vacation` | `{}` |
| End vacation | `input_boolean` | `turn_off` | `{"entity_id": "input_boolean.sprinkler_vacation_mode"}` |
| Set zone N runtime | `input_number` | `set_value` | `{"entity_id": "input_number.sprinkler_zone_N_runtime", "value": N}` |

---

## Webapp API endpoints

- `GET /api/state` — full snapshot: Pi zone states + HA mode state + webapp run state (current_zone, run_in_progress, last_webapp_run)
- `POST /api/run` — start run-all-zones background task (Pi-direct sequencing)
- `POST /api/stop` — cancel run task + call Pi `/alloff`
- `POST /api/zone` body `{"zone": N, "on": true/false}` — single zone direct Pi control
- `POST /api/winterize` — cancel run task + call Pi `/alloff` + turn on HA `sprinkler_winterized`
- `POST /api/unwinterize` — turn off HA `sprinkler_winterized`
- `POST /api/manual` body `{"on": true/false}` — HA helper toggle
- `POST /api/rain_skip` body `{"on": true/false}` — HA helper toggle
- `POST /api/vacation` body `{"days": N}` — set vacation (0 = end early)
- `POST /api/zone_runtimes` body `{"zone_1": N, …, "zone_6": N}` — write HA runtimes
- `GET /api/history?limit=10` — combined list of webapp runs (from `runs.jsonl`) and last HA-initiated run (from `sensor.sprinkler_last_ran`)
- `GET /api/audit?limit=50` — audit log
- `GET /healthz` — `{"ok": true}`
- `GET /` — serves index.html

---

## Frontend layout (index.html)

Single page, mobile-first (375px), dark/light mode via CSS variables.

**Header** — "Sprinkler Control", last-updated time, refresh button, audit log button.

**Mode card** (full width, top) — large pill, color-coded:
- AUTO → green · MANUAL → orange · VACATION → purple · RAIN SKIP → grey · WINTERIZED → steel-blue (#4a90b8)

Below pill: active zone or "Idle" (from Pi states), last run, next run.

**Control buttons** (2-up): Run All (green, disabled when winterized/vacation/rain-skip), Stop All (red, enabled when run_in_progress).

**Mode toggles**: Manual Mode toggle (confirm on), Rain Skip toggle (confirm on), Winterize button (confirm; shows Un-winterize when active).

**Vacation section**: days input + Set button when off; countdown + End button when on.

**Zone status grid** (3×2): each card shows zone number, runtime (from HA), valve state dot (green=open from Pi poll), tap-to-toggle direct Pi control. Highlight the active zone during a run.

**Zone runtimes** (collapsible): 6 sliders 5–40 min step 5, Save button.

**Frontend patterns (from netcore-ipam):** polling `load()` every 5 s, `<dialog>` modals for confirmations, toast notifications (3 s), button spinner during async actions.

---

## Deployment target

| Item | Value |
|---|---|
| Host | `192.168.74.45` (DietPi LXC, Dockge) |
| Stack name | `sprinkler` |
| Port | `8097` (host network) |
| URL | `https://sprinkler.home.mihirfamily.com` (Caddy + Authentik, `admins` group) |
| Data volume | `/opt/stacks/sprinkler/data:/data` |

### Caddy snippet
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
`sprinkler.home.mihirfamily.com A 192.168.74.45` in Technitium DNS-A (`192.168.74.29:5380`), zone `home.mihirfamily.com`.

### Deploy
```bash
tar -cf - --exclude=.git . | ssh root@192.168.74.45 'mkdir -p /opt/stacks/sprinkler && tar -C /opt/stacks/sprinkler -xf -'
ssh root@192.168.74.45 'cd /opt/stacks/sprinkler && [ -f .env ] || install -m600 .env.example .env'
# Set HA_TOKEN in .env, then:
ssh root@192.168.74.45 'cd /opt/stacks/sprinkler && docker compose up -d --build'
```

---

## What to build — step by step

1. Read `raspberry-pi/server.py` in this repo to confirm Pi API response shapes before coding.
2. Read `/Users/mihirpatel/synced-ollama-claude-projects/netcore-ipam/app/main.py` and `app/static/index.html` fully.
3. Create `/Users/mihirpatel/synced-ollama-claude-projects/diy-smart-sprinkler/webapp/`.
4. Write `app/main.py`: env config → Pi httpx client → HA httpx client → `_state` dict → Pi poll task → HA poll task → `run_all_zones_task` with cancellation → FastAPI endpoints → static mount.
5. Write `app/static/index.html` per the layout above.
6. Write `Dockerfile`, `compose.yaml`, `requirements.txt`, `.env.example`, `.gitignore`.
7. Write `README.md` covering architecture (both Pi-direct and HA paths), env vars, deploy steps.
8. `git init && git add -A && git commit -m "Initial commit: sprinkler webapp"`.

Do not start a dev server or deploy — produce the code only. I will review and deploy manually.

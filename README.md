# SENTRY v2.7: Mining Ops Console

**The definitive Ship Management & Threat Detection HUD for EVE Online.**

## 🚦 Priority Color Legend

The background color of the console provides instant status recognition. **Priority 1** overrides all other colors.

| Priority | State | Color | Trigger |
| --- | --- | --- | --- |
| **1** | **COMBAT** | **Orange Strobe** | Incoming hits, outgoing drone fire, or ECM Jams. |
| **2** | **CARGO FULL** | **Electric Cyan** | Log reports "cargo hold is full" or "docking perimeter." |
| **3** | **IDLE** | **Blood Red** | No mining hits for 190s OR "Laser Deactivates" (Rock Popped). |
| **4** | **ACTIVE** | **Charcoal** | Systems nominal; laser cycles in progress. |

## 🛠 Features & Intelligence

* **Identity Lock:** Automatically parses the `Listener:` header to identify the active **PILOT**.
* **Active Rock Monitoring:** Instantly detects when a laser deactivates because a target is lost (Rock Popped), bypassing the 190s idle delay.
* **ECM Awareness:** Recognizes being **Jammed** as a combat event, triggering the strobe before damage is even taken.
* **Auto-Pause (Timer Accuracy):** Automatically pauses the session timer when cargo is full or docking begins. This ensures your **Eff (Units/Min)** represents actual time in the belt, not time spent hauling.
* **Alt-Swap Logic:** The `RESET | SWAP` button allows seamless transition between character log files without an application restart.

## 🎮 Standard Operating Procedure (SOP)

### 1. The Drone Radar

Always deploy drones and set them to **Aggressive / Focus Fire**. Because EVE does not log "Yellow Boxing" (locking), your drones are your early warning system. SENTRY will strobe orange the second they engage a target.

### 2. Multi-Boxing Flow

1. Log into your alt.
2. Click `RESET | SWAP`.
3. Verify the **PILOT** name updates in the header.
4. If switching back, click the button again once you are active in the second client.

### 3. Handling Alerts

* **Red Window:** Your lasers have stopped. Relock a new rock and cycle.
* **Cyan Window:** Your hold is full. Warp to station. The script has already paused your efficiency timer.
* **Orange Strobe:** Check your drones or your shield—threats are on grid.

---

## 📋 Technical Requirements

* **Python 3.13+**
* **Dear PyGui 1.10.0+** (`pip install dearpygui`)
* **Pathing:** Works with standard EVE Gamelog locations (including OneDrive).

---
# 🛰️ SENTRY v2.7.3: Mining Ops Console
> **The definitive Ship Management & Threat Detection HUD for EVE Online.**

---

## 🚦 Priority Color Legend
The console uses "Mood Lighting" for instant status recognition. **Priority 1** overrides all other states.

| Priority | State | Color | Trigger |
| :--- | :--- | :--- | :--- |
| 🟠 **1** | **COMBAT** | **Orange Strobe** | Incoming hits, drone fire, or **ECM Jams**. |
| 💎 **2** | **HOLD FULL** | **Electric Cyan** | Log reports "cargo hold is full" or docking. |
| 🔴 **3** | **IDLE** | **Blood Red** | No hits for 190s OR **Active Rock Pop**. |
| ⚫ **4** | **ACTIVE** | **Charcoal** | Systems nominal; lasers cycling. |

---

## 🛠️ Intelligence & Automation (v2.7.3)

* 🚀 **Universal Rock Monitoring**
    Instantly detects deactivation across all module types (Gaussian, Strip Miners, etc.) by watching for "resource" or "target" loss notifications.
* 🔄 **Zero-Click Auto-Resume**
    The session timer and HUD status automatically "wake up" the second new ore hits your cargo hold. No manual interaction required.
* 📡 **ECM Awareness**
    Identifies "Jammed" status as a combat event, triggering the strobe before physical damage is sustained.
* ⏸️ **Auto-Pause (Efficiency Guard)**
    Freezes tracking during hauling/docking to ensure your **Eff (Units/Min)** represents actual time in the belt.
* 👤 **Pilot Identity Lock**
    Parses the log header to display the active **PILOT** name, ensuring accuracy after an Alt-Swap.

---

## 🎮 Standard Operating Procedure (SOP)

### 1️⃣ The Setup
* Run `Sentry_v2.7.3.pyw`.
* Ensure drones are out and set to **Aggressive / Focus Fire**.
* Click `RESET | SWAP` when switching character clients.

### 2️⃣ The Mining Loop
* **Undocking:** Just start your lasers. The console will turn from **Red** to **Charcoal** automatically.
* **Full Hold:** When the window turns **Electric Cyan**, warp to station. The timer is already paused for you.
* **Unloading:** Once back in the belt, the first successful cycle will auto-resume the HUD.

---

## 📋 Technical Requirements
* **Python:** 3.13+
* **Library:** `dearpygui` (`pip install dearpygui`)
* **EVE Setting:** "Log to File" must be **ENABLED** in the EVE Esc-menu.

---
*Safe flying, Pilot. Keep the lasers hot.*
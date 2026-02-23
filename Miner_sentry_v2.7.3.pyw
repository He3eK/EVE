#!/usr/bin/env python3
import dearpygui.dearpygui as dpg
import os, time, re, glob, threading
from datetime import datetime

# --- CONFIG & PATHS ---
def get_log_directory():
    win_onedrive = r"D:\OneDrive\Documents\EVE\logs\Gamelogs"
    if os.path.exists(win_onedrive): return win_onedrive
    win_standard = os.path.join(os.environ.get('USERPROFILE', ''), 'Documents', 'EVE', 'logs', 'Gamelogs')
    if os.path.exists(win_standard): return win_standard
    return os.path.expanduser("~/Documents/EVE/logs/Gamelogs/")

LOG_DIR = get_log_directory()
IDLE_THRESHOLD = 190  
stats = {
    "total": 0, "waste": 0, "last_crit": 0, "last_hit_time": time.time(),
    "start_time": None, "history": [], "paused": False,
    "pause_start": None, "total_paused_time": 0,
    "under_attack": False, "last_combat_time": 0,
    "current_log": "", "pilot_name": "Scanning..."
}
running = True
log_lock = threading.Lock()

def get_pilot_name(filepath):
    try:
        with open(filepath, "r", encoding="latin-1") as f:
            for _ in range(10): 
                line = f.readline()
                if "Listener:" in line: return line.split("Listener:")[1].strip()
    except: pass
    return "Unknown Pilot"

def get_latest_log():
    if not os.path.exists(LOG_DIR): return None
    list_of_files = glob.glob(os.path.join(LOG_DIR, "*.txt"))
    if not list_of_files: return None
    latest = max(list_of_files, key=os.path.getctime)
    stats["current_log"] = os.path.basename(latest)
    stats["pilot_name"] = get_pilot_name(latest)
    return latest

# --- UI ACTIONS ---
def toggle_pause(force_state=None):
    if force_state is not None: stats["paused"] = force_state
    else: stats["paused"] = not stats["paused"]
        
    if stats["paused"]:
        stats["pause_start"] = time.time()
        dpg.configure_item("pause_btn", label="RESUME OPS")
    else:
        if stats["pause_start"]:
            stats["total_paused_time"] += (time.time() - stats["pause_start"])
        stats["last_hit_time"] = time.time()
        dpg.configure_item("pause_btn", label="PAUSE (DOCKING)")

def reset_session():
    with log_lock:
        stats.update({"total": 0, "waste": 0, "last_crit": 0, "history": [], 
                      "start_time": datetime.now(), "last_hit_time": time.time(), 
                      "total_paused_time": 0, "under_attack": False})
        get_latest_log(); update_ui()

# --- MONITOR ---
def log_monitor():
    global running
    while running:
        latest_log = get_latest_log()
        if not latest_log:
            time.sleep(2); continue
        with open(latest_log, "rb") as f:
            f.seek(0, os.SEEK_END)
            while running and dpg.is_dearpygui_running():
                if stats["current_log"] != os.path.basename(latest_log): break 
                now = time.time()
                time_since_hit = now - stats["last_hit_time"]
                
                # VISUAL PRIORITY ENGINE
                if dpg.does_item_exist("status_text"):
                    if stats["under_attack"]:
                        color = (255, 100, 0) if int(now * 3) % 2 == 0 else (60, 20, 0)
                        with dpg.theme() as ct:
                            with dpg.theme_component(dpg.mvAll):
                                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, color, category=dpg.mvThemeCat_Core)
                        dpg.bind_item_theme("PrimaryWindow", ct)
                        dpg.set_value("status_text", "!!! HOSTILE CONTACT !!!")
                        if now - stats["last_combat_time"] > 40: stats["under_attack"] = False
                    elif stats["paused"]:
                        with dpg.theme() as pt:
                            with dpg.theme_component(dpg.mvAll):
                                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (0, 150, 200), category=dpg.mvThemeCat_Core)
                        dpg.bind_item_theme("PrimaryWindow", pt)
                        dpg.set_value("status_text", "STATUS: HOLD FULL / DOCKED")
                    elif time_since_hit > IDLE_THRESHOLD:
                        with dpg.theme() as it:
                            with dpg.theme_component(dpg.mvAll):
                                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (100, 0, 0), category=dpg.mvThemeCat_Core)
                        dpg.bind_item_theme("PrimaryWindow", it)
                        dpg.set_value("status_text", "STATUS: IDLE")
                    else:
                        dpg.bind_item_theme("PrimaryWindow", 0)
                        dpg.set_value("status_text", "STATUS: ACTIVE")

                line = f.readline()
                if not line: time.sleep(0.1); continue
                
                text = line.decode('latin-1').replace('\x00', '').strip()
                text = re.sub(r'<.*?>', '', text)
                ts = datetime.now().strftime("%H:%M:%S")

                # --- AUTO-ALERTS ---
                # 1. Universal Rock Popped detection
                if "deactivates" in text and ("target" in text or "resource" in text):
                    if not stats["paused"]:
                        stats["history"].insert(0, f"[{ts}] !! ROCK POPPED !!")
                        stats["last_hit_time"] = now - IDLE_THRESHOLD 

                # 2. Jamming / Combat
                if "jammed by" in text or ((" from " in text or " to " in text) and any(res in text for res in ["Hits", "Smashes", "Glances", "Penetrates"])):
                    stats["under_attack"] = True; stats["last_combat_time"] = now
                    if "jammed" in text: stats["history"].insert(0, f"[{ts}] !! ECM JAM DETECTED !!")

                # 3. Cargo Full
                if "cargo hold is full" in text or "Setting course to docking" in text:
                    if not stats["paused"]:
                        toggle_pause(force_state=True)
                        stats["history"].insert(0, f"[{ts}] !! HOLD FULL !!")

                # --- MINING PARSING & AUTO-RESUME ---
                norm_m = re.search(r"mined ([\d,.]+) units of ([\w\s]+)", text)
                crit_m = re.search(r"additional ([\d,.]+) units of (.*)", text)
                waste_m = re.search(r"Additional ([\d,.]+) units depleted.*residue", text)

                if norm_m:
                    if stats["paused"]: # Auto-Resume on new ore
                        toggle_pause(force_state=False)
                        stats["history"].insert(0, f"[{ts}] >> AUTO-RESUMING <<")
                    if stats["start_time"] is None: stats["start_time"] = datetime.now()
                    val = int(norm_m.group(1).replace(',', ''))
                    stats["total"] += val; stats["last_hit_time"] = now
                    stats["history"].insert(0, f"[{ts}] +{val:,} {norm_m.group(2).strip()[:10]}")
                elif "Critical mining success" in text and crit_m:
                    val = int(crit_m.group(1).replace(',', ''))
                    stats["total"] += val; stats["last_hit_time"] = now
                    stats["history"].insert(0, f"[{ts}] *** CRIT: +{val:,} ***")
                elif waste_m:
                    stats["waste"] += int(waste_m.group(1).replace(',', ''))
                
                stats["history"] = stats["history"][:50]; update_ui()

def update_ui():
    if not dpg.does_item_exist("total_text"): return
    dpg.set_value("pilot_display", f"PILOT: {stats['pilot_name']}")
    dpg.set_value("total_text", f"Total: {stats['total']:,}")
    dpg.set_value("crit_text", f"LAST CRIT: {stats['last_crit']:,}")
    wp = (stats["waste"] / (stats["total"] + stats["waste"])) * 100 if (stats["total"] + stats["waste"]) > 0 else 0
    dpg.set_value("waste_text", f"Residue: {stats['waste']:,} ({wp:.1f}%)")
    if stats["start_time"]:
        active_sec = (datetime.now() - stats["start_time"]).total_seconds() - stats["total_paused_time"]
        dpg.set_value("timer_text", f"Session: {str(datetime.now() - stats['start_time']).split('.')[0]}")
        if active_sec > 5: dpg.set_value("upm_text", f"Eff: {int(stats['total'] / (active_sec / 60)):,}/m")
    dpg.set_value("log_list", "\n".join(stats["history"]))

# --- GUI ---
dpg.create_context()
with dpg.window(label="SENTRY_V2.7.3", tag="PrimaryWindow"):
    with dpg.group(horizontal=True):
        dpg.add_text("STATUS: ACTIVE", tag="status_text", color=[0, 255, 0])
        dpg.add_spacer(width=20)
        dpg.add_text("PILOT: Scanning...", tag="pilot_display", color=[200, 200, 255])
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_text("Total: 0", tag="total_text", color=[100, 255, 100])
        dpg.add_spacer(width=20)
        dpg.add_text("Eff: 0/m", tag="upm_text", color=[0, 190, 255])
    dpg.add_text("LAST CRIT: 0", tag="crit_text", color=[255, 215, 0])
    with dpg.group(horizontal=True):
        dpg.add_text("Session: 0:00:00", tag="timer_text", color=[150, 150, 150])
        dpg.add_spacer(width=15)
        dpg.add_text("Residue: 0 (0.0%)", tag="waste_text", color=[100, 100, 100])
    dpg.add_spacer(height=5)
    with dpg.group(horizontal=True):
        dpg.add_button(label="PAUSE (DOCKING)", tag="pause_btn", callback=lambda: toggle_pause(), width=160)
        dpg.add_button(label="RESET | SWAP", callback=reset_session, width=160)
    dpg.add_separator()
    with dpg.child_window(height=180, tag="log_container", border=True):
        dpg.add_text("", tag="log_list", color=[50, 255, 50])
    dpg.add_spacer(height=5)
    with dpg.group(horizontal=True):
        dpg.add_checkbox(label="ON TOP", default_value=True, callback=lambda s, a: dpg.set_viewport_always_top(a))
        dpg.add_spacer(width=20)
        dpg.add_button(label="TERMINATE", callback=lambda: dpg.stop_dearpygui(), width=-1)

dpg.create_viewport(title='SENTRY_V2.7.3', width=360, height=520)
dpg.setup_dearpygui(); dpg.show_viewport(); dpg.set_primary_window("PrimaryWindow", True)
dpg.set_viewport_always_top(True)
threading.Thread(target=log_monitor, daemon=True).start()
dpg.start_dearpygui(); dpg.destroy_context()
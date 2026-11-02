#!/usr/bin/env python3
import dearpygui.dearpygui as dpg
import os, sys, time, re, glob, threading

# --- CONFIG & PATHS ---
VERSION = "1.6"
MAX_LOG_ENTRIES = 60
COMBAT_TIMEOUT = 15          # seconds of quiet before "COMBAT ACTIVE" clears
NEWER_LOG_CHECK = 5          # seconds between checks for a newer log file

def get_log_directory():
    path = r"D:\OneDrive\Documents\EVE\logs\Gamelogs"
    if os.path.exists(path): return path
    return os.path.join(os.environ.get('USERPROFILE', ''), 'Documents', 'EVE', 'logs', 'Gamelogs')

LOG_DIR = get_log_directory()

# Lines the parser could not classify get written here (one per distinct shape)
# so new formats (jams, webs, damps, painters, nos...) can be added without guessing.
UNPARSED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combat_sentry_unparsed.txt")

def fresh_stats():
    return {
        "out_total": 0, "in_total": 0, "top_attacker": "None",
        "miss_in": 0, "miss_out": 0,
        "ewar": {}, "ewar_src": {}, "neut_in_gj": 0, "neut_out_gj": 0,
        "top_ewar": "None",
        "under_attack": False, "last_combat_time": 0,
        "attackers_db": {},
    }

stats = fresh_stats()
stats.update({"paused": False, "current_log": "", "pilot_name": "Scanning..."})
running = True
THEME_ATTACK = THEME_PAUSED = None

# --- LINE PARSING ---------------------------------------------------------
TAG_RE      = re.compile(r"<[^>]*>")
LINE_RE     = re.compile(r"^\[\s*([\d.]+\s+[\d:]+)\s*\]\s*\((\w+)\)\s*(.*)$")
DMG_RE      = re.compile(r"^(?P<amt>\d+) (?P<dir>to|from) (?P<rest>.+)$")
MISS_IN_RE  = re.compile(r"^(?P<who>.+?) misses you completely(?: - (?P<weapon>.+))?$")
MISS_OUT_RE = re.compile(r"^Your (?P<weapon>.+?) misses (?P<who>.+?) completely(?: - .+)?$")
EWAR_RE     = re.compile(r"^(?P<kind>.+?) attempt from (?P<src>.+?) to (?P<dst>.+?)!?$")
NEUT_RE     = re.compile(r"^(?P<amt>[\d,.]+) GJ energy neutralized (?P<rest>.+)$")
BOUNTY_RE   = re.compile(r"^(?P<amt>[\d,.]+) ISK added to next bounty payout")

EWAR_SHORT = {"Warp scramble": "SCRAM", "Warp disruption": "DISRUPT"}

def parse_line(raw):
    """Turn one raw log line into an event dict, or None if it isn't combat-related.
    Event kinds: out, in, miss_in, miss_out, ewar_in, ewar_out, neut_in, neut_out,
                 bounty, unparsed"""
    m = LINE_RE.match(raw.strip())
    if not m: return None
    _ts, channel, rest = m.groups()
    if channel not in ("combat", "bounty"): return None

    text = re.sub(r"\s+", " ", TAG_RE.sub("", rest).replace("\xa0", " ")).strip()

    if channel == "bounty":
        b = BOUNTY_RE.match(text)
        return {"kind": "bounty", "amt": b["amt"]} if b else None

    d = DMG_RE.match(text)
    if d:
        parts = [p.strip() for p in d["rest"].split(" - ")]
        return {"kind": "out" if d["dir"] == "to" else "in",
                "amt": int(d["amt"]), "name": parts[0],
                "weapon": parts[1] if len(parts) > 2 else "",
                "quality": parts[-1] if len(parts) > 1 else ""}

    mi = MISS_IN_RE.match(text)
    if mi: return {"kind": "miss_in", "name": mi["who"], "weapon": mi["weapon"] or ""}
    mo = MISS_OUT_RE.match(text)
    if mo: return {"kind": "miss_out", "name": mo["who"], "weapon": mo["weapon"]}

    n = NEUT_RE.match(text)
    if n:
        # Direction isn't in the text, only the colour: e57f7f (red) = you were neuted.
        incoming = "e57f7f" in rest.lower()
        return {"kind": "neut_in" if incoming else "neut_out",
                "amt": int(float(n["amt"].replace(",", ""))),
                "name": n["rest"].split(" - ")[0].strip()}

    e = EWAR_RE.match(text)
    if e:
        kind = EWAR_SHORT.get(e["kind"], e["kind"].upper())
        if e["dst"].lower() == "you":
            return {"kind": "ewar_in", "ewar": kind, "name": e["src"]}
        if e["src"].lower() == "you":
            return {"kind": "ewar_out", "ewar": kind, "name": e["dst"]}

    return {"kind": "unparsed", "text": text}

_seen_unparsed = set()
def note_unparsed(text):
    shape = re.sub(r"\d+", "#", text)
    if shape in _seen_unparsed: return
    _seen_unparsed.add(shape)
    try:
        with open(UNPARSED_FILE, "a", encoding="utf-8") as fh: fh.write(text + "\n")
    except OSError: pass

def _bump(d, key, amt=1):
    d[key] = d.get(key, 0) + amt

def record_event(ev, now):
    """Update stats for one event. Returns (log message, colour) or None."""
    k = ev["kind"]
    hostile = False
    msg = None

    if k == "out":
        stats["out_total"] += ev["amt"]
        msg = (f"OUT: {ev['amt']} to {ev['name']}", [100, 255, 100])
    elif k == "in":
        hostile = True
        stats["in_total"] += ev["amt"]
        _bump(stats["attackers_db"], ev["name"], ev["amt"])
        stats["top_attacker"] = max(stats["attackers_db"], key=stats["attackers_db"].get)
        msg = (f"IN: {ev['amt']} from {ev['name']}", [255, 100, 100])
    elif k == "miss_in":
        hostile = True
        stats["miss_in"] += 1
        msg = (f"MISS: {ev['name']} missed you", [110, 200, 255])
    elif k == "miss_out":
        stats["miss_out"] += 1
        msg = (f"MISS: your {ev['weapon']} missed {ev['name']}", [200, 200, 120])
    elif k in ("ewar_in", "neut_in"):
        hostile = True
        label = ev["ewar"] if k == "ewar_in" else "NEUT"
        _bump(stats["ewar"], label)
        if k == "neut_in": stats["neut_in_gj"] += ev["amt"]
        _bump(stats["ewar_src"], ev["name"])
        stats["top_ewar"] = max(stats["ewar_src"], key=stats["ewar_src"].get)
        if k == "ewar_in": msg = (f"{label}: {ev['name']}", [255, 110, 255])
        else:              msg = (f"NEUT: {ev['amt']} GJ from {ev['name']}", [190, 130, 255])
    elif k in ("ewar_out", "neut_out"):
        if k == "neut_out": stats["neut_out_gj"] += ev["amt"]
        msg = ((f"YOU {ev['ewar']}: {ev['name']}" if k == "ewar_out"
                else f"YOU NEUT: {ev['amt']} GJ on {ev['name']}"), [150, 220, 180])
    elif k == "bounty":
        msg = (f"+{ev['amt']} ISK", [255, 215, 0])
    elif k == "unparsed":
        note_unparsed(ev["text"])

    if hostile:
        stats["under_attack"] = True
        stats["last_combat_time"] = now
    return msg

# --- LOG FILE DISCOVERY ---------------------------------------------------
def get_pilot_name(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(20):
                line = f.readline()
                if "Listener:" in line: return line.split("Listener:")[1].strip()
    except OSError: pass
    return "Unknown Pilot"

def newest_log_path():
    if not os.path.exists(LOG_DIR): return None
    files = glob.glob(os.path.join(LOG_DIR, "*.txt"))
    return max(files, key=os.path.getctime) if files else None

def get_latest_log():
    latest = newest_log_path()
    if latest:
        stats["current_log"] = os.path.basename(latest)
        stats["pilot_name"] = get_pilot_name(latest)
    return latest

# --- UI ACTIONS -----------------------------------------------------------
def toggle_pause(force_state=None):
    stats["paused"] = (not stats["paused"]) if force_state is None else force_state
    dpg.configure_item("pause_btn", label="RESUME MONITOR" if stats["paused"] else "PAUSE (STATION)")

def reset_session():
    stats.update(fresh_stats())
    dpg.delete_item("log_container", children_only=True)
    get_latest_log()
    update_ui()

def add_log_entry(message, color):
    kids = dpg.get_item_children("log_container", 1)
    # wrap=0 -> wrap at the edge of the window instead of cutting names off
    if kids: dpg.add_text(message, parent="log_container", color=color, wrap=0, before=kids[0])
    else:    dpg.add_text(message, parent="log_container", color=color, wrap=0)
    kids = dpg.get_item_children("log_container", 1)
    while len(kids) > MAX_LOG_ENTRIES:
        dpg.delete_item(kids.pop())

def update_ui():
    if not dpg.does_item_exist("total_text"): return
    dpg.set_value("pilot_display", f"PILOT: {stats['pilot_name']}")
    dpg.set_value("total_text", f"OUTGOING: {stats['out_total']:,}   (you missed: {stats['miss_out']:,})")
    top_dmg = stats["attackers_db"].get(stats["top_attacker"], 0)
    dpg.set_value("threat_text", f"TOP THREAT: {stats['top_attacker']} ({top_dmg:,})")
    dpg.set_value("incoming_text", f"INCOMING: {stats['in_total']:,}   (they missed: {stats['miss_in']:,})")
    ew = stats["ewar"]
    parts = [f"SCRAM {ew.get('SCRAM', 0)}", f"DISRUPT {ew.get('DISRUPT', 0)}"]
    parts += [f"{k} {v}" for k, v in sorted(ew.items()) if k not in ("SCRAM", "DISRUPT", "NEUT")]
    parts.append(f"NEUT {ew.get('NEUT', 0)} ({stats['neut_in_gj']:,} GJ)")
    dpg.set_value("ewar_text", "EWAR: " + " | ".join(parts))
    top_n = stats["ewar_src"].get(stats["top_ewar"], 0)
    dpg.set_value("ewar_top_text", f"TOP EWAR: {stats['top_ewar']} ({top_n})")

def handle_raw(raw_bytes):
    ev = parse_line(raw_bytes.decode("utf-8", errors="replace").replace("\x00", ""))
    if not ev: return False
    out = record_event(ev, time.time())
    if out: add_log_entry(*out)
    return True

# --- VISUAL STATE (themes are built once, only re-bound on change) --------
_last_visual = None
def refresh_visual_state(now):
    global _last_visual
    if not dpg.does_item_exist("status_text"): return
    if stats["under_attack"]:
        state, text, theme = "attack", "!!! COMBAT ACTIVE !!!", THEME_ATTACK
        if now - stats["last_combat_time"] > COMBAT_TIMEOUT: stats["under_attack"] = False
    elif stats["paused"]:
        state, text, theme = "paused", "STATUS: PAUSED", THEME_PAUSED
    else:
        state, text, theme = "active", "STATUS: ACTIVE", 0
    if state != _last_visual:
        dpg.bind_item_theme("PrimaryWindow", theme)
        dpg.set_value("status_text", text)
        _last_visual = state

# --- MONITOR --------------------------------------------------------------
def log_monitor():
    while running:
        latest_log = get_latest_log()
        update_ui()
        if not latest_log:
            time.sleep(2); continue

        last_check = time.time()
        with open(latest_log, "rb") as f:
            f.seek(0, os.SEEK_END)
            while running and dpg.is_dearpygui_running():
                now = time.time()
                refresh_visual_state(now)

                # A new EVE client session creates a new log file - switch to it.
                if now - last_check > NEWER_LOG_CHECK:
                    last_check = now
                    newest = newest_log_path()
                    if newest and newest != latest_log: break

                pos = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(0.1); continue
                if not line.endswith(b"\n"):          # half-written line, retry
                    f.seek(pos); time.sleep(0.1); continue
                if stats["paused"]: continue          # drain & discard while paused

                if handle_raw(line): update_ui()

def replay(path):
    """--replay FILE: feed an existing log through the UI from the start."""
    n = 0
    with open(path, "rb") as f:
        for line in f:
            if not running: break
            handle_raw(line)
            n += 1
            if n % 25 == 0: update_ui(); time.sleep(0.005)
    update_ui()

# --- GUI ------------------------------------------------------------------
def build_gui():
    global THEME_ATTACK, THEME_PAUSED
    dpg.create_context()
    for name, rgb in (("THEME_ATTACK", (80, 0, 0)), ("THEME_PAUSED", (0, 50, 100))):
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, rgb, category=dpg.mvThemeCat_Core)
        globals()[name] = t

    with dpg.window(label=f"COMBAT_SENTRY v{VERSION}", tag="PrimaryWindow"):
        with dpg.group(horizontal=True):
            dpg.add_text("STATUS: SCANNING", tag="status_text", color=[0, 255, 0])
            dpg.add_spacer(width=20)
            dpg.add_text("PILOT: Scanning...", tag="pilot_display", color=[200, 200, 255])
        dpg.add_separator()

        dpg.add_text("OUTGOING: 0", tag="total_text", color=[100, 255, 100], wrap=0)
        dpg.add_text("TOP THREAT: None", tag="threat_text", color=[255, 100, 100], wrap=0)
        dpg.add_text("INCOMING: 0", tag="incoming_text", color=[255, 150, 0], wrap=0)
        dpg.add_text("EWAR: -", tag="ewar_text", color=[255, 110, 255], wrap=0)
        dpg.add_text("TOP EWAR: None", tag="ewar_top_text", color=[190, 130, 255], wrap=0)

        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_button(label="PAUSE (STATION)", tag="pause_btn", callback=lambda: toggle_pause(), width=200)
            dpg.add_button(label="RESET SESSION", callback=reset_session, width=200)
        dpg.add_separator()

        with dpg.child_window(height=300, tag="log_container", border=True):
            pass

        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_checkbox(label="ON TOP", default_value=True, callback=lambda s, a: dpg.set_viewport_always_top(a))
            dpg.add_spacer(width=20)
            dpg.add_button(label="TERMINATE", callback=lambda: dpg.stop_dearpygui(), width=-1)

    dpg.create_viewport(title=f"COMBAT_SENTRY v{VERSION}", width=460, height=640)
    dpg.setup_dearpygui(); dpg.show_viewport(); dpg.set_primary_window("PrimaryWindow", True)
    dpg.set_viewport_always_top(True)

def main():
    build_gui()
    if "--replay" in sys.argv:
        path = sys.argv[sys.argv.index("--replay") + 1]
        stats["current_log"] = os.path.basename(path)
        stats["pilot_name"] = get_pilot_name(path)
        threading.Thread(target=replay, args=(path,), daemon=True).start()
    else:
        threading.Thread(target=log_monitor, daemon=True).start()
    dpg.start_dearpygui(); dpg.destroy_context()

if __name__ == "__main__":
    main()

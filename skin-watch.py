# -*- coding: utf-8 -*-
"""WorkBuddy skin keeper (self-healing, zero third-party deps).

What it does, in one endless loop (every ~2s):
  1. keeps the WorkDaddy daemon alive (restarts it if it died)
  2. keeps the chosen theme applied (colors + CSS patches pushed over CDP)
  3. keeps the wallpaper style element alive (WorkDaddy's own injection can
     compute to `background-image: none`, so we re-inject a longhand rule
     with !important whenever it goes missing - e.g. after every page reload)
  4. if WorkBuddy is running WITHOUT the CDP port (started from the plain
     icon) it relaunches it once, so injection becomes possible again

Singleton: binds 127.0.0.1:47999. Second instance exits immediately.
Config:   theme.txt (theme id), optional `no-restart.flag` to disable (4).
Log:      watch.log (rotated at 1 MB)
"""
import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import cdpmini

HOME = Path.home()
ROAM = HOME / "AppData" / "Roaming" / "WorkDaddy"
HERE = Path(__file__).resolve().parent
LOG = HERE / "watch.log"
THEME_FILE = HERE / "theme.txt"
NO_RESTART = HERE / "no-restart.flag"
LOCK_PORT = 47999
CDP_PORT = 9222
WB_EXE = HOME / "AppData" / "Local" / "Programs" / "WorkBuddy" / "WorkBuddy.exe"
DD_SCRIPTS = HOME / "AppData" / "Local" / "Programs" / "WorkDaddy" / "scripts"
NODE = DD_SCRIPTS / "runtime" / "node" / "node.exe"
DEFAULT_THEME = "moon-silhouette"
# The 4-skin library. Anything outside this list is refused, so WorkDaddy's
# built-in themes (or a stray click in its panel) can never take the skin away.
SKINS = [
    ("moon-silhouette", "水月剪影"),
    ("gojo-inverse",    "反转五条悟"),
    ("neon-violet",     "紫发霓虹少女"),
    ("amber-eye",       "琥珀魔眼"),
]
SKIN_IDS = [x[0] for x in SKINS]
UI_JS = HERE / "skin-ui.js"
KEEP_ALL = HERE / "keep-all.flag"   # create this file to restore WorkDaddy's full panel
HIDE_WIN = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS

STATE = {
    "theme": DEFAULT_THEME,
    "last_apply": 0.0,
    "apply_count": 0,
    "wb_seen_no_cdp": 0.0,
    "restarts": [],
    "session": None,
    "bg_b64": "",
    "bg_theme": "",
    "injected_theme": "",
    "force_inject": False,
}


# --------------------------------------------------------------------------- log
def log(msg):
    line = "[%s] %s\n" % (time.strftime("%H:%M:%S"), msg)
    try:
        if LOG.exists() and LOG.stat().st_size > 1024 * 1024:
            LOG.replace(LOG.with_suffix(".old.log"))
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ------------------------------------------------------------------------ helper
def port_open(port, host="127.0.0.1", timeout=0.35):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def daemon_port():
    try:
        return int(json.loads((ROAM / "ui-port.json").read_text())["port"])
    except Exception:
        return 47832


def api(path, payload, timeout=40):
    token = (ROAM / ".api-token").read_text(encoding="utf-8").strip()
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (daemon_port(), path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-workdaddy-token": token},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body}


def wb_running():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq WorkBuddy.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=HIDE_WIN,
        ).stdout
        return "WorkBuddy.exe" in out
    except Exception:
        return False


def load_theme():
    try:
        t = THEME_FILE.read_text(encoding="utf-8-sig").strip()
        if t:
            t = t.splitlines()[0].strip()
            if t in SKIN_IDS:
                return t
    except Exception:
        pass
    return DEFAULT_THEME


def save_theme(theme):
    if theme in SKIN_IDS:
        THEME_FILE.write_text(theme, encoding="utf-8")


# ---------------------------------------------------------------- daemon control
def ensure_daemon():
    port = daemon_port()
    if port_open(port):
        return True
    if not NODE.exists() or not (DD_SCRIPTS / "daemon.js").exists():
        log("daemon binary missing, skip")
        return False
    log("daemon down -> starting (%s)" % NODE.name)
    try:
        env = dict(os.environ)
        # CRITICAL: without WBSWITCH_PROFILE the daemon refuses to claim a
        # bare-title WorkBuddy page on Windows (cdp-targets.js strict check),
        # so theme-apply fails with 'CDP 未连接' (HTTP 500).
        pid_file = DD_SCRIPTS / "profile-id.txt"
        profile = pid_file.read_text().strip() if pid_file.exists() else "workbuddy-cn"
        env["WBSWITCH_PROFILE"] = profile
        subprocess.Popen(
            [str(NODE), "--experimental-sqlite", str(DD_SCRIPTS / "daemon.js")],
            cwd=str(DD_SCRIPTS), env=env, creationflags=HIDE_WIN,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True,
        )
    except Exception as e:
        log("daemon start failed: %r" % e)
        return False
    for _ in range(24):
        time.sleep(0.5)
        if port_open(daemon_port()):
            log("daemon up on %d" % daemon_port())
            return True
    log("daemon did not come up")
    return False


def apply_theme(theme):
    now = time.time()
    if now - STATE["last_apply"] < 8:
        return False
    STATE["last_apply"] = now
    try:
        res = api("/api/theme-apply", {"id": theme})
        ok = bool(res.get("applied")) or bool(res.get("ok"))
        msg = "theme-apply %s -> %s" % (theme, str(res)[:120])
        if now - STATE.get("last_apply_log", 0) > 60 or not ok:
            log(msg)
            STATE["last_apply_log"] = now
        return ok
    except Exception as e:
        log("theme-apply failed: %r" % e)
        return False


# ------------------------------------------------------------------ page control
def page_target():
    try:
        return cdpmini.pick_page(cdpmini.list_targets(CDP_PORT, timeout=1.5))
    except Exception:
        return None


JS_STATE = (
    "(function(){"
    "var r=document.getElementById('root');"
    "var cs=r?getComputedStyle(r):null;"
    "var bg=cs?String(cs.backgroundImage):'';"
    "var st=document.getElementById('wbs-wallpaper-fix');"
    "var tid=document.documentElement.getAttribute('data-wbs-theme-id')||'';"
    "var want=document.documentElement.getAttribute('data-swx-want')||'';"
    "var ui=!!document.getElementById('swx-skin-fab');"
    "var trim=(window.__swxTrim===undefined)?null:!!window.__swxTrim;"
    "return JSON.stringify({root:!!r,bgOk:(bg.indexOf('data:image')>-1)&&!!st,"
    "wb:tid,bg:bg.slice(0,32),want:want,ui:ui,trim:trim});"
    "})()"
)


def bg_data_uri(theme):
    if STATE["bg_theme"] != theme or not STATE["bg_b64"]:
        p = ROAM / "themes" / theme / "background.webp"
        if not p.exists():
            log("wallpaper missing: %s" % p)
            return ""
        STATE["bg_b64"] = base64.b64encode(p.read_bytes()).decode()
        STATE["bg_theme"] = theme
    return STATE["bg_b64"]


def inject_wallpaper(sess, theme):
    b64 = bg_data_uri(theme)
    if not b64:
        return False
    expr = (
        "(function(){"
        "var old=document.getElementById('wbs-wallpaper-fix');"
        "if(old) old.remove();"
        "var st=document.createElement('style');"
        "st.id='wbs-wallpaper-fix';"
        "st.textContent='#root{background-image:"
        "linear-gradient(rgba(0,0,0,0.12),rgba(0,0,0,0.12)),"
        "url(\"data:image/webp;base64," + b64 + "\") !important;"
        "background-position:right center !important;"
        "background-size:cover !important;"
        "background-repeat:no-repeat !important;"
        "background-attachment:fixed !important;}"
        "#root .conversation-shell{"
        "background:rgba(16,17,20,0.55) !important;}';"
        "document.head.appendChild(st);"
        "var r=document.getElementById('root');"
        "return r?String(getComputedStyle(r).backgroundImage).indexOf('data:image')>-1:false;"
        "})()"
    )
    return bool(sess.eval(expr))


def inject_ui(sess):
    """Inject the trim-CSS + the skin switcher button/card (idempotent)."""
    tpl = UI_JS.read_text(encoding="utf-8")
    payload = json.dumps(
        [{"id": i, "name": n} for i, n in SKINS], ensure_ascii=False
    )
    walls = {}
    for tid, _ in SKINS:
        p = ROAM / "themes" / tid / "background.webp"
        if p.exists():
            walls[tid] = ("data:image/webp;base64,"
                          + base64.b64encode(p.read_bytes()).decode())
    try:
        token = (ROAM / ".api-token").read_text(encoding="utf-8").strip()
    except Exception:
        token = ""
    js = (tpl.replace("__THEMES_JSON__", payload)
             .replace("__WALLPAPERS__", json.dumps(walls))
             .replace("__API_TOKEN__", json.dumps(token))
             .replace("__API_PORT__", str(daemon_port()))
             .replace("__TRIM__", "false" if KEEP_ALL.exists() else "true"))
    return sess.eval(js)


def adopt_or_enforce(theme, cur):
    """Which theme should win when daemon state and theme.txt disagree?

    A change made *later* in the daemon (our in-page fallback button, or a
    click in WorkDaddy's own panel) is adopted instead of rolled back, as
    long as it is one of our 4 skins. A newer theme.txt (desktop switcher)
    still wins. Everything outside the library is refused.
    """
    if cur == theme or cur not in SKIN_IDS:
        return theme
    try:
        mt_theme = THEME_FILE.stat().st_mtime
        mt_daemon = (ROAM / "current-theme.json").stat().st_mtime
    except Exception:
        return theme
    if mt_daemon > mt_theme + 0.2:
        log("theme adopted from daemon -> %s" % cur)
        save_theme(cur)
        return cur
    return theme


def want_trim():
    return not KEEP_ALL.exists()


def connect(target):
    if STATE["session"] and STATE.get("target_id") == target.get("id"):
        return STATE["session"]
    if STATE["session"]:
        try:
            STATE["session"].close()
        except Exception:
            pass
    sess = cdpmini.Session(target["webSocketDebuggerUrl"])
    STATE["session"] = sess
    STATE["target_id"] = target.get("id")
    STATE["need_inject"] = True
    log("attached to page %s" % target.get("id", "")[:8])
    return sess


def reset_session():
    if STATE["session"]:
        try:
            STATE["session"].close()
        except Exception:
            pass
    STATE["session"] = None
    STATE["target_id"] = None


# --------------------------------------------------------------- relaunch logic
def maybe_relaunch_wb():
    """WorkBuddy is alive but has no CDP port: relaunch it once, right after
    it was opened, so the skin can attach."""
    if NO_RESTART.exists():
        return
    now = time.time()
    if not STATE["wb_seen_no_cdp"]:
        STATE["wb_seen_no_cdp"] = now
        log("WorkBuddy running without CDP - watching for 45s")
        return
    if now - STATE["wb_seen_no_cdp"] > 45:
        return
    recent = [t for t in STATE["restarts"] if now - t < 3600]
    STATE["restarts"] = recent
    if len(recent) >= 2:
        return
    if not WB_EXE.exists():
        return
    log("relaunching WorkBuddy with CDP env")
    STATE["restarts"].append(now)
    STATE["wb_seen_no_cdp"] = 0
    try:
        subprocess.run(["taskkill", "/IM", "WorkBuddy.exe", "/F"],
                       capture_output=True, creationflags=HIDE_WIN, timeout=20)
    except Exception as e:
        log("taskkill failed: %r" % e)
    time.sleep(2.0)
    env = dict(os.environ)
    env["WORKBUDDY_REMOTE_DEBUGGING_PORT"] = str(CDP_PORT)
    try:
        subprocess.Popen([str(WB_EXE)], env=env, creationflags=HIDE_WIN,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
        log("WorkBuddy relaunched")
    except Exception as e:
        log("relaunch failed: %r" % e)


# ----------------------------------------------------------------------- main loop
def tick(theme):
    if not ensure_daemon():
        return
    target = page_target()
    if target is None:
        reset_session()
        if wb_running():
            maybe_relaunch_wb()
        else:
            STATE["wb_seen_no_cdp"] = 0
        return
    STATE["wb_seen_no_cdp"] = 0
    try:
        sess = connect(target)
        st = json.loads(sess.eval(JS_STATE) or "{}")
    except Exception as e:
        log("page eval failed: %r" % e)
        reset_session()
        return
    if not st.get("root"):
        return

    # 1) UI -> keeper channel. The button only sets a DOM attribute; the
    #    keeper does the real theme-apply, so no fetch/token/CORS is involved.
    want = st.get("want") or ""
    if want:
        try:
            sess.eval("document.documentElement.removeAttribute('data-swx-want')")
        except Exception:
            pass
        if want in SKIN_IDS and want != theme:
            log("UI switch -> %s" % want)
            save_theme(want)
            theme = want
            STATE["theme"] = theme
            STATE["last_apply"] = 0.0       # bypass the 8s apply throttle
            STATE["force_inject"] = True

    # 2) keep the trimmed panel + skin switcher alive across page reloads
    if (STATE.get("need_inject") or not st.get("ui")
            or st.get("trim") is not want_trim()):
        try:
            inject_ui(sess)
        except Exception as e:
            log("skin UI inject failed: %r" % e)

    # 3) theme consistency: both the daemon state and the page marker must
    #    match the chosen skin, otherwise re-apply and re-inject the wallpaper.
    try:
        cur = json.loads((ROAM / "current-theme.json").read_text()).get("id")
    except Exception:
        cur = None
    theme = adopt_or_enforce(theme, cur)
    STATE["theme"] = theme
    marker = st.get("wb") or ""
    if cur != theme or marker != theme:
        log("theme drift: daemon=%s page=%s want=%s" % (cur, marker, theme))
        apply_theme(theme)
        STATE["force_inject"] = True
        return

    # 4) wallpaper (WorkDaddy's own `background` shorthand computes to none)
    if (STATE.get("need_inject") or STATE.get("force_inject")
            or not st.get("bgOk") or STATE.get("injected_theme") != theme):
        STATE["need_inject"] = False
        STATE["force_inject"] = False
        try:
            if inject_wallpaper(sess, theme):
                STATE["injected_theme"] = theme
                log("wallpaper set (%s)" % theme)
        except Exception as e:
            log("inject failed: %r" % e)
            reset_session()


def main():
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        # pythonw.exe has no stdout; never print here.
        return
    theme_override = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if theme_override in SKIN_IDS:
        THEME_FILE.write_text(theme_override, encoding="utf-8")
    log("=== skin keeper started (pid %d) ===" % os.getpid())
    while True:
        try:
            theme = load_theme()
            STATE["theme"] = theme
            tick(theme)
        except Exception as e:
            log("tick error: %r" % e)
        time.sleep(2.0)


if __name__ == "__main__":
    main()

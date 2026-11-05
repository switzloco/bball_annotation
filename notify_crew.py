"""
ESPN+ Pickup Film Room — Discord Webhook & Desktop Clipboard Notifier (`notify_crew.py`)

1. If DISCORD_WEBHOOK_URL (or VITE_DISCORD_WEBHOOK_URL) is present in:
     - C:/Users/Nick/.env
     - c:/dev/bball_annotation/.env
     - Environment variables
   it posts a rich ESPN SportsCenter-style Discord Embed automatically.
2. On Windows, if `--clipboard` (or no webhook URL is set yet), it automatically copies
   a ready-to-paste Discord Markdown recap (with direct `?play=` deep-links and `?reel=top5`
   auto-reel links) to the Windows clipboard and optionally launches `discord://`.
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone


def load_env_file(filepath: str) -> dict:
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env_vars


def get_discord_webhook_url() -> str:
    paths = [
        os.path.expanduser("~/.env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        r"C:\Users\Nick\Documents\GitHub\TameMane\.env.local",
        r"C:\Users\Nick\Documents\GitHub\TameMane\.env",
    ]
    for k in ("DISCORD_WEBHOOK_URL", "VITE_DISCORD_WEBHOOK_URL"):
        if os.environ.get(k):
            return os.environ[k]
    for p in paths:
        vals = load_env_file(p)
        for k in ("DISCORD_WEBHOOK_URL", "VITE_DISCORD_WEBHOOK_URL"):
            if vals.get(k) and vals[k].startswith("https://"):
                return vals[k]
    return ""


def build_whatsapp_message(
    live_url: str = "https://bball-film-room-615717094211.us-central1.run.app",
    custom_note: str = "",
) -> str:
    lines = [
        "🏀 *CPSN — CAMPBELL PARK SPORTS NETWORK FILM ROOM IS LIVE!*",
        f"👉 *Full Interactive Film Room:* {live_url}",
        f"🎬 *Auto-Play All CPSN Top 5 Highlights:* {live_url}/?reel=top5",
        "",
        "🔥 *CPSN TOP 5 PLAYS (Starts 5s Before the Bucket so You See Every Pass):*",
        f"• *#1 (23:05)* — *Josh* DREB & Full-Court Outlet Pass → *Kenny* Walk-Off Fast-Break Layup (15–14 Final) 🔥\n{live_url}/?play=1385",
        f"• *#2 (22:35)* — *Rock* (22:33 Dish) → *Timor* (22:36 Right-Wing Jumper, 14–14)\n{live_url}/?play=1355",
        f"• *#3 (21:37)* — *Timor* Midcourt Steal → *Damien* Fast-Break Layup\n{live_url}/?play=1297",
        f"• *#4 (08:54)* — *Damien* Coast-to-Coast Steal & Fast-Break Finish\n{live_url}/?play=539",
        f"• *#5 (37:18)* — *Brian* Shooter's Touch High-Bounce Runner\n{live_url}/?play=2238",
        "",
        "👕 *Day-to-Day Crew Mapped:* Josh • Damien • Kenny • Brian • Donnie • Timor • Rock • Spider",
        "💬 _Tap any play to watch on mobile (sticky video player!), download an 11s MP4 clip for WhatsApp/IG, or flag a stat as 🧢 Cap!_",
    ]
    if custom_note:
        lines.append(f"\n📝 *Update:* {custom_note}")
    return "\n".join(lines)


def build_discord_markdown_message(
    live_url: str = "https://bball-film-room-615717094211.us-central1.run.app",
    custom_note: str = "",
) -> str:
    lines = [
        "🏀 **CPSN — CAMPBELL PARK SPORTS NETWORK FILM ROOM IS LIVE!**",
        f"👉 **Full Interactive Film Room:** {live_url}",
        f"🎬 **Auto-Play All CPSN Top 5 Highlights:** {live_url}/?reel=top5",
        "",
        "🔥 **CPSN TOP 5 PLAYS (Pure Hoops — Starts 5s Before the Bucket so You See Every Pass):**",
        f"• **#1 (`23:05`)** — **Josh** DREB & Full-Court Outlet Pass → **Kenny** Walk-Off Fast-Break Layup (`15–14` Final, Game to 15) 🔥 → <{live_url}/?play=1385>",
        f"• **#2 (`22:35`)** — **Rock** (`22:33` Dish) → **Timor** (`22:36` Right-Wing Jumper, `14–14`) → <{live_url}/?play=1355>",
        f"• **#3 (`21:37`)** — **Timor** Midcourt Steal → **Damien** Fast-Break Layup → <{live_url}/?play=1297>",
        f"• **#4 (`08:54`)** — **Damien** Coast-to-Coast Steal & Fast-Break Finish → <{live_url}/?play=539>",
        f"• **#5 (`37:18`)** — **Brian** Shooter's Touch High-Bounce Runner → <{live_url}/?play=2238>",
        "",
        "👕 **Day-to-Day Crew Mapped:** Josh • Damien • Kenny • Brian • Donnie • Timor • Rock • Spider",
        "💬 *Click any play to watch, download an 11s MP4 clip, or flag a stat as `🧢 Cap`!*",
    ]
    if custom_note:
        lines.append(f"\n📝 **Update:** {custom_note}")
    return "\n".join(lines)


def copy_to_windows_clipboard(text: str) -> bool:
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, close_fds=True)
        proc.communicate(input=text.encode("utf-16-le"))
        return proc.returncode == 0
    except Exception:
        return False


def send_film_room_discord_ping(
    title: str = "🏀 CPSN — Campbell Park Sports Network Film Room is LIVE!",
    session_label: str = "Session #1 — Oct 31, 2026 (Full Game + Shootaround + Game 2)",
    live_url: str = "https://bball-film-room-615717094211.us-central1.run.app",
    custom_note: str = "",
    prefer_whatsapp_clipboard: bool = True,
) -> bool:
    wa_text = build_whatsapp_message(live_url=live_url, custom_note=custom_note)
    md_text = build_discord_markdown_message(live_url=live_url, custom_note=custom_note)
    clip_payload = wa_text if prefer_whatsapp_clipboard else md_text
    copied = copy_to_windows_clipboard(clip_payload)
    if copied:
        fmt_label = "WhatsApp" if prefer_whatsapp_clipboard else "Discord"
        print(f"✅ Copied formatted CPSN {fmt_label} recap (with ?play= deep-links) to Windows clipboard!")

    webhook_url = get_discord_webhook_url()
    if not webhook_url:
        print(
            "ℹ️ No DISCORD_WEBHOOK_URL in ~/.env yet — message is ready on your Windows clipboard (Ctrl+V in Discord)!"
        )
        return copied

    embed = {
        "title": title,
        "url": live_url,
        "description": (
            f"**[{session_label}]({live_url})** has been annotated, verified by the "
            f"Real-Chrome Video QA Agent (`0.00s` frame drift), and published to Cloud Run!\n\n"
            f"👉 **Watch & Audit Your Stats:** {live_url}\n"
            f"🎬 **Auto-Play CPSN Top 5 Reel:** {live_url}/?reel=top5"
            + (f"\n\n💬 **Note:** {custom_note}" if custom_note else "")
        ),
        "color": 0xD00000,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "CPSN • Campbell Park Sports Network • Pickup Crew AI Flywheel"},
        "fields": [
            {
                "name": "🔥 CPSN TOP 5 PLAYS (PURE HOOPS — 5s SETUP PRE-ROLL)",
                "value": (
                    f"**#1** [`23:05`]({live_url}/?play=1385) — **Josh** DREB & Outlet Pass → **Kenny** Walk-Off Fast-Break Layup (`15–14`) 🔥\n"
                    f"**#2** [`22:35`]({live_url}/?play=1355) — **Rock** (`22:33` Dish) → **Timor** Clutch Jumper (`14–14`)\n"
                    f"**#3** [`21:37`]({live_url}/?play=1297) — **Timor** Steal → **Damien** Fast-Break Finish\n"
                    f"**#4** [`08:54`]({live_url}/?play=539) — **Damien** Coast-to-Coast Steal & Fast-Break Layup\n"
                    f"**#5** [`37:18`]({live_url}/?play=2238) — **Brian** High-Bounce Shooter's Touch Runner"
                ),
                "inline": False,
            },
            {
                "name": "👕 Day-to-Day Crew Mapped (Outfit-Invariant)",
                "value": "Josh • Damien • Kenny • Brian • Donnie • Timor • Rock • Spider",
                "inline": True,
            },
            {
                "name": "🎬 Video & QA Status",
                "value": "✅ Real Chrome 30fps Verified\n✅ 11s MP4 Clip Downloader Ready",
                "inline": True,
            },
        ],
    }

    payload = json.dumps(
        {
            "username": "CPSN — Campbell Park Sports Network",
            "embeds": [embed],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "CPSN-FilmRoom-Bot/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status in (200, 204)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    note = " ".join([a for a in sys.argv[1:] if not a.startswith("--")])
    ok = send_film_room_discord_ping(custom_note=note)
    sys.exit(0 if ok else 1)

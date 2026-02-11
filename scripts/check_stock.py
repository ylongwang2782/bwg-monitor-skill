#!/usr/bin/env python3
"""
BWG Stock Monitor - OpenClaw Skill Edition
搬瓦工库存监控 - OpenClaw Skill 精简版

Pure Python 3 stdlib, no external dependencies.
Output: JSON to stdout for OpenClaw agent consumption.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
STATE_FILE = SCRIPT_DIR / ".state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def beijing_now():
    return datetime.now(timezone(timedelta(hours=8)))


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_stock(pid, check_url_tpl):
    """Check if a product is in stock by fetching the cart page."""
    url = check_url_tpl.format(pid=pid)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if "Out of Stock" in html:
                return False
            if "Annually" in html or "Monthly" in html or "Order Summary" in html:
                return True
            return False
    except Exception as e:
        print(f"Error checking PID {pid}: {e}", file=sys.stderr)
        return None


def main():
    cfg = load_config()
    state = load_state()
    now_str = beijing_now().strftime("%Y-%m-%d %H:%M:%S")

    products = cfg["products"]
    check_url = cfg.get("check_url", "https://bwh81.net/cart.php?a=add&pid={pid}")
    buy_url = cfg.get("buy_url", "https://bwh81.net/cart.php?a=add&pid={pid}")

    results = []
    changed = []
    in_stock_list = []

    for p in products:
        pid = p["pid"]
        stock = check_stock(pid, check_url)

        prev = state.get(str(pid), {}).get("in_stock")
        status_changed = prev is not None and prev != stock and stock is not None

        entry = {
            "pid": pid,
            "name": p["name"],
            "price": p["price"],
            "desc": p.get("desc", ""),
            "in_stock": stock,
            "url": buy_url.format(pid=pid),
        }
        results.append(entry)

        if stock is True:
            in_stock_list.append(entry)

        if status_changed:
            entry_changed = dict(entry)
            entry_changed["prev_stock"] = prev
            changed.append(entry_changed)

        # Update state
        state[str(pid)] = {
            "in_stock": stock,
            "checked_at": now_str,
        }

        time.sleep(1)  # polite delay

    save_state(state)

    # Build text summary
    lines = [f"🖥️ BWG Stock Check — {now_str}", ""]
    for r in results:
        icon = "🟢" if r["in_stock"] else ("🔴" if r["in_stock"] is False else "⚠️")
        status = "In Stock ✅" if r["in_stock"] else ("Out of Stock" if r["in_stock"] is False else "Unknown")
        lines.append(f"{icon} ${r['price']}/yr — {r['name']} ({r['desc']}) — {status}")
        if r["in_stock"]:
            lines.append(f"   🔗 {r['url']}")
    lines.append("")

    if changed:
        lines.append("📢 Status changes:")
        for c in changed:
            prev_s = "In Stock" if c["prev_stock"] else "Out of Stock"
            now_s = "In Stock ✅" if c["in_stock"] else "Out of Stock"
            lines.append(f"   {c['name']} ${c['price']}: {prev_s} → {now_s}")

    if in_stock_list:
        lines.append(f"\n🎉 {len(in_stock_list)} plan(s) IN STOCK! Buy now before they're gone!")

    text = "\n".join(lines)

    output = {
        "timestamp": now_str,
        "products": results,
        "in_stock_count": len(in_stock_list),
        "changed": changed,
        "text": text,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

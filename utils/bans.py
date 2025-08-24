import os
import json
import time

BANS_FILE = 'bans.json'

def load_bans():
    if not os.path.exists(BANS_FILE):
        return {}
    with open(BANS_FILE, 'r') as f:
        return json.load(f)

def save_bans(data):
    with open(BANS_FILE, 'w') as f:
        json.dump(data, f)

def is_banned(user_id):
    """
    Check if a user is currently banned (within 24h window).
    If 24h over, auto-reset their ban.
    Returns True if banned, False otherwise.
    """
    bans = load_bans()
    u = str(user_id)
    if u in bans:
        ban_time = bans[u].get("ban_time", 0)
        if ban_time > 0:
            if time.time() - ban_time >= 86400:
                # 24h passed, reset ban
                bans[u]["ban_time"] = 0
                bans[u]["warnings"] = 0
                save_bans(bans)
                return False
            else:
                return True
    return False

def add_warning(user_id):
    """
    Add a warning for user. If warnings reach 5, ban for 24h.
    Returns (warnings_count, ban_time).
    """
    bans = load_bans()
    u = str(user_id)
    if u not in bans:
        bans[u] = {"warnings": 0, "ban_time": 0}
    bans[u]["warnings"] += 1
    if bans[u]["warnings"] >= 5:
        bans[u]["ban_time"] = int(time.time())
        bans[u]["warnings"] = 5
    save_bans(bans)
    return bans[u]["warnings"], bans[u]["ban_time"]

def reset_warning(user_id):
    """
    Reset warnings and ban for user (admin use or 24h auto-reset).
    """
    bans = load_bans()
    u = str(user_id)
    if u in bans:
        bans[u] = {"warnings": 0, "ban_time": 0}
        save_bans(bans)

def get_warning_count(user_id):
    """
    Return current warning count for user, or 0 if none.
    """
    bans = load_bans()
    u = str(user_id)
    return bans.get(u, {}).get("warnings", 0)

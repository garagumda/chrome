#!/usr/bin/env python3
# continuous_history_watcher.py

import os
import shutil
import sqlite3
import time
import sys
import socket
import json
import http.client
from datetime import datetime, timedelta, timezone

# ---------------- CONFIG ----------------
RECEIVER_IP = "127.0.0.1"
RECEIVER_PORT = 5000
KEYWORDS_FILE = "keywords.txt"
POLL_INTERVAL = 2
LOOKBACK_DAYS = 7
HISTORY_SNAPSHOT = "chrome-history-watcher.db"
MAX_RETRY_COPY = 3
COPY_RETRY_DELAY = 1.0
SEND_RETRY = 2
SEND_RETRY_DELAY = 1.0
# ----------------------------------------

def get_username():
    try:
        return os.getlogin()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def possible_chrome_history_paths():
    candidates = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        user = os.environ.get("USERPROFILE")
        if local:
            candidates.append(os.path.join(local, "Google", "Chrome", "User Data", "Default", "History"))
        if user:
            candidates.append(os.path.join(user, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "History"))
        if local:
            candidates.append(os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "History"))
    else:
        home = os.path.expanduser("~")
        candidates.append(os.path.join(home, ".config", "google-chrome", "Default", "History"))
        candidates.append(os.path.join(home, ".config", "chromium", "Default", "History"))
        candidates.append(os.path.join(home, "Library", "Application Support", "Google", "Chrome", "Default", "History"))
    return candidates

def find_existing_history_path():
    for p in possible_chrome_history_paths():
        if p and os.path.exists(p):
            return p
    return None

def copy_with_retries(src, dst):
    last_exc = None
    for _ in range(MAX_RETRY_COPY):
        try:
            shutil.copy2(src, dst)
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                return
        except Exception as e:
            last_exc = e
            time.sleep(COPY_RETRY_DELAY)
    raise RuntimeError(f"Failed to copy history file: {last_exc}")

def datetime_to_webkit_us(dt):
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=None).astimezone(timezone.utc)
    delta = dt_utc - epoch
    return int(delta.total_seconds() * 1_000_000) + dt_utc.microsecond

def webkit_us_to_local_dt(webkit_us):
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    seconds, microseconds = divmod(int(webkit_us), 1_000_000)
    dt_utc = epoch + timedelta(seconds=seconds, microseconds=microseconds)
    return dt_utc.astimezone().replace(tzinfo=None)

def load_keywords(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip()]

def query_history(db_path, after_us):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = "SELECT id, url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time ASC;"
    try:
        cursor.execute(sql, (after_us,))
        return cursor.fetchall()
    finally:
        conn.close()

def send_to_server(payload):
    body = json.dumps(payload, ensure_ascii=False)
    for _ in range(SEND_RETRY):
        try:
            conn = http.client.HTTPConnection(RECEIVER_IP, RECEIVER_PORT, timeout=5)
            conn.request("POST", "/", body, {"Content-Type": "application/json"})
            resp = conn.getresponse()
            conn.close()
            return resp.status == 200
        except:
            time.sleep(SEND_RETRY_DELAY)
    return False

def main_loop():
    username = get_username()
    source_ip = get_local_ip()
    history_file = find_existing_history_path()
    if not history_file:
        print("Chrome history not found")
        return

    keywords = load_keywords(KEYWORDS_FILE)
    if not keywords:
        print("No keywords in", KEYWORDS_FILE)
        return

    last_check_us = datetime_to_webkit_us(datetime.now() - timedelta(days=LOOKBACK_DAYS))
    seen_ids = {}

    print(f"Monitoring continuously for keywords: {keywords}")

    while True:
        try:
            copy_with_retries(history_file, HISTORY_SNAPSHOT)
        except Exception as e:
            print("Copy failed:", e)
            time.sleep(POLL_INTERVAL)
            continue

        matches = query_history(HISTORY_SNAPSHOT, last_check_us)
        max_last_visit = last_check_us

        for rid, url, title, last_visit in matches:
            if rid in seen_ids and seen_ids[rid] >= last_visit:
                continue

            title_l = (title or "").lower()
            url_l = (url or "").lower()
            matched_kw = [kw for kw in keywords if kw in title_l or kw in url_l]
            if not matched_kw:
                continue

            last_visit_iso = webkit_us_to_local_dt(last_visit).isoformat()
            payload = {
                "username": username,
                "source_ip": source_ip,
                "last_visit": last_visit_iso,
                "url": url,
                "title": title,
                "matched_keywords": matched_kw
            }

            ok = send_to_server(payload)
            print("[SENT]" if ok else "[FAILED]", payload)

            seen_ids[rid] = last_visit
            if last_visit > max_last_visit:
                max_last_visit = last_visit

        last_check_us = max_last_visit + 1
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        while True:
            try:
                main_loop()
            except KeyboardInterrupt:
                print("Exiting...")
                break
            except Exception as e:
                print("Error:", e)
                time.sleep(POLL_INTERVAL)
                continue
    except Exception as final_ex:
        print("Fatal error:", final_ex)
        sys.exit(1)

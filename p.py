#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome History-y barlaýar — "apple" sözi anyklansa konsola gözleg wagtyny, IP/username/URL çykarýar we
desktop duýduryş görkezer. Chrome brauzerini açmaga gerek däl.
"""

import os
import sys
import time
import shutil
import sqlite3
import socket
import uuid
import getpass
from pathlib import Path
from plyer import notification
from typing import List, Tuple
from datetime import datetime

# --------- Config ----------
POLL_SECONDS = 2.0        # History faýlyny näçe wagtyň aralygy bilen barlar
SEARCH_WORD = "apple"     # gözlenjek söz (kiçi/uly harplara üns edýäris)
# ---------------------------

def chrome_history_paths() -> List[Path]:
    """Platforma görä mümkin bolan Chrome History faýllarynyň sanawy."""
    paths = []
    home = Path.home()
    if sys.platform.startswith("win"):
        local = Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local"))
        paths += [
            local / "Google" / "Chrome" / "User Data" / "Default" / "History",
            local / "Chromium" / "User Data" / "Default" / "History",
        ]
    elif sys.platform == "darwin":
        paths += [
            home / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History",
            home / "Library" / "Application Support" / "Chromium" / "Default" / "History",
        ]
    else:  # linux / other unix
        paths += [
            home / ".config" / "google-chrome" / "Default" / "History",
            home / ".config" / "chromium" / "Default" / "History",
            home / ".config" / "brave" / "Default" / "History",
        ]
    return [p for p in paths if p.exists()]

def copy_history(src: Path, dst: Path):
    """History faýlynyň nusgasyny döret (Chrome faýlyny okamagyň öňüni alýar)."""
    shutil.copy2(src, dst)

def get_primary_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "N/A"

def get_all_ips() -> List[str]:
    ips = set()
    try:
        hostname = socket.gethostname()
        # IPv4 adreslerini al (IPv6 görkezme)
        for res in socket.getaddrinfo(hostname, None):
            addr = res[4][0]
            if ':' not in addr:  # Yalňyş ýagdaýda diňe IPv4'yi goş
                ips.add(f"IPv4: {addr}")
    except Exception:
        pass
    primary = get_primary_ip()
    if primary and primary != "N/A":
        ips.add(f"IPv4: {primary}")  # IP-ä IPv4 görnüşde goşulýar
    if not ips:
        return ["N/A"]
    return list(ips)

def get_username() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "N/A"

def notify(title: str, message: str, timeout: int = 6):
    try:
        # Gysgaça maglumat döretmek
        MAX_TITLE_LEN = 100
        MAX_MSG_LEN = 256
        
        short_title = title[:MAX_TITLE_LEN]  # Title gysgaça
        short_message = message[:MAX_MSG_LEN]  # Mesaj gysgaça

        notification.notify(title=short_title, message=short_message, timeout=timeout)
    except Exception as e:
        print("Duýduryş berilmän bildiriş:", e)

# ---------- History query functions ----------
def query_search_terms(conn: sqlite3.Connection, word: str) -> List[Tuple]:
    """search_terms tablisasy bar bolsa, ondan termleri getir (term, url_id mumkin)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT term, url_id FROM search_terms WHERE term LIKE ?", (f"%{word}%",))
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []

def query_urls_for_search(conn: sqlite3.Connection, word: str) -> List[Tuple]:
    """urls tablisasyndan url/title we id alyp, word barlaryny tap."""
    cur = conn.cursor()
    like_word = f"%{word}%"
    try:
        cur.execute(
            "SELECT id, url, title, last_visit_time FROM urls WHERE url LIKE ? OR title LIKE ?",
            (f"%q={word}%", like_word)
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                "SELECT id, url, title, last_visit_time FROM urls WHERE url LIKE ? OR title LIKE ?",
                (like_word, like_word)
            )
            rows = cur.fetchall()
        return rows
    except sqlite3.OperationalError:
        return []

def get_url_by_id(conn: sqlite3.Connection, url_id: int) -> Tuple:
    """urls tablisasyndan id bilen (id, url, title, last_visit_time) almaga synanyş."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, url, title, last_visit_time FROM urls WHERE id = ?", (url_id,))
        return cur.fetchone()
    except sqlite3.OperationalError:
        return None

def convert_timestamp_to_date(timestamp: int) -> str:
    """UNIX timestamp (epoch) sanawyny data formatyna geçirýär."""
    return datetime.utcfromtimestamp(timestamp / 1000000 - 11644473600).strftime('%Y-%m-%d %H:%M:%S')

# ---------- Main watcher ----------
def main():
    print("Chrome History gözegçiligi başlandy. (brauzeri açmaga gerek däl)")
    candidates = chrome_history_paths()
    if not candidates:
        print("Chrome History faýly tapylmady. Chrome profil ýollaryny barlaň.")
        return

    history_path = candidates[0]
    print("Ulanylýan History faýly:", history_path)

    tmp_dir = Path.cwd() / "tmp_chrome_history"
    tmp_dir.mkdir(exist_ok=True)
    copy_path = tmp_dir / "History_copy"
    seen_keys = set()

    try:
        while True:
            try:
                # Nusga döret
                copy_history(history_path, copy_path)
                conn = sqlite3.connect(str(copy_path))

                found_entries = []  # list of dicts with info to display

                # 1) search_terms tablisasy bar bolsa ondan al
                st_rows = query_search_terms(conn, SEARCH_WORD)
                if st_rows:
                    for term, url_id in st_rows:
                        key = ("term", term, url_id)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        row = get_url_by_id(conn, url_id)
                        if row:
                            _, url, title, last_visit = row
                        else:
                            url = f"(url_id={url_id} not found)"
                            title = ""
                            last_visit = None
                        found_entries.append({"source": "search_terms", "term": term, "url": url, "title": title, "last_visit": last_visit})

                # 2) urls tablisasyndan göwnejaý söz bilen tap (fallback)
                url_rows = query_urls_for_search(conn, SEARCH_WORD)
                for rid, url, title, last_visit in url_rows:
                    key = ("url", rid)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    found_entries.append({"source": "urls", "url_id": rid, "url": url, "title": title, "last_visit": last_visit})

                conn.close()

                if found_entries:
                    username = get_username()
                    ips = get_all_ips()
                    ips_str = ", ".join(ips)
                    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                    print(f"[{stamp}] '{SEARCH_WORD}' bilen baglanyşykly täze ýazgy tapyldy:")
                    print("Ulanyjy:", username)
                    print("IP(ler):", ips_str)
                    print("Tapylan URL(ler):")
                    # Konsolda format: title öň, url soň
                    for i, ent in enumerate(found_entries, start=1):
                        title = ent.get("title") or "(Title tapylmady)"
                        url = ent.get("url") or "(URL tapylmady)"
                        last_visit = ent.get("last_visit")
                        if last_visit:
                            formatted_time = convert_timestamp_to_date(last_visit)
                            print(f"{i}. Title: {title}")
                            print(f"   URL: {url}")
                            print(f"   Gözleg wagty: {formatted_time}")
                        else:
                            print(f"{i}. Title: {title}")
                            print(f"   URL: {url}")
                    print("-" * 60)

                    # Duýduryş üçin gysgaltma
                    first_titles = [e.get("title", "") for e in found_entries][:2]
                    first_urls = [e.get("url", "") for e in found_entries][:2]
                    titles_short = "; ".join(t if len(t) <= 80 else t[:77] + "..." for t in first_titles)
                    urls_short = "; ".join(u if len(u) <= 80 else u[:77] + "..." for u in first_urls)
                    notif_msg = f"Ulanyjy: {username}\nIP: {ips_str}\nGözleg wagty: {formatted_time}\nTitle: {titles_short}\nURL: {urls_short}"
                    notify(f"Gözleg: '{SEARCH_WORD}' anyklandy", notif_msg, timeout=8)

            except Exception as e:
                print("Ýalňyşlyk barlanan wagty:", e)
            finally:
                time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("Programm togtadyldy (Ctrl+C).")
    finally:
        try:
            if copy_path.exists():
                copy_path.unlink()
        except Exception:
            pass

if __name__ == "__main__":
    main()

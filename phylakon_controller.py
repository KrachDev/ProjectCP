"""
⚡ PHYLAKON: LEGEND REBORN — MASTER COMMAND CENTER
Companion Desktop Orchestrator & Live ASP.NET Core Session Monitor

Directly interfaces with the Phylakon Extension (ws://127.0.0.1:8765/)
Features:
- Authentic .AspNetCore.Session Expiry HUD & Real-time Countdown
- Open Appointment Slot Radar & Instant Audio/Visual Alerts
- Multi-Region Batch Presets (Spain & Portugal)
- 1-Click Multi-Profile Chrome Grid Launcher with auto-loaded Phylakon Extension
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import winsound
except ImportError:
    winsound = None

# GUI Toolkit: CustomTkinter with Tkinter fallback
try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_CTK = False

from refresh_server import RefreshServer, ConnectedTab

PHYLAKON_DIR = r"C:\PhylakonExtension" if os.path.exists(r"C:\PhylakonExtension\manifest.json") else (r"C:\Phylakon" if os.path.exists(r"C:\Phylakon\manifest.json") else r"C:\Users\krach\Documents\BLS Project\Phylakon")

# Theme Colors
BG_DARK = "#0B0E14"
SIDEBAR_BG = "#121622"
CARD_BG = "#1A2030"
CARD_HOVER = "#242C42"
BORDER_COLOR = "#232A3E"
ACCENT_CYAN = "#06B6D4"
ACCENT_BLUE = "#3B82F6"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"
TEXT_PRIMARY = "#F8FAFC"
TEXT_MUTED = "#64748B"

PRESETS = {
    "Spain": {
        "cities": ["Casablanca", "Nador", "Tetouan", "Tangier", "Rabat", "Agadir"],
        "categories": ["Normal", "Premium", "Prime Time"],
        "types": [
            "Schengen Visa", "National Visa", "Student Visa", "Work Visa",
            "Casa 1", "Casa 2", "Family Reunification Visa"
        ],
        "members": ["1", "2", "3", "4"]
    },
    "Portugal": {
        "cities": ["Casablanca", "Rabat"],
        "categories": ["Normal", "Premium", "Prime Time"],
        "types": [
            "Short Stay Visa", "Any other category of Long-Stay visa", "Highly Qualified Activity"
        ],
        "members": ["1", "2", "3", "4"]
    }
}


class PhylakonControllerApp(ctk.CTk if HAS_CTK else tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("⚡ Phylakon: Legend Reborn — Master Commander")
        self.geometry("1100x720")
        self.minsize(960, 640)

        if HAS_CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.configure(fg_color=BG_DARK)

        # Server initialization
        self.server = RefreshServer(host="127.0.0.1", port=8765)
        self.server_thread = threading.Thread(target=self.server.start, daemon=True)
        self.server_thread.start()

        self.tab_cards: Dict[str, Any] = {}
        self.active_alert_slots = []
        self.current_region = "Spain"

        self._build_ui()
        self._start_poll_loop()

    def _build_ui(self):
        # 1. Top Header Bar
        header = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, height=60, corner_radius=0)
        header.pack(fill="x", side="top")

        lbl_title = ctk.CTkLabel(
            header,
            text="⚡ PHYLAKON : LEGEND REBORN",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#38BDF8"
        )
        lbl_title.pack(side="left", padx=(20, 10), pady=12)

        lbl_sub = ctk.CTkLabel(
            header,
            text="ASP.NET Core Session HUD • Slot Radar • Grid Orchestrator",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED
        )
        lbl_sub.pack(side="left", pady=16)

        ext_status_text = "🟢 Extension Linked" if os.path.isdir(PHYLAKON_DIR) else "🔴 Extension Not Found"
        lbl_ext = ctk.CTkLabel(
            header,
            text=ext_status_text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_SUCCESS if os.path.isdir(PHYLAKON_DIR) else COLOR_DANGER
        )
        lbl_ext.pack(side="right", padx=20)

        self.lbl_server_badge = ctk.CTkLabel(
            header,
            text="🟢 Server: ws://127.0.0.1:8765",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_SUCCESS
        )
        self.lbl_server_badge.pack(side="right", padx=(0, 15))

        # 2. Slot Discovery Alert Banner (Radar)
        self.banner_alert = ctk.CTkFrame(self, fg_color="#78350F", border_color="#F59E0B", border_width=1, corner_radius=8)
        self.lbl_alert_text = ctk.CTkLabel(
            self.banner_alert,
            text="🚨 APPOINTMENT SLOTS DISCOVERED! Action Required.",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FEF08A"
        )
        self.lbl_alert_text.pack(side="left", padx=20, pady=10)

        btn_dismiss = ctk.CTkButton(
            self.banner_alert,
            text="Dismiss",
            width=80,
            height=28,
            fg_color="#B45309",
            hover_color="#D97706",
            command=self._dismiss_alert
        )
        btn_dismiss.pack(side="right", padx=15, pady=10)

        # 3. Main Workspace Area (Left: Tabs HUD, Right: Batch Config & Launcher)
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=15, pady=10)
        workspace.grid_columnconfigure(0, weight=6)
        workspace.grid_columnconfigure(1, weight=4)
        workspace.grid_rowconfigure(0, weight=1)

        # Left Column: Connected Tabs & Session Expiry HUD
        left_box = ctk.CTkFrame(workspace, fg_color=SIDEBAR_BG, corner_radius=10, border_color=BORDER_COLOR, border_width=1)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_box.grid_rowconfigure(1, weight=1)
        left_box.grid_columnconfigure(0, weight=1)

        left_header = ctk.CTkFrame(left_box, fg_color="transparent", height=42)
        left_header.grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        self.lbl_hud_title = ctk.CTkLabel(
            left_header,
            text="Connected Chrome Instances & Session Timers (0)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.lbl_hud_title.pack(side="left")

        btn_refresh_all = ctk.CTkButton(
            left_header,
            text="🔄 Refresh All",
            width=90,
            height=28,
            fg_color=ACCENT_BLUE,
            hover_color="#2563EB",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_refresh_all_click
        )
        btn_refresh_all.pack(side="right")

        btn_keepalive = ctk.CTkButton(
            left_header,
            text="💓 Session Keepalive",
            width=130,
            height=28,
            fg_color="#059669",
            hover_color="#10B981",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_keepalive_click
        )
        btn_keepalive.pack(side="right", padx=(0, 8))

        self.scroll_tabs = ctk.CTkScrollableFrame(left_box, fg_color="transparent")
        self.scroll_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Right Column: Unified Configuration & Quick Launcher
        right_box = ctk.CTkFrame(workspace, fg_color=SIDEBAR_BG, corner_radius=10, border_color=BORDER_COLOR, border_width=1)
        right_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        lbl_cfg_hdr = ctk.CTkLabel(
            right_box,
            text="⚡ Unified Dispatcher (Spain & Portugal)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F59E0B"
        )
        lbl_cfg_hdr.pack(anchor="w", padx=16, pady=(14, 8))

        # Region Toggle (Spain vs Portugal)
        self.seg_region = ctk.CTkSegmentedButton(
            right_box,
            values=["🇪🇸 Spain", "🇵🇹 Portugal"],
            command=self._on_region_changed,
            height=30,
            selected_color=ACCENT_BLUE
        )
        self.seg_region.set("🇪🇸 Spain")
        self.seg_region.pack(fill="x", padx=16, pady=4)

        # Config fields
        form_frame = ctk.CTkFrame(right_box, fg_color="transparent")
        form_frame.pack(fill="x", padx=16, pady=8)

        # City / Center
        ctk.CTkLabel(form_frame, text="Center / City:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w")
        self.opt_city = ctk.CTkOptionMenu(form_frame, values=PRESETS["Spain"]["cities"], height=30)
        self.opt_city.pack(fill="x", pady=(2, 6))

        # Visa Category
        ctk.CTkLabel(form_frame, text="Appointment Category:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w")
        self.opt_cat = ctk.CTkOptionMenu(form_frame, values=PRESETS["Spain"]["categories"], height=30)
        self.opt_cat.pack(fill="x", pady=(2, 6))

        # Visa Type
        ctk.CTkLabel(form_frame, text="Visa Sub-Type:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w")
        self.opt_type = ctk.CTkOptionMenu(form_frame, values=PRESETS["Spain"]["types"], height=30)
        self.opt_type.pack(fill="x", pady=(2, 6))

        # Pax Count
        ctk.CTkLabel(form_frame, text="Number of Applicants (Pax):", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w")
        self.opt_pax = ctk.CTkSegmentedButton(form_frame, values=["1", "2", "3", "4"], height=28)
        self.opt_pax.set("1")
        self.opt_pax.pack(fill="x", pady=(2, 10))

        # Dispatch Button
        self.btn_dispatch = ctk.CTkButton(
            right_box,
            text="⚡ DISPATCH CONFIG TO ALL CHROMES",
            height=38,
            fg_color="#059669",
            hover_color="#10B981",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_dispatch_config
        )
        self.btn_dispatch.pack(fill="x", padx=16, pady=(10, 8))

        # Status feedback label
        self.lbl_dispatch_status = ctk.CTkLabel(
            right_box,
            text="Ready to dispatch settings.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED
        )
        self.lbl_dispatch_status.pack(padx=16)

        # Separator
        ctk.CTkFrame(right_box, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=16, pady=10)

        # ---------------------------------------------------------------
        # ⏱️ Sec / MS Slot Timing & Mesh Sharing Section
        # ---------------------------------------------------------------
        lbl_timing_hdr = ctk.CTkLabel(
            right_box,
            text="⏱️ Slot Submit Timing (Sec & MS Mesh)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38BDF8"
        )
        lbl_timing_hdr.pack(anchor="w", padx=16, pady=(0, 4))

        timing_row = ctk.CTkFrame(right_box, fg_color="transparent")
        timing_row.pack(fill="x", padx=16, pady=2)
        timing_row.grid_columnconfigure(0, weight=1)
        timing_row.grid_columnconfigure(1, weight=1)

        self.entry_sec = ctk.CTkEntry(timing_row, placeholder_text="Sec (0-59)", height=28)
        self.entry_sec.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.entry_ms = ctk.CTkEntry(timing_row, placeholder_text="MS (0-999)", height=28)
        self.entry_ms.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        btn_send_timing = ctk.CTkButton(
            right_box,
            text="⏱️ ARM & SYNC TIMING (ALL CHROMES)",
            height=30,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_send_timing_click
        )
        btn_send_timing.pack(fill="x", padx=16, pady=(6, 4))

        # Separator
        ctk.CTkFrame(right_box, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=16, pady=10)

        # ---------------------------------------------------------------
        # 👤 Client Data Management (1-Click Autofill)
        # ---------------------------------------------------------------
        lbl_client_hdr = ctk.CTkLabel(
            right_box,
            text="👤 Client / Applicant Data Autofill",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#A855F7"
        )
        lbl_client_hdr.pack(anchor="w", padx=16, pady=(0, 4))

        client_grid = ctk.CTkFrame(right_box, fg_color="transparent")
        client_grid.pack(fill="x", padx=16, pady=2)
        client_grid.grid_columnconfigure(0, weight=1)
        client_grid.grid_columnconfigure(1, weight=1)

        self.c_fname = ctk.CTkEntry(client_grid, placeholder_text="First Name", height=26)
        self.c_fname.grid(row=0, column=0, padx=(0, 2), pady=2, sticky="ew")
        self.c_lname = ctk.CTkEntry(client_grid, placeholder_text="Last Name", height=26)
        self.c_lname.grid(row=0, column=1, padx=(2, 0), pady=2, sticky="ew")

        self.c_pass = ctk.CTkEntry(client_grid, placeholder_text="Passport ID", height=26)
        self.c_pass.grid(row=1, column=0, padx=(0, 2), pady=2, sticky="ew")
        self.c_dob = ctk.CTkEntry(client_grid, placeholder_text="Birth (DD/MM/YYYY)", height=26)
        self.c_dob.grid(row=1, column=1, padx=(2, 0), pady=2, sticky="ew")

        self.c_exp = ctk.CTkEntry(client_grid, placeholder_text="Pass Expiry Date", height=26)
        self.c_exp.grid(row=2, column=0, padx=(0, 2), pady=2, sticky="ew")
        self.c_city = ctk.CTkEntry(client_grid, placeholder_text="City", height=26)
        self.c_city.grid(row=2, column=1, padx=(2, 0), pady=2, sticky="ew")

        self.c_addr = ctk.CTkEntry(client_grid, placeholder_text="Address", height=26)
        self.c_addr.grid(row=3, column=0, columnspan=2, pady=2, sticky="ew")

        self.c_zip = ctk.CTkEntry(client_grid, placeholder_text="Code Postal", height=26)
        self.c_zip.grid(row=4, column=0, columnspan=2, pady=2, sticky="ew")

        btn_fill_client = ctk.CTkButton(
            right_box,
            text="👤 DISPATCH CLIENT DATA TO APPLICANT FORMS",
            height=30,
            fg_color="#7E22CE",
            hover_color="#6B21A8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_dispatch_client_data
        )
        btn_fill_client.pack(fill="x", padx=16, pady=(6, 4))

        # Separator
        ctk.CTkFrame(right_box, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=16, pady=14)

        # Chrome Launch Section
        lbl_launch_hdr = ctk.CTkLabel(
            right_box,
            text="🚀 Multi-Profile Chrome Grid Launcher",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        lbl_launch_hdr.pack(anchor="w", padx=16, pady=(0, 8))

        self.btn_launch_grid = ctk.CTkButton(
            right_box,
            text="🚀 Launch Chrome Windows (Auto-Load Phylakon)",
            height=34,
            fg_color=CARD_BG,
            hover_color=CARD_HOVER,
            border_color=ACCENT_BLUE,
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_launch_chrome
        )
        self.btn_launch_grid.pack(fill="x", padx=16, pady=4)

        # 4. Status Bar
        status_bar = ctk.CTkFrame(self, fg_color="#0E121B", height=28, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")

        self.lbl_status = ctk.CTkLabel(
            status_bar,
            text="Phylakon Master Commander initialized. Listening on ws://127.0.0.1:8765",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED
        )
        self.lbl_status.pack(side="left", padx=15, pady=4)

    def _on_region_changed(self, value: str):
        reg = "Portugal" if "Portugal" in value else "Spain"
        self.current_region = reg
        data = PRESETS[reg]

        self.opt_city.configure(values=data["cities"])
        self.opt_city.set(data["cities"][0])

        self.opt_cat.configure(values=data["categories"])
        self.opt_cat.set(data["categories"][0])

        self.opt_type.configure(values=data["types"])
        self.opt_type.set(data["types"][0])

    def _on_dispatch_config(self):
        settings = {
            "region": self.current_region,
            "vtData": {
                "city": self.opt_city.get(),
                "category": self.opt_cat.get(),
                "type": self.opt_type.get(),
                "members": int(self.opt_pax.get())
            }
        }
        cmd_id = self.server.broadcast_phylakon_config(settings)
        self.server.broadcast_thunder_config(settings)

        now = datetime.now().strftime("%H:%M:%S")
        msg = f"⚡ [{now}] Dispatched to Phylakon: {self.current_region} | {settings['vtData']['city']} (Cmd: {cmd_id})"
        self.lbl_dispatch_status.configure(text=msg, text_color=COLOR_SUCCESS)
        self.lbl_status.configure(text=msg)

    def _on_refresh_all_click(self):
        self.server.broadcast_refresh()
        self.lbl_status.configure(text="Dispatched refresh signal to all active tabs.")

    def _on_keepalive_click(self):
        self.server.broadcast_refresh()
        self.lbl_status.configure(text="💓 Keepalive sent to maintain active ASP.NET Core session timers.")

    def _on_send_timing_click(self):
        s_val = self.entry_sec.get().strip()
        m_val = self.entry_ms.get().strip()
        try:
            sec_int = int(s_val) if s_val else 0
            ms_int = int(m_val) if m_val else 0
        except ValueError:
            self.lbl_status.configure(text="❌ Invalid Sec or MS value.")
            return

        self.server.broadcast_slot_click(sec=sec_int, ms=ms_int, target="all")
        msg = f"⏱️ Dispatched timing to all tabs: Sec={sec_int}, MS={ms_int}"
        self.lbl_dispatch_status.configure(text=msg, text_color="#38BDF8")
        self.lbl_status.configure(text=msg)

    def _on_dispatch_client_data(self):
        client_data = {
            "name": self.c_fname.get().strip(),
            "lastName": self.c_lname.get().strip(),
            "passportId": self.c_pass.get().strip(),
            "birthDay": self.c_dob.get().strip(),
            "expiryDate": self.c_exp.get().strip(),
            "address": self.c_addr.get().strip(),
            "postalCode": self.c_zip.get().strip(),
            "city": self.c_city.get().strip()
        }
        self.server.broadcast_applicant_profile(client_data)
        msg = f"👤 Dispatched client profile for '{client_data['name']} {client_data['lastName']}' to tabs."
        self.lbl_dispatch_status.configure(text=msg, text_color="#A855F7")
        self.lbl_status.configure(text=msg)

    def _on_launch_chrome(self):
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_path):
            chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

        if not os.path.exists(chrome_path):
            self.lbl_status.configure(text="❌ Google Chrome executable not found at default paths.")
            return

        cmd = [
            chrome_path,
            "--new-window",
            f"--load-extension={PHYLAKON_DIR}",
            "https://www.blsspainmorocco.net/"
        ]
        try:
            subprocess.Popen(cmd)
            self.lbl_status.configure(text="🚀 Launched Chrome window with Phylakon Extension pre-loaded.")
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Failed to launch Chrome: {e}")

    def _dismiss_alert(self):
        self.banner_alert.pack_forget()

    def _trigger_slot_alert(self, tab_title: str, dates: List[str]):
        if winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass

        dates_str = ", ".join(dates[:3])
        self.lbl_alert_text.configure(
            text=f"🚨 APPOINTMENT SLOTS DISCOVERED on '{tab_title}'! Dates: [{dates_str}]"
        )
        self.banner_alert.pack(fill="x", padx=15, pady=(5, 0), before=self.winfo_children()[2])

    def _start_poll_loop(self):
        self._update_hud()
        self.after(1000, self._start_poll_loop)

    def _update_hud(self):
        clients = self.server.get_clients_snapshot()
        self.lbl_hud_title.configure(text=f"Connected Chrome Instances & Session Timers ({len(clients)})")

        active_ids = {c["tab_id"] for c in clients}

        # Remove cards for closed tabs
        for tid in list(self.tab_cards.keys()):
            if tid not in active_ids:
                card = self.tab_cards.pop(tid)
                try:
                    card["frame"].destroy()
                except Exception:
                    pass

        # Update or render cards
        for client in clients:
            tid = client.get("tab_id", "")
            title = client.get("title") or "Chrome Tab"
            url = client.get("url") or "BLS Portal"
            rem_sec = client.get("session_remaining_sec", -1)
            has_slots = client.get("has_open_slots", False)
            dates = client.get("dates_open", []) or []

            # Check if open slots newly found
            if has_slots and tid not in self.active_alert_slots:
                self.active_alert_slots.append(tid)
                self._trigger_slot_alert(title, dates)

            # Format countdown
            if rem_sec > 0:
                mins = rem_sec // 60
                secs = rem_sec % 60
                session_text = f"⏳ Session: {mins:02d}:{secs:02d}"
                badge_color = COLOR_SUCCESS if rem_sec > 180 else (COLOR_WARNING if rem_sec > 60 else COLOR_DANGER)
            elif rem_sec == 0:
                session_text = "⚠️ Session Expired"
                badge_color = COLOR_DANGER
            else:
                session_text = "⏳ Session: Detecting..."
                badge_color = TEXT_MUTED

            if tid in self.tab_cards:
                c = self.tab_cards[tid]
                c["lbl_title"].configure(text=f"⚡ {title[:35]}")
                c["lbl_url"].configure(text=f"{url[:40]} • Status: Active")
                c["lbl_session"].configure(text=session_text, text_color=badge_color)
                if has_slots:
                    c["lbl_slots"].configure(text=f"🚨 SLOTS: {', '.join(dates[:2])}", text_color="#F59E0B")
            else:
                card_frame = ctk.CTkFrame(self.scroll_tabs, fg_color=CARD_BG, corner_radius=8, border_color=BORDER_COLOR, border_width=1)
                card_frame.pack(fill="x", pady=4, padx=2)
                card_frame.grid_columnconfigure(0, weight=1)

                top_row = ctk.CTkFrame(card_frame, fg_color="transparent")
                top_row.pack(fill="x", padx=12, pady=(8, 2))

                lbl_t = ctk.CTkLabel(top_row, text=f"⚡ {title[:35]}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY)
                lbl_t.pack(side="left")

                lbl_sess = ctk.CTkLabel(top_row, text=session_text, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=badge_color)
                lbl_sess.pack(side="right")

                bottom_row = ctk.CTkFrame(card_frame, fg_color="transparent")
                bottom_row.pack(fill="x", padx=12, pady=(0, 8))

                lbl_u = ctk.CTkLabel(bottom_row, text=f"{url[:40]} • Status: Active", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_MUTED)
                lbl_u.pack(side="left")

                slot_txt = f"🚨 SLOTS: {', '.join(dates[:2])}" if has_slots else ""
                lbl_sl = ctk.CTkLabel(bottom_row, text=slot_txt, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#F59E0B")
                lbl_sl.pack(side="right")

                self.tab_cards[tid] = {
                    "frame": card_frame,
                    "lbl_title": lbl_t,
                    "lbl_url": lbl_u,
                    "lbl_session": lbl_sess,
                    "lbl_slots": lbl_sl
                }


if __name__ == "__main__":
    app = PhylakonControllerApp()
    app.mainloop()

"""
Chrome Grid Launcher — Single-File Windows Desktop Application
Detects all installed Chrome profiles, allows visual grid arrangement,
and launches/positions Chrome profile windows automatically using pywin32.

Dependencies:
    pip install customtkinter pywin32 pillow
"""

import os
import sys
import json
import time
import re
import shutil
import ctypes
from ctypes import wintypes
import threading
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Callable
import webbrowser
from refresh_server import RefreshServer, ConnectedTab

# Windows DPI awareness setup
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Third-party dependencies
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps
import win32gui
import win32con
import win32process
import win32api

# ---------------------------------------------------------------------------
# Constants, Paths & Modern Dark Color Palette
# ---------------------------------------------------------------------------
APP_NAME = "Chrome Grid Launcher"
APP_VERSION = "v1.0"
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChromeGridLauncher")
LAYOUTS_DIR = os.path.join(APPDATA_DIR, "layouts")
SETTINGS_FILE = os.path.join(APPDATA_DIR, "settings.json")
LAST_LAYOUT_FILE = os.path.join(APPDATA_DIR, "last_layout.json")
GROUPS_FILE = os.path.join(APPDATA_DIR, "groups.json")
THUNDER_PRESETS_FILE = os.path.join(APPDATA_DIR, "thunder_presets.json")
THUNDER_CELL_CONFIGS_FILE = os.path.join(APPDATA_DIR, "thunder_cell_configs.json")

THUNDER_CITY_COLORS = {
    "Casablanca": {"bg": "#0369A1", "border": "#38BDF8", "text": "#F0F9FF"},
    "Rabat": {"bg": "#047857", "border": "#34D399", "text": "#ECFDF5"},
    "Tangier": {"bg": "#B45309", "border": "#FBBF24", "text": "#FFFBEB"},
    "Nador": {"bg": "#6D28D9", "border": "#A78BFA", "text": "#F5F3FF"},
    "Tetouan": {"bg": "#0E7490", "border": "#22D3EE", "text": "#ECFEFF"},
    "Agadir": {"bg": "#BE185D", "border": "#F472B6", "text": "#FDF2F8"},
}
DEFAULT_THUNDER_CARD_COLOR = {"bg": "#1E293B", "border": "#475569", "text": "#94A3B8"}

THUNDER_REGION_CONFIGS = {
    "Spain": {
        "title": "Spain (BLS Spain v1.8.8)",
        "tag": "🇪🇸 Spain",
        "visa_types": [
            "Schengen Visa", "National Visa", "Student Visa", "Work Visa",
            "Casa 1", "Casa 2", "Family Reunification Visa", "Schengen Visa Prior 2023",
            "Students - Language/selectivity", "Students - Non-tertiary studies",
            "Students - Graduate studies", "Student - Others"
        ],
        "centers": ["Casablanca", "Nador", "Tetouan", "Tangier", "Rabat", "Agadir"],
        "categories": ["Normal", "Premium", "Prime Time"],
        "members": ["1", "2", "3", "4"],
        "on_max": ["New App"]
    },
    "Portugal": {
        "title": "Portugal (BLS Portugal v1.6.5)",
        "tag": "🇵🇹 Portugal",
        "visa_types": [
            "Short Stay Visa",
            "Any other category of Long-Stay visa",
            "Highly Qualified Activity"
        ],
        "centers": ["Casablanca", "Rabat"],
        "categories": ["Normal", "Premium", "Prime Time"],
        "members": ["1", "2", "3", "4"],
        "on_max": ["New App"]
    }
}


os.makedirs(LAYOUTS_DIR, exist_ok=True)

# Ultra-performance flags for running 50+ concurrent Chrome profiles on heavy sites like BLS Visa:
# 1. V8 memory capping & garbage collection (stops 30GB+ memory explosion)
# 2. Audio and background thread muting (saves ~100 Windows audio/telemetry threads)
# 3. Compositor & raster thread clamping (stops CPU core saturation)
# 4. Anti-throttling & unthrottled execution in background/occluded windows
CHROME_PERF_FLAGS = [
    # V8 JavaScript Memory Capping & Aggressive Garbage Collection
    '--js-flags=--max-old-space-size=256 --expose-gc',

    # Audio & Thread Reductions (saves ~100 threads across 50 profiles)
    '--mute-audio',
    '--disable-background-networking',
    '--disable-sync',
    '--disable-default-apps',
    '--disable-component-update',
    '--disable-domain-reliability',
    '--disable-client-side-phishing-detection',
    '--disable-speech-api',
    '--disable-breakpad',
    '--num-raster-threads=1',
    '--disable-smooth-scrolling',

    # Anti-throttling & Real-time Execution in Background/Occluded Windows
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-features=CalculateNativeWinOcclusion,Translate,OptimizationHints,MediaRouter,DialMediaRouteProvider,CastMediaRouteProvider',
    '--disable-hang-monitor',
    '--disable-dev-shm-usage',
]

# UI Theme Tokens
COLOR_BG_DARK = "#0B0E14"
COLOR_SIDEBAR_BG = "#121622"
COLOR_TOPBAR_BG = "#151A27"
COLOR_STATUSBAR_BG = "#0E121B"
COLOR_CARD_BG = "#1A2030"
COLOR_CARD_HOVER = "#242C42"
COLOR_CARD_ACTIVE = "#2C3754"
COLOR_EMPTY_CELL = "#141824"
COLOR_EMPTY_HOVER = "#1C2233"
COLOR_BORDER = "#232A3E"
COLOR_BORDER_ACCENT = "#3B82F6"
COLOR_BORDER_HOVER = "#60A5FA"
COLOR_ACCENT = "#3B82F6"
COLOR_ACCENT_HOVER = "#2563EB"
COLOR_SUCCESS = "#10B981"
COLOR_SUCCESS_HOVER = "#059669"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"
COLOR_DANGER_HOVER = "#DC2626"
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_SECONDARY = "#94A3B8"
COLOR_TEXT_MUTED = "#64748B"

# Group Color Tokens
COLOR_GROUP_PRT = "#8B5CF6"      # Purple for PRT profiles
COLOR_GROUP_NUMBERS = "#10B981"  # Emerald for Numbered profiles
COLOR_GROUP_OTHER = "#64748B"    # Slate for Other profiles

PALETTE_COLORS = [
    "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#F59E0B",
    "#06B6D4", "#6366F1", "#14B8A6", "#F97316", "#84CC16"
]

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class ProfileGroup:
    id: str
    name: str
    color: str = "#8B5CF6"
    icon: str = "📁"
    is_builtin: bool = False
    profile_keys: List[str] = None

    def __post_init__(self):
        if self.profile_keys is None:
            self.profile_keys = []


@dataclass
class ChromeProfile:
    key: str                 # Profile directory (e.g. "Default", "Profile 1")
    name: str                # Human-readable name (e.g. "Achraf", "Personal")
    gaia_name: str = ""      # Google account display name
    email: str = ""          # Google account email
    avatar_file: str = ""    # Local path to profile picture
    color: str = "#3B82F6"   # Derived accent color
    initials: str = "?"      # 1-2 letter initial badge
    group_id: str = ""       # Assigned group ID
    group_name: str = ""     # Assigned group display name
    group_color: str = ""    # Assigned group badge color

    @property
    def display_name(self) -> str:
        return self.name if self.name else self.key

    @property
    def subtitle(self) -> str:
        if self.email:
            return f"{self.key} • {self.email}"
        if self.gaia_name and self.gaia_name != self.name:
            return f"{self.key} • {self.gaia_name}"
        return self.key


@dataclass
class MonitorInfo:
    index: int
    hmon: Any
    rect: Tuple[int, int, int, int]        # (left, top, right, bottom)
    work_rect: Tuple[int, int, int, int]   # Work area excluding taskbar
    device: str
    is_primary: bool

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def work_width(self) -> int:
        return self.work_rect[2] - self.work_rect[0]

    @property
    def work_height(self) -> int:
        return self.work_rect[3] - self.work_rect[1]

    @property
    def display_label(self) -> str:
        prim = " (Primary)" if self.is_primary else ""
        return f"Monitor {self.index + 1}: {self.width}×{self.height}{prim}"


# ---------------------------------------------------------------------------
# High-DPI Avatar Badge Generator
# ---------------------------------------------------------------------------
class AvatarCache:
    """Generates and caches antialiased circular profile badges."""
    _cache: Dict[str, ctk.CTkImage] = {}

    @classmethod
    def get_avatar(cls, profile: ChromeProfile, size: int = 40) -> ctk.CTkImage:
        cache_key = f"{profile.key}_{profile.name}_{profile.avatar_file}_{size}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        scale = 2  # Supersample for high-DPI
        full_size = size * scale

        # Attempt to load custom picture
        if profile.avatar_file and os.path.exists(profile.avatar_file):
            try:
                img = Image.open(profile.avatar_file).convert("RGBA")
                img = ImageOps.fit(img, (full_size, full_size), method=Image.Resampling.LANCZOS)
                mask = Image.new("L", (full_size, full_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, full_size, full_size), fill=255)
                img.putalpha(mask)
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(size, size))
                cls._cache[cache_key] = ctk_img
                return ctk_img
            except Exception:
                pass

        # Fallback initials badge
        img = Image.new("RGBA", (full_size, full_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, full_size, full_size), fill=profile.color)

        font_size = int(full_size * 0.44)
        try:
            font = ImageFont.truetype("segoeui.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        draw.text((full_size // 2, full_size // 2), profile.initials, fill="#FFFFFF", font=font, anchor="mm")
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(size, size))
        cls._cache[cache_key] = ctk_img
        return ctk_img


# ---------------------------------------------------------------------------
# Chrome Profile Detection Manager
# ---------------------------------------------------------------------------
class ChromeProfileManager:
    """Discovers Chrome executable and reads all profiles from Local State."""

    @staticmethod
    def get_user_data_path() -> str:
        local_app = os.environ.get("LOCALAPPDATA", "")
        return os.path.join(local_app, "Google", "Chrome", "User Data")

    @staticmethod
    def find_chrome_executable() -> Optional[str]:
        # 1. Standard Program Files
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path

        # 2. Registry lookup
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.exists(val):
                    return val
        except Exception:
            pass

        # 3. PATH search
        which_path = shutil.which("chrome.exe") or shutil.which("chrome")
        if which_path and os.path.exists(which_path):
            return which_path

        return None

    @classmethod
    def load_profiles(cls) -> List[ChromeProfile]:
        user_data_dir = cls.get_user_data_path()
        local_state_file = os.path.join(user_data_dir, "Local State")
        profiles: List[ChromeProfile] = []

        if not os.path.exists(local_state_file):
            return profiles

        try:
            with open(local_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            info_cache = data.get("profile", {}).get("info_cache", {})
        except Exception as e:
            print(f"[ChromeProfileManager] Error reading Local State: {e}")
            return profiles

        # Natural sorting: Default first, then Profile 1, Profile 2, etc.
        def sort_key(k: str):
            if k.lower() == "default":
                return (0, 0, "")
            m = re.match(r"Profile\s*(\d+)", k, re.IGNORECASE)
            if m:
                return (1, int(m.group(1)), "")
            return (2, 999999, k.lower())

        sorted_keys = sorted(info_cache.keys(), key=sort_key)

        for idx, key in enumerate(sorted_keys):
            info = info_cache.get(key, {})
            name = (info.get("name") or "").strip()
            gaia_name = (info.get("gaia_name") or "").strip()
            email = (info.get("user_name") or "").strip()

            display_name = name or gaia_name or key

            # Compute initials
            words = display_name.split()
            if len(words) >= 2:
                initials = (words[0][0] + words[1][0]).upper()
            elif len(display_name) >= 2:
                initials = display_name[:2].upper()
            elif display_name:
                initials = display_name[0].upper()
            else:
                initials = "?"

            color = PALETTE_COLORS[hash(key + display_name) % len(PALETTE_COLORS)]

            # Check profile picture
            pic_filename = info.get("gaia_picture_file_name", "")
            avatar_path = ""
            if pic_filename:
                cand = os.path.join(user_data_dir, key, pic_filename)
                if os.path.exists(cand):
                    avatar_path = cand
            if not avatar_path:
                cand2 = os.path.join(user_data_dir, key, "Google Profile Picture.png")
                if os.path.exists(cand2):
                    avatar_path = cand2

            profiles.append(
                ChromeProfile(
                    key=key,
                    name=display_name,
                    gaia_name=gaia_name,
                    email=email,
                    avatar_file=avatar_path,
                    color=color,
                    initials=initials
                )
            )

        # Apply group detection and custom groups immediately
        GroupManager.apply_groups_to_profiles(profiles, GroupManager.load_custom_groups())

        return profiles


def natural_sort_key(s: str):
    """Sort strings containing numbers in natural human order (e.g. PRT2 before PRT10, 2 before 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


def _get_cg_attr(cg: Any, attr: str, default: Any = "") -> Any:
    """Helper to get attributes from either ProfileGroup dataclass or dict."""
    if isinstance(cg, dict):
        return cg.get(attr, default)
    return getattr(cg, attr, default)


# ---------------------------------------------------------------------------
# Profile Group Manager
# ---------------------------------------------------------------------------
class GroupManager:
    """Manages profile categorization: Numbered, PRT, Other, and Custom user groups."""
    GROUP_ALL = "all"
    GROUP_NUMBERS = "numbers"
    GROUP_PRT = "prt"
    GROUP_OTHER = "other"

    @staticmethod
    def load_custom_groups() -> List[ProfileGroup]:
        if os.path.exists(GROUPS_FILE):
            try:
                with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_groups = data.get("custom_groups", [])
                    result = []
                    for g in raw_groups:
                        if isinstance(g, dict):
                            result.append(ProfileGroup(
                                id=g.get("id", ""),
                                name=g.get("name", ""),
                                color=g.get("color", "#3B82F6"),
                                profile_keys=list(g.get("profile_keys", [])),
                                icon=g.get("icon", "📁")
                            ))
                        elif isinstance(g, ProfileGroup):
                            result.append(g)
                    return result
            except Exception as e:
                print(f"[GroupManager] Error reading {GROUPS_FILE}: {e}")
        return []

    @staticmethod
    def load_overrides() -> Dict[str, str]:
        if os.path.exists(GROUPS_FILE):
            try:
                with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("overrides", {})
            except Exception:
                pass
        return {}

    @staticmethod
    def save_data(custom_groups: List[Any], overrides: Optional[Dict[str, str]] = None):
        try:
            if overrides is None:
                overrides = GroupManager.load_overrides()
            serialized = []
            for g in custom_groups:
                if isinstance(g, ProfileGroup):
                    serialized.append({
                        "id": g.id,
                        "name": g.name,
                        "color": g.color,
                        "icon": g.icon,
                        "profile_keys": list(g.profile_keys)
                    })
                elif isinstance(g, dict):
                    serialized.append(g)
            with open(GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump({"custom_groups": serialized, "overrides": overrides}, f, indent=2)
        except Exception as e:
            print(f"[GroupManager] Error saving {GROUPS_FILE}: {e}")

    @staticmethod
    def save_custom_groups(custom_groups: List[Any]):
        GroupManager.save_data(custom_groups)

    @staticmethod
    def is_prt_profile(profile_key: str, profile_name: str) -> bool:
        comb = f"{profile_name} {profile_key}".upper()
        return bool(re.search(r'\bPRT\d*\b|PRT', comb))

    @staticmethod
    def is_number_profile(profile_key: str, profile_name: str) -> bool:
        if GroupManager.is_prt_profile(profile_key, profile_name):
            return False
        clean = (profile_name or "").strip()
        if clean.isdigit():
            return True
        if re.match(r'^Profile\s*\d+$', profile_key, re.IGNORECASE) and (not clean or clean.lower().startswith("profile")):
            return True
        return False

    @classmethod
    def apply_groups_to_profiles(
        cls,
        profiles: List[ChromeProfile],
        custom_groups: Optional[List[Any]] = None,
        overrides: Optional[Dict[str, str]] = None
    ):
        if custom_groups is None:
            custom_groups = cls.load_custom_groups()
        if overrides is None:
            overrides = cls.load_overrides()

        custom_map = {}
        for cg in custom_groups:
            cg_id = _get_cg_attr(cg, "id", "")
            cg_name = _get_cg_attr(cg, "name", "Custom")
            cg_color = _get_cg_attr(cg, "color", "#3B82F6")
            pkeys = _get_cg_attr(cg, "profile_keys", [])
            for pkey in pkeys:
                custom_map[pkey] = (cg_id, cg_name, cg_color)

        for p in profiles:
            if p.key in custom_map:
                p.group_id, p.group_name, p.group_color = custom_map[p.key]
            elif p.key in overrides:
                ov = overrides[p.key]
                if ov == cls.GROUP_PRT:
                    p.group_id = cls.GROUP_PRT
                    p.group_name = "PRT"
                    p.group_color = COLOR_GROUP_PRT
                elif ov == cls.GROUP_NUMBERS:
                    p.group_id = cls.GROUP_NUMBERS
                    p.group_name = "Numbers"
                    p.group_color = COLOR_GROUP_NUMBERS
                elif ov == cls.GROUP_OTHER:
                    p.group_id = cls.GROUP_OTHER
                    p.group_name = "Other"
                    p.group_color = COLOR_GROUP_OTHER
                else:
                    p.group_id = cls.GROUP_OTHER
                    p.group_name = "Other"
                    p.group_color = COLOR_GROUP_OTHER
            elif cls.is_prt_profile(p.key, p.display_name):
                p.group_id = cls.GROUP_PRT
                p.group_name = "PRT"
                p.group_color = COLOR_GROUP_PRT
            elif cls.is_number_profile(p.key, p.display_name):
                p.group_id = cls.GROUP_NUMBERS
                p.group_name = "Numbers"
                p.group_color = COLOR_GROUP_NUMBERS
            else:
                p.group_id = cls.GROUP_OTHER
                p.group_name = "Other"
                p.group_color = COLOR_GROUP_OTHER

    @classmethod
    def get_group_counts(cls, profiles: List[ChromeProfile], custom_groups: Optional[List[Any]] = None) -> Dict[str, int]:
        if custom_groups is None:
            custom_groups = cls.load_custom_groups()

        cls.apply_groups_to_profiles(profiles, custom_groups)

        counts = {
            cls.GROUP_ALL: len(profiles),
            cls.GROUP_NUMBERS: 0,
            cls.GROUP_PRT: 0,
            cls.GROUP_OTHER: 0
        }
        for cg in custom_groups:
            cg_id = _get_cg_attr(cg, "id", "")
            if cg_id:
                counts[cg_id] = 0

        for p in profiles:
            gid = p.group_id
            if gid in counts:
                counts[gid] += 1
            elif gid:
                counts[gid] = 1

        return counts

    @classmethod
    def filter_profiles(
        cls,
        profiles: List[ChromeProfile],
        group_id: str,
        custom_groups: Optional[List[Any]] = None,
        search_query: str = ""
    ) -> List[ChromeProfile]:
        if custom_groups is None:
            custom_groups = cls.load_custom_groups()

        if profiles and not profiles[0].group_id:
            cls.apply_groups_to_profiles(profiles, custom_groups)

        query = search_query.strip().lower()

        if group_id == cls.GROUP_ALL or not group_id:
            matched = list(profiles)
        elif group_id in (cls.GROUP_PRT, cls.GROUP_NUMBERS, cls.GROUP_OTHER):
            matched = [p for p in profiles if p.group_id == group_id]
        else:
            cg = next((g for g in custom_groups if _get_cg_attr(g, "id") == group_id), None)
            if cg:
                pkeys = set(_get_cg_attr(cg, "profile_keys", []))
                matched = [p for p in profiles if p.key in pkeys or p.group_id == group_id]
            else:
                matched = list(profiles)

        # Natural sort within group
        matched.sort(key=lambda p: natural_sort_key(p.display_name))

        # Search filter
        if query:
            matched = [
                p for p in matched
                if query in p.name.lower() or query in p.key.lower() or query in p.email.lower() or query in p.gaia_name.lower()
            ]

        return matched

    @classmethod
    def create_custom_group(cls, name: str, color: str, profile_keys: List[str], custom_groups: List[Any]) -> ProfileGroup:
        group_id = f"group_{int(time.time())}_{len(custom_groups) + 1}"
        new_group = ProfileGroup(
            id=group_id,
            name=name.strip() or f"Group {len(custom_groups) + 1}",
            color=color or "#3B82F6",
            icon="📁",
            profile_keys=list(profile_keys)
        )
        custom_groups.append(new_group)
        cls.save_custom_groups(custom_groups)
        return new_group

    @classmethod
    def delete_custom_group(cls, group_id: str, custom_groups: List[Any]):
        idx = next((i for i, g in enumerate(custom_groups) if _get_cg_attr(g, "id") == group_id), None)
        if idx is not None:
            custom_groups.pop(idx)
            cls.save_custom_groups(custom_groups)

    @classmethod
    def assign_profile_to_group(cls, profile_key: str, target_group_id: str, custom_groups: List[Any]):
        for cg in custom_groups:
            pkeys = _get_cg_attr(cg, "profile_keys", [])
            if profile_key in pkeys:
                pkeys.remove(profile_key)

        if target_group_id and not target_group_id.startswith("__") and target_group_id != "auto":
            target = next((g for g in custom_groups if _get_cg_attr(g, "id") == target_group_id), None)
            if target:
                pkeys = _get_cg_attr(target, "profile_keys", [])
                if profile_key not in pkeys:
                    pkeys.append(profile_key)

        cls.save_custom_groups(custom_groups)


# ---------------------------------------------------------------------------
# Window & Monitor Placement Manager (pywin32)
# ---------------------------------------------------------------------------
class WindowManager:
    """Handles multi-monitor enumeration and win32 window positioning."""

    @staticmethod
    def get_monitors() -> List[MonitorInfo]:
        monitors: List[MonitorInfo] = []
        try:
            raw_monitors = win32api.EnumDisplayMonitors()
            for idx, raw in enumerate(raw_monitors):
                hmon, hdc, rect = raw
                info = win32api.GetMonitorInfo(hmon)
                is_primary = bool(info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY)
                monitors.append(
                    MonitorInfo(
                        index=idx,
                        hmon=hmon,
                        rect=info["Monitor"],
                        work_rect=info["Work"],
                        device=info.get("Device", f"Display{idx+1}"),
                        is_primary=is_primary
                    )
                )
        except Exception as e:
            print(f"[WindowManager] Error enumerating monitors: {e}")

        # Fallback to primary screen
        if not monitors:
            rect = (0, 0, win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN))
            monitors.append(
                MonitorInfo(
                    index=0,
                    hmon=None,
                    rect=rect,
                    work_rect=rect,
                    device="DefaultDisplay",
                    is_primary=True
                )
            )
        return monitors

    @staticmethod
    def get_window_shadow_insets(hwnd: int, default_offset: int = 7) -> Tuple[int, int, int, int]:
        """Returns (left_inset, top_inset, right_inset, bottom_inset) for Windows DWM invisible borders."""
        try:
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]
            frame_rect = RECT()
            # DWMWA_EXTENDED_FRAME_BOUNDS = 9
            res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd,
                9,
                ctypes.byref(frame_rect),
                ctypes.sizeof(frame_rect)
            )
            if res == 0:
                win_rect = win32gui.GetWindowRect(hwnd)
                s_left = max(0, frame_rect.left - win_rect[0])
                s_top = max(0, frame_rect.top - win_rect[1])
                s_right = max(0, win_rect[2] - frame_rect.right)
                s_bottom = max(0, win_rect[3] - frame_rect.bottom)
                if 0 <= s_left <= 40 and 0 <= s_right <= 40 and 0 <= s_bottom <= 40:
                    return (s_left, s_top, s_right, s_bottom)
        except Exception:
            pass
        return (default_offset, 0, default_offset, default_offset)

    @staticmethod
    def calculate_cell_rect(
        monitor: MonitorInfo,
        rows: int,
        cols: int,
        row: int,
        col: int,
        gap: int = 4,
        use_full_screen: bool = False,
        margins: Optional[Dict[str, int]] = None,
        cell_offsets: Optional[Dict[str, Dict[str, int]]] = None,
        col_weights: Optional[List[float]] = None,
        row_weights: Optional[List[float]] = None,
    ) -> Tuple[int, int, int, int]:
        """Calculates (x, y, width, height) with optional full-screen coverage, custom margins,
        proportional column/row weights, and per-cell fine adjustments.
        """
        rows = max(1, rows)
        cols = max(1, cols)
        row = min(max(0, row), rows - 1)
        col = min(max(0, col), cols - 1)

        # Base bounds: Work area vs Full screen
        if use_full_screen:
            b_left, b_top, b_right, b_bottom = monitor.rect
        else:
            b_left, b_top, b_right, b_bottom = monitor.work_rect

        # Inset by custom margins (top, bottom, left, right)
        margins = margins or {}
        m_left = int(margins.get("left", 0))
        m_top = int(margins.get("top", 0))
        m_right = int(margins.get("right", 0))
        m_bottom = int(margins.get("bottom", 0))

        area_left = b_left + m_left
        area_top = b_top + m_top
        area_right = b_right - m_right
        area_bottom = b_bottom - m_bottom

        area_w = max(cols * 20, area_right - area_left)
        area_h = max(rows * 20, area_bottom - area_top)

        gap = int(gap)
        total_gap_w = gap * (cols - 1)
        total_gap_h = gap * (rows - 1)

        avail_w = max(cols * 10, area_w - total_gap_w)
        avail_h = max(rows * 10, area_h - total_gap_h)

        # Column widths & X positions
        if col_weights and len(col_weights) == cols and sum(col_weights) > 0:
            total_cw = sum(col_weights)
            col_widths = [int(avail_w * (w / total_cw)) for w in col_weights]
            diff_w = avail_w - sum(col_widths)
            for idx in range(diff_w):
                col_widths[idx % cols] += 1
        else:
            base_w = avail_w // cols
            rem_w = avail_w % cols
            col_widths = [base_w + (1 if c < rem_w else 0) for c in range(cols)]

        col_x_offsets = []
        cur_x = area_left
        for w in col_widths:
            col_x_offsets.append(cur_x)
            cur_x += w + gap

        # Row heights & Y positions
        if row_weights and len(row_weights) == rows and sum(row_weights) > 0:
            total_rw = sum(row_weights)
            row_heights = [int(avail_h * (h / total_rw)) for h in row_weights]
            diff_h = avail_h - sum(row_heights)
            for idx in range(diff_h):
                row_heights[idx % rows] += 1
        else:
            base_h = avail_h // rows
            rem_h = avail_h % rows
            row_heights = [base_h + (1 if r < rem_h else 0) for r in range(rows)]

        row_y_offsets = []
        cur_y = area_top
        for h in row_heights:
            row_y_offsets.append(cur_y)
            cur_y += h + gap

        x = col_x_offsets[col]
        y = row_y_offsets[row]
        w = col_widths[col]
        h = row_heights[row]

        # Per-cell fine offsets
        if cell_offsets:
            c_key = f"{row},{col}"
            c_offset = cell_offsets.get(c_key, cell_offsets.get((row, col), {}))
            if c_offset:
                x += int(c_offset.get("dx", 0))
                y += int(c_offset.get("dy", 0))
                w = max(10, w + int(c_offset.get("dw", 0)))
                h = max(10, h + int(c_offset.get("dh", 0)))

        return (int(x), int(y), int(w), int(h))

    @staticmethod
    def is_chrome_window(hwnd: int) -> bool:
        """Strictly verifies that a window handle belongs to a real Google Chrome (chrome.exe) process."""
        if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False

        try:
            cls_name = win32gui.GetClassName(hwnd)
            if cls_name != "Chrome_WidgetWin_1":
                return False

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return False

            # Query process executable name via QueryFullProcessImageNameW
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = ctypes.c_ulong(1024)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                        exe_name = os.path.basename(buf.value).lower()
                        return exe_name == "chrome.exe"
                finally:
                    ctypes.windll.kernel32.CloseHandle(h_proc)

            # Fallback check via win32process
            try:
                h_proc2 = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
                if h_proc2:
                    try:
                        exe_path = win32process.GetModuleFileNameEx(h_proc2, 0)
                        if exe_path:
                            return os.path.basename(exe_path).lower() == "chrome.exe"
                    finally:
                        win32api.CloseHandle(h_proc2)
            except Exception:
                pass
        except Exception:
            pass

        return False

    @staticmethod
    def get_chrome_window_profile_key(hwnd: int) -> Optional[str]:
        """Extracts the profile directory key (e.g. 'Default', 'Profile 2') for a Chrome window."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return None
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                return None
            try:
                class UNICODE_STRING(ctypes.Structure):
                    _fields_ = [
                        ('Length', wintypes.USHORT),
                        ('MaximumLength', wintypes.USHORT),
                        ('Buffer', ctypes.c_wchar_p)
                    ]
                buf = ctypes.create_string_buffer(4096)
                ret_len = wintypes.ULONG()
                # ProcessCommandLineInformation = 60
                status = ctypes.windll.ntdll.NtQueryInformationProcess(h_proc, 60, buf, ctypes.sizeof(buf), ctypes.byref(ret_len))
                if status == 0:
                    us = UNICODE_STRING.from_buffer_copy(buf)
                    cmd_line = us.Buffer or ""
                    m = re.search(r'--profile-directory=(?:["\']([^"\']+)["\']|([^\s]+))', cmd_line)
                    if m:
                        return m.group(1) or m.group(2)
            finally:
                ctypes.windll.kernel32.CloseHandle(h_proc)
        except Exception:
            pass
        return None

    @classmethod
    def get_chrome_windows(cls) -> List[Tuple[int, str, Tuple[int, int, int, int]]]:
        """Returns list of (hwnd, title, rect) for visible top-level Chrome windows (chrome.exe only)."""
        results = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                if cls.is_chrome_window(hwnd):
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    # Filter out tiny off-screen or toast windows
                    if w > 200 and h > 150:
                        title = win32gui.GetWindowText(hwnd)
                        results.append((hwnd, title, rect))
            return True

        try:
            ctypes.windll.kernel32.SetLastError(0)
            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            # Error 183 or 0 occurs if no windows exist in current desktop session
            pass
        return results

    @classmethod
    def position_window(
        cls,
        hwnd: int,
        x: int,
        y: int,
        w: int,
        h: int,
        dwm_compensation: bool = True,
        dwm_border_offset: int = 7
    ):
        """Restores and repositions a window to (x, y, w, h) with optional DWM shadow compensation."""
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] in (win32con.SW_SHOWMINIMIZED, win32con.SW_SHOWMAXIMIZED):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.06)

            pos_x, pos_y, pos_w, pos_h = x, y, w, h
            if dwm_compensation:
                s_left, s_top, s_right, s_bottom = cls.get_window_shadow_insets(hwnd, default_offset=dwm_border_offset)
                pos_x = x - s_left
                pos_y = y - s_top
                pos_w = w + s_left + s_right
                pos_h = h + s_top + s_bottom

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                int(pos_x),
                int(pos_y),
                int(pos_w),
                int(pos_h),
                win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE
            )
            # Short second pass to guarantee final position/size after Windows completes paint
            time.sleep(0.05)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                int(pos_x),
                int(pos_y),
                int(pos_w),
                int(pos_h),
                win32con.SWP_NOACTIVATE
            )
        except Exception as e:
            print(f"[WindowManager] Failed to position hwnd {hwnd}: {e}")

    @classmethod
    def launch_and_position(
        cls,
        chrome_exe: str,
        profile_key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        timeout: float = 8.0,
        reuse_existing: bool = False,
        dwm_compensation: bool = True,
        dwm_border_offset: int = 7,
        already_managed_hwnds: Optional[Set[int]] = None
    ) -> Optional[int]:
        """Launches Chrome with profile, detects the window, and moves it to the cell."""
        existing_hwnds = {hwnd for hwnd, _, _ in cls.get_chrome_windows()}
        if already_managed_hwnds:
            existing_hwnds.update(already_managed_hwnds)

        cmd = [
            chrome_exe,
            f'--profile-directory={profile_key}',
            f'--window-position={int(x)},{int(y)}',
            f'--window-size={int(w)},{int(h)}'
        ] + CHROME_PERF_FLAGS

        # Chrome has an OS-level minimum window width (~516px on Windows at 100% DPI).
        # For high-density grids where cell width < 500px (e.g. 10 columns or narrow monitors),
        # force device scale factor to scale Chrome controls down so it can shrink cleanly without overlapping.
        if w < 500:
            scale = round(max(0.40, min(1.0, (w - 10) / 490.0)), 2)
            cmd.append(f"--force-device-scale-factor={scale}")

        if not reuse_existing:
            cmd.append("--new-window")

        try:
            subprocess.Popen(cmd)
        except Exception as e:
            print(f"[WindowManager] Failed to launch Chrome: {e}")
            return None

        # Poll for new window
        start_time = time.time()
        target_hwnd = None
        current_windows = []

        while time.time() - start_time < timeout:
            time.sleep(0.12)
            current_windows = cls.get_chrome_windows()
            current_hwnds = {hwnd for hwnd, _, _ in current_windows}
            new_hwnds = current_hwnds - existing_hwnds

            if new_hwnds:
                target_hwnd = list(new_hwnds)[0]
                break

        # Fallback: check foreground window or any unmanaged Chrome window (never steal existing ones)
        if not target_hwnd:
            fg_hwnd = win32gui.GetForegroundWindow()
            if fg_hwnd and cls.is_chrome_window(fg_hwnd) and fg_hwnd not in existing_hwnds:
                target_hwnd = fg_hwnd
            elif current_windows:
                unmanaged_candidates = [hwnd for hwnd, _, _ in current_windows if hwnd not in existing_hwnds]
                if unmanaged_candidates:
                    target_hwnd = unmanaged_candidates[0]

        if target_hwnd:
            cls.position_window(target_hwnd, x, y, w, h, dwm_compensation=dwm_compensation, dwm_border_offset=dwm_border_offset)
            return target_hwnd

        return None


# ---------------------------------------------------------------------------
# Configuration & Layout Storage Manager
# ---------------------------------------------------------------------------
class ConfigManager:
    """Handles settings persistence and layout preset JSON files."""

    @staticmethod
    def load_settings() -> Dict[str, Any]:
        default_settings = {
            "theme": "Dark",
            "monitor_index": 0,
            "cell_gap": 4,
            "window_timeout": 8.0,
            "launch_interval": 400,
            "reuse_existing": False,
            "custom_rows": 2,
            "custom_cols": 2,
            "chrome_path_override": "",
            "protected_profile_key": "Default",
            "use_full_screen": False,
            "screen_margins": {"top": 0, "bottom": 0, "left": 0, "right": 0},
            "dwm_compensation": True,
            "dwm_border_offset": 7,
            "cell_offsets": {},
            "col_weights": [],
            "row_weights": []
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_settings.update(data)
            except Exception as e:
                print(f"[ConfigManager] Error reading settings: {e}")
        return default_settings

    @staticmethod
    def save_settings(settings: Dict[str, Any]):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"[ConfigManager] Error saving settings: {e}")

    @staticmethod
    def save_layout_file(name: str, layout_data: Dict[str, Any]) -> str:
        safe_name = re.sub(r'[\\/*?:"<>|]', "", name).strip() or "Unnamed"
        file_path = os.path.join(LAYOUTS_DIR, f"{safe_name}.json")
        layout_data["name"] = safe_name
        layout_data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(layout_data, f, indent=2)
        return file_path

    @staticmethod
    def load_layout_file(name_or_file: str) -> Optional[Dict[str, Any]]:
        path = name_or_file if os.path.isabs(name_or_file) else os.path.join(LAYOUTS_DIR, f"{name_or_file}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ConfigManager] Error loading layout {path}: {e}")
        return None

    @staticmethod
    def list_saved_layouts() -> List[Dict[str, Any]]:
        layouts = []
        if os.path.exists(LAYOUTS_DIR):
            for fname in os.listdir(LAYOUTS_DIR):
                if fname.endswith(".json"):
                    full_p = os.path.join(LAYOUTS_DIR, fname)
                    try:
                        with open(full_p, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            data["_filename"] = fname
                            data["_filepath"] = full_p
                            layouts.append(data)
                    except Exception:
                        pass
        return layouts

    @staticmethod
    def delete_layout_file(filepath: str):
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"[ConfigManager] Failed to delete {filepath}: {e}")

    @staticmethod
    def save_last_layout(layout_data: Dict[str, Any]):
        try:
            with open(LAST_LAYOUT_FILE, "w", encoding="utf-8") as f:
                json.dump(layout_data, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def load_last_layout() -> Optional[Dict[str, Any]]:
        if os.path.exists(LAST_LAYOUT_FILE):
            try:
                with open(LAST_LAYOUT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None


# ---------------------------------------------------------------------------
# UI Widget: Draggable Profile Card (Sidebar)
# ---------------------------------------------------------------------------
class ProfileSidebarCard(ctk.CTkFrame):
    """Profile card in the sidebar with click-to-select, drag-and-drop, and personal protection shield."""

    def __init__(self, master, profile: ChromeProfile, on_select, on_quick_add, on_drag_drop, on_toggle_protect=None, on_assign_group=None, is_protected=False, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_CARD_BG,
            corner_radius=10,
            border_width=2 if is_protected else 1,
            border_color="#F59E0B" if is_protected else COLOR_BORDER,
            cursor="hand2",
            **kwargs
        )
        self.profile = profile
        self.on_select = on_select
        self.on_quick_add = on_quick_add
        self.on_drag_drop = on_drag_drop
        self.on_toggle_protect = on_toggle_protect
        self.on_assign_group = on_assign_group
        self.is_protected = is_protected
        self.is_selected = False

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        self._drag_window = None

        self.grid_columnconfigure(1, weight=1)

        # Avatar Badge
        self.avatar_img = AvatarCache.get_avatar(profile, size=36)
        self.avatar_label = ctk.CTkLabel(self, text="", image=self.avatar_img)
        self.avatar_label.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=8)

        # Name + Group Badge Row
        name_display = f"🛡️ {profile.display_name}" if is_protected else profile.display_name
        name_color = "#FCD34D" if is_protected else COLOR_TEXT_PRIMARY

        name_row = ctk.CTkFrame(self, fg_color="transparent")
        name_row.grid(row=0, column=1, sticky="w", pady=(8, 0))

        self.name_label = ctk.CTkLabel(
            name_row,
            text=name_display,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=name_color,
            anchor="w"
        )
        self.name_label.pack(side="left")

        # Group Pill Badge
        if profile.group_name:
            self.grp_badge = ctk.CTkLabel(
                name_row,
                text=profile.group_name,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color="#FFFFFF",
                fg_color=profile.group_color or COLOR_GROUP_PRT,
                corner_radius=4,
                padx=5,
                pady=1
            )
            self.grp_badge.pack(side="left", padx=(6, 0))

        # Subtitle
        sub_text = f"{profile.subtitle} • Personal" if is_protected else profile.subtitle
        self.sub_label = ctk.CTkLabel(
            self,
            text=sub_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#F59E0B" if is_protected else COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.sub_label.grid(row=1, column=1, sticky="w", pady=(0, 8))

        # Right-side Action Buttons Frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=(2, 10), pady=8)

        # Group Assign Button
        if self.on_assign_group:
            self.btn_grp = ctk.CTkButton(
                btn_frame,
                text="🏷️",
                width=26,
                height=28,
                corner_radius=6,
                fg_color=COLOR_CARD_HOVER,
                hover_color=COLOR_ACCENT,
                font=ctk.CTkFont(size=11),
                command=lambda: self.on_assign_group(self.profile)
            )
            self.btn_grp.pack(side="left", padx=(0, 4))

        # Protect Toggle Button
        self.btn_protect = ctk.CTkButton(
            btn_frame,
            text="🛡️",
            width=28,
            height=28,
            corner_radius=6,
            fg_color="#3D2006" if is_protected else COLOR_CARD_HOVER,
            hover_color="#78350F" if is_protected else "#451A03",
            font=ctk.CTkFont(size=12),
            command=lambda: self.on_toggle_protect(self.profile) if self.on_toggle_protect else None
        )
        self.btn_protect.pack(side="left", padx=(0, 4))

        # Quick Add Button
        self.add_btn = ctk.CTkButton(
            btn_frame,
            text="+",
            width=28,
            height=28,
            corner_radius=6,
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
            command=lambda: self.on_quick_add(self.profile)
        )
        self.add_btn.pack(side="left")

        # Event bindings for drag & click
        for w in [self, self.avatar_label, self.name_label, self.sub_label, name_row]:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, event=None):
        if not self.is_selected and not self._is_dragging:
            border_c = "#F59E0B" if self.is_protected else (self.profile.group_color or COLOR_BORDER_ACCENT)
            self.configure(fg_color=COLOR_CARD_HOVER, border_color=border_c)

    def _on_leave(self, event=None):
        if not self.is_selected and not self._is_dragging:
            border_c = "#F59E0B" if self.is_protected else COLOR_BORDER
            self.configure(fg_color=COLOR_CARD_BG, border_color=border_c)

    def _on_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._is_dragging = False

    def _on_motion(self, event):
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if (dx > 6 or dy > 6) and not self._is_dragging:
            self._is_dragging = True
            self._create_drag_window(event.x_root, event.y_root)

        if self._is_dragging and self._drag_window:
            self._drag_window.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

    def _create_drag_window(self, x, y):
        self._drag_window = tk.Toplevel(self)
        self._drag_window.wm_overrideredirect(True)
        self._drag_window.attributes("-topmost", True)
        self._drag_window.attributes("-alpha", 0.90)
        self._drag_window.configure(bg=COLOR_CARD_BG)

        f = tk.Frame(self._drag_window, bg=COLOR_CARD_ACTIVE, padx=10, pady=6, highlightbackground=COLOR_ACCENT, highlightthickness=1)
        f.pack()
        lbl = tk.Label(
            f,
            text=f"📂 {self.profile.display_name}",
            bg=COLOR_CARD_ACTIVE,
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold")
        )
        lbl.pack()
        self._drag_window.geometry(f"+{x + 12}+{y + 12}")

    def _on_release(self, event):
        if self._is_dragging:
            self._is_dragging = False
            if self._drag_window:
                self._drag_window.destroy()
                self._drag_window = None

            target_widget = self.winfo_containing(event.x_root, event.y_root)
            curr = target_widget
            found_cell = None
            while curr and curr != self.winfo_toplevel():
                if isinstance(curr, GridCellCard):
                    found_cell = curr
                    break
                curr = getattr(curr, "master", None)

            if found_cell:
                self.on_drag_drop(found_cell.row, found_cell.col, self.profile)
            border_c = "#F59E0B" if self.is_protected else COLOR_BORDER
            self.configure(fg_color=COLOR_CARD_BG, border_color=border_c)
        else:
            self.on_select(self.profile)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.configure(fg_color=COLOR_CARD_ACTIVE, border_color=COLOR_ACCENT, border_width=2)
        else:
            border_c = "#F59E0B" if self.is_protected else COLOR_BORDER
            border_w = 2 if self.is_protected else 1
            self.configure(fg_color=COLOR_CARD_BG, border_color=border_c, border_width=border_w)


# ---------------------------------------------------------------------------
# UI Widget: Grid Cell Card (Center Canvas)
# ---------------------------------------------------------------------------
class GridCellCard(ctk.CTkFrame):
    """Visual preview card for a single cell in the grid with adaptive density styling."""

    def __init__(
        self,
        master,
        row: int,
        col: int,
        cell_index: int,
        profile: Optional[ChromeProfile],
        on_cell_clicked,
        on_cell_cleared,
        on_cell_change,
        is_compact: bool = False,
        cell_rect: Optional[Tuple[int, int, int, int]] = None,
        on_cell_fine_tune: Optional[Any] = None,
        **kwargs
    ):
        border_c = (profile.group_color or COLOR_BORDER_ACCENT) if profile else COLOR_BORDER
        super().__init__(
            master,
            fg_color=COLOR_CARD_BG if profile else COLOR_EMPTY_CELL,
            corner_radius=8 if is_compact else 12,
            border_width=2 if profile else 1,
            border_color=border_c,
            cursor="hand2",
            **kwargs
        )
        self.row = row
        self.col = col
        self.cell_index = cell_index
        self.profile = profile
        self.on_cell_clicked = on_cell_clicked
        self.on_cell_cleared = on_cell_cleared
        self.on_cell_change = on_cell_change
        self.is_compact = is_compact
        self.cell_rect = cell_rect
        self.on_cell_fine_tune = on_cell_fine_tune
        self.status_text = ""

        self._build_ui()

    def _build_ui(self):
        for child in self.winfo_children():
            child.destroy()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header: Cell coordinate label & Action buttons
        header = ctk.CTkFrame(self, fg_color="transparent")
        h_pad_y = (4, 1) if self.is_compact else (8, 2)
        h_pad_x = 6 if self.is_compact else 10
        header.grid(row=0, column=0, sticky="ew", padx=h_pad_x, pady=h_pad_y)
        header.grid_columnconfigure(0, weight=1)

        if self.is_compact:
            tag_text = f"#{self.cell_index + 1:02d} [R{self.row + 1},C{self.col + 1}]"
        else:
            tag_text = f"Cell {self.cell_index + 1}  [R{self.row + 1}, C{self.col + 1}]"

        lbl_tag = ctk.CTkLabel(
            header,
            text=tag_text,
            font=ctk.CTkFont(family="Segoe UI", size=10 if self.is_compact else 11, weight="bold"),
            text_color=COLOR_ACCENT if self.is_compact else COLOR_TEXT_MUTED
        )
        lbl_tag.grid(row=0, column=0, sticky="w")

        # Header Actions (Right side: resolution pill, fine-tune button, clear button)
        hdr_actions = ctk.CTkFrame(header, fg_color="transparent")
        hdr_actions.grid(row=0, column=1, sticky="e")

        if self.cell_rect:
            _, _, w_px, h_px = self.cell_rect
            lbl_res = ctk.CTkLabel(
                hdr_actions,
                text=f"{w_px}×{h_px}",
                font=ctk.CTkFont(family="Segoe UI", size=9 if self.is_compact else 10),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_res.pack(side="left", padx=(0, 4))

        if self.on_cell_fine_tune:
            btn_fine = ctk.CTkButton(
                hdr_actions,
                text="📐",
                width=18 if self.is_compact else 22,
                height=18 if self.is_compact else 22,
                corner_radius=4,
                fg_color="transparent",
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(size=9 if self.is_compact else 11),
                text_color=COLOR_TEXT_MUTED,
                command=lambda: self.on_cell_fine_tune(self.row, self.col)
            )
            btn_fine.pack(side="left", padx=(0, 2))

        if self.profile:
            btn_clear = ctk.CTkButton(
                hdr_actions,
                text="✕",
                width=18 if self.is_compact else 22,
                height=18 if self.is_compact else 22,
                corner_radius=4,
                fg_color="transparent",
                hover_color=COLOR_DANGER_HOVER,
                font=ctk.CTkFont(size=10 if self.is_compact else 11, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                command=lambda: self.on_cell_cleared(self.row, self.col)
            )
            btn_clear.pack(side="left")

        # Center Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        b_pad_y = 2 if self.is_compact else 4
        b_pad_x = 6 if self.is_compact else 10
        body.grid(row=1, column=0, sticky="nsew", padx=b_pad_x, pady=b_pad_y)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        if self.profile:
            center_box = ctk.CTkFrame(body, fg_color="transparent")
            center_box.pack(expand=True, fill="both")

            av_size = 28 if self.is_compact else 48
            avatar_img = AvatarCache.get_avatar(self.profile, size=av_size)
            av_lbl = ctk.CTkLabel(center_box, text="", image=avatar_img)
            av_lbl.pack(pady=(1, 2) if self.is_compact else (4, 4))

            # Display name
            name_size = 11 if self.is_compact else 13
            name_lbl = ctk.CTkLabel(
                center_box,
                text=self.profile.display_name,
                font=ctk.CTkFont(family="Segoe UI", size=name_size, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY
            )
            name_lbl.pack()

            # Group Badge Pill (if present)
            if self.profile.group_name:
                grp_pill = ctk.CTkLabel(
                    center_box,
                    text=self.profile.group_name,
                    font=ctk.CTkFont(family="Segoe UI", size=8 if self.is_compact else 10, weight="bold"),
                    text_color="#FFFFFF",
                    fg_color=self.profile.group_color or COLOR_GROUP_PRT,
                    corner_radius=3 if self.is_compact else 4,
                    padx=4 if self.is_compact else 6,
                    pady=0 if self.is_compact else 1
                )
                grp_pill.pack(pady=(1, 2) if self.is_compact else (2, 2))

            if not self.is_compact:
                key_lbl = ctk.CTkLabel(
                    center_box,
                    text=self.profile.key,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=COLOR_ACCENT
                )
                key_lbl.pack()

            if self.status_text:
                status_color = COLOR_SUCCESS if self.status_text == "Active" else COLOR_WARNING
                st_lbl = ctk.CTkLabel(
                    center_box,
                    text=f"● {self.status_text}",
                    font=ctk.CTkFont(family="Segoe UI", size=9 if self.is_compact else 10, weight="bold"),
                    text_color=status_color
                )
                st_lbl.pack(pady=(1, 0))

            # Bottom Change Button (Only in standard mode to save space in compact grids)
            if not self.is_compact:
                btn_change = ctk.CTkButton(
                    self,
                    text="Change Profile",
                    height=26,
                    corner_radius=6,
                    fg_color=COLOR_CARD_HOVER,
                    hover_color=COLOR_ACCENT,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=COLOR_TEXT_SECONDARY,
                    command=lambda: self.on_cell_change(self.row, self.col)
                )
                btn_change.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))

        else:
            empty_box = ctk.CTkFrame(body, fg_color="transparent")
            empty_box.pack(expand=True)

            plus_size = 20 if self.is_compact else 30
            plus_lbl = ctk.CTkLabel(
                empty_box,
                text="＋",
                font=ctk.CTkFont(size=plus_size, weight="bold"),
                text_color=COLOR_TEXT_MUTED
            )
            plus_lbl.pack(pady=(2, 0) if self.is_compact else (6, 0))

            if not self.is_compact:
                hint_lbl = ctk.CTkLabel(
                    empty_box,
                    text="Click or Drag Profile Here",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=COLOR_TEXT_MUTED
                )
                hint_lbl.pack()
            else:
                hint_lbl = ctk.CTkLabel(
                    empty_box,
                    text="Empty",
                    font=ctk.CTkFont(family="Segoe UI", size=9),
                    text_color=COLOR_TEXT_MUTED
                )
                hint_lbl.pack()

        # Bind clicks to cell frame
        self.bind("<Button-1>", lambda e: self.on_cell_clicked(self.row, self.col))
        body.bind("<Button-1>", lambda e: self.on_cell_clicked(self.row, self.col))

        if self.on_cell_fine_tune:
            self.bind("<Button-3>", lambda e: self.on_cell_fine_tune(self.row, self.col))
            body.bind("<Button-3>", lambda e: self.on_cell_fine_tune(self.row, self.col))

    def set_profile(self, profile: Optional[ChromeProfile], is_compact: Optional[bool] = None, cell_rect: Optional[Tuple[int, int, int, int]] = None):
        self.profile = profile
        if is_compact is not None:
            self.is_compact = is_compact
        if cell_rect is not None:
            self.cell_rect = cell_rect
        self.status_text = ""
        border_c = (profile.group_color or COLOR_BORDER_ACCENT) if profile else COLOR_BORDER
        self.configure(
            fg_color=COLOR_CARD_BG if profile else COLOR_EMPTY_CELL,
            border_color=border_c,
            border_width=2 if profile else 1
        )
        self._build_ui()

    def set_launch_status(self, text: str):
        self.status_text = text
        self._build_ui()


# ---------------------------------------------------------------------------
# Modal: Searchable Profile Selector
# ---------------------------------------------------------------------------
class ProfilePickerModal(ctk.CTkToplevel):
    """Searchable popup dialog to choose a profile for a cell."""

    def __init__(self, parent, profiles: List[ChromeProfile], on_chosen):
        super().__init__(parent)
        self.profiles = profiles
        self.on_chosen = on_chosen

        self.title("Select Chrome Profile")
        self.geometry("420x520")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color=COLOR_BG_DARK)

        lbl = ctk.CTkLabel(
            self,
            text="Choose Profile for Cell",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl.pack(pady=(16, 8), padx=16, anchor="w")

        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text="🔍 Search profiles...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER
        )
        self.search_entry.pack(fill="x", padx=16, pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._render_list(self.profiles)

    def _render_list(self, items: List[ChromeProfile]):
        for child in self.scroll.winfo_children():
            child.destroy()

        if not items:
            lbl = ctk.CTkLabel(
                self.scroll,
                text="No matching profiles found.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLOR_TEXT_MUTED
            )
            lbl.pack(pady=20)
            return

        for profile in items:
            card = ctk.CTkFrame(
                self.scroll,
                fg_color=COLOR_CARD_BG,
                corner_radius=8,
                border_width=1,
                border_color=COLOR_BORDER,
                cursor="hand2"
            )
            card.pack(fill="x", pady=3)
            card.grid_columnconfigure(1, weight=1)

            avatar_img = AvatarCache.get_avatar(profile, size=32)
            av_lbl = ctk.CTkLabel(card, text="", image=avatar_img)
            av_lbl.grid(row=0, column=0, rowspan=2, padx=(8, 8), pady=6)

            name_lbl = ctk.CTkLabel(
                card,
                text=profile.display_name,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            name_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))

            sub_lbl = ctk.CTkLabel(
                card,
                text=profile.subtitle,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            )
            sub_lbl.grid(row=1, column=1, sticky="w", pady=(0, 6))

            for w in [card, av_lbl, name_lbl, sub_lbl]:
                w.bind("<Button-1>", lambda e, p=profile: self._choose(p))

    def _on_search(self, event=None):
        q = self.search_entry.get().strip().lower()
        if not q:
            self._render_list(self.profiles)
        else:
            filtered = [
                p for p in self.profiles
                if q in p.name.lower() or q in p.key.lower() or q in p.email.lower() or q in p.gaia_name.lower()
            ]
            self._render_list(filtered)

    def _choose(self, profile: ChromeProfile):
        self.on_chosen(profile)
        self.destroy()


# ---------------------------------------------------------------------------
# Modal: Auto-Launch Tampermonkey Installer in Profiles
# ---------------------------------------------------------------------------
class InstallScriptProfilesModal(ctk.CTkToplevel):
    """Dialog allowing users to select specific profiles and automatically launch Chrome to open the Tampermonkey installer URL."""

    def __init__(
        self,
        parent,
        profiles: List[ChromeProfile],
        grid_assigned_profiles: List[ChromeProfile],
        chrome_exe: Optional[str],
        server_port: int,
        on_log: Optional[Callable[[str, str], None]] = None
    ):
        super().__init__(parent)
        self.profiles = profiles
        self.grid_assigned_profiles = grid_assigned_profiles
        self.chrome_exe = chrome_exe
        self.server_port = server_port
        self.on_log = on_log

        self.title("Auto-Open Script Installer in Profiles")
        self.geometry("520x670")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=COLOR_BG_DARK)

        # Default select grid assigned profiles if any, else all
        assigned_keys = {p.key for p in grid_assigned_profiles if p}
        if assigned_keys:
            self.selected_profile_keys = set(assigned_keys)
        else:
            self.selected_profile_keys = {p.key for p in profiles}

        self.checkbox_vars: Dict[str, tk.BooleanVar] = {}
        self.is_launching = False

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(18, 10))

        ctk.CTkLabel(
            hdr,
            text="🚀 Launch Installer in Specific Profiles",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w")

        ctk.CTkLabel(
            hdr,
            text=f"Launches Chrome profiles directly to http://127.0.0.1:{self.server_port}/userscript.user.js so Tampermonkey automatically displays the 1-click install prompt.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=475,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Selection Bar (Grid Assigned / All / Clear)
        sel_bar = ctk.CTkFrame(self, fg_color="transparent")
        sel_bar.pack(fill="x", padx=20, pady=(0, 8))

        assigned_count = len({p.key for p in self.grid_assigned_profiles if p})
        btn_sel_grid = ctk.CTkButton(
            sel_bar,
            text=f"Grid Assigned ({assigned_count})",
            height=28,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._select_grid_assigned
        )
        btn_sel_grid.pack(side="left", padx=(0, 6))

        btn_sel_all = ctk.CTkButton(
            sel_bar,
            text=f"All Profiles ({len(self.profiles)})",
            height=28,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._select_all
        )
        btn_sel_all.pack(side="left", padx=(0, 6))

        btn_sel_none = ctk.CTkButton(
            sel_bar,
            text="Clear",
            height=28,
            width=50,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._select_none
        )
        btn_sel_none.pack(side="left")

        self.lbl_selected_counter = ctk.CTkLabel(
            sel_bar,
            text=f"{len(self.selected_profile_keys)} selected",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_selected_counter.pack(side="right")

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text="🔍 Filter profiles...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            height=32,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER
        )
        self.search_entry.pack(fill="x", padx=20, pady=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Scrollable List of Profiles with Checkboxes
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_SIDEBAR_BG, corner_radius=10)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._render_profiles(self.profiles)

        # Options Row: Stagger delay
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(
            opt_frame,
            text="Launch Delay Between Profiles:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(side="left")

        self.opt_stagger = ctk.CTkOptionMenu(
            opt_frame,
            values=["500ms", "800ms (Recommended)", "1200ms", "2000ms"],
            width=170,
            height=28,
            fg_color=COLOR_SIDEBAR_BG,
            button_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11)
        )
        self.opt_stagger.set("800ms (Recommended)")
        self.opt_stagger.pack(side="right")

        # Reuse existing window toggle (avoids disrupting grid layout)
        self.chk_new_tab = ctk.CTkCheckBox(
            self,
            text="Open as new tab in existing window (keeps grid layout intact)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER
        )
        self.chk_new_tab.select()
        self.chk_new_tab.pack(padx=20, pady=(0, 8), anchor="w")

        # Progress bar + status label
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            progress_color=COLOR_SUCCESS,
            fg_color=COLOR_CARD_BG
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 4))
        self.progress_bar.pack_forget()

        self.lbl_status = ctk.CTkLabel(
            self,
            text=f"Ready to open installer in {len(self.selected_profile_keys)} profiles.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.lbl_status.pack(padx=20, pady=(0, 8), anchor="w")

        # Footer Buttons
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))

        self.btn_launch = ctk.CTkButton(
            footer,
            text="🚀 Open Installer in Selected Profiles",
            height=40,
            corner_radius=8,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFFFFF",
            command=self._start_launch
        )
        self.btn_launch.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn_close = ctk.CTkButton(
            footer,
            text="Close",
            width=85,
            height=40,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.destroy
        )
        btn_close.pack(side="right")

    def _render_profiles(self, profiles_to_show: List[ChromeProfile]):
        for child in self.scroll.winfo_children():
            child.destroy()

        for p in profiles_to_show:
            if p.key not in self.checkbox_vars:
                self.checkbox_vars[p.key] = tk.BooleanVar(value=(p.key in self.selected_profile_keys))

            var = self.checkbox_vars[p.key]

            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=4)
            row.grid_columnconfigure(1, weight=1)

            cb = ctk.CTkCheckBox(
                row,
                text=p.display_name,
                variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER,
                command=lambda k=p.key, v=var: self._on_checkbox_toggle(k, v)
            )
            cb.grid(row=0, column=0, sticky="w", padx=(4, 8), pady=3)

            meta = f"[{p.key}]" + (f"  •  {p.group_name}" if p.group_name else "")
            ctk.CTkLabel(
                row,
                text=meta,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLOR_TEXT_MUTED
            ).grid(row=0, column=1, sticky="e", padx=(0, 4))

    def _on_checkbox_toggle(self, key: str, var: tk.BooleanVar):
        if var.get():
            self.selected_profile_keys.add(key)
        else:
            self.selected_profile_keys.discard(key)
        self._update_counter()

    def _update_counter(self):
        count = len(self.selected_profile_keys)
        self.lbl_selected_counter.configure(text=f"{count} selected")
        if not self.is_launching:
            self.lbl_status.configure(text=f"Ready to open installer in {count} profiles.")

    def _select_grid_assigned(self):
        assigned_keys = {p.key for p in self.grid_assigned_profiles if p}
        self.selected_profile_keys = set(assigned_keys)
        for k, var in self.checkbox_vars.items():
            var.set(k in self.selected_profile_keys)
        self._update_counter()

    def _select_all(self):
        self.selected_profile_keys = {p.key for p in self.profiles}
        for var in self.checkbox_vars.values():
            var.set(True)
        self._update_counter()

    def _select_none(self):
        self.selected_profile_keys.clear()
        for var in self.checkbox_vars.values():
            var.set(False)
        self._update_counter()

    def _on_search(self, event=None):
        q = self.search_entry.get().strip().lower()
        if not q:
            self._render_profiles(self.profiles)
        else:
            filtered = [
                p for p in self.profiles
                if q in p.name.lower() or q in p.key.lower() or q in (p.group_name or "").lower()
            ]
            self._render_profiles(filtered)

    def _start_launch(self):
        if self.is_launching:
            return

        if not self.chrome_exe or not os.path.exists(self.chrome_exe):
            messagebox.showerror("Error", "Chrome executable not found. Please check your path in Settings (⚙️).")
            return

        selected = [p for p in self.profiles if p.key in self.selected_profile_keys]
        if not selected:
            messagebox.showwarning("No Profiles Selected", "Please select at least one Chrome profile to launch.")
            return

        # Parse stagger delay
        val = self.opt_stagger.get()
        m = re.search(r"(\d+)ms", val)
        delay_ms = int(m.group(1)) if m else 800

        self.is_launching = True
        self.btn_launch.configure(state="disabled", text="Opening Chrome Profiles...")
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 4))
        self.progress_bar.set(0)

        threading.Thread(target=self._launch_worker, args=(selected, delay_ms), daemon=True).start()

    def _launch_worker(self, targets: List[ChromeProfile], delay_ms: int):
        total = len(targets)
        url = f"http://127.0.0.1:{self.server_port}/userscript.user.js"
        use_existing = getattr(self, "chk_new_tab", None) is not None and self.chk_new_tab.get()

        for idx, profile in enumerate(targets, start=1):
            progress_val = (idx - 1) / total
            self.after(0, lambda v=progress_val, n=profile.display_name, i=idx: self._update_ui_progress(
                v, f"Opening ({i}/{total}): {n}..."
            ))

            if use_existing:
                # Omit --new-window so Chrome routes to the already-open window for this profile
                cmd = [self.chrome_exe, f"--profile-directory={profile.key}", url]
            else:
                cmd = [self.chrome_exe, f"--profile-directory={profile.key}", "--new-window", url] + CHROME_PERF_FLAGS
            try:
                subprocess.Popen(cmd)
                if self.on_log:
                    self.on_log(f"Opened installer URL in profile '{profile.display_name}' [{profile.key}] (existing window: {use_existing})", "INFO")
            except Exception as e:
                if self.on_log:
                    self.on_log(f"Failed to launch profile '{profile.display_name}': {e}", "ERROR")

            time.sleep(delay_ms / 1000.0)

        self.after(0, lambda: self._finish_launch(total))

    def _update_ui_progress(self, val: float, text: str):
        self.progress_bar.set(val)
        self.lbl_status.configure(text=text)

    def _finish_launch(self, total: int):
        self.is_launching = False
        self.progress_bar.set(1.0)
        self.lbl_status.configure(
            text=f"✅ Opened installer in {total} profiles! Click 'Install' on each Tampermonkey prompt."
        )
        self.btn_launch.configure(state="normal", text="🚀 Open Again in Selected Profiles")


# ---------------------------------------------------------------------------
# Modal: Create or Edit Custom Profile Group
# ---------------------------------------------------------------------------
class NewGroupModal(ctk.CTkToplevel):
    """Dialog to create or edit a custom profile group."""

    def __init__(
        self,
        parent,
        profiles: Optional[List[ChromeProfile]] = None,
        on_save: Optional[Callable] = None,
        existing_group: Optional[Any] = None,
        all_profiles: Optional[List[ChromeProfile]] = None,
        on_save_group: Optional[Callable] = None
    ):
        super().__init__(parent)
        self.profiles = profiles if profiles is not None else (all_profiles or [])
        self.on_save = on_save or on_save_group
        self.existing_group = existing_group

        if existing_group:
            if isinstance(existing_group, dict):
                group_name = existing_group.get("name", "")
                group_color = existing_group.get("color", "#8B5CF6")
                initial_keys = set(existing_group.get("profile_keys", []))
            else:
                group_name = getattr(existing_group, "name", "")
                group_color = getattr(existing_group, "color", "#8B5CF6")
                initial_keys = set(getattr(existing_group, "profile_keys", []))
        else:
            group_name = ""
            group_color = "#8B5CF6"
            initial_keys = set()

        self.title("New Profile Group" if not existing_group else f"Edit Group — {group_name}")
        self.geometry("480x600")
        self.minsize(440, 500)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=COLOR_BG_DARK)

        self.selected_keys = set(initial_keys)
        self.chosen_color = group_color

        lbl_title = ctk.CTkLabel(
            self,
            text="✨ Create New Profile Group" if not existing_group else "✏️ Edit Profile Group",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_title.pack(pady=(16, 6), padx=20, anchor="w")

        lbl_name = ctk.CTkLabel(self, text="Group Name:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
        lbl_name.pack(padx=20, anchor="w", pady=(6, 2))

        self.entry_name = ctk.CTkEntry(
            self,
            placeholder_text="e.g. Trading Accounts, Batch 1, Work",
            font=ctk.CTkFont(size=12),
            height=34,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_BORDER
        )
        if group_name:
            self.entry_name.insert(0, group_name)
        self.entry_name.pack(fill="x", padx=20, pady=(0, 10))

        lbl_col = ctk.CTkLabel(self, text="Group Color:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
        lbl_col.pack(padx=20, anchor="w", pady=(0, 4))

        color_row = ctk.CTkFrame(self, fg_color="transparent")
        color_row.pack(fill="x", padx=20, pady=(0, 10))

        self.color_buttons = []
        palette = ["#8B5CF6", "#10B981", "#3B82F6", "#EC4899", "#F59E0B", "#06B6D4", "#EF4444", "#84CC16"]
        for c in palette:
            b = ctk.CTkButton(
                color_row,
                text="",
                width=28,
                height=28,
                corner_radius=14,
                fg_color=c,
                hover_color=c,
                border_width=3 if c == self.chosen_color else 0,
                border_color="#FFFFFF" if c == self.chosen_color else "transparent",
                command=lambda col=c: self._pick_color(col)
            )
            b.pack(side="left", padx=3)
            self.color_buttons.append((b, c))

        p_header = ctk.CTkFrame(self, fg_color="transparent")
        p_header.pack(fill="x", padx=20, pady=(4, 4))

        ctk.CTkLabel(
            p_header,
            text="Assign Profiles to Group:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(side="left")

        self.lbl_selected_count = ctk.CTkLabel(
            p_header,
            text=f"{len(self.selected_keys)} selected",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_selected_count.pack(side="right")

        btn_sel_all = ctk.CTkButton(
            p_header,
            text="All",
            width=36,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            command=self._select_all
        )
        btn_sel_all.pack(side="right", padx=(0, 6))

        btn_sel_none = ctk.CTkButton(
            p_header,
            text="None",
            width=42,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            command=self._select_none
        )
        btn_sel_none.pack(side="right", padx=(0, 4))

        self.search_entry = ctk.CTkEntry(
            self,
            placeholder_text="🔍 Filter profiles...",
            font=ctk.CTkFont(size=11),
            height=28,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_BORDER
        )
        self.search_entry.pack(fill="x", padx=20, pady=(0, 6))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.scroll_profiles = ctk.CTkScrollableFrame(self, fg_color=COLOR_SIDEBAR_BG, corner_radius=10, height=200)
        self.scroll_profiles.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        self.checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self._render_profile_checkboxes(self.profiles)

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_HOVER, command=self.destroy)
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 8))

        btn_save = ctk.CTkButton(btn_box, text="💾 Save Group", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, font=ctk.CTkFont(weight="bold"), command=self._save)
        btn_save.pack(side="right", expand=True, fill="x", padx=(8, 0))

    def _pick_color(self, color: str):
        self.chosen_color = color
        for b, c in self.color_buttons:
            if c == color:
                b.configure(border_width=3, border_color="#FFFFFF")
            else:
                b.configure(border_width=0, border_color="transparent")

    def _select_all(self):
        for p in self.profiles:
            self.selected_keys.add(p.key)
            if p.key in self.checkboxes:
                self.checkboxes[p.key].select()
        self.lbl_selected_count.configure(text=f"{len(self.selected_keys)} selected")

    def _select_none(self):
        self.selected_keys.clear()
        for p in self.profiles:
            if p.key in self.checkboxes:
                self.checkboxes[p.key].deselect()
        self.lbl_selected_count.configure(text=f"{len(self.selected_keys)} selected")

    def _on_check_toggle(self, key: str, is_checked: bool):
        if is_checked:
            self.selected_keys.add(key)
        else:
            self.selected_keys.discard(key)
        self.lbl_selected_count.configure(text=f"{len(self.selected_keys)} selected")

    def _render_profile_checkboxes(self, profile_list: List[ChromeProfile]):
        for child in self.scroll_profiles.winfo_children():
            child.destroy()
        self.checkboxes.clear()

        for p in profile_list:
            row = ctk.CTkFrame(self.scroll_profiles, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=4)

            cb = ctk.CTkCheckBox(
                row,
                text=f"{p.display_name}  ({p.key})",
                font=ctk.CTkFont(size=12),
                fg_color=self.chosen_color,
                hover_color=self.chosen_color,
                command=lambda k=p.key: self._on_check_toggle(k, self.checkboxes[k].get() == 1)
            )
            cb.pack(side="left", fill="x", expand=True)
            if p.key in self.selected_keys:
                cb.select()
            else:
                cb.deselect()
            self.checkboxes[p.key] = cb

    def _on_search(self, event=None):
        q = self.search_entry.get().strip().lower()
        if not q:
            self._render_profile_checkboxes(self.profiles)
        else:
            filtered = [
                p for p in self.profiles
                if q in p.name.lower() or q in p.key.lower() or q in p.email.lower() or q in p.gaia_name.lower()
            ]
            self._render_profile_checkboxes(filtered)

    def _save(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a name for the group.", parent=self)
            return

        if self.existing_group:
            if isinstance(self.existing_group, ProfileGroup):
                self.existing_group.name = name
                self.existing_group.color = self.chosen_color
                self.existing_group.profile_keys = list(self.selected_keys)
                group_obj = self.existing_group
            elif isinstance(self.existing_group, dict):
                group_obj = ProfileGroup(
                    id=self.existing_group.get("id", f"grp_{int(time.time()*1000)}"),
                    name=name,
                    color=self.chosen_color,
                    profile_keys=list(self.selected_keys)
                )
            else:
                group_obj = ProfileGroup(
                    id=getattr(self.existing_group, "id", f"grp_{int(time.time()*1000)}"),
                    name=name,
                    color=self.chosen_color,
                    profile_keys=list(self.selected_keys)
                )
        else:
            group_obj = ProfileGroup(
                id=f"grp_{int(time.time()*1000)}",
                name=name,
                color=self.chosen_color,
                profile_keys=list(self.selected_keys)
            )

        if self.on_save:
            try:
                import inspect
                sig = inspect.signature(self.on_save)
                if len(sig.parameters) == 1:
                    self.on_save(group_obj)
                else:
                    self.on_save(name, self.chosen_color, list(self.selected_keys))
            except Exception:
                try:
                    self.on_save(group_obj)
                except TypeError:
                    self.on_save(name, self.chosen_color, list(self.selected_keys))

        self.destroy()


# ---------------------------------------------------------------------------
# Modal: Assign Profile to Group
# ---------------------------------------------------------------------------
class AssignGroupModal(ctk.CTkToplevel):
    """Quick modal to assign a profile to an existing custom group or remove it."""

    def __init__(
        self,
        parent,
        profile: ChromeProfile,
        custom_groups: List[Any],
        on_assigned: Optional[Callable[[ChromeProfile, Optional[str]], None]] = None,
        on_assign: Optional[Callable[[ChromeProfile, Optional[str]], None]] = None,
        on_create_new: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.profile = profile
        self.custom_groups = custom_groups
        self.on_assign_callback = on_assigned or on_assign
        self.on_create_new = on_create_new

        self.title(f"Group — {profile.display_name}")
        self.geometry("400x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=COLOR_BG_DARK)

        lbl = ctk.CTkLabel(
            self,
            text=f"Assign '{profile.display_name}' to Group",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl.pack(pady=(16, 4), padx=20, anchor="w")

        curr_text = f"Current Group: {profile.group_name or 'Default'}"
        ctk.CTkLabel(self, text=curr_text, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor="w", pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_CARD_BG, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        # Auto-detect button
        btn_auto = ctk.CTkButton(
            scroll,
            text="↺ Auto Group (Rule-based detection)",
            anchor="w",
            height=34,
            corner_radius=6,
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_ACCENT,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=lambda: self._choose("auto")
        )
        btn_auto.pack(fill="x", pady=(2, 6))

        # System Groups Section
        ctk.CTkLabel(
            scroll,
            text="SYSTEM GROUPS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=4, pady=(8, 4))

        system_groups = [
            (GroupManager.GROUP_NUMBERS, "🔢 Numbers (0-99 Profiles)", COLOR_GROUP_NUMBERS),
            (GroupManager.GROUP_PRT, "🏷️ PRT (PRT Suffix Profiles)", COLOR_GROUP_PRT),
            (GroupManager.GROUP_OTHER, "📁 Other (Personal Profiles)", COLOR_GROUP_OTHER),
        ]

        for sg_id, sg_label, sg_color in system_groups:
            is_current = (self.profile.group_id == sg_id)
            btn_sg = ctk.CTkButton(
                scroll,
                text=f"{sg_label}{' (Active)' if is_current else ''}",
                anchor="w",
                height=34,
                corner_radius=6,
                fg_color=COLOR_ACCENT if is_current else COLOR_CARD_HOVER,
                hover_color=sg_color,
                border_width=1 if is_current else 0,
                border_color=sg_color if is_current else COLOR_BORDER,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                command=lambda gid=sg_id: self._choose(gid)
            )
            btn_sg.pack(fill="x", pady=2)

        # Custom Groups Section
        ctk.CTkLabel(
            scroll,
            text="CUSTOM GROUPS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=4, pady=(12, 4))

        if not custom_groups:
            ctk.CTkLabel(
                scroll,
                text="No custom groups created yet.\nClick '➕ Create New Group' below.",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_MUTED,
                justify="left"
            ).pack(anchor="w", padx=8, pady=4)
        else:
            for cg in custom_groups:
                c_id = _get_cg_attr(cg, "id")
                c_name = _get_cg_attr(cg, "name")
                c_color = _get_cg_attr(cg, "color", "#3B82F6")
                is_current = (self.profile.group_id == c_id)
                b = ctk.CTkButton(
                    scroll,
                    text=f"📁 {c_name}{' (Active)' if is_current else ''}",
                    anchor="w",
                    height=34,
                    corner_radius=6,
                    fg_color=COLOR_ACCENT if is_current else COLOR_CARD_HOVER,
                    hover_color=c_color,
                    border_width=1 if is_current else 0,
                    border_color=c_color if is_current else COLOR_BORDER,
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                    command=lambda cid=c_id: self._choose(cid)
                )
                b.pack(fill="x", pady=2)

        btn_new = ctk.CTkButton(
            self,
            text="➕ Create New Group...",
            height=34,
            corner_radius=8,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._create_new
        )
        btn_new.pack(fill="x", padx=20, pady=(0, 14))

    def _choose(self, group_id: str):
        if self.on_assign_callback:
            try:
                self.on_assign_callback(self.profile, group_id)
            except TypeError:
                self.on_assign_callback(self.profile.key, group_id)
        self.destroy()

    def _create_new(self):
        self.destroy()
        if self.on_create_new:
            self.on_create_new()


# ---------------------------------------------------------------------------
# Modal: Save Layout Preset
# ---------------------------------------------------------------------------
class SaveLayoutModal(ctk.CTkToplevel):
    def __init__(self, parent, default_name: str, on_save):
        super().__init__(parent)
        self.on_save = on_save

        self.title("Save Grid Layout")
        self.geometry("380x190")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color=COLOR_BG_DARK)

        lbl = ctk.CTkLabel(
            self,
            text="Save Current Layout Preset",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl.pack(pady=(20, 8), padx=16, anchor="w")

        self.entry = ctk.CTkEntry(
            self,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=36,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER
        )
        self.entry.insert(0, default_name)
        self.entry.pack(fill="x", padx=16, pady=(0, 18))
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._submit())

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=16)

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            command=self.destroy
        )
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 6))

        btn_confirm = ctk.CTkButton(
            btn_box,
            text="Save Layout",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._submit
        )
        btn_confirm.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _submit(self):
        name = self.entry.get().strip()
        if name:
            self.on_save(name)
            self.destroy()


# ---------------------------------------------------------------------------
# Modal: Load Layout Presets
# ---------------------------------------------------------------------------
class LoadLayoutModal(ctk.CTkToplevel):
    def __init__(self, parent, on_load_layout):
        super().__init__(parent)
        self.on_load_layout = on_load_layout

        self.title("Load Grid Layout")
        self.geometry("480x460")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color=COLOR_BG_DARK)

        lbl = ctk.CTkLabel(
            self,
            text="Saved Layout Presets",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl.pack(pady=(16, 10), padx=16, anchor="w")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._refresh()

    def _refresh(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        layouts = ConfigManager.list_saved_layouts()
        if not layouts:
            empty_lbl = ctk.CTkLabel(
                self.scroll,
                text="No saved presets found yet.\nUse 'Save Layout' to store your custom arrangements.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLOR_TEXT_MUTED
            )
            empty_lbl.pack(pady=40)
            return

        for item in layouts:
            card = ctk.CTkFrame(
                self.scroll,
                fg_color=COLOR_CARD_BG,
                corner_radius=10,
                border_width=1,
                border_color=COLOR_BORDER
            )
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(0, weight=1)

            name = item.get("name", "Unnamed")
            rows = item.get("rows", 2)
            cols = item.get("cols", 2)
            date_str = item.get("updated_at", "")
            assigned_count = len(item.get("assignments", {}))

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
            top_row.grid_columnconfigure(0, weight=1)

            lbl_name = ctk.CTkLabel(
                top_row,
                text=f"{name}",
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_name.grid(row=0, column=0, sticky="w")

            badge = ctk.CTkLabel(
                top_row,
                text=f"{cols}×{rows} Grid • {assigned_count} Assigned",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLOR_ACCENT
            )
            badge.grid(row=0, column=1, sticky="e")

            if date_str:
                lbl_date = ctk.CTkLabel(
                    card,
                    text=f"Saved: {date_str}",
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w"
                )
                lbl_date.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

            btn_load = ctk.CTkButton(
                btn_row,
                text="Load Layout",
                height=28,
                corner_radius=6,
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda d=item: self._select_layout(d)
            )
            btn_load.pack(side="left", padx=(0, 8))

            btn_del = ctk.CTkButton(
                btn_row,
                text="Delete",
                width=60,
                height=28,
                corner_radius=6,
                fg_color=COLOR_CARD_HOVER,
                hover_color=COLOR_DANGER_HOVER,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
                command=lambda p=item.get("_filepath", ""): self._delete_layout(p)
            )
            btn_del.pack(side="left")

    def _select_layout(self, data: Dict[str, Any]):
        self.on_load_layout(data)
        self.destroy()

    def _delete_layout(self, filepath: str):
        if filepath:
            ConfigManager.delete_layout_file(filepath)
            self._refresh()


# ---------------------------------------------------------------------------
# Modal: Custom Grid Dimensions
# ---------------------------------------------------------------------------
class CustomGridModal(ctk.CTkToplevel):
    def __init__(self, parent, current_rows: int, current_cols: int, on_apply):
        super().__init__(parent)
        self.on_apply = on_apply
        self.current_rows = current_rows
        self.current_cols = current_cols

        self.title("Custom Grid Dimensions (Up to 50)")
        self.geometry("460x470")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color=COLOR_BG_DARK)

        lbl_title = ctk.CTkLabel(
            self,
            text="Set Custom Grid Size (Up to 50)",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_title.pack(pady=(18, 10), padx=20, anchor="w")

        # Main Card Container
        f_card = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=12)
        f_card.pack(fill="x", padx=20, pady=(0, 12))

        # Columns Section
        col_box = ctk.CTkFrame(f_card, fg_color="transparent")
        col_box.pack(fill="x", padx=16, pady=(12, 6))
        col_box.grid_columnconfigure(1, weight=1)

        lbl_col_title = ctk.CTkLabel(
            col_box,
            text="Columns (Across):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_col_title.grid(row=0, column=0, sticky="w")

        col_ctrl = ctk.CTkFrame(col_box, fg_color="transparent")
        col_ctrl.grid(row=0, column=1, sticky="e")

        btn_col_m5 = ctk.CTkButton(
            col_ctrl, text="-5", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: self._adjust_cols(-5)
        )
        btn_col_m5.pack(side="left", padx=1)

        btn_col_m1 = ctk.CTkButton(
            col_ctrl, text="–", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._adjust_cols(-1)
        )
        btn_col_m1.pack(side="left", padx=1)

        self.entry_cols = ctk.CTkEntry(
            col_ctrl, width=54, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER,
            justify="center"
        )
        self.entry_cols.insert(0, str(self.current_cols))
        self.entry_cols.pack(side="left", padx=4)
        self.entry_cols.bind("<KeyRelease>", self._on_entry_changed)

        btn_col_p1 = ctk.CTkButton(
            col_ctrl, text="+", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._adjust_cols(1)
        )
        btn_col_p1.pack(side="left", padx=1)

        btn_col_p5 = ctk.CTkButton(
            col_ctrl, text="+5", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: self._adjust_cols(5)
        )
        btn_col_p5.pack(side="left", padx=1)

        # Rows Section
        row_box = ctk.CTkFrame(f_card, fg_color="transparent")
        row_box.pack(fill="x", padx=16, pady=(6, 12))
        row_box.grid_columnconfigure(1, weight=1)

        lbl_row_title = ctk.CTkLabel(
            row_box,
            text="Rows (Down):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_row_title.grid(row=0, column=0, sticky="w")

        row_ctrl = ctk.CTkFrame(row_box, fg_color="transparent")
        row_ctrl.grid(row=0, column=1, sticky="e")

        btn_row_m5 = ctk.CTkButton(
            row_ctrl, text="-5", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: self._adjust_rows(-5)
        )
        btn_row_m5.pack(side="left", padx=1)

        btn_row_m1 = ctk.CTkButton(
            row_ctrl, text="–", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._adjust_rows(-1)
        )
        btn_row_m1.pack(side="left", padx=1)

        self.entry_rows = ctk.CTkEntry(
            row_ctrl, width=54, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER,
            justify="center"
        )
        self.entry_rows.insert(0, str(self.current_rows))
        self.entry_rows.pack(side="left", padx=4)
        self.entry_rows.bind("<KeyRelease>", self._on_entry_changed)

        btn_row_p1 = ctk.CTkButton(
            row_ctrl, text="+", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: self._adjust_rows(1)
        )
        btn_row_p1.pack(side="left", padx=1)

        btn_row_p5 = ctk.CTkButton(
            row_ctrl, text="+5", width=30, height=32, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: self._adjust_rows(5)
        )
        btn_row_p5.pack(side="left", padx=1)

        # Quick Large Presets
        f_presets = ctk.CTkFrame(self, fg_color="transparent")
        f_presets.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            f_presets,
            text="Presets:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        large_presets = [
            ("5×5 (25)", 5, 5),
            ("7×7 (49)", 7, 7),
            ("10×5 (50)", 5, 10),
            ("5×10 (50)", 10, 5)
        ]
        for lbl, r, c in large_presets:
            b = ctk.CTkButton(
                f_presets,
                text=lbl,
                height=26,
                corner_radius=6,
                fg_color=COLOR_CARD_BG,
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
                command=lambda rows=r, cols=c: self._set_dimensions(rows, cols)
            )
            b.pack(side="left", padx=2)

        # Summary Badge
        self.summary_card = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR_BG, corner_radius=8)
        self.summary_card.pack(fill="x", padx=20, pady=(0, 16))

        self.lbl_summary = ctk.CTkLabel(
            self.summary_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_SUCCESS
        )
        self.lbl_summary.pack(pady=8)
        self._update_summary()

        # Buttons
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=20)

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            height=36,
            corner_radius=8,
            command=self.destroy
        )
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 6))

        btn_apply = ctk.CTkButton(
            btn_box,
            text="Apply Grid Layout",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._submit
        )
        btn_apply.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _set_dimensions(self, rows: int, cols: int):
        self.current_rows = max(1, min(50, rows))
        self.current_cols = max(1, min(50, cols))
        self.entry_cols.delete(0, "end")
        self.entry_cols.insert(0, str(self.current_cols))
        self.entry_rows.delete(0, "end")
        self.entry_rows.insert(0, str(self.current_rows))
        self._update_summary()

    def _adjust_cols(self, delta: int):
        self._read_entries()
        self.current_cols = max(1, min(50, self.current_cols + delta))
        self.entry_cols.delete(0, "end")
        self.entry_cols.insert(0, str(self.current_cols))
        self._update_summary()

    def _adjust_rows(self, delta: int):
        self._read_entries()
        self.current_rows = max(1, min(50, self.current_rows + delta))
        self.entry_rows.delete(0, "end")
        self.entry_rows.insert(0, str(self.current_rows))
        self._update_summary()

    def _on_entry_changed(self, event=None):
        self._read_entries()
        self._update_summary()

    def _read_entries(self):
        try:
            c = int(self.entry_cols.get().strip())
            self.current_cols = max(1, min(50, c))
        except Exception:
            pass
        try:
            r = int(self.entry_rows.get().strip())
            self.current_rows = max(1, min(50, r))
        except Exception:
            pass

    def _update_summary(self):
        total = self.current_rows * self.current_cols
        self.lbl_summary.configure(text=f"Total: {total} Windows ({self.current_cols} Columns × {self.current_rows} Rows)")

    def _submit(self):
        self._read_entries()
        self.on_apply(self.current_rows, self.current_cols)
        self.destroy()


# ---------------------------------------------------------------------------
# Modal: Screen Fit & Fine Positioning Calibration Tool
# ---------------------------------------------------------------------------
class FineControlModal(ctk.CTkToplevel):
    """Provides precision control over cell positioning, full-screen coverage,
    margins, inter-window gap, DWM invisible border compensation, and per-cell offsets.
    """

    def __init__(
        self,
        parent,
        settings: Dict[str, Any],
        monitors: List[MonitorInfo],
        current_rows: int,
        current_cols: int,
        grid_assignments: Dict[Tuple[int, int], Optional[ChromeProfile]],
        on_apply,
        on_test_position,
        initial_selected_cell: Optional[Tuple[int, int]] = None
    ):
        super().__init__(parent)
        self.parent_app = parent
        self.settings = dict(settings)
        self.monitors = monitors
        self.current_rows = max(1, current_rows)
        self.current_cols = max(1, current_cols)
        self.grid_assignments = grid_assignments
        self.on_apply = on_apply
        self.on_test_position = on_test_position

        self.title("📐 Screen Fit & Fine Positioning Calibration")
        self.geometry("880x850")
        self.minsize(820, 780)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=COLOR_BG_DARK)

        # Working state copies
        self.selected_mon_idx = min(self.settings.get("monitor_index", 0), max(0, len(self.monitors) - 1))
        self.use_full_screen = bool(self.settings.get("use_full_screen", False))
        self.margins = dict(self.settings.get("screen_margins", {"top": 0, "bottom": 0, "left": 0, "right": 0}))
        for k in ("top", "bottom", "left", "right"):
            if k not in self.margins:
                self.margins[k] = 0
        self.gap = int(self.settings.get("cell_gap", 4))
        self.dwm_compensation = bool(self.settings.get("dwm_compensation", True))
        self.dwm_border_offset = int(self.settings.get("dwm_border_offset", 7))
        self.cell_offsets: Dict[str, Dict[str, int]] = {
            k: dict(v) for k, v in self.settings.get("cell_offsets", {}).items()
        }
        self.col_weights: List[float] = list(self.settings.get("col_weights", []))
        self.row_weights: List[float] = list(self.settings.get("row_weights", []))

        self.active_cell = initial_selected_cell if initial_selected_cell is not None else (0, 0)
        self.link_margins = tk.BooleanVar(value=True)

        # Dictionary to store entries for programmatic update
        self.margin_entries: Dict[str, ctk.CTkEntry] = {}
        self.offset_entries: Dict[str, ctk.CTkEntry] = {}

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=22, pady=(16, 6))

        title_lbl = ctk.CTkLabel(
            hdr_frame,
            text="📐 Screen Fit & Fine Positioning Calibration",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            hdr_frame,
            text="Maximize screen coverage, customize margins, eliminate invisible border gaps, and fine-tune every window.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Top Bar: Monitor Selection & Quick Coverage Presets
        bar_f = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=10)
        bar_f.pack(fill="x", padx=22, pady=(4, 10))

        mon_frame = ctk.CTkFrame(bar_f, fg_color="transparent")
        mon_frame.pack(side="left", padx=12, pady=8)

        ctk.CTkLabel(
            mon_frame,
            text="Target Display:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        mon_names = [m.display_label for m in self.monitors]
        cur_mon_label = mon_names[self.selected_mon_idx] if mon_names else "Monitor 1"
        self.opt_mon = ctk.CTkOptionMenu(
            mon_frame,
            values=mon_names,
            width=210,
            height=30,
            fg_color=COLOR_SIDEBAR_BG,
            button_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._on_monitor_changed
        )
        self.opt_mon.set(cur_mon_label)
        self.opt_mon.pack(side="left")

        # Quick Preset Buttons
        presets_bar = ctk.CTkFrame(bar_f, fg_color="transparent")
        presets_bar.pack(side="right", padx=12, pady=8)

        ctk.CTkLabel(
            presets_bar,
            text="Quick Presets:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        btn_preset_full = ctk.CTkButton(
            presets_bar,
            text="⚡ Full Screen (100%)",
            width=134,
            height=28,
            corner_radius=6,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._apply_preset_fullscreen
        )
        btn_preset_full.pack(side="left", padx=3)

        btn_preset_work = ctk.CTkButton(
            presets_bar,
            text="🖥️ Work Area",
            width=96,
            height=28,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._apply_preset_workarea
        )
        btn_preset_work.pack(side="left", padx=3)

        btn_reset_offsets = ctk.CTkButton(
            presets_bar,
            text="🔄 Clear Offsets",
            width=100,
            height=28,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_DANGER_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._reset_all_offsets
        )
        btn_reset_offsets.pack(side="left", padx=3)

        # Interactive Monitor Preview Canvas
        self.preview_card = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=12)
        self.preview_card.pack(fill="x", padx=22, pady=(0, 10))

        prev_header = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        prev_header.pack(fill="x", padx=14, pady=(8, 4))

        self.lbl_preview_info = ctk.CTkLabel(
            prev_header,
            text="Physical Screen Map (Click any cell to inspect & calibrate):",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.lbl_preview_info.pack(side="left")

        self.lbl_active_cell_badge = ctk.CTkLabel(
            prev_header,
            text=f"Selected: Cell [R{self.active_cell[0]+1}, C{self.active_cell[1]+1}]",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_active_cell_badge.pack(side="right")

        self.canvas_w = 830
        self.canvas_h = 160
        self.canvas = tk.Canvas(
            self.preview_card,
            bg="#0B0E14",
            width=self.canvas_w,
            height=self.canvas_h,
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(padx=14, pady=(0, 10))
        self.canvas.bind("<Button-1>", self._on_canvas_clicked)

        # Tabview for Configuration Controls
        self.tab_view = ctk.CTkTabview(self, fg_color=COLOR_CARD_BG, corner_radius=12)
        self.tab_view.pack(fill="both", expand=True, padx=22, pady=(0, 10))

        tab_margins = self.tab_view.add("📺 Screen & Margins")
        tab_gap = self.tab_view.add("⚡ Gap & Border Snap")
        tab_cell = self.tab_view.add("🎯 Per-Cell Offsets")
        tab_weights = self.tab_view.add("📊 Column/Row Proportions")

        self._build_tab_margins(tab_margins)
        self._build_tab_gap(tab_gap)
        self._build_tab_cell_offsets(tab_cell)
        self._build_tab_weights(tab_weights)

        # Bottom Action Bar
        bottom_bar = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR_BG, corner_radius=10, height=52)
        bottom_bar.pack(fill="x", padx=22, pady=(0, 16))

        btn_test = ctk.CTkButton(
            bottom_bar,
            text="📐 Test Live Placement",
            width=165,
            height=34,
            corner_radius=8,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._test_placement
        )
        btn_test.pack(side="left", padx=12, pady=8)

        lbl_test_hint = ctk.CTkLabel(
            bottom_bar,
            text="Snap open Chrome windows to these exact coordinates now to preview fit.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_test_hint.pack(side="left", padx=4)

        btn_apply = ctk.CTkButton(
            bottom_bar,
            text="💾 Apply & Save",
            width=130,
            height=34,
            corner_radius=8,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFFFFF",
            command=self._submit
        )
        btn_apply.pack(side="right", padx=12, pady=8)

        btn_cancel = ctk.CTkButton(
            bottom_bar,
            text="Cancel",
            width=80,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(0, 4))

        self._draw_preview()

    # -----------------------------------------------------------------------
    # Tab 1: Screen & Margins
    # -----------------------------------------------------------------------
    def _build_tab_margins(self, tab):
        # Screen Coverage Mode
        cov_f = ctk.CTkFrame(tab, fg_color="transparent")
        cov_f.pack(fill="x", padx=12, pady=(8, 12))

        ctk.CTkLabel(
            cov_f,
            text="Display Coverage Mode:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(0, 14))

        modes = ["🖥️ Work Area (Avoid Taskbar)", "📺 Full Display (100% Edge-to-Edge)"]
        cur_mode = modes[1] if self.use_full_screen else modes[0]
        self.seg_mode = ctk.CTkSegmentedButton(
            cov_f,
            values=modes,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._on_coverage_mode_changed
        )
        self.seg_mode.set(cur_mode)
        self.seg_mode.pack(side="left")

        # Outer Margins
        sep = ctk.CTkFrame(tab, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=(0, 10))

        hdr_m = ctk.CTkFrame(tab, fg_color="transparent")
        hdr_m.pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkLabel(
            hdr_m,
            text="Outer Screen Margins / Edge Insets (pixels):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        chk_link = ctk.CTkCheckBox(
            hdr_m,
            text="🔗 Link All 4 Edges (Uniform)",
            variable=self.link_margins,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY
        )
        chk_link.pack(side="right")

        margins_grid = ctk.CTkFrame(tab, fg_color="transparent")
        margins_grid.pack(fill="x", padx=12, pady=4)
        margins_grid.grid_columnconfigure((0, 1), weight=1)

        # Top & Bottom (Left Column)
        col_left = ctk.CTkFrame(margins_grid, fg_color="transparent")
        col_left.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        self.margin_entries["top"] = self._create_stepper(
            col_left, "Top Margin:",
            get_val=lambda: self.margins["top"],
            set_val=lambda v: self._set_margin("top", v)
        )
        self.margin_entries["bottom"] = self._create_stepper(
            col_left, "Bottom Margin:",
            get_val=lambda: self.margins["bottom"],
            set_val=lambda v: self._set_margin("bottom", v)
        )

        # Left & Right (Right Column)
        col_right = ctk.CTkFrame(margins_grid, fg_color="transparent")
        col_right.grid(row=0, column=1, sticky="ew", padx=(16, 0))

        self.margin_entries["left"] = self._create_stepper(
            col_right, "Left Margin:",
            get_val=lambda: self.margins["left"],
            set_val=lambda v: self._set_margin("left", v)
        )
        self.margin_entries["right"] = self._create_stepper(
            col_right, "Right Margin:",
            get_val=lambda: self.margins["right"],
            set_val=lambda v: self._set_margin("right", v)
        )

        # Margin Quick Inset Buttons
        q_m_f = ctk.CTkFrame(tab, fg_color="transparent")
        q_m_f.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(
            q_m_f,
            text="Quick Insets:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        for m_val in (0, 4, 8, 12, 16):
            btn_m = ctk.CTkButton(
                q_m_f,
                text=f"{m_val} px",
                width=50,
                height=26,
                corner_radius=6,
                fg_color=COLOR_SIDEBAR_BG,
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(size=11),
                command=lambda val=m_val: self._set_all_margins(val)
            )
            btn_m.pack(side="left", padx=2)

    def _set_margin(self, edge: str, val: int):
        val = max(-200, min(800, val))
        if self.link_margins.get():
            for k in ("top", "bottom", "left", "right"):
                self.margins[k] = val
                if k in self.margin_entries:
                    self.margin_entries[k].delete(0, "end")
                    self.margin_entries[k].insert(0, f"{val} px")
        else:
            self.margins[edge] = val
            if edge in self.margin_entries:
                self.margin_entries[edge].delete(0, "end")
                self.margin_entries[edge].insert(0, f"{val} px")
        self._draw_preview()

    def _set_all_margins(self, val: int):
        for k in ("top", "bottom", "left", "right"):
            self.margins[k] = val
            if k in self.margin_entries:
                self.margin_entries[k].delete(0, "end")
                self.margin_entries[k].insert(0, f"{val} px")
        self._draw_preview()

    def _on_coverage_mode_changed(self, mode: str):
        self.use_full_screen = "Full Display" in mode
        self._draw_preview()

    # -----------------------------------------------------------------------
    # Tab 2: Gap & Border Snap
    # -----------------------------------------------------------------------
    def _build_tab_gap(self, tab):
        # Gap Section
        gap_sec = ctk.CTkFrame(tab, fg_color="transparent")
        gap_sec.pack(fill="x", padx=12, pady=(8, 12))

        ctk.CTkLabel(
            gap_sec,
            text="Inter-Window Gap (pixels between cells):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 6))

        slider_row = ctk.CTkFrame(gap_sec, fg_color="transparent")
        slider_row.pack(fill="x", pady=2)

        self.gap_slider = ctk.CTkSlider(
            slider_row,
            from_=-15,
            to=40,
            number_of_steps=55,
            command=self._on_gap_slider_moved
        )
        self.gap_slider.set(self.gap)
        self.gap_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_gap_val = ctk.CTkLabel(
            slider_row,
            text=f"{self.gap} px",
            width=65,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_gap_val.pack(side="right")

        # Gap Presets
        presets_row = ctk.CTkFrame(gap_sec, fg_color="transparent")
        presets_row.pack(fill="x", pady=(8, 4))

        gap_presets = [
            ("⚡ Flush Snap (-7px)", -7),
            ("⚡ Touch (0px)", 0),
            ("2px", 2),
            ("4px Standard", 4),
            ("8px", 8),
            ("16px Spaced", 16)
        ]
        for lbl, g_val in gap_presets:
            b = ctk.CTkButton(
                presets_row,
                text=lbl,
                height=26,
                corner_radius=6,
                fg_color=COLOR_ACCENT if self.gap == g_val else COLOR_SIDEBAR_BG,
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(size=11),
                command=lambda v=g_val: self._set_gap_value(v)
            )
            b.pack(side="left", padx=2)

        # DWM Border Compensation
        sep = ctk.CTkFrame(tab, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=(10, 12))

        dwm_sec = ctk.CTkFrame(tab, fg_color="transparent")
        dwm_sec.pack(fill="x", padx=12, pady=4)

        self.switch_dwm = ctk.CTkSwitch(
            dwm_sec,
            text="Compensate Windows 10/11 Invisible Drop-Shadow Borders (Snap Flush)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            progress_color=COLOR_ACCENT,
            command=self._on_dwm_switch_toggled
        )
        if self.dwm_compensation:
            self.switch_dwm.select()
        else:
            self.switch_dwm.deselect()
        self.switch_dwm.pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            dwm_sec,
            text="Windows adds ~7px of invisible resize borders around Chrome windows. Enabling compensation automatically\nexpands the window placement coordinates to cancel this invisible padding so Chrome windows physically touch flush edge-to-edge.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        ).pack(anchor="w", pady=(0, 8))

        b_off_row = ctk.CTkFrame(dwm_sec, fg_color="transparent")
        b_off_row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            b_off_row,
            text="Invisible Border Offset (default 7px):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 10))

        self.slider_dwm_offset = ctk.CTkSlider(
            b_off_row,
            from_=0,
            to=15,
            number_of_steps=15,
            width=180,
            command=self._on_dwm_offset_slider_moved
        )
        self.slider_dwm_offset.set(self.dwm_border_offset)
        self.slider_dwm_offset.pack(side="left", padx=(0, 8))

        self.lbl_dwm_offset_val = ctk.CTkLabel(
            b_off_row,
            text=f"{self.dwm_border_offset} px",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_dwm_offset_val.pack(side="left")

    def _on_gap_slider_moved(self, val):
        self.gap = int(val)
        self.lbl_gap_val.configure(text=f"{self.gap} px")
        self._draw_preview()

    def _set_gap_value(self, val: int):
        self.gap = val
        self.gap_slider.set(val)
        self.lbl_gap_val.configure(text=f"{val} px")
        self._draw_preview()

    def _on_dwm_switch_toggled(self):
        self.dwm_compensation = bool(self.switch_dwm.get())
        self._draw_preview()

    def _on_dwm_offset_slider_moved(self, val):
        self.dwm_border_offset = int(val)
        self.lbl_dwm_offset_val.configure(text=f"{self.dwm_border_offset} px")

    # -----------------------------------------------------------------------
    # Tab 3: Per-Cell Precision Offsets
    # -----------------------------------------------------------------------
    def _build_tab_cell_offsets(self, tab):
        top_row = ctk.CTkFrame(tab, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(8, 8))

        ctk.CTkLabel(
            top_row,
            text="Select Grid Cell to Calibrate:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(0, 8))

        cell_options = []
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                idx = r * self.current_cols + c + 1
                p = self.grid_assignments.get((r, c))
                p_name = f" — {p.display_name}" if p else " (Empty)"
                cell_options.append(f"Cell #{idx:02d} [R{r+1}, C{c+1}]{p_name}")

        self.opt_cell_selector = ctk.CTkOptionMenu(
            top_row,
            values=cell_options,
            width=260,
            height=30,
            fg_color=COLOR_SIDEBAR_BG,
            button_color=COLOR_CARD_HOVER,
            command=self._on_cell_dropdown_selected
        )
        act_idx = self.active_cell[0] * self.current_cols + self.active_cell[1]
        if act_idx < len(cell_options):
            self.opt_cell_selector.set(cell_options[act_idx])
        self.opt_cell_selector.pack(side="left")

        # Live Target Rect Card
        self.cell_info_card = ctk.CTkFrame(tab, fg_color=COLOR_SIDEBAR_BG, corner_radius=8)
        self.cell_info_card.pack(fill="x", padx=12, pady=(0, 10))

        self.lbl_cell_target_info = ctk.CTkLabel(
            self.cell_info_card,
            text="Calculated Screen Bounds: X: 0 px  |  Y: 0 px  |  Width: 0 px  |  Height: 0 px",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_cell_target_info.pack(padx=12, pady=8)

        # 4 Precision Steppers for Cell Offset
        steppers_f = ctk.CTkFrame(tab, fg_color="transparent")
        steppers_f.pack(fill="x", padx=12, pady=4)
        steppers_f.grid_columnconfigure((0, 1), weight=1)

        col_l = ctk.CTkFrame(steppers_f, fg_color="transparent")
        col_l.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        self.offset_entries["dx"] = self._create_stepper(
            col_l, "Horizontal (X) Offset:",
            get_val=lambda: self._get_active_cell_offset("dx"),
            set_val=lambda v: self._set_active_cell_offset("dx", v)
        )
        self.offset_entries["dy"] = self._create_stepper(
            col_l, "Vertical (Y) Offset:",
            get_val=lambda: self._get_active_cell_offset("dy"),
            set_val=lambda v: self._set_active_cell_offset("dy", v)
        )

        col_r = ctk.CTkFrame(steppers_f, fg_color="transparent")
        col_r.grid(row=0, column=1, sticky="ew", padx=(16, 0))

        self.offset_entries["dw"] = self._create_stepper(
            col_r, "Width Delta (+/- px):",
            get_val=lambda: self._get_active_cell_offset("dw"),
            set_val=lambda v: self._set_active_cell_offset("dw", v)
        )
        self.offset_entries["dh"] = self._create_stepper(
            col_r, "Height Delta (+/- px):",
            get_val=lambda: self._get_active_cell_offset("dh"),
            set_val=lambda v: self._set_active_cell_offset("dh", v)
        )

        # Action buttons for cell offsets
        act_row = ctk.CTkFrame(tab, fg_color="transparent")
        act_row.pack(fill="x", padx=12, pady=(12, 4))

        btn_reset_active = ctk.CTkButton(
            act_row,
            text="🔄 Reset Selected Cell",
            width=150,
            height=28,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._reset_active_cell_offset
        )
        btn_reset_active.pack(side="left", padx=(0, 6))

        btn_clear_all = ctk.CTkButton(
            act_row,
            text="🗑️ Clear All Cell Offsets",
            width=160,
            height=28,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_DANGER_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._reset_all_offsets
        )
        btn_clear_all.pack(side="left")

        self._update_cell_info_card()

    def _get_active_cell_offset(self, key: str) -> int:
        c_key = f"{self.active_cell[0]},{self.active_cell[1]}"
        return self.cell_offsets.get(c_key, {}).get(key, 0)

    def _set_active_cell_offset(self, key: str, val: int):
        c_key = f"{self.active_cell[0]},{self.active_cell[1]}"
        if c_key not in self.cell_offsets:
            self.cell_offsets[c_key] = {"dx": 0, "dy": 0, "dw": 0, "dh": 0}
        self.cell_offsets[c_key][key] = val
        self._update_cell_info_card()
        self._draw_preview()

    def _reset_active_cell_offset(self):
        c_key = f"{self.active_cell[0]},{self.active_cell[1]}"
        if c_key in self.cell_offsets:
            del self.cell_offsets[c_key]
        self._update_offset_entries()
        self._update_cell_info_card()
        self._draw_preview()

    def _update_offset_entries(self):
        for k, entry in self.offset_entries.items():
            val = self._get_active_cell_offset(k)
            entry.delete(0, "end")
            entry.insert(0, f"{val} px")

    def _on_cell_dropdown_selected(self, choice: str):
        # Extract row and col from choice: "Cell #01 [R1, C1]..."
        m = re.search(r'\[R(\d+),\s*C(\d+)\]', choice)
        if m:
            r = int(m.group(1)) - 1
            c = int(m.group(2)) - 1
            self.active_cell = (r, c)
            self._update_offset_entries()
            self._update_cell_info_card()
            self._draw_preview()

    def _update_cell_info_card(self):
        mon = self.monitors[self.selected_mon_idx]
        r, c = self.active_cell
        x, y, w, h = WindowManager.calculate_cell_rect(
            monitor=mon,
            rows=self.current_rows,
            cols=self.current_cols,
            row=r,
            col=c,
            gap=self.gap,
            use_full_screen=self.use_full_screen,
            margins=self.margins,
            cell_offsets=self.cell_offsets,
            col_weights=self.col_weights,
            row_weights=self.row_weights
        )
        if hasattr(self, "lbl_cell_target_info"):
            self.lbl_cell_target_info.configure(
                text=f"Calculated Screen Bounds:  X = {x} px   |   Y = {y} px   |   Width = {w} px   |   Height = {h} px"
            )
        if hasattr(self, "lbl_active_cell_badge"):
            self.lbl_active_cell_badge.configure(
                text=f"Selected: Cell [R{r+1}, C{c+1}] ({w}×{h} px)"
            )

    # -----------------------------------------------------------------------
    # Tab 4: Column & Row Weights
    # -----------------------------------------------------------------------
    def _build_tab_weights(self, tab):
        ctk.CTkLabel(
            tab,
            text="Proportional Column & Row Sizing:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            tab,
            text="Adjust proportional width/height weights across columns or rows (useful for asymmetric multi-window monitoring).",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # Equalize Button
        btn_equal = ctk.CTkButton(
            tab,
            text="⚖️ Equalize All Columns & Rows (Uniform)",
            width=240,
            height=30,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_ACCENT,
            command=self._equalize_weights
        )
        btn_equal.pack(anchor="w", padx=12, pady=(0, 12))

        # Sliders Container
        weights_container = ctk.CTkScrollableFrame(tab, fg_color="transparent", height=180)
        weights_container.pack(fill="both", expand=True, padx=12, pady=0)

        # Columns
        ctk.CTkLabel(
            weights_container,
            text=f"Column Widths ({self.current_cols} Columns):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(4, 2))

        if not self.col_weights or len(self.col_weights) != self.current_cols:
            self.col_weights = [1.0] * self.current_cols

        self.col_sliders = []
        for i in range(self.current_cols):
            row_c = ctk.CTkFrame(weights_container, fg_color="transparent")
            row_c.pack(fill="x", pady=2)
            lbl_c = ctk.CTkLabel(row_c, text=f"Column {i+1}:", width=80, anchor="w")
            lbl_c.pack(side="left")
            s = ctk.CTkSlider(
                row_c, from_=0.2, to=3.0, number_of_steps=28,
                command=lambda val, idx=i: self._on_col_weight_changed(idx, val)
            )
            s.set(self.col_weights[i])
            s.pack(side="left", fill="x", expand=True, padx=8)
            lbl_val = ctk.CTkLabel(row_c, text=f"{self.col_weights[i]:.1f}x", width=45)
            lbl_val.pack(side="right")
            self.col_sliders.append((s, lbl_val))

        # Rows
        ctk.CTkLabel(
            weights_container,
            text=f"Row Heights ({self.current_rows} Rows):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(10, 2))

        if not self.row_weights or len(self.row_weights) != self.current_rows:
            self.row_weights = [1.0] * self.current_rows

        self.row_sliders = []
        for i in range(self.current_rows):
            row_r = ctk.CTkFrame(weights_container, fg_color="transparent")
            row_r.pack(fill="x", pady=2)
            lbl_r = ctk.CTkLabel(row_r, text=f"Row {i+1}:", width=80, anchor="w")
            lbl_r.pack(side="left")
            s = ctk.CTkSlider(
                row_r, from_=0.2, to=3.0, number_of_steps=28,
                command=lambda val, idx=i: self._on_row_weight_changed(idx, val)
            )
            s.set(self.row_weights[i])
            s.pack(side="left", fill="x", expand=True, padx=8)
            lbl_val = ctk.CTkLabel(row_r, text=f"{self.row_weights[i]:.1f}x", width=45)
            lbl_val.pack(side="right")
            self.row_sliders.append((s, lbl_val))

    def _on_col_weight_changed(self, idx: int, val: float):
        self.col_weights[idx] = round(val, 2)
        self.col_sliders[idx][1].configure(text=f"{val:.1f}x")
        self._draw_preview()
        self._update_cell_info_card()

    def _on_row_weight_changed(self, idx: int, val: float):
        self.row_weights[idx] = round(val, 2)
        self.row_sliders[idx][1].configure(text=f"{val:.1f}x")
        self._draw_preview()
        self._update_cell_info_card()

    def _equalize_weights(self):
        self.col_weights = [1.0] * self.current_cols
        for s, lbl in self.col_sliders:
            s.set(1.0)
            lbl.configure(text="1.0x")
        self.row_weights = [1.0] * self.current_rows
        for s, lbl in self.row_sliders:
            s.set(1.0)
            lbl.configure(text="1.0x")
        self._draw_preview()
        self._update_cell_info_card()

    # -----------------------------------------------------------------------
    # Stepper Helper
    # -----------------------------------------------------------------------
    def _create_stepper(self, parent, label_text: str, get_val, set_val, step_small=1, step_large=5):
        row_f = ctk.CTkFrame(parent, fg_color="transparent")
        row_f.pack(fill="x", pady=3)
        row_f.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(
            row_f,
            text=label_text,
            width=140,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl.grid(row=0, column=0, sticky="w")

        ctrl_f = ctk.CTkFrame(row_f, fg_color="transparent")
        ctrl_f.grid(row=0, column=1, sticky="e")

        def adjust(delta):
            val = get_val() + delta
            set_val(val)
            entry.delete(0, "end")
            entry.insert(0, f"{val} px")
            self._draw_preview()
            self._update_cell_info_card()

        btn_m5 = ctk.CTkButton(
            ctrl_f, text=f"-{step_large}", width=34, height=28, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: adjust(-step_large)
        )
        btn_m5.pack(side="left", padx=1)

        btn_m1 = ctk.CTkButton(
            ctrl_f, text=f"-{step_small}", width=30, height=28, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: adjust(-step_small)
        )
        btn_m1.pack(side="left", padx=1)

        entry = ctk.CTkEntry(
            ctrl_f, width=70, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER,
            justify="center"
        )
        entry.insert(0, f"{get_val()} px")
        entry.pack(side="left", padx=3)

        def on_entry_change(e):
            raw = entry.get().replace("px", "").strip()
            try:
                val = int(raw)
                set_val(val)
                self._draw_preview()
                self._update_cell_info_card()
            except Exception:
                pass
        entry.bind("<KeyRelease>", on_entry_change)

        btn_p1 = ctk.CTkButton(
            ctrl_f, text=f"+{step_small}", width=30, height=28, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY,
            command=lambda: adjust(step_small)
        )
        btn_p1.pack(side="left", padx=1)

        btn_p5 = ctk.CTkButton(
            ctrl_f, text=f"+{step_large}", width=34, height=28, corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG, hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED,
            command=lambda: adjust(step_large)
        )
        btn_p5.pack(side="left", padx=1)

        return entry

    # -----------------------------------------------------------------------
    # Interactive Canvas Monitor Map
    # -----------------------------------------------------------------------
    def _draw_preview(self):
        self.canvas.delete("all")
        mon = self.monitors[self.selected_mon_idx]
        mon_w, mon_h = mon.width, mon.height

        pad_x = 24
        pad_y = 12
        avail_canvas_w = self.canvas_w - 2 * pad_x
        avail_canvas_h = self.canvas_h - 2 * pad_y

        scale_w = avail_canvas_w / max(1, mon_w)
        scale_h = avail_canvas_h / max(1, mon_h)
        scale = min(scale_w, scale_h)

        draw_w = mon_w * scale
        draw_h = mon_h * scale
        start_x = pad_x + (avail_canvas_w - draw_w) / 2
        start_y = pad_y + (avail_canvas_h - draw_h) / 2

        # Draw Physical Display Screen Bezel
        self.canvas.create_rectangle(
            start_x - 3, start_y - 3, start_x + draw_w + 3, start_y + draw_h + 3,
            outline="#334155", width=2, fill="#0F1420"
        )

        # Draw Taskbar reserve area if not Full Screen
        if not self.use_full_screen:
            wl, wt, wr, wb = mon.work_rect
            ml, mt, mr, mb = mon.rect
            tb_x1 = start_x + (wl - ml) * scale
            tb_y1 = start_y + (wt - mt) * scale
            tb_x2 = start_x + (wr - ml) * scale
            tb_y2 = start_y + (wb - mt) * scale

            # If taskbar is at bottom
            if mb > wb:
                self.canvas.create_rectangle(
                    start_x, tb_y2, start_x + draw_w, start_y + draw_h,
                    fill="#1E293B", outline="#475569", stipple="gray25"
                )
                self.canvas.create_text(
                    start_x + draw_w / 2, (tb_y2 + start_y + draw_h) / 2,
                    text="Windows Taskbar Area (Avoided in Work Area Mode)",
                    fill="#94A3B8", font=("Segoe UI", 8)
                )

        # Draw Cells
        self.cell_canvas_boxes = {}
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                cx, cy, cw, ch = WindowManager.calculate_cell_rect(
                    monitor=mon,
                    rows=self.current_rows,
                    cols=self.current_cols,
                    row=r,
                    col=c,
                    gap=self.gap,
                    use_full_screen=self.use_full_screen,
                    margins=self.margins,
                    cell_offsets=self.cell_offsets,
                    col_weights=self.col_weights,
                    row_weights=self.row_weights
                )
                # Map from monitor space to canvas space
                x1 = start_x + (cx - mon.rect[0]) * scale
                y1 = start_y + (cy - mon.rect[1]) * scale
                x2 = x1 + cw * scale
                y2 = y1 + ch * scale

                is_active = (r == self.active_cell[0] and c == self.active_cell[1])
                bg_c = "#1E293B" if is_active else "#162032"
                bdr_c = COLOR_ACCENT if is_active else "#334155"
                bdr_w = 2 if is_active else 1

                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=bg_c, outline=bdr_c, width=bdr_w,
                    tags=f"cell_{r}_{c}"
                )
                self.cell_canvas_boxes[(r, c)] = (x1, y1, x2, y2)

                # Label text
                idx = r * self.current_cols + c + 1
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2

                if (x2 - x1) > 50 and (y2 - y1) > 25:
                    self.canvas.create_text(
                        mid_x, mid_y - 6,
                        text=f"#{idx} [R{r+1},C{c+1}]",
                        fill=COLOR_ACCENT if is_active else "#F8FAFC",
                        font=("Segoe UI", 9, "bold" if is_active else "normal"),
                        tags=f"cell_{r}_{c}"
                    )
                    self.canvas.create_text(
                        mid_x, mid_y + 8,
                        text=f"{cw}×{ch} px",
                        fill="#94A3B8",
                        font=("Segoe UI", 8),
                        tags=f"cell_{r}_{c}"
                    )
                elif (x2 - x1) > 30 and (y2 - y1) > 16:
                    self.canvas.create_text(
                        mid_x, mid_y,
                        text=f"#{idx}",
                        fill=COLOR_ACCENT if is_active else "#F8FAFC",
                        font=("Segoe UI", 8, "bold" if is_active else "normal"),
                        tags=f"cell_{r}_{c}"
                    )

        # Resolution label at bottom right
        mode_tag = "Full Screen (100% Display)" if self.use_full_screen else "Work Area"
        self.canvas.create_text(
            start_x + draw_w - 4, start_y + draw_h - 6,
            text=f"{mon_w}×{mon_h} px | {mode_tag}",
            anchor="se",
            fill="#64748B",
            font=("Segoe UI", 8)
        )

    def _on_canvas_clicked(self, event):
        for (r, c), (x1, y1, x2, y2) in getattr(self, "cell_canvas_boxes", {}).items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.active_cell = (r, c)
                act_idx = r * self.current_cols + c
                if hasattr(self, "opt_cell_selector"):
                    vals = self.opt_cell_selector._values
                    if act_idx < len(vals):
                        self.opt_cell_selector.set(vals[act_idx])
                self._update_offset_entries()
                self._update_cell_info_card()
                self._draw_preview()
                break

    # -----------------------------------------------------------------------
    # Preset & Action Handlers
    # -----------------------------------------------------------------------
    def _apply_preset_fullscreen(self):
        self.use_full_screen = True
        self.margins = {"top": 0, "bottom": 0, "left": 0, "right": 0}
        self.gap = 0
        self.dwm_compensation = True
        self.dwm_border_offset = 7
        self.cell_offsets.clear()
        self.col_weights = [1.0] * self.current_cols
        self.row_weights = [1.0] * self.current_rows

        if hasattr(self, "seg_mode"):
            self.seg_mode.set("📺 Full Display (100% Edge-to-Edge)")
        if hasattr(self, "gap_slider"):
            self.gap_slider.set(0)
            self.lbl_gap_val.configure(text="0 px")
        if hasattr(self, "switch_dwm"):
            self.switch_dwm.select()
        self._set_all_margins(0)
        self._update_offset_entries()
        self._update_cell_info_card()
        self._draw_preview()

    def _apply_preset_workarea(self):
        self.use_full_screen = False
        self.margins = {"top": 0, "bottom": 0, "left": 0, "right": 0}
        self.gap = 4
        self.dwm_compensation = True
        self.dwm_border_offset = 7
        self.cell_offsets.clear()
        self.col_weights = [1.0] * self.current_cols
        self.row_weights = [1.0] * self.current_rows

        if hasattr(self, "seg_mode"):
            self.seg_mode.set("🖥️ Work Area (Avoid Taskbar)")
        if hasattr(self, "gap_slider"):
            self.gap_slider.set(4)
            self.lbl_gap_val.configure(text="4 px")
        if hasattr(self, "switch_dwm"):
            self.switch_dwm.select()
        self._set_all_margins(0)
        self._update_offset_entries()
        self._update_cell_info_card()
        self._draw_preview()

    def _reset_all_offsets(self):
        self.cell_offsets.clear()
        self._update_offset_entries()
        self._update_cell_info_card()
        self._draw_preview()

    def _on_monitor_changed(self, choice: str):
        for idx, m in enumerate(self.monitors):
            if m.display_label == choice:
                self.selected_mon_idx = idx
                break
        self._draw_preview()
        self._update_cell_info_card()

    def _get_current_settings(self) -> Dict[str, Any]:
        return {
            "monitor_index": self.selected_mon_idx,
            "use_full_screen": self.use_full_screen,
            "screen_margins": dict(self.margins),
            "cell_gap": self.gap,
            "dwm_compensation": self.dwm_compensation,
            "dwm_border_offset": self.dwm_border_offset,
            "cell_offsets": {k: dict(v) for k, v in self.cell_offsets.items() if any(v.values())},
            "col_weights": list(self.col_weights) if self.col_weights else [],
            "row_weights": list(self.row_weights) if self.row_weights else [],
        }

    def _test_placement(self):
        self.on_test_position(self._get_current_settings())

    def _submit(self):
        self.on_apply(self._get_current_settings())
        self.destroy()


# ---------------------------------------------------------------------------
# Modal: Application Settings Dialog
# ---------------------------------------------------------------------------
class SettingsModal(ctk.CTkToplevel):
    def __init__(self, parent, settings: Dict[str, Any], monitors: List[MonitorInfo], profiles: List[ChromeProfile], on_save):
        super().__init__(parent)
        self.settings = settings
        self.monitors = monitors
        self.profiles = profiles
        self.on_save = on_save

        self.title("Settings — Chrome Grid Launcher")
        self.geometry("540x680")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color=COLOR_BG_DARK)

        lbl_title = ctk.CTkLabel(
            self,
            text="Settings & Preferences",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_title.pack(pady=(18, 12), padx=20, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Protected Profile Section
        self._add_section_header(scroll, "Protected Personal Profile (Exclusion)")
        ctk.CTkLabel(
            scroll,
            text="Personal profile to protect (excluded from Auto-Populate & 'Close Chrome'):",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(anchor="w", pady=(4, 2))

        prof_options = ["None (No exclusion)"] + [f"{p.key}: {p.display_name}" for p in self.profiles]
        cur_prot = self.settings.get("protected_profile_key", "Default")
        cur_prot_val = "None (No exclusion)"
        for opt in prof_options:
            if opt.startswith(f"{cur_prot}:") or opt == cur_prot:
                cur_prot_val = opt
                break

        self.opt_protected = ctk.CTkOptionMenu(scroll, values=prof_options, fg_color=COLOR_CARD_BG, button_color=COLOR_CARD_HOVER)
        self.opt_protected.set(cur_prot_val)
        self.opt_protected.pack(fill="x", pady=(0, 14))

        # Monitor Section
        self._add_section_header(scroll, "Display & Monitor Placement")
        ctk.CTkLabel(scroll, text="Target Screen for Gridded Chrome Windows:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(4, 2))

        mon_options = [m.display_label for m in self.monitors]
        cur_idx = min(self.settings.get("monitor_index", 0), len(mon_options) - 1)
        cur_mon_val = mon_options[cur_idx] if mon_options else "Monitor 1"
        self.opt_mon = ctk.CTkOptionMenu(scroll, values=mon_options, fg_color=COLOR_CARD_BG, button_color=COLOR_CARD_HOVER)
        self.opt_mon.set(cur_mon_val)
        self.opt_mon.pack(fill="x", pady=(0, 8))

        self.switch_fullscreen = ctk.CTkSwitch(
            scroll,
            text="Use Full Screen Display (100% Edge-to-Edge, bypass taskbar reserve)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color=COLOR_ACCENT
        )
        if self.settings.get("use_full_screen", False):
            self.switch_fullscreen.select()
        else:
            self.switch_fullscreen.deselect()
        self.switch_fullscreen.pack(anchor="w", pady=(2, 6))

        self.switch_dwm_comp = ctk.CTkSwitch(
            scroll,
            text="Compensate Windows DWM Invisible Borders (Snap Flush)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color=COLOR_ACCENT
        )
        if self.settings.get("dwm_compensation", True):
            self.switch_dwm_comp.select()
        else:
            self.switch_dwm_comp.deselect()
        self.switch_dwm_comp.pack(anchor="w", pady=(0, 6))

        btn_open_fine = ctk.CTkButton(
            scroll,
            text="📐 Open Precision Screen Fit & Fine Positioning Tool...",
            height=30,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_fine_tool
        )
        btn_open_fine.pack(anchor="w", pady=(2, 12))

        # Cell Gap Section
        self._add_section_header(scroll, "Grid Spacing")
        ctk.CTkLabel(scroll, text="Cell Gap (pixel margin between windows):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(4, 2))

        gap_val = self.settings.get("cell_gap", 4)
        self.gap_slider = ctk.CTkSlider(scroll, from_=0, to=30, number_of_steps=30)
        self.gap_slider.set(gap_val)
        self.gap_slider.pack(fill="x", pady=(0, 2))

        self.lbl_gap_val = ctk.CTkLabel(scroll, text=f"{gap_val} px", font=ctk.CTkFont(size=11), text_color=COLOR_ACCENT)
        self.lbl_gap_val.pack(anchor="w", pady=(0, 12))
        self.gap_slider.configure(command=lambda val: self.lbl_gap_val.configure(text=f"{int(val)} px"))

        # Launch & Detection Timing
        self._add_section_header(scroll, "Window Detection & Launch Behavior")

        ctk.CTkLabel(scroll, text="Window Detection Timeout (seconds):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(4, 2))
        self.entry_timeout = ctk.CTkEntry(scroll, height=32, fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER)
        self.entry_timeout.insert(0, str(self.settings.get("window_timeout", 8.0)))
        self.entry_timeout.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Launch Delay between Windows (ms):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(4, 2))
        self.entry_interval = ctk.CTkEntry(scroll, height=32, fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER)
        self.entry_interval.insert(0, str(self.settings.get("launch_interval", 400)))
        self.entry_interval.pack(fill="x", pady=(0, 10))

        self.switch_reuse = ctk.CTkSwitch(
            scroll,
            text="Reuse Existing Chrome Windows (if already open for profile)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color=COLOR_ACCENT
        )
        if self.settings.get("reuse_existing", False):
            self.switch_reuse.select()
        else:
            self.switch_reuse.deselect()
        self.switch_reuse.pack(anchor="w", pady=(4, 10))

        self.switch_minimize = ctk.CTkSwitch(
            scroll,
            text="Minimize Launcher on Launch (clean desktop view)",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            progress_color=COLOR_ACCENT
        )
        if self.settings.get("minimize_on_launch", False):
            self.switch_minimize.select()
        else:
            self.switch_minimize.deselect()
        self.switch_minimize.pack(anchor="w", pady=(0, 14))

        # Chrome Executable Section
        self._add_section_header(scroll, "Chrome Path Override")
        ctk.CTkLabel(scroll, text="Custom Chrome Executable Path (leave blank for auto-detect):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(4, 2))

        p_row = ctk.CTkFrame(scroll, fg_color="transparent")
        p_row.pack(fill="x", pady=(0, 14))

        self.entry_chrome_path = ctk.CTkEntry(p_row, height=32, fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_BORDER)
        self.entry_chrome_path.insert(0, self.settings.get("chrome_path_override", ""))
        self.entry_chrome_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(
            p_row,
            text="Browse...",
            width=80,
            height=32,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            command=self._browse_chrome_path
        )
        btn_browse.pack(side="right")

        # Theme Section
        self._add_section_header(scroll, "Appearance")
        self.opt_theme = ctk.CTkOptionMenu(scroll, values=["Dark", "Light", "System"], fg_color=COLOR_CARD_BG, button_color=COLOR_CARD_HOVER)
        self.opt_theme.set(self.settings.get("theme", "Dark"))
        self.opt_theme.pack(anchor="w", pady=(4, 18))

        # Buttons
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(0, 16))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_HOVER, command=self.destroy)
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 8))

        btn_save = ctk.CTkButton(btn_box, text="Save Settings", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self._submit)
        btn_save.pack(side="right", expand=True, fill="x", padx=(8, 0))

    def _browse_chrome_path(self):
        f = filedialog.askopenfilename(
            parent=self,
            title="Locate chrome.exe",
            filetypes=[("Chrome Executable", "chrome.exe"), ("All Executables", "*.exe")]
        )
        if f:
            self.entry_chrome_path.delete(0, "end")
            self.entry_chrome_path.insert(0, f)

    def _add_section_header(self, parent, text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_ACCENT
        )
        lbl.pack(anchor="w", pady=(10, 4))

    def _open_fine_tool(self):
        if hasattr(self.master, "_open_fine_control_modal"):
            self.master._open_fine_control_modal()

    def _submit(self):
        selected_mon_str = self.opt_mon.get()
        mon_idx = 0
        for i, m in enumerate(self.monitors):
            if m.display_label == selected_mon_str:
                mon_idx = i
                break

        try:
            timeout_val = float(self.entry_timeout.get().strip())
        except ValueError:
            timeout_val = 8.0

        try:
            interval_val = int(self.entry_interval.get().strip())
        except ValueError:
            interval_val = 400

        sel_prot = self.opt_protected.get()
        prot_key = ""
        if sel_prot != "None (No exclusion)":
            prot_key = sel_prot.split(":")[0].strip()

        new_settings = {
            "monitor_index": mon_idx,
            "use_full_screen": bool(self.switch_fullscreen.get()),
            "dwm_compensation": bool(self.switch_dwm_comp.get()),
            "cell_gap": int(self.gap_slider.get()),
            "window_timeout": timeout_val,
            "launch_interval": interval_val,
            "reuse_existing": bool(self.switch_reuse.get()),
            "minimize_on_launch": bool(self.switch_minimize.get()),
            "chrome_path_override": self.entry_chrome_path.get().strip(),
            "theme": self.opt_theme.get(),
            "protected_profile_key": prot_key
        }

        self.on_save(new_settings)
        self.destroy()


# ---------------------------------------------------------------------------
# Main Chrome Grid Launcher Controller
# ---------------------------------------------------------------------------
class ChromeGridLauncherApp(ctk.CTk):
    """Main desktop application window and orchestrator."""

    def __init__(self):
        super().__init__()

        self.settings = ConfigManager.load_settings()
        self._apply_theme(self.settings.get("theme", "Dark"))

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1380x840")
        self.minsize(1060, 680)
        self.configure(fg_color=COLOR_BG_DARK)

        # Hardware & Profile State
        self.monitors = WindowManager.get_monitors()
        self.profiles: List[ChromeProfile] = []
        self.custom_groups: List[ProfileGroup] = GroupManager.load_custom_groups()
        self.active_group_id: str = GroupManager.GROUP_ALL
        self.group_buttons: Dict[str, ctk.CTkButton] = {}
        self.selected_profile_for_assign: Optional[ChromeProfile] = None
        self.chrome_executable: Optional[str] = None

        # Grid State (rows x cols)
        self.current_rows: int = 2
        self.current_cols: int = 2
        self.grid_assignments: Dict[Tuple[int, int], Optional[ChromeProfile]] = {}
        self.cell_widgets: Dict[Tuple[int, int], GridCellCard] = {}
        self.managed_hwnds: set = set()

        # Launch State
        self.is_launching = False
        self.cancel_launch_flag = False

        # Refresh Server & Remote Tab Execution
        server_port = int(self.settings.get("refresh_server_port", 8765))
        self.refresh_server = RefreshServer(port=server_port)
        self.refresh_server.on_clients_changed = self._on_refresh_server_clients_changed
        self.refresh_server.on_ack_received = self._on_refresh_ack_received
        self.refresh_server.on_log = self._on_refresh_server_log
        self.refresh_server.on_status_changed = self._on_refresh_server_status_changed

        self.auto_refresh_job = None
        self.active_workspace_tab = "grid"

        # Thunder Configurateur State
        self.thunder_selected_cells: set = set()
        self.thunder_cell_cards: dict = {}
        self._init_thunder_state()

        # Keyboard shortcuts
        self.bind("<Control-l>", lambda e: self._handle_launch_all())
        self.bind("<Control-w>", lambda e: self._handle_close_chrome())
        self.bind("<Control-s>", lambda e: self._open_save_layout_dialog())
        self.bind("<Control-o>", lambda e: self._open_load_layout_dialog())
        self.bind("<Control-r>", lambda e: self._detect_environment())
        self.bind("<Control-a>", lambda e: self._auto_populate_grid())
        self.bind("<Control-Shift-R>", lambda e: self._trigger_refresh_all())

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # Build UI layout
        self._init_layout()
        self._detect_environment()
        self._restore_initial_grid()

        # Auto-start Refresh Server
        if self.settings.get("auto_start_refresh_server", True):
            self.refresh_server.start()

    def _apply_theme(self, theme_name: str):
        if theme_name.lower() == "light":
            ctk.set_appearance_mode("light")
        elif theme_name.lower() == "dark":
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

    def _init_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_top_bar()
        self._build_sidebar()
        self._build_center_grid_area()
        self._build_status_bar()

    # -----------------------------------------------------------------------
    # Top Control Bar
    # -----------------------------------------------------------------------
    def _build_top_bar(self):
        self.top_bar = ctk.CTkFrame(self, fg_color=COLOR_TOPBAR_BG, corner_radius=0, height=64)
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.top_bar.grid_columnconfigure(1, weight=1)

        # Brand Title
        brand_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=(18, 16), pady=12, sticky="w")

        title_lbl = ctk.CTkLabel(
            brand_frame,
            text="Chrome Grid",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(side="left")

        launcher_lbl = ctk.CTkLabel(
            brand_frame,
            text="Launcher",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLOR_ACCENT
        )
        launcher_lbl.pack(side="left", padx=(4, 0))

        # Presets & Gap Controls Group
        presets_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        presets_frame.grid(row=0, column=1, sticky="w", padx=6)

        ctk.CTkLabel(
            presets_frame,
            text="Grid:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        self.preset_buttons: Dict[str, ctk.CTkButton] = {}
        presets = [
            ("2×2", 2, 2),
            ("3×3", 3, 3),
            ("4×4", 4, 4),
            ("4×6 (24)", 4, 6),
            ("5×10 (50)", 10, 5),
            ("10×5 (50)", 5, 10),
        ]
        for label, r, c in presets:
            btn = ctk.CTkButton(
                presets_frame,
                text=label,
                width=54 if "(" not in label else 74,
                height=32,
                corner_radius=8,
                fg_color=COLOR_CARD_BG,
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                command=lambda rows=r, cols=c, lbl=label: self._set_grid_preset(rows, cols, lbl)
            )
            btn.pack(side="left", padx=2)
            self.preset_buttons[f"{c}x{r}"] = btn
            self.preset_buttons[f"{c}×{r}"] = btn
            self.preset_buttons[f"{r}x{c}"] = btn
            self.preset_buttons[f"{r}×{c}"] = btn

        # Custom Size Button
        self.btn_custom = ctk.CTkButton(
            presets_frame,
            text="Custom...",
            width=68,
            height=32,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._prompt_custom_grid
        )
        self.btn_custom.pack(side="left", padx=2)

        # Gap / Max Resolution Quick Toggles
        gap_frame = ctk.CTkFrame(presets_frame, fg_color="transparent")
        gap_frame.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            gap_frame,
            text="Gap:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 4))

        cur_gap = self.settings.get("cell_gap", 4)

        self.btn_gap_zero = ctk.CTkButton(
            gap_frame,
            text="⚡ Max Res (0px)",
            width=100,
            height=32,
            corner_radius=8,
            fg_color=COLOR_ACCENT if cur_gap == 0 else COLOR_CARD_BG,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self._set_gap(0)
        )
        self.btn_gap_zero.pack(side="left", padx=2)

        self.btn_gap_2 = ctk.CTkButton(
            gap_frame,
            text="2px",
            width=38,
            height=32,
            corner_radius=8,
            fg_color=COLOR_ACCENT if cur_gap == 2 else COLOR_CARD_BG,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._set_gap(2)
        )
        self.btn_gap_2.pack(side="left", padx=2)

        self.btn_gap_4 = ctk.CTkButton(
            gap_frame,
            text="4px",
            width=38,
            height=32,
            corner_radius=8,
            fg_color=COLOR_ACCENT if cur_gap == 4 else COLOR_CARD_BG,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._set_gap(4)
        )
        self.btn_gap_4.pack(side="left", padx=2)

        # Fine Position Calibration Button
        self.btn_fine_pos = ctk.CTkButton(
            gap_frame,
            text="📐 Fine Position",
            width=112,
            height=32,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_ACCENT,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._open_fine_control_modal
        )
        self.btn_fine_pos.pack(side="left", padx=(6, 2))

        # Quick Full Screen / Work Area Toggle Button
        cur_fs = self.settings.get("use_full_screen", False)
        self.btn_screen_mode = ctk.CTkButton(
            gap_frame,
            text="📺 Full Screen" if cur_fs else "🖥️ Work Area",
            width=102,
            height=32,
            corner_radius=8,
            fg_color=COLOR_ACCENT if cur_fs else COLOR_CARD_BG,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._toggle_screen_mode
        )
        self.btn_screen_mode.pack(side="left", padx=2)

        # Actions Group (Right)
        actions_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        actions_frame.grid(row=0, column=2, padx=(10, 18), pady=12, sticky="e")

        # Monitor Selector Dropdown
        mon_names = [m.display_label for m in self.monitors]
        sel_idx = min(self.settings.get("monitor_index", 0), len(mon_names) - 1)
        cur_val = mon_names[sel_idx] if mon_names else "Monitor 1"
        self.opt_top_monitor = ctk.CTkOptionMenu(
            actions_frame,
            values=mon_names,
            width=200,
            height=34,
            fg_color=COLOR_CARD_BG,
            button_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._on_monitor_changed
        )
        self.opt_top_monitor.set(cur_val)
        self.opt_top_monitor.pack(side="left", padx=(0, 6))

        # Save Layout
        btn_save = ctk.CTkButton(
            actions_frame,
            text="💾 Save",
            width=70,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._open_save_layout_dialog
        )
        btn_save.pack(side="left", padx=2)

        # Load Layout
        btn_load = ctk.CTkButton(
            actions_frame,
            text="📂 Load",
            width=70,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._open_load_layout_dialog
        )
        btn_load.pack(side="left", padx=2)

        # Arrange Existing
        btn_arrange = ctk.CTkButton(
            actions_frame,
            text="📐 Arrange Existing",
            width=128,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_ACCENT,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._arrange_existing_windows
        )
        btn_arrange.pack(side="left", padx=2)

        # Settings
        btn_settings = ctk.CTkButton(
            actions_frame,
            text="⚙️",
            width=36,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=14),
            command=self._open_settings_dialog
        )
        btn_settings.pack(side="left", padx=(2, 8))

        # Launch All Primary Action Button
        self.btn_launch_all = ctk.CTkButton(
            actions_frame,
            text="🚀 LAUNCH ALL",
            width=134,
            height=36,
            corner_radius=8,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FFFFFF",
            command=self._handle_launch_all
        )
        self.btn_launch_all.pack(side="left", padx=2)

        # Remote Refresh All Button in Top Bar
        self.btn_top_refresh_all = ctk.CTkButton(
            actions_frame,
            text="🔄 REFRESH ALL",
            width=132,
            height=36,
            corner_radius=8,
            fg_color="#1E3A8A",
            hover_color="#2563EB",
            border_width=1,
            border_color="#3B82F6",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#93C5FD",
            command=self._trigger_refresh_all
        )
        self.btn_top_refresh_all.pack(side="left", padx=2)

        # Close Chrome Action Button
        self.btn_close_all = ctk.CTkButton(
            actions_frame,
            text="🛑 Close Chrome",
            width=126,
            height=36,
            corner_radius=8,
            fg_color="#3B1219",
            hover_color=COLOR_DANGER_HOVER,
            border_width=1,
            border_color="#991B1B",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FCA5A5",
            command=self._handle_close_chrome
        )
        self.btn_close_all.pack(side="left", padx=(3, 0))

    def _set_gap(self, gap: int):
        self.settings["cell_gap"] = gap
        ConfigManager.save_settings(self.settings)
        if hasattr(self, "btn_gap_zero"):
            self.btn_gap_zero.configure(fg_color=COLOR_ACCENT if gap == 0 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_2"):
            self.btn_gap_2.configure(fg_color=COLOR_ACCENT if gap == 2 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_4"):
            self.btn_gap_4.configure(fg_color=COLOR_ACCENT if gap == 4 else COLOR_CARD_BG)
        if gap == 0:
            self.lbl_status.configure(text="⚡ Maximize Resolution enabled (0px zero-gap edge-to-edge coverage).")
        else:
            self.lbl_status.configure(text=f"Grid gap set to {gap}px.")

    # -----------------------------------------------------------------------
    # Left Sidebar (Profiles & Groups)
    # -----------------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR_BG, corner_radius=0, width=335)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Header & Profile Count
        header_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_box.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        header_box.grid_columnconfigure(0, weight=1)

        lbl_sidebar_title = ctk.CTkLabel(
            header_box,
            text="Detected Profiles",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_sidebar_title.grid(row=0, column=0, sticky="w")

        self.lbl_profile_count = ctk.CTkLabel(
            header_box,
            text="0 profiles",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_profile_count.grid(row=0, column=1, sticky="e")

        # Search Bar
        search_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        search_box.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="🔍 Filter profiles...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=32,
            fg_color=COLOR_CARD_BG,
            border_color=COLOR_BORDER
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_sidebar_search)

        # Group Tabs & Management Bar (Row 2)
        self.group_bar = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.group_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))
        self.group_bar.grid_columnconfigure(0, weight=1)

        hdr_grp = ctk.CTkFrame(self.group_bar, fg_color="transparent")
        hdr_grp.pack(fill="x", pady=(0, 4))

        lbl_grp = ctk.CTkLabel(
            hdr_grp,
            text="PROFILE GROUPS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_grp.pack(side="left")

        self.group_actions_frame = ctk.CTkFrame(hdr_grp, fg_color="transparent")
        self.group_actions_frame.pack(side="right")

        self.btn_new_group = ctk.CTkButton(
            self.group_actions_frame,
            text="➕ New",
            width=54,
            height=22,
            corner_radius=6,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._open_new_group_modal
        )
        self.btn_new_group.pack(side="right", padx=1)

        self.group_tabs_scroll = ctk.CTkScrollableFrame(
            self.group_bar,
            orientation="horizontal",
            height=36,
            fg_color=COLOR_TOPBAR_BG,
            corner_radius=8
        )
        self.group_tabs_scroll.pack(fill="x")

        # Scrollable Profiles List (Row 3)
        self.sidebar_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.sidebar_scroll.grid(row=3, column=0, sticky="nsew", padx=10, pady=0)
        self.sidebar_scroll.grid_columnconfigure(0, weight=1)

        # Footer Actions (Row 4)
        footer_box = ctk.CTkFrame(self.sidebar, fg_color=COLOR_TOPBAR_BG, corner_radius=10)
        footer_box.grid(row=4, column=0, sticky="ew", padx=12, pady=10)
        footer_box.grid_columnconfigure((0, 1), weight=1)

        self.btn_auto_populate = ctk.CTkButton(
            footer_box,
            text="⚡ Auto Populate",
            height=34,
            corner_radius=6,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._auto_populate_grid
        )
        self.btn_auto_populate.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        btn_refresh = ctk.CTkButton(
            footer_box,
            text="🔄 Refresh",
            height=28,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._detect_environment
        )
        btn_refresh.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))

        btn_clear_grid = ctk.CTkButton(
            footer_box,
            text="🗑️ Clear Grid",
            height=28,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_DANGER_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._clear_grid_assignments
        )
        btn_clear_grid.grid(row=1, column=1, sticky="ew", padx=(4, 8), pady=(0, 8))

    # -----------------------------------------------------------------------
    # Group Tabs & Group Management
    # -----------------------------------------------------------------------
    def _render_group_tabs(self):
        for child in self.group_tabs_scroll.winfo_children():
            child.destroy()
        self.group_buttons.clear()

        # Clear custom group edit/delete buttons from group_actions_frame
        for child in self.group_actions_frame.winfo_children():
            if child != self.btn_new_group:
                child.destroy()

        counts = GroupManager.get_group_counts(self.profiles, self.custom_groups)

        tabs = [
            (GroupManager.GROUP_ALL, "All", counts.get(GroupManager.GROUP_ALL, len(self.profiles)), COLOR_TEXT_PRIMARY),
            (GroupManager.GROUP_NUMBERS, "🔢 Numbers", counts.get(GroupManager.GROUP_NUMBERS, 0), COLOR_GROUP_NUMBERS),
            (GroupManager.GROUP_PRT, "🏷️ PRT", counts.get(GroupManager.GROUP_PRT, 0), COLOR_GROUP_PRT),
        ]

        for cg in self.custom_groups:
            cnt = counts.get(cg.id, len(cg.profile_keys))
            tabs.append((cg.id, f"📁 {cg.name}", cnt, cg.color))

        other_cnt = counts.get(GroupManager.GROUP_OTHER, 0)
        if other_cnt > 0:
            tabs.append((GroupManager.GROUP_OTHER, "Other", other_cnt, COLOR_GROUP_OTHER))

        for gid, label, cnt, color in tabs:
            is_active = (gid == self.active_group_id)
            btn_text = f"{label} ({cnt})"

            btn = ctk.CTkButton(
                self.group_tabs_scroll,
                text=btn_text,
                height=26,
                corner_radius=6,
                fg_color=COLOR_ACCENT if is_active else COLOR_CARD_BG,
                hover_color=COLOR_ACCENT_HOVER if is_active else COLOR_CARD_HOVER,
                text_color="#FFFFFF" if is_active else COLOR_TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold" if is_active else "normal"),
                border_width=1 if is_active else 0,
                border_color=color if is_active else COLOR_BORDER,
                command=lambda g=gid: self._select_group(g)
            )
            btn.pack(side="left", padx=2, pady=2)
            self.group_buttons[gid] = btn

        # If active group is a custom group, show edit and delete buttons in group_actions_frame
        built_in_groups = (GroupManager.GROUP_ALL, GroupManager.GROUP_NUMBERS, GroupManager.GROUP_PRT, GroupManager.GROUP_OTHER)
        if self.active_group_id not in built_in_groups:
            btn_del = ctk.CTkButton(
                self.group_actions_frame,
                text="🗑️",
                width=24,
                height=22,
                corner_radius=5,
                fg_color="#3B1219",
                hover_color=COLOR_DANGER_HOVER,
                border_width=1,
                border_color="#991B1B",
                font=ctk.CTkFont(size=10),
                text_color="#FCA5A5",
                command=self._delete_active_custom_group
            )
            btn_del.pack(side="right", padx=(2, 2))

            btn_edit = ctk.CTkButton(
                self.group_actions_frame,
                text="✏️",
                width=24,
                height=22,
                corner_radius=5,
                fg_color=COLOR_CARD_BG,
                hover_color=COLOR_CARD_HOVER,
                font=ctk.CTkFont(size=10),
                command=self._open_edit_group_modal
            )
            btn_edit.pack(side="right", padx=(0, 2))

    def _select_group(self, group_id: str):
        self.active_group_id = group_id
        self._render_group_tabs()
        self._filter_and_render_sidebar()
        self._update_auto_populate_button()

        grp_name = "All"
        if group_id == GroupManager.GROUP_NUMBERS:
            grp_name = "Numbers"
        elif group_id == GroupManager.GROUP_PRT:
            grp_name = "PRT"
        elif group_id == GroupManager.GROUP_OTHER:
            grp_name = "Other"
        else:
            cg = next((g for g in self.custom_groups if g.id == group_id), None)
            if cg:
                grp_name = cg.name

        self.lbl_status.configure(text=f"Filtered view to group '{grp_name}'.")

    def _update_auto_populate_button(self):
        if self.active_group_id == GroupManager.GROUP_ALL:
            label = "⚡ Auto Populate (All)"
        elif self.active_group_id == GroupManager.GROUP_NUMBERS:
            label = "⚡ Auto Populate (Numbers)"
        elif self.active_group_id == GroupManager.GROUP_PRT:
            label = "⚡ Auto Populate (PRT)"
        elif self.active_group_id == GroupManager.GROUP_OTHER:
            label = "⚡ Auto Populate (Other)"
        else:
            grp = next((g for g in self.custom_groups if g.id == self.active_group_id), None)
            name = grp.name if grp else "Group"
            label = f"⚡ Auto Populate ({name})"
        self.btn_auto_populate.configure(text=label)

    def _open_new_group_modal(self):
        NewGroupModal(
            parent=self,
            all_profiles=self.profiles,
            on_save_group=self._on_custom_group_created
        )

    def _on_custom_group_created(self, new_group: ProfileGroup):
        self.custom_groups.append(new_group)
        GroupManager.save_custom_groups(self.custom_groups)
        GroupManager.apply_groups_to_profiles(self.profiles, self.custom_groups)
        self.active_group_id = new_group.id
        self._render_group_tabs()
        self._filter_and_render_sidebar()
        self._update_auto_populate_button()
        self.lbl_status.configure(text=f"Created custom group '{new_group.name}' with {len(new_group.profile_keys)} profiles.")

    def _open_edit_group_modal(self):
        grp = next((g for g in self.custom_groups if g.id == self.active_group_id), None)
        if not grp:
            return
        NewGroupModal(
            parent=self,
            all_profiles=self.profiles,
            on_save_group=self._on_custom_group_edited,
            existing_group=grp
        )

    def _on_custom_group_edited(self, updated_group: ProfileGroup):
        for i, g in enumerate(self.custom_groups):
            if g.id == updated_group.id:
                self.custom_groups[i] = updated_group
                break
        GroupManager.save_custom_groups(self.custom_groups)
        GroupManager.apply_groups_to_profiles(self.profiles, self.custom_groups)
        self._render_group_tabs()
        self._filter_and_render_sidebar()
        self._update_auto_populate_button()
        self.lbl_status.configure(text=f"Updated group '{updated_group.name}'.")

    def _delete_active_custom_group(self):
        grp = next((g for g in self.custom_groups if g.id == self.active_group_id), None)
        if not grp:
            return
        self.custom_groups = [g for g in self.custom_groups if g.id != grp.id]
        GroupManager.save_custom_groups(self.custom_groups)
        GroupManager.apply_groups_to_profiles(self.profiles, self.custom_groups)
        self.active_group_id = GroupManager.GROUP_ALL
        self._render_group_tabs()
        self._filter_and_render_sidebar()
        self._update_auto_populate_button()
        self.lbl_status.configure(text=f"Deleted custom group '{grp.name}'.")

    def _open_assign_group_dialog(self, profile: ChromeProfile):
        AssignGroupModal(
            parent=self,
            profile=profile,
            custom_groups=self.custom_groups,
            on_assigned=self._on_profile_assigned_to_group,
            on_create_new=self._open_new_group_modal
        )

    def _on_profile_assigned_to_group(self, profile: ChromeProfile, new_group_id: Optional[str]):
        # Remove from any existing custom group
        for g in self.custom_groups:
            if profile.key in g.profile_keys:
                g.profile_keys.remove(profile.key)

        overrides = GroupManager.load_overrides()

        if not new_group_id or new_group_id == "auto":
            # Revert to automatic rule-based detection
            if profile.key in overrides:
                del overrides[profile.key]
        elif new_group_id in (GroupManager.GROUP_PRT, GroupManager.GROUP_NUMBERS, GroupManager.GROUP_OTHER):
            # Explicit system group assignment
            overrides[profile.key] = new_group_id
        else:
            # Custom group assignment
            if profile.key in overrides:
                del overrides[profile.key]
            target = next((g for g in self.custom_groups if g.id == new_group_id), None)
            if target and profile.key not in target.profile_keys:
                target.profile_keys.append(profile.key)

        GroupManager.save_data(self.custom_groups, overrides)
        GroupManager.apply_groups_to_profiles(self.profiles, self.custom_groups, overrides)
        self._render_group_tabs()
        self._filter_and_render_sidebar()

        for (r, c), p in self.grid_assignments.items():
            if p and p.key == profile.key:
                self.grid_assignments[(r, c)] = profile
                if (r, c) in self.cell_widgets:
                    is_compact = (self.current_cols >= 4 or self.current_rows >= 3)
                    self.cell_widgets[(r, c)].set_profile(profile, is_compact=is_compact)

        self.lbl_status.configure(text=f"Updated group assignment for '{profile.display_name}'.")

    # -----------------------------------------------------------------------
    # Center Preview Area
    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Center Preview Area & Navigation Tabs
    # -----------------------------------------------------------------------
    def _build_center_grid_area(self):
        self.center_area = ctk.CTkFrame(self, fg_color=COLOR_BG_DARK, corner_radius=0)
        self.center_area.grid(row=1, column=1, sticky="nsew", padx=14, pady=14)
        self.center_area.grid_rowconfigure(1, weight=1)
        self.center_area.grid_columnconfigure(0, weight=1)

        # Tab Navigation Header
        self._build_center_nav_tabs()

        # Workspace Tab 1: Grid Arrangement Container
        self.grid_container = ctk.CTkScrollableFrame(
            self.center_area,
            fg_color=COLOR_STATUSBAR_BG,
            corner_radius=14
        )
        self.grid_container.grid(row=1, column=0, sticky="nsew")

        # Workspace Tab 2: Refresh All Tab Container
        self._build_refresh_all_tab()

        # Workspace Tab 3: Slot Clicker Tab Container
        self._build_slot_clicker_tab()

        # Workspace Tab 4: Thunder Configurateur Container
        self._build_thunder_tab()

    def _build_center_nav_tabs(self):
        self.center_nav_bar = ctk.CTkFrame(self.center_area, fg_color="transparent", height=38)
        self.center_nav_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.center_nav_bar.grid_columnconfigure(2, weight=1)

        self.btn_nav_grid = ctk.CTkButton(
            self.center_nav_bar,
            text="🖥️ Grid Arrangement",
            width=170,
            height=34,
            corner_radius=8,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._switch_main_workspace_tab("grid")
        )
        self.btn_nav_grid.pack(side="left", padx=(0, 6))

        self.btn_nav_refresh = ctk.CTkButton(
            self.center_nav_bar,
            text="🔄 Refresh All Tab (0)",
            width=185,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._switch_main_workspace_tab("refresh")
        )
        self.btn_nav_refresh.pack(side="left", padx=2)

        self.btn_nav_slot_clicker = ctk.CTkButton(
            self.center_nav_bar,
            text="⏱️ Slot Clicker",
            width=155,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._switch_main_workspace_tab("slot_clicker")
        )
        self.btn_nav_slot_clicker.pack(side="left", padx=2)

        self.btn_nav_thunder = ctk.CTkButton(
            self.center_nav_bar,
            text="⚡ Thunder Configurateur",
            width=195,
            height=34,
            corner_radius=8,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._switch_main_workspace_tab("thunder")
        )
        self.btn_nav_thunder.pack(side="left", padx=2)

        # Server status badge on right side of nav bar
        self.lbl_nav_server_status = ctk.CTkLabel(
            self.center_nav_bar,
            text="🟢 Server: ws://127.0.0.1:8765",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_SUCCESS
        )
        self.lbl_nav_server_status.pack(side="right", padx=(10, 4))

    def _switch_main_workspace_tab(self, tab_name: str):
        self.active_workspace_tab = tab_name

        # Hide all workspace frames first
        for attr in ("grid_container", "refresh_all_tab_frame", "slot_clicker_tab_frame", "thunder_tab_frame"):
            if hasattr(self, attr):
                try:
                    getattr(self, attr).grid_remove()
                except Exception:
                    pass

        # Reset all nav button colors
        nav_default = {"fg_color": COLOR_CARD_BG, "hover_color": COLOR_CARD_HOVER}
        nav_active  = {"fg_color": COLOR_ACCENT,   "hover_color": COLOR_ACCENT_HOVER}
        for btn_attr in ("btn_nav_grid", "btn_nav_refresh", "btn_nav_slot_clicker", "btn_nav_thunder"):
            if hasattr(self, btn_attr):
                getattr(self, btn_attr).configure(**nav_default)

        if tab_name == "grid":
            if hasattr(self, "grid_container"):
                self.grid_container.grid(row=1, column=0, sticky="nsew")
            if hasattr(self, "btn_nav_grid"):
                self.btn_nav_grid.configure(**nav_active)
            self.lbl_status.configure(text="Switched to Grid Arrangement workspace.")
        elif tab_name == "refresh":
            if hasattr(self, "refresh_all_tab_frame"):
                self.refresh_all_tab_frame.grid(row=1, column=0, sticky="nsew")
            if hasattr(self, "btn_nav_refresh"):
                self.btn_nav_refresh.configure(**nav_active)
            self._update_refresh_ui_stats()
            self._render_connected_tabs_list()
            self.lbl_status.configure(text="Switched to Remote Refresh Controller tab.")
        elif tab_name == "slot_clicker":
            if hasattr(self, "slot_clicker_tab_frame"):
                self.slot_clicker_tab_frame.grid(row=1, column=0, sticky="nsew")
            if hasattr(self, "btn_nav_slot_clicker"):
                self.btn_nav_slot_clicker.configure(**nav_active)
            self.lbl_status.configure(text="Switched to Slot Clicker — configure Sec/MS/Delay then send.")
        elif tab_name == "thunder":
            if hasattr(self, "thunder_tab_frame"):
                self.thunder_tab_frame.grid(row=1, column=0, sticky="nsew")
            if hasattr(self, "btn_nav_thunder"):
                self.btn_nav_thunder.configure(**nav_active)
            self._render_thunder_chrome_grid()
            self.lbl_status.configure(text="Switched to Thunder Configurateur — select Chromes/rows and apply settings.")

    def _build_refresh_all_tab(self):
        self.refresh_all_tab_frame = ctk.CTkFrame(self.center_area, fg_color="transparent")
        self.refresh_all_tab_frame.grid_rowconfigure(2, weight=1)
        self.refresh_all_tab_frame.grid_columnconfigure(0, weight=1)

        # -------------------------------------------------------------------
        # 1. Hero Card: Primary Action & Live Metric Counters
        # -------------------------------------------------------------------
        hero_card = ctk.CTkFrame(
            self.refresh_all_tab_frame,
            fg_color=COLOR_CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        hero_card.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=2)
        hero_card.grid_columnconfigure(0, weight=1)

        hero_content = ctk.CTkFrame(hero_card, fg_color="transparent")
        hero_content.pack(fill="x", padx=18, pady=16)
        hero_content.grid_columnconfigure(0, weight=1)
        hero_content.grid_columnconfigure(1, weight=0)

        # Left: Titles and Action Buttons
        hero_left = ctk.CTkFrame(hero_content, fg_color="transparent")
        hero_left.grid(row=0, column=0, sticky="w")

        title_box = ctk.CTkFrame(hero_left, fg_color="transparent")
        title_box.pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            title_box,
            text="⚡ Remote Refresh Control Center",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkLabel(
            hero_left,
            text="Triggers an automated click on the webpage's Refresh button across all active Chrome profiles simultaneously.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 12))

        btn_row = ctk.CTkFrame(hero_left, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(0, 6))

        self.btn_hero_refresh = ctk.CTkButton(
            btn_row,
            text="⚡ REFRESH ALL CHROME TABS",
            height=40,
            width=250,
            corner_radius=8,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFFFFF",
            command=self._trigger_refresh_all
        )
        self.btn_hero_refresh.pack(side="left", padx=(0, 8))

        self.btn_hero_live_update = ctk.CTkButton(
            btn_row,
            text="⚡ Live Update Script (Existing Windows)",
            height=40,
            width=270,
            corner_radius=8,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFFFFF",
            command=self._live_update_userscript_in_open_tabs
        )
        self.btn_hero_live_update.pack(side="left", padx=(0, 8))

        btn_row2 = ctk.CTkFrame(hero_left, fg_color="transparent")
        btn_row2.pack(anchor="w")

        self.btn_hero_auto_profiles = ctk.CTkButton(
            btn_row2,
            text="🚀 Auto-Open in Profiles...",
            height=32,
            width=180,
            corner_radius=7,
            fg_color="#1E3A8A",
            hover_color="#2563EB",
            border_width=1,
            border_color="#3B82F6",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#93C5FD",
            command=self._open_install_in_profiles_modal
        )
        self.btn_hero_auto_profiles.pack(side="left", padx=(0, 8))

        self.btn_hero_copy_script = ctk.CTkButton(
            btn_row2,
            text="📋 Copy Tampermonkey Script",
            height=32,
            width=190,
            corner_radius=7,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._copy_userscript_to_clipboard
        )
        self.btn_hero_copy_script.pack(side="left", padx=(0, 8))

        self.btn_hero_install_script = ctk.CTkButton(
            btn_row2,
            text="🌐 1-Click Install in Chrome",
            height=32,
            width=180,
            corner_radius=7,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._open_userscript_install_page
        )
        self.btn_hero_install_script.pack(side="left")

        # Right: Metric Stat Cards (Connected Tabs, Sent, Success, Failed)
        hero_stats = ctk.CTkFrame(hero_content, fg_color="transparent")
        hero_stats.grid(row=0, column=1, sticky="e", padx=(18, 0))

        def make_stat_box(parent, title, val, color):
            box = ctk.CTkFrame(parent, fg_color=COLOR_SIDEBAR_BG, corner_radius=10, width=95, height=72)
            box.pack_propagate(False)
            box.pack(side="left", padx=4)
            lbl_v = ctk.CTkLabel(box, text=val, font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=color)
            lbl_v.pack(pady=(10, 0))
            lbl_t = ctk.CTkLabel(box, text=title, font=ctk.CTkFont(family="Segoe UI", size=10), text_color=COLOR_TEXT_MUTED)
            lbl_t.pack()
            return lbl_v

        self.lbl_stat_tabs = make_stat_box(hero_stats, "Connected Tabs", "0", COLOR_ACCENT)
        self.lbl_stat_broadcasts = make_stat_box(hero_stats, "Refreshes Sent", "0", COLOR_TEXT_PRIMARY)
        self.lbl_stat_success = make_stat_box(hero_stats, "Success ACKs", "0", COLOR_SUCCESS)
        self.lbl_stat_failed = make_stat_box(hero_stats, "Failed", "0", COLOR_DANGER)

        # -------------------------------------------------------------------
        # 2. Config & Server Settings Row (2 Cards)
        # -------------------------------------------------------------------
        settings_row = ctk.CTkFrame(self.refresh_all_tab_frame, fg_color="transparent")
        settings_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        settings_row.grid_columnconfigure(0, weight=3)
        settings_row.grid_columnconfigure(1, weight=2)

        # Card A: Target Button Selector & Execution Parameters
        card_selector = ctk.CTkFrame(settings_row, fg_color=COLOR_CARD_BG, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        card_selector.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        sel_hdr = ctk.CTkFrame(card_selector, fg_color="transparent")
        sel_hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            sel_hdr,
            text="🎯 Target Button Locator & Timing",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        # Row 1: XPath
        row_xpath = ctk.CTkFrame(card_selector, fg_color="transparent")
        row_xpath.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row_xpath, text="XPath:", width=65, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.entry_xpath = ctk.CTkEntry(
            row_xpath,
            height=30,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.entry_xpath.insert(0, "/html/body/div[5]/div[1]/button[1]")
        self.entry_xpath.pack(side="left", fill="x", expand=True)

        # Row 2: Text & Class
        row_text_class = ctk.CTkFrame(card_selector, fg_color="transparent")
        row_text_class.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row_text_class, text="Button Text:", width=65, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.entry_text = ctk.CTkEntry(
            row_text_class,
            width=110,
            height=30,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11)
        )
        self.entry_text.insert(0, "Refresh")
        self.entry_text.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row_text_class, text="Class:", width=42, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.entry_class = ctk.CTkEntry(
            row_text_class,
            height=30,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11)
        )
        self.entry_class.insert(0, "btn btn-primary")
        self.entry_class.pack(side="left", fill="x", expand=True)

        # Row 3: Stagger & Auto-Refresh Timer
        row_timing = ctk.CTkFrame(card_selector, fg_color="transparent")
        row_timing.pack(fill="x", padx=14, pady=(3, 12))
        ctk.CTkLabel(row_timing, text="Dispatch:", width=65, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.opt_stagger = ctk.CTkOptionMenu(
            row_timing,
            values=["Simultaneous (0ms)", "25ms stagger", "50ms stagger", "100ms stagger", "250ms stagger"],
            height=28,
            width=145,
            fg_color=COLOR_SIDEBAR_BG,
            button_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11)
        )
        self.opt_stagger.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row_timing, text="Auto-Refresh:", width=80, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.opt_auto_refresh = ctk.CTkOptionMenu(
            row_timing,
            values=["Off", "15 seconds", "30 seconds", "1 minute", "2 minutes", "5 minutes"],
            height=28,
            width=120,
            fg_color=COLOR_SIDEBAR_BG,
            button_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=self._on_auto_refresh_changed
        )
        self.opt_auto_refresh.pack(side="left")

        # Card B: Local Server Control & Options
        card_server = ctk.CTkFrame(settings_row, fg_color=COLOR_CARD_BG, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        card_server.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        srv_hdr = ctk.CTkFrame(card_server, fg_color="transparent")
        srv_hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            srv_hdr,
            text="📡 Local WebSocket & HTTP Server",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        # Server Status Pill
        row_srv1 = ctk.CTkFrame(card_server, fg_color="transparent")
        row_srv1.pack(fill="x", padx=14, pady=3)
        self.lbl_server_pill = ctk.CTkLabel(
            row_srv1,
            text="🟢 Server Active: ws://127.0.0.1:8765",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_SUCCESS
        )
        self.lbl_server_pill.pack(side="left")

        # Port configuration row
        row_srv2 = ctk.CTkFrame(card_server, fg_color="transparent")
        row_srv2.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(row_srv2, text="Port:", width=40, anchor="w", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self.entry_server_port = ctk.CTkEntry(
            row_srv2,
            width=70,
            height=28,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11)
        )
        self.entry_server_port.insert(0, str(self.refresh_server.port))
        self.entry_server_port.pack(side="left", padx=(0, 8))

        self.btn_toggle_server = ctk.CTkButton(
            row_srv2,
            text="Stop Server",
            width=90,
            height=28,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_DANGER_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11),
            command=self._toggle_server_state
        )
        self.btn_toggle_server.pack(side="left", padx=(0, 6))

        self.btn_restart_server = ctk.CTkButton(
            row_srv2,
            text="Restart",
            width=70,
            height=28,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11),
            command=self._restart_refresh_server
        )
        self.btn_restart_server.pack(side="left", padx=(0, 6))

        self.btn_ping_tabs = ctk.CTkButton(
            row_srv2,
            text="📡 Ping All",
            width=80,
            height=28,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_ACCENT_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=11),
            command=self._ping_all_tabs
        )
        self.btn_ping_tabs.pack(side="left")

        # -------------------------------------------------------------------
        # 3. Live Activity Area: Connected Tabs List & Event Log
        # -------------------------------------------------------------------
        activity_row = ctk.CTkFrame(self.refresh_all_tab_frame, fg_color="transparent")
        activity_row.grid(row=2, column=0, sticky="nsew")
        activity_row.grid_rowconfigure(0, weight=1)
        activity_row.grid_columnconfigure(0, weight=3)  # Tabs List
        activity_row.grid_columnconfigure(1, weight=2)  # Log Textbox

        # Left: Connected Tabs List Frame
        left_box = ctk.CTkFrame(activity_row, fg_color=COLOR_CARD_BG, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_box.grid_rowconfigure(1, weight=1)
        left_box.grid_columnconfigure(0, weight=1)

        tab_list_hdr = ctk.CTkFrame(left_box, fg_color="transparent")
        tab_list_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        self.lbl_connected_tabs_hdr = ctk.CTkLabel(
            tab_list_hdr,
            text="Connected Chrome Profiles & Tabs (0)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.lbl_connected_tabs_hdr.pack(side="left")

        btn_refresh_list = ctk.CTkButton(
            tab_list_hdr,
            text="🔄 Refresh List",
            width=90,
            height=24,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10),
            command=self._render_connected_tabs_list
        )
        btn_refresh_list.pack(side="right")

        self.scroll_connected_tabs = ctk.CTkScrollableFrame(
            left_box,
            fg_color="transparent",
            corner_radius=8
        )
        self.scroll_connected_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_connected_tabs.grid_columnconfigure(0, weight=1)

        # Right: Real-time Event Log Frame
        right_box = ctk.CTkFrame(activity_row, fg_color=COLOR_CARD_BG, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        right_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_box.grid_rowconfigure(1, weight=1)
        right_box.grid_columnconfigure(0, weight=1)

        log_hdr = ctk.CTkFrame(right_box, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        ctk.CTkLabel(
            log_hdr,
            text="Activity & Execution Log",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        btn_clear_log = ctk.CTkButton(
            log_hdr,
            text="Clear",
            width=50,
            height=24,
            corner_radius=6,
            fg_color=COLOR_SIDEBAR_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10),
            command=self._clear_refresh_log
        )
        btn_clear_log.pack(side="right")

        self.txt_refresh_log = ctk.CTkTextbox(
            right_box,
            fg_color=COLOR_SIDEBAR_BG,
            text_color=COLOR_TEXT_SECONDARY,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        self.txt_refresh_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_refresh_log.configure(state="disabled")

        # Initial render of tabs list
        self._render_connected_tabs_list()

    # -----------------------------------------------------------------------
    # Slot Clicker Tab
    # -----------------------------------------------------------------------
    def _build_slot_clicker_tab(self):
        """Builds the Slot Clicker workspace tab.

        Two cards let the user configure Sec / MS independently for:
          Page A — BLS SlotSelection page (XPath-based inputs)
          Page B — BLS SPA page (#InputSec / #InputMs)
        Each card has its own dedicated Send button and independent Step increment.
        """
        self.slot_clicker_tab_frame = ctk.CTkFrame(self.center_area, fg_color="transparent")
        self.slot_clicker_tab_frame.grid_rowconfigure(1, weight=1)
        self.slot_clicker_tab_frame.grid_columnconfigure(0, weight=1)
        self.slot_clicker_tab_frame.grid_remove()  # hidden by default

        # -------------------------------------------------------------------
        # Hero header card
        # -------------------------------------------------------------------
        hero = ctk.CTkFrame(
            self.slot_clicker_tab_frame,
            fg_color=COLOR_CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=2)

        hero_inner = ctk.CTkFrame(hero, fg_color="transparent")
        hero_inner.pack(fill="x", padx=18, pady=12)

        title_row = ctk.CTkFrame(hero_inner, fg_color="transparent")
        title_row.pack(anchor="w", pady=(0, 2), fill="x")

        ctk.CTkLabel(
            title_row,
            text="⏱️ Timed Slot Input Clicker",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            title_row,
            text="⚡ Live Update Script (Existing Windows)",
            height=30,
            width=260,
            corner_radius=7,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#FFFFFF",
            command=self._live_update_userscript_in_open_tabs
        ).pack(side="right")

        ctk.CTkLabel(
            hero_inner,
            text=(
                "Configure Sec, MS, and independent Step Count (\"Delay\") for each page. "
                "Each page has its own dedicated Send button and increments its own step independently per Chrome."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=820,
            justify="left"
        ).pack(anchor="w")

        # -------------------------------------------------------------------
        # Two config cards side by side
        # -------------------------------------------------------------------
        cards_row = ctk.CTkFrame(self.slot_clicker_tab_frame, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="nsew", padx=2)
        cards_row.grid_columnconfigure(0, weight=1)
        cards_row.grid_columnconfigure(1, weight=1)
        cards_row.grid_rowconfigure(0, weight=0)

        def _build_page_card(parent, col, title, badge_color, badge_text, page_key, btn_text, btn_color, btn_hover, send_cmd):
            """Builds one Page card with fields and dedicated Send button."""
            card = ctk.CTkFrame(
                parent,
                fg_color=COLOR_CARD_BG,
                corner_radius=12,
                border_width=1,
                border_color=COLOR_BORDER
            )
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0, 6) if col == 0 else (6, 0))

            # Card header
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=16, pady=(14, 6))

            badge = ctk.CTkLabel(
                hdr,
                text=badge_text,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="white",
                fg_color=badge_color,
                corner_radius=6,
                width=56,
                height=22
            )
            badge.pack(side="left", padx=(0, 10))

            ctk.CTkLabel(
                hdr,
                text=title,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY
            ).pack(side="left")

            # URL hint
            url_hint = {
                "a": "morocco.blsportugal.com/…/SlotSelection  •  XPath input[2] (sec) / input[3] (ms)",
                "b": "morocco.blsportugal.com  •  #InputSec / #InputMs"
            }[page_key]
            ctk.CTkLabel(
                card,
                text=url_hint,
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill="x", padx=16, pady=(0, 10))

            sep = ctk.CTkFrame(card, fg_color=COLOR_BORDER, height=1)
            sep.pack(fill="x", padx=12, pady=(0, 12))

            # Input fields
            fields_frame = ctk.CTkFrame(card, fg_color="transparent")
            fields_frame.pack(fill="x", padx=16, pady=(0, 10))
            fields_frame.grid_columnconfigure(1, weight=1)

            def _field_row(row_idx, label, placeholder, min_v, max_v, default_val, width=90):
                var = tk.StringVar(value=str(default_val))
                ctk.CTkLabel(
                    fields_frame,
                    text=label,
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                    text_color=COLOR_TEXT_SECONDARY,
                    anchor="w",
                    width=175
                ).grid(row=row_idx, column=0, sticky="w", pady=6)

                entry = ctk.CTkEntry(
                    fields_frame,
                    textvariable=var,
                    width=width,
                    height=36,
                    fg_color=COLOR_SIDEBAR_BG,
                    border_color=COLOR_BORDER,
                    font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                    justify="center",
                    placeholder_text=placeholder
                )
                entry.grid(row=row_idx, column=1, sticky="w", padx=(8, 0), pady=6)

                # Range label
                ctk.CTkLabel(
                    fields_frame,
                    text=f"{min_v}\u2013{max_v}",
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w"
                ).grid(row=row_idx, column=2, sticky="w", padx=(8, 0), pady=6)

                return var

            sec_var     = _field_row(0, "Seconds (sec)",                 "00",  0,  59, 0)
            ms_var      = _field_row(1, "Milliseconds (ms)",              "000", 0, 999, 0)
            ms_step_var = _field_row(2, 'MS Step ("Delay") / Chrome',    "0",   0, 999, 0)

            # Info label at bottom of card
            ctk.CTkLabel(
                card,
                text="ℹ️ Chrome 1: ms=base  •  Chrome 2: ms=base+step  •  Chrome N: ms=base+(N−1)×step",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLOR_TEXT_MUTED,
                anchor="w",
                wraplength=340,
                justify="left"
            ).pack(fill="x", padx=16, pady=(0, 14))

            # Dedicated Send button for this card
            btn_send = ctk.CTkButton(
                card,
                text=btn_text,
                height=42,
                corner_radius=8,
                fg_color=btn_color,
                hover_color=btn_hover,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color="#FFFFFF",
                command=send_cmd
            )
            btn_send.pack(fill="x", padx=16, pady=(0, 16))

            return sec_var, ms_var, ms_step_var, btn_send

        (self.slot_a_sec, self.slot_a_ms, self.slot_a_ms_step, self.btn_slot_send_a) = _build_page_card(
            cards_row, 0,
            title="Page A — Calendar",
            badge_color="#1D4ED8",
            badge_text="PAGE A",
            page_key="a",
            btn_text="⚡ SEND CALENDAR (PAGE A)",
            btn_color="#1D4ED8",
            btn_hover="#1E40AF",
            send_cmd=self._trigger_slot_click_a
        )

        (self.slot_b_sec, self.slot_b_ms, self.slot_b_ms_step, self.btn_slot_send_b) = _build_page_card(
            cards_row, 1,
            title="Page B — VisaType",
            badge_color="#065F46",
            badge_text="PAGE B",
            page_key="b",
            btn_text="⚡ SEND VISATYPE (PAGE B)",
            btn_color="#059669",
            btn_hover="#047857",
            send_cmd=self._trigger_slot_click_b
        )

    def _trigger_slot_click_a(self):
        """Sends Sec/MS values specifically to Page A (Calendar) tabs."""
        self._dispatch_slot_page("a")

    def _trigger_slot_click_b(self):
        """Sends Sec/MS values specifically to Page B (VisaType) tabs."""
        self._dispatch_slot_page("b")

    def _trigger_slot_click(self):
        """Broadcasts slot values to all pages."""
        self._dispatch_slot_page("all")

    def _dispatch_slot_page(self, target: str):
        """Reads values and broadcasts slot_click to the specified target ('a', 'b', or 'all')."""
        def _safe_int(var, lo, hi, default=0):
            try:
                return max(lo, min(hi, int(var.get().strip() or default)))
            except (ValueError, AttributeError):
                return default

        a_sec  = _safe_int(getattr(self, "slot_a_sec", None),     0,  59)
        a_ms   = _safe_int(getattr(self, "slot_a_ms", None),      0, 999)
        a_step = _safe_int(getattr(self, "slot_a_ms_step", None), 0, 999)
        b_sec  = _safe_int(getattr(self, "slot_b_sec", None),     0,  59)
        b_ms   = _safe_int(getattr(self, "slot_b_ms", None),      0, 999)
        b_step = _safe_int(getattr(self, "slot_b_ms_step", None), 0, 999)

        # Visual feedback on the corresponding Send button
        if target == "a" and hasattr(self, "btn_slot_send_a"):
            self.btn_slot_send_a.configure(text="⏳ SENDING...", fg_color=COLOR_WARNING)
            self.after(600, lambda: self.btn_slot_send_a.configure(
                text="⚡ SEND CALENDAR (PAGE A)", fg_color="#1D4ED8"
            ))
        elif target == "b" and hasattr(self, "btn_slot_send_b"):
            self.btn_slot_send_b.configure(text="⏳ SENDING...", fg_color=COLOR_WARNING)
            self.after(600, lambda: self.btn_slot_send_b.configure(
                text="⚡ SEND VISATYPE (PAGE B)", fg_color="#059669"
            ))

        client_count = len(self.refresh_server.clients) + len(self.refresh_server.http_clients)
        self.refresh_server.broadcast_slot_click(
            target=target,
            page_a_sec=a_sec,
            page_a_ms=a_ms,
            page_a_ms_step=a_step,
            page_b_sec=b_sec,
            page_b_ms=b_ms,
            page_b_ms_step=b_step,
        )

        if client_count == 0:
            self.lbl_status.configure(
                text=f"⚠️ Slot-click ({target.upper()}) sent, but 0 Chrome tabs are connected to the server."
            )
        else:
            if target == "a":
                self.lbl_status.configure(
                    text=f"⚡ Slot-Click → Calendar (Page A) | Sec: {a_sec:02d}s | MS: {a_ms}ms | Step: +{a_step}ms/Chrome"
                )
            elif target == "b":
                self.lbl_status.configure(
                    text=f"⚡ Slot-Click → VisaType (Page B) | Sec: {b_sec:02d}s | MS: {b_ms}ms | Step: +{b_step}ms/Chrome"
                )
            else:
                self.lbl_status.configure(
                    text=(
                        f"⚡ Slot-Click → {client_count} Chrome(s) — "
                        f"A: {a_sec:02d}s / ms={a_ms} step={a_step} | "
                        f"B: {b_sec:02d}s / ms={b_ms} step={b_step}"
                    )
                )

    # -----------------------------------------------------------------------
    # Thunder Configurateur Tab & Bulk Chrome Layout Controller
    # -----------------------------------------------------------------------

    def _init_thunder_state(self):
        """Initializes state variables and presets for Thunder Configurateur."""
        self.thunder_presets = self._load_thunder_presets()
        preset_names = list(self.thunder_presets.keys())
        self.thunder_active_preset_name = preset_names[0] if preset_names else "Default"
        self.thunder_region = ctk.StringVar(value="Spain")

        # Advanced Settings (vtData)
        self.thunder_visa_type = ctk.StringVar(value="Schengen Visa")
        self.thunder_center = ctk.StringVar(value="Casablanca")
        self.thunder_category = ctk.StringVar(value="Normal")
        self.thunder_members = ctk.StringVar(value="1")

        # Active subtab in Thunder config panel
        self.thunder_active_subtab = "advanced"

        # Selection of cells in the layout: set of (row, col)
        self.thunder_selected_cells = set()
        self.thunder_cell_cards = {}
        self.thunder_subtab_frames = {}

        # Per-cell configuration store: key is "r,c" string -> Dict[str, Any]
        self.thunder_cell_configs: Dict[str, Dict[str, Any]] = self._load_thunder_cell_configs()
        # Currently inspected cell for live display: (r, c) or None
        self.thunder_inspected_cell: Optional[Tuple[int, int]] = None

        # Apply default preset values if found
        default_cfg = self.thunder_presets.get(self.thunder_active_preset_name, {})
        if default_cfg:
            self._apply_thunder_dict_to_vars(default_cfg)

    def _load_thunder_cell_configs(self) -> Dict[str, Any]:
        if os.path.exists(THUNDER_CELL_CONFIGS_FILE):
            try:
                with open(THUNDER_CELL_CONFIGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"[Thunder] Failed to load cell configs: {e}")
        return {}

    def _save_thunder_cell_configs(self):
        try:
            with open(THUNDER_CELL_CONFIGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.thunder_cell_configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Thunder] Failed to save cell configs: {e}")

    def _load_thunder_presets(self) -> Dict[str, Any]:
        default_preset = {
            "Spain Default": {
                "region": "Spain",
                "vtData": {
                    "city": "Casablanca",
                    "category": "Normal",
                    "type": "Schengen Visa",
                    "members": 1
                }
            },
            "Portugal Default": {
                "region": "Portugal",
                "vtData": {
                    "city": "Casablanca",
                    "category": "Normal",
                    "type": "Short Stay Visa",
                    "members": 1
                }
            }
        }
        if os.path.exists(THUNDER_PRESETS_FILE):
            try:
                with open(THUNDER_PRESETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        clean_data = {}
                        for k, v in data.items():
                            if isinstance(v, dict):
                                clean_cfg = {"region": v.get("region", "Spain")}
                                if "vtData" in v and isinstance(v["vtData"], dict):
                                    clean_cfg["vtData"] = v["vtData"]
                                else:
                                    clean_cfg["vtData"] = default_preset.get("Spain Default", {}).get("vtData", {})
                                clean_data[k] = clean_cfg
                        for k, v in default_preset.items():
                            if k not in clean_data:
                                clean_data[k] = v
                        return clean_data
            except Exception as e:
                print(f"[Thunder] Failed to load presets: {e}")
        return default_preset

    def _save_thunder_presets(self, presets: Dict[str, Any]):
        try:
            with open(THUNDER_PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Thunder] Failed to save presets: {e}")

    def _apply_thunder_region_options(self, region_key: str):
        if region_key not in THUNDER_REGION_CONFIGS:
            region_key = "Spain"
        cfg = THUNDER_REGION_CONFIGS[region_key]
        self.thunder_region.set(region_key)

        if hasattr(self, "lbl_thunder_version_tag"):
            self.lbl_thunder_version_tag.configure(text=f" {cfg['title']}")

        if hasattr(self, "combo_thunder_visa_type"):
            self.combo_thunder_visa_type.configure(values=cfg["visa_types"])
            if self.thunder_visa_type.get() not in cfg["visa_types"]:
                self.thunder_visa_type.set(cfg["visa_types"][0])

        if hasattr(self, "combo_thunder_center"):
            self.combo_thunder_center.configure(values=cfg["centers"])
            if self.thunder_center.get() not in cfg["centers"]:
                self.thunder_center.set(cfg["centers"][0])

        if hasattr(self, "combo_thunder_category"):
            self.combo_thunder_category.configure(values=cfg["categories"])
            if self.thunder_category.get() not in cfg["categories"]:
                self.thunder_category.set(cfg["categories"][0])

        if hasattr(self, "combo_thunder_members"):
            self.combo_thunder_members.configure(values=cfg["members"])
            if self.thunder_members.get() not in cfg["members"]:
                self.thunder_members.set(cfg["members"][0])

    def _on_thunder_region_segmented_changed(self, choice: str):
        reg = "Portugal" if "Portugal" in choice else "Spain"
        self._apply_thunder_region_options(reg)
        if hasattr(self, "lbl_thunder_status"):
            self.lbl_thunder_status.configure(text=f"Switched Thunder options to {choice} ({THUNDER_REGION_CONFIGS[reg]['title']})")

    def _apply_thunder_dict_to_vars(self, cfg: Dict[str, Any]):
        reg = cfg.get("region", "Spain")
        self.thunder_region.set(reg)
        if hasattr(self, "seg_thunder_region"):
            self.seg_thunder_region.set("🇵🇹 Portugal" if reg == "Portugal" else "🇪🇸 Spain")
        self._apply_thunder_region_options(reg)

        reg_cfg = THUNDER_REGION_CONFIGS.get(reg, THUNDER_REGION_CONFIGS["Spain"])

        vt = cfg.get("vtData", {})
        vtype = vt.get("type", reg_cfg["visa_types"][0])
        city = vt.get("city", reg_cfg["centers"][0])
        cat = vt.get("category", reg_cfg["categories"][0])
        mems = str(vt.get("members", 1))

        if vtype not in reg_cfg["visa_types"]:
            vtype = reg_cfg["visa_types"][0]
        if city not in reg_cfg["centers"]:
            city = reg_cfg["centers"][0]
        if cat not in reg_cfg["categories"]:
            cat = reg_cfg["categories"][0]
        if mems not in reg_cfg["members"]:
            mems = reg_cfg["members"][0]

        self.thunder_visa_type.set(vtype)
        if hasattr(self, "combo_thunder_visa_type"):
            self.combo_thunder_visa_type.configure(values=reg_cfg["visa_types"])
            self.combo_thunder_visa_type.set(vtype)

        self.thunder_center.set(city)
        if hasattr(self, "combo_thunder_center"):
            self.combo_thunder_center.configure(values=reg_cfg["centers"])
            self.combo_thunder_center.set(city)

        self.thunder_category.set(cat)
        if hasattr(self, "combo_thunder_category"):
            self.combo_thunder_category.configure(values=reg_cfg["categories"])
            self.combo_thunder_category.set(cat)

        self.thunder_members.set(mems)
        if hasattr(self, "combo_thunder_members"):
            self.combo_thunder_members.configure(values=reg_cfg["members"])
            self.combo_thunder_members.set(mems)

    def _get_current_thunder_config_dict(self) -> Dict[str, Any]:
        try:
            members_val = int(self.thunder_members.get().strip() or "1")
        except Exception:
            members_val = 1

        reg_name = self.thunder_region.get() if hasattr(self, "thunder_region") else "Spain"

        return {
            "region": reg_name,
            "vtData": {
                "city": self.thunder_center.get(),
                "category": self.thunder_category.get(),
                "type": self.thunder_visa_type.get(),
                "members": members_val
            }
        }

    def _build_thunder_tab(self):
        """Builds the complete Thunder Configurateur workspace tab."""
        self.thunder_tab_frame = ctk.CTkFrame(self.center_area, fg_color="transparent")
        self.thunder_tab_frame.grid_rowconfigure(1, weight=1)
        self.thunder_tab_frame.grid_columnconfigure(0, weight=1)
        self.thunder_tab_frame.grid_remove()

        # -------------------------------------------------------------------
        # 1. Hero Header Card with Preset Controls
        # -------------------------------------------------------------------
        hero = ctk.CTkFrame(
            self.thunder_tab_frame,
            fg_color=COLOR_CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=2)

        hero_inner = ctk.CTkFrame(hero, fg_color="transparent")
        hero_inner.pack(fill="x", padx=18, pady=12)

        top_line = ctk.CTkFrame(hero_inner, fg_color="transparent")
        top_line.pack(fill="x")

        title_box = ctk.CTkFrame(top_line, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="⚡ Thunder Configurateur",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#F59E0B"
        ).pack(side="left")

        current_reg = self.thunder_region.get() if hasattr(self, "thunder_region") else "Spain"
        cfg = THUNDER_REGION_CONFIGS.get(current_reg, THUNDER_REGION_CONFIGS["Spain"])

        self.lbl_thunder_version_tag = ctk.CTkLabel(
            title_box,
            text=f" {cfg['title']}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_thunder_version_tag.pack(side="left", padx=(4, 12), pady=(4, 0))

        # Target Region Selector (Spain vs Portugal)
        self.seg_thunder_region = ctk.CTkSegmentedButton(
            title_box,
            values=["🇪🇸 Spain", "🇵🇹 Portugal"],
            command=self._on_thunder_region_segmented_changed,
            height=28,
            corner_radius=6,
            selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.seg_thunder_region.set("🇵🇹 Portugal" if current_reg == "Portugal" else "🇪🇸 Spain")
        self.seg_thunder_region.pack(side="left", padx=(2, 0))

        # Presets Bar on the right
        presets_bar = ctk.CTkFrame(top_line, fg_color="transparent")
        presets_bar.pack(side="right")

        ctk.CTkLabel(
            presets_bar,
            text="Preset:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        preset_names = list(self.thunder_presets.keys()) or ["Default"]
        self.combo_thunder_preset = ctk.CTkComboBox(
            presets_bar,
            values=preset_names,
            width=160,
            height=30,
            corner_radius=7,
            command=self._on_thunder_preset_selected
        )
        self.combo_thunder_preset.set(self.thunder_active_preset_name)
        self.combo_thunder_preset.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            presets_bar,
            text="💾 Save As...",
            width=90,
            height=30,
            corner_radius=7,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._save_current_thunder_preset
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            presets_bar,
            text="🗑️ Delete",
            width=72,
            height=30,
            corner_radius=7,
            fg_color=COLOR_DANGER,
            hover_color=COLOR_DANGER_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._delete_current_thunder_preset
        ).pack(side="left", padx=2)

        ctk.CTkLabel(
            hero_inner,
            text="Set up unified extension parameters, select specific Chrome rows or custom instances, and apply settings in bulk with one click.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(anchor="w", pady=(4, 0))

        # -------------------------------------------------------------------
        # 2. Main Dual Panel (Left: Settings, Right: Layout & Selection)
        # -------------------------------------------------------------------
        main_split = ctk.CTkFrame(self.thunder_tab_frame, fg_color="transparent")
        main_split.grid(row=1, column=0, sticky="nsew", padx=2)
        main_split.grid_columnconfigure(0, weight=6)
        main_split.grid_columnconfigure(1, weight=5)
        main_split.grid_rowconfigure(0, weight=1)

        self._build_thunder_left_settings_panel(main_split)
        self._build_thunder_right_layout_panel(main_split)

    def _build_thunder_left_settings_panel(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # Header
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))

        ctk.CTkLabel(
            header_frame,
            text="🎯 Advanced Settings (vtData)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        # Scrollable content area for settings
        self.thunder_settings_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.thunder_settings_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.thunder_settings_scroll.grid_columnconfigure(0, weight=1)

        # Build Advanced vtData fields directly
        self._build_thunder_advanced_subtab()

    def _switch_thunder_subtab(self, subtab_key: str = "advanced"):
        pass

    def _build_thunder_advanced_subtab(self):
        frame = ctk.CTkFrame(self.thunder_settings_scroll, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.thunder_subtab_frames["advanced"] = frame

        # Helpful notice badge
        notice_box = ctk.CTkFrame(frame, fg_color=COLOR_SIDEBAR_BG, corner_radius=8, border_width=1, border_color="#0284C7")
        notice_box.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            notice_box,
            text="🎯 Configures BLS vtData (Visa Type, Center, Category, Members).\nOther automation tabs are disabled to prevent conflicts with external launchers.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#38BDF8",
            justify="left"
        ).pack(padx=12, pady=8, anchor="w")

        reg = self.thunder_region.get() if hasattr(self, "thunder_region") else "Spain"
        cfg = THUNDER_REGION_CONFIGS.get(reg, THUNDER_REGION_CONFIGS["Spain"])

        fields = [
            ("Visa Type :", self.thunder_visa_type, cfg["visa_types"], "combo_thunder_visa_type"),
            ("Center (City) :", self.thunder_center, cfg["centers"], "combo_thunder_center"),
            ("Category :", self.thunder_category, cfg["categories"], "combo_thunder_category"),
            ("Members :", self.thunder_members, cfg["members"], "combo_thunder_members")
        ]

        for label, var, values, attr_name in fields:
            card = ctk.CTkFrame(frame, fg_color=COLOR_SIDEBAR_BG, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
            card.pack(fill="x", pady=4)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                width=110,
                anchor="w"
            ).grid(row=0, column=0, padx=12, pady=10, sticky="w")

            combo = ctk.CTkOptionMenu(
                card,
                values=values,
                variable=var,
                height=32,
                corner_radius=7,
                fg_color=COLOR_CARD_BG,
                button_color=COLOR_BORDER,
                button_hover_color=COLOR_BORDER_ACCENT
            )
            combo.grid(row=0, column=1, padx=12, pady=10, sticky="ew")
            setattr(self, attr_name, combo)

    # -------------------------------------------------------------------
    # Right Panel: Chrome Grid Layout & Row Selection Manager
    # -------------------------------------------------------------------
    def _build_thunder_right_layout_panel(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        card.grid_rowconfigure(3, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # 1. Header
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            head,
            text="🖥️ Chrome Grid Layout & Selection",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        self.lbl_thunder_target_count = ctk.CTkLabel(
            head,
            text="Targeted: 0 / 0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#F59E0B"
        )
        self.lbl_thunder_target_count.pack(side="right")

        # 2. Quick Selection Toolbar (Row buttons, Halves, All/None)
        toolbar = ctk.CTkFrame(card, fg_color=COLOR_SIDEBAR_BG, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))

        toolbar_inner = ctk.CTkScrollableFrame(toolbar, fg_color="transparent", height=42, orientation="horizontal")
        toolbar_inner.pack(fill="x", padx=4, pady=3)

        ctk.CTkLabel(
            toolbar_inner,
            text="Quick Select:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(4, 6))

        ctk.CTkButton(
            toolbar_inner,
            text="Select All",
            width=76,
            height=26,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._thunder_select_all
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            toolbar_inner,
            text="Clear",
            width=58,
            height=26,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._thunder_deselect_all
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            toolbar_inner,
            text="Invert",
            width=58,
            height=26,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._thunder_invert_selection
        ).pack(side="left", padx=2)

        # Top / Bottom halves
        ctk.CTkButton(
            toolbar_inner,
            text="⬆️ Top Half",
            width=80,
            height=26,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._thunder_select_top_half
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            toolbar_inner,
            text="⬇️ Bottom Half",
            width=90,
            height=26,
            corner_radius=6,
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._thunder_select_bottom_half
        ).pack(side="left", padx=2)

        # Dynamic Row Buttons container
        self.thunder_row_btn_container = ctk.CTkFrame(toolbar_inner, fg_color="transparent")
        self.thunder_row_btn_container.pack(side="left", padx=(6, 2))

        # 3. Live Inspector & Quick Actions Bar
        inspector_frame = ctk.CTkFrame(card, fg_color="#0F172A", corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        inspector_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        self.lbl_thunder_inspector = ctk.CTkLabel(
            inspector_frame,
            text="🔍 Click any Chrome tile to inspect or load its configuration",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.lbl_thunder_inspector.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        self.btn_load_thunder_inspector = ctk.CTkButton(
            inspector_frame,
            text="📥 Load into Editor",
            width=130,
            height=26,
            corner_radius=6,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._load_inspected_thunder_config
        )
        self.btn_load_thunder_inspector.pack(side="right", padx=(4, 8), pady=5)

        self.btn_groups_thunder = ctk.CTkButton(
            inspector_frame,
            text="📊 Config Groups",
            width=115,
            height=26,
            corner_radius=6,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._show_thunder_groups_overview
        )
        self.btn_groups_thunder.pack(side="right", padx=2, pady=5)

        # 4. Interactive Visual Grid
        self.thunder_grid_scroll = ctk.CTkScrollableFrame(card, fg_color=COLOR_STATUSBAR_BG, corner_radius=8)
        self.thunder_grid_scroll.grid(row=3, column=0, sticky="nsew", padx=10, pady=2)

        # 5. Action & Execution Footer
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=10, pady=10)

        self.btn_apply_thunder = ctk.CTkButton(
            footer,
            text="⚡ APPLY UNIFIED SETTINGS TO SELECTED CHROMES",
            height=44,
            corner_radius=9,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._apply_thunder_unified_settings
        )
        self.btn_apply_thunder.pack(fill="x", pady=(0, 6))

        # Progress bar & Live log
        self.thunder_progress = ctk.CTkProgressBar(footer, height=6, corner_radius=3, progress_color="#10B981")
        self.thunder_progress.pack(fill="x", pady=(0, 4))
        self.thunder_progress.set(0)

        self.lbl_thunder_status = ctk.CTkLabel(
            footer,
            text="Ready. Select Chromes above, adjust settings, and click Apply.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.lbl_thunder_status.pack(fill="x")

    def _render_thunder_chrome_grid(self):
        """Renders the interactive grid of Chrome cards in Thunder Configurateur with visual config badges."""
        # 1. Update dynamic row buttons in toolbar with city tags
        for w in self.thunder_row_btn_container.winfo_children():
            w.destroy()

        for r in range(self.current_rows):
            row_cities = []
            for c in range(self.current_cols):
                cfg = self.thunder_cell_configs.get(f"{r},{c}")
                if cfg and cfg.get("vtData", {}).get("city"):
                    row_cities.append(cfg.get("vtData", {}).get("city"))

            unique_cities = list(dict.fromkeys(row_cities))
            if len(unique_cities) == 1:
                c_name = unique_cities[0]
                row_label = f"Row {r+1} ({c_name[:4]})"
                c_style = THUNDER_CITY_COLORS.get(c_name, {})
                btn_color = c_style.get("bg", "#1E3A8A")
            elif len(unique_cities) > 1:
                row_label = f"Row {r+1} (Mix)"
                btn_color = "#581C87"
            else:
                row_label = f"Row {r+1}"
                btn_color = "#1E3A8A"

            btn = ctk.CTkButton(
                self.thunder_row_btn_container,
                text=row_label,
                width=62,
                height=26,
                corner_radius=6,
                fg_color=btn_color,
                hover_color="#2563EB",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda row_i=r: self._thunder_select_row(row_i)
            )
            btn.pack(side="left", padx=2)

        # 2. Re-render visual grid
        for w in self.thunder_grid_scroll.winfo_children():
            w.destroy()

        self.thunder_cell_cards.clear()

        for c in range(self.current_cols):
            self.thunder_grid_scroll.grid_columnconfigure(c, weight=1)

        # Default select all if empty initially
        total_cells = self.current_rows * self.current_cols
        if not self.thunder_selected_cells:
            self.thunder_selected_cells = {(r, c) for r in range(self.current_rows) for c in range(self.current_cols)}

        # Check connected tabs from refresh server
        connected_clients = self.refresh_server.get_clients_snapshot() if hasattr(self, "refresh_server") else []
        client_count = len(connected_clients)

        for r in range(self.current_rows):
            for c in range(self.current_cols):
                profile = self.grid_assignments.get((r, c))
                cell_key = (r, c)
                is_selected = cell_key in self.thunder_selected_cells

                # Build cell card
                card = ctk.CTkFrame(
                    self.thunder_grid_scroll,
                    fg_color="#14283b" if is_selected else COLOR_SIDEBAR_BG,
                    corner_radius=8,
                    border_width=2 if is_selected else 1,
                    border_color="#00D2FF" if is_selected else COLOR_BORDER,
                    cursor="hand2"
                )
                card.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

                top_bar = ctk.CTkFrame(card, fg_color="transparent")
                top_bar.pack(fill="x", padx=6, pady=(5, 2))

                pos_lbl = ctk.CTkLabel(
                    top_bar,
                    text=f"[R{r+1}:C{c+1}]",
                    font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                    text_color="#00D2FF" if is_selected else COLOR_TEXT_MUTED
                )
                pos_lbl.pack(side="left")

                check_lbl = ctk.CTkLabel(
                    top_bar,
                    text="✓ TARGETED" if is_selected else "○",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#10B981" if is_selected else COLOR_TEXT_MUTED
                )
                check_lbl.pack(side="right")

                p_name = profile.display_name if profile else "Empty Profile"
                p_lbl = ctk.CTkLabel(
                    card,
                    text=p_name[:16] + ("..." if len(p_name) > 16 else ""),
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=COLOR_TEXT_PRIMARY if profile else COLOR_TEXT_MUTED,
                    anchor="w"
                )
                p_lbl.pack(fill="x", padx=6, pady=(0, 2))

                # Visual Config Badge (City, Visa Type, Region Flag)
                cfg = self.thunder_cell_configs.get(f"{r},{c}")
                if cfg:
                    city = cfg.get("vtData", {}).get("city", "Default")
                    vtype = cfg.get("vtData", {}).get("type", "Visa")
                    mems = cfg.get("vtData", {}).get("members", 1)
                    reg = cfg.get("region", "Spain")
                    flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
                    c_style = THUNDER_CITY_COLORS.get(city, DEFAULT_THUNDER_CARD_COLOR)
                    badge_bg = c_style.get("bg", "#1E293B")
                    badge_border = c_style.get("border", "#334155")
                    badge_text_color = c_style.get("text", "#F8FAFC")
                    badge_str = f"{flag} {city} • {vtype[:8]} ({mems})"
                else:
                    badge_bg = "#1E293B"
                    badge_border = "#334155"
                    badge_text_color = COLOR_TEXT_MUTED
                    badge_str = "⚪ Not Set"

                cfg_frame = ctk.CTkFrame(card, fg_color=badge_bg, corner_radius=5, border_width=1, border_color=badge_border)
                cfg_frame.pack(fill="x", padx=6, pady=(1, 2))
                cfg_lbl = ctk.CTkLabel(
                    cfg_frame,
                    text=badge_str,
                    font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                    text_color=badge_text_color
                )
                cfg_lbl.pack(fill="x", padx=4, pady=1)

                # Online indicator
                cell_idx = r * self.current_cols + c
                is_online = (cell_idx < client_count)
                status_color = COLOR_SUCCESS if is_online else COLOR_TEXT_MUTED
                status_text = "● Connected" if is_online else "○ Offline"

                stat_lbl = ctk.CTkLabel(
                    card,
                    text=status_text,
                    font=ctk.CTkFont(size=9),
                    text_color=status_color,
                    anchor="w"
                )
                stat_lbl.pack(fill="x", padx=6, pady=(0, 4))

                # Click handlers: Single click toggles selection & updates inspector; Double-click directly loads into editor!
                def _make_click_handler(k=cell_key):
                    return lambda event=None: self._on_thunder_cell_clicked(k)

                def _make_double_click_handler(k=cell_key):
                    return lambda event=None: self._load_cell_config_directly(k)

                for widget in (card, top_bar, pos_lbl, check_lbl, p_lbl, cfg_frame, cfg_lbl, stat_lbl):
                    widget.bind("<Button-1>", _make_click_handler(cell_key))
                    widget.bind("<Double-Button-1>", _make_double_click_handler(cell_key))

                self.thunder_cell_cards[cell_key] = {
                    "card": card,
                    "check_lbl": check_lbl,
                    "pos_lbl": pos_lbl,
                    "cfg_frame": cfg_frame,
                    "cfg_lbl": cfg_lbl,
                    "is_selected": is_selected
                }

        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _load_cell_config_directly(self, cell: Tuple[int, int]):
        """Directly targets a single cell and loads its configuration into the editor immediately on double-click."""
        self.thunder_selected_cells = {cell}
        self.thunder_inspected_cell = cell
        for cl in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cl)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()
        self._load_inspected_thunder_config()

    def _on_thunder_cell_clicked(self, cell: Tuple[int, int]):
        """Triggered when a user clicks a cell card in the grid."""
        self._toggle_thunder_cell(cell)
        if cell in self.thunder_selected_cells:
            self.thunder_inspected_cell = cell
        elif self.thunder_selected_cells:
            self.thunder_inspected_cell = sorted(list(self.thunder_selected_cells))[0]
        else:
            self.thunder_inspected_cell = cell
        self._update_thunder_inspector_ui()

    def _toggle_thunder_cell(self, cell: Tuple[int, int]):
        if cell in self.thunder_selected_cells:
            self.thunder_selected_cells.remove(cell)
        else:
            self.thunder_selected_cells.add(cell)

        self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()

    def _update_thunder_cell_visual(self, cell: Tuple[int, int]):
        data = self.thunder_cell_cards.get(cell)
        if not data:
            return
        is_selected = cell in self.thunder_selected_cells
        data["is_selected"] = is_selected
        data["card"].configure(
            fg_color="#14283b" if is_selected else COLOR_SIDEBAR_BG,
            border_width=2 if is_selected else 1,
            border_color="#00D2FF" if is_selected else COLOR_BORDER
        )
        data["check_lbl"].configure(
            text="✓ TARGETED" if is_selected else "○",
            text_color="#10B981" if is_selected else COLOR_TEXT_MUTED
        )
        data["pos_lbl"].configure(
            text_color="#00D2FF" if is_selected else COLOR_TEXT_MUTED
        )

    def _update_thunder_inspector_ui(self):
        """Updates the live inspector bar above the grid with details of inspected Chrome."""
        if not hasattr(self, "lbl_thunder_inspector"):
            return

        target_cell = self.thunder_inspected_cell
        if (target_cell is None or target_cell not in self.thunder_selected_cells) and self.thunder_selected_cells:
            target_cell = sorted(list(self.thunder_selected_cells))[0]
            self.thunder_inspected_cell = target_cell

        # Check if all selected cells share identical configuration
        if len(self.thunder_selected_cells) > 1:
            sel_cfgs = [self.thunder_cell_configs.get(f"{r},{c}") for r, c in self.thunder_selected_cells]
            all_valid = all(c is not None for c in sel_cfgs)
            if all_valid and all(
                c.get("region") == sel_cfgs[0].get("region") and
                c.get("vtData") == sel_cfgs[0].get("vtData")
                for c in sel_cfgs
            ):
                cfg = sel_cfgs[0]
                vt = cfg.get("vtData", {})
                reg = cfg.get("region", "Spain")
                flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
                city = vt.get("city", "N/A")
                cat = vt.get("category", "Normal")
                vtype = vt.get("type", "N/A")
                mems = vt.get("members", 1)
                text = f"🔎 Selected ({len(self.thunder_selected_cells)} Chromes) ➔ {flag} {city} • {cat} • {vtype} • {mems} Mem"
                self.lbl_thunder_inspector.configure(text=text, text_color="#38BDF8")
                return

        if target_cell:
            r, c = target_cell
            prof = self.grid_assignments.get((r, c))
            p_name = prof.display_name if prof else f"Chrome {r*self.current_cols+c+1}"
            cfg = self.thunder_cell_configs.get(f"{r},{c}")
            if cfg:
                vt = cfg.get("vtData", {})
                reg = cfg.get("region", "Spain")
                flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
                city = vt.get("city", "N/A")
                cat = vt.get("category", "Normal")
                vtype = vt.get("type", "N/A")
                mems = vt.get("members", 1)
                extra = f" (+{len(self.thunder_selected_cells)-1} more)" if len(self.thunder_selected_cells) > 1 else ""
                text = f"🔎 [R{r+1}:C{c+1}] {p_name} ➔ {flag} {city} • {cat} • {vtype} • {mems} Mem{extra}"
            else:
                text = f"🔎 [R{r+1}:C{c+1}] {p_name} ➔ ⚪ Default / Not Configured"
            self.lbl_thunder_inspector.configure(text=text, text_color=COLOR_TEXT_PRIMARY)
        else:
            sel_count = len(self.thunder_selected_cells)
            if sel_count > 0:
                text = f"🔎 {sel_count} Chromes selected. Click any tile or 'Load into Editor'."
            else:
                text = "🔍 Click or double-click any Chrome tile to inspect or load its configuration"
            self.lbl_thunder_inspector.configure(text=text, text_color=COLOR_TEXT_SECONDARY)

    def _load_inspected_thunder_config(self):
        """Loads the configuration of the inspected Chrome tile into the left editor controls."""
        target_cell = self.thunder_inspected_cell
        if (target_cell is None or target_cell not in self.thunder_selected_cells) and self.thunder_selected_cells:
            target_cell = sorted(list(self.thunder_selected_cells))[0]
            self.thunder_inspected_cell = target_cell
        elif target_cell is None and not self.thunder_selected_cells:
            self.lbl_thunder_status.configure(text="⚠️ Please click or select a Chrome tile first to load its configuration.")
            return

        r, c = target_cell
        cfg = self.thunder_cell_configs.get(f"{r},{c}")
        if not cfg:
            self.lbl_thunder_status.configure(text=f"⚠️ Tile [R{r+1}:C{c+1}] has no custom configuration saved yet.")
            return

        self._apply_thunder_dict_to_vars(cfg)
        self._switch_thunder_subtab("advanced")
        city = cfg.get("vtData", {}).get("city", "")
        vtype = cfg.get("vtData", {}).get("type", "")
        reg = cfg.get("region", "Spain")
        flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
        mems = cfg.get("vtData", {}).get("members", 1)
        msg = f"📥 Loaded config from [R{r+1}:C{c+1}] ({flag} {city} • {vtype} • {mems} Mem) into editor!"
        self.lbl_thunder_status.configure(text=msg)
        self._update_thunder_inspector_ui()

    def _show_thunder_groups_overview(self):
        """Displays a summary modal of all Chromes grouped by their Thunder configuration."""
        top = ctk.CTkToplevel(self)
        top.title("📊 Thunder Configuration Groups Overview")
        top.geometry("700x520")
        top.configure(fg_color=COLOR_BG_DARK)
        top.transient(self)
        top.grab_set()

        head = ctk.CTkFrame(top, fg_color=COLOR_CARD_BG, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        head.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            head,
            text="📊 Configuration Groups & Chromes Breakdown",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#F59E0B"
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            head,
            text="See which Chromes share identical options. Click 'Target & Load' to immediately select those Chromes on the grid and populate the editor.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(anchor="w", padx=16, pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(top, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Group cells by their config signature
        groups: Dict[str, Dict[str, Any]] = {}
        unassigned_cells = []

        for r in range(self.current_rows):
            for c in range(self.current_cols):
                k = f"{r},{c}"
                cfg = self.thunder_cell_configs.get(k)
                if not cfg:
                    unassigned_cells.append((r, c))
                    continue

                reg = cfg.get("region", "Spain")
                vt = cfg.get("vtData", {})
                city = vt.get("city", "Casablanca")
                vtype = vt.get("type", "Schengen Visa")
                cat = vt.get("category", "Normal")
                mems = vt.get("members", 1)
                sig = f"{reg}|{city}|{vtype}|{cat}|{mems}"

                if sig not in groups:
                    groups[sig] = {
                        "region": reg,
                        "city": city,
                        "vtype": vtype,
                        "category": cat,
                        "members": mems,
                        "config": cfg,
                        "cells": []
                    }
                groups[sig]["cells"].append((r, c))

        if not groups and not unassigned_cells:
            ctk.CTkLabel(scroll, text="No Chromes found in grid.", text_color=COLOR_TEXT_MUTED).pack(pady=40)
            return

        # Render each group
        for sig, grp in groups.items():
            reg = grp["region"]
            flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
            city = grp["city"]
            vtype = grp["vtype"]
            cat = grp["category"]
            mems = grp["members"]
            cells = grp["cells"]
            c_style = THUNDER_CITY_COLORS.get(city, DEFAULT_THUNDER_CARD_COLOR)

            g_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD_BG, corner_radius=8, border_width=1, border_color=c_style.get("border", COLOR_BORDER))
            g_card.pack(fill="x", pady=6)

            g_inner = ctk.CTkFrame(g_card, fg_color="transparent")
            g_inner.pack(fill="x", padx=12, pady=10)

            # Left description
            g_info = ctk.CTkFrame(g_inner, fg_color="transparent")
            g_info.pack(side="left", fill="both", expand=True)

            title_txt = f"{flag} {city} • {cat} • {vtype} ({mems} Mem)"
            ctk.CTkLabel(
                g_info,
                text=title_txt,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=c_style.get("text", COLOR_TEXT_PRIMARY)
            ).pack(anchor="w")

            # Determine rows summary
            row_set = sorted(list({rw + 1 for rw, _ in cells}))
            rows_str = ", ".join(f"Row {rw}" for rw in row_set)
            cell_coords = " ".join(f"[R{rw+1}:C{cl+1}]" for rw, cl in cells[:16])
            if len(cells) > 16:
                cell_coords += f" ... (+{len(cells)-16} more)"

            ctk.CTkLabel(
                g_info,
                text=f"{len(cells)} Chrome(s) in {rows_str}  ➔  {cell_coords}",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLOR_TEXT_SECONDARY
            ).pack(anchor="w", pady=(3, 0))

            # Action button
            def _make_target_cmd(target_cells=cells, target_cfg=grp["config"], title=title_txt):
                def _cmd():
                    self.thunder_selected_cells = set(target_cells)
                    for cl in self.thunder_cell_cards:
                        self._update_thunder_cell_visual(cl)
                    self._update_thunder_target_count()
                    self._apply_thunder_dict_to_vars(target_cfg)
                    self._update_thunder_inspector_ui()
                    self.lbl_thunder_status.configure(
                        text=f"⚡ Targeted {len(target_cells)} Chromes for '{title}' and loaded settings into editor!"
                    )
                    top.destroy()
                return _cmd

            ctk.CTkButton(
                g_inner,
                text="⚡ Target & Load",
                width=120,
                height=32,
                corner_radius=6,
                fg_color="#059669",
                hover_color="#047857",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=_make_target_cmd()
            ).pack(side="right", padx=6)

        # Render unassigned group if any
        if unassigned_cells:
            u_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD_BG, corner_radius=8, border_width=1, border_color="#334155")
            u_card.pack(fill="x", pady=6)

            u_inner = ctk.CTkFrame(u_card, fg_color="transparent")
            u_inner.pack(fill="x", padx=12, pady=10)

            u_info = ctk.CTkFrame(u_inner, fg_color="transparent")
            u_info.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                u_info,
                text="⚪ Default / Unassigned Chromes",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLOR_TEXT_MUTED
            ).pack(anchor="w")

            cell_coords = " ".join(f"[R{rw+1}:C{cl+1}]" for rw, cl in unassigned_cells[:16])
            if len(unassigned_cells) > 16:
                cell_coords += f" ... (+{len(unassigned_cells)-16} more)"

            ctk.CTkLabel(
                u_info,
                text=f"{len(unassigned_cells)} Chrome(s)  ➔  {cell_coords}",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=COLOR_TEXT_SECONDARY
            ).pack(anchor="w", pady=(3, 0))

            def _target_unassigned(t_cells=unassigned_cells):
                self.thunder_selected_cells = set(t_cells)
                for cl in self.thunder_cell_cards:
                    self._update_thunder_cell_visual(cl)
                self._update_thunder_target_count()
                self._update_thunder_inspector_ui()
                self.lbl_thunder_status.configure(text=f"⚡ Targeted {len(t_cells)} unassigned Chromes on grid.")
                top.destroy()

            ctk.CTkButton(
                u_inner,
                text="⚡ Target These",
                width=120,
                height=32,
                corner_radius=6,
                fg_color="#334155",
                hover_color="#475569",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=_target_unassigned
            ).pack(side="right", padx=6)

    def _update_thunder_target_count(self):
        total = self.current_rows * self.current_cols
        sel = len(self.thunder_selected_cells)
        connected = len(self.refresh_server.clients) + len(self.refresh_server.http_clients) if hasattr(self, "refresh_server") else 0
        if hasattr(self, "lbl_thunder_target_count"):
            self.lbl_thunder_target_count.configure(
                text=f"Targeted: {sel} / {total} Chromes ({connected} Online)"
            )

    def _thunder_select_all(self):
        self.thunder_selected_cells = {(r, c) for r in range(self.current_rows) for c in range(self.current_cols)}
        self.thunder_inspected_cell = (0, 0)
        for cell in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _thunder_deselect_all(self):
        self.thunder_selected_cells.clear()
        self.thunder_inspected_cell = None
        for cell in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _thunder_invert_selection(self):
        all_cells = {(r, c) for r in range(self.current_rows) for c in range(self.current_cols)}
        self.thunder_selected_cells = all_cells - self.thunder_selected_cells
        self.thunder_inspected_cell = sorted(list(self.thunder_selected_cells))[0] if self.thunder_selected_cells else None
        for cell in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _thunder_select_row(self, row_idx: int):
        row_cells = {(row_idx, c) for c in range(self.current_cols)}
        # Toggle: if all cells in this row are already selected, deselect them; otherwise select them all
        if row_cells.issubset(self.thunder_selected_cells):
            self.thunder_selected_cells -= row_cells
            if self.thunder_selected_cells:
                self.thunder_inspected_cell = sorted(list(self.thunder_selected_cells))[0]
            else:
                self.thunder_inspected_cell = None
        else:
            self.thunder_selected_cells |= row_cells
            self.thunder_inspected_cell = (row_idx, 0)
        for cell in row_cells:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

        # Display informative status about row configuration
        row_cfgs = [self.thunder_cell_configs.get(f"{row_idx},{c}") for c in range(self.current_cols)]
        valid_cfgs = [c for c in row_cfgs if c]
        if valid_cfgs:
            cities = list(dict.fromkeys([c.get("vtData", {}).get("city") for c in valid_cfgs]))
            vtypes = list(dict.fromkeys([c.get("vtData", {}).get("type") for c in valid_cfgs]))
            reg = valid_cfgs[0].get("region", "Spain")
            flag = "🇪🇸" if reg == "Spain" else "🇵🇹"
            if len(cities) == 1 and len(valid_cfgs) == self.current_cols:
                self.lbl_thunder_status.configure(
                    text=f"Selected Row {row_idx+1}: All {self.current_cols} Chromes configured as {flag} {cities[0]} • {vtypes[0]}. Click 'Load into Editor' to load."
                )
            else:
                self.lbl_thunder_status.configure(
                    text=f"Selected Row {row_idx+1}: Configured cities: {', '.join(cities)}."
                )

    def _thunder_select_top_half(self):
        half = max(1, self.current_rows // 2)
        top_cells = {(r, c) for r in range(half) for c in range(self.current_cols)}
        self.thunder_selected_cells = set(top_cells)
        self.thunder_inspected_cell = (0, 0)
        for cell in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _thunder_select_bottom_half(self):
        half = max(1, self.current_rows // 2)
        bot_cells = {(r, c) for r in range(half, self.current_rows) for c in range(self.current_cols)}
        self.thunder_selected_cells = set(bot_cells)
        self.thunder_inspected_cell = (half, 0)
        for cell in self.thunder_cell_cards:
            self._update_thunder_cell_visual(cell)
        self._update_thunder_target_count()
        self._update_thunder_inspector_ui()

    def _apply_thunder_unified_settings(self):
        """Applies configured settings in bulk to all selected Chromes and persists assignments."""
        try:
            total_cells = self.current_rows * self.current_cols
            sel_count = len(self.thunder_selected_cells)

            if sel_count == 0:
                self.lbl_thunder_status.configure(text="⚠️ No Chromes selected. Click tiles or 'Select All' first.")
                return

            settings = self._get_current_thunder_config_dict()

            # Record and persist per-cell settings for all selected cells immediately
            for (r, c) in self.thunder_selected_cells:
                self.thunder_cell_configs[f"{r},{c}"] = dict(settings)
            self._save_thunder_cell_configs()
            self._render_thunder_chrome_grid()
            self._update_thunder_inspector_ui()

            # Temporary button animation
            self.btn_apply_thunder.configure(text="⏳ DISPATCHING UNIFIED CONFIGURATION...", fg_color=COLOR_WARNING)
            self.thunder_progress.set(0.3)

            now_str = datetime.now().strftime("%H:%M:%S")

            # Correlate selected cells with connected tabs
            connected_tabs = self.refresh_server.get_clients_snapshot() if hasattr(self, "refresh_server") else []
            target_tab_ids = None

            if not connected_tabs:
                # Still store in broadcast queue so tabs pick it up immediately when opened/polled
                self.refresh_server.broadcast_thunder_config(settings, None)
                self.thunder_progress.set(1.0)
                self.btn_apply_thunder.configure(
                    text="⚡ APPLY UNIFIED SETTINGS TO SELECTED CHROMES",
                    fg_color="#059669"
                )
                warn_msg = f"⚡ [{now_str}] Settings saved & queued for {sel_count} selected Chrome(s). (0 Chrome windows currently active)."
                self.lbl_thunder_status.configure(text=warn_msg)
                if hasattr(self, "lbl_status"):
                    self.lbl_status.configure(text=warn_msg)
                return

            if sel_count < total_cells:
                matched_tab_ids = []
                target_indices = {r * self.current_cols + c for (r, c) in self.thunder_selected_cells}
                
                mon = self.monitors[0] if getattr(self, "monitors", None) else None
                mon_w = getattr(mon, "work_width", 1920) if mon else 1920
                mon_h = getattr(mon, "work_height", 1080) if mon else 1080
                cell_w = max(1, mon_w // self.current_cols)
                cell_h = max(1, mon_h // self.current_rows)

                for idx, tab in enumerate(connected_tabs):
                    tx = tab.get("screen_x")
                    ty = tab.get("screen_y")
                    matched = False
                    if tx is not None and ty is not None and (int(tx) > 0 or int(ty) > 0):
                        calc_col = min(self.current_cols - 1, max(0, int(tx) // cell_w))
                        calc_row = min(self.current_rows - 1, max(0, int(ty) // cell_h))
                        if (calc_row, calc_col) in self.thunder_selected_cells:
                            matched_tab_ids.append(tab.get("tab_id"))
                            matched = True
                    if not matched and idx in target_indices:
                        matched_tab_ids.append(tab.get("tab_id"))

                if matched_tab_ids:
                    target_tab_ids = matched_tab_ids

            # Broadcast via server
            cmd_id = self.refresh_server.broadcast_thunder_config(settings, target_tab_ids)

            actual_dispatched = len(target_tab_ids) if target_tab_ids else len(connected_tabs)
            target_desc = f"{actual_dispatched} of {len(connected_tabs)} connected Chrome(s)"
            status_msg = f"⚡ [{now_str}] ThunderBolt configuration dispatched to {target_desc} & saved! (Verifying ACKs...)"

            self.after(400, lambda: self.thunder_progress.set(0.7))
            self.after(700, lambda: self.thunder_progress.set(1.0))
            self.after(700, lambda: self.btn_apply_thunder.configure(
                text="⚡ APPLY UNIFIED SETTINGS TO SELECTED CHROMES",
                fg_color="#059669"
            ))
            self.lbl_thunder_status.configure(text=status_msg)
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(text=status_msg)

        except Exception as e:
            self.thunder_progress.set(0)
            self.btn_apply_thunder.configure(
                text="⚡ APPLY UNIFIED SETTINGS TO SELECTED CHROMES",
                fg_color="#059669"
            )
            self.lbl_thunder_status.configure(text=f"❌ Error dispatching Thunder settings: {e}")

    # -------------------------------------------------------------------
    # Presets Manager
    # -------------------------------------------------------------------
    def _on_thunder_preset_selected(self, choice: str):
        self.thunder_active_preset_name = choice
        cfg = self.thunder_presets.get(choice)
        if cfg:
            self._apply_thunder_dict_to_vars(cfg)
            self.lbl_thunder_status.configure(text=f"Loaded preset: '{choice}'")

    def _save_current_thunder_preset(self):
        dialog = ctk.CTkInputDialog(
            text="Enter preset name (e.g. 'Casa Normal' or 'Tangier Premium'):",
            title="Save Thunder Preset"
        )
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()
        cfg = self._get_current_thunder_config_dict()
        self.thunder_presets[name] = cfg
        self._save_thunder_presets(self.thunder_presets)
        self.thunder_active_preset_name = name
        self.combo_thunder_preset.configure(values=list(self.thunder_presets.keys()))
        self.combo_thunder_preset.set(name)
        self.lbl_thunder_status.configure(text=f"Saved preset: '{name}' successfully!")

    def _delete_current_thunder_preset(self):
        name = self.combo_thunder_preset.get()
        if name == "Default":
            self.lbl_thunder_status.configure(text="⚠️ Cannot delete the 'Default' preset.")
            return
        if name in self.thunder_presets:
            del self.thunder_presets[name]
            self._save_thunder_presets(self.thunder_presets)
            names = list(self.thunder_presets.keys()) or ["Default"]
            self.thunder_active_preset_name = names[0]
            self.combo_thunder_preset.configure(values=names)
            self.combo_thunder_preset.set(self.thunder_active_preset_name)
            self._on_thunder_preset_selected(self.thunder_active_preset_name)
            self.lbl_thunder_status.configure(text=f"Deleted preset: '{name}'")

    # -----------------------------------------------------------------------
    # Refresh Tab Helpers & Server Coordination
    # -----------------------------------------------------------------------

    def _get_stagger_ms(self) -> int:
        val = self.opt_stagger.get() if hasattr(self, "opt_stagger") else "0"
        match = re.search(r"(\d+)ms", val)
        return int(match.group(1)) if match else 0

    def _trigger_refresh_all(self):
        """Dispatches refresh command to all connected Chrome tabs."""
        xpath = self.entry_xpath.get().strip() if hasattr(self, "entry_xpath") else "/html/body/div[5]/div[1]/button[1]"
        text = self.entry_text.get().strip() if hasattr(self, "entry_text") else "Refresh"
        class_name = self.entry_class.get().strip() if hasattr(self, "entry_class") else "btn btn-primary"
        stagger = self._get_stagger_ms()

        # Temporary button animation feedback
        if hasattr(self, "btn_hero_refresh"):
            self.btn_hero_refresh.configure(text="⏳ SENDING COMMAND...", fg_color=COLOR_WARNING)
            self.after(500, lambda: self.btn_hero_refresh.configure(
                text="⚡ REFRESH ALL CHROME TABS",
                fg_color=COLOR_SUCCESS
            ))
        if hasattr(self, "btn_top_refresh_all"):
            self.btn_top_refresh_all.configure(text="⏳ SENDING...")
            self.after(500, lambda: self.btn_top_refresh_all.configure(text="🔄 REFRESH ALL"))

        client_count = len(self.refresh_server.clients) + len(self.refresh_server.http_clients)
        cmd_id = self.refresh_server.broadcast_refresh(
            xpath=xpath,
            text=text,
            class_name=class_name,
            stagger_ms=stagger
        )

        if client_count == 0:
            self.lbl_status.configure(
                text=f"⚠️ Refresh command queued, but 0 Chrome tabs are connected to server on port {self.refresh_server.port}."
            )
        else:
            self.lbl_status.configure(
                text=f"⚡ Broadcasted Refresh command to {client_count} Chrome tab(s) via Tampermonkey."
            )
        self._update_refresh_ui_stats()

    def _render_connected_tabs_list(self):
        """Renders/updates cards for all connected Chrome tabs without destroying and recreating them."""
        if not hasattr(self, "scroll_connected_tabs"):
            return

        if not hasattr(self, "_tab_cards"):
            self._tab_cards = {}

        clients = self.refresh_server.get_clients_snapshot()
        current_tab_ids = {c["tab_id"] for c in clients}

        # Remove cards for tabs that have disconnected
        for tid in list(self._tab_cards.keys()):
            if tid not in current_tab_ids:
                card_data = self._tab_cards.pop(tid)
                try:
                    card_data["frame"].destroy()
                except Exception:
                    pass

        # If no clients connected, show empty placeholder
        if not clients:
            if not hasattr(self, "_empty_tabs_box") or not self._empty_tabs_box.winfo_exists():
                self._empty_tabs_box = ctk.CTkFrame(self.scroll_connected_tabs, fg_color="transparent")
                self._empty_tabs_box.pack(fill="both", expand=True, pady=30)
                ctk.CTkLabel(
                    self._empty_tabs_box,
                    text="No Chrome Windows Connected",
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    text_color=COLOR_TEXT_PRIMARY
                ).pack()
                ctk.CTkLabel(
                    self._empty_tabs_box,
                    text="1. Click '1-Click Install in Chrome' or 'Copy Tampermonkey Script'.\n2. Open your target pages in Chrome.\n3. Connected tabs will appear here automatically in real time.",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=COLOR_TEXT_MUTED,
                    justify="center"
                ).pack(pady=(6, 0))
            return
        else:
            if hasattr(self, "_empty_tabs_box") and self._empty_tabs_box.winfo_exists():
                try:
                    self._empty_tabs_box.destroy()
                except Exception:
                    pass
                del self._empty_tabs_box

        for client in clients:
            tab_id = client.get("tab_id", "")
            title_text = client.get("title") or "Untitled Tab"
            url_text = client.get("url") or "No URL"
            res = client.get("last_result", "Ready")
            dur_ms = client.get("last_duration_ms", 0)
            strat = client.get("last_strategy", "")
            dot_color = COLOR_SUCCESS if res == "Success" else (COLOR_DANGER if res == "Error" else COLOR_ACCENT)
            stat_str = f"Result: {res}" + (f" ({dur_ms}ms via {strat})" if dur_ms else "")
            display_title = title_text[:38] + ("..." if len(title_text) > 38 else "")
            display_url = f"{url_text[:45]}  •  {stat_str}"

            if tab_id in self._tab_cards:
                # Fast in-place property update only if values actually changed (eliminates CPU spikes for 50+ profiles)
                card_data = self._tab_cards[tab_id]
                new_state = (display_title, display_url, dot_color)
                if card_data.get("_last_state") != new_state:
                    card_data["_last_state"] = new_state
                    try:
                        card_data["dot_lbl"].configure(text_color=dot_color)
                        card_data["title_lbl"].configure(text=display_title)
                        card_data["url_lbl"].configure(text=display_url)
                    except Exception:
                        pass
            else:
                card = ctk.CTkFrame(
                    self.scroll_connected_tabs,
                    fg_color=COLOR_SIDEBAR_BG,
                    corner_radius=8,
                    border_width=1,
                    border_color=COLOR_BORDER
                )
                card.pack(fill="x", pady=2, padx=2)
                card.grid_columnconfigure(1, weight=1)

                dot_lbl = ctk.CTkLabel(card, text="●", text_color=dot_color, font=ctk.CTkFont(size=14))
                dot_lbl.grid(row=0, column=0, rowspan=2, padx=(10, 6))

                title_lbl = ctk.CTkLabel(
                    card,
                    text=display_title,
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=COLOR_TEXT_PRIMARY,
                    anchor="w"
                )
                title_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))

                url_lbl = ctk.CTkLabel(
                    card,
                    text=display_url,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w"
                )
                url_lbl.grid(row=1, column=1, sticky="w", pady=(0, 6))

                btn_single = ctk.CTkButton(
                    card,
                    text="🔄 Refresh",
                    width=76,
                    height=26,
                    corner_radius=6,
                    fg_color=COLOR_CARD_BG,
                    hover_color=COLOR_CARD_HOVER,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda: self._trigger_refresh_all()
                )
                btn_single.grid(row=0, column=2, rowspan=2, padx=10)

                self._tab_cards[tab_id] = {
                    "frame": card,
                    "dot_lbl": dot_lbl,
                    "title_lbl": title_lbl,
                    "url_lbl": url_lbl,
                    "_last_state": (display_title, display_url, dot_color)
                }

    def _schedule_render_connected_tabs(self):
        """Debounces tab list rendering to prevent GUI lag when many profiles connect or ACK."""
        if self.active_workspace_tab != "refresh":
            return
        if getattr(self, "_render_tabs_timer", None) is not None:
            return
        self._render_tabs_timer = self.after(800, self._do_render_connected_tabs)

    def _do_render_connected_tabs(self):
        self._render_tabs_timer = None
        if self.active_workspace_tab == "refresh":
            self._render_connected_tabs_list()

    def _update_refresh_ui_clients(self, count: int, clients: List[Dict[str, Any]]):
        """Thread-safe update of client count and badges."""
        if hasattr(self, "btn_nav_refresh"):
            self.btn_nav_refresh.configure(text=f"🔄 Refresh All Tab ({count})")
        if hasattr(self, "lbl_stat_tabs"):
            self.lbl_stat_tabs.configure(text=str(count))
        if hasattr(self, "lbl_connected_tabs_hdr"):
            self.lbl_connected_tabs_hdr.configure(text=f"Connected Chrome Profiles & Tabs ({count})")

        if self.active_workspace_tab == "refresh":
            self._schedule_render_connected_tabs()

    def _schedule_update_stats(self):
        """Debounces statistics updates to prevent high-frequency UI calls."""
        if getattr(self, "_stats_timer", None) is not None:
            return
        self._stats_timer = self.after(300, self._do_update_stats)

    def _do_update_stats(self):
        self._stats_timer = None
        self._update_refresh_ui_stats()

    def _update_refresh_ui_stats(self):
        """Thread-safe update of execution statistics."""
        stats = self.refresh_server.get_stats()
        if hasattr(self, "lbl_stat_broadcasts"):
            self.lbl_stat_broadcasts.configure(text=str(stats.get("total_broadcasts", 0)))
        if hasattr(self, "lbl_stat_success"):
            self.lbl_stat_success.configure(text=str(stats.get("total_acks_success", 0)))
        if hasattr(self, "lbl_stat_failed"):
            self.lbl_stat_failed.configure(text=str(stats.get("total_acks_failed", 0)))

    def _on_refresh_server_clients_changed(self, count: int, clients: List[Dict[str, Any]]):
        self.after(0, lambda c=count, cl=clients: self._update_refresh_ui_clients(c, cl))

    def _on_refresh_ack_received(self, ack_data: Dict[str, Any]):
        self._schedule_update_stats()
        if self.active_workspace_tab == "refresh":
            self._schedule_render_connected_tabs()
        elif ack_data.get("type") == "thunder_config_ack":
            tid = ack_data.get("tab_id", "")
            succ = ack_data.get("success", False)
            confirmed = ack_data.get("confirmed_by_extension", False)
            sym = "✅" if succ else "⚠️"
            conf_str = " (Verified by Thunder Extension)" if confirmed else ""
            msg = f"{sym} Received confirmation from tab {tid[:8]}: Settings applied!{conf_str}"
            if hasattr(self, "lbl_thunder_status"):
                self.after(0, lambda m=msg: self.lbl_thunder_status.configure(text=m))

    def _on_refresh_server_log(self, msg: str, level: str):
        self.after(0, lambda m=msg, l=level: self._append_refresh_log(m, l))

    def _append_refresh_log(self, msg: str, level: str):
        if not hasattr(self, "txt_refresh_log"):
            return
        if not hasattr(self, "_pending_log_lines"):
            self._pending_log_lines = []
        self._pending_log_lines.append(msg)
        if getattr(self, "_flush_log_timer", None) is None:
            self._flush_log_timer = self.after(500, self._flush_log_batch)

    def _flush_log_batch(self):
        self._flush_log_timer = None
        lines = getattr(self, "_pending_log_lines", [])
        self._pending_log_lines = []
        if not lines or not hasattr(self, "txt_refresh_log"):
            return
        try:
            self.txt_refresh_log.configure(state="normal")
            self.txt_refresh_log.insert("end", "\n".join(lines) + "\n")
            self.txt_refresh_log.see("end")
            # Cap log buffer to 200 lines to prevent memory bloat under heavy load
            line_count = int(self.txt_refresh_log.index("end-1c").split(".")[0])
            if line_count > 200:
                self.txt_refresh_log.delete("1.0", f"{line_count - 120}.0")
            self.txt_refresh_log.configure(state="disabled")
        except Exception:
            pass

    def _clear_refresh_log(self):
        if hasattr(self, "txt_refresh_log"):
            self.txt_refresh_log.configure(state="normal")
            self.txt_refresh_log.delete("1.0", "end")
            self.txt_refresh_log.configure(state="disabled")

    def _on_refresh_server_status_changed(self, is_running: bool, info: str):
        self.after(0, lambda r=is_running, i=info: self._update_server_status_indicator(r, i))

    def _update_server_status_indicator(self, is_running: bool, info: str):
        status_text = f"🟢 Server: ws://127.0.0.1:{self.refresh_server.port}" if is_running else "🔴 Server: Stopped"
        status_color = COLOR_SUCCESS if is_running else COLOR_DANGER

        if hasattr(self, "lbl_nav_server_status"):
            self.lbl_nav_server_status.configure(text=status_text, text_color=status_color)
        if hasattr(self, "lbl_server_pill"):
            self.lbl_server_pill.configure(text=f"{status_text} ({info})", text_color=status_color)
        if hasattr(self, "btn_toggle_server"):
            self.btn_toggle_server.configure(
                text="Stop Server" if is_running else "Start Server",
                hover_color=COLOR_DANGER_HOVER if is_running else COLOR_SUCCESS_HOVER
            )

    def _toggle_server_state(self):
        if self.refresh_server.running:
            self.refresh_server.stop()
        else:
            try:
                p = int(self.entry_server_port.get().strip())
                self.refresh_server.port = p
            except Exception:
                pass
            self.refresh_server.start()

    def _restart_refresh_server(self):
        try:
            p = int(self.entry_server_port.get().strip())
            self.refresh_server.restart(new_port=p)
        except Exception:
            self.refresh_server.restart()

    def _ping_all_tabs(self):
        """Sends ping to all tabs to update latency and health."""
        if hasattr(self, "refresh_server"):
            if self.refresh_server.loop and self.refresh_server.loop.is_running():
                import asyncio
                payload = json.dumps({"action": "ping", "timestamp": time.time()})
                async def _send():
                    for ws in list(self.refresh_server.clients.keys()):
                        try:
                            await ws.send(payload)
                        except Exception:
                            pass
                asyncio.run_coroutine_threadsafe(_send(), self.refresh_server.loop)
                self.lbl_status.configure(text="📡 Ping dispatched to all connected Chrome tabs.")

    def _copy_userscript_to_clipboard(self):
        script_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_refresh_listener.user.js")
        try:
            with open(script_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.clipboard_clear()
            self.clipboard_append(content)
            self.update()
            if hasattr(self, "btn_hero_copy_script"):
                self.btn_hero_copy_script.configure(text="✅ Copied to Clipboard!")
                self.after(1500, lambda: self.btn_hero_copy_script.configure(text="📋 Copy Tampermonkey Script"))
            self.lbl_status.configure(text="✅ Tampermonkey userscript copied to clipboard! Paste it into Tampermonkey.")
        except Exception as e:
            messagebox.showerror("Error Copying Script", f"Could not read script file:\n{e}")

    def _open_userscript_install_page(self):
        port = self.refresh_server.port
        url = f"http://127.0.0.1:{port}/userscript.user.js"
        try:
            webbrowser.open(url)
            self.lbl_status.configure(text=f"Opened 1-click install URL in browser: {url}")
        except Exception as e:
            messagebox.showerror("Error Opening Browser", f"Could not launch browser:\n{e}")

    def _open_install_in_profiles_modal(self):
        """Opens dialog to select specific Chrome profiles and auto-launch them to the Tampermonkey install URL."""
        if not self.refresh_server.running:
            self.refresh_server.start()

        assigned_profiles = [p for p in self.grid_assignments.values() if p]
        InstallScriptProfilesModal(
            parent=self,
            profiles=self.profiles,
            grid_assigned_profiles=assigned_profiles,
            chrome_exe=self.chrome_executable,
            server_port=self.refresh_server.port,
            on_log=self.refresh_server.log
        )

    def _live_update_userscript_in_open_tabs(self):
        """Opens the Tampermonkey installer URL as a new tab in the already-open window of each profile without creating new windows."""
        if not self.refresh_server.running:
            self.refresh_server.start()

        port = self.refresh_server.port
        url = f"http://127.0.0.1:{port}/userscript.user.js"

        # Determine target profiles: grid assigned profiles first, otherwise all profiles
        assigned_profiles = [p for p in self.grid_assignments.values() if p is not None]
        source_profiles = assigned_profiles if assigned_profiles else self.profiles
        seen_keys = set()
        targets: List[ChromeProfile] = []
        for p in source_profiles:
            if p.key not in seen_keys:
                seen_keys.add(p.key)
                targets.append(p)

        if not targets:
            messagebox.showwarning(
                "No Profiles Found",
                "No Chrome profiles are currently assigned to the grid or available.",
                parent=self
            )
            return

        chrome_exe = self.chrome_executable
        if not chrome_exe or not os.path.exists(chrome_exe):
            for cand in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                shutil.which("chrome")
            ]:
                if cand and os.path.exists(cand):
                    chrome_exe = cand
                    self.chrome_executable = cand
                    break

        if not chrome_exe or not os.path.exists(chrome_exe):
            messagebox.showerror(
                "Error",
                "Chrome executable not found. Please verify your Chrome path in Settings (⚙️).",
                parent=self
            )
            return

        total = len(targets)
        msg_start = f"⚡ Live Updating Tampermonkey: Opening update tab across {total} existing profile window(s)..."
        self.refresh_server.log(msg_start, "INFO")
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(text=msg_start)

        # Also broadcast in-page in case any tabs already support remote open_tab
        try:
            self.refresh_server.broadcast_open_tab(url)
        except Exception:
            pass

        # Launch worker to route URL to each profile's already-open window via Chrome CLI (NO --new-window)
        def _launch_worker():
            success_count = 0
            for idx, p in enumerate(targets, start=1):
                # Omission of --new-window tells Chrome IPC to open a new tab in the profile's EXISTING window!
                cmd = [chrome_exe, f"--profile-directory={p.key}", url]
                try:
                    subprocess.Popen(cmd)
                    success_count += 1
                    self.refresh_server.log(
                        f"Opened installer tab in existing window: {p.display_name} [{p.key}] ({idx}/{total})",
                        "INFO"
                    )
                except Exception as e:
                    self.refresh_server.log(f"Failed to open tab for profile '{p.key}': {e}", "ERROR")

                if idx < total:
                    time.sleep(0.12)

            msg_done = f"✅ Opened Tampermonkey update tab in {success_count}/{total} existing window(s)! Grid layout 100% intact."
            self.refresh_server.log(msg_done, "SUCCESS")
            if hasattr(self, "lbl_status"):
                self.after(0, lambda: self.lbl_status.configure(text=f"✅ Opened update tab in {success_count}/{total} existing window(s)! Click 'Update' in Tampermonkey."))

        threading.Thread(target=_launch_worker, daemon=True).start()

    def _on_auto_refresh_changed(self, choice: str):
        if self.auto_refresh_job is not None:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

        interval_map = {
            "15 seconds": 15,
            "30 seconds": 30,
            "1 minute": 60,
            "2 minutes": 120,
            "5 minutes": 300,
        }
        sec = interval_map.get(choice)
        if sec:
            self.lbl_status.configure(text=f"⏱️ Auto-Refresh enabled: every {choice}.")
            self.auto_refresh_job = self.after(sec * 1000, lambda: self._auto_refresh_tick(sec))
        else:
            self.lbl_status.configure(text="Auto-Refresh disabled.")

    def _auto_refresh_tick(self, interval_seconds: int):
        self._trigger_refresh_all()
        # Schedule next tick if still active
        cur_choice = self.opt_auto_refresh.get() if hasattr(self, "opt_auto_refresh") else "Off"
        if cur_choice != "Off":
            self.auto_refresh_job = self.after(interval_seconds * 1000, lambda: self._auto_refresh_tick(interval_seconds))

    def _on_app_close(self):
        """Graceful teardown when application window is closed."""
        try:
            if self.auto_refresh_job:
                self.after_cancel(self.auto_refresh_job)
        except Exception:
            pass

        try:
            if hasattr(self, "refresh_server"):
                self.refresh_server.stop()
        except Exception:
            pass

        self.destroy()

    # -----------------------------------------------------------------------
    # Bottom Status Bar
    # -----------------------------------------------------------------------
    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, fg_color=COLOR_STATUSBAR_BG, corner_radius=0, height=36)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(
            self.status_bar,
            text="Initializing Chrome Grid Launcher...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=16, pady=6)

        self.progress_bar = ctk.CTkProgressBar(
            self.status_bar,
            width=220,
            height=8,
            corner_radius=4,
            progress_color=COLOR_SUCCESS,
            fg_color=COLOR_CARD_BG
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=6)
        self.progress_bar.grid_remove()

    # -----------------------------------------------------------------------
    # Environment & Profile Detection
    # -----------------------------------------------------------------------
    def _detect_environment(self):
        self.lbl_status.configure(text="Scanning Chrome profiles and displays...")

        override_path = self.settings.get("chrome_path_override", "")
        if override_path and os.path.exists(override_path):
            self.chrome_executable = override_path
        else:
            self.chrome_executable = ChromeProfileManager.find_chrome_executable()

        self.profiles = ChromeProfileManager.load_profiles()
        GroupManager.apply_groups_to_profiles(self.profiles, self.custom_groups)
        self.lbl_profile_count.configure(text=f"{len(self.profiles)} detected")

        self.monitors = WindowManager.get_monitors()
        mon_names = [m.display_label for m in self.monitors]
        self.opt_top_monitor.configure(values=mon_names)

        self._render_group_tabs()
        self._filter_and_render_sidebar()
        self._update_auto_populate_button()

        if self.chrome_executable:
            self.lbl_status.configure(text=f"Ready • {len(self.profiles)} profiles detected • Chrome: {os.path.basename(self.chrome_executable)}")
        else:
            self.lbl_status.configure(text="⚠️ Chrome executable not found! Click Settings (⚙️) to locate chrome.exe.")

    def _filter_and_render_sidebar(self):
        query = self.search_entry.get().strip().lower()
        group_profiles = GroupManager.filter_profiles(self.profiles, self.active_group_id)

        if query:
            filtered = [
                p for p in group_profiles
                if query in p.name.lower() or query in p.key.lower() or query in p.email.lower() or query in p.gaia_name.lower()
            ]
        else:
            filtered = group_profiles

        self._render_sidebar_profiles(filtered)

    def _render_sidebar_profiles(self, profile_list: List[ChromeProfile]):
        for child in self.sidebar_scroll.winfo_children():
            child.destroy()

        if not profile_list:
            lbl_none = ctk.CTkLabel(
                self.sidebar_scroll,
                text="No Chrome profiles found in\nthis view.",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_none.pack(pady=20)
            return

        prot_key = self.settings.get("protected_profile_key", "Default")

        for p in profile_list:
            card = ProfileSidebarCard(
                self.sidebar_scroll,
                profile=p,
                on_select=self._on_profile_selected_in_sidebar,
                on_quick_add=self._on_quick_add_profile,
                on_drag_drop=self._on_profile_drag_dropped,
                on_toggle_protect=self._toggle_protected_profile,
                on_assign_group=self._open_assign_group_dialog,
                is_protected=(p.key == prot_key)
            )
            card.pack(fill="x", pady=3)

    def _toggle_protected_profile(self, profile: ChromeProfile):
        cur_prot = self.settings.get("protected_profile_key", "Default")
        if cur_prot == profile.key:
            self.settings["protected_profile_key"] = ""
            self.lbl_status.configure(text=f"Removed protected status from '{profile.display_name}'.")
        else:
            self.settings["protected_profile_key"] = profile.key
            self.lbl_status.configure(text=f"🛡️ Set '{profile.display_name}' as Protected Personal Profile (excluded from Auto-Populate & Closure).")
        ConfigManager.save_settings(self.settings)
        self._filter_and_render_sidebar()

    def _on_sidebar_search(self, event=None):
        self._filter_and_render_sidebar()

    def _on_profile_selected_in_sidebar(self, profile: ChromeProfile):
        if self.selected_profile_for_assign == profile:
            self.selected_profile_for_assign = None
            self.lbl_status.configure(text="Profile unselected.")
        else:
            self.selected_profile_for_assign = profile
            self.lbl_status.configure(text=f"Selected '{profile.display_name}'. Click any grid cell to place it.")

        for child in self.sidebar_scroll.winfo_children():
            if isinstance(child, ProfileSidebarCard):
                child.set_selected(child.profile == self.selected_profile_for_assign)

    def _on_quick_add_profile(self, profile: ChromeProfile):
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                if (r, c) not in self.grid_assignments or self.grid_assignments[(r, c)] is None:
                    self._assign_cell(r, c, profile)
                    self.lbl_status.configure(text=f"Assigned '{profile.display_name}' to Cell [R{r+1}, C{c+1}].")
                    return
        self.lbl_status.configure(text="All grid cells are currently occupied.")

    def _on_profile_drag_dropped(self, row: int, col: int, profile: ChromeProfile):
        self._assign_cell(row, col, profile)
        self.lbl_status.configure(text=f"Dropped '{profile.display_name}' into Cell [R{row+1}, C{col+1}].")

    # -----------------------------------------------------------------------
    # Grid Arrangement & Adaptive Density Rendering
    # -----------------------------------------------------------------------
    def _render_grid(self):
        for child in self.grid_container.winfo_children():
            child.destroy()
        self.cell_widgets.clear()

        # Prune assignments outside current dimensions
        self.grid_assignments = {
            (r, c): p for (r, c), p in self.grid_assignments.items()
            if r < self.current_rows and c < self.current_cols
        }

        for r in range(self.current_rows):
            self.grid_container.grid_rowconfigure(r, weight=1)
        for c in range(self.current_cols):
            self.grid_container.grid_columnconfigure(c, weight=1)

        active_key = f"{self.current_cols}x{self.current_rows}"
        for key, btn in self.preset_buttons.items():
            if key == active_key or key == f"{self.current_cols}×{self.current_rows}":
                btn.configure(fg_color=COLOR_ACCENT)
            else:
                btn.configure(fg_color=COLOR_CARD_BG)

        # High-density / compact layout threshold (for dense grids like 4x6, 5x10, etc.)
        is_compact = (self.current_cols >= 4 or self.current_rows >= 3)
        cell_pad = 3 if is_compact else 6

        cell_index = 0
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                profile = self.grid_assignments.get((r, c), None)
                cell_rect = self._get_cell_rect(r, c)
                card = GridCellCard(
                    self.grid_container,
                    row=r,
                    col=c,
                    cell_index=cell_index,
                    profile=profile,
                    is_compact=is_compact,
                    cell_rect=cell_rect,
                    on_cell_clicked=self._handle_cell_clicked,
                    on_cell_cleared=self._handle_cell_cleared,
                    on_cell_change=self._handle_cell_change,
                    on_cell_fine_tune=self._handle_cell_fine_tune
                )
                card.grid(row=r, column=c, padx=cell_pad, pady=cell_pad, sticky="nsew")
                self.cell_widgets[(r, c)] = card
                cell_index += 1

        self._save_state_auto()

    def _set_grid_preset(self, rows: int, cols: int, label: str):
        self.current_rows = rows
        self.current_cols = cols
        self._render_grid()
        self.lbl_status.configure(text=f"Switched grid layout to {label}.")

    def _prompt_custom_grid(self):
        CustomGridModal(
            parent=self,
            current_rows=self.current_rows,
            current_cols=self.current_cols,
            on_apply=self._apply_custom_grid
        )

    def _apply_custom_grid(self, rows: int, cols: int):
        self.current_rows = rows
        self.current_cols = cols
        self._render_grid()
        self.lbl_status.configure(text=f"Switched grid layout to {cols}×{rows} Custom.")

    def _get_cell_rect(self, row: int, col: int) -> Tuple[int, int, int, int]:
        mon_idx = min(self.settings.get("monitor_index", 0), max(0, len(self.monitors) - 1))
        target_monitor = self.monitors[mon_idx] if self.monitors else None
        if not target_monitor:
            return (0, 0, 800, 600)
        return WindowManager.calculate_cell_rect(
            monitor=target_monitor,
            rows=self.current_rows,
            cols=self.current_cols,
            row=row,
            col=col,
            gap=self.settings.get("cell_gap", 4),
            use_full_screen=self.settings.get("use_full_screen", False),
            margins=self.settings.get("screen_margins", {}),
            cell_offsets=self.settings.get("cell_offsets", {}),
            col_weights=self.settings.get("col_weights", []),
            row_weights=self.settings.get("row_weights", [])
        )

    def _handle_cell_fine_tune(self, row: int, col: int):
        self._open_fine_control_modal(initial_cell=(row, col))

    def _open_fine_control_modal(self, initial_cell: Optional[Tuple[int, int]] = None):
        FineControlModal(
            parent=self,
            settings=self.settings,
            monitors=self.monitors,
            current_rows=self.current_rows,
            current_cols=self.current_cols,
            grid_assignments=self.grid_assignments,
            on_apply=self._on_fine_control_applied,
            on_test_position=self._test_live_placement,
            initial_selected_cell=initial_cell
        )

    def _on_fine_control_applied(self, updated_settings: Dict[str, Any]):
        self.settings.update(updated_settings)
        ConfigManager.save_settings(self.settings)

        if hasattr(self, "btn_screen_mode"):
            cur_fs = self.settings.get("use_full_screen", False)
            self.btn_screen_mode.configure(
                text="📺 Full Screen" if cur_fs else "🖥️ Work Area",
                fg_color=COLOR_ACCENT if cur_fs else COLOR_CARD_BG
            )

        cur_gap = self.settings.get("cell_gap", 4)
        if hasattr(self, "btn_gap_zero"):
            self.btn_gap_zero.configure(fg_color=COLOR_ACCENT if cur_gap == 0 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_2"):
            self.btn_gap_2.configure(fg_color=COLOR_ACCENT if cur_gap == 2 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_4"):
            self.btn_gap_4.configure(fg_color=COLOR_ACCENT if cur_gap == 4 else COLOR_CARD_BG)

        self._render_grid()
        self.lbl_status.configure(text="Applied fine positioning & screen fit calibration.")

    def _toggle_screen_mode(self):
        new_val = not self.settings.get("use_full_screen", False)
        self.settings["use_full_screen"] = new_val
        ConfigManager.save_settings(self.settings)
        mode_str = "Full Screen (100% Edge-to-Edge)" if new_val else "Work Area (Excluding Taskbar)"
        if hasattr(self, "btn_screen_mode"):
            self.btn_screen_mode.configure(
                text="📺 Full Screen" if new_val else "🖥️ Work Area",
                fg_color=COLOR_ACCENT if new_val else COLOR_CARD_BG
            )
        self._render_grid()
        self.lbl_status.configure(text=f"Screen mode switched to {mode_str}.")

    def _test_live_placement(self, temp_settings: Dict[str, Any]):
        windows = WindowManager.get_chrome_windows()
        if not windows:
            self.lbl_status.configure(text="No active Chrome windows to test. Launch profiles or open Chrome first.")
            return

        assigned_cells = [
            (r, c, p) for (r, c), p in self.grid_assignments.items() if p is not None
        ]
        if not assigned_cells:
            assigned_cells = [
                (r, c, None) for r in range(self.current_rows) for c in range(self.current_cols)
            ]

        mon_idx = min(temp_settings.get("monitor_index", 0), max(0, len(self.monitors) - 1))
        target_monitor = self.monitors[mon_idx]

        arranged_count = 0
        for i, (hwnd, title, _) in enumerate(windows):
            if i >= len(assigned_cells):
                break
            r, c, _ = assigned_cells[i]
            x, y, w, h = WindowManager.calculate_cell_rect(
                monitor=target_monitor,
                rows=self.current_rows,
                cols=self.current_cols,
                row=r,
                col=c,
                gap=temp_settings.get("cell_gap", 4),
                use_full_screen=temp_settings.get("use_full_screen", False),
                margins=temp_settings.get("screen_margins", {}),
                cell_offsets=temp_settings.get("cell_offsets", {}),
                col_weights=temp_settings.get("col_weights", []),
                row_weights=temp_settings.get("row_weights", [])
            )
            WindowManager.position_window(
                hwnd=hwnd,
                x=x,
                y=y,
                w=w,
                h=h,
                dwm_compensation=temp_settings.get("dwm_compensation", True),
                dwm_border_offset=temp_settings.get("dwm_border_offset", 7)
            )
            self.managed_hwnds.add(hwnd)
            arranged_count += 1

        self.lbl_status.configure(text=f"Live test placed {arranged_count} window(s) onto {target_monitor.display_label}.")

    def _handle_cell_clicked(self, row: int, col: int):
        if self.selected_profile_for_assign:
            self._assign_cell(row, col, self.selected_profile_for_assign)
            self.lbl_status.configure(text=f"Placed '{self.selected_profile_for_assign.display_name}' into Cell [R{row+1}, C{col+1}].")
            self._on_profile_selected_in_sidebar(self.selected_profile_for_assign)  # Unselect
        else:
            self._handle_cell_change(row, col)

    def _handle_cell_change(self, row: int, col: int):
        ProfilePickerModal(
            parent=self,
            profiles=self.profiles,
            on_chosen=lambda p: self._assign_cell(row, col, p)
        )

    def _handle_cell_cleared(self, row: int, col: int):
        self.grid_assignments[(row, col)] = None
        if (row, col) in self.cell_widgets:
            is_compact = (self.current_cols >= 4 or self.current_rows >= 3)
            self.cell_widgets[(row, col)].set_profile(None, is_compact=is_compact)
        self.lbl_status.configure(text=f"Cleared Cell [R{row+1}, C{col+1}].")
        self._save_state_auto()

    def _assign_cell(self, row: int, col: int, profile: ChromeProfile):
        self.grid_assignments[(row, col)] = profile
        if (row, col) in self.cell_widgets:
            is_compact = (self.current_cols >= 4 or self.current_rows >= 3)
            self.cell_widgets[(row, col)].set_profile(profile, is_compact=is_compact)
        self._save_state_auto()

    def _clear_grid_assignments(self):
        for k in self.grid_assignments:
            self.grid_assignments[k] = None
        self._render_grid()
        self.lbl_status.configure(text="Cleared all cells in grid.")

    def _auto_populate_grid(self):
        """Sequentially assigns detected profiles from active group to grid cells, skipping protected personal profile."""
        if not self.profiles:
            self.lbl_status.configure(text="No profiles found to auto-populate.")
            return

        prot_key = self.settings.get("protected_profile_key", "Default")
        group_candidates = GroupManager.filter_profiles(self.profiles, self.active_group_id)
        allowed_profiles = [p for p in group_candidates if p.key != prot_key]

        if not allowed_profiles:
            self.lbl_status.configure(text="No profiles available in active group to auto-populate.")
            return

        assigned_count = 0
        idx = 0
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                if idx < len(allowed_profiles):
                    self.grid_assignments[(r, c)] = allowed_profiles[idx]
                    idx += 1
                    assigned_count += 1
                else:
                    self.grid_assignments[(r, c)] = None

        self._render_grid()

        grp_name = "All"
        if self.active_group_id == GroupManager.GROUP_NUMBERS:
            grp_name = "Numbers"
        elif self.active_group_id == GroupManager.GROUP_PRT:
            grp_name = "PRT"
        elif self.active_group_id == GroupManager.GROUP_OTHER:
            grp_name = "Other"
        else:
            cg = next((g for g in self.custom_groups if g.id == self.active_group_id), None)
            if cg:
                grp_name = cg.name

        prot_p = next((p for p in self.profiles if p.key == prot_key), None)
        prot_name = f" (Excluded: '{prot_p.display_name}')" if prot_p else ""
        self.lbl_status.configure(text=f"Auto populated {assigned_count} cells from group '{grp_name}'{prot_name}.")

    # -----------------------------------------------------------------------
    # Layout Persistence
    # -----------------------------------------------------------------------
    def _export_current_layout(self) -> Dict[str, Any]:
        assignments_data = {}
        for (r, c), p in self.grid_assignments.items():
            if p is not None:
                assignments_data[f"{r},{c}"] = {
                    "key": p.key,
                    "name": p.name,
                    "display_name": p.display_name
                }
        return {
            "rows": self.current_rows,
            "cols": self.current_cols,
            "monitor_index": self.settings.get("monitor_index", 0),
            "use_full_screen": self.settings.get("use_full_screen", False),
            "screen_margins": self.settings.get("screen_margins", {"top": 0, "bottom": 0, "left": 0, "right": 0}),
            "cell_gap": self.settings.get("cell_gap", 4),
            "dwm_compensation": self.settings.get("dwm_compensation", True),
            "dwm_border_offset": self.settings.get("dwm_border_offset", 7),
            "cell_offsets": self.settings.get("cell_offsets", {}),
            "col_weights": self.settings.get("col_weights", []),
            "row_weights": self.settings.get("row_weights", []),
            "assignments": assignments_data
        }

    def _save_state_auto(self):
        data = self._export_current_layout()
        ConfigManager.save_last_layout(data)

    def _restore_initial_grid(self):
        last_layout = ConfigManager.load_last_layout()
        if last_layout:
            self._apply_layout_dict(last_layout)
        else:
            self.current_rows = 2
            self.current_cols = 2
            self._auto_populate_grid()

    def _apply_layout_dict(self, layout: Dict[str, Any]):
        self.current_rows = max(1, layout.get("rows", 2))
        self.current_cols = max(1, layout.get("cols", 2))
        assignments_data = layout.get("assignments", {})

        if "use_full_screen" in layout:
            self.settings["use_full_screen"] = layout["use_full_screen"]
        if "screen_margins" in layout:
            self.settings["screen_margins"] = layout["screen_margins"]
        if "cell_gap" in layout:
            self.settings["cell_gap"] = layout["cell_gap"]
        if "dwm_compensation" in layout:
            self.settings["dwm_compensation"] = layout["dwm_compensation"]
        if "dwm_border_offset" in layout:
            self.settings["dwm_border_offset"] = layout["dwm_border_offset"]
        if "cell_offsets" in layout:
            self.settings["cell_offsets"] = layout["cell_offsets"]
        if "col_weights" in layout:
            self.settings["col_weights"] = layout["col_weights"]
        if "row_weights" in layout:
            self.settings["row_weights"] = layout["row_weights"]
        ConfigManager.save_settings(self.settings)

        if hasattr(self, "btn_screen_mode"):
            cur_fs = self.settings.get("use_full_screen", False)
            self.btn_screen_mode.configure(
                text="📺 Full Screen" if cur_fs else "🖥️ Work Area",
                fg_color=COLOR_ACCENT if cur_fs else COLOR_CARD_BG
            )

        cur_gap = self.settings.get("cell_gap", 4)
        if hasattr(self, "btn_gap_zero"):
            self.btn_gap_zero.configure(fg_color=COLOR_ACCENT if cur_gap == 0 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_2"):
            self.btn_gap_2.configure(fg_color=COLOR_ACCENT if cur_gap == 2 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_4"):
            self.btn_gap_4.configure(fg_color=COLOR_ACCENT if cur_gap == 4 else COLOR_CARD_BG)

        profile_map = {p.key: p for p in self.profiles}

        self.grid_assignments.clear()
        for r in range(self.current_rows):
            for c in range(self.current_cols):
                coord_key = f"{r},{c}"
                if coord_key in assignments_data:
                    p_info = assignments_data[coord_key]
                    p_key = p_info.get("key", "")
                    matched_profile = profile_map.get(p_key)
                    if not matched_profile and p_key:
                        matched_profile = ChromeProfile(
                            key=p_key,
                            name=p_info.get("name") or p_key,
                            initials=p_key[:2].upper()
                        )
                    self.grid_assignments[(r, c)] = matched_profile
                else:
                    self.grid_assignments[(r, c)] = None

        self._render_grid()

    def _open_save_layout_dialog(self):
        preset_name = f"Layout {self.current_cols}x{self.current_rows}"
        SaveLayoutModal(
            parent=self,
            default_name=preset_name,
            on_save=self._save_named_layout
        )

    def _save_named_layout(self, name: str):
        layout_data = self._export_current_layout()
        filepath = ConfigManager.save_layout_file(name, layout_data)
        self.lbl_status.configure(text=f"Saved layout preset '{name}' to {os.path.basename(filepath)}.")

    def _open_load_layout_dialog(self):
        LoadLayoutModal(parent=self, on_load_layout=self._apply_layout_dict)

    # -----------------------------------------------------------------------
    # Settings & Monitor Controls
    # -----------------------------------------------------------------------
    def _open_settings_dialog(self):
        SettingsModal(
            parent=self,
            settings=self.settings,
            monitors=self.monitors,
            profiles=self.profiles,
            on_save=self._on_settings_saved
        )

    def _on_settings_saved(self, new_settings: Dict[str, Any]):
        self.settings.update(new_settings)
        ConfigManager.save_settings(self.settings)

        sel_idx = min(self.settings.get("monitor_index", 0), len(self.monitors) - 1)
        if self.monitors:
            self.opt_top_monitor.set(self.monitors[sel_idx].display_label)

        self._apply_theme(self.settings.get("theme", "Dark"))

        override = self.settings.get("chrome_path_override", "")
        if override and os.path.exists(override):
            self.chrome_executable = override
        else:
            self.chrome_executable = ChromeProfileManager.find_chrome_executable()

        cur_gap = self.settings.get("cell_gap", 4)
        if hasattr(self, "btn_gap_zero"):
            self.btn_gap_zero.configure(fg_color=COLOR_ACCENT if cur_gap == 0 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_2"):
            self.btn_gap_2.configure(fg_color=COLOR_ACCENT if cur_gap == 2 else COLOR_CARD_BG)
        if hasattr(self, "btn_gap_4"):
            self.btn_gap_4.configure(fg_color=COLOR_ACCENT if cur_gap == 4 else COLOR_CARD_BG)

        self._filter_and_render_sidebar()
        self.lbl_status.configure(text="Settings saved successfully.")

    def _on_monitor_changed(self, choice: str):
        for idx, m in enumerate(self.monitors):
            if m.display_label == choice:
                self.settings["monitor_index"] = idx
                ConfigManager.save_settings(self.settings)
                self.lbl_status.configure(text=f"Switched active placement to {choice}.")
                break

    # -----------------------------------------------------------------------
    # Window Placement: Arrange Existing
    # -----------------------------------------------------------------------
    def _arrange_existing_windows(self):
        """Snaps already-open Chrome windows to assigned grid cells."""
        windows = WindowManager.get_chrome_windows()
        if not windows:
            self.lbl_status.configure(text="No active, visible Chrome windows found to arrange. Launch profiles with 🚀 LAUNCH ALL.")
            return

        assigned_cells = [
            (r, c, p) for (r, c), p in self.grid_assignments.items() if p is not None
        ]
        if not assigned_cells:
            assigned_cells = [
                (r, c, None) for r in range(self.current_rows) for c in range(self.current_cols)
            ]

        mon_idx = min(self.settings.get("monitor_index", 0), max(0, len(self.monitors) - 1))
        target_monitor = self.monitors[mon_idx]
        gap = self.settings.get("cell_gap", 4)
        use_fs = self.settings.get("use_full_screen", False)
        margins = self.settings.get("screen_margins", {})
        cell_offsets = self.settings.get("cell_offsets", {})
        col_weights = self.settings.get("col_weights", [])
        row_weights = self.settings.get("row_weights", [])
        dwm_comp = self.settings.get("dwm_compensation", True)
        dwm_offset = self.settings.get("dwm_border_offset", 7)

        arranged_count = 0
        for i, (hwnd, title, _) in enumerate(windows):
            if i >= len(assigned_cells):
                break
            r, c, _ = assigned_cells[i]
            x, y, w, h = WindowManager.calculate_cell_rect(
                monitor=target_monitor,
                rows=self.current_rows,
                cols=self.current_cols,
                row=r,
                col=c,
                gap=gap,
                use_full_screen=use_fs,
                margins=margins,
                cell_offsets=cell_offsets,
                col_weights=col_weights,
                row_weights=row_weights
            )
            WindowManager.position_window(
                hwnd=hwnd,
                x=x,
                y=y,
                w=w,
                h=h,
                dwm_compensation=dwm_comp,
                dwm_border_offset=dwm_offset
            )
            self.managed_hwnds.add(hwnd)
            arranged_count += 1

        self.lbl_status.configure(text=f"Arranged {arranged_count} active Chrome window(s) onto {target_monitor.display_label}.")

    # -----------------------------------------------------------------------
    # Multi-Threaded Launch Orchestrator
    # -----------------------------------------------------------------------
    def _handle_launch_all(self):
        if self.is_launching:
            self.cancel_launch_flag = True
            self.btn_launch_all.configure(text="Cancelling...")
            return

        if not self.chrome_executable or not os.path.exists(self.chrome_executable):
            self.lbl_status.configure(text="Error: Chrome executable not found. Please configure in Settings (⚙️).")
            self._open_settings_dialog()
            return

        assigned_cells = [
            (r, c, p) for (r, c), p in self.grid_assignments.items() if p is not None
        ]

        if not assigned_cells:
            self.lbl_status.configure(text="No profiles assigned to grid. Click '⚡ Auto Populate' or assign profiles first.")
            return

        self.is_launching = True
        self.cancel_launch_flag = False
        self.btn_launch_all.configure(text="🛑 STOP LAUNCH", fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER)
        self.progress_bar.grid()
        self.progress_bar.set(0)

        thread = threading.Thread(
            target=self._launch_worker,
            args=(assigned_cells,),
            daemon=True
        )
        thread.start()

    def _launch_worker(self, assigned_cells: List[Tuple[int, int, ChromeProfile]]):
        total = len(assigned_cells)
        mon_idx = min(self.settings.get("monitor_index", 0), max(0, len(self.monitors) - 1))
        target_monitor = self.monitors[mon_idx]
        gap = self.settings.get("cell_gap", 4)
        use_fs = self.settings.get("use_full_screen", False)
        margins = self.settings.get("screen_margins", {})
        cell_offsets = self.settings.get("cell_offsets", {})
        col_weights = self.settings.get("col_weights", [])
        row_weights = self.settings.get("row_weights", [])
        dwm_comp = self.settings.get("dwm_compensation", True)
        dwm_offset = self.settings.get("dwm_border_offset", 7)
        timeout = float(self.settings.get("window_timeout", 8.0))
        interval_ms = int(self.settings.get("launch_interval", 400))
        reuse = bool(self.settings.get("reuse_existing", False))

        success_count = 0

        for idx, (r, c, profile) in enumerate(assigned_cells, start=1):
            if self.cancel_launch_flag:
                break

            progress_val = (idx - 1) / total
            self.after(0, lambda v=progress_val, n=profile.display_name, i=idx: self._update_launch_progress(
                v, f"Launching ({i}/{total}): {n}..."
            ))

            x, y, w, h = WindowManager.calculate_cell_rect(
                monitor=target_monitor,
                rows=self.current_rows,
                cols=self.current_cols,
                row=r,
                col=c,
                gap=gap,
                use_full_screen=use_fs,
                margins=margins,
                cell_offsets=cell_offsets,
                col_weights=col_weights,
                row_weights=row_weights
            )

            hwnd = WindowManager.launch_and_position(
                chrome_exe=self.chrome_executable,
                profile_key=profile.key,
                x=x,
                y=y,
                w=w,
                h=h,
                timeout=timeout,
                reuse_existing=reuse,
                dwm_compensation=dwm_comp,
                dwm_border_offset=dwm_offset,
                already_managed_hwnds=self.managed_hwnds
            )

            if hwnd:
                self.managed_hwnds.add(hwnd)
                success_count += 1
                self.after(0, lambda row=r, col=c: self._mark_cell_status(row, col, "Active"))
            else:
                self.after(0, lambda row=r, col=c: self._mark_cell_status(row, col, "Timeout"))

            time.sleep(interval_ms / 1000.0)

        self.after(0, lambda count=success_count, t=total: self._finish_launch(count, t))

    def _handle_close_chrome(self):
        """Closes managed/gridded Chrome windows while protecting personal profile and never touching other apps."""
        active_windows = WindowManager.get_chrome_windows()
        if not active_windows and not self.managed_hwnds:
            self.lbl_status.configure(text="No active, visible Chrome windows found to close.")
            return

        prot_key = self.settings.get("protected_profile_key", "Default")
        prot_profile = next((p for p in self.profiles if p.key == prot_key), None)
        prot_name = prot_profile.display_name if prot_profile else "Personal"

        # Determine target windows to close:
        # If managed_hwnds are present, prioritize closing ONLY windows managed by this app.
        # Otherwise, close active Chrome windows (excluding protected personal profile).
        has_managed = bool(self.managed_hwnds)
        candidate_hwnds = set()

        if has_managed:
            for h in list(self.managed_hwnds):
                if win32gui.IsWindow(h) and WindowManager.is_chrome_window(h):
                    candidate_hwnds.add(h)
        else:
            for h, _, _ in active_windows:
                candidate_hwnds.add(h)

        if not candidate_hwnds:
            self.managed_hwnds.clear()
            self.lbl_status.configure(text="No target Chrome windows found to close.")
            return

        closed_count = 0
        for hwnd in candidate_hwnds:
            # 1. Absolute verification: MUST be real Google Chrome (chrome.exe)
            if not WindowManager.is_chrome_window(hwnd):
                continue

            # 2. Check if this window belongs to the protected personal profile
            is_prot = False
            win_prof = WindowManager.get_chrome_window_profile_key(hwnd)
            if prot_key and win_prof and win_prof.lower() == prot_key.lower():
                is_prot = True
            else:
                title = win32gui.GetWindowText(hwnd)
                if prot_name and prot_name.lower() in title.lower():
                    is_prot = True

            if is_prot:
                continue

            # 3. Post WM_CLOSE to Chrome window
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                closed_count += 1
            except Exception:
                pass

        self.managed_hwnds.clear()
        for cell in self.cell_widgets.values():
            cell.set_launch_status("")

        target_desc = "managed" if has_managed else "active"
        self.lbl_status.configure(text=f"Closed {closed_count} {target_desc} Chrome window(s) cleanly. Protected profile '{prot_name}' and other applications remain untouched.")

    def _update_launch_progress(self, progress: float, status_msg: str):
        self.progress_bar.set(progress)
        self.lbl_status.configure(text=status_msg)

    def _mark_cell_status(self, r: int, c: int, status: str):
        if (r, c) in self.cell_widgets:
            self.cell_widgets[(r, c)].set_launch_status(status)

    def _finish_launch(self, success_count: int, total: int):
        self.is_launching = False
        self.progress_bar.set(1.0)
        self.btn_launch_all.configure(
            text="🚀 LAUNCH ALL",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER
        )
        self.lbl_status.configure(
            text=f"Completed! Positioned {success_count} of {total} Chrome profile window(s) to grid."
        )
        self.after(4000, lambda: self.progress_bar.grid_remove())

        if self.settings.get("minimize_on_launch", False):
            self.after(300, self.iconify)


# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    app = ChromeGridLauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()

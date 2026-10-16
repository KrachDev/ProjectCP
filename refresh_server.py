"""
Refresh Server — Dedicated WebSocket & HTTP Server for Chrome Grid Launcher
Allows bidirectional real-time communication with Tampermonkey userscripts running
in multiple Chrome windows, triggering automated clicks on the page's Refresh button.
"""

import os
import sys
import json
import time
import random
import socket
import asyncio
import threading
import datetime
import urllib.parse
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable, Any

try:
    import websockets
    from websockets.http11 import Response
    Headers = getattr(websockets, "Headers", None)
except ImportError:
    websockets = None
    Response = None
    Headers = None


@dataclass
class ConnectedTab:
    tab_id: str
    title: str = "Untitled Tab"
    url: str = ""
    user_agent: str = ""
    version: str = ""  # e.g. "1.8.4"
    page_type: str = ""  # "a", "b", "other"
    has_inputs: bool = False
    connected_at: float = 0.0
    last_seen: float = 0.0
    last_result: str = "Ready"  # Ready, Success, Error, Timeout
    last_duration_ms: int = 0
    last_strategy: str = ""
    refresh_count: int = 0
    screen_x: int = 0
    screen_y: int = 0
    outer_w: int = 0
    outer_h: int = 0
    session_exp: float = 0.0
    session_remaining_sec: int = -1
    has_open_slots: bool = False
    dates_open: List[str] = None
    extension: str = "phylakon"

    def __post_init__(self):
        if self.dates_open is None:
            self.dates_open = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BroadcastTracker:
    cmd_id: str
    action: str
    targeted_count: int
    start_time: float
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    durations: List[int] = None
    completed: bool = False

    def __post_init__(self):
        if self.durations is None:
            self.durations = []


class RefreshServer:
    """Thread-safe WebSocket + HTTP server for orchestrating remote Chrome refreshes."""

    DEFAULT_PORT = 8765
    DEFAULT_HOST = "127.0.0.1"

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        script_path: Optional[str] = None
    ):
        self.host = host
        self.port = port
        if script_path:
            self.script_path = script_path
        else:
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            candidate = os.path.join(base_dir, "chrome_refresh_listener.user.js")
            if not os.path.exists(candidate):
                candidate = os.path.join(os.getcwd(), "chrome_refresh_listener.user.js")
            self.script_path = candidate

        self.running = False
        self.server_obj = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Connected clients mapping: websocket -> ConnectedTab
        self.clients: Dict[Any, ConnectedTab] = {}
        # HTTP-polled clients (for when browser blocks WebSockets via Mixed Content/CSP)
        self.http_clients: Dict[str, ConnectedTab] = {}
        self.pending_poll_waiters: Dict[str, asyncio.Future] = {}

        # Aggregate Statistics
        self.stats = {
            "total_broadcasts": 0,
            "total_acks_success": 0,
            "total_acks_failed": 0,
            "last_broadcast_time": 0.0,
            "last_command_id": "",
        }

        # Recent broadcast replay cache (5-second window for reconnecting tabs)
        self.recent_broadcast: Optional[Dict[str, Any]] = None
        # Active broadcast execution trackers for high-concurrency consolidated reporting
        self.broadcast_trackers: Dict[str, BroadcastTracker] = {}

        # Activity log (thread-safe list of dicts)
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 300

        # UI Callbacks
        self.on_clients_changed: Optional[Callable[[int, List[Dict[str, Any]]], None]] = None
        self.on_ack_received: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_log: Optional[Callable[[str, str], None]] = None
        self.on_status_changed: Optional[Callable[[bool, str], None]] = None

    # -----------------------------------------------------------------------
    # Logging & Notification Helpers
    # -----------------------------------------------------------------------
    def _create_broadcast_tracker(self, cmd_id: str, action: str, count: int):
        """Initializes a tracker to aggregate ACKs and log a single summary line."""
        with self._lock:
            tracker = BroadcastTracker(cmd_id=cmd_id, action=action, targeted_count=count, start_time=time.time())
            self.broadcast_trackers[cmd_id] = tracker
            now = time.time()
            for k in list(self.broadcast_trackers.keys()):
                if now - self.broadcast_trackers[k].start_time > 45:
                    self.broadcast_trackers.pop(k, None)

        if self.loop and self.loop.is_running():
            def _timeout_check():
                with self._lock:
                    tr = self.broadcast_trackers.get(cmd_id)
                    if tr and not tr.completed:
                        tr.completed = True
                        avg_dur = int(sum(tr.durations) / len(tr.durations)) if tr.durations else 0
                        elapsed = int((time.time() - tr.start_time) * 1000)
                        self.log(
                            f"⚡ Broadcast [{tr.action}] finished: {tr.success_count}/{tr.targeted_count} OK "
                            f"({tr.failed_count} fail, {tr.skipped_count} skipped, avg {avg_dur}ms, total {elapsed}ms)",
                            "SUCCESS" if tr.failed_count == 0 else "WARN"
                        )
            self.loop.call_later(7.0, _timeout_check)

    def _record_ack(
        self,
        tab_id: str,
        cmd_id: str,
        success: bool,
        ignored: bool,
        dur: int,
        strategy: str,
        err: str
    ):
        """Processes execution ACK from standalone endpoint or piggybacked on /api/poll."""
        with self._lock:
            target_tab = self.http_clients.get(tab_id)
            if not target_tab:
                for ct in self.clients.values():
                    if ct.tab_id == tab_id:
                        target_tab = ct
                        break
            tab_title = target_tab.title if target_tab else "Chrome Tab"
            if target_tab:
                target_tab.last_result = "Skipped" if ignored else ("Success" if success else "Error")
                target_tab.last_duration_ms = dur
                target_tab.last_strategy = strategy
                target_tab.last_seen = time.time()
                if success and (strategy != "open_tab"):
                    target_tab.refresh_count += 1

            if ignored:
                self.log(f"ACK SKIPPED from '{tab_title}': {err}", "INFO")
            elif success:
                self.stats["total_acks_success"] += 1
            else:
                if "Slot inputs not found on Page B after 11 attempts" in (err or ""):
                    # Ignore stale error from duplicate legacy script instance
                    return
                self.stats["total_acks_failed"] += 1
                self.log(f"ACK FAIL from '{tab_title}': {err}", "WARN")

            tracker = self.broadcast_trackers.get(cmd_id)
            if tracker and not tracker.completed:
                if ignored:
                    tracker.skipped_count += 1
                elif success:
                    tracker.success_count += 1
                    if dur > 0:
                        tracker.durations.append(dur)
                else:
                    tracker.failed_count += 1

                total_resp = tracker.success_count + tracker.failed_count + tracker.skipped_count
                if total_resp >= tracker.targeted_count:
                    tracker.completed = True
                    avg_dur = int(sum(tracker.durations) / len(tracker.durations)) if tracker.durations else 0
                    elapsed = int((time.time() - tracker.start_time) * 1000)
                    self.log(
                        f"⚡ Broadcast [{tracker.action}] finished: {tracker.success_count}/{tracker.targeted_count} OK "
                        f"({tracker.failed_count} fail, {tracker.skipped_count} skipped, avg {avg_dur}ms, total {elapsed}ms)",
                        "SUCCESS" if tracker.failed_count == 0 else "WARN"
                    )

        if self.on_ack_received:
            try:
                self.on_ack_received({
                    "tab_id": tab_id,
                    "command_id": cmd_id,
                    "success": success,
                    "ignored": ignored,
                    "duration_ms": dur,
                    "strategy": strategy,
                    "error": err
                })
            except Exception:
                pass

    def log(self, message: str, level: str = "INFO"):
        """Append to internal log buffer and notify callback."""
        ts_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": ts_str,
            "level": level,
            "message": message,
            "timestamp": time.time()
        }
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)

        if self.on_log:
            try:
                self.on_log(f"[{ts_str}] [{level}] {message}", level)
            except Exception:
                pass

    def _notify_clients_changed(self):
        """Invoke clients changed callback with current snapshot."""
        if not self.on_clients_changed:
            return
        snapshot = self.get_clients_snapshot()
        try:
            self.on_clients_changed(len(snapshot), snapshot)
        except Exception as e:
            self.log(f"Error in on_clients_changed callback: {e}", "WARN")

    def _schedule_clients_changed_notification(self, delay: float = 0.8):
        """Debounces clients changed callback to prevent CPU thrashing under high concurrency (e.g. 50 profiles)."""
        if not self.on_clients_changed:
            return
        with self._lock:
            if getattr(self, "_clients_changed_timer", None) is not None:
                return
            if self.loop and self.loop.is_running():
                try:
                    self._clients_changed_timer = self.loop.call_later(
                        delay,
                        self._fire_clients_changed_notification
                    )
                except Exception:
                    self._notify_clients_changed()
            else:
                self._notify_clients_changed()

    def _fire_clients_changed_notification(self):
        with self._lock:
            self._clients_changed_timer = None
        self._notify_clients_changed()

    def _notify_status(self, is_running: bool, info: str):
        self.running = is_running
        if self.on_status_changed:
            try:
                self.on_status_changed(is_running, info)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # HTTP Request Processor (for userscript delivery & status endpoint)
    # -----------------------------------------------------------------------
    def _process_response(self, connection, request, response):
        """Enriches WebSocket opening handshake response with CORS and Private Network headers."""
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    async def _process_http_request(self, connection, request):
        """Serves HTTP endpoints directly over the same port as WebSockets."""
        common_headers = [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "*"),
            ("Access-Control-Allow-Private-Network", "true"),
        ]

        # 1. Handle OPTIONS preflight request (crucial for Chrome Private Network Access)
        if getattr(request, "method", "") == "OPTIONS":
            opts_headers = Headers(common_headers + [("Access-Control-Max-Age", "86400")])
            return Response(204, "No Content", opts_headers, b"")

        # 2. If this is a WebSocket upgrade handshake, pass through to WebSocket handler
        if hasattr(request, "headers") and request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        path_parts = request.path.split("?")
        path = path_parts[0]
        query_str = path_parts[1] if len(path_parts) > 1 else ""
        query_params = urllib.parse.parse_qs(query_str)

        # 3. 1-Click Tampermonkey Script Installer Endpoint
        if path in ("/userscript.user.js", "/chrome_refresh_listener.user.js"):
            try:
                content = b""
                if os.path.exists(self.script_path):
                    with open(self.script_path, "rb") as f:
                        content = f.read()
                else:
                    content = b"// Error: chrome_refresh_listener.user.js not found on host disk."

                headers = Headers(common_headers + [
                    ("Content-Type", "text/javascript; charset=utf-8"),
                    ("Content-Disposition", 'inline; filename="chrome_refresh_listener.user.js"'),
                    ("Cache-Control", "no-cache, no-store, must-revalidate")
                ])
                return Response(200, "OK", headers, content)
            except Exception as e:
                err_body = f"Failed to read userscript: {e}".encode("utf-8")
                return Response(500, "Internal Server Error", Headers(common_headers + [("Content-Type", "text/plain")]), err_body)

        # 4. JSON Status API
        if path in ("/api/status", "/status"):
            data = {
                "running": self.running,
                "host": self.host,
                "port": self.port,
                "client_count": len(self.clients) + len(self.http_clients),
                "stats": self.stats,
                "clients": self.get_clients_snapshot()
            }
            body = json.dumps(data, indent=2).encode("utf-8")
            headers = Headers(common_headers + [("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        # 5. HTTP Trigger Refresh
        if path in ("/api/refresh", "/refresh"):
            cmd_id = self.broadcast_refresh()
            body = json.dumps({"status": "command_dispatched", "command_id": cmd_id, "clients_targeted": len(self.clients) + len(self.http_clients)}).encode("utf-8")
            headers = Headers(common_headers + [("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        # 5b. HTTP Trigger Slot Click (supports Page A / Page B / All)
        if path in ("/api/slot_click", "/api/slot"):
            target = query_params.get("target", ["b"])[0]
            a_sec = int(query_params.get("a_sec", ["0"])[0])
            a_ms = int(query_params.get("a_ms", ["0"])[0])
            a_step = int(query_params.get("a_step", ["0"])[0])
            b_sec = int(query_params.get("b_sec", ["55"])[0])
            b_ms = int(query_params.get("b_ms", ["10"])[0])
            b_step = int(query_params.get("b_step", ["0"])[0])
            cmd_id = self.broadcast_slot_click(
                target=target,
                page_a_sec=a_sec, page_a_ms=a_ms, page_a_ms_step=a_step,
                page_b_sec=b_sec, page_b_ms=b_ms, page_b_ms_step=b_step
            )
            body = json.dumps({
                "status": "command_dispatched",
                "command_id": cmd_id,
                "target": target,
                "sec": b_sec if target == "b" else a_sec,
                "ms": b_ms if target == "b" else a_ms
            }).encode("utf-8")
            headers = Headers(common_headers + [("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        # 6. Real-time Long-Poll Endpoint for GM_xmlhttpRequest (bypasses browser Mixed Content & CSP)
        if path in ("/api/poll", "/poll"):
            tab_id = query_params.get("tab_id", ["temp"])[0]
            title = query_params.get("title", ["Chrome Tab"])[0]
            url = query_params.get("url", [""])[0]
            version = query_params.get("v", [""])[0]
            page_type = query_params.get("page_type", [""])[0]
            has_inputs = query_params.get("has_inputs", ["0"])[0] in ("1", "true")
            try:
                screen_x = int(query_params.get("screen_x", ["0"])[0])
                screen_y = int(query_params.get("screen_y", ["0"])[0])
            except Exception:
                screen_x, screen_y = 0, 0

            # Process piggybacked execution ACK if present (slashes HTTP network roundtrips by 50%!)
            ack_cmd = query_params.get("ack_cmd", [""])[0]
            if ack_cmd:
                ack_success = query_params.get("ack_success", ["false"])[0].lower() in ("true", "1")
                ack_ignored = query_params.get("ack_ignored", ["false"])[0].lower() in ("true", "1")
                ack_dur = int(query_params.get("ack_dur", ["0"])[0])
                ack_strategy = query_params.get("ack_strategy", [""])[0]
                ack_err = query_params.get("ack_err", [""])[0]
                self._record_ack(tab_id, ack_cmd, ack_success, ack_ignored, ack_dur, ack_strategy, ack_err)
                self._schedule_clients_changed_notification(0.8)

            is_new = False
            pending_cached_broadcast = None
            with self._lock:
                if tab_id not in self.http_clients:
                    is_new = True
                    self.http_clients[tab_id] = ConnectedTab(
                        tab_id=tab_id,
                        title=title,
                        url=url,
                        version=version,
                        page_type=page_type,
                        has_inputs=has_inputs,
                        screen_x=screen_x,
                        screen_y=screen_y,
                        connected_at=time.time(),
                        last_seen=time.time()
                    )
                else:
                    self.http_clients[tab_id].last_seen = time.time()
                    self.http_clients[tab_id].title = title
                    self.http_clients[tab_id].url = url
                    self.http_clients[tab_id].screen_x = screen_x
                    self.http_clients[tab_id].screen_y = screen_y
                    if version:
                        self.http_clients[tab_id].version = version
                    if page_type:
                        self.http_clients[tab_id].page_type = page_type
                    self.http_clients[tab_id].has_inputs = has_inputs

                # Check if there is an unconsumed recent broadcast within 5s replay window
                recent = self.recent_broadcast
                if recent and time.time() < recent.get("expires_at", 0):
                    if tab_id not in recent["delivered_to"]:
                        recent["delivered_to"].add(tab_id)
                        pending_cached_broadcast = recent.get("payload_bytes") or json.dumps(recent["payload"]).encode("utf-8")

            if is_new:
                self.log(f"Chrome tab connected via HTTP poll: '{title}' [{tab_id[:10]}]")
                self._schedule_clients_changed_notification(0.8)

            # If there was an active broadcast within the last 5s, dispatch immediately to this reconnecting tab!
            if pending_cached_broadcast:
                headers = Headers(common_headers + [("Content-Type", "application/json")])
                return Response(200, "OK", headers, pending_cached_broadcast)

            with self._lock:
                future = self.loop.create_future()
                old_fut = self.pending_poll_waiters.pop(tab_id, None)
                if old_fut and not old_fut.done():
                    old_fut.cancel()
                self.pending_poll_waiters[tab_id] = future

            # Dynamic jittered server timeout: 22s to 32s (eliminates synchronized wave reconnects!)
            poll_timeout = 22.0 + random.uniform(0.0, 10.0)
            try:
                result = await asyncio.wait_for(future, timeout=poll_timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                result = {"action": "heartbeat"}
            finally:
                with self._lock:
                    if self.pending_poll_waiters.get(tab_id) is future:
                        self.pending_poll_waiters.pop(tab_id, None)
                    if tab_id in self.http_clients:
                        self.http_clients[tab_id].last_seen = time.time()

            body = b'{"action":"heartbeat"}' if (isinstance(result, dict) and result.get("action") == "heartbeat") else json.dumps(result).encode("utf-8")
            headers = Headers(common_headers + [("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        # 7. Execution ACK Endpoint (for standalone callers)
        if path in ("/api/ack", "/ack"):
            tab_id = query_params.get("tab_id", [""])[0]
            cmd_id = query_params.get("command_id", [""])[0]
            success = query_params.get("success", ["false"])[0].lower() in ("true", "1")
            ignored = query_params.get("ignored", ["false"])[0].lower() in ("true", "1")
            dur = int(query_params.get("duration_ms", ["0"])[0])
            strategy = query_params.get("strategy", [""])[0]
            err = query_params.get("error", [""])[0]

            self._record_ack(tab_id, cmd_id, success, ignored, dur, strategy, err)
            self._schedule_clients_changed_notification(0.8)
            body = b'{"status":"ack_recorded"}'
            headers = Headers(common_headers + [("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        # 8. Root Info Page
        if path == "/":
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Chrome Grid Refresh Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0e14; color: #f8fafc; padding: 40px; }}
        .card {{ background: #1a2030; border: 1px solid #232a3e; border-radius: 12px; padding: 24px; max-width: 650px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h1 {{ margin-top: 0; color: #3b82f6; font-size: 24px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: bold; background: #10b981; color: white; }}
        .btn {{ display: inline-block; background: #3b82f6; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 15px; margin-right: 10px; }}
        .btn:hover {{ background: #2563eb; }}
        .btn-success {{ background: #10b981; }}
        .btn-success:hover {{ background: #059669; }}
        pre {{ background: #121622; padding: 12px; border-radius: 6px; overflow-x: auto; color: #94a3b8; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Chrome Grid Refresh Server</h1>
        <p><span class="badge">Running</span> Server active on <code>{self.host}:{self.port}</code></p>
        <p><strong>Connected Chrome Tabs:</strong> {len(self.clients) + len(self.http_clients)}</p>
        <hr style="border: 0; border-top: 1px solid #232a3e; margin: 20px 0;">
        <h3>Tampermonkey Setup</h3>
        <p>Click below to install the userscript in this browser profile via Tampermonkey:</p>
        <a class="btn btn-success" href="/userscript.user.js">📥 1-Click Install Tampermonkey Script</a>
        <a class="btn" href="/status">📊 View Status JSON</a>
    </div>
</body>
</html>"""
            headers = Headers(common_headers + [("Content-Type", "text/html; charset=utf-8")])
            return Response(200, "OK", headers, html.encode("utf-8"))

        # Return None to proceed with regular WebSocket handshake
        return None

    # -----------------------------------------------------------------------
    # WebSocket Client Handler
    # -----------------------------------------------------------------------
    async def _handle_connection(self, websocket):
        """Handles an individual WebSocket connection from a Chrome tab."""
        client_tab = ConnectedTab(
            tab_id=f"temp_{id(websocket)}",
            connected_at=time.time(),
            last_seen=time.time()
        )

        with self._lock:
            self.clients[websocket] = client_tab

        client_ip = getattr(websocket.remote_address, "0", "unknown") if hasattr(websocket, "remote_address") else "browser"
        self.log(f"Chrome tab connected from {client_ip} (Total: {len(self.clients)})")
        self._schedule_clients_changed_notification(0.8)

        try:
            async for raw_msg in websocket:
                client_tab.last_seen = time.time()
                try:
                    data = json.loads(raw_msg)
                    msg_type = data.get("type", "")

                    if msg_type == "register":
                        client_tab.tab_id = data.get("tab_id", client_tab.tab_id)
                        client_tab.title = data.get("title", "Chrome Tab")
                        client_tab.url = data.get("url", "")
                        client_tab.user_agent = data.get("user_agent", "")
                        client_tab.screen_x = int(data.get("screen_x", 0))
                        client_tab.screen_y = int(data.get("screen_y", 0))
                        client_tab.outer_w = int(data.get("outer_w", 0))
                        client_tab.outer_h = int(data.get("outer_h", 0))
                        self.log(f"Registered Tab '{client_tab.title}' [{client_tab.tab_id[:10]}] at ({client_tab.screen_x},{client_tab.screen_y}) - {client_tab.url[:45]}")
                        self._schedule_clients_changed_notification(0.8)

                    elif msg_type in ("heartbeat", "tab_update"):
                        client_tab.title = data.get("title", client_tab.title)
                        client_tab.url = data.get("url", client_tab.url)
                        if "screen_x" in data:
                            client_tab.screen_x = int(data.get("screen_x", 0))
                        if "screen_y" in data:
                            client_tab.screen_y = int(data.get("screen_y", 0))

                    elif msg_type in ("session_update", "SESSION_UPDATE"):
                        client_tab.last_seen = time.time()
                        exp_date = float(data.get("expirationDate") or data.get("expiration_date") or 0.0)
                        rem_sec = int(data.get("remainingSec") or data.get("remaining_sec") or -1)
                        client_tab.session_exp = exp_date
                        client_tab.session_remaining_sec = rem_sec
                        self._schedule_clients_changed_notification(0.5)

                    elif msg_type in ("dates_found", "slots_open", "SLOTS_OPEN"):
                        client_tab.last_seen = time.time()
                        dates = data.get("dates") or []
                        client_tab.has_open_slots = True
                        client_tab.dates_open = dates
                        self.log(f"⚡ [OPEN SLOTS] Tab '{client_tab.title}' discovered open dates: {', '.join(dates)}", "CRITICAL")
                        self._schedule_clients_changed_notification(0.1)

                    elif msg_type in ("slot_timing_shared", "SLOT_TIMING_SHARED", "timing_share"):
                        client_tab.last_seen = time.time()
                        sec_val = data.get("sec")
                        ms_val = data.get("ms")
                        self.log(f"⚡ [TIMING SHARED] Tab '{client_tab.title}' discovered winning timing: Sec={sec_val}, MS={ms_val}! Relaying to all grid Chromes...", "CRITICAL")
                        # Relay timing immediately to all other connected tabs
                        self.broadcast_slot_click(sec=sec_val, ms=ms_val, target="all")

                    elif msg_type in ("refresh_ack", "slot_ack", "open_tab_ack", "thunder_config_ack", "phylakon_config_ack"):
                        success = bool(data.get("success", False))
                        dur = int(data.get("duration_ms", 0))
                        strategy = str(data.get("strategy", ""))
                        err = str(data.get("error", ""))
                        cmd_id = str(data.get("command_id", ""))

                        client_tab.last_result = "Success" if success else "Error"
                        client_tab.last_duration_ms = dur
                        client_tab.last_strategy = strategy
                        if success:
                            self.log(f"ACK OK from '{client_tab.title}' ({dur}ms via {strategy or msg_type})", "SUCCESS")
                        else:
                            self.log(f"ACK FAIL from '{client_tab.title}': {err}", "WARN")

                        self._record_ack(client_tab.tab_id, cmd_id, success, False, dur, strategy or msg_type, err)
                        self._schedule_clients_changed_notification(0.8)

                    elif msg_type == "pong":
                        pass

                except json.JSONDecodeError:
                    self.log(f"Invalid JSON received from tab: {raw_msg[:50]}", "WARN")

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.log(f"Connection exception with tab: {e}", "DEBUG")
        finally:
            with self._lock:
                self.clients.pop(websocket, None)
            self.log(f"Chrome tab disconnected: '{client_tab.title}' (Remaining: {len(self.clients)})")
            self._schedule_clients_changed_notification(0.8)

    # -----------------------------------------------------------------------
    # Server Lifecycle (Background Thread + Asyncio Event Loop)
    # -----------------------------------------------------------------------
    def start(self) -> bool:
        """Start the server in a background daemon thread."""
        if self.running or (self.thread and self.thread.is_alive()):
            self.log("Server is already running.")
            return True

        if websockets is None:
            err = "The 'websockets' Python library is not installed."
            self.log(err, "ERROR")
            self._notify_status(False, err)
            return False

        self.thread = threading.Thread(target=self._run_server_thread, daemon=True, name="RefreshServerThread")
        self.thread.start()

        # Wait briefly for server startup
        for _ in range(25):
            time.sleep(0.05)
            if self.running:
                break

        return self.running

    def _run_server_thread(self):
        """Target for background thread: sets up event loop and runs websockets.serve."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _serve():
            try:
                self.server_obj = await websockets.serve(
                    self._handle_connection,
                    self.host,
                    self.port,
                    process_request=self._process_http_request,
                    process_response=self._process_response,
                    open_timeout=None,
                    ping_interval=None,
                    max_queue=1024,
                    max_size=2**20,
                    backlog=1024
                )
                for s in getattr(self.server_obj, "sockets", []):
                    try:
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    except Exception:
                        pass
                self.log(f"Server started on ws://{self.host}:{self.port} (High-Concurrency Engine Active)", "SUCCESS")
                self._notify_status(True, f"Running on port {self.port}")
                await self.server_obj.wait_closed()
            except OSError as e:
                err_msg = f"Failed to bind to {self.host}:{self.port} — {e}"
                self.log(err_msg, "ERROR")
                self._notify_status(False, err_msg)
            except Exception as e:
                err_msg = f"Server loop error: {e}"
                self.log(err_msg, "ERROR")
                self._notify_status(False, err_msg)
            finally:
                self.running = False

        try:
            self.loop.run_until_complete(_serve())
        except Exception:
            pass
        finally:
            self.running = False
            self._notify_status(False, "Stopped")

    def stop(self):
        """Stops the server cleanly."""
        if not self.running and not (self.thread and self.thread.is_alive()):
            return

        self.log("Stopping server...")
        if self.server_obj and self.loop and self.loop.is_running():
            async def _close():
                # Cancel all waiting HTTP poll requests
                with self._lock:
                    waiters = list(self.pending_poll_waiters.values())
                    self.pending_poll_waiters.clear()
                for fut in waiters:
                    if not fut.done():
                        try:
                            fut.cancel()
                        except Exception:
                            pass

                # Close all active client connections
                with self._lock:
                    active_sockets = list(self.clients.keys())
                for ws in active_sockets:
                    try:
                        await ws.close(code=1000, reason="Server shutting down")
                    except Exception:
                        pass
                self.server_obj.close()
                await self.server_obj.wait_closed()

            try:
                future = asyncio.run_coroutine_threadsafe(_close(), self.loop)
                future.result(timeout=2.0)
            except Exception as e:
                self.log(f"Error during server close: {e}", "DEBUG")

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            self.thread.join(timeout=1.5)

        self.running = False
        self.server_obj = None
        self.thread = None
        with self._lock:
            self.clients.clear()
            self.http_clients.clear()
            self.pending_poll_waiters.clear()
        self.log("Server stopped successfully.")
        self._notify_status(False, "Stopped")
        self._notify_clients_changed()

    def restart(self, new_port: Optional[int] = None) -> bool:
        """Restart server, optionally with a new port."""
        self.stop()
        time.sleep(0.2)
        if new_port is not None:
            self.port = int(new_port)
        return self.start()

    # -----------------------------------------------------------------------
    # Refresh Command Broadcasting
    # -----------------------------------------------------------------------
    def broadcast_refresh(
        self,
        xpath: str = "/html/body/div[5]/div[1]/button[1]",
        text: str = "Refresh",
        class_name: str = "btn btn-primary",
        target: str = "all",
        stagger_ms: int = 0
    ) -> str:
        """Dispatches refresh command to connected Chrome tabs."""
        cmd_id = f"cmd_{int(time.time()*1000)}"
        self.stats["total_broadcasts"] += 1
        self.stats["last_broadcast_time"] = time.time()
        self.stats["last_command_id"] = cmd_id

        payload = {
            "action": "refresh",
            "command_id": cmd_id,
            "xpath": xpath,
            "text": text,
            "class_name": class_name,
            "target": target,
            "timestamp": time.time()
        }

        payload_bytes = json.dumps(payload).encode("utf-8")

        with self._lock:
            active_clients = list(self.clients.keys())
            active_waiters = list(self.pending_poll_waiters.items())
            self.pending_poll_waiters.clear()

            # Cache broadcast for 5.0s replay window so tabs that reconnect shortly after still get it
            delivered = set(t[0] for t in active_waiters)
            self.recent_broadcast = {
                "command_id": cmd_id,
                "payload": payload,
                "payload_bytes": payload_bytes,
                "expires_at": time.time() + 5.0,
                "delivered_to": delivered
            }

            total_targeted = len(active_clients) + len(active_waiters)
            if total_targeted == 0 and len(self.http_clients) == 0:
                self.log("Broadcast requested, but no Chrome tabs are currently connected.", "WARN")
                return cmd_id

            target_count = max(total_targeted, len(self.http_clients))
            self._create_broadcast_tracker(cmd_id, "Refresh", target_count)

        self.log(f"Broadcasting Refresh to {target_count} connected Chrome tabs (XPath: '{xpath}')", "INFO")

        # Single-tick batch resolution for all waiting long-poll futures (zero GIL thrashing)
        if self.loop and self.loop.is_running() and active_waiters:
            def _resolve_all():
                for tab_id, fut in active_waiters:
                    if not fut.done():
                        fut.set_result(payload)
            self.loop.call_soon_threadsafe(_resolve_all)

        if self.loop and self.loop.is_running() and active_clients:
            asyncio.run_coroutine_threadsafe(
                self._dispatch_broadcast(active_clients, payload, stagger_ms),
                self.loop
            )
        elif not self.loop or not self.loop.is_running():
            self.log("Server event loop is not running. Cannot broadcast.", "ERROR")

        return cmd_id

    def broadcast_open_tab(self, url: str) -> str:
        """Dispatches open_tab command to all connected Chrome tabs to open url as a new tab in their existing window."""
        cmd_id = f"tab_{int(time.time()*1000)}"
        self.stats["total_broadcasts"] += 1
        self.stats["last_broadcast_time"] = time.time()
        self.stats["last_command_id"] = cmd_id

        payload = {
            "action": "open_tab",
            "command_id": cmd_id,
            "url": url,
            "timestamp": time.time()
        }

        payload_bytes = json.dumps(payload).encode("utf-8")

        with self._lock:
            active_clients = list(self.clients.keys())
            active_waiters = list(self.pending_poll_waiters.items())
            self.pending_poll_waiters.clear()

            delivered = set(t[0] for t in active_waiters)
            self.recent_broadcast = {
                "command_id": cmd_id,
                "payload": payload,
                "payload_bytes": payload_bytes,
                "expires_at": time.time() + 5.0,
                "delivered_to": delivered
            }

            total_targeted = len(active_clients) + len(active_waiters)
            if total_targeted == 0 and len(self.http_clients) == 0:
                self.log("Open-tab requested, but no Chrome tabs are currently connected.", "WARN")
                return cmd_id

            target_count = max(total_targeted, len(self.http_clients))
            self._create_broadcast_tracker(cmd_id, "OpenTab", target_count)

        self.log(f"Broadcasting Open-Tab to {target_count} connected Chrome tab(s) (URL: '{url}')", "INFO")

        # Single-tick batch resolution for all waiting long-poll futures
        if self.loop and self.loop.is_running() and active_waiters:
            def _resolve_all():
                for tab_id, fut in active_waiters:
                    if not fut.done():
                        fut.set_result(payload)
            self.loop.call_soon_threadsafe(_resolve_all)

        if self.loop and self.loop.is_running() and active_clients:
            asyncio.run_coroutine_threadsafe(
                self._dispatch_broadcast(active_clients, payload, stagger_ms=40),
                self.loop
            )
        elif not self.loop or not self.loop.is_running():
            self.log("Server event loop is not running. Cannot broadcast open-tab.", "ERROR")

        return cmd_id

    def broadcast_phylakon_config(self, settings: dict, target_tab_ids: Optional[List[str]] = None) -> str:
        """Dispatches phylakon_config + thunder_config command to all or specifically targeted Chrome tabs."""
        cmd_id = f"phylakon_{int(time.time()*1000)}"
        self.stats["total_broadcasts"] += 1
        self.stats["last_broadcast_time"] = time.time()
        self.stats["last_command_id"] = cmd_id

        payload = {
            "action": "phylakon_config",
            "type": "phylakon_config",
            "command_id": cmd_id,
            "settings": settings,
            "timestamp": time.time()
        }

        payload_bytes = json.dumps(payload).encode("utf-8")
        target_tab_set = set(target_tab_ids) if target_tab_ids is not None else None

        with self._lock:
            if target_tab_set is not None:
                active_ws_clients = [ws for ws, tab in self.clients.items() if tab.tab_id in target_tab_set]
                active_waiters = [(tid, fut) for tid, fut in self.pending_poll_waiters.items() if tid in target_tab_set]
                for tid, _ in active_waiters:
                    self.pending_poll_waiters.pop(tid, None)
            else:
                active_ws_clients = list(self.clients.keys())
                active_waiters = list(self.pending_poll_waiters.items())
                self.pending_poll_waiters.clear()

            delivered = set(t[0] for t in active_waiters)
            self.recent_broadcast = {
                "command_id": cmd_id,
                "payload": payload,
                "payload_bytes": payload_bytes,
                "expires_at": time.time() + 5.0,
                "delivered_to": delivered
            }

            target_count = len(active_ws_clients) + len(active_waiters)
            if target_count == 0 and len(self.http_clients) == 0:
                self.log("Phylakon config requested, but no targeted Chrome tabs are connected.", "WARN")
                return cmd_id

            if target_tab_set is not None:
                target_count = len(target_tab_set)
            else:
                target_count = len(self.clients) + len(self.http_clients)

        self._create_broadcast_tracker(cmd_id, "phylakon_config", target_count)

        dispatched_ws = 0
        for ws in active_ws_clients:
            if getattr(ws, "open", True) and not getattr(ws, "closed", False):
                try:
                    asyncio.run_coroutine_threadsafe(ws.send(payload_bytes), self.loop)
                    dispatched_ws += 1
                except Exception:
                    pass

        dispatched_http = 0
        for tid, fut in active_waiters:
            if not fut.done():
                try:
                    fut.set_result(json.dumps(payload))
                    dispatched_http += 1
                except Exception:
                    pass

        reg = settings.get("region", "Spain")
        vt = settings.get("vtData", {})
        summary = f"{reg} | {vt.get('city','')} | {vt.get('category','')} | {vt.get('type','')} (Pax: {vt.get('members',1)})"
        self.log(
            f"⚡ Dispatched Phylakon Config [{summary}] to {dispatched_ws + dispatched_http} tab(s) (WS: {dispatched_ws}, HTTP: {dispatched_http})",
            "INFO"
        )
        return cmd_id

    def broadcast_applicant_profile(self, applicant: dict, target_tab_ids: Optional[List[str]] = None) -> str:
        """Dispatches applicant profile data (name, passport, birth, expiry, address, postal, city) to tabs."""
        cmd_id = f"applicant_{int(time.time()*1000)}"
        payload = {
            "action": "fill_applicant",
            "type": "fill_applicant",
            "command_id": cmd_id,
            "applicant": applicant,
            "timestamp": time.time()
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        with self._lock:
            active_ws = list(self.clients.keys())
        dispatched = 0
        for ws in active_ws:
            if getattr(ws, "open", True) and not getattr(ws, "closed", False):
                try:
                    asyncio.run_coroutine_threadsafe(ws.send(payload_bytes), self.loop)
                    dispatched += 1
                except Exception:
                    pass
        self.log(f"⚡ Dispatched Applicant Profile for '{applicant.get('name','')}' to {dispatched} tab(s).", "INFO")
        return cmd_id

    def broadcast_thunder_config(self, settings: dict, target_tab_ids: Optional[List[str]] = None) -> str:
        """Dispatches thunder_config command to all or specifically targeted Chrome tabs."""
        cmd_id = f"thunder_{int(time.time()*1000)}"
        self.stats["total_broadcasts"] += 1
        self.stats["last_broadcast_time"] = time.time()
        self.stats["last_command_id"] = cmd_id

        payload = {
            "action": "thunder_config",
            "command_id": cmd_id,
            "settings": settings,
            "timestamp": time.time()
        }

        payload_bytes = json.dumps(payload).encode("utf-8")
        target_tab_set = set(target_tab_ids) if target_tab_ids is not None else None

        with self._lock:
            # WebSocket clients to send to
            if target_tab_set is not None:
                active_ws_clients = [ws for ws, tab in self.clients.items() if tab.tab_id in target_tab_set]
                active_waiters = [(tid, fut) for tid, fut in self.pending_poll_waiters.items() if tid in target_tab_set]
                for tid, _ in active_waiters:
                    self.pending_poll_waiters.pop(tid, None)
            else:
                active_ws_clients = list(self.clients.keys())
                active_waiters = list(self.pending_poll_waiters.items())
                self.pending_poll_waiters.clear()

            delivered = set(t[0] for t in active_waiters)
            self.recent_broadcast = {
                "command_id": cmd_id,
                "payload": payload,
                "payload_bytes": payload_bytes,
                "expires_at": time.time() + 5.0,
                "delivered_to": delivered
            }

            target_count = len(active_ws_clients) + len(active_waiters)
            if target_count == 0 and len(self.http_clients) == 0:
                self.log("Thunder config requested, but no targeted Chrome tabs are connected.", "WARN")
                return cmd_id

            if target_tab_set is not None:
                target_count = len(target_tab_set)
            else:
                target_count = max(target_count, len(self.http_clients))

            self._create_broadcast_tracker(cmd_id, "ThunderConfig", target_count)

        self.log(f"Dispatched ThunderBolt settings to {target_count} target tab(s)", "INFO")

        # Resolve long-poll waiters
        if self.loop and self.loop.is_running() and active_waiters:
            def _resolve_all():
                for tab_id, fut in active_waiters:
                    if not fut.done():
                        fut.set_result(payload)
            self.loop.call_soon_threadsafe(_resolve_all)

        # Dispatch over WebSocket
        if self.loop and self.loop.is_running() and active_ws_clients:
            asyncio.run_coroutine_threadsafe(
                self._dispatch_broadcast(active_ws_clients, payload, stagger_ms=25),
                self.loop
            )

        return cmd_id

    def broadcast_slot_click(
        self,
        target: str = "all",
        page_a_sec: int = 0,
        page_a_ms: int = 0,
        page_a_ms_step: int = 0,
        page_a_delay_ms: int = 0,
        page_b_sec: int = 0,
        page_b_ms: int = 0,
        page_b_ms_step: int = 0,
        page_b_delay_ms: int = 0,
    ) -> str:
        """Dispatches individually addressed slot_click payloads to each Chrome tab.

        The MS value is incremented per targeted Chrome; sec rolls over automatically:
          Chrome 1  →  sec=base_sec,       ms=base_ms
          Chrome 2  →  sec=base_sec+carry, ms=(base_ms + step) % 1000
          Chrome N  →  sec=base_sec+carry, ms=(base_ms + (N-1)*step) % 1000

        target can be:
          'a'   → Only Page A (Calendar) tabs, using page_a_* values and step count
          'b'   → Only Page B (VisaType) tabs, using page_b_* values and step count
          'all' → Both pages
        """
        cmd_id = f"slot_{int(time.time()*1000)}"

        target = target.lower() if target in ("a", "b", "all") else "all"

        a_sec   = int(max(0, min(59,  page_a_sec)))
        a_ms    = int(max(0, min(999, page_a_ms)))
        a_step  = int(max(0, page_a_ms_step))
        a_delay = int(max(0, page_a_delay_ms))
        b_sec   = int(max(0, min(59,  page_b_sec)))
        b_ms    = int(max(0, min(999, page_b_ms)))
        b_step  = int(max(0, page_b_ms_step))
        b_delay = int(max(0, page_b_delay_ms))

        def _tab_matches(url: str, title: str, tgt: str, tab_obj: Optional[ConnectedTab] = None) -> bool:
            if tgt == "all":
                return True
            u = (url or "").lower()
            t = (title or "").lower()
            if not u and not t:
                return True
            # Exclude known non-slot pages from receiving slot-click commands
            if any(x in t for x in ("too many requests", "recaptcha", "captcha", "login", "blocked", "forbidden", "403", "502", "503")):
                return False

            # 1. If client tab explicitly reported its detected page type from DOM:
            if tab_obj and tab_obj.page_type:
                if tgt == "a" and tab_obj.page_type == "a":
                    return True
                if tgt == "b" and tab_obj.page_type == "b":
                    return True
                if tab_obj.page_type in ("a", "b") and tab_obj.page_type != tgt:
                    return False

            is_a = (
                "slotselection" in u or
                "slot-selection" in u or
                "slot_selection" in u or
                "slot selection" in t or
                "slot" in t or
                "calendar" in t or
                "calendar" in u
            )
            is_b = (
                "visatype" in u or
                "visa-type" in u or
                "visa_type" in u or
                "visa type" in t or
                "visatype" in t or
                "favicon.png" in u or
                "favicon" in u
            )
            if tgt == "a":
                # Tab must match Page A and not be specifically Page B
                if is_b and not is_a:
                    return False
                return is_a
            elif tgt == "b":
                # Tab must match Page B and not be specifically Page A
                if is_a and not is_b:
                    return False
                return is_b or (tab_obj and tab_obj.has_inputs)
            return True

        with self._lock:
            all_ws_clients = list(self.clients.items())
            all_waiters    = list(self.pending_poll_waiters.items())

            # Filter targeted waiters and pop ONLY targeted waiters
            targeted_waiters = []
            for tab_id, fut in all_waiters:
                tab_obj = self.http_clients.get(tab_id)
                tab_url = tab_obj.url if tab_obj else ""
                tab_title = tab_obj.title if tab_obj else ""
                if _tab_matches(tab_url, tab_title, target, tab_obj):
                    targeted_waiters.append((tab_id, fut))
                    self.pending_poll_waiters.pop(tab_id, None)

            targeted_ws = []
            for ws, tab_obj in all_ws_clients:
                tab_url = tab_obj.url if tab_obj else ""
                tab_title = tab_obj.title if tab_obj else ""
                if _tab_matches(tab_url, tab_title, target, tab_obj):
                    targeted_ws.append(ws)

        total_targeted = len(targeted_waiters) + len(targeted_ws)
        if total_targeted == 0 and len(self.http_clients) == 0:
            self.log(f"Slot-click ({target.upper()}) broadcast requested, but no Chrome tabs are connected.", "WARN")
            return cmd_id

        # Target count uses total_targeted or active matching clients in http_clients
        matching_http = sum(1 for c in self.http_clients.values() if _tab_matches(c.url, c.title, target, c))
        target_count = max(total_targeted, matching_http)
        if target_count == 0:
            self.log(f"Slot-click ({target.upper()}) requested, but no matching Chrome tabs found (Target='{target.upper()}').", "WARN")
            return cmd_id

        self._create_broadcast_tracker(cmd_id, f"SlotClick-{target.upper()}", target_count)

        self.log(
            f"Broadcasting Slot-Click [{target.upper()}] to {target_count} matching Chrome tab(s) "
            f"(Step: A={a_step}, B={b_step})",
            "INFO"
        )

        def _compute(base_sec, base_ms, step, idx):
            """Compute sec/ms for Chrome at index idx, with ms rollover into sec."""
            total_ms = base_ms + idx * step
            sec_out  = (base_sec + total_ms // 1000) % 60
            ms_out   = total_ms % 1000
            return sec_out, ms_out

        def _build_payload(idx: int) -> Dict[str, Any]:
            if target == "a":
                sec_i, ms_i = _compute(a_sec, a_ms, a_step, idx)
                return {
                    "action": "slot_click",
                    "target": "a",
                    "command_id": cmd_id,
                    "sec": sec_i,
                    "ms": ms_i,
                    "page_a_sec": sec_i,
                    "page_a_ms": ms_i,
                    "page_a_delay_ms": a_delay,
                    "page_b_sec": sec_i,
                    "page_b_ms": ms_i,
                    "page_b_delay_ms": b_delay,
                    "timestamp": time.time()
                }
            elif target == "b":
                sec_i, ms_i = _compute(b_sec, b_ms, b_step, idx)
                return {
                    "action": "slot_click",
                    "target": "b",
                    "command_id": cmd_id,
                    "sec": sec_i,
                    "ms": ms_i,
                    "page_a_sec": sec_i,
                    "page_a_ms": ms_i,
                    "page_a_delay_ms": a_delay,
                    "page_b_sec": sec_i,
                    "page_b_ms": ms_i,
                    "page_b_delay_ms": b_delay,
                    "timestamp": time.time()
                }
            else:
                a_sec_i, a_ms_i = _compute(a_sec, a_ms, a_step, idx)
                b_sec_i, b_ms_i = _compute(b_sec, b_ms, b_step, idx)
                return {
                    "action": "slot_click",
                    "target": "all",
                    "command_id": cmd_id,
                    "sec": a_sec_i,
                    "ms": a_ms_i,
                    "page_a_sec": a_sec_i,
                    "page_a_ms": a_ms_i,
                    "page_a_delay_ms": a_delay,
                    "page_b_sec": b_sec_i,
                    "page_b_ms": b_sec_i,
                    "page_b_delay_ms": b_delay,
                    "timestamp": time.time()
                }

        with self._lock:
            # Cache broadcast for 5.0s replay window so reconnecting tabs get it
            payload_sample = _build_payload(len(targeted_waiters) + len(targeted_ws))
            self.recent_broadcast = {
                "command_id": cmd_id,
                "payload": payload_sample,
                "payload_bytes": json.dumps(payload_sample).encode("utf-8"),
                "expires_at": time.time() + 5.0,
                "delivered_to": set(t[0] for t in targeted_waiters)
            }

        # ---- HTTP long-poll clients (single-tick batch resolution) ----
        if self.loop and self.loop.is_running() and targeted_waiters:
            def _resolve_slot_waiters():
                for idx, (tab_id, fut) in enumerate(targeted_waiters):
                    if not fut.done():
                        fut.set_result(_build_payload(idx))
            self.loop.call_soon_threadsafe(_resolve_slot_waiters)

        # ---- WebSocket clients (continue indexing after HTTP clients) ----
        ws_start_idx = len(targeted_waiters)
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._dispatch_slot_click_individual(
                    targeted_ws, cmd_id, target,
                    a_sec, a_ms, a_step, a_delay,
                    b_sec, b_ms, b_step, b_delay,
                    start_idx=ws_start_idx
                ),
                self.loop
            )
        else:
            self.log("Server event loop is not running. Cannot broadcast slot-click.", "ERROR")

        return cmd_id

    async def _dispatch_slot_click_individual(
        self,
        ws_clients: List[Any],
        cmd_id: str,
        target: str,
        a_sec: int, a_ms: int, a_step: int, a_delay: int,
        b_sec: int, b_ms: int, b_step: int, b_delay: int,
        start_idx: int = 0
    ):
        """Sends individually addressed slot_click payloads; MS increments per Chrome."""
        def _compute(base_sec, base_ms, step, idx):
            total_ms = base_ms + idx * step
            return (base_sec + total_ms // 1000) % 60, total_ms % 1000

        for idx, ws in enumerate(ws_clients):
            abs_idx = start_idx + idx
            if target == "a":
                sec_i, ms_i = _compute(a_sec, a_ms, a_step, abs_idx)
                payload = {
                    "action": "slot_click",
                    "target": "a",
                    "command_id": cmd_id,
                    "sec": sec_i,
                    "ms": ms_i,
                    "page_a_sec": sec_i,
                    "page_a_ms": ms_i,
                    "page_a_delay_ms": a_delay,
                    "timestamp": time.time()
                }
            elif target == "b":
                sec_i, ms_i = _compute(b_sec, b_ms, b_step, abs_idx)
                payload = {
                    "action": "slot_click",
                    "target": "b",
                    "command_id": cmd_id,
                    "sec": sec_i,
                    "ms": ms_i,
                    "page_b_sec": sec_i,
                    "page_b_ms": ms_i,
                    "page_b_delay_ms": b_delay,
                    "timestamp": time.time()
                }
            else:
                a_sec_i, a_ms_i = _compute(a_sec, a_ms, a_step, abs_idx)
                b_sec_i, b_ms_i = _compute(b_sec, b_ms, b_step, abs_idx)
                payload = {
                    "action": "slot_click",
                    "target": "all",
                    "command_id": cmd_id,
                    "page_a_sec": a_sec_i,
                    "page_a_ms": a_ms_i,
                    "page_a_delay_ms": a_delay,
                    "page_b_sec": b_sec_i,
                    "page_b_ms": b_ms_i,
                    "page_b_delay_ms": b_delay,
                    "timestamp": time.time()
                }
            try:
                await ws.send(json.dumps(payload))
            except Exception as e:
                self.log(f"Failed to send slot_click to client {abs_idx}: {e}", "DEBUG")




    async def _dispatch_broadcast(self, clients: List[Any], payload: Dict[str, Any], stagger_ms: int = 0):
        """Async worker that sends payload to WebSocket clients, optionally staggered."""
        msg_str = json.dumps(payload)

        # Send to WebSocket clients
        for idx, ws in enumerate(clients):
            try:
                await ws.send(msg_str)
            except Exception as e:
                self.log(f"Failed to send to client {idx}: {e}", "DEBUG")

            if stagger_ms > 0 and idx < len(clients) - 1:
                await asyncio.sleep(stagger_ms / 1000.0)

    # -----------------------------------------------------------------------
    # Status & Snapshot Retrieval
    # -----------------------------------------------------------------------
    def get_clients_snapshot(self) -> List[Dict[str, Any]]:
        """Returns a list of dicts for each connected tab (both WebSocket and HTTP)."""
        with self._lock:
            ws_tabs = [tab.to_dict() for tab in self.clients.values()]
            now = time.time()
            active_http = []
            for tid, tab in list(self.http_clients.items()):
                if (tid in self.pending_poll_waiters) or (now - tab.last_seen < 65):
                    active_http.append(tab.to_dict())
                else:
                    self.http_clients.pop(tid, None)
            return ws_tabs + active_http

    def get_stats(self) -> Dict[str, Any]:
        """Returns a snapshot copy of server stats."""
        with self._lock:
            res = dict(self.stats)
            res["active_clients"] = len(self.clients) + len(self.http_clients)
            res["running"] = self.running
            res["port"] = self.port
            return res


# ---------------------------------------------------------------------------
# Standalone CLI execution for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Starting Chrome Grid Refresh Server in standalone mode...")
    print("=" * 60)
    server = RefreshServer(port=8765)
    server.start()

    try:
        while True:
            cmd = input("\nEnter 'r' to broadcast refresh, 's' for status, 'q' to quit: ").strip().lower()
            if cmd == "r":
                server.broadcast_refresh()
            elif cmd == "s":
                print(json.dumps(server.get_stats(), indent=2))
                print(f"Connected tabs ({len(server.clients)}):")
                for c in server.get_clients_snapshot():
                    print(f" - {c['title']} ({c['url']}) | Last: {c['last_result']}")
            elif cmd == "q":
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print("Server shutdown complete.")

using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;

namespace ChromeGridLauncher.Services
{
    public static class ExtensionDeploymentService
    {
        public const string GlobalExtensionDirectory = @"C:\ChromeGridExtension";
        private static string? _cachedExtensionPath = null;
        private static string? _cachedUserscriptPath = null;

        /// <summary>
        /// Ensures that the ChromeGridExtension unpacked directory exists at the permanent global location
        /// (C:\ChromeGridExtension) and is fully populated with manifest.json, background.js, and content.js.
        /// Extracts directly on the spot from embedded resources or fallback code strings.
        /// Enables the user pattern: "load it manually once so change it once, change in all".
        /// </summary>
        public static string EnsureExtensionDeployed()
        {
            // 1. Primary Target: Global location C:\ChromeGridExtension
            string globalDir = GlobalExtensionDirectory;
            try
            {
                if (!Directory.Exists(globalDir))
                {
                    Directory.CreateDirectory(globalDir);
                }

                // Extract or update manifest.json
                string manifestPath = Path.Combine(globalDir, "manifest.json");
                string manifestContent = ReadEmbeddedResource("manifest.json") ?? FallbackManifestJson;
                DeployIfDifferent(manifestPath, manifestContent);

                // Extract or update background.js
                string bgPath = Path.Combine(globalDir, "background.js");
                string bgContent = ReadEmbeddedResource("background.js") ?? FallbackBackgroundJs;
                DeployIfDifferent(bgPath, bgContent);

                // Extract or update content.js
                string contentPath = Path.Combine(globalDir, "content.js");
                string contentContent = ReadEmbeddedResource("content.js") ?? FallbackContentJs;
                DeployIfDifferent(contentPath, contentContent);

                _cachedExtensionPath = Path.GetFullPath(globalDir);
                Console.WriteLine($"[ExtensionDeploymentService] Global extension ready on the spot at: {_cachedExtensionPath}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ExtensionDeploymentService] Error deploying to global directory {globalDir}: {ex.Message}");
            }

            // 2. Also deploy secondary adjacent copy if different
            try
            {
                string localDir = GetBestDeploymentDirectory("ChromeGridExtension");
                if (!string.Equals(localDir, globalDir, StringComparison.OrdinalIgnoreCase))
                {
                    if (!Directory.Exists(localDir)) Directory.CreateDirectory(localDir);
                    DeployIfDifferent(Path.Combine(localDir, "manifest.json"), ReadEmbeddedResource("manifest.json") ?? FallbackManifestJson);
                    DeployIfDifferent(Path.Combine(localDir, "background.js"), ReadEmbeddedResource("background.js") ?? FallbackBackgroundJs);
                    DeployIfDifferent(Path.Combine(localDir, "content.js"), ReadEmbeddedResource("content.js") ?? FallbackContentJs);
                }
            }
            catch { }

            if (!string.IsNullOrEmpty(_cachedExtensionPath) && Directory.Exists(_cachedExtensionPath))
            {
                return _cachedExtensionPath;
            }

            // 3. Fallback to LocalAppData if C:\ root was not writable
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string fallbackDir = Path.Combine(appData, "ChromeGridLauncher", "ChromeGridExtension");
            Directory.CreateDirectory(fallbackDir);

            File.WriteAllText(Path.Combine(fallbackDir, "manifest.json"), ReadEmbeddedResource("manifest.json") ?? FallbackManifestJson);
            File.WriteAllText(Path.Combine(fallbackDir, "background.js"), ReadEmbeddedResource("background.js") ?? FallbackBackgroundJs);
            File.WriteAllText(Path.Combine(fallbackDir, "content.js"), ReadEmbeddedResource("content.js") ?? FallbackContentJs);

            _cachedExtensionPath = Path.GetFullPath(fallbackDir);
            return _cachedExtensionPath;
        }

        /// <summary>
        /// Forces re-extraction and overwriting of latest manifest, background, and content scripts
        /// into the global C:\ChromeGridExtension directory.
        /// </summary>
        public static void ForceSyncGlobalFiles()
        {
            string targetDir = GlobalExtensionDirectory;
            if (!Directory.Exists(targetDir))
            {
                Directory.CreateDirectory(targetDir);
            }

            string manifest = ReadEmbeddedResource("manifest.json") ?? FallbackManifestJson;
            string bg = ReadEmbeddedResource("background.js") ?? FallbackBackgroundJs;
            string content = ReadEmbeddedResource("content.js") ?? FallbackContentJs;

            File.WriteAllText(Path.Combine(targetDir, "manifest.json"), manifest, Encoding.UTF8);
            File.WriteAllText(Path.Combine(targetDir, "background.js"), bg, Encoding.UTF8);
            File.WriteAllText(Path.Combine(targetDir, "content.js"), content, Encoding.UTF8);
            _cachedExtensionPath = Path.GetFullPath(targetDir);
            Console.WriteLine($"[ExtensionDeploymentService] Force-synced files to: {targetDir}");
        }

        public static bool IsGlobalExtensionReady()
        {
            return Directory.Exists(GlobalExtensionDirectory) &&
                   File.Exists(Path.Combine(GlobalExtensionDirectory, "manifest.json")) &&
                   File.Exists(Path.Combine(GlobalExtensionDirectory, "content.js"));
        }

        /// <summary>
        /// Ensures chrome_refresh_listener.user.js is extracted on the spot if not already present.
        /// </summary>
        private static string GetActualApplicationDirectory()
        {
            string? exePath = Environment.ProcessPath;
            if (!string.IsNullOrWhiteSpace(exePath) && File.Exists(exePath))
            {
                string? dir = Path.GetDirectoryName(exePath);
                if (!string.IsNullOrWhiteSpace(dir) && Directory.Exists(dir))
                    return dir;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            if (!string.IsNullOrWhiteSpace(baseDir) && !baseDir.Contains(@"\Temp\.net\", StringComparison.OrdinalIgnoreCase))
            {
                return baseDir;
            }

            return Directory.GetCurrentDirectory();
        }

        public static string EnsureUserscriptDeployed()
        {
            if (!string.IsNullOrEmpty(_cachedUserscriptPath) && File.Exists(_cachedUserscriptPath))
            {
                return _cachedUserscriptPath;
            }

            string baseDir = GetActualApplicationDirectory();
            string targetPath = Path.Combine(baseDir, "chrome_refresh_listener.user.js");

            if (!File.Exists(targetPath))
            {
                string? script = ReadEmbeddedResource("chrome_refresh_listener.user.js");
                if (!string.IsNullOrWhiteSpace(script))
                {
                    try
                    {
                        File.WriteAllText(targetPath, script, Encoding.UTF8);
                        _cachedUserscriptPath = targetPath;
                        return _cachedUserscriptPath;
                    }
                    catch { }
                }
            }
            else
            {
                _cachedUserscriptPath = targetPath;
                return _cachedUserscriptPath;
            }

            // Fallback
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string fallbackPath = Path.Combine(appData, "ChromeGridLauncher", "chrome_refresh_listener.user.js");
            if (!File.Exists(fallbackPath))
            {
                string? script = ReadEmbeddedResource("chrome_refresh_listener.user.js");
                if (!string.IsNullOrWhiteSpace(script))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(fallbackPath)!);
                    File.WriteAllText(fallbackPath, script, Encoding.UTF8);
                }
            }

            _cachedUserscriptPath = File.Exists(targetPath) ? targetPath : fallbackPath;
            return _cachedUserscriptPath;
        }

        private static string GetBestDeploymentDirectory(string subFolderName)
        {
            string exeDir = GetActualApplicationDirectory();
            string targetDir = Path.Combine(exeDir, subFolderName);

            // Test if directory is writable
            try
            {
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }
                string testFile = Path.Combine(targetDir, ".write_probe_" + Guid.NewGuid().ToString("N"));
                File.WriteAllText(testFile, "probe");
                File.Delete(testFile);
                return targetDir;
            }
            catch
            {
                // Read-only directory: fallback to LocalAppData
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return Path.Combine(appData, "ChromeGridLauncher", subFolderName);
            }
        }

        private static void DeployIfDifferent(string filePath, string newContent)
        {
            try
            {
                if (File.Exists(filePath))
                {
                    string existing = File.ReadAllText(filePath);
                    if (existing == newContent) return;

                    // Safety guard: if disk file has modern code (e.g. contains isSlotPageA) and newContent does not,
                    // do not overwrite the disk file with an older embedded version!
                    if (filePath.EndsWith("content.js", StringComparison.OrdinalIgnoreCase) &&
                        existing.Contains("isSlotPageA") && !newContent.Contains("isSlotPageA"))
                    {
                        Console.WriteLine($"[ExtensionDeploymentService] Preserving newer disk copy of {filePath}");
                        return;
                    }
                }
                File.WriteAllText(filePath, newContent, Encoding.UTF8);
            }
            catch
            {
                // Write failure (file might be locked by running Chrome) - ignore if file exists
                if (!File.Exists(filePath))
                {
                    throw;
                }
            }
        }

        public static string? ReadEmbeddedResource(string resourceSuffix)
        {
            try
            {
                var assembly = Assembly.GetExecutingAssembly();
                string? name = assembly.GetManifestResourceNames()
                    .FirstOrDefault(n => n.EndsWith(resourceSuffix, StringComparison.OrdinalIgnoreCase));

                if (name == null) return null;

                using var stream = assembly.GetManifestResourceStream(name);
                if (stream == null) return null;

                using var reader = new StreamReader(stream, Encoding.UTF8);
                return reader.ReadToEnd();
            }
            catch
            {
                return null;
            }
        }

        // =========================================================================
        // Fallback Embedded Code Strings (Zero-Failure Guarantees)
        // =========================================================================

        public static readonly string FallbackManifestJson = """
{
  "manifest_version": 3,
  "name": "Chrome Grid Sync Bridge",
  "version": "1.3.1",
  "description": "Ultra-reliable native sync bridge for Chrome Grid Launcher. Zero-install, DRM-proof, and zero proxy interference.",
  "permissions": [
    "storage",
    "alarms",
    "tabs",
    "scripting"
  ],
  "host_permissions": [
    "<all_urls>"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": [
        "<all_urls>"
      ],
      "js": [
        "content.js"
      ],
      "run_at": "document_start",
      "all_frames": true,
      "match_about_blank": true
    }
  ],
  "action": {
    "default_title": "Chrome Grid Sync Bridge"
  }
}
""";

        public static readonly string FallbackBackgroundJs = """
const SERVER_PORT = 8765;
const WS_URL = `ws://127.0.0.1:${SERVER_PORT}/`;
const HTTP_BASE = `http://127.0.0.1:${SERVER_PORT}`;
let socket = null;
let isConnected = false;
let reconnectTimer = null;
let reconnectDelay = 3000;
const MAX_RECONNECT_DELAY = 30000;
const registeredTabs = new Map();

function connectWs() {
    if (isConnected || socket) return;
    try {
        socket = new WebSocket(WS_URL);
        socket.onopen = () => {
            isConnected = true;
            reconnectDelay = 3000;
            broadcastToTabs({ type: "connection_status", connected: true, mode: "websocket" });
            for (const [, info] of registeredTabs) {
                wsSend({ type: "tab_init", tab_id: info.tabId, title: info.title, url: info.url, screen_x: 0, screen_y: 0 });
            }
        };
        socket.onmessage = (event) => { try { const d = JSON.parse(event.data); const a = (d.action || d.type || "").toLowerCase(); if (a === "pong" || a === "sync_pong" || a === "noop") return; broadcastToTabs({ type: "server_message", data: d }); } catch (e) {} };
        socket.onclose = () => { cleanupSocket(); scheduleReconnect(); };
        socket.onerror = () => { cleanupSocket(); scheduleReconnect(); };
    } catch (e) { cleanupSocket(); scheduleReconnect(); }
}

function cleanupSocket() {
    if (socket) { try { socket.close(); } catch (e) {} socket = null; }
    let was = isConnected; isConnected = false;
    if (was) broadcastToTabs({ type: "connection_status", connected: false, mode: "none" });
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => { reconnectTimer = null; connectWs(); }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
}

function wsSend(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) { try { socket.send(JSON.stringify(payload)); return true; } catch (e) {} }
    return false;
}

async function httpAck(data) { try { await fetch(`${HTTP_BASE}/ack`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }); } catch (e) {} }

async function httpPoll(tabId, title, url) {
    try { const r = await fetch(`${HTTP_BASE}/poll?tab_id=${encodeURIComponent(tabId)}&title=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`, { cache: "no-store" });
        if (r.ok) { const m = await r.json(); if (m && m.action && m.action !== "noop" && m.action !== "pong" && m.action !== "sync_pong") return m; }
    } catch (e) {} return null;
}

function broadcastToTabs(message) {
    for (const id of registeredTabs.keys()) { try { chrome.tabs.sendMessage(id, message).catch(() => {}); } catch (e) {} }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    const cid = sender.tab?.id;
    switch (msg.type) {
        case "register_tab": {
            if (cid != null) registeredTabs.set(cid, { tabId: msg.tabId, title: msg.title || "", url: msg.url || "" });
            const p = { type: "tab_init", tab_id: msg.tabId, title: msg.title || "", url: msg.url || "", screen_x: msg.screen_x || 0, screen_y: msg.screen_y || 0 };
            if (!wsSend(p)) { httpPoll(msg.tabId, msg.title || "", msg.url || "").then(d => { if (d && cid != null) try { chrome.tabs.sendMessage(cid, { type: "server_message", data: d }).catch(() => {}); } catch (e) {} }); }
            sendResponse({ connected: isConnected }); break;
        }
        case "send_payload": {
            const pl = msg.payload;
            if (!wsSend(pl) && pl && (pl.type === "ack" || pl.type === "slot_ack" || pl.type === "thunder_config_ack" || pl.type === "pong")) httpAck(pl);
            sendResponse({ ok: true }); break;
        }
        case "tab_update": {
            if (cid != null && registeredTabs.has(cid)) { const i = registeredTabs.get(cid); i.title = msg.title || i.title; i.url = msg.url || i.url; }
            wsSend({ type: "tab_update", tab_id: msg.tabId, title: msg.title || "", url: msg.url || "" }); break;
        }
        case "get_status": { sendResponse({ connected: isConnected }); break; }
    }
    return true;
});

chrome.tabs.onRemoved.addListener((tabId) => { registeredTabs.delete(tabId); });
try { chrome.alarms.create("cgl_keepalive", { periodInMinutes: 0.4 }); chrome.alarms.onAlarm.addListener((a) => { if (a.name === "cgl_keepalive" && !isConnected && !socket) connectWs(); }); } catch (e) {}
connectWs();
console.log("[ChromeGrid BG] Background service worker initialized. Relay mode active.");
""";

        public static readonly string FallbackContentJs = """
// Chrome Grid Sync Bridge - Content Script (PNA-safe relay via background service worker)
(() => {
    if (window.top !== window) return;
    if (window.__chromeGridSyncBridgeLoaded) return;
    window.__chromeGridSyncBridgeLoaded = true;

    let tabId = "";
    try { tabId = sessionStorage.getItem("__cgl_tab_id") || ""; } catch (e) {}
    if (!tabId) {
        tabId = "tab_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 7);
        try { sessionStorage.setItem("__cgl_tab_id", tabId); } catch (e) {}
    }

    let isConnected = false;
    let refreshCount = 0;
    let badgeEl = null;
    let isWaitingForBody = false;
    let registerRetryTimer = null;

    function updateBadge(status, text, bg) {
        if (!document.body) {
            if (!isWaitingForBody) { isWaitingForBody = true; window.addEventListener("DOMContentLoaded", () => { isWaitingForBody = false; updateBadge(status, text, bg); }, { once: true }); }
            return;
        }
        if (!badgeEl) {
            badgeEl = document.createElement("div");
            badgeEl.id = "__cgl_status_badge";
            badgeEl.style.cssText = "position:fixed;bottom:6px;right:6px;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:10px;font-weight:600;padding:3px 6px;border-radius:4px;display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none;opacity:0.8;pointer-events:auto;";
            badgeEl.title = "Chrome Grid Sync Bridge";
            badgeEl.addEventListener("click", () => { badgeEl.style.opacity = badgeEl.style.opacity === "0.2" ? "0.8" : "0.2"; });
            document.body.appendChild(badgeEl);
        }
        badgeEl.style.background = bg || "#1E293B"; badgeEl.style.color = "#F8FAFC";
        badgeEl.innerHTML = `<span style="font-size:7px;">●</span> ${text}`;
    }

    function sendPayload(obj) { try { chrome.runtime.sendMessage({ type: "send_payload", payload: obj }); return true; } catch (e) { return false; } }
    function sendAck(ackData) { sendPayload({ type: "ack", ...ackData }); }

    function registerWithBackground() {
        if (registerRetryTimer) { clearTimeout(registerRetryTimer); registerRetryTimer = null; }
        try {
            chrome.runtime.sendMessage({ type: "register_tab", tabId, title: document.title, url: window.location.href, screen_x: window.screenX || 0, screen_y: window.screenY || 0 }, (r) => {
                if (chrome.runtime.lastError) { updateBadge("error", "Grid Sync: Waiting...", "#D97706"); registerRetryTimer = setTimeout(registerWithBackground, 5000); return; }
                isConnected = r && r.connected; updateBadge(isConnected ? "connected" : "waiting", isConnected ? "Grid Sync: Connected" : "Grid Sync: Waiting...", isConnected ? "#047857" : "#D97706");
            });
        } catch (e) { registerRetryTimer = setTimeout(registerWithBackground, 5000); }
    }

    chrome.runtime.onMessage.addListener((msg) => {
        if (msg.type === "connection_status") { isConnected = msg.connected; updateBadge(msg.connected ? "connected" : "disconnected", msg.connected ? "Grid Sync: Connected" : "Grid Sync: Disconnected", msg.connected ? "#047857" : "#B91C1C"); }
        else if (msg.type === "server_message") handleServerMessage(msg.data);
    });

    function handleServerMessage(data) {
        if (!data || !data.action) return;
        switch (data.action) {
            case "refresh": case "trigger_refresh": executeRefresh(data); break;
            case "hard_reload": case "HARD_RELOAD": case "reload": window.location.reload(true); break;
            case "slot_click": case "SLOT_CLICK": executeSlotClick(data); break;
            case "thunder_config": executeThunderConfig(data); break;
            case "ping": sendPayload({ type: "pong", tab_id: tabId, timestamp: Date.now() }); break;
            case "pong": case "sync_pong": case "noop": break;
        }
    }

    function setNativeInputValue(el, value) {
        if (!el) return false; const s = String(value);
        try { el.focus(); } catch (e) {}
        try { const t = el._valueTracker; if (t) t.setValue(el.value + "_prev"); } catch (e) {}
        let ok = false;
        try { const p = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set; if (p) { p.call(el, s); ok = true; } } catch (e) {}
        if (!ok) try { el.value = s; } catch (e) {}
        try { el.value = s; } catch (e) {} try { el.setAttribute("value", s); } catch (e) {}
        try { el.dispatchEvent(new Event('input', { bubbles: true, composed: true })); el.dispatchEvent(new Event('change', { bubbles: true, composed: true })); } catch (e) {}
        return true;
    }

    function executeSlotClick(params = {}) {
        const target = (params.target || "all").toLowerCase();
        const aSec = params.page_a_sec !== undefined ? params.page_a_sec : (params.sec || 0), aMs = params.page_a_ms !== undefined ? params.page_a_ms : (params.ms || 0);
        const bSec = params.page_b_sec !== undefined ? params.page_b_sec : (params.sec || 0), bMs = params.page_b_ms !== undefined ? params.page_b_ms : (params.ms || 0);
        let attempts = 0;
        function tryFill() {
            attempts++; let filledAny = false;
            if (target === "b" || target === "all") {
                let sB = null, mB = null; const c = document.getElementById('controller');
                if (c) { sB = c.querySelector('#InputSec') || c.querySelector('input:nth-of-type(1)'); mB = c.querySelector('#InputMs') || c.querySelector('input:nth-of-type(2)'); }
                if (!sB) { sB = document.getElementById('InputSec'); mB = document.getElementById('InputMs'); }
                if (sB && mB) { setNativeInputValue(sB, bSec); setNativeInputValue(mB, bMs); filledAny = true; }
            }
            if (target === "a" || (target === "all" && !filledAny)) {
                let sA = document.querySelector('input[placeholder="0-59"]'), mA = document.querySelector('input[placeholder="MS" i]');
                if (!sA || !mA) { sA = document.querySelector('input[max="59"]'); mA = document.querySelector('input[max="999"]'); }
                if (sA && mA) { setNativeInputValue(sA, aSec); setNativeInputValue(mA, aMs); filledAny = true; }
            }
            if (filledAny || attempts >= 15) { sendAck({ type: "slot_ack", tab_id: tabId, command_id: params.command_id || null, success: filledAny, target, sec: target === "b" ? bSec : aSec, ms: target === "b" ? bMs : aMs, url: window.location.href, title: document.title, timestamp: Date.now() }); }
            else setTimeout(tryFill, 150);
        }
        tryFill();
    }

    function executeRefresh(params = {}) {
        const t0 = performance.now(); refreshCount++; let el = null;
        if (params.xpath) try { el = document.evaluate(params.xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; } catch (e) {}
        if (!el && params.text) { const bs = Array.from(document.querySelectorAll("button, a, input[type='button'], input[type='submit']")); const tt = params.text.trim().toLowerCase(); el = bs.find(b => (b.innerText || b.textContent || b.value || "").trim().toLowerCase().includes(tt)); }
        if (!el && params.className) el = document.querySelector(`.${params.className.trim().split(" ").join(".")}`);
        let ok = false, err = null;
        if (el) { try { el.focus(); el.dispatchEvent(new MouseEvent("click", { view: window, bubbles: true, cancelable: true })); if (typeof el.click === "function") el.click(); ok = true; } catch (e) { err = String(e); } }
        else { err = "Target not found."; if (params.reloadFallback) { window.location.reload(); ok = true; } }
        sendAck({ tab_id: tabId, action: "refresh", result: ok ? "Success" : "Failed", duration_ms: Math.round(performance.now() - t0), refresh_count: refreshCount, error: err, url: window.location.href, title: document.title, timestamp: Date.now() });
    }

    let lastThunderCommandId = null;
    function executeThunderConfig(params = {}) {
        const settings = params.settings || {}; lastThunderCommandId = params.command_id || lastThunderCommandId;
        const safe = { region: settings.region || "Spain" }; if (settings.vtData && typeof settings.vtData === "object") safe.vtData = settings.vtData;
        let ok = true, err = null;
        try { const p = { type: "SET_DYNAMIC_STORAGE", data: safe }; window.postMessage(p, "*"); setTimeout(() => { try { window.postMessage(p, "*"); } catch (e) {} }, 300); }
        catch (e) { ok = false; err = String(e); }
        sendAck({ type: "thunder_config_ack", tab_id: tabId, command_id: params.command_id || null, success: ok, confirmed_by_extension: false, error: err, url: window.location.href, title: document.title, timestamp: Date.now() });
    }

    window.addEventListener("message", (ev) => {
        if (ev && ev.data && ev.data.type === "DYNAMIC_STORAGE_SET_CONFIRM") sendAck({ type: "thunder_config_ack", tab_id: tabId, command_id: lastThunderCommandId, confirmed_by_extension: true, success: true, url: window.location.href, title: document.title, timestamp: Date.now() });
    });

    registerWithBackground();
    let lastUrl = window.location.href;
    function checkUrlUpdate() { if (window.location.href !== lastUrl) { lastUrl = window.location.href; try { chrome.runtime.sendMessage({ type: "tab_update", tabId, title: document.title, url: window.location.href }); } catch (e) {} } }
    window.addEventListener("popstate", checkUrlUpdate); window.addEventListener("hashchange", checkUrlUpdate); setInterval(checkUrlUpdate, 4000);
})();
""";

    }
}

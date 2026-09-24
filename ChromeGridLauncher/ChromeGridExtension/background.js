// ===========================================================================
// Chrome Grid Sync Bridge - Background Service Worker (MV3 Relay)
// All networking goes through the service worker to bypass Chrome's
// Private Network Access (PNA) restrictions on content scripts.
// ===========================================================================

const SERVER_PORT = 8765;
const PRIMARY_WS = `ws://127.0.0.1:${SERVER_PORT}/`;
const FALLBACK_WS = `ws://localhost:${SERVER_PORT}/`;
const HTTP_BASE = `http://127.0.0.1:${SERVER_PORT}`;

let socket = null;
let isConnected = false;
let reconnectTimer = null;
const RECONNECT_INTERVAL_MS = 2000;
let currentWsUrl = PRIMARY_WS;

// Track active persistent tab ports (keeps MV3 service worker awake)
const activePorts = new Set();

// Map of Chrome tab IDs -> { tabId, title, url }
const registeredTabs = new Map();

// ─────────────────────────────────────────────────────────────────────────────
// CRITICAL: Top-Level Event Listeners (Registered immediately at script boot)
// ─────────────────────────────────────────────────────────────────────────────

// 1. Message listener (Wakes up service worker when content script pings)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === "wake_worker") {
        if (!isConnected && !socket) {
            connectWs();
        }
        sendResponse({ status: "awake", connected: isConnected });
        return true;
    }
    handleClientMessage(msg, sender.tab?.id, sendResponse);
    return true; // Keep channel open for async response
});

// 2. Port connection listener (Handles long-lived ports from tabs)
chrome.runtime.onConnect.addListener((port) => {
    if (port.name === "cgl_bridge") {
        activePorts.add(port);
        console.log("[ChromeGrid BG] Tab port connected. Active ports:", activePorts.size);

        // Wake WebSocket if disconnected
        if (!isConnected && !socket) {
            connectWs();
        }

        // Send current connection status to tab
        try {
            port.postMessage({ type: "connection_status", connected: isConnected, mode: isConnected ? "websocket" : "none" });
        } catch (e) {}

        port.onMessage.addListener((msg) => {
            if (msg && msg.type === "port_ping") {
                try { port.postMessage({ type: "port_pong" }); } catch (e) {}
                return;
            }
            handleClientMessage(msg, port.sender?.tab?.id);
        });

        port.onDisconnect.addListener(() => {
            activePorts.delete(port);
            console.log("[ChromeGrid BG] Tab port disconnected. Remaining:", activePorts.size);
        });
    }
});

// 3. Tab removed listener
chrome.tabs.onRemoved.addListener((tabId) => {
    registeredTabs.delete(tabId);
});

// 4. On installed / reloaded listener: auto-inject content script into open tabs
chrome.runtime.onInstalled.addListener(async (details) => {
    console.log("[ChromeGrid BG] Extension installed/updated. Reason:", details.reason);
    try {
        const tabs = await chrome.tabs.query({ url: ["http://*/*", "https://*/*"] });
        for (const tab of tabs) {
            if (tab.id != null) {
                try {
                    await chrome.scripting.executeScript({
                        target: { tabId: tab.id, allFrames: true },
                        files: ["content.js"]
                    });
                } catch (e) {
                    // Ignore restricted frames/tabs
                }
            }
        }
    } catch (e) {}
});

// ─────────────────────────────────────────────────────────────────────────────
// Zero-Click Extension Auto-Reload System
// ─────────────────────────────────────────────────────────────────────────────
let isReloading = false;

function triggerExtensionReload(newBuildHash = null) {
    if (isReloading) return;
    isReloading = true;
    console.log("[ChromeGrid BG] Zero-click auto-reload triggered across profile...");
    broadcastToTabs({ type: "extension_reloading" });

    const executeReload = () => {
        setTimeout(() => {
            try {
                chrome.runtime.reload();
            } catch (e) {
                console.error("[ChromeGrid BG] Error invoking chrome.runtime.reload():", e);
            }
        }, 150);
    };

    if (newBuildHash) {
        try {
            chrome.storage.local.set({ active_build_hash: newBuildHash }, executeReload);
        } catch (e) {
            executeReload();
        }
    } else {
        executeReload();
    }
}

function checkBuildHash(serverHash) {
    if (!serverHash || isReloading) return;
    try {
        chrome.storage.local.get(["active_build_hash"], (res) => {
            const localHash = res ? res.active_build_hash : null;
            if (!localHash) {
                chrome.storage.local.set({ active_build_hash: serverHash });
            } else if (localHash !== serverHash) {
                console.log(`[ChromeGrid BG] Extension updated on disk (${localHash} -> ${serverHash}). Auto-reloading...`);
                triggerExtensionReload(serverHash);
            }
        });
    } catch (e) {}
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket Management (single shared connection for ALL tabs in this profile)
// ─────────────────────────────────────────────────────────────────────────────

function connectWs() {
    if (isConnected || socket) return;

    try {
        console.log(`[ChromeGrid BG] Connecting to ${currentWsUrl}...`);
        socket = new WebSocket(currentWsUrl);

        socket.onopen = () => {
            isConnected = true;
            console.log("[ChromeGrid BG] WebSocket connected to server on port", SERVER_PORT);
            broadcastToTabs({ type: "connection_status", connected: true, mode: "websocket" });

            // Send immediate registration hello
            wsSend({
                action: "hello",
                type: "hello",
                tab_id: "chrome_profile_" + Date.now().toString(36),
                title: "Chrome Profile Bridge",
                url: "chrome-extension://relay",
                version: "1.3.2"
            });

            // Re-register all known tabs with the server
            for (const [, info] of registeredTabs) {
                wsSend({
                    action: "hello",
                    type: "tab_init",
                    tab_id: info.tabId,
                    title: info.title,
                    url: info.url,
                    screen_x: 0,
                    screen_y: 0
                });
            }
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const action = (data.action || data.type || "").toLowerCase();

                // Reply to server heartbeat ping immediately
                if (action === "ping" || action === "sync_ping") {
                    wsSend({
                        action: "pong",
                        type: "SYNC_PONG",
                        timestamp: Date.now()
                    });
                    if (data.build_hash) {
                        checkBuildHash(data.build_hash);
                    }
                    return;
                }

                // Heartbeat / ping responses / hello acknowledgment from server: consume quietly, do not broadcast to tabs
                if (action === "hello_ack" || action === "pong" || action === "sync_pong" || action === "noop") {
                    if (data.build_hash) {
                        checkBuildHash(data.build_hash);
                    }
                    return;
                }

                // Zero-click reload extension command from desktop app
                if (action === "reload_extension" || action === "update_extension") {
                    console.log("[ChromeGrid BG] Received reload_extension command from launcher.");
                    triggerExtensionReload(data.build_hash || null);
                    return;
                }

                if (data.build_hash) {
                    checkBuildHash(data.build_hash);
                }

                // Relay commands (slot_click, refresh, hard_reload, thunder_config) to all tabs
                broadcastToTabs({ type: "server_message", data });
            } catch (e) {
                console.warn("[ChromeGrid BG] Failed to parse message:", e);
            }
        };

        socket.onclose = () => {
            cleanupSocket();
            currentWsUrl = (currentWsUrl === PRIMARY_WS) ? FALLBACK_WS : PRIMARY_WS;
            scheduleReconnect();
        };

        socket.onerror = () => {
            cleanupSocket();
            currentWsUrl = (currentWsUrl === PRIMARY_WS) ? FALLBACK_WS : PRIMARY_WS;
            scheduleReconnect();
        };
    } catch (e) {
        cleanupSocket();
        scheduleReconnect();
    }
}

function cleanupSocket() {
    if (socket) {
        try { socket.close(); } catch (e) {}
        socket = null;
    }
    const wasConnected = isConnected;
    isConnected = false;
    if (wasConnected) {
        broadcastToTabs({ type: "connection_status", connected: false, mode: "none" });
    }
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWs();
    }, RECONNECT_INTERVAL_MS);
}

function wsSend(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        try {
            socket.send(JSON.stringify(payload));
            return true;
        } catch (e) {}
    }
    return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Fallback (runs from service worker -> no PNA restrictions)
// ─────────────────────────────────────────────────────────────────────────────

async function httpAck(data) {
    try {
        await fetch(`${HTTP_BASE}/ack`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
    } catch (e) {}
}

async function httpPoll(tabId, title, url) {
    try {
        const pollUrl = `${HTTP_BASE}/poll?tab_id=${encodeURIComponent(tabId)}&title=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`;
        const res = await fetch(pollUrl, { cache: "no-store" });
        if (res.ok) {
            const msg = await res.json();
            if (msg && msg.action && msg.action !== "noop") {
                const act = (msg.action || msg.type || "").toLowerCase();
                if (act === "reload_extension" || act === "update_extension") {
                    triggerExtensionReload(msg.build_hash || null);
                    return null;
                }
                if (act === "pong" || act === "sync_pong" || act === "noop") {
                    return null;
                }
                if (msg.build_hash) {
                    checkBuildHash(msg.build_hash);
                }
                return msg;
            }
        }
    } catch (e) {}
    return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab Communication (service worker -> content scripts)
// ─────────────────────────────────────────────────────────────────────────────

function broadcastToTabs(message) {
    // 1. Relay through all active long-lived ports
    for (const port of activePorts) {
        try { port.postMessage(message); } catch (e) {}
    }

    // 2. Relay via chrome.tabs.sendMessage with lastError consumption
    try {
        chrome.tabs.query({}, (tabs) => {
            if (tabs) {
                for (const t of tabs) {
                    if (t.id != null) {
                        try {
                            chrome.tabs.sendMessage(t.id, message, () => {
                                const _ = chrome.runtime.lastError;
                            });
                        } catch (e) {}
                    }
                }
            }
        });
    } catch (e) {}
}

function handleClientMessage(msg, chromeTabId, sendResponse = null) {
    if (!msg || !msg.type) return;

    // Wake WebSocket if not connected
    if (!isConnected && !socket) {
        connectWs();
    }

    switch (msg.type) {
        case "register_tab": {
            if (chromeTabId != null) {
                registeredTabs.set(chromeTabId, {
                    tabId: msg.tabId,
                    title: msg.title || "",
                    url: msg.url || "",
                    pageType: msg.pageType || "",
                    hasInputs: msg.hasInputs || false
                });
            }

            const initPayload = {
                action: "hello",
                type: "tab_init",
                tab_id: msg.tabId,
                title: msg.title || "",
                url: msg.url || "",
                page_type: msg.pageType || "",
                has_inputs: msg.hasInputs || false,
                screen_x: msg.screen_x || 0,
                screen_y: msg.screen_y || 0
            };

            if (!wsSend(initPayload)) {
                httpPoll(msg.tabId, msg.title || "", msg.url || "").then(data => {
                    if (data) {
                        broadcastToTabs({ type: "server_message", data });
                    }
                });
            }

            if (sendResponse) sendResponse({ connected: isConnected });
            break;
        }

        case "ack":
        case "slot_ack":
        case "thunder_config_ack":
        case "refresh_ack": {
            if (!wsSend(msg)) {
                httpAck(msg);
            }
            if (sendResponse) sendResponse({ ok: true });
            break;
        }

        case "send_payload": {
            const payload = msg.payload || msg;
            if (!wsSend(payload)) {
                if (payload && (payload.type === "ack" || payload.type === "slot_ack" ||
                    payload.type === "thunder_config_ack" || payload.type === "pong" ||
                    payload.action === "refresh")) {
                    httpAck(payload);
                }
            }
            if (sendResponse) sendResponse({ ok: true });
            break;
        }

        case "tab_update": {
            if (chromeTabId != null && registeredTabs.has(chromeTabId)) {
                const info = registeredTabs.get(chromeTabId);
                info.title = msg.title || info.title;
                info.url = msg.url || info.url;
            }
            wsSend({
                action: "hello",
                type: "tab_update",
                tab_id: msg.tabId,
                title: msg.title || "",
                url: msg.url || ""
            });
            break;
        }

        case "get_status": {
            if (sendResponse) sendResponse({ connected: isConnected });
            break;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Continuous Keepalive & Heartbeat
// ─────────────────────────────────────────────────────────────────────────────

// Heartbeat every 10 seconds: keeps WebSocket and Service Worker alive
setInterval(() => {
    if (isConnected && socket && socket.readyState === WebSocket.OPEN) {
        wsSend({ action: "ping", type: "ping", timestamp: Date.now() });
    } else if (!isConnected && !socket) {
        connectWs();
    }
}, 10000);

// Chrome alarm backup (wakes up worker every 30 seconds if dormant)
try {
    chrome.alarms.create("cgl_keepalive", { periodInMinutes: 0.5 });
    chrome.alarms.onAlarm.addListener((alarm) => {
        if (alarm.name === "cgl_keepalive") {
            if (!isConnected && !socket) {
                connectWs();
            }
        }
    });
} catch (e) {}

// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────

connectWs();
console.log("[ChromeGrid BG v1.3.2] Background service worker initialized. Robust relay active.");

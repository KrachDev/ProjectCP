// ===========================================================================
// Chrome Grid Sync Bridge - Content Script (Native Extension)
// 100% Stealth, Zero-Install, Zero-Proxy Architecture
// Supports Top-Level Windows + Nested Frames (#controller / #InputSec)
// ===========================================================================

(() => {
    // ---------------------------------------------------------------------------
    // Frame Guard: Run in top-level window OR if this subframe contains slot inputs
    // ---------------------------------------------------------------------------
    const isTop = window.top === window.self;
    const isControllerFrame = !isTop && !!(
        document.getElementById('controller') ||
        document.getElementById('InputSec') ||
        document.getElementById('btnToggleSec') ||
        (window.location.href && window.location.href.includes("favicon.png"))
    );

    // If subframe is not a controller frame, ignore it
    if (!isTop && !isControllerFrame) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", () => {
                if (document.getElementById('controller') || document.getElementById('InputSec')) {
                    initBridge();
                }
            }, { once: true });
        }
        return;
    }

    initBridge();

    function initBridge() {
        if (window.__chromeGridSyncBridgeLoaded) {
            if (window.__cglCleanup) {
                try { window.__cglCleanup(); } catch (e) {}
            }
        }
        window.__chromeGridSyncBridgeLoaded = true;

        // Verify extension context is valid
        if (!chrome.runtime || !chrome.runtime.id) {
            console.warn("[ChromeGrid Extension] Extension context not available. Please refresh the page.");
            return;
        }

        // Generate or reuse persistent Tab ID for this session
        let tabId = "";
        try {
            tabId = sessionStorage.getItem("__cgl_tab_id") || "";
        } catch (e) {}

        if (!tabId) {
            tabId = "tab_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 7);
            try {
                sessionStorage.setItem("__cgl_tab_id", tabId);
            } catch (e) {}
        }

        let isConnected = false;
        let refreshCount = 0;
        let badgeEl = null;
        let isWaitingForBody = false;
        console.log(`[ChromeGrid Extension v1.3.3] Bridge active for Tab ID: ${tabId} (top: ${isTop})`);

        // ---------------------------------------------------------------------------
        // Visual Status Badge (Only rendered in top window)
        // ---------------------------------------------------------------------------
        function updateBadge(status, text, bg) {
            if (!isTop) return;

            if (!document.body) {
                if (!isWaitingForBody) {
                    isWaitingForBody = true;
                    window.addEventListener("DOMContentLoaded", () => {
                        isWaitingForBody = false;
                        updateBadge(status, text, bg);
                    }, { once: true });
                }
                return;
            }

            if (!badgeEl) {
                badgeEl = document.getElementById("__cgl_status_badge");
            }
            if (!badgeEl) {
                badgeEl = document.createElement("div");
                badgeEl.id = "__cgl_status_badge";
                badgeEl.style.cssText = `
                    position: fixed;
                    bottom: 6px;
                    right: 6px;
                    z-index: 2147483647;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 3px 6px;
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    cursor: pointer;
                    user-select: none;
                    opacity: 0.85;
                    pointer-events: auto;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    transition: all 0.2s ease;
                `;
                badgeEl.title = "Chrome Grid Sync Bridge • Click to minimize";
                badgeEl.addEventListener("click", () => {
                    badgeEl.style.opacity = badgeEl.style.opacity === "0.2" ? "0.85" : "0.2";
                });
                document.body.appendChild(badgeEl);
            }

            badgeEl.style.background = bg || "#1E293B";
            badgeEl.style.color = "#F8FAFC";
            badgeEl.innerHTML = `<span style="font-size: 7px;">●</span> ${text}`;
        }

        // ---------------------------------------------------------------------------
        // Page Detection Helpers (Page A vs Page B)
        // ---------------------------------------------------------------------------
        function isSlotPageA() {
            const title = (document.title || "").toLowerCase();
            const href = (window.location.href || "").toLowerCase();
            if (title.includes("too many requests") || title.includes("recaptcha") || title.includes("captcha") || title.includes("login")) {
                return false;
            }
            if (document.getElementById('controller') || document.getElementById('InputSec') || document.getElementById('btnToggleSec') || href.includes("favicon.png")) {
                return false;
            }
            if (title.includes("visa type") || title.includes("visatype")) {
                return false;
            }
            if (href.includes("slotselection") ||
                href.includes("slot-selection") ||
                href.includes("slot_selection") ||
                href.includes("calendar") ||
                title.includes("slot selection") ||
                title.includes("calendar")) {
                return true;
            }
            try {
                if (document.querySelector('input[placeholder="0-59"], input[placeholder*="0-59"]') ||
                    document.querySelector('body > div:nth-child(7) > div:nth-child(2) > div > input:nth-child(2)')) {
                    return true;
                }
            } catch (e) {}
            return false;
        }

        function isSlotPageB() {
            const title = (document.title || "").toLowerCase();
            const href = (window.location.href || "").toLowerCase();
            if (title.includes("too many requests") || title.includes("recaptcha") || title.includes("captcha") || title.includes("login")) {
                return false;
            }
            if (document.getElementById('controller') || document.getElementById('InputSec') || document.getElementById('InputMs') || document.getElementById('btnToggleSec')) {
                return true;
            }
            if (href.includes("favicon.png") || href.includes("favicon")) {
                return true;
            }
            if (title.includes("visa type") ||
                title.includes("visatype") ||
                href.includes("visatype") ||
                href.includes("visa-type") ||
                href.includes("visa_type")) {
                return true;
            }
            return false;
        }

        // ---------------------------------------------------------------------------
        // Background Sync & Tab Registration (Zero Port Disconnect Loop)
        // ---------------------------------------------------------------------------
        function syncWithBackground() {
            if (!chrome.runtime || !chrome.runtime.id) {
                updateBadge("error", "Extension Reloaded — Press F5", "#B91C1C");
                return;
            }

            const inputs = findSlotInputs();
            let pageType = "other";
            try {
                if (typeof isSlotPageA === "function" && isSlotPageA()) {
                    pageType = "a";
                } else if (typeof isSlotPageB === "function" && isSlotPageB()) {
                    pageType = "b";
                }
            } catch (e) {}
            if (pageType === "other" && inputs && inputs.page && inputs.page !== "unknown") {
                pageType = inputs.page;
            }
            const hasInputs = !!(inputs.secEl && inputs.msEl);

            try {
                chrome.runtime.sendMessage({
                    type: "register_tab",
                    tabId: tabId,
                    title: document.title || "Chrome Tab",
                    url: window.location.href,
                    pageType: pageType,
                    hasInputs: hasInputs,
                    screen_x: window.screenX || window.screenLeft || 0,
                    screen_y: window.screenY || window.screenTop || 0
                }, (resp) => {
                    const _ = chrome.runtime.lastError;
                    if (resp && resp.connected) {
                        isConnected = true;
                        updateBadge("connected", "Grid Sync: Connected", "#047857");
                    } else {
                        updateBadge("waiting", "Grid Sync: Waiting...", "#D97706");
                    }
                });
            } catch (e) {
                updateBadge("waiting", "Grid Sync: Connecting...", "#D97706");
            }
        }

        function sendPayload(obj) {
            try {
                chrome.runtime.sendMessage({ type: "send_payload", payload: obj }, () => {
                    const _ = chrome.runtime.lastError;
                });
                return true;
            } catch (e) {
                return false;
            }
        }

        function sendAck(ackData) {
            try {
                chrome.runtime.sendMessage({ type: "ack", ...ackData }, () => {
                    const _ = chrome.runtime.lastError;
                });
            } catch (e) {}
        }

        // Listen for broadcasts relayed from background service worker
        chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
            if (!msg) return;
            if (msg.type === "extension_reloading") {
                updateBadge("reloading", "Grid Sync: Reloading...", "#2563EB");
                if (sendResponse) sendResponse({ ok: true });
                return;
            }

            if (msg.type === "connection_status") {
                isConnected = msg.connected;
                updateBadge(isConnected ? "connected" : "waiting",
                    isConnected ? "Grid Sync: Connected" : "Grid Sync: Waiting...",
                    isConnected ? "#047857" : "#D97706");
                if (sendResponse) sendResponse({ ok: true });
                return;
            }

            if (msg.type === "server_message" && msg.data) {
                handleServerMessage(msg.data);
            } else if (msg.action) {
                handleServerMessage(msg);
            }

            if (sendResponse) sendResponse({ received: true });
        });

        // Initial sync and periodic keepalive
        syncWithBackground();
        const keepaliveInterval = setInterval(syncWithBackground, 10000);

        // ---------------------------------------------------------------------------
        // Message Dispatcher
        // ---------------------------------------------------------------------------
        function handleServerMessage(data) {
            if (!data) return;
            const action = (data.action || data.type || "").toLowerCase();

            switch (action) {
                case "click_refresh":
                case "refresh":
                case "trigger_refresh":
                    executeRefresh(data);
                    break;

                case "hard_reload":
                case "reload":
                    console.log("[ChromeGrid Extension] Executing hard reload.");
                    window.location.reload(true);
                    break;

                case "slot_click":
                    executeSlotClick(data);
                    break;

                case "thunder_config":
                    executeThunderConfig(data);
                    break;

                case "ping":
                case "sync_ping":
                    sendPayload({
                        type: "pong",
                        action: "pong",
                        tab_id: tabId,
                        timestamp: Date.now()
                    });
                    break;

                case "hello_ack":
                case "hello":
                case "tab_init":
                case "ack":
                case "pong":
                case "sync_pong":
                case "port_pong":
                case "port_ping":
                case "noop":
                    // Quietly consume internal heartbeat & registration acknowledgments
                    break;

                default:
                    console.log("[ChromeGrid Extension] Unknown action received:", action);
            }
        }

        // ---------------------------------------------------------------------------
        // Slot Input Finding & Dispatching (Page A vs Page B)
        // ---------------------------------------------------------------------------
        function setNativeInputValue(el, value) {
            if (!el) return false;
            const strVal = String(value);

            try { el.focus(); } catch (e) {}

            try {
                const tracker = el._valueTracker;
                if (tracker) tracker.setValue(el.value + "_prev");
            } catch (e) {}

            let protoSuccess = false;
            try {
                const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (descriptor && descriptor.set) {
                    descriptor.set.call(el, strVal);
                    protoSuccess = true;
                }
            } catch (e) {}

            if (!protoSuccess) {
                try { el.value = strVal; } catch (e) {}
            }

            try { el.value = strVal; } catch (e) {}
            try { el.setAttribute("value", strVal); } catch (e) {}

            try {
                el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
            } catch (e) {}
            return true;
        }

        function findSlotInputs(targetHint) {
            const tgt = (targetHint || "").toLowerCase();

            // PRIORITY 1: Check for Page B inputs inside #controller or direct (#InputSec & #InputMs)
            if (tgt === "b" || tgt === "all" || !tgt) {
                try {
                    const ctrl = document.getElementById('controller');
                    if (ctrl) {
                        const s = ctrl.querySelector('#InputSec') || ctrl.querySelector('input:nth-of-type(1)');
                        const m = ctrl.querySelector('#InputMs') || ctrl.querySelector('input:nth-of-type(2)');
                        if (s && m) {
                            return { secEl: s, msEl: m, strategy: "controller_parent_div", page: "b" };
                        }
                    }
                } catch (e) {}

                try {
                    const s = document.getElementById('InputSec');
                    const m = document.getElementById('InputMs');
                    if (s && m) {
                        return { secEl: s, msEl: m, strategy: "id_inputsec_page_b", page: "b" };
                    }
                } catch (e) {}
            }

            // PRIORITY 2: Check for Page A inputs (Calendar / SlotSelection)
            if (tgt === "a" || tgt === "all" || !tgt) {
                try {
                    const s = document.querySelector('input[placeholder="0-59"], input[placeholder*="0-59"]');
                    const m = document.querySelector('input[placeholder="MS" i], input[placeholder="ms"], input[placeholder*="MS" i]');
                    if (s && m) {
                        return { secEl: s, msEl: m, strategy: "placeholder_exact_page_a", page: "a" };
                    }
                } catch (e) {}

                try {
                    const s = document.querySelector('body > div:nth-child(7) > div:nth-child(2) > div > input:nth-child(2)') ||
                              document.querySelector('body > div:nth-child(6) > div:nth-child(2) > div > input:nth-child(2)') ||
                              document.querySelector('body > div:nth-child(5) > div:nth-child(2) > div > input:nth-child(2)') ||
                              document.querySelector('body > div:nth-child(8) > div:nth-child(2) > div > input:nth-child(2)');
                    const m = document.querySelector('body > div:nth-child(7) > div:nth-child(2) > div > input:nth-child(3)') ||
                              document.querySelector('body > div:nth-child(6) > div:nth-child(2) > div > input:nth-child(3)') ||
                              document.querySelector('body > div:nth-child(5) > div:nth-child(2) > div > input:nth-child(3)') ||
                              document.querySelector('body > div:nth-child(8) > div:nth-child(2) > div > input:nth-child(3)');
                    if (s && m) {
                        return { secEl: s, msEl: m, strategy: "dom_hierarchy_page_a", page: "a" };
                    }
                } catch (e) {}
            }

            // PRIORITY 3: Inputs with max="59" & max="999"
            if (tgt !== "b") {
                try {
                    const s = document.querySelector('input[type="number"][max="59"], input[max="59"].form-control, input[max="59"]');
                    const m = document.querySelector('input[type="number"][max="999"], input[max="999"].form-control, input[max="999"]');
                    if (s && m) {
                        return { secEl: s, msEl: m, strategy: "attr_max_59_999", page: "a" };
                    }
                } catch (e) {}
            }

            // PRIORITY 4: Partial id match
            try {
                const s = document.querySelector('input[id*="sec" i], input[name*="sec" i]');
                const m = document.querySelector('input[id*="ms" i], input[name*="ms" i]');
                if (s && m && s !== m) {
                    return { secEl: s, msEl: m, strategy: "id_partial_sec_ms", page: tgt === "b" ? "b" : "a" };
                }
            } catch (e) {}

            return { secEl: null, msEl: null, strategy: "none", page: "unknown" };
        }

        function executeSlotClick(params = {}) {
            const target = (params.target || "all").toLowerCase();
            const aSec = params.page_a_sec !== undefined ? params.page_a_sec : (params.sec || 0);
            const aMs  = params.page_a_ms !== undefined ? params.page_a_ms : (params.ms || 0);
            const bSec = params.page_b_sec !== undefined ? params.page_b_sec : (params.sec || 0);
            const bMs  = params.page_b_ms !== undefined ? params.page_b_ms : (params.ms || 0);

            const t0 = performance.now();
            let attempts = 0;
            const maxAttempts = 20;

            function tryFill() {
                attempts++;
                const found = findSlotInputs(target);

                if (found.secEl && found.msEl) {
                    const secVal = (found.page === "b" || target === "b") ? bSec : aSec;
                    const msVal  = (found.page === "b" || target === "b") ? bMs : aMs;

                    const okSec = setNativeInputValue(found.secEl, secVal);
                    const okMs  = setNativeInputValue(found.msEl, msVal);
                    const ok = okSec && okMs;
                    const durationMs = Math.round(performance.now() - t0);

                    updateBadge("connected", `Slot Synced: ${secVal}s / ${msVal}ms`, "#047857");

                    sendAck({
                        type: "slot_ack",
                        action: "slot_ack",
                        tab_id: tabId,
                        command_id: params.command_id || null,
                        result: ok ? "Success" : "Failed",
                        success: ok,
                        target: target,
                        sec: secVal,
                        ms: msVal,
                        strategy: found.strategy,
                        duration_ms: durationMs,
                        url: window.location.href,
                        title: document.title,
                        timestamp: Date.now()
                    });
                    console.log(`[ChromeGrid Extension] Slot synced successfully via ${found.strategy}: Sec=${secVal}, MS=${msVal}`);
                } else if (attempts < maxAttempts) {
                    setTimeout(tryFill, 150);
                } else {
                    console.warn(`[ChromeGrid Extension] Slot inputs not found after ${maxAttempts} attempts for target: ${target}`);
                    sendAck({
                        type: "slot_ack",
                        action: "slot_ack",
                        tab_id: tabId,
                        command_id: params.command_id || null,
                        result: "Failed",
                        success: false,
                        target: target,
                        error: `Slot inputs not found on page ('${document.title}')`,
                        duration_ms: Math.round(performance.now() - t0),
                        url: window.location.href,
                        title: document.title,
                        timestamp: Date.now()
                    });
                }
            }

            tryFill();
        }

        // ---------------------------------------------------------------------------
        // Safety Guard: Elements that MUST NEVER be clicked
        // ---------------------------------------------------------------------------
        function isForbiddenTarget(el) {
            if (!el || el.nodeType !== Node.ELEMENT_NODE) return true;
            const id = (el.id || "").toLowerCase();
            const text = (el.innerText || el.textContent || el.value || "").trim().toLowerCase();
            const cls = (el.className || "").toString().toLowerCase();

            // Strictly forbid external redirect toggles and non-refresh launcher controls
            if (id === "toggle-redirect" || id.includes("redirect") || id.includes("toggle-red") || id.includes("autoredirect")) {
                return true;
            }
            if (text.includes("auto redirect") || text.includes("enable auto redirect") || text.includes("disable auto redirect")) {
                return true;
            }
            if (cls.includes("redirect") || cls.includes("toggle-redirect")) {
                return true;
            }
            // Forbid navigational links to prevent leaving the page
            if (el.tagName === "A") {
                const href = (el.getAttribute("href") || "").trim();
                if (href && !href.startsWith("#") && !href.startsWith("javascript:") && (href.startsWith("http") || href.startsWith("/"))) {
                    return true;
                }
            }
            return false;
        }

        // ---------------------------------------------------------------------------
        // Refresh Command Execution
        // ---------------------------------------------------------------------------
        function executeRefresh(params = {}) {
            const t0 = performance.now();
            refreshCount++;
            let targetEl = null;

            if (params.xpath) {
                const rawXp = params.xpath.trim().toLowerCase();
                if (rawXp.includes("div[4]/div[4]/button") || rawXp.includes("toggle-redirect") || rawXp.includes("redirect")) {
                    console.warn("[ChromeGrid Extension] Rejected dangerous XPath targeting redirect toggle:", params.xpath);
                } else {
                    try {
                        const result = document.evaluate(params.xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        if (result && result.singleNodeValue && !isForbiddenTarget(result.singleNodeValue)) {
                            targetEl = result.singleNodeValue;
                        } else if (result && result.singleNodeValue && isForbiddenTarget(result.singleNodeValue)) {
                            console.warn("[ChromeGrid Extension] XPath resolved to forbidden target (e.g. redirect button). Skipping XPath:", result.singleNodeValue);
                        }
                    } catch (e) {}
                }
            }

            if (!targetEl && params.text) {
                const candidates = Array.from(document.querySelectorAll("button, a, input[type='button'], input[type='submit']"));
                const targetText = params.text.trim().toLowerCase();
                targetEl = candidates.find(el => {
                    if (isForbiddenTarget(el)) return false;
                    const text = (el.innerText || el.textContent || el.value || "").trim().toLowerCase();
                    return text.includes(targetText);
                });
            }

            if (!targetEl && params.class_name) {
                try {
                    const selector = `.${params.class_name.trim().split(" ").join(".")}`;
                    const el = document.querySelector(selector);
                    if (el && !isForbiddenTarget(el)) {
                        targetEl = el;
                    }
                } catch (e) {}
            }

            // Safe Fallback: Search for legitimate "Refresh" button in DOM that is NOT forbidden
            if (!targetEl) {
                try {
                    const allButtons = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], .btn"));
                    targetEl = allButtons.find(b => {
                        if (isForbiddenTarget(b)) return false;
                        const txt = (b.innerText || b.textContent || b.value || "").trim().toLowerCase();
                        const id = (b.id || "").toLowerCase();
                        return (txt === "refresh" || txt.includes("refresh") || id.includes("refresh") || id === "btnrefresh");
                    });
                } catch (e) {}
            }

            let success = false;
            let err = null;

            if (targetEl && !isForbiddenTarget(targetEl)) {
                try {
                    targetEl.focus();
                    targetEl.dispatchEvent(new MouseEvent("click", { view: window, bubbles: true, cancelable: true }));
                    if (typeof targetEl.click === "function") targetEl.click();
                    success = true;
                } catch (e) {
                    err = String(e);
                }
            } else {
                err = "Target refresh element not found in DOM (or was rejected as forbidden redirect button).";
                if (params.reloadFallback) {
                    window.location.reload();
                    success = true;
                }
            }

            const durationMs = Math.round(performance.now() - t0);

            sendAck({
                type: "refresh_ack",
                action: "refresh_ack",
                tab_id: tabId,
                command_id: params.command_id || null,
                result: success ? "Success" : "Failed",
                duration_ms: durationMs,
                refresh_count: refreshCount,
                error: err,
                url: window.location.href,
                title: document.title,
                timestamp: Date.now()
            });

            if (isTop) {
                updateBadge("refreshing", success ? `Refreshed #${refreshCount}` : "Refresh Failed", success ? "#2563EB" : "#B91C1C");
                setTimeout(() => {
                    updateBadge(isConnected ? "connected" : "waiting",
                        isConnected ? "Grid Sync: Connected" : "Grid Sync: Waiting...",
                        isConnected ? "#047857" : "#D97706");
                }, 1200);
            }
        }

        // ---------------------------------------------------------------------------
        // ThunderBolt Dynamic Storage Sync
        // ---------------------------------------------------------------------------
        let lastThunderCommandId = null;

        function executeThunderConfig(params = {}) {
            const settings = params.settings || params.config || params;
            lastThunderCommandId = params.command_id || lastThunderCommandId;

            const region = settings.region || settings.Region || params.region || params.Region || "Spain";
            const rawVt = settings.vtData || settings.VtData || params.vtData || params.VtData || {};

            const safeData = {
                region: region,
                vtData: {
                    city: rawVt.city || rawVt.City || "",
                    category: rawVt.category || rawVt.Category || "Normal",
                    type: rawVt.type || rawVt.Type || "",
                    members: Number(rawVt.members || rawVt.Members || 1)
                }
            };

            let ok = true;
            let err = null;
            try {
                const payload = { type: "SET_DYNAMIC_STORAGE", data: safeData };

                // Dispatch to current window
                window.postMessage(payload, "*");

                // Dispatch to top window if inside frame
                try {
                    if (window.top && window.top !== window) {
                        window.top.postMessage(payload, "*");
                    }
                } catch (e) {}

                // Dispatch to all nested child frames
                try {
                    for (let i = 0; i < window.frames.length; i++) {
                        window.frames[i].postMessage(payload, "*");
                    }
                } catch (e) {}

                // Brief delayed retry for dynamic frames that mount late
                setTimeout(() => {
                    try {
                        window.postMessage(payload, "*");
                        if (window.top && window.top !== window) {
                            window.top.postMessage(payload, "*");
                        }
                        for (let i = 0; i < window.frames.length; i++) {
                            window.frames[i].postMessage(payload, "*");
                        }
                    } catch (e) {}
                }, 300);
            } catch (e) {
                ok = false;
                err = String(e);
            }

            sendAck({
                type: "thunder_config_ack",
                action: "thunder_config_ack",
                tab_id: tabId,
                command_id: params.command_id || null,
                success: ok,
                confirmed_by_extension: false,
                error: err,
                url: window.location.href,
                title: document.title,
                timestamp: Date.now()
            });
        }

        window.addEventListener("message", (ev) => {
            if (ev && ev.data && ev.data.type === "DYNAMIC_STORAGE_SET_CONFIRM") {
                sendAck({
                    type: "thunder_config_ack",
                    action: "thunder_config_ack",
                    tab_id: tabId,
                    command_id: lastThunderCommandId,
                    confirmed_by_extension: true,
                    success: true,
                    url: window.location.href,
                    title: document.title,
                    timestamp: Date.now()
                });
            }
        });

        // ---------------------------------------------------------------------------
        // Boot & Periodic Watchers
        // ---------------------------------------------------------------------------
        // URL Change Watcher
        let lastUrl = window.location.href;
        function checkUrlUpdate() {
            if (window.location.href !== lastUrl) {
                lastUrl = window.location.href;
                sendPayload({
                    type: "tab_update",
                    tabId: tabId,
                    title: document.title,
                    url: window.location.href
                });
            }
        }
        window.addEventListener("popstate", checkUrlUpdate);
        window.addEventListener("hashchange", checkUrlUpdate);
        const urlCheckInterval = setInterval(checkUrlUpdate, 3000);

        window.__cglCleanup = () => {
            if (keepaliveInterval) clearInterval(keepaliveInterval);
            if (urlCheckInterval) clearInterval(urlCheckInterval);
            window.removeEventListener("popstate", checkUrlUpdate);
            window.removeEventListener("hashchange", checkUrlUpdate);
        };
    }
})();

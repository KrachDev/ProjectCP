// ==UserScript==
// @name         Chrome Grid - Remote Refresh Listener & BLS Turbo Optimizer
// @namespace    https://github.com/chromegridlauncher
// @version      1.8.9
// @description  High-concurrency listener for 50+ Chrome profiles on BLS Visa portals. Automatically clicks Refresh and synchronizes slot inputs without interfering with page styles or date pickers.
// @author       Chrome Grid Launcher
// @match        *://*/*
// @updateURL    http://127.0.0.1:8765/userscript.user.js
// @downloadURL  http://127.0.0.1:8765/userscript.user.js
// @grant        GM_xmlhttpRequest
// @grant        GM_openInTab
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ---------------------------------------------------------------------------
    // Environment & URL Validation Guard
    // ---------------------------------------------------------------------------
    // 1. FRAME GUARD: Never run inside standard tracking frames, but ALWAYS run if top window or if frame contains #controller or favicon.png
    if (window.top !== window.self) {
        const isControllerFrame = !!(
            document.getElementById('controller') ||
            document.getElementById('InputSec') ||
            document.getElementById('btnToggleSec') ||
            window.location.href.includes("favicon.png")
        );
        if (!isControllerFrame) {
            return;
        }
    }

    // 2. SINGLETON INSTANCE LOCK: Prevent duplicate userscripts from running concurrently in the same tab
    const SCRIPT_VERSION = 189;
    const win = (typeof unsafeWindow !== "undefined" && unsafeWindow) ? unsafeWindow : window;
    if (win.__cgl_active_version && win.__cgl_active_version >= SCRIPT_VERSION) {
        console.warn(`[ChromeGrid] Instance v${win.__cgl_active_version} is already active on this tab. Halting duplicate.`);
        return;
    }
    win.__cgl_active_version = SCRIPT_VERSION;

    // 3. Protocol and origin guards
    const currentProto = window.location.protocol;
    if (currentProto.startsWith("chrome") ||
        currentProto.startsWith("moz") ||
        currentProto.startsWith("about") ||
        currentProto.startsWith("edge") ||
        (window.location.hostname === "127.0.0.1" && window.location.port === "8765")) {
        return;
    }

    // 4. Media/document guard: NEVER ignore the BLS favicon.png controller app!
    const isFaviconControllerApp = window.location.href.includes("favicon.png") ||
                                   !!(document.getElementById('controller') || document.getElementById('InputSec'));
    if (!isFaviconControllerApp) {
        if (window.location.pathname.match(/\.(jpe?g|gif|svg|ico|webp|pdf)$/i)) {
            return;
        }
        if (document.contentType && !document.contentType.includes("html")) {
            return;
        }
    }

    // ---------------------------------------------------------------------------
    // Configuration
    // ---------------------------------------------------------------------------
    const WS_SERVER_URL = "ws://127.0.0.1:8765";
    const HTTP_SERVER_URL = "http://127.0.0.1:8765";
    const RECONNECT_INTERVAL_MS = 3000;
    const HEARTBEAT_INTERVAL_MS = 15000;

    // Default target selector specs (matching the requested Refresh button)
    // XPath: /html/body/div[5]/div[1]/button[1]
    // Text: Refresh | Class: btn btn-primary
    const DEFAULT_XPATH = "/html/body/div[5]/div[1]/button[1]";
    const DEFAULT_TEXT = "Refresh";
    const DEFAULT_CLASS = "btn btn-primary";

    // Unique tab identifier
    const TAB_ID = "tab_" + Math.random().toString(36).substring(2, 9) + "_" + Date.now().toString(36);

    let socket = null;
    let reconnectTimer = null;
    let heartbeatTimer = null;
    let isConnected = false;
    let connectionMode = "pending"; // "websocket" | "polling"
    let pollActive = false;
    let pollFailures = 0;
    let pendingAck = null;

    // ---------------------------------------------------------------------------
    // Status Indicator Badge (subtle in bottom-right corner)
    // ---------------------------------------------------------------------------
    let badgeEl = null;

    function createStatusBadge() {
        if (badgeEl || !document.body) return;

        badgeEl = document.createElement("div");
        badgeEl.id = "cgl-refresh-badge";
        badgeEl.setAttribute("title", "Chrome Grid: Connecting to Desktop App...");
        badgeEl.style.cssText = `
            position: fixed;
            bottom: 6px;
            right: 6px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: #f59e0b;
            border: 1px solid rgba(0, 0, 0, 0.4);
            box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
            z-index: 2147483647;
            cursor: pointer;
            transition: all 0.3s ease;
            opacity: 0.7;
        `;

        badgeEl.addEventListener("mouseenter", () => {
            badgeEl.style.opacity = "1";
            badgeEl.style.transform = "scale(1.3)";
        });

        badgeEl.addEventListener("mouseleave", () => {
            badgeEl.style.opacity = "0.7";
            badgeEl.style.transform = "scale(1.0)";
        });

        badgeEl.addEventListener("click", () => {
            alert(
                `[Chrome Grid Refresh Listener]\n` +
                `Status: ${isConnected ? "Connected 🟢" : "Disconnected 🔴"}\n` +
                `Mode: ${connectionMode.toUpperCase()}\n` +
                `Tab ID: ${TAB_ID}\n` +
                `Target XPath: ${DEFAULT_XPATH}\n` +
                `Target Class: ${DEFAULT_CLASS}\n` +
                `Target Text: ${DEFAULT_TEXT}`
            );
        });

        document.body.appendChild(badgeEl);
    }

    function updateBadge(status) {
        if (!badgeEl) createStatusBadge();
        if (!badgeEl) return;

        if (status === "connected") {
            badgeEl.style.backgroundColor = "#10b981"; // green
            badgeEl.setAttribute("title", `Chrome Grid: Connected to Desktop App (${connectionMode.toUpperCase()})`);
        } else if (status === "refreshing") {
            badgeEl.style.backgroundColor = "#3b82f6"; // blue pulse
            badgeEl.setAttribute("title", "Chrome Grid: Refresh button clicked!");
            setTimeout(() => updateBadge(isConnected ? "connected" : "disconnected"), 1000);
        } else {
            badgeEl.style.backgroundColor = "#ef4444"; // red
            badgeEl.setAttribute("title", "Chrome Grid: Reconnecting to Desktop App...");
        }
    }

    // ---------------------------------------------------------------------------
    // Target Button Finder & Execution Logic
    // ---------------------------------------------------------------------------
    function isElementClickable(el) {
        if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
        const tag = el.tagName.toUpperCase();
        if (tag === "BUTTON") return true;
        if (tag === "INPUT" && ["button", "submit"].includes((el.type || "").toLowerCase())) return true;
        if (el.getAttribute("role") === "button") return true;
        if (tag === "A") {
            // Allow anchor styled as button if not navigating away
            const href = (el.getAttribute("href") || "").trim();
            return !href || href.startsWith("#") || href.startsWith("javascript:");
        }
        return false;
    }

    function findTargetButton(xpath = DEFAULT_XPATH, targetText = DEFAULT_TEXT, targetClass = DEFAULT_CLASS) {
        // Attempt 1: Direct specified XPath (e.g. /html/body/div[5]/div[1]/button[1])
        try {
            const result = document.evaluate(
                xpath,
                document,
                null,
                XPathResult.FIRST_ORDERED_NODE_TYPE,
                null
            );
            if (result && result.singleNodeValue && isElementClickable(result.singleNodeValue)) {
                return { element: result.singleNodeValue, strategy: "xpath_exact", path: xpath };
            }
        } catch (e) {
            // Evaluator error fallback
        }

        // Attempt 2: Flexible div position check for retrier toolbar (e.g. /html/body/div[any]/div[1]/button[1])
        try {
            const result = document.evaluate(
                "//body/div[position()>=3]/div[1]//button[contains(normalize-space(.), 'Refresh') or @id='btnRefresh']",
                document,
                null,
                XPathResult.FIRST_ORDERED_NODE_TYPE,
                null
            );
            if (result && result.singleNodeValue && isElementClickable(result.singleNodeValue)) {
                return { element: result.singleNodeValue, strategy: "xpath_flexible_retrier" };
            }
        } catch (e) {}

        // Attempt 3: Button in div 5 > div 1 with text "Refresh"
        try {
            const result = document.evaluate(
                "//div[5]/div[1]//button[contains(normalize-space(.), 'Refresh')]",
                document,
                null,
                XPathResult.FIRST_ORDERED_NODE_TYPE,
                null
            );
            if (result && result.singleNodeValue && isElementClickable(result.singleNodeValue)) {
                return { element: result.singleNodeValue, strategy: "xpath_div5_button" };
            }
        } catch (e) {}

        // Attempt 4: Strict match on BUTTON/INPUT element with class "btn-primary" and text "Refresh"
        try {
            const primaryButtons = Array.from(document.querySelectorAll("button.btn.btn-primary, button.btn-primary, input.btn.btn-primary, .btn-primary"));
            for (const btn of primaryButtons) {
                const text = (btn.textContent || btn.innerText || btn.value || "").trim().toLowerCase();
                if ((text === "refresh" || text.includes("refresh")) && isElementClickable(btn)) {
                    return { element: btn, strategy: "btn_primary_button", text: text };
                }
            }
        } catch (e) {}

        // Attempt 5: Any BUTTON or INPUT element having exact or partial text/value "Refresh"
        try {
            const allButtons = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit'], [role='button']"));
            for (const b of allButtons) {
                const text = (b.innerText || b.textContent || b.value || "").trim().toLowerCase();
                if (text === "refresh" && isElementClickable(b)) {
                    return { element: b, strategy: "button_exact_text" };
                }
            }
        } catch (e) {}

        return null;
    }

    function triggerClickOnButton(btnElement) {
        if (!btnElement || btnElement.nodeType !== Node.ELEMENT_NODE) return false;

        // Strict safety guard: Only reject external link navigation
        if (btnElement.tagName === "A") {
            const href = (btnElement.getAttribute("href") || "").trim();
            if (href && !href.startsWith("#") && !href.startsWith("javascript:") && (href.startsWith("http") || href.startsWith("/"))) {
                console.warn("[ChromeGrid] Rejected click on external navigation link to prevent leaving the page.");
                return false;
            }
        }

        // 1. Visual flash indication on the target button (subtle green pulse)
        try {
            const origOutline = btnElement.style.outline;
            const origBoxShadow = btnElement.style.boxShadow;
            btnElement.style.outline = "3px solid #10b981";
            btnElement.style.boxShadow = "0 0 12px #10b981";

            setTimeout(() => {
                btnElement.style.outline = origOutline;
                btnElement.style.boxShadow = origBoxShadow;
            }, 800);
        } catch (e) {}

        // 2. Bring element into viewport if needed
        try {
            btnElement.scrollIntoView({ behavior: "instant", block: "nearest", inline: "nearest" });
        } catch (e) {}

        // 3. Focus the button
        try {
            if (typeof btnElement.focus === "function") btnElement.focus();
        } catch (e) {}

        // 4. Trigger clean click sequence
        let clicked = false;
        try {
            const eventOpts = { bubbles: true, cancelable: true, view: window };
            btnElement.dispatchEvent(new MouseEvent("mousedown", eventOpts));
            btnElement.dispatchEvent(new MouseEvent("mouseup", eventOpts));

            if (typeof btnElement.click === "function") {
                btnElement.click();
                clicked = true;
            } else {
                btnElement.dispatchEvent(new MouseEvent("click", eventOpts));
                clicked = true;
            }
        } catch (err) {
            console.error("[ChromeGrid] Error executing button click:", err);
            try {
                btnElement.click();
                clicked = true;
            } catch (clickErr) {
                clicked = false;
            }
        }

        return clicked;
    }

    function isCalendarSlotPage() {
        const title = (document.title || "").toLowerCase();
        if (title.includes("recaptcha") || title.includes("captcha") || title.includes("too many requests") || title.includes("login")) {
            return false;
        }
        const href = (window.location.href || "").toLowerCase();
        return href.includes("slotselection") ||
               href.includes("slot-selection") ||
               href.includes("slot_selection") ||
               title.includes("slot selection") ||
               title.includes("calendar");
    }

    function executeRefresh(params = {}) {
        const target = (params.target || "all").toLowerCase();
        const isCal = isCalendarSlotPage();

        // If command specifically targeted calendar tabs ('a' or 'calendar') and this tab is not one, ignore gracefully
        if ((target === "a" || target === "calendar") && !isCal) {
            console.log("[ChromeGrid] Tab ignored refresh: not a calendar/slot page.");
            sendAck({
                type: "refresh_ack",
                tab_id: TAB_ID,
                command_id: params.command_id || null,
                success: false,
                ignored: true,
                error: "Not a calendar slot page (tab skipped)",
                duration_ms: 0,
                url: window.location.href,
                title: document.title,
                timestamp: Date.now()
            });
            return false;
        }

        const xpath = params.xpath || DEFAULT_XPATH;
        const text = params.text || DEFAULT_TEXT;
        const className = params.class_name || DEFAULT_CLASS;
        const maxRetries = params.max_retries !== undefined ? params.max_retries : 8;
        const retryDelayMs = 200;

        const startTs = performance.now();
        let attempts = 0;

        function attemptFindAndClick() {
            attempts++;
            const found = findTargetButton(xpath, text, className);

            if (found && found.element) {
                const clicked = triggerClickOnButton(found.element);
                const durationMs = Math.round(performance.now() - startTs);
                updateBadge("refreshing");

                sendAck({
                    type: "refresh_ack",
                    tab_id: TAB_ID,
                    command_id: params.command_id || null,
                    success: clicked,
                    strategy: found.strategy,
                    element_tag: found.element.tagName,
                    element_class: found.element.className,
                    element_text: (found.element.textContent || found.element.value || "").trim().substring(0, 50),
                    duration_ms: durationMs,
                    attempts: attempts,
                    url: window.location.href,
                    title: document.title,
                    timestamp: Date.now()
                });

                console.log(`[ChromeGrid] Successfully clicked refresh button via ${found.strategy} in ${durationMs}ms (attempt ${attempts})`);
                if (typeof window.gc === "function") {
                    try { window.gc(); } catch (e) {}
                }
                return true;
            }

            if (attempts <= maxRetries) {
                setTimeout(attemptFindAndClick, retryDelayMs);
                return false;
            }

            const durationMs = Math.round(performance.now() - startTs);
            const isNonCal = !isCalendarSlotPage();

            sendAck({
                type: "refresh_ack",
                tab_id: TAB_ID,
                command_id: params.command_id || null,
                success: false,
                ignored: isNonCal, // Do not count as failure if this page never had a calendar retrier
                error: isNonCal
                    ? `Not a slot calendar page ('${document.title}')`
                    : `Button not found after ${attempts} attempts. Checked XPath: "${xpath}", Text: "${text}", Class: "${className}"`,
                duration_ms: durationMs,
                attempts: attempts,
                url: window.location.href,
                title: document.title,
                timestamp: Date.now()
            });

            console.warn(`[ChromeGrid] Target refresh button not found in page ('${document.title}').`);
            return false;
        }

        return attemptFindAndClick();
    }

    // ---------------------------------------------------------------------------
    // Slot Input Filler (Page A & Page B)
    // ---------------------------------------------------------------------------
    /**
     * Sets an <input type="number"> value in a way that JS frameworks and browser extensions detect:
     *   1. Focuses element
     *   2. Uses native prototype value setter (bypasses React/Vue/Angular controlled-input protection)
     *   3. Sets direct property .value and HTML attribute 'value'
     *   4. Updates React internal _valueTracker if present
     *   5. Dispatches jQuery input/change triggers if jQuery is present
     *   6. Dispatches synthetic focus, keydown, keypress, input, keyup, change, and blur events
     */
    function setNativeInputValue(el, value) {
        if (!el) return false;
        const strVal = String(value);
        const win = (typeof unsafeWindow !== "undefined" && unsafeWindow) ? unsafeWindow : window;

        try {
            el.focus();
        } catch (e) {}

        // 1. Reset React _valueTracker so React recognizes the change!
        try {
            const tracker = el._valueTracker;
            if (tracker) {
                tracker.setValue(el.value + "_prev");
            }
        } catch (e) {}

        // 2. Prototype setter call on HTMLInputElement.prototype
        let setterSucceeded = false;
        try {
            const protoSetter = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value')?.set
                || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
            if (protoSetter) {
                protoSetter.call(el, strVal);
                setterSucceeded = true;
            }
        } catch (e) {}

        if (!setterSucceeded) {
            try { el.value = strVal; } catch (e) {}
        }

        try { el.value = strVal; } catch (e) {}
        try { el.setAttribute("value", strVal); } catch (e) {}

        // 3. Direct React onChange handler invocation if attached (__reactProps$ / __reactEventHandlers$)
        try {
            const reactKey = Object.keys(el).find(k => k.startsWith("__reactProps$") || k.startsWith("__reactEventHandlers$"));
            if (reactKey && el[reactKey]) {
                const props = el[reactKey];
                if (typeof props.onChange === "function") {
                    props.onChange({ target: el, currentTarget: el, bubbles: true });
                }
                if (typeof props.onInput === "function") {
                    props.onInput({ target: el, currentTarget: el, bubbles: true });
                }
            }
        } catch (e) {}

        // 4. jQuery / Bootstrap support
        try {
            const $ = win.jQuery || win.$ || (typeof $ !== "undefined" ? $ : null);
            if ($ && typeof $(el).val === "function") {
                $(el).val(strVal);
                if (typeof $(el).trigger === "function") {
                    $(el).trigger("input").trigger("change");
                }
            }
        } catch (e) {}

        // 5. Dispatch standard DOM events across both execution worlds
        const eventNames = ["focus", "keydown", "keypress", "input", "keyup", "change", "blur"];
        for (const evtName of eventNames) {
            try {
                const EvtClass = evtName.startsWith("key")
                    ? (win.KeyboardEvent || KeyboardEvent)
                    : (win.Event || Event);
                const evt = new EvtClass(evtName, {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    key: strVal
                });
                el.dispatchEvent(evt);
            } catch (e) {
                try {
                    el.dispatchEvent(new Event(evtName, { bubbles: true, composed: true }));
                } catch (err) {}
            }
        }

        // 6. Direct DOM oninput / onchange callbacks
        try {
            if (typeof el.oninput === "function") el.oninput(new Event('input', { bubbles: true }));
            if (typeof el.onchange === "function") el.onchange(new Event('change', { bubbles: true }));
        } catch (e) {}

        return true;
    }

    function queryDeep(selector) {
        if (!selector) return null;
        try {
            if (selector.startsWith('#')) {
                const id = selector.slice(1);
                const byId = document.getElementById(id);
                if (byId) return byId;
                if (typeof unsafeWindow !== "undefined" && unsafeWindow && unsafeWindow.document) {
                    const uById = unsafeWindow.document.getElementById(id);
                    if (uById) return uById;
                }
            }
            const el = document.querySelector(selector);
            if (el) return el;
        } catch (e) {}

        try {
            if (typeof unsafeWindow !== "undefined" && unsafeWindow && unsafeWindow.document) {
                const el = unsafeWindow.document.querySelector(selector);
                if (el) return el;
            }
        } catch (e) {}

        return null;
    }

    function isSlotPageA() {
        const title = (document.title || "").toLowerCase();
        const href = (window.location.href || "").toLowerCase();
        if (title.includes("too many requests") || title.includes("recaptcha") || title.includes("captcha") || title.includes("login")) {
            return false;
        }
        // If #controller, #InputSec, or favicon.png exists, this is Page B (Visa Type), NOT Page A!
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
        // DOM check: retrier toolbar inputs
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
        // If #controller, #InputSec, or #btnToggleSec exists, this is 100% Page B (Visa Type)!
        if (document.getElementById('controller') || document.getElementById('InputSec') || document.getElementById('InputMs') || document.getElementById('btnToggleSec')) {
            return true;
        }
        // If URL contains favicon.png -> 100% Page B!
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
        try {
            if (document.querySelector('select[name*="visa" i], select[id*="visa" i]')) {
                return true;
            }
        } catch (e) {}
        return false;
    }

    function findSlotInputs(targetHint) {
        const tgt = (targetHint || "").toLowerCase();

        // PRIORITY 1: Check for Page B inputs inside #controller or direct (#InputSec & #InputMs)
        // User's exact container: <div id="controller"><input id="InputSec"><input id="InputMs"><button id="btnToggleSec">OFF</button></div>
        if (tgt === "b" || tgt === "all" || !tgt) {
            try {
                const ctrl = document.getElementById('controller');
                if (ctrl) {
                    const s = ctrl.querySelector('#InputSec') || ctrl.querySelector('input:nth-of-type(1)');
                    const m = ctrl.querySelector('#InputMs') || ctrl.querySelector('input:nth-of-type(2)');
                    if (s && m) {
                        return { secEl: s, msEl: m, strategy: "controller_parent_div" };
                    }
                }
            } catch (e) {}

            try {
                const s = document.getElementById('InputSec');
                const m = document.getElementById('InputMs');
                if (s && m) {
                    return { secEl: s, msEl: m, strategy: "id_inputsec_page_b" };
                }
            } catch (e) {}
        }

        // PRIORITY 2: Check for Page A inputs (Retrier Toolbar)
        // User's exact Calendar inputs: placeholder="0-59" & placeholder="MS" or body > div:nth-child(7)
        if (tgt === "a" || tgt === "all" || !tgt) {
            try {
                const s = document.querySelector('input[placeholder="0-59"], input[placeholder*="0-59"]');
                const m = document.querySelector('input[placeholder="MS" i], input[placeholder="ms"], input[placeholder*="MS" i]');
                if (s && m) {
                    return { secEl: s, msEl: m, strategy: "placeholder_exact_page_a" };
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
                    return { secEl: s, msEl: m, strategy: "dom_hierarchy_page_a" };
                }
            } catch (e) {}
        }

        // PRIORITY 3: If target is not 'b', check inputs with max="59" & max="999"
        if (tgt !== "b") {
            try {
                const s = document.querySelector('input[type="number"][max="59"], input[max="59"].form-control, input[max="59"]');
                const m = document.querySelector('input[type="number"][max="999"], input[max="999"].form-control, input[max="999"]');
                if (s && m) {
                    return { secEl: s, msEl: m, strategy: "attr_max_59_999" };
                }
            } catch (e) {}
        }

        // PRIORITY 4: Fallback for Page B: any input with id containing "sec" and id containing "ms"
        try {
            const s = document.querySelector('input[id*="sec" i], input[name*="sec" i]');
            const m = document.querySelector('input[id*="ms" i], input[name*="ms" i]');
            if (s && m && s !== m) {
                return { secEl: s, msEl: m, strategy: "id_partial_sec_ms" };
            }
        } catch (e) {}

        return { secEl: null, msEl: null, strategy: "none" };
    }

    function executeSlotClick(params = {}) {
        const target = (params.target || "all").toLowerCase();

        // Resolve sec and ms values
        let secVal = params.sec;
        let msVal = params.ms;
        let delayMs = 0;

        const isPageA = isSlotPageA();
        const isPageB = isSlotPageB();

        if (secVal === undefined || secVal === null) {
            secVal = (target === "b" || isPageB) ? params.page_b_sec : params.page_a_sec;
        }
        if (msVal === undefined || msVal === null) {
            msVal = (target === "b" || isPageB) ? params.page_b_ms : params.page_a_ms;
        }
        delayMs = Math.max(0, parseInt((target === "b" || isPageB) ? params.page_b_delay_ms : params.page_a_delay_ms, 10) || 0);

        if (secVal === undefined || secVal === null) {
            console.warn("[ChromeGrid SlotClick] No sec value provided in params.", params);
            return false;
        }

        const startTs = performance.now();
        let attempts = 0;
        const maxRetries = 20;
        const retryDelayMs = 150;

        function attemptFindAndFill() {
            attempts++;
            const found = findSlotInputs(target);

            if (found.secEl && found.msEl) {
                const okSec = setNativeInputValue(found.secEl, secVal);
                const okMs = setNativeInputValue(found.msEl, msVal);
                const durationMs = Math.round(performance.now() - startTs);
                const success = okSec && okMs;

                updateBadge(success ? "refreshing" : "disconnected");

                sendAck({
                    type: "slot_ack",
                    tab_id: TAB_ID,
                    command_id: params.command_id || null,
                    success: success,
                    strategy: found.strategy,
                    duration_ms: durationMs,
                    attempts: attempts,
                    url: window.location.href,
                    title: document.title,
                    timestamp: Date.now()
                });

                console.log(`[ChromeGrid SlotClick] Inputs filled via ${found.strategy} in ${durationMs}ms (sec=${secVal}, ms=${msVal})`);

                if (typeof window.gc === "function") {
                    try { window.gc(); } catch (e) {}
                }
                return true;
            }

            if (attempts <= maxRetries) {
                setTimeout(attemptFindAndFill, retryDelayMs);
                return false;
            }

            // Target mismatch check (only report ignored if definitively another page and no inputs found)
            const titleLow = (document.title || "").toLowerCase();
            const isTargetMismatch = (target === "b" && isPageA && !isPageB && !titleLow.includes("visa")) ||
                                     (target === "a" && isPageB && !isPageA && !titleLow.includes("slot"));
            const durationMs = Math.round(performance.now() - startTs);
            sendAck({
                type: "slot_ack",
                tab_id: TAB_ID,
                command_id: params.command_id || null,
                success: false,
                ignored: isTargetMismatch,
                error: isTargetMismatch
                    ? `Ignored: target is '${target}' but page is ${isPageA ? "Page A" : "Page B"} ('${document.title}')`
                    : `Slot inputs (#InputSec/#InputMs) not found after ${attempts} attempts ('${document.title}')`,
                duration_ms: durationMs,
                attempts: attempts,
                url: window.location.href,
                title: document.title,
                timestamp: Date.now()
            });

            console.warn(`[ChromeGrid SlotClick] Slot inputs not found after ${attempts} attempts.`);
            return false;
        }

        if (delayMs > 0) {
            setTimeout(attemptFindAndFill, delayMs);
        } else {
            attemptFindAndFill();
        }
        return true;
    }

    function executeEval(params = {}) {
        const code = params.code || "";
        let result = null;
        let err = null;
        try {
            const fn = new Function("win", "doc", code);
            result = fn(win, document);
        } catch (e) {
            err = String(e);
        }
        sendAck({
            type: "eval_ack",
            tab_id: TAB_ID,
            command_id: params.command_id || null,
            success: !err,
            error: err,
            result: String(result),
            url: window.location.href,
            title: document.title,
            timestamp: Date.now()
        });
    }

    function executeOpenTab(params = {}) {
        const targetUrl = params.url || `${HTTP_SERVER_URL}/userscript.user.js`;
        console.log(`[ChromeGrid] Opening installer tab in existing window: ${targetUrl}`);
        let opened = false;
        try {
            if (typeof GM_openInTab === "function") {
                GM_openInTab(targetUrl, { active: true, insert: true });
                opened = true;
            } else {
                window.open(targetUrl, "_blank");
                opened = true;
            }
        } catch (e) {
            console.error("[ChromeGrid] Failed to open tab:", e);
        }

        sendAck({
            type: "open_tab_ack",
            tab_id: TAB_ID,
            command_id: params.command_id || null,
            success: opened,
            url: window.location.href,
            title: document.title,
            timestamp: Date.now()
        });
    }

    // ---------------------------------------------------------------------------
    // ThunderBolt Extension Configuration Handler (Zero-Proxy Mode)
    // ---------------------------------------------------------------------------
    let lastThunderCommandId = null;

    function executeThunderConfig(params = {}) {
        const settings = params.settings || {};
        lastThunderCommandId = params.command_id || lastThunderCommandId;
        console.log("[ChromeGrid] Applying Thunder Bolt Configuration (Zero-Proxy Mode):", settings);

        // Whitelist ONLY region and vtData to ensure external launcher settings are never touched
        const safeSettings = {
            region: settings.region || "Spain"
        };
        if (settings.vtData && typeof settings.vtData === "object") {
            safeSettings.vtData = settings.vtData;
        }

        let success = true;
        let errMsg = null;

        try {
            const targetWin = (typeof unsafeWindow !== "undefined" && unsafeWindow) ? unsafeWindow : window;

            // Post to window and unsafeWindow for Thunder extension's bridge.js (SET_DYNAMIC_STORAGE)
            const postPayload = {
                type: "SET_DYNAMIC_STORAGE",
                data: safeSettings
            };
            targetWin.postMessage(postPayload, "*");
            if (targetWin !== window) {
                window.postMessage(postPayload, "*");
            }

            // Retry after brief delay
            setTimeout(() => {
                try {
                    targetWin.postMessage(postPayload, "*");
                } catch (e) {}
            }, 350);

        } catch (e) {
            success = false;
            errMsg = String(e);
            console.error("[ChromeGrid] Failed to apply Thunder configuration:", e);
        }

        sendAck({
            type: "thunder_config_ack",
            tab_id: TAB_ID,
            command_id: params.command_id || null,
            success: success,
            confirmed_by_extension: false,
            error: errMsg,
            url: window.location.href,
            title: document.title,
            timestamp: Date.now()
        });
    }

    // Listen for Thunder extension's bridge confirmation
    window.addEventListener("message", (ev) => {
        if (ev && ev.data && ev.data.type === "DYNAMIC_STORAGE_SET_CONFIRM") {
            sendAck({
                type: "thunder_config_ack",
                tab_id: TAB_ID,
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
    function sendPayload(obj) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            try {
                socket.send(JSON.stringify(obj));
                return true;
            } catch (e) {
                console.error("[ChromeGrid] WebSocket send error:", e);
            }
        }
        return false;
    }

    function sendAck(ackData) {
        // 1. Send via WebSocket if connected
        if (socket && socket.readyState === WebSocket.OPEN) {
            sendPayload(ackData);
            return;
        }

        // 2. In HTTP polling mode: queue ACK to be piggybacked on the next poll request!
        // This cuts HTTP network traffic in half (from 100 requests to 50 for 50 Chromes).
        pendingAck = ackData;
    }

    function sendRegistration() {
        sendPayload({
            type: "register",
            tab_id: TAB_ID,
            title: document.title || "Untitled Tab",
            url: window.location.href,
            user_agent: navigator.userAgent,
            screen_x: typeof window.screenX !== "undefined" ? window.screenX : (window.screenLeft || 0),
            screen_y: typeof window.screenY !== "undefined" ? window.screenY : (window.screenTop || 0),
            outer_w: window.outerWidth || 0,
            outer_h: window.outerHeight || 0,
            timestamp: Date.now()
        });
    }

    function sendHeartbeat() {
        sendPayload({
            type: "heartbeat",
            tab_id: TAB_ID,
            title: document.title,
            url: window.location.href,
            screen_x: typeof window.screenX !== "undefined" ? window.screenX : (window.screenLeft || 0),
            screen_y: typeof window.screenY !== "undefined" ? window.screenY : (window.screenTop || 0),
            outer_w: window.outerWidth || 0,
            outer_h: window.outerHeight || 0,
            timestamp: Date.now()
        });
    }

    // ---------------------------------------------------------------------------
    // GM_xmlhttpRequest Long-Polling (Bypasses Mixed Content, CSP & PNA)
    // ---------------------------------------------------------------------------
    function startLongPolling() {
        if (pollActive) return;
        pollActive = true;
        connectionMode = "polling";

        // Stop WebSocket heartbeat timer: the HTTP long-poll acts as keepalive itself
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }

        console.log("[ChromeGrid] Starting background HTTP long-poll listener via GM_xmlhttpRequest...");
        // Add subtle initial stagger (50-450ms) on first page load
        setTimeout(doPoll, 50 + Math.floor(Math.random() * 400));
    }

    function doPoll() {
        if (!pollActive) return;

        if (typeof GM_xmlhttpRequest !== "function") {
            console.warn("[ChromeGrid] GM_xmlhttpRequest is unavailable. Check Tampermonkey @grant settings.");
            return;
        }

        const pageType = isSlotPageA() ? "a" : (isSlotPageB() ? "b" : "other");
        const inputs = findSlotInputs();
        const hasInputs = !!(inputs.secEl && inputs.msEl);
        const scrX = typeof window.screenX !== "undefined" ? window.screenX : (window.screenLeft || 0);
        const scrY = typeof window.screenY !== "undefined" ? window.screenY : (window.screenTop || 0);
        let pollUrl = `${HTTP_SERVER_URL}/api/poll?tab_id=${encodeURIComponent(TAB_ID)}&v=1.8.8&title=${encodeURIComponent(document.title || "Chrome Tab")}&url=${encodeURIComponent(window.location.href)}&page_type=${encodeURIComponent(pageType)}&has_inputs=${hasInputs ? "1" : "0"}&screen_x=${scrX}&screen_y=${scrY}`;

        // Piggyback pending execution ACK directly onto poll request to eliminate extra TCP connection!
        if (pendingAck) {
            pollUrl += `&ack_cmd=${encodeURIComponent(pendingAck.command_id || "")}` +
                       `&ack_success=${pendingAck.success ? "true" : "false"}` +
                       `&ack_ignored=${pendingAck.ignored ? "true" : "false"}` +
                       `&ack_dur=${pendingAck.duration_ms || 0}` +
                       `&ack_strategy=${encodeURIComponent(pendingAck.strategy || "")}` +
                       `&ack_err=${encodeURIComponent((pendingAck.error || "").substring(0, 150))}`;
            pendingAck = null;
        }

        GM_xmlhttpRequest({
            method: "GET",
            url: pollUrl,
            timeout: 45000, // 20s safety margin over server's wait
            onload: function (resp) {
                pollFailures = 0;
                isConnected = true;
                updateBadge("connected");

                try {
                    const data = JSON.parse(resp.responseText);
                    if (data && (data.action === "refresh" || data.action === "click_refresh")) {
                        executeRefresh(data);
                    } else if (data && data.action === "slot_click") {
                        executeSlotClick(data);
                    } else if (data && (data.action === "open_tab" || data.action === "update_userscript")) {
                        executeOpenTab(data);
                    } else if (data && data.action === "eval") {
                        executeEval(data);
                    } else if (data && (data.action === "thunder_config" || data.action === "set_thunder_config")) {
                        executeThunderConfig(data);
                    }
                } catch (e) {
                    // Ignore heartbeat parse
                }

                // Immediately re-poll (25ms) to be armed and ready for the next operation
                setTimeout(doPoll, 25);
            },
            onerror: function () {
                pollFailures++;
                isConnected = false;
                updateBadge("disconnected");
                const delay = Math.min(8000, 1500 + pollFailures * 1000);
                setTimeout(doPoll, delay);
            },
            ontimeout: function () {
                // Heartbeat ping from server — stay green, re-poll immediately so we never miss a broadcast
                isConnected = true;
                updateBadge("connected");
                setTimeout(doPoll, 25);
            }
        });
    }

    // ---------------------------------------------------------------------------
    // WebSocket Client with Graceful Fallback
    // ---------------------------------------------------------------------------
    function connectWebSocket() {
        if (connectionMode === "polling") {
            startLongPolling();
            return;
        }

        if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
            return;
        }

        try {
            socket = new WebSocket(WS_SERVER_URL);

            socket.onopen = function () {
                isConnected = true;
                connectionMode = "websocket";
                updateBadge("connected");
                console.log("[ChromeGrid] Connected to Chrome Grid Desktop App via WebSocket at", WS_SERVER_URL);

                // Register this tab
                sendRegistration();

                // Setup regular heartbeat
                clearInterval(heartbeatTimer);
                heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
            };

            socket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (!data || !data.action) return;

                    if (data.action === "refresh" || data.action === "click_refresh") {
                        executeRefresh(data);
                    } else if (data.action === "slot_click") {
                        executeSlotClick(data);
                    } else if (data.action === "open_tab" || data.action === "update_userscript") {
                        executeOpenTab(data);
                    } else if (data.action === "eval") {
                        executeEval(data);
                    } else if (data.action === "thunder_config" || data.action === "set_thunder_config") {
                        executeThunderConfig(data);
                    } else if (data.action === "ping") {
                        sendPayload({ type: "pong", tab_id: TAB_ID, timestamp: Date.now() });
                    }
                } catch (err) {
                    console.error("[ChromeGrid] Message parse error:", err);
                }
            };

            socket.onclose = function () {
                clearInterval(heartbeatTimer);
                if (typeof GM_xmlhttpRequest === "function") {
                    // Switch seamlessly to long polling without spamming reconnect loops
                    console.log("[ChromeGrid] WebSocket closed, switching to GM_xmlhttpRequest long-polling...");
                    startLongPolling();
                } else {
                    isConnected = false;
                    updateBadge("disconnected");
                    scheduleReconnect();
                }
            };

            socket.onerror = function () {
                // WebSocket connection failed (likely Mixed Content on HTTPS or CSP)
                if (typeof GM_xmlhttpRequest === "function") {
                    console.log("[ChromeGrid] WebSocket blocked by browser security. Engaging GM_xmlhttpRequest long-polling...");
                    try { socket.close(); } catch (e) {}
                    startLongPolling();
                } else {
                    isConnected = false;
                    updateBadge("disconnected");
                }
            };
        } catch (e) {
            if (typeof GM_xmlhttpRequest === "function") {
                startLongPolling();
            } else {
                isConnected = false;
                updateBadge("disconnected");
                scheduleReconnect();
            }
        }
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
        }, RECONNECT_INTERVAL_MS);
    }

    // ---------------------------------------------------------------------------
    // Connection Orchestrator
    // ---------------------------------------------------------------------------
    function startConnection() {
        // If current webpage is loaded over HTTPS, Chrome's Mixed Content security strictly
        // forbids connecting to unencrypted ws://127.0.0.1.
        // In that case, jump immediately to GM_xmlhttpRequest long polling!
        // This avoids the "WebSocket connection to 'ws://127.0.0.1:8765/' failed:" console error entirely.
        if (window.location.protocol === "https:" && typeof GM_xmlhttpRequest === "function") {
            console.log("[ChromeGrid] HTTPS detected: using GM_xmlhttpRequest to bypass Mixed Content & CSP restrictions.");
            startLongPolling();
            return;
        }

        // On plain HTTP or local origins, try WebSocket first, with automatic fallback
        connectWebSocket();
    }

    // ---------------------------------------------------------------------------
    // Initialization
    // ---------------------------------------------------------------------------
    function init() {
        createStatusBadge();
        startConnection();

        // Clean up and purge any stale cached extension configurations to prevent proxy locking
        try {
            if (typeof GM_deleteValue !== "undefined") {
                GM_deleteValue("__cgl_thunder_config");
            }
        } catch (e) {}
        try {
            localStorage.removeItem("__cgl_thunder_config");
        } catch (e) {}

        // Update registration if page title changes (SPA navigation)
        const titleObserver = new MutationObserver(() => {
            if (isConnected) {
                if (connectionMode === "websocket") {
                    sendPayload({
                        type: "tab_update",
                        tab_id: TAB_ID,
                        title: document.title,
                        url: window.location.href,
                        screen_x: typeof window.screenX !== "undefined" ? window.screenX : (window.screenLeft || 0),
                        screen_y: typeof window.screenY !== "undefined" ? window.screenY : (window.screenTop || 0)
                    });
                }
            }
        });

        const titleEl = document.querySelector("title");
        if (titleEl) {
            titleObserver.observe(titleEl, { childList: true, characterData: true, subtree: true });
        }

        // Active tab visibility & window focus auto-recovery
        window.addEventListener("focus", () => {
            if (!pollActive) startLongPolling();
        });
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible" && !pollActive) {
                startLongPolling();
            }
        });
    }

    if (document.readyState === "complete" || document.readyState === "interactive") {
        init();
    } else {
        window.addEventListener("DOMContentLoaded", init);
    }
})();

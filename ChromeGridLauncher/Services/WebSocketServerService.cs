using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class WebSocketServerService
    {
        public const int DefaultPort = 8765;
        private HttpListener? _listener;
        private CancellationTokenSource? _cts;
        private readonly ConcurrentDictionary<WebSocket, ConnectedTab> _clients = new();
        private readonly ConcurrentDictionary<string, ConnectedTab> _httpClients = new();
        private readonly ConcurrentDictionary<string, TaskCompletionSource<string?>> _pollWaiters = new();

        private readonly object _debounceLock = new();
        private DateTime _lastNotifyTime = DateTime.MinValue;
        private System.Threading.Timer? _debounceTimer;
        private bool _notifyPending = false;

        public event Action<int, List<ConnectedTab>>? OnClientsChanged;
        public event Action<Dictionary<string, object>>? OnAckReceived;
        public event Action<string, string>? OnLog;
        public event Action<bool, string>? OnStatusChanged;

        public bool IsRunning { get; private set; } = false;
        public int Port { get; set; } = DefaultPort;

        public int TotalBroadcasts { get; private set; } = 0;
        public int TotalAcksSuccess { get; private set; } = 0;
        public int TotalAcksFailed { get; private set; } = 0;

        public string UserscriptFilePath { get; set; } = string.Empty;
        public string CurrentExtensionBuildHash { get; private set; } = string.Empty;

        private FileSystemWatcher? _extensionWatcher;
        private System.Threading.Timer? _watcherDebounceTimer;

        public WebSocketServerService()
        {
            LocateUserscriptFile();
            UpdateExtensionBuildHash();
        }

        private void LocateUserscriptFile()
        {
            try
            {
                UserscriptFilePath = ExtensionDeploymentService.EnsureUserscriptDeployed();
            }
            catch
            {
                UserscriptFilePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "chrome_refresh_listener.user.js");
            }
        }

        public string UpdateExtensionBuildHash()
        {
            try
            {
                string dir = ExtensionDeploymentService.GlobalExtensionDirectory;
                if (!Directory.Exists(dir))
                {
                    CurrentExtensionBuildHash = "init_" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                    return CurrentExtensionBuildHash;
                }

                var files = new[] { "manifest.json", "background.js", "content.js" };
                var sb = new StringBuilder();
                foreach (var f in files)
                {
                    string p = Path.Combine(dir, f);
                    if (File.Exists(p))
                    {
                        var fi = new FileInfo(p);
                        sb.Append($"{f}:{fi.Length}:{fi.LastWriteTimeUtc.Ticks};");
                    }
                }
                CurrentExtensionBuildHash = sb.Length > 0 ? sb.ToString() : ("b_" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());
            }
            catch
            {
                CurrentExtensionBuildHash = "fallback_" + Guid.NewGuid().ToString("N").Substring(0, 8);
            }
            return CurrentExtensionBuildHash;
        }

        private void StartExtensionDirectoryWatcher()
        {
            try
            {
                string dir = ExtensionDeploymentService.GlobalExtensionDirectory;
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

                _extensionWatcher = new FileSystemWatcher(dir)
                {
                    Filter = "*.*",
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName | NotifyFilters.Size,
                    EnableRaisingEvents = true
                };

                _watcherDebounceTimer = new System.Threading.Timer(_ =>
                {
                    try
                    {
                        string oldHash = CurrentExtensionBuildHash;
                        string newHash = UpdateExtensionBuildHash();
                        if (oldHash != newHash)
                        {
                            Log("[ExtensionWatcher] Extension files changed on disk. Auto-reloading all Chrome profiles...", "INFO");
                            BroadcastReloadExtension();
                        }
                    }
                    catch { }
                }, null, Timeout.Infinite, Timeout.Infinite);

                FileSystemEventHandler onFileChanged = (s, e) =>
                {
                    string fn = Path.GetFileName(e.FullPath).ToLowerInvariant();
                    if (fn.EndsWith(".js") || fn.EndsWith(".json"))
                    {
                        _watcherDebounceTimer?.Change(500, Timeout.Infinite);
                    }
                };

                _extensionWatcher.Changed += onFileChanged;
                _extensionWatcher.Created += onFileChanged;
                _extensionWatcher.Renamed += (s, e) => onFileChanged(s, e);
            }
            catch (Exception ex)
            {
                Log($"[ExtensionWatcher] Could not start directory watcher: {ex.Message}", "WARNING");
            }
        }

        public void Start(int? port = null)
        {
            if (IsRunning) return;
            if (port.HasValue) Port = port.Value;

            _cts = new CancellationTokenSource();
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://127.0.0.1:{Port}/");

            try
            {
                _listener.Start();
                IsRunning = true;
                UpdateExtensionBuildHash();
                StartExtensionDirectoryWatcher();
                Task.Run(() => ListenLoopAsync(_cts.Token));
                Task.Run(() => PingLoopAsync(_cts.Token));
                Log($"[Server] WebSocket & HTTP server started on ws://127.0.0.1:{Port} & http://127.0.0.1:{Port}", "SUCCESS");
                OnStatusChanged?.Invoke(true, $"Listening on port {Port}");
                NotifyClientsChanged(immediate: true);
            }
            catch (Exception ex)
            {
                Log($"[Server] Failed to start on port {Port}: {ex.Message}", "ERROR");
                OnStatusChanged?.Invoke(false, ex.Message);
            }
        }

        public void Stop()
        {
            if (!IsRunning) return;
            IsRunning = false;
            _cts?.Cancel();

            foreach (var ws in _clients.Keys)
            {
                try
                {
                    ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Server Stopping", CancellationToken.None);
                }
                catch { }
            }
            _clients.Clear();
            _httpClients.Clear();

            foreach (var kvp in _pollWaiters)
            {
                kvp.Value.TrySetResult(null);
            }
            _pollWaiters.Clear();

            try
            {
                _listener?.Stop();
                _listener?.Close();
            }
            catch { }

            try
            {
                _extensionWatcher?.Dispose();
                _extensionWatcher = null;
                _watcherDebounceTimer?.Dispose();
                _watcherDebounceTimer = null;
            }
            catch { }

            lock (_debounceLock)
            {
                _debounceTimer?.Dispose();
                _debounceTimer = null;
                _notifyPending = false;
            }

            Log("[Server] Server stopped.", "INFO");
            OnStatusChanged?.Invoke(false, "Stopped");
            NotifyClientsChanged(immediate: true);
        }

        public void Restart(int? newPort = null)
        {
            Stop();
            Thread.Sleep(200);
            Start(newPort);
        }

        private async Task ListenLoopAsync(CancellationToken token)
        {
            while (IsRunning && !token.IsCancellationRequested)
            {
                try
                {
                    var context = await _listener!.GetContextAsync();
                    if (context.Request.IsWebSocketRequest)
                    {
                        _ = ProcessWebSocketConnectionAsync(context, token);
                    }
                    else
                    {
                        _ = ProcessHttpRequestAsync(context);
                    }
                }
                catch (Exception)
                {
                    if (token.IsCancellationRequested) break;
                }
            }
        }

        private async Task ProcessHttpRequestAsync(HttpListenerContext context)
        {
            try
            {
                var req = context.Request;
                var res = context.Response;

                res.Headers.Add("Access-Control-Allow-Origin", "*");
                res.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                res.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-Requested-With");
                res.Headers.Add("Access-Control-Allow-Private-Network", "true");

                if (req.HttpMethod.Equals("OPTIONS", StringComparison.OrdinalIgnoreCase))
                {
                    res.StatusCode = 204;
                    res.Close();
                    return;
                }

                string path = req.Url?.AbsolutePath.ToLowerInvariant() ?? "/";

                if (path.EndsWith("userscript.user.js") || path.EndsWith("chrome_refresh_listener.user.js"))
                {
                    if (File.Exists(UserscriptFilePath))
                    {
                        byte[] scriptBytes = await File.ReadAllBytesAsync(UserscriptFilePath);
                        res.ContentType = "application/javascript; charset=utf-8";
                        res.StatusCode = 200;
                        await res.OutputStream.WriteAsync(scriptBytes, 0, scriptBytes.Length);
                    }
                    else
                    {
                        res.StatusCode = 404;
                        byte[] err = Encoding.UTF8.GetBytes("// chrome_refresh_listener.user.js not found on server.");
                        await res.OutputStream.WriteAsync(err, 0, err.Length);
                    }
                    res.Close();
                    return;
                }
                else if (path == "/poll" || path == "/api/poll" || path.EndsWith("/poll"))
                {
                    // HTTP Long-Polling fallback (bypasses browser mixed content / CSP / PNA)
                    string tabId = req.QueryString["tab_id"] ?? ("http_tab_" + Guid.NewGuid().ToString("N").Substring(0, 8));
                    string title = req.QueryString["title"] ?? "Chrome Tab (HTTP Polling)";
                    string url = req.QueryString["url"] ?? "";
                    string pageType = req.QueryString["page_type"] ?? "";
                    bool hasInputs = req.QueryString["has_inputs"] == "1" || req.QueryString["has_inputs"]?.ToLowerInvariant() == "true";
                    string version = req.QueryString["v"] ?? "";
                    _ = int.TryParse(req.QueryString["screen_x"], out int scrX);
                    _ = int.TryParse(req.QueryString["screen_y"], out int scrY);

                    // Check for piggybacked execution ACK directly on poll request
                    string? ackCmd = req.QueryString["ack_cmd"];
                    if (!string.IsNullOrEmpty(ackCmd))
                    {
                        bool ackSuccess = req.QueryString["ack_success"]?.ToLowerInvariant() == "true";
                        _ = int.TryParse(req.QueryString["ack_dur"], out int ackDur);
                        string ackStrategy = req.QueryString["ack_strategy"] ?? "";
                        string ackErr = req.QueryString["ack_err"] ?? "";
                        var ackDict = new Dictionary<string, object>
                        {
                            ["tab_id"] = tabId,
                            ["command_id"] = ackCmd,
                            ["result"] = ackSuccess ? "Success" : "Error",
                            ["duration_ms"] = ackDur,
                            ["strategy"] = ackStrategy,
                            ["error"] = ackErr
                        };
                        HandleAckPayload(ackDict);
                    }

                    var tab = _httpClients.GetOrAdd(tabId, tid => new ConnectedTab
                    {
                        TabId = tid,
                        Title = title,
                        Url = url,
                        PageType = pageType,
                        HasInputs = hasInputs,
                        Version = version,
                        ScreenX = scrX,
                        ScreenY = scrY,
                        ConnectedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
                    });

                    tab.LastSeen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
                    tab.Title = title;
                    tab.Url = url;
                    if (!string.IsNullOrEmpty(pageType)) tab.PageType = pageType;
                    tab.HasInputs = hasInputs;
                    tab.ScreenX = scrX;
                    tab.ScreenY = scrY;
                    NotifyClientsChanged();

                    var tcs = new TaskCompletionSource<string?>();
                    _pollWaiters[tabId] = tcs;

                    var timeoutTask = Task.Delay(25000);
                    var completedTask = await Task.WhenAny(tcs.Task, timeoutTask);

                    _pollWaiters.TryRemove(tabId, out _);

                    res.ContentType = "application/json; charset=utf-8";
                    res.StatusCode = 200;

                    if (completedTask == tcs.Task && tcs.Task.Result != null)
                    {
                        byte[] payloadBytes = Encoding.UTF8.GetBytes(tcs.Task.Result);
                        await res.OutputStream.WriteAsync(payloadBytes, 0, payloadBytes.Length);
                    }
                    else
                    {
                        byte[] emptyBytes = Encoding.UTF8.GetBytes("{\"action\":\"noop\"}");
                        await res.OutputStream.WriteAsync(emptyBytes, 0, emptyBytes.Length);
                    }

                    res.Close();
                    return;
                }
                else if (path == "/ack" || path == "/api/ack" || path.EndsWith("/ack"))
                {
                    if (req.HttpMethod.Equals("POST", StringComparison.OrdinalIgnoreCase))
                    {
                        using var reader = new StreamReader(req.InputStream, req.ContentEncoding);
                        string body = await reader.ReadToEndAsync();
                        try
                        {
                            var data = JsonSerializer.Deserialize<Dictionary<string, object>>(body);
                            if (data != null)
                            {
                                HandleAckPayload(data);
                            }
                        }
                        catch { }
                    }
                    else
                    {
                        // GET ACK fallback with query params
                        string tabId = req.QueryString["tab_id"] ?? "";
                        string cmdId = req.QueryString["command_id"] ?? "";
                        bool success = req.QueryString["success"]?.ToLowerInvariant() == "true";
                        _ = int.TryParse(req.QueryString["duration_ms"], out int dur);
                        string strat = req.QueryString["strategy"] ?? "";
                        string err = req.QueryString["error"] ?? "";
                        var ackDict = new Dictionary<string, object>
                        {
                            ["tab_id"] = tabId,
                            ["command_id"] = cmdId,
                            ["result"] = success ? "Success" : "Error",
                            ["duration_ms"] = dur,
                            ["strategy"] = strat,
                            ["error"] = err
                        };
                        HandleAckPayload(ackDict);
                    }

                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] ok = Encoding.UTF8.GetBytes("{\"status\":\"ok\"}");
                    await res.OutputStream.WriteAsync(ok, 0, ok.Length);
                    res.Close();
                    return;
                }
                else if (path == "/refresh" || path == "/api/refresh" || path.EndsWith("/refresh"))
                {
                    string cmdId = BroadcastRefresh("/html/body/div[5]/div[1]/button[1]", "Refresh", "btn btn-primary", 0);
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] rBytes = Encoding.UTF8.GetBytes($"{{\"status\":\"command_dispatched\",\"command_id\":\"{cmdId}\"}}");
                    await res.OutputStream.WriteAsync(rBytes, 0, rBytes.Length);
                    res.Close();
                    return;
                }
                else if (path == "/slot_click" || path == "/api/slot_click" || path == "/api/slot" || path.EndsWith("/slot_click"))
                {
                    string target = req.QueryString["target"] ?? "all";
                    _ = int.TryParse(req.QueryString["a_sec"] ?? req.QueryString["sec"], out int aSec);
                    _ = int.TryParse(req.QueryString["a_ms"] ?? req.QueryString["ms"], out int aMs);
                    _ = int.TryParse(req.QueryString["a_step"] ?? req.QueryString["step"], out int aStep);
                    _ = int.TryParse(req.QueryString["b_sec"] ?? req.QueryString["sec"], out int bSec);
                    _ = int.TryParse(req.QueryString["b_ms"] ?? req.QueryString["ms"], out int bMs);
                    _ = int.TryParse(req.QueryString["b_step"] ?? req.QueryString["step"], out int bStep);

                    string cmdId = BroadcastSlotClick(target, aSec, aMs, aStep, bSec, bMs, bStep);
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] rBytes = Encoding.UTF8.GetBytes($"{{\"status\":\"command_dispatched\",\"command_id\":\"{cmdId}\",\"target\":\"{target}\"}}");
                    await res.OutputStream.WriteAsync(rBytes, 0, rBytes.Length);
                    res.Close();
                    return;
                }
                else if (path == "/reload_extension" || path == "/api/reload_extension" || path == "/update_extension")
                {
                    string cmdId = BroadcastReloadExtension();
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] rBytes = Encoding.UTF8.GetBytes($"{{\"status\":\"command_dispatched\",\"command_id\":\"{cmdId}\",\"build_hash\":\"{CurrentExtensionBuildHash}\"}}");
                    await res.OutputStream.WriteAsync(rBytes, 0, rBytes.Length);
                    res.Close();
                    return;
                }
                else if (path == "/version" || path == "/api/version" || path == "/api/extension_version")
                {
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] rBytes = Encoding.UTF8.GetBytes($"{{\"status\":\"ok\",\"build_hash\":\"{CurrentExtensionBuildHash}\"}}");
                    await res.OutputStream.WriteAsync(rBytes, 0, rBytes.Length);
                    res.Close();
                    return;
                }
                else
                {
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    byte[] statusBytes = Encoding.UTF8.GetBytes($"{{\"status\":\"running\",\"server\":\"ChromeGridLauncher\",\"clients\":{_clients.Count + _httpClients.Count}}}");
                    await res.OutputStream.WriteAsync(statusBytes, 0, statusBytes.Length);
                    res.Close();
                    return;
                }
            }
            catch (Exception ex)
            {
                try
                {
                    context.Response.StatusCode = 500;
                    context.Response.Close();
                }
                catch { }
                Console.WriteLine($"[WebSocketServer] HTTP Error: {ex.Message}");
            }
        }

        private async Task ProcessWebSocketConnectionAsync(HttpListenerContext context, CancellationToken token)
        {
            WebSocketContext wsContext;
            try
            {
                try
                {
                    context.Response.Headers.Add("Access-Control-Allow-Origin", "*");
                    context.Response.Headers.Add("Access-Control-Allow-Private-Network", "true");
                }
                catch { }

                wsContext = await context.AcceptWebSocketAsync(subProtocol: null);
            }
            catch
            {
                try
                {
                    context.Response.StatusCode = 500;
                    context.Response.Close();
                }
                catch { }
                return;
            }

            var webSocket = wsContext.WebSocket;
            var tab = new ConnectedTab
            {
                TabId = "tab_" + Guid.NewGuid().ToString("N").Substring(0, 8),
                ConnectedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0,
                LastSeen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };

            _clients[webSocket] = tab;
            NotifyClientsChanged();

            byte[] buffer = new byte[16384];

            try
            {
                while (webSocket.State == WebSocketState.Open && !token.IsCancellationRequested)
                {
                    var result = await webSocket.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closed", token);
                        break;
                    }

                    if (result.MessageType == WebSocketMessageType.Text)
                    {
                        string jsonStr = Encoding.UTF8.GetString(buffer, 0, result.Count);
                        await HandleWebSocketMessageAsync(webSocket, tab, jsonStr);
                    }
                }
            }
            catch (Exception) { }
            finally
            {
                _clients.TryRemove(webSocket, out _);
                Log($"[Server] Chrome tab disconnected: {tab.DisplayTitle} [{tab.TabId}]", "INFO");
                NotifyClientsChanged();
            }
        }

        private async Task HandleWebSocketMessageAsync(WebSocket ws, ConnectedTab tab, string jsonText)
        {
            try
            {
                using var doc = JsonDocument.Parse(jsonText);
                var root = doc.RootElement;
                string action = root.TryGetProperty("action", out var aProp) ? aProp.GetString() ?? "" : "";
                if (string.IsNullOrEmpty(action) && root.TryGetProperty("type", out var tProp))
                {
                    action = tProp.GetString() ?? "";
                }

                tab.LastSeen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;

                if (action == "hello" || action == "HELLO" || action == "tab_init" || action == "register_tab" || action == "tab_update" || action == "status" || action == "register")
                {
                    if (root.TryGetProperty("tab_id", out var tid)) tab.TabId = tid.GetString() ?? tab.TabId;
                    if (root.TryGetProperty("clientId", out var cid)) tab.TabId = cid.GetString() ?? tab.TabId;
                    if (root.TryGetProperty("title", out var tit)) tab.Title = tit.GetString() ?? tab.Title;
                    if (root.TryGetProperty("url", out var u)) tab.Url = u.GetString() ?? tab.Url;
                    if (root.TryGetProperty("version", out var ver)) tab.Version = ver.GetString() ?? tab.Version;
                    if (root.TryGetProperty("page_type", out var pt)) tab.PageType = pt.GetString() ?? tab.PageType;
                    if (root.TryGetProperty("has_inputs", out var hi))
                    {
                        tab.HasInputs = hi.ValueKind == JsonValueKind.True || (hi.ValueKind == JsonValueKind.Number && hi.GetInt32() == 1);
                    }
                    if (root.TryGetProperty("screen_x", out var sx) && sx.TryGetInt32(out int scrX)) tab.ScreenX = scrX;
                    if (root.TryGetProperty("screen_y", out var sy) && sy.TryGetInt32(out int scrY)) tab.ScreenY = scrY;

                    Log($"[Server] Chrome tab synced: {tab.DisplayTitle} ({tab.Url}) [{tab.TabId}]", "SUCCESS");
                    NotifyClientsChanged(immediate: true);

                    // Send hello confirmation with latest extension build hash
                    var helloAck = new
                    {
                        type = "hello_ack",
                        action = "hello_ack",
                        status = "ok",
                        tab_id = tab.TabId,
                        build_hash = CurrentExtensionBuildHash,
                        timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
                    };
                    byte[] ackBytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(helloAck));
                    if (ws.State == WebSocketState.Open)
                    {
                        try { await ws.SendAsync(new ArraySegment<byte>(ackBytes), WebSocketMessageType.Text, true, CancellationToken.None); } catch { }
                    }
                }
                else if (action == "ping" || action == "SYNC_PING")
                {
                    long serverTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                    string pongJson = JsonSerializer.Serialize(new
                    {
                        type = "SYNC_PONG",
                        action = "pong",
                        serverTime = serverTime,
                        timestamp = serverTime / 1000.0
                    });
                    byte[] bytes = Encoding.UTF8.GetBytes(pongJson);
                    if (ws.State == WebSocketState.Open)
                    {
                        await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                    }
                }
                else if (action == "pong" || action == "SYNC_PONG")
                {
                    tab.LastSeen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
                }
                else if (action == "slot_ack" || action == "SLOT_ACK")
                {
                    string res = root.TryGetProperty("result", out var r) ? r.GetString() ?? "Success" : "Success";
                    int dur = root.TryGetProperty("duration_ms", out var d) ? d.GetInt32() : 0;
                    string target = root.TryGetProperty("target", out var tgt) ? tgt.GetString() ?? "" : "";

                    tab.LastResult = res;
                    tab.LastDurationMs = dur;
                    tab.RefreshCount++;

                    if (res == "Success") TotalAcksSuccess++;
                    else TotalAcksFailed++;

                    var dict = new Dictionary<string, object>
                    {
                        ["type"] = "slot_ack",
                        ["tab_id"] = tab.TabId,
                        ["result"] = res,
                        ["target"] = target,
                        ["duration_ms"] = dur
                    };
                    OnAckReceived?.Invoke(dict);
                    Log($"[Slot] Ack received from {tab.DisplayTitle} [{tab.TabId}] => {res}", "SUCCESS");
                    NotifyClientsChanged();
                }
                else if (action == "refresh_ack" || action == "REFRESH_ACK" || action == "ack")
                {
                    string res = root.TryGetProperty("result", out var r) ? r.GetString() ?? "Success" : "Success";
                    int dur = root.TryGetProperty("duration_ms", out var d) ? d.GetInt32() : 0;
                    string strat = root.TryGetProperty("strategy", out var s) ? s.GetString() ?? "" : "";

                    tab.LastResult = res;
                    tab.LastDurationMs = dur;
                    tab.LastStrategy = strat;
                    tab.RefreshCount++;

                    if (res == "Success") TotalAcksSuccess++;
                    else TotalAcksFailed++;

                    var dict = new Dictionary<string, object>
                    {
                        ["tab_id"] = tab.TabId,
                        ["result"] = res,
                        ["duration_ms"] = dur,
                        ["strategy"] = strat
                    };
                    OnAckReceived?.Invoke(dict);
                    NotifyClientsChanged();
                }
                else if (action == "thunder_config_ack")
                {
                    bool success = root.TryGetProperty("success", out var succ) && succ.GetBoolean();
                    bool confirmed = root.TryGetProperty("confirmed_by_extension", out var c) && c.GetBoolean();

                    var dict = new Dictionary<string, object>
                    {
                        ["type"] = "thunder_config_ack",
                        ["tab_id"] = tab.TabId,
                        ["success"] = success,
                        ["confirmed_by_extension"] = confirmed
                    };
                    OnAckReceived?.Invoke(dict);
                    Log($"[Thunder] Configuration verified on tab {tab.TabId.Substring(0, Math.Min(8, tab.TabId.Length))}: {(success ? "Success" : "Failed")}", success ? "SUCCESS" : "WARNING");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WebSocketServer] Parse message error: {ex.Message}");
            }
        }

        private async Task PingLoopAsync(CancellationToken token)
        {
            while (IsRunning && !token.IsCancellationRequested)
            {
                try
                {
                    await Task.Delay(10000, token);
                    if (!IsRunning || token.IsCancellationRequested) break;

                    long serverTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                    string pingJson = JsonSerializer.Serialize(new
                    {
                        type = "SYNC_PING",
                        action = "ping",
                        serverTime = serverTime,
                        timestamp = serverTime / 1000.0,
                        build_hash = CurrentExtensionBuildHash
                    });
                    byte[] bytes = Encoding.UTF8.GetBytes(pingJson);

                    foreach (var (ws, tab) in _clients)
                    {
                        if (ws.State == WebSocketState.Open)
                        {
                            try
                            {
                                await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                            }
                            catch { }
                        }
                    }
                }
                catch (OperationCanceledException) { break; }
                catch { }
            }
        }

        private void HandleAckPayload(Dictionary<string, object> data)
        {
            string tabId = data.TryGetValue("tab_id", out var tid) ? tid?.ToString() ?? "" : "";
            string res = data.TryGetValue("result", out var r) ? r?.ToString() ?? "Success" : "Success";
            int dur = 0;
            if (data.TryGetValue("duration_ms", out var d) && int.TryParse(d?.ToString(), out int val))
                dur = val;

            if (_httpClients.TryGetValue(tabId, out var tab))
            {
                tab.LastResult = res;
                tab.LastDurationMs = dur;
                tab.RefreshCount++;
                tab.LastSeen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            }

            if (res == "Success") TotalAcksSuccess++;
            else TotalAcksFailed++;

            OnAckReceived?.Invoke(data);
            NotifyClientsChanged();
        }

        public string BroadcastRefresh(string xpath, string text, string className, int staggerMs = 0)
        {
            TotalBroadcasts++;
            string cmdId = "cmd_" + Guid.NewGuid().ToString("N").Substring(0, 8);

            // Never allow targeting of external redirect / non-refresh buttons
            if (string.IsNullOrWhiteSpace(xpath) || xpath.Trim() == "/html/body/div[5]/div[1]/button[1]")
            {
                xpath = "//button[contains(normalize-space(.), 'Refresh') and not(contains(@id, 'redirect'))]";
            }

            var payload = new
            {
                action = "click_refresh",
                type = "CLICK_REFRESH",
                command_id = cmdId,
                xpath = xpath,
                text = text,
                class_name = className,
                stagger_ms = staggerMs,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };

            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            // WebSocket broadcast
            Task.Run(async () =>
            {
                int idx = 0;
                foreach (var ws in _clients.Keys)
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            if (staggerMs > 0 && idx > 0)
                            {
                                await Task.Delay(staggerMs);
                            }
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                            idx++;
                        }
                        catch { }
                    }
                }
            });

            // HTTP long-poll broadcast
            foreach (var kvp in _pollWaiters)
            {
                kvp.Value.TrySetResult(jsonStr);
            }

            int clientCount = _clients.Count + _httpClients.Count;
            Log($"[Server] Broadcasted Refresh command to {clientCount} connected tab(s).", "SUCCESS");
            return cmdId;
        }

        public string BroadcastThunderConfig(ThunderConfig config, List<string>? targetTabIds)
        {
            string cmdId = "thunder_" + Guid.NewGuid().ToString("N").Substring(0, 8);

            var payload = new
            {
                action = "thunder_config",
                type = "THUNDER_CONFIG",
                command_id = cmdId,
                config = config,
                settings = new
                {
                    region = config.Region,
                    vtData = new
                    {
                        city = config.VtData?.City,
                        category = config.VtData?.Category,
                        type = config.VtData?.Type,
                        members = config.VtData?.Members ?? 1
                    }
                },
                region = config.Region,
                vtData = new
                {
                    city = config.VtData?.City,
                    category = config.VtData?.Category,
                    type = config.VtData?.Type,
                    members = config.VtData?.Members ?? 1
                },
                target_tab_ids = targetTabIds,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };

            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            Task.Run(async () =>
            {
                foreach (var (ws, tab) in _clients)
                {
                    if (targetTabIds != null && targetTabIds.Count > 0 && !targetTabIds.Contains(tab.TabId))
                        continue;

                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                        }
                        catch { }
                    }
                }
            });

            foreach (var kvp in _pollWaiters)
            {
                if (targetTabIds == null || targetTabIds.Count == 0 || targetTabIds.Contains(kvp.Key))
                {
                    kvp.Value.TrySetResult(jsonStr);
                }
            }

            int targetCount = (targetTabIds != null && targetTabIds.Count > 0) ? targetTabIds.Count : (_clients.Count + _httpClients.Count);
            Log($"[Thunder] Dispatched ThunderBolt config to {targetCount} tab(s).", "SUCCESS");
            return cmdId;
        }

        public static bool IsPageA(ConnectedTab? tab)
        {
            if (tab == null) return false;
            if (tab.PageType == "a") return true;
            if (tab.PageType == "b") return false;

            string u = (tab.Url ?? "").ToLowerInvariant();
            string t = (tab.Title ?? "").ToLowerInvariant();

            if (t.Contains("too many requests") || t.Contains("recaptcha") || t.Contains("captcha") || t.Contains("login") || t.Contains("blocked") || t.Contains("forbidden"))
                return false;

            if (t.Contains("visa type") || t.Contains("visatype") || u.Contains("visatype") || u.Contains("visa-type") || u.Contains("favicon"))
                return false;

            return u.Contains("slotselection") || u.Contains("slot-selection") || u.Contains("slot_selection") ||
                   u.Contains("calendar") || t.Contains("slot selection") || t.Contains("slot") || t.Contains("calendar");
        }

        public static bool IsPageB(ConnectedTab? tab)
        {
            if (tab == null) return false;
            if (tab.PageType == "b") return true;
            if (tab.PageType == "a") return false;

            string u = (tab.Url ?? "").ToLowerInvariant();
            string t = (tab.Title ?? "").ToLowerInvariant();

            if (t.Contains("too many requests") || t.Contains("recaptcha") || t.Contains("captcha") || t.Contains("login") || t.Contains("blocked") || t.Contains("forbidden"))
                return false;

            if (tab.HasInputs) return true;

            return u.Contains("visatype") || u.Contains("visa-type") || u.Contains("visa_type") ||
                   u.Contains("favicon.png") || u.Contains("favicon") ||
                   t.Contains("visa type") || t.Contains("visatype");
        }

        public string BroadcastSlotClick(string target, int aSec, int aMs, int aStep, int bSec, int bMs, int bStep)
        {
            TotalBroadcasts++;
            string cmdId = "slot_" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            target = (target ?? "all").ToLowerInvariant();

            (int Sec, int Ms) Compute(int baseSec, int baseMs, int step, int idx)
            {
                int totalMs = baseMs + idx * step;
                int secOut = (baseSec + totalMs / 1000) % 60;
                int msOut = totalMs % 1000;
                return (secOut, msOut);
            }

            Task.Run(async () =>
            {
                int pageAIdx = 0;
                int pageBIdx = 0;

                foreach (var (ws, tab) in _clients)
                {
                    if (ws.State != WebSocketState.Open) continue;

                    bool isA = IsPageA(tab);
                    bool isB = IsPageB(tab);

                    // If neither is explicitly detected, treat by target
                    if (!isA && !isB)
                    {
                        if (target == "a") isA = true;
                        else if (target == "b") isB = true;
                        else { isA = true; isB = true; }
                    }

                    if (target == "a" && !isA) continue;
                    if (target == "b" && !isB) continue;

                    var resA = Compute(aSec, aMs, aStep, pageAIdx);
                    var resB = Compute(bSec, bMs, bStep, pageBIdx);

                    int sec_i = (target == "b" || (!isA && isB)) ? resB.Sec : resA.Sec;
                    int ms_i  = (target == "b" || (!isA && isB)) ? resB.Ms  : resA.Ms;

                    var payload = new
                    {
                        action = "slot_click",
                        type = "SLOT_CLICK",
                        target = target,
                        command_id = cmdId,
                        sec = sec_i,
                        ms = ms_i,
                        page_a_sec = resA.Sec,
                        page_a_ms = resA.Ms,
                        page_b_sec = resB.Sec,
                        page_b_ms = resB.Ms,
                        timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
                    };

                    string json = JsonSerializer.Serialize(payload);
                    byte[] bytes = Encoding.UTF8.GetBytes(json);
                    try
                    {
                        await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                    }
                    catch { }

                    if (isA) pageAIdx++;
                    if (isB) pageBIdx++;
                }
            });

            // HTTP poll waiters (same per-page modifier isolation)
            int httpPageAIdx = 0;
            int httpPageBIdx = 0;

            foreach (var kvp in _pollWaiters)
            {
                _httpClients.TryGetValue(kvp.Key, out var tab);
                bool isA = IsPageA(tab);
                bool isB = IsPageB(tab);

                if (!isA && !isB)
                {
                    if (target == "a") isA = true;
                    else if (target == "b") isB = true;
                    else { isA = true; isB = true; }
                }

                if (target == "a" && !isA) continue;
                if (target == "b" && !isB) continue;

                var rA = Compute(aSec, aMs, aStep, httpPageAIdx);
                var rB = Compute(bSec, bMs, bStep, httpPageBIdx);

                int sec_i = (target == "b" || (!isA && isB)) ? rB.Sec : rA.Sec;
                int ms_i  = (target == "b" || (!isA && isB)) ? rB.Ms  : rA.Ms;

                var payload = new
                {
                    action = "slot_click",
                    type = "SLOT_CLICK",
                    target = target,
                    command_id = cmdId,
                    sec = sec_i,
                    ms = ms_i,
                    page_a_sec = rA.Sec,
                    page_a_ms = rA.Ms,
                    page_b_sec = rB.Sec,
                    page_b_ms = rB.Ms,
                    timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
                };
                kvp.Value.TrySetResult(JsonSerializer.Serialize(payload));

                if (isA) httpPageAIdx++;
                if (isB) httpPageBIdx++;
            }

            int count = _clients.Count + _httpClients.Count;
            Log($"[SlotClick] Dispatched Slot-Click ({target.ToUpper()}) to {count} connected tab(s) with isolated per-page modifier.", "SUCCESS");
            return cmdId;
        }

        public string BroadcastHardReload(int staggerMs = 0)
        {
            TotalBroadcasts++;
            string cmdId = "reload_" + Guid.NewGuid().ToString("N").Substring(0, 8);

            var payload = new
            {
                action = "hard_reload",
                type = "HARD_RELOAD",
                command_id = cmdId,
                reloadFallback = true,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };

            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            Task.Run(async () =>
            {
                int idx = 0;
                foreach (var ws in _clients.Keys)
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            if (staggerMs > 0 && idx > 0)
                            {
                                await Task.Delay(staggerMs);
                            }
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                            idx++;
                        }
                        catch { }
                    }
                }
            });

            foreach (var kvp in _pollWaiters)
            {
                kvp.Value.TrySetResult(jsonStr);
            }

            int clientCount = _clients.Count + _httpClients.Count;
            Log($"[Server] Dispatched Hard Reload broadcast to {clientCount} connected tab(s).", "WARNING");
            return cmdId;
        }

        public string BroadcastReloadExtension()
        {
            TotalBroadcasts++;
            UpdateExtensionBuildHash();
            string cmdId = "reload_ext_" + Guid.NewGuid().ToString("N").Substring(0, 8);

            var payload = new
            {
                action = "reload_extension",
                type = "RELOAD_EXTENSION",
                command_id = cmdId,
                build_hash = CurrentExtensionBuildHash,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };

            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            Task.Run(async () =>
            {
                foreach (var ws in _clients.Keys)
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                        }
                        catch { }
                    }
                }
            });

            foreach (var kvp in _pollWaiters)
            {
                kvp.Value.TrySetResult(jsonStr);
            }

            int count = _clients.Count + _httpClients.Count;
            Log($"[Extension] Sent zero-click auto-reload command to {count} connected Chrome profile(s).", "SUCCESS");
            return cmdId;
        }

        public void BroadcastOpenTab(string url)
        {
            var payload = new
            {
                action = "open_tab",
                type = "OPEN_TAB",
                url = url
            };
            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            Task.Run(async () =>
            {
                foreach (var ws in _clients.Keys)
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                        }
                        catch { }
                    }
                }
            });
        }

        public void PingAllTabs()
        {
            var payload = new
            {
                action = "ping",
                type = "SYNC_PING",
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };
            string jsonStr = JsonSerializer.Serialize(payload);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonStr);

            Task.Run(async () =>
            {
                foreach (var ws in _clients.Keys)
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        try
                        {
                            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                        }
                        catch { }
                    }
                }
            });
            Log("[Server] Ping dispatched to all connected Chrome tabs.", "INFO");
        }

        public List<ConnectedTab> GetClientsSnapshot()
        {
            var list = new List<ConnectedTab>();
            list.AddRange(_clients.Values);
            list.AddRange(_httpClients.Values);
            return list;
        }

        public void PruneStaleHttpClients()
        {
            double now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            foreach (var kvp in _httpClients)
            {
                if (now - kvp.Value.LastSeen > 35.0)
                {
                    _httpClients.TryRemove(kvp.Key, out _);
                }
            }
        }

        private void NotifyClientsChanged(bool immediate = false)
        {
            lock (_debounceLock)
            {
                double elapsedMs = (DateTime.UtcNow - _lastNotifyTime).TotalMilliseconds;
                if (immediate || elapsedMs >= 400)
                {
                    _lastNotifyTime = DateTime.UtcNow;
                    _notifyPending = false;
                    _debounceTimer?.Dispose();
                    _debounceTimer = null;
                    DispatchClientsChanged();
                }
                else if (!_notifyPending)
                {
                    _notifyPending = true;
                    int delay = Math.Max(50, 400 - (int)elapsedMs);
                    _debounceTimer?.Dispose();
                    _debounceTimer = new System.Threading.Timer(_ =>
                    {
                        lock (_debounceLock)
                        {
                            _lastNotifyTime = DateTime.UtcNow;
                            _notifyPending = false;
                            _debounceTimer?.Dispose();
                            _debounceTimer = null;
                        }
                        DispatchClientsChanged();
                    }, null, delay, Timeout.Infinite);
                }
            }
        }

        private void DispatchClientsChanged()
        {
            PruneStaleHttpClients();
            var snapshot = GetClientsSnapshot();
            OnClientsChanged?.Invoke(snapshot.Count, snapshot);
        }

        private void Log(string msg, string level)
        {
            OnLog?.Invoke(msg, level);
        }
    }
}

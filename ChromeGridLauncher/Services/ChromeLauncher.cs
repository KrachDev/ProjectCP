using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class ChromeLauncher
    {
        public static readonly string[] ChromePerfFlags = new[]
        {
            // V8 JavaScript Memory Capping & Aggressive Garbage Collection (stops 30GB+ memory explosion)
            "--js-flags=\"--max-old-space-size=256 --expose-gc\"",

            // Audio & Background Thread Reductions (saves ~100 threads across 50 profiles)
            "--mute-audio",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-client-side-phishing-detection",
            "--disable-speech-api",
            "--disable-breakpad",
            "--num-raster-threads=1",
            "--disable-smooth-scrolling",

            // Anti-throttling & Real-time Execution in Background/Occluded Windows
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion,Translate,OptimizationHints,MediaRouter,DialMediaRouteProvider,CastMediaRouteProvider,AutofillServerCommunication,ChromeLabs,InterestFeedContentSuggestions,PrivateNetworkAccessSendPreflights,PrivateNetworkAccessRespectPreflightResults",
            "--disable-hang-monitor",
            "--disable-dev-shm-usage",

            // Anti-lag & Concurrency Optimizations
            "--disable-ipc-flooding-protection",
            "--disable-search-engine-choice-screen",
            "--disable-logging",
            "--log-level=3"
        };

        public static string? GetExtensionDirectory()
        {
            try
            {
                return ExtensionDeploymentService.EnsureExtensionDeployed();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ChromeLauncher] Error ensuring extension: {ex.Message}");
                return null;
            }
        }

        public static IntPtr LaunchAndPosition(
            string chromeExe,
            string profileKey,
            int x,
            int y,
            int w,
            int h,
            double timeoutSeconds = 8.0,
            bool reuseExisting = false,
            bool dwmCompensation = true,
            int dwmBorderOffset = 7,
            HashSet<IntPtr>? alreadyManagedHwnds = null,
            bool enableNativeExtension = true,
            string? targetExeName = null)
        {
            string exeName = !string.IsNullOrWhiteSpace(targetExeName)
                ? Path.GetFileName(targetExeName).ToLowerInvariant()
                : (!string.IsNullOrWhiteSpace(chromeExe) ? Path.GetFileName(chromeExe).ToLowerInvariant() : "chrome.exe");

            if (string.IsNullOrWhiteSpace(chromeExe) || !File.Exists(chromeExe))
            {
                chromeExe = exeName switch
                {
                    "brave.exe" => ChromeProfileScanner.FindBraveExecutable(),
                    "msedge.exe" => ChromeProfileScanner.FindEdgeExecutable(),
                    _ => ChromeProfileScanner.FindChromeExecutable()
                };
            }

            var existingWindows = WindowPlacementService.GetBrowserWindows(exeName);
            var existingHwnds = new HashSet<IntPtr>(existingWindows.Select(w => w.Hwnd));
            if (alreadyManagedHwnds != null)
            {
                foreach (var hMan in alreadyManagedHwnds)
                    existingHwnds.Add(hMan);
            }

            var argsList = new List<string>
            {
                $"--profile-directory=\"{profileKey}\"",
                $"--window-position={x},{y}",
                $"--window-size={w},{h}"
            };

            argsList.AddRange(ChromePerfFlags);

            // Auto-load stealth native Chrome extension & Phylakon
            if (enableNativeExtension)
            {
                string phylakonDir = @"C:\Users\krach\Documents\BLS Project\Phylakon";
                string? extDir = GetExtensionDirectory();
                var loadedExts = new List<string>();
                if (Directory.Exists(phylakonDir)) loadedExts.Add(phylakonDir);
                if (!string.IsNullOrEmpty(extDir) && Directory.Exists(extDir) && !extDir.Equals(phylakonDir, StringComparison.OrdinalIgnoreCase))
                {
                    loadedExts.Add(extDir);
                }
                if (loadedExts.Count > 0)
                {
                    argsList.Add($"--load-extension=\"{string.Join(",", loadedExts)}\"");
                }
            }

            // For ultra-dense grids where cell width < 260px, gently adjust device scale factor
            if (w > 0 && w < 260)
            {
                double scale = Math.Round(Math.Clamp(w / 300.0, 0.50, 1.0), 2);
                argsList.Add($"--force-device-scale-factor={scale.ToString(System.Globalization.CultureInfo.InvariantCulture)}");
            }

            if (!reuseExisting)
            {
                argsList.Add("--new-window");
            }

            string fullArgs = string.Join(" ", argsList);

            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = chromeExe,
                    Arguments = fullArgs,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ChromeLauncher] Failed to launch {exeName}: {ex.Message}");
                return IntPtr.Zero;
            }

            // Poll for new window
            var stopwatch = Stopwatch.StartNew();
            IntPtr targetHwnd = IntPtr.Zero;
            List<(IntPtr Hwnd, string Title, WindowPlacementService.RECT Rect)> currentWindows = new();

            while (stopwatch.Elapsed.TotalSeconds < timeoutSeconds)
            {
                Thread.Sleep(120);

                currentWindows = WindowPlacementService.GetBrowserWindows(exeName);
                var currentHwnds = currentWindows.Select(cw => cw.Hwnd);
                var newHwnds = currentHwnds.Where(hwnd => !existingHwnds.Contains(hwnd)).ToList();

                if (newHwnds.Count > 0)
                {
                    targetHwnd = newHwnds[0];
                    break;
                }
            }

            // Fallback: check foreground window or unmanaged browser window
            if (targetHwnd == IntPtr.Zero)
            {
                IntPtr fgHwnd = WindowPlacementService.GetForegroundWindow();
                if (fgHwnd != IntPtr.Zero && WindowPlacementService.IsBrowserWindow(fgHwnd, exeName) && !existingHwnds.Contains(fgHwnd))
                {
                    targetHwnd = fgHwnd;
                }
                else if (currentWindows.Count > 0)
                {
                    var unmanaged = currentWindows.Where(cw => !existingHwnds.Contains(cw.Hwnd)).ToList();
                    if (unmanaged.Count > 0)
                    {
                        targetHwnd = unmanaged[0].Hwnd;
                    }
                }
            }

            if (targetHwnd != IntPtr.Zero)
            {
                WindowPlacementService.PositionWindow(
                    targetHwnd,
                    x,
                    y,
                    w,
                    h,
                    dwmCompensation: dwmCompensation,
                    dwmBorderOffset: dwmBorderOffset
                );
                return targetHwnd;
            }

            return IntPtr.Zero;
        }

        public static int CloseManagedWindows(
            HashSet<IntPtr> managedHwnds,
            string protectedProfileKey,
            string protectedProfileName = "",
            string? targetExeName = null)
        {
            string? exeFilter = !string.IsNullOrWhiteSpace(targetExeName) ? Path.GetFileName(targetExeName).ToLowerInvariant() : null;
            var activeWindows = WindowPlacementService.GetBrowserWindows(exeFilter);
            if (activeWindows.Count == 0 && managedHwnds.Count == 0)
                return 0;

            bool hasManaged = managedHwnds.Count > 0;
            var candidateHwnds = new HashSet<IntPtr>();

            if (hasManaged)
            {
                foreach (var h in managedHwnds)
                {
                    if (WindowPlacementService.IsWindow(h) && WindowPlacementService.IsBrowserWindow(h, exeFilter))
                        candidateHwnds.Add(h);
                }
            }
            else
            {
                foreach (var (h, _, _) in activeWindows)
                    candidateHwnds.Add(h);
            }

            int closedCount = 0;
            foreach (var hwnd in candidateHwnds)
            {
                if (!WindowPlacementService.IsBrowserWindow(hwnd, exeFilter))
                    continue;

                // Protect personal profile from being closed
                bool isProt = false;
                string? winProf = WindowPlacementService.GetChromeWindowProfileKey(hwnd);
                if (!string.IsNullOrWhiteSpace(protectedProfileKey) &&
                    !string.IsNullOrWhiteSpace(winProf) &&
                    string.Equals(winProf, protectedProfileKey, StringComparison.OrdinalIgnoreCase))
                {
                    isProt = true;
                }
                else if (!string.IsNullOrWhiteSpace(protectedProfileName))
                {
                    var sb = new System.Text.StringBuilder(512);
                    WindowPlacementService.GetWindowText(hwnd, sb, sb.Capacity);
                    string title = sb.ToString();
                    if (title.Contains(protectedProfileName, StringComparison.OrdinalIgnoreCase))
                        isProt = true;
                }

                if (isProt) continue;

                if (WindowPlacementService.CloseChromeWindow(hwnd))
                {
                    closedCount++;
                }
            }

            managedHwnds.RemoveWhere(h => !WindowPlacementService.IsWindow(h));
            return closedCount;
        }
    }
}

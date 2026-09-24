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
            bool enableNativeExtension = true)
        {
            if (string.IsNullOrWhiteSpace(chromeExe) || !File.Exists(chromeExe))
            {
                chromeExe = ChromeProfileScanner.FindChromeExecutable();
            }

            var existingWindows = WindowPlacementService.GetChromeWindows();
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

            // Auto-load stealth native Chrome extension (Option B: Zero-Install, isolated context, no CDP)
            if (enableNativeExtension)
            {
                string? extDir = GetExtensionDirectory();
                if (!string.IsNullOrEmpty(extDir))
                {
                    argsList.Add($"--load-extension=\"{extDir}\"");
                }
            }

            // Chrome has an OS-level minimum window width (~516px on Windows at 100% DPI).
            // For high-density grids where cell width < 500px (e.g. 10 columns or narrow monitors),
            // force device scale factor to scale Chrome controls down so it can shrink cleanly without overlapping.
            if (w < 500)
            {
                double scale = Math.Round(Math.Clamp((w - 10) / 490.0, 0.40, 1.0), 2);
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
                Console.WriteLine($"[ChromeLauncher] Failed to launch Chrome: {ex.Message}");
                return IntPtr.Zero;
            }

            // Poll for new window
            var stopwatch = Stopwatch.StartNew();
            IntPtr targetHwnd = IntPtr.Zero;
            List<(IntPtr Hwnd, string Title, WindowPlacementService.RECT Rect)> currentWindows = new();

            while (stopwatch.Elapsed.TotalSeconds < timeoutSeconds)
            {
                Thread.Sleep(120);

                currentWindows = WindowPlacementService.GetChromeWindows();
                var currentHwnds = currentWindows.Select(cw => cw.Hwnd);
                var newHwnds = currentHwnds.Where(hwnd => !existingHwnds.Contains(hwnd)).ToList();

                if (newHwnds.Count > 0)
                {
                    targetHwnd = newHwnds[0];
                    break;
                }
            }

            // Fallback: check foreground window or unmanaged Chrome window
            if (targetHwnd == IntPtr.Zero)
            {
                IntPtr fgHwnd = WindowPlacementService.GetForegroundWindow();
                if (fgHwnd != IntPtr.Zero && WindowPlacementService.IsChromeWindow(fgHwnd) && !existingHwnds.Contains(fgHwnd))
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
            string protectedProfileName = "")
        {
            var activeWindows = WindowPlacementService.GetChromeWindows();
            if (activeWindows.Count == 0 && managedHwnds.Count == 0)
                return 0;

            bool hasManaged = managedHwnds.Count > 0;
            var candidateHwnds = new HashSet<IntPtr>();

            if (hasManaged)
            {
                foreach (var h in managedHwnds)
                {
                    if (WindowPlacementService.IsWindow(h) && WindowPlacementService.IsChromeWindow(h))
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
                if (!WindowPlacementService.IsChromeWindow(hwnd))
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

            managedHwnds.Clear();
            return closedCount;
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class WindowPlacementService
    {
        #region Win32 P/Invoke Definitions

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;

            public int Width => Math.Max(0, Right - Left);
            public int Height => Math.Max(0, Bottom - Top);
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        public struct MONITORINFOEX
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public uint dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
            public string szDevice;
        }

        public const uint MONITORINFOF_PRIMARY = 1;
        public const uint SWP_NOZORDER = 0x0004;
        public const uint SWP_NOACTIVATE = 0x0010;
        public const uint SWP_SHOWWINDOW = 0x0040;
        public const int DWMWA_EXTENDED_FRAME_BOUNDS = 9;
        public const int SW_RESTORE = 9;
        public const int SW_SHOWMINIMIZED = 2;
        public const int SW_SHOWMAXIMIZED = 3;
        public const uint WM_CLOSE = 0x0010;
        public const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
        public static readonly IntPtr HWND_TOP = IntPtr.Zero;

        public delegate bool MonitorEnumDelegate(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumDelegate lpfnEnum, IntPtr dwData);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFOEX lpmi);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("dwmapi.dll")]
        public static extern int DwmGetWindowAttribute(IntPtr hwnd, int dwAttribute, out RECT pvAttribute, int cbAttribute);

        [DllImport("user32.dll")]
        public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("user32.dll")]
        public static extern bool IsWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool IsIconic(IntPtr hWnd);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern IntPtr OpenProcess(uint processAccess, bool bInheritHandle, uint processId);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern bool QueryFullProcessImageNameW(IntPtr hProcess, int flags, StringBuilder text, ref int size);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool CloseHandle(IntPtr hObject);

        [DllImport("ntdll.dll")]
        public static extern int NtQueryInformationProcess(IntPtr processHandle, int processInformationClass, IntPtr processInformation, int processInformationLength, out int returnLength);

        [StructLayout(LayoutKind.Sequential)]
        public struct UNICODE_STRING
        {
            public ushort Length;
            public ushort MaximumLength;
            public IntPtr Buffer;
        }

        #endregion

        public static List<MonitorInfo> GetMonitors()
        {
            var monitors = new List<MonitorInfo>();
            int index = 0;

            EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, (IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData) =>
            {
                var mi = new MONITORINFOEX();
                mi.cbSize = Marshal.SizeOf(mi);
                if (GetMonitorInfo(hMonitor, ref mi))
                {
                    monitors.Add(new MonitorInfo
                    {
                        Index = index++,
                        HMonitor = hMonitor,
                        DeviceName = mi.szDevice,
                        Left = mi.rcMonitor.Left,
                        Top = mi.rcMonitor.Top,
                        Right = mi.rcMonitor.Right,
                        Bottom = mi.rcMonitor.Bottom,
                        WorkLeft = mi.rcWork.Left,
                        WorkTop = mi.rcWork.Top,
                        WorkRight = mi.rcWork.Right,
                        WorkBottom = mi.rcWork.Bottom,
                        IsPrimary = (mi.dwFlags & MONITORINFOF_PRIMARY) != 0
                    });
                }
                return true;
            }, IntPtr.Zero);

            if (monitors.Count == 0)
            {
                monitors.Add(new MonitorInfo
                {
                    Index = 0,
                    HMonitor = IntPtr.Zero,
                    DeviceName = "DefaultDisplay",
                    Left = 0,
                    Top = 0,
                    Right = 1920,
                    Bottom = 1080,
                    WorkLeft = 0,
                    WorkTop = 0,
                    WorkRight = 1920,
                    WorkBottom = 1040,
                    IsPrimary = true
                });
            }

            return monitors;
        }

        public static (int leftInset, int topInset, int rightInset, int bottomInset) GetWindowShadowInsets(IntPtr hwnd, int defaultOffset = 7)
        {
            try
            {
                if (hwnd != IntPtr.Zero && GetWindowRect(hwnd, out RECT winRect))
                {
                    if (DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, out RECT frameRect, Marshal.SizeOf(typeof(RECT))) == 0)
                    {
                        int sLeft = Math.Max(0, frameRect.Left - winRect.Left);
                        int sTop = Math.Max(0, frameRect.Top - winRect.Top);
                        int sRight = Math.Max(0, winRect.Right - frameRect.Right);
                        int sBottom = Math.Max(0, winRect.Bottom - frameRect.Bottom);

                        if (sLeft >= 0 && sLeft <= 40 && sRight >= 0 && sRight <= 40 && sBottom >= 0 && sBottom <= 40)
                        {
                            return (sLeft, sTop, sRight, sBottom);
                        }
                    }
                }
            }
            catch { }

            return (defaultOffset, 0, defaultOffset, defaultOffset);
        }

        public static (int x, int y, int w, int h) CalculateCellRect(
            MonitorInfo monitor,
            int rows,
            int cols,
            int row,
            int col,
            int gap = 4,
            bool useFullScreen = false,
            ScreenMargins? margins = null,
            Dictionary<string, CellOffset>? cellOffsets = null,
            List<double>? colWeights = null,
            List<double>? rowWeights = null)
        {
            rows = Math.Max(1, rows);
            cols = Math.Max(1, cols);
            row = Math.Clamp(row, 0, rows - 1);
            col = Math.Clamp(col, 0, cols - 1);

            int bLeft = useFullScreen ? monitor.Left : monitor.WorkLeft;
            int bTop = useFullScreen ? monitor.Top : monitor.WorkTop;
            int bRight = useFullScreen ? monitor.Right : monitor.WorkRight;
            int bBottom = useFullScreen ? monitor.Bottom : monitor.WorkBottom;

            margins ??= new ScreenMargins();
            int areaLeft = bLeft + margins.Left;
            int areaTop = bTop + margins.Top;
            int areaRight = bRight - margins.Right;
            int areaBottom = bBottom - margins.Bottom;

            int areaW = Math.Max(cols * 20, areaRight - areaLeft);
            int areaH = Math.Max(rows * 20, areaBottom - areaTop);

            int totalGapW = gap * (cols - 1);
            int totalGapH = gap * (rows - 1);

            int availW = Math.Max(cols * 10, areaW - totalGapW);
            int availH = Math.Max(rows * 10, areaH - totalGapH);

            // Column Widths
            int[] colWidths = new int[cols];
            if (colWeights != null && colWeights.Count == cols && colWeights.Sum() > 0)
            {
                double totalCw = colWeights.Sum();
                for (int i = 0; i < cols; i++)
                {
                    colWidths[i] = (int)(availW * (colWeights[i] / totalCw));
                }
                int diffW = availW - colWidths.Sum();
                for (int i = 0; i < diffW; i++)
                {
                    colWidths[i % cols]++;
                }
            }
            else
            {
                int baseW = availW / cols;
                int remW = availW % cols;
                for (int c = 0; c < cols; c++)
                {
                    colWidths[c] = baseW + (c < remW ? 1 : 0);
                }
            }

            int[] colXOffsets = new int[cols];
            int curX = areaLeft;
            for (int c = 0; c < cols; c++)
            {
                colXOffsets[c] = curX;
                curX += colWidths[c] + gap;
            }

            // Row Heights
            int[] rowHeights = new int[rows];
            if (rowWeights != null && rowWeights.Count == rows && rowWeights.Sum() > 0)
            {
                double totalRw = rowWeights.Sum();
                for (int i = 0; i < rows; i++)
                {
                    rowHeights[i] = (int)(availH * (rowWeights[i] / totalRw));
                }
                int diffH = availH - rowHeights.Sum();
                for (int i = 0; i < diffH; i++)
                {
                    rowHeights[i % rows]++;
                }
            }
            else
            {
                int baseH = availH / rows;
                int remH = availH % rows;
                for (int r = 0; r < rows; r++)
                {
                    rowHeights[r] = baseH + (r < remH ? 1 : 0);
                }
            }

            int[] rowYOffsets = new int[rows];
            int curY = areaTop;
            for (int r = 0; r < rows; r++)
            {
                rowYOffsets[r] = curY;
                curY += rowHeights[r] + gap;
            }

            int x = colXOffsets[col];
            int y = rowYOffsets[row];
            int w = colWidths[col];
            int h = rowHeights[row];

            // Per-cell fine offsets
            if (cellOffsets != null)
            {
                string cKey = $"{row},{col}";
                if (cellOffsets.TryGetValue(cKey, out var offset) && offset != null)
                {
                    x += offset.Dx;
                    y += offset.Dy;
                    w = Math.Max(10, w + offset.Dw);
                    h = Math.Max(10, h + offset.Dh);
                }
            }

            return (x, y, w, h);
        }

        public static bool IsChromeWindow(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero || !IsWindow(hwnd) || !IsWindowVisible(hwnd))
                return false;

            try
            {
                var sbClass = new StringBuilder(256);
                GetClassName(hwnd, sbClass, sbClass.Capacity);
                if (sbClass.ToString() != "Chrome_WidgetWin_1")
                    return false;

                GetWindowThreadProcessId(hwnd, out uint pid);
                if (pid == 0) return false;

                IntPtr hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
                if (hProc != IntPtr.Zero)
                {
                    try
                    {
                        var sbPath = new StringBuilder(1024);
                        int size = sbPath.Capacity;
                        if (QueryFullProcessImageNameW(hProc, 0, sbPath, ref size))
                        {
                            string exeName = Path.GetFileName(sbPath.ToString()).ToLowerInvariant();
                            return exeName == "chrome.exe";
                        }
                    }
                    finally
                    {
                        CloseHandle(hProc);
                    }
                }
            }
            catch { }

            return false;
        }

        public static string? GetChromeWindowProfileKey(IntPtr hwnd)
        {
            try
            {
                GetWindowThreadProcessId(hwnd, out uint pid);
                if (pid == 0) return null;

                IntPtr hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
                if (hProc == IntPtr.Zero) return null;

                try
                {
                    int bufSize = 4096;
                    IntPtr pBuf = Marshal.AllocHGlobal(bufSize);
                    try
                    {
                        // ProcessCommandLineInformation = 60
                        int status = NtQueryInformationProcess(hProc, 60, pBuf, bufSize, out int retLen);
                        if (status == 0)
                        {
                            var unicodeString = Marshal.PtrToStructure<UNICODE_STRING>(pBuf);
                            if (unicodeString.Buffer != IntPtr.Zero)
                            {
                                string cmdLine = Marshal.PtrToStringUni(unicodeString.Buffer, unicodeString.Length / 2) ?? "";
                                var match = Regex.Match(cmdLine, @"--profile-directory=(?:[""']([^""']+)[""']|([^\s]+))");
                                if (match.Success)
                                {
                                    return !string.IsNullOrWhiteSpace(match.Groups[1].Value) ? match.Groups[1].Value : match.Groups[2].Value;
                                }
                            }
                        }
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(pBuf);
                    }
                }
                finally
                {
                    CloseHandle(hProc);
                }
            }
            catch { }

            return null;
        }

        public static List<(IntPtr Hwnd, string Title, RECT Rect)> GetChromeWindows()
        {
            var results = new List<(IntPtr, string, RECT)>();

            EnumWindows((hwnd, lParam) =>
            {
                if (IsWindowVisible(hwnd) && !IsIconic(hwnd))
                {
                    if (IsChromeWindow(hwnd))
                    {
                        if (GetWindowRect(hwnd, out RECT rect))
                        {
                            if (rect.Width > 200 && rect.Height > 150)
                            {
                                var sbTitle = new StringBuilder(512);
                                GetWindowText(hwnd, sbTitle, sbTitle.Capacity);
                                results.Add((hwnd, sbTitle.ToString(), rect));
                            }
                        }
                    }
                }
                return true;
            }, IntPtr.Zero);

            return results;
        }

        public static void PositionWindow(
            IntPtr hwnd,
            int x,
            int y,
            int w,
            int h,
            bool dwmCompensation = true,
            int dwmBorderOffset = 7)
        {
            if (hwnd == IntPtr.Zero) return;

            try
            {
                ShowWindow(hwnd, SW_RESTORE);
                Thread.Sleep(50);

                int posX = x;
                int posY = y;
                int posW = w;
                int posH = h;

                if (dwmCompensation)
                {
                    var (sLeft, sTop, sRight, sBottom) = GetWindowShadowInsets(hwnd, dwmBorderOffset);
                    posX = x - sLeft;
                    posY = y - sTop;
                    posW = w + sLeft + sRight;
                    posH = h + sTop + sBottom;
                }

                // SWP_NOACTIVATE prevents 50 windows from stealing focus and freezing the Windows shell
                SetWindowPos(
                    hwnd,
                    HWND_TOP,
                    posX,
                    posY,
                    posW,
                    posH,
                    SWP_SHOWWINDOW | SWP_NOACTIVATE
                );

                // Second pass after paint completes ensures stable final coordinates
                Thread.Sleep(40);
                SetWindowPos(
                    hwnd,
                    HWND_TOP,
                    posX,
                    posY,
                    posW,
                    posH,
                    SWP_NOACTIVATE
                );
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WindowPlacementService] Failed to position hwnd {hwnd}: {ex.Message}");
            }
        }

        public static bool CloseChromeWindow(IntPtr hwnd)
        {
            if (hwnd != IntPtr.Zero && IsWindow(hwnd))
            {
                return PostMessage(hwnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
            }
            return false;
        }

        public const uint WM_KEYDOWN = 0x0100;
        public const uint WM_KEYUP = 0x0101;
        public const int VK_F5 = 0x74;

        public static bool SendHardReload(IntPtr hwnd)
        {
            if (hwnd != IntPtr.Zero && IsWindow(hwnd))
            {
                try
                {
                    PostMessage(hwnd, WM_KEYDOWN, (IntPtr)VK_F5, IntPtr.Zero);
                    PostMessage(hwnd, WM_KEYUP, (IntPtr)VK_F5, IntPtr.Zero);
                    return true;
                }
                catch
                {
                    return false;
                }
            }
            return false;
        }
    }
}

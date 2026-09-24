using System;

namespace ChromeGridLauncher.Models
{
    public class MonitorInfo
    {
        public int Index { get; set; }
        public IntPtr HMonitor { get; set; }
        public string DeviceName { get; set; } = "Display";
        public int Left { get; set; }
        public int Top { get; set; }
        public int Right { get; set; }
        public int Bottom { get; set; }
        public int WorkLeft { get; set; }
        public int WorkTop { get; set; }
        public int WorkRight { get; set; }
        public int WorkBottom { get; set; }
        public bool IsPrimary { get; set; }

        public int Width => Math.Max(1, Right - Left);
        public int Height => Math.Max(1, Bottom - Top);
        public int WorkWidth => Math.Max(1, WorkRight - WorkLeft);
        public int WorkHeight => Math.Max(1, WorkBottom - WorkTop);

        public string DisplayLabel
        {
            get
            {
                string prim = IsPrimary ? " (Primary)" : "";
                return $"Monitor {Index + 1}: {Width}×{Height}{prim}";
            }
        }
    }
}

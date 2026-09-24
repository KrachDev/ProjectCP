using System.Collections.Generic;

namespace ChromeGridLauncher.Models
{
    public class ScreenMargins
    {
        public int Top { get; set; } = 0;
        public int Bottom { get; set; } = 0;
        public int Left { get; set; } = 0;
        public int Right { get; set; } = 0;
    }

    public class CellOffset
    {
        public int Dx { get; set; } = 0;
        public int Dy { get; set; } = 0;
        public int Dw { get; set; } = 0;
        public int Dh { get; set; } = 0;
    }

    public class AppSettings
    {
        public string Theme { get; set; } = "Dark";
        public int MonitorIndex { get; set; } = 0;
        public int CellGap { get; set; } = 0;
        public double WindowTimeout { get; set; } = 8.0;
        public int LaunchInterval { get; set; } = 400;
        public bool ReuseExisting { get; set; } = false;
        public int CustomRows { get; set; } = 2;
        public int CustomCols { get; set; } = 2;
        public string ChromePathOverride { get; set; } = string.Empty;
        public string ProtectedProfileKey { get; set; } = "Default";
        public bool UseFullScreen { get; set; } = false;
        public ScreenMargins ScreenMargins { get; set; } = new();
        public bool DwmCompensation { get; set; } = true;
        public int DwmBorderOffset { get; set; } = 7;
        public Dictionary<string, CellOffset> CellOffsets { get; set; } = new();
        public List<double> ColWeights { get; set; } = new();
        public List<double> RowWeights { get; set; } = new();
        public int RefreshServerPort { get; set; } = 8765;
        public bool AutoStartRefreshServer { get; set; } = true;
        public bool SoundAlertsEnabled { get; set; } = true;
        public bool MinimizeOnLaunch { get; set; } = false;
        public bool EnableNativeExtension { get; set; } = true;
        public string TargetRefreshUrl { get; set; } = "https://spain.blsspainmorocco.net/";
        public string RefreshXPath { get; set; } = "/html/body/div[5]/div[1]/button[1]";
        public string RefreshText { get; set; } = "Refresh";
        public string RefreshClassName { get; set; } = "btn btn-primary";
        public int StaggerMs { get; set; } = 0;
        public string AutoRefreshChoice { get; set; } = "Off";
    }
}

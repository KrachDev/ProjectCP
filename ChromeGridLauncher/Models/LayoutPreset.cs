using System.Collections.Generic;

namespace ChromeGridLauncher.Models
{
    public class CellAssignmentData
    {
        public string Key { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string DisplayName { get; set; } = string.Empty;
    }

    public class LayoutPreset
    {
        public string Name { get; set; } = "Unnamed";
        public string UpdatedAt { get; set; } = string.Empty;
        public int Rows { get; set; } = 2;
        public int Cols { get; set; } = 2;
        public int MonitorIndex { get; set; } = 0;
        public bool UseFullScreen { get; set; } = false;
        public ScreenMargins ScreenMargins { get; set; } = new();
        public int CellGap { get; set; } = 0;
        public bool DwmCompensation { get; set; } = true;
        public int DwmBorderOffset { get; set; } = 7;
        public Dictionary<string, CellOffset> CellOffsets { get; set; } = new();
        public List<double> ColWeights { get; set; } = new();
        public List<double> RowWeights { get; set; } = new();
        public Dictionary<string, CellAssignmentData> Assignments { get; set; } = new();

        public string FilePath { get; set; } = string.Empty;
        public string FileName { get; set; } = string.Empty;
    }
}

using System;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace ChromeGridLauncher.Models
{
    public class ConnectedTab : INotifyPropertyChanged
    {
        private string _tabId = string.Empty;
        private string _title = "Untitled Tab";
        private string _url = string.Empty;
        private string _userAgent = string.Empty;
        private string _version = string.Empty;
        private string _pageType = string.Empty;
        private bool _hasInputs = false;
        private double _connectedAt = 0.0;
        private double _lastSeen = 0.0;
        private string _lastResult = "Ready";
        private int _lastDurationMs = 0;
        private string _lastStrategy = string.Empty;
        private int _refreshCount = 0;
        private int _screenX = 0;
        private int _screenY = 0;
        private int _outerW = 0;
        private int _outerH = 0;

        public string TabId
        {
            get => _tabId;
            set { if (_tabId != value) { _tabId = value; OnPropertyChanged(); } }
        }

        public string Title
        {
            get => _title;
            set { if (_title != value) { _title = value; OnPropertyChanged(); OnPropertyChanged(nameof(DisplayTitle)); } }
        }

        public string Url
        {
            get => _url;
            set { if (_url != value) { _url = value; OnPropertyChanged(); OnPropertyChanged(nameof(DisplayUrl)); } }
        }

        public string UserAgent
        {
            get => _userAgent;
            set { if (_userAgent != value) { _userAgent = value; OnPropertyChanged(); } }
        }

        public string Version
        {
            get => _version;
            set { if (_version != value) { _version = value; OnPropertyChanged(); } }
        }

        public string PageType
        {
            get => _pageType;
            set { if (_pageType != value) { _pageType = value; OnPropertyChanged(); } }
        }

        public bool HasInputs
        {
            get => _hasInputs;
            set { if (_hasInputs != value) { _hasInputs = value; OnPropertyChanged(); } }
        }

        public double ConnectedAt
        {
            get => _connectedAt;
            set { if (_connectedAt != value) { _connectedAt = value; OnPropertyChanged(); } }
        }

        public double LastSeen
        {
            get => _lastSeen;
            set { if (_lastSeen != value) { _lastSeen = value; OnPropertyChanged(); } }
        }

        public string LastResult
        {
            get => _lastResult;
            set { if (_lastResult != value) { _lastResult = value; OnPropertyChanged(); OnPropertyChanged(nameof(StatusDotColor)); OnPropertyChanged(nameof(DisplayUrl)); } }
        }

        public int LastDurationMs
        {
            get => _lastDurationMs;
            set { if (_lastDurationMs != value) { _lastDurationMs = value; OnPropertyChanged(); OnPropertyChanged(nameof(DisplayUrl)); } }
        }

        public string LastStrategy
        {
            get => _lastStrategy;
            set { if (_lastStrategy != value) { _lastStrategy = value; OnPropertyChanged(); OnPropertyChanged(nameof(DisplayUrl)); } }
        }

        public int RefreshCount
        {
            get => _refreshCount;
            set { if (_refreshCount != value) { _refreshCount = value; OnPropertyChanged(); } }
        }

        public int ScreenX { get => _screenX; set => _screenX = value; }
        public int ScreenY { get => _screenY; set => _screenY = value; }
        public int OuterW { get => _outerW; set => _outerW = value; }
        public int OuterH { get => _outerH; set => _outerH = value; }

        public string DisplayTitle => (Title.Length > 38 ? Title.Substring(0, 38) + "..." : Title);

        public string DisplayUrl
        {
            get
            {
                string u = Url.Length > 45 ? Url.Substring(0, 45) + "..." : Url;
                string stat = $"Result: {LastResult}";
                if (LastDurationMs > 0)
                {
                    stat += $" ({LastDurationMs}ms{(string.IsNullOrWhiteSpace(LastStrategy) ? "" : $" via {LastStrategy}")})";
                }
                return $"{u}  •  {stat}";
            }
        }

        public string StatusDotColor
        {
            get
            {
                if (LastResult == "Success") return "#10B981";
                if (LastResult == "Error" || LastResult == "Timeout") return "#EF4444";
                return "#3B82F6";
            }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? propName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propName));
        }
    }
}

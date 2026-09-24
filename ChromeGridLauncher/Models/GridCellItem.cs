using System;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace ChromeGridLauncher.Models
{
    public class GridCellItem : INotifyPropertyChanged
    {
        private ChromeProfile? _assignedProfile;
        private string _statusText = string.Empty;
        private int _cellWidth = 0;
        private int _cellHeight = 0;
        private bool _isCompact = false;
        private int _offsetX = 0;
        private int _offsetY = 0;
        private int _offsetWidth = 0;
        private int _offsetHeight = 0;

        public int Row { get; set; }
        public int Col { get; set; }
        public int CellIndex { get; set; }

        public ChromeProfile? AssignedProfile
        {
            get => _assignedProfile;
            set
            {
                if (_assignedProfile != value)
                {
                    _assignedProfile = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(HasProfile));
                    OnPropertyChanged(nameof(BorderColor));
                }
            }
        }

        public string StatusText
        {
            get => _statusText;
            set
            {
                if (_statusText != value)
                {
                    _statusText = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(HasStatus));
                }
            }
        }

        public int CellWidth
        {
            get => _cellWidth;
            set
            {
                if (_cellWidth != value)
                {
                    _cellWidth = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(ResolutionText));
                }
            }
        }

        public int CellHeight
        {
            get => _cellHeight;
            set
            {
                if (_cellHeight != value)
                {
                    _cellHeight = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(ResolutionText));
                }
            }
        }

        public bool IsCompact
        {
            get => _isCompact;
            set
            {
                if (_isCompact != value)
                {
                    _isCompact = value;
                    OnPropertyChanged();
                }
            }
        }

        public int OffsetX
        {
            get => _offsetX;
            set
            {
                if (_offsetX != value)
                {
                    _offsetX = value;
                    OnPropertyChanged();
                }
            }
        }

        public int OffsetY
        {
            get => _offsetY;
            set
            {
                if (_offsetY != value)
                {
                    _offsetY = value;
                    OnPropertyChanged();
                }
            }
        }

        public int OffsetWidth
        {
            get => _offsetWidth;
            set
            {
                if (_offsetWidth != value)
                {
                    _offsetWidth = value;
                    OnPropertyChanged();
                }
            }
        }

        public int OffsetHeight
        {
            get => _offsetHeight;
            set
            {
                if (_offsetHeight != value)
                {
                    _offsetHeight = value;
                    OnPropertyChanged();
                }
            }
        }

        public bool HasProfile => AssignedProfile != null;
        public bool HasStatus => !string.IsNullOrWhiteSpace(StatusText);

        public string CellTag
        {
            get
            {
                if (IsCompact)
                    return $"#{CellIndex + 1:02d} [R{Row + 1},C{Col + 1}]";
                return $"Cell {CellIndex + 1}  [R{Row + 1}, C{Col + 1}]";
            }
        }

        public string ResolutionText => (CellWidth > 0 && CellHeight > 0) ? $"{CellWidth}×{CellHeight}" : "";

        public string BorderColor
        {
            get
            {
                if (AssignedProfile != null)
                {
                    if (AssignedProfile.IsProtected) return "#F59E0B";
                    if (!string.IsNullOrWhiteSpace(AssignedProfile.GroupColor)) return AssignedProfile.GroupColor;
                    return "#3B82F6";
                }
                return "#232A3E";
            }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? propName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propName));
        }
    }
}

using System;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.ViewModels
{
    public class ThunderCellViewModel : INotifyPropertyChanged
    {
        private bool _isSelected = false;
        private string _city = "Casablanca";
        private string _visaType = "National Visa";
        private string _category = "Normal";
        private int _members = 1;

        private string _pillBg = "#0C4A6E";
        private string _pillBorder = "#0284C7";
        private string _pillText = "#E0F2FE";

        private bool _hasConflict = false;
        private string _conflictMessage = string.Empty;

        public int Row { get; set; }
        public int Col { get; set; }
        public int CellIndex { get; set; }
        public ChromeProfile? Profile { get; set; }

        public bool IsSelected
        {
            get => _isSelected;
            set
            {
                if (_isSelected != value)
                {
                    _isSelected = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CardBgColor));
                    OnPropertyChanged(nameof(CardBorderColor));
                    OnPropertyChanged(nameof(CardBorderThickness));
                    OnPropertyChanged(nameof(SelectionStatusText));
                    OnPropertyChanged(nameof(SelectionBadgeVisible));
                }
            }
        }

        public string CardBgColor => IsSelected ? "#182234" : "#121722";
        public string CardBorderColor
        {
            get
            {
                if (HasConflict) return "#EF4444"; // Red for conflict
                if (IsSelected) return "#10B981";  // Vibrant emerald green for selected
                return "#232A3E";                 // Neutral dark border
            }
        }

        public int CardBorderThickness => (IsSelected || HasConflict) ? 2 : 1;
        public string SelectionStatusText => IsSelected ? "✓ SELECTED" : "";
        public bool SelectionBadgeVisible => IsSelected;

        public bool HasConflict
        {
            get => _hasConflict;
            set
            {
                if (_hasConflict != value)
                {
                    _hasConflict = value;
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CardBorderColor));
                    OnPropertyChanged(nameof(CardBorderThickness));
                }
            }
        }

        public string ConflictMessage
        {
            get => _conflictMessage;
            set { if (_conflictMessage != value) { _conflictMessage = value; OnPropertyChanged(); } }
        }

        public string City
        {
            get => _city;
            set
            {
                if (_city != value)
                {
                    _city = value;
                    UpdateCityColors();
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CityTag));
                }
            }
        }

        public string VisaType
        {
            get => _visaType;
            set { if (_visaType != value) { _visaType = value; OnPropertyChanged(); } }
        }

        public string Category
        {
            get => _category;
            set { if (_category != value) { _category = value; OnPropertyChanged(); } }
        }

        public int Members
        {
            get => _members;
            set { if (_members != value) { _members = value; OnPropertyChanged(); OnPropertyChanged(nameof(MembersText)); } }
        }

        public string PillBg
        {
            get => _pillBg;
            set { if (_pillBg != value) { _pillBg = value; OnPropertyChanged(); } }
        }

        public string PillBorder
        {
            get => _pillBorder;
            set { if (_pillBorder != value) { _pillBorder = value; OnPropertyChanged(); } }
        }

        public string PillText
        {
            get => _pillText;
            set { if (_pillText != value) { _pillText = value; OnPropertyChanged(); } }
        }

        public string CellTag => $"#{CellIndex + 1:02d}";
        public string CoordinatesTag => $"R{Row + 1}:C{Col + 1}";
        public string CityTag => string.IsNullOrWhiteSpace(City) ? "Not Set" : City;
        public string MembersText => $"{Members} pax";
        public string ProfileName => Profile != null ? Profile.DisplayName : "⚠️ No Profile";
        public string ProfileGroupColor => Profile != null ? Profile.GroupColor : "#64748B";

        public void ApplyConfig(ThunderConfig cfg)
        {
            if (cfg?.VtData != null)
            {
                City = cfg.VtData.City;
                VisaType = cfg.VtData.Type;
                Category = cfg.VtData.Category;
                Members = cfg.VtData.Members;
            }
        }

        public ThunderConfig ToConfig(string region)
        {
            return new ThunderConfig
            {
                Region = region,
                VtData = new ThunderVtData
                {
                    City = City,
                    Type = VisaType,
                    Category = Category,
                    Members = Members
                }
            };
        }

        public void UpdateCityColors()
        {
            if (ThunderConstants.CityColors.TryGetValue(City, out var color))
            {
                PillBg = color.PillBg;
                PillBorder = color.PillBorder;
                PillText = color.PillText;
            }
            else
            {
                PillBg = ThunderConstants.DefaultColor.PillBg;
                PillBorder = ThunderConstants.DefaultColor.PillBorder;
                PillText = ThunderConstants.DefaultColor.PillText;
            }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? propName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propName));
        }
    }
}

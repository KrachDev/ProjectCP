using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;
using ChromeGridLauncher.Models;
using ChromeGridLauncher.Services;
using ChromeGridLauncher.Views.Modals;

namespace ChromeGridLauncher.ViewModels
{
    public class MainViewModel : ViewModelBase
    {
        private readonly ChromeProfileScanner _profileScanner = new();
        private readonly WebSocketServerService _wsServer = new();
        private readonly LayoutStorageService _storageService = new();
        private readonly ThunderConfigService _thunderService = new();

        private ObservableCollection<ChromeProfile> _allProfiles = new();
        private ObservableCollection<ChromeProfile> _filteredProfiles = new();
        private ObservableCollection<MonitorInfo> _monitors = new();
        private ObservableCollection<ConnectedTab> _connectedTabs = new();
        private ObservableCollection<ProfileGroup> _profileGroups = new();
        private ObservableCollection<GridCellItem> _gridCells = new();
        private ObservableCollection<ThunderCellViewModel> _thunderCells = new();
        private ObservableCollection<string> _activityLogs = new();

        private MonitorInfo? _selectedMonitor;
        private ProfileGroup? _selectedGroupFilter;
        private string _searchText = string.Empty;
        private string _activeWorkspaceTab = "grid"; // "grid" | "thunder" | "refresh"

        private int _gridRows = 2;
        private int _gridCols = 2;
        private int _cellGap = 0;
        private bool _useFullScreen = false;
        private string _statusMessage = "Ready";
        private bool _isLaunching = false;
        private bool _cancelLaunchFlag = false;
        private double _launchProgress = 0.0;
        private bool _launchProgressVisible = false;

        private AppSettings _settings = new();
        private readonly HashSet<IntPtr> _managedHwnds = new();
        private ChromeProfile? _selectedProfileForPlacement = null;

        // Thunder state
        private string _thunderRegion = "Spain";
        private string _thunderVisaType = "National Visa";
        private string _thunderCenter = "Casablanca";
        private string _thunderCategory = "Normal";
        private string _thunderMembers = "1";
        private string _thunderPresetName = "Default";
        private ObservableCollection<string> _thunderPresetNames = new();
        private Dictionary<string, ThunderConfig> _thunderPresets = new();
        private Dictionary<string, ThunderConfig> _thunderCellConfigs = new();
        private ObservableCollection<string> _availableVisaTypes = new();
        private ObservableCollection<string> _availableCenters = new();
        private ObservableCollection<string> _availableCategories = new();
        private ObservableCollection<string> _availableMembers = new();

        // Conflict & Bulk state
        private int _conflictCount = 0;
        private string _conflictBannerText = "🟢 Configuration Clean: 0 conflicts detected.";
        private string _conflictBannerColor = "#10B981";

        // Slot Time state
        private int _slotASec = 0;
        private int _slotAMs = 0;
        private int _slotAStep = 0;
        private int _slotBSec = 0;
        private int _slotBMs = 0;
        private int _slotBStep = 0;

        // Refresh state
        private string _refreshXPath = "//button[contains(normalize-space(.), 'Refresh') and not(contains(@id, 'redirect'))]";
        private string _refreshText = "Refresh";
        private string _refreshClassName = "btn btn-primary";
        private int _staggerMs = 0;
        private string _autoRefreshChoice = "Off";
        private DispatcherTimer? _autoRefreshTimer;

        public MainViewModel()
        {
            InitializeCommands();
            LoadData();
            InitializeThunder();
            RebuildGridCells();
            StartWebSocketServer();
        }

        #region Observables & Properties

        public string ActiveWorkspaceTab
        {
            get => _activeWorkspaceTab;
            set
            {
                if (SetProperty(ref _activeWorkspaceTab, value))
                {
                    OnPropertyChanged(nameof(IsGridTabActive));
                    OnPropertyChanged(nameof(IsThunderTabActive));
                    OnPropertyChanged(nameof(IsSlotTimeTabActive));
                    OnPropertyChanged(nameof(IsRefreshTabActive));
                }
            }
        }

        public bool IsGridTabActive => _activeWorkspaceTab == "grid";
        public bool IsThunderTabActive => _activeWorkspaceTab == "thunder";
        public bool IsSlotTimeTabActive => _activeWorkspaceTab == "slot_time";
        public bool IsRefreshTabActive => _activeWorkspaceTab == "refresh";

        public ObservableCollection<ChromeProfile> FilteredProfiles
        {
            get => _filteredProfiles;
            set => SetProperty(ref _filteredProfiles, value);
        }

        public ObservableCollection<MonitorInfo> Monitors
        {
            get => _monitors;
            set => SetProperty(ref _monitors, value);
        }

        public ObservableCollection<ConnectedTab> ConnectedTabs
        {
            get => _connectedTabs;
            set => SetProperty(ref _connectedTabs, value);
        }

        public ObservableCollection<ProfileGroup> ProfileGroups
        {
            get => _profileGroups;
            set => SetProperty(ref _profileGroups, value);
        }

        public ObservableCollection<GridCellItem> GridCells
        {
            get => _gridCells;
            set => SetProperty(ref _gridCells, value);
        }

        public ObservableCollection<ThunderCellViewModel> ThunderCells
        {
            get => _thunderCells;
            set => SetProperty(ref _thunderCells, value);
        }

        public ObservableCollection<ThunderRowSelectorItem> ThunderRowSelectors { get; } = new();

        public ObservableCollection<string> ActivityLogs
        {
            get => _activityLogs;
            set => SetProperty(ref _activityLogs, value);
        }

        public MonitorInfo? SelectedMonitor
        {
            get => _selectedMonitor;
            set
            {
                if (SetProperty(ref _selectedMonitor, value))
                {
                    if (value != null)
                    {
                        _settings.MonitorIndex = value.Index;
                        _storageService.SaveSettings(_settings);
                    }
                    UpdateCellResolutions();
                }
            }
        }

        public ProfileGroup? SelectedGroupFilter
        {
            get => _selectedGroupFilter;
            set
            {
                if (SetProperty(ref _selectedGroupFilter, value))
                {
                    ApplyFilter();
                }
            }
        }

        public string SearchText
        {
            get => _searchText;
            set
            {
                if (SetProperty(ref _searchText, value))
                {
                    ApplyFilter();
                }
            }
        }

        public int GridRows
        {
            get => _gridRows;
            set
            {
                if (SetProperty(ref _gridRows, Math.Max(1, Math.Min(20, value))))
                {
                    RebuildGridCells();
                    RebuildThunderGrid();
                }
            }
        }

        public int GridCols
        {
            get => _gridCols;
            set
            {
                if (SetProperty(ref _gridCols, Math.Max(1, Math.Min(20, value))))
                {
                    RebuildGridCells();
                    RebuildThunderGrid();
                }
            }
        }

        public int CellGap
        {
            get => _cellGap;
            set
            {
                if (SetProperty(ref _cellGap, Math.Max(0, value)))
                {
                    _settings.CellGap = value;
                    _storageService.SaveSettings(_settings);
                    SaveAutoState();
                    UpdateCellResolutions();
                    OnPropertyChanged(nameof(IsGap0Active));
                    OnPropertyChanged(nameof(IsGap2Active));
                    OnPropertyChanged(nameof(IsGap4Active));
                }
            }
        }

        public bool IsGap0Active => _cellGap == 0;
        public bool IsGap2Active => _cellGap == 2;
        public bool IsGap4Active => _cellGap == 4;

        public bool UseFullScreen
        {
            get => _useFullScreen;
            set
            {
                if (SetProperty(ref _useFullScreen, value))
                {
                    _settings.UseFullScreen = value;
                    _storageService.SaveSettings(_settings);
                    UpdateCellResolutions();
                    OnPropertyChanged(nameof(ScreenModeText));
                }
            }
        }

        public string ScreenModeText => UseFullScreen ? "📺 Full Screen" : "🖥️ Work Area";

        public string StatusMessage
        {
            get => _statusMessage;
            set => SetProperty(ref _statusMessage, value);
        }

        public bool IsLaunching
        {
            get => _isLaunching;
            set
            {
                if (SetProperty(ref _isLaunching, value))
                {
                    OnPropertyChanged(nameof(LaunchButtonText));
                    OnPropertyChanged(nameof(LaunchButtonColor));
                }
            }
        }

        public string LaunchButtonText => IsLaunching ? "🛑 STOP LAUNCH" : "🚀 LAUNCH ALL";
        public string LaunchButtonColor => IsLaunching ? "#EF4444" : "#10B981";

        public double LaunchProgress
        {
            get => _launchProgress;
            set => SetProperty(ref _launchProgress, value);
        }

        public bool LaunchProgressVisible
        {
            get => _launchProgressVisible;
            set => SetProperty(ref _launchProgressVisible, value);
        }

        public string ProfileCountText => $"{_allProfiles.Count} profiles detected";
        public string ServerPillText => _wsServer.IsRunning ? $"🟢 ws://127.0.0.1:{_wsServer.Port} ({ConnectedTabs.Count} tabs)" : "🔴 Server: Stopped";
        public string ServerPillColor => _wsServer.IsRunning ? "#10B981" : "#EF4444";

        #endregion

        #region Thunder Properties

        public string ThunderRegion
        {
            get => _thunderRegion;
            set
            {
                if (SetProperty(ref _thunderRegion, value))
                {
                    ApplyThunderRegionOptions(value);
                    OnPropertyChanged(nameof(ThunderRegionTag));
                }
            }
        }

        public string ThunderRegionTag => ThunderRegion == "Portugal" ? "🇵🇹 Portugal (v1.6.5)" : "🇪🇸 Spain (v1.8.8)";

        public string ThunderVisaType
        {
            get => _thunderVisaType;
            set => SetProperty(ref _thunderVisaType, value);
        }

        public string ThunderCenter
        {
            get => _thunderCenter;
            set => SetProperty(ref _thunderCenter, value);
        }

        public string ThunderCategory
        {
            get => _thunderCategory;
            set => SetProperty(ref _thunderCategory, value);
        }

        public string ThunderMembers
        {
            get => _thunderMembers;
            set => SetProperty(ref _thunderMembers, value);
        }

        public string ThunderPresetName
        {
            get => _thunderPresetName;
            set
            {
                if (SetProperty(ref _thunderPresetName, value))
                {
                    if (!string.IsNullOrWhiteSpace(value) && _thunderPresets.TryGetValue(value, out var cfg))
                    {
                        ApplyThunderConfigToVars(cfg);
                    }
                }
            }
        }

        public ObservableCollection<string> ThunderPresetNames
        {
            get => _thunderPresetNames;
            set => SetProperty(ref _thunderPresetNames, value);
        }

        public ObservableCollection<string> AvailableVisaTypes
        {
            get => _availableVisaTypes;
            set => SetProperty(ref _availableVisaTypes, value);
        }

        public ObservableCollection<string> AvailableCenters
        {
            get => _availableCenters;
            set => SetProperty(ref _availableCenters, value);
        }

        public ObservableCollection<string> AvailableCategories
        {
            get => _availableCategories;
            set => SetProperty(ref _availableCategories, value);
        }

        public ObservableCollection<string> AvailableMembers
        {
            get => _availableMembers;
            set => SetProperty(ref _availableMembers, value);
        }

        public string ThunderTargetCountText
        {
            get
            {
                int selectedCount = ThunderCells.Count(c => c.IsSelected);
                return $"Targeting {selectedCount} of {ThunderCells.Count} Chrome instances";
            }
        }

        public int ConflictCount
        {
            get => _conflictCount;
            set => SetProperty(ref _conflictCount, value);
        }

        public string ConflictBannerText
        {
            get => _conflictBannerText;
            set => SetProperty(ref _conflictBannerText, value);
        }

        public string ConflictBannerColor
        {
            get => _conflictBannerColor;
            set => SetProperty(ref _conflictBannerColor, value);
        }

        public bool HasConflicts => _conflictCount > 0;

        #endregion

        #region Slot Time Properties

        public int SlotASec
        {
            get => _slotASec;
            set => SetProperty(ref _slotASec, Math.Clamp(value, 0, 59));
        }

        public int SlotAMs
        {
            get => _slotAMs;
            set => SetProperty(ref _slotAMs, Math.Clamp(value, 0, 999));
        }

        public int SlotAStep
        {
            get => _slotAStep;
            set => SetProperty(ref _slotAStep, Math.Clamp(value, 0, 999));
        }

        public int SlotBSec
        {
            get => _slotBSec;
            set => SetProperty(ref _slotBSec, Math.Clamp(value, 0, 59));
        }

        public int SlotBMs
        {
            get => _slotBMs;
            set => SetProperty(ref _slotBMs, Math.Clamp(value, 0, 999));
        }

        public int SlotBStep
        {
            get => _slotBStep;
            set => SetProperty(ref _slotBStep, Math.Clamp(value, 0, 999));
        }

        #endregion

        #region Refresh Properties

        public string RefreshXPath
        {
            get => _refreshXPath;
            set => SetProperty(ref _refreshXPath, value);
        }

        public string RefreshText
        {
            get => _refreshText;
            set => SetProperty(ref _refreshText, value);
        }

        public string RefreshClassName
        {
            get => _refreshClassName;
            set => SetProperty(ref _refreshClassName, value);
        }

        public int StaggerMs
        {
            get => _staggerMs;
            set => SetProperty(ref _staggerMs, value);
        }

        public string AutoRefreshChoice
        {
            get => _autoRefreshChoice;
            set
            {
                if (SetProperty(ref _autoRefreshChoice, value))
                {
                    ConfigureAutoRefresh(value);
                }
            }
        }

        public int TotalBroadcastsCount => _wsServer.TotalBroadcasts;
        public int TotalAcksSuccessCount => _wsServer.TotalAcksSuccess;
        public int TotalAcksFailedCount => _wsServer.TotalAcksFailed;

        #endregion

        #region Commands

        public ICommand SelectWorkspaceTabCommand { get; private set; } = null!;
        public ICommand SetGridPresetCommand { get; private set; } = null!;
        public ICommand SetGapCommand { get; private set; } = null!;
        public ICommand ToggleScreenModeCommand { get; private set; } = null!;
        public ICommand AutoPopulateGridCommand { get; private set; } = null!;
        public ICommand ClearGridCommand { get; private set; } = null!;
        public ICommand LaunchAllCommand { get; private set; } = null!;
        public ICommand TileWindowsCommand { get; private set; } = null!;
        public ICommand CloseManagedChromeCommand { get; private set; } = null!;
        public ICommand RefreshProfilesCommand { get; private set; } = null!;
        public ICommand ToggleProtectProfileCommand { get; private set; } = null!;
        public ICommand SelectProfileForPlacementCommand { get; private set; } = null!;
        public ICommand QuickAddProfileCommand { get; private set; } = null!;
        public ICommand CellClickedCommand { get; private set; } = null!;
        public ICommand ClearCellCommand { get; private set; } = null!;
        public ICommand ChangeCellProfileCommand { get; private set; } = null!;
        public ICommand FineTuneCellCommand { get; private set; } = null!;

        // Layouts & Modals
        public ICommand OpenCustomGridModalCommand { get; private set; } = null!;
        public ICommand OpenFineControlModalCommand { get; private set; } = null!;
        public ICommand OpenSaveLayoutModalCommand { get; private set; } = null!;
        public ICommand OpenLoadLayoutModalCommand { get; private set; } = null!;
        public ICommand OpenNewGroupModalCommand { get; private set; } = null!;
        public ICommand OpenSettingsModalCommand { get; private set; } = null!;

        // Thunder Commands
        public ICommand ThunderSelectAllCommand { get; private set; } = null!;
        public ICommand ThunderDeselectAllCommand { get; private set; } = null!;
        public ICommand ThunderInvertSelectionCommand { get; private set; } = null!;
        public ICommand ThunderSelectTopHalfCommand { get; private set; } = null!;
        public ICommand ThunderSelectBottomHalfCommand { get; private set; } = null!;
        public ICommand ThunderToggleCellSelectionCommand { get; private set; } = null!;
        public ICommand ThunderSavePresetCommand { get; private set; } = null!;
        public ICommand ThunderDeletePresetCommand { get; private set; } = null!;
        public ICommand ApplyThunderUnifiedConfigCommand { get; private set; } = null!;
        public ICommand AutoFixConflictsCommand { get; private set; } = null!;
        public ICommand ThunderSelectByCityCommand { get; private set; } = null!;
        public ICommand ThunderDistributeEvenlyCommand { get; private set; } = null!;
        public ICommand ThunderDistributeByGroupCommand { get; private set; } = null!;

        // Refresh Commands
        public ICommand TriggerRefreshAllCommand { get; private set; } = null!;
        public ICommand ToggleServerCommand { get; private set; } = null!;
        public ICommand PingAllTabsCommand { get; private set; } = null!;
        public ICommand CopyUserscriptCommand { get; private set; } = null!;
        public ICommand OpenInstallScriptPageCommand { get; private set; } = null!;
        public ICommand LiveUpdateScriptInOpenTabsCommand { get; private set; } = null!;
        public ICommand OpenExtensionFolderCommand { get; private set; } = null!;
        public ICommand CopyExtensionPathCommand { get; private set; } = null!;
        public ICommand OpenChromeExtensionsPageCommand { get; private set; } = null!;
        public ICommand SyncGlobalExtensionCommand { get; private set; } = null!;
        public ICommand ReloadAllExtensionsCommand { get; private set; } = null!;
        public ICommand ClearActivityLogCommand { get; private set; } = null!;

        // Slot Time Commands
        public ICommand TriggerSlotClickACommand { get; private set; } = null!;
        public ICommand TriggerSlotClickBCommand { get; private set; } = null!;
        public ICommand TriggerSlotClickAllCommand { get; private set; } = null!;

        // Hard Refresh All
        public ICommand HardRefreshAllCommand { get; private set; } = null!;

        private void InitializeCommands()
        {
            SelectWorkspaceTabCommand = new RelayCommand(p => ActiveWorkspaceTab = p?.ToString() ?? "grid");
            SetGridPresetCommand = new RelayCommand(p =>
            {
                if (p is string s)
                {
                    var m = Regex.Match(s, @"(\d+)[x×](\d+)");
                    if (m.Success)
                    {
                        GridRows = int.Parse(m.Groups[1].Value);
                        GridCols = int.Parse(m.Groups[2].Value);
                        StatusMessage = $"Switched grid layout to {GridRows}×{GridCols}.";
                    }
                }
            });

            SetGapCommand = new RelayCommand(p =>
            {
                if (int.TryParse(p?.ToString(), out int gap))
                {
                    CellGap = gap;
                    _settings.CellGap = gap;
                    _storageService.SaveSettings(_settings);
                    SaveAutoState();
                    StatusMessage = $"Cell gap set to {gap}px and saved.";
                }
            });

            ToggleScreenModeCommand = new RelayCommand(() => UseFullScreen = !UseFullScreen);
            AutoPopulateGridCommand = new RelayCommand(ExecuteAutoPopulate);
            ClearGridCommand = new RelayCommand(ExecuteClearGrid);
            LaunchAllCommand = new RelayCommand(ExecuteLaunchAll);
            TileWindowsCommand = new RelayCommand(ExecuteTileWindows);
            CloseManagedChromeCommand = new RelayCommand(ExecuteCloseManagedChrome);
            RefreshProfilesCommand = new RelayCommand(ExecuteScanProfiles);

            ToggleProtectProfileCommand = new RelayCommand(p =>
            {
                if (p is ChromeProfile cp) ExecuteToggleProtect(cp);
            });

            SelectProfileForPlacementCommand = new RelayCommand(p =>
            {
                if (p is ChromeProfile cp)
                {
                    if (_selectedProfileForPlacement == cp)
                    {
                        _selectedProfileForPlacement = null;
                        StatusMessage = "Profile placement unselected.";
                    }
                    else
                    {
                        _selectedProfileForPlacement = cp;
                        StatusMessage = $"Selected '{cp.DisplayName}'. Click any grid cell to place it.";
                    }
                }
            });

            QuickAddProfileCommand = new RelayCommand(p =>
            {
                if (p is ChromeProfile cp) ExecuteQuickAdd(cp);
            });

            CellClickedCommand = new RelayCommand(p =>
            {
                if (p is GridCellItem cell) ExecuteCellClicked(cell);
            });

            ClearCellCommand = new RelayCommand(p =>
            {
                if (p is GridCellItem cell)
                {
                    cell.AssignedProfile = null;
                    SaveAutoState();
                    StatusMessage = $"Cleared Cell [R{cell.Row + 1}, C{cell.Col + 1}].";
                }
            });

            ChangeCellProfileCommand = new RelayCommand(p =>
            {
                if (p is GridCellItem cell)
                {
                    var modal = new ProfilePickerModal(_allProfiles.ToList());
                    if (modal.ShowDialog() == true && modal.SelectedProfile != null)
                    {
                        cell.AssignedProfile = modal.SelectedProfile;
                        SaveAutoState();
                        StatusMessage = $"Assigned '{modal.SelectedProfile.DisplayName}' to Cell [R{cell.Row + 1}, C{cell.Col + 1}].";
                    }
                }
            });

            FineTuneCellCommand = new RelayCommand(p =>
            {
                ExecuteOpenFineControlModal();
            });

            // Modals
            OpenCustomGridModalCommand = new RelayCommand(() =>
            {
                var modal = new CustomGridModal(GridRows, GridCols);
                if (modal.ShowDialog() == true)
                {
                    GridRows = modal.SelectedRows;
                    GridCols = modal.SelectedCols;
                    StatusMessage = $"Set custom grid dimensions: {GridRows}×{GridCols}.";
                }
            });

            OpenFineControlModalCommand = new RelayCommand(ExecuteOpenFineControlModal);
            OpenSaveLayoutModalCommand = new RelayCommand(ExecuteOpenSaveLayoutModal);
            OpenLoadLayoutModalCommand = new RelayCommand(ExecuteOpenLoadLayoutModal);
            OpenNewGroupModalCommand = new RelayCommand(ExecuteOpenNewGroupModal);
            OpenSettingsModalCommand = new RelayCommand(ExecuteOpenSettingsModal);

            // Thunder commands
            ThunderSelectAllCommand = new RelayCommand(() =>
            {
                foreach (var cell in ThunderCells) cell.IsSelected = true;
                OnPropertyChanged(nameof(ThunderTargetCountText));
            });
            ThunderDeselectAllCommand = new RelayCommand(() =>
            {
                foreach (var cell in ThunderCells) cell.IsSelected = false;
                OnPropertyChanged(nameof(ThunderTargetCountText));
            });
            ThunderInvertSelectionCommand = new RelayCommand(() =>
            {
                foreach (var cell in ThunderCells) cell.IsSelected = !cell.IsSelected;
                OnPropertyChanged(nameof(ThunderTargetCountText));
            });
            ThunderSelectTopHalfCommand = new RelayCommand(() =>
            {
                int half = GridRows / 2;
                foreach (var cell in ThunderCells) cell.IsSelected = (cell.Row < half);
                OnPropertyChanged(nameof(ThunderTargetCountText));
            });
            ThunderSelectBottomHalfCommand = new RelayCommand(() =>
            {
                int half = GridRows / 2;
                foreach (var cell in ThunderCells) cell.IsSelected = (cell.Row >= half);
                OnPropertyChanged(nameof(ThunderTargetCountText));
            });
            ThunderToggleCellSelectionCommand = new RelayCommand(p =>
            {
                if (p is ThunderCellViewModel cell)
                {
                    cell.IsSelected = !cell.IsSelected;
                    OnPropertyChanged(nameof(ThunderTargetCountText));
                }
            });
            ThunderSavePresetCommand = new RelayCommand(ExecuteSaveThunderPreset);
            ThunderDeletePresetCommand = new RelayCommand(ExecuteDeleteThunderPreset);
            ApplyThunderUnifiedConfigCommand = new RelayCommand(ExecuteApplyThunderUnifiedConfig);
            AutoFixConflictsCommand = new RelayCommand(ExecuteAutoFixConflicts);
            ThunderSelectByCityCommand = new RelayCommand(ExecuteThunderSelectByCity);
            ThunderDistributeEvenlyCommand = new RelayCommand(ExecuteThunderDistributeEvenly);
            ThunderDistributeByGroupCommand = new RelayCommand(ExecuteThunderDistributeByGroup);

            // Refresh Commands
            TriggerRefreshAllCommand = new RelayCommand(ExecuteTriggerRefreshAll);
            ToggleServerCommand = new RelayCommand(ExecuteToggleServer);
            PingAllTabsCommand = new RelayCommand(() => _wsServer.PingAllTabs());
            CopyUserscriptCommand = new RelayCommand(ExecuteCopyUserscript);
            OpenInstallScriptPageCommand = new RelayCommand(ExecuteOpenInstallScriptPage);
            LiveUpdateScriptInOpenTabsCommand = new RelayCommand(ExecuteLiveUpdateScriptInOpenTabs);
            OpenExtensionFolderCommand = new RelayCommand(ExecuteOpenExtensionFolder);
            CopyExtensionPathCommand = new RelayCommand(ExecuteCopyExtensionPath);
            OpenChromeExtensionsPageCommand = new RelayCommand(ExecuteOpenChromeExtensionsPage);
            SyncGlobalExtensionCommand = new RelayCommand(ExecuteSyncGlobalExtension);
            ReloadAllExtensionsCommand = new RelayCommand(ExecuteReloadAllExtensions);
            TriggerSlotClickACommand = new RelayCommand(() => ExecuteDispatchSlotPage("a"));
            TriggerSlotClickBCommand = new RelayCommand(() => ExecuteDispatchSlotPage("b"));
            TriggerSlotClickAllCommand = new RelayCommand(() => ExecuteDispatchSlotPage("all"));
            HardRefreshAllCommand = new RelayCommand(ExecuteHardRefreshAll);
            ClearActivityLogCommand = new RelayCommand(() => ActivityLogs.Clear());
        }

        #endregion

        #region Initialization & Data Loading

        private void LoadData()
        {
            _settings = _storageService.LoadSettings();
            _gridRows = Math.Max(1, _settings.CustomRows);
            _gridCols = Math.Max(1, _settings.CustomCols);
            _cellGap = _settings.CellGap;
            _useFullScreen = _settings.UseFullScreen;

            // Load monitors
            var mons = WindowPlacementService.GetMonitors();
            Monitors = new ObservableCollection<MonitorInfo>(mons);
            int monIdx = Math.Clamp(_settings.MonitorIndex, 0, Math.Max(0, mons.Count - 1));
            SelectedMonitor = mons.Count > monIdx ? mons[monIdx] : mons.FirstOrDefault();

            // Load groups
            var customGroups = _storageService.LoadCustomGroups();
            var groupsList = new List<ProfileGroup>
            {
                new ProfileGroup { Id = "all", Name = "All", Color = "#3B82F6", Icon = "📁", IsBuiltin = true },
                new ProfileGroup { Id = "numbers", Name = "Numbers", Color = "#10B981", Icon = "🔢", IsBuiltin = true },
                new ProfileGroup { Id = "prt", Name = "PRT", Color = "#8B5CF6", Icon = "🇵🇹", IsBuiltin = true },
                new ProfileGroup { Id = "other", Name = "Other", Color = "#64748B", Icon = "📁", IsBuiltin = true }
            };
            groupsList.AddRange(customGroups);
            ProfileGroups = new ObservableCollection<ProfileGroup>(groupsList);
            SelectedGroupFilter = ProfileGroups[0];

            // Scan profiles
            ExecuteScanProfiles();

            // Restore last layout
            var lastLayout = _storageService.LoadLastLayout();
            if (lastLayout != null)
            {
                ApplyLayoutPreset(lastLayout);
            }
        }

        private void InitializeThunder()
        {
            _thunderPresets = _thunderService.LoadPresets();
            _thunderCellConfigs = _thunderService.LoadCellConfigs();
            ThunderPresetNames = new ObservableCollection<string>(_thunderPresets.Keys);
            ThunderPresetName = _thunderPresets.ContainsKey("Default") ? "Default" : _thunderPresets.Keys.FirstOrDefault() ?? "Default";
            ApplyThunderRegionOptions(ThunderRegion);
        }

        private void ApplyThunderRegionOptions(string region)
        {
            if (ThunderConstants.Regions.TryGetValue(region, out var regCfg))
            {
                AvailableVisaTypes = new ObservableCollection<string>(regCfg.VisaTypes);
                AvailableCenters = new ObservableCollection<string>(regCfg.Centers);
                AvailableCategories = new ObservableCollection<string>(regCfg.Categories);
                AvailableMembers = new ObservableCollection<string>(regCfg.Members);

                if (!AvailableVisaTypes.Contains(ThunderVisaType)) ThunderVisaType = AvailableVisaTypes.FirstOrDefault() ?? "National Visa";
                if (!AvailableCenters.Contains(ThunderCenter)) ThunderCenter = AvailableCenters.FirstOrDefault() ?? "Casablanca";
                if (!AvailableCategories.Contains(ThunderCategory)) ThunderCategory = AvailableCategories.FirstOrDefault() ?? "Normal";
                if (!AvailableMembers.Contains(ThunderMembers)) ThunderMembers = AvailableMembers.FirstOrDefault() ?? "1";
            }
        }

        private void ApplyThunderConfigToVars(ThunderConfig cfg)
        {
            if (cfg == null) return;
            ThunderRegion = cfg.Region;
            if (cfg.VtData != null)
            {
                ThunderCenter = cfg.VtData.City;
                ThunderVisaType = cfg.VtData.Type;
                ThunderCategory = cfg.VtData.Category;
                ThunderMembers = cfg.VtData.Members.ToString();
            }
        }

        private void ExecuteScanProfiles()
        {
            string? overridePath = !string.IsNullOrWhiteSpace(_settings.ChromePathOverride) ? _settings.ChromePathOverride : null;
            var scanned = _profileScanner.ScanProfiles(overridePath);
            ChromeProfileScanner.ApplyGroupsToProfiles(scanned, _storageService.LoadCustomGroups(), _storageService.LoadOverrides());

            // Mark protected profile
            string protKey = _settings.ProtectedProfileKey;
            foreach (var p in scanned)
            {
                p.IsProtected = (!string.IsNullOrWhiteSpace(protKey) && string.Equals(p.Key, protKey, StringComparison.OrdinalIgnoreCase));
            }

            _allProfiles = new ObservableCollection<ChromeProfile>(scanned);
            ApplyFilter();
            OnPropertyChanged(nameof(ProfileCountText));
            StatusMessage = $"Detected {_allProfiles.Count} Chrome profiles.";
        }

        private void ApplyFilter()
        {
            IEnumerable<ChromeProfile> query = _allProfiles;

            if (SelectedGroupFilter != null && SelectedGroupFilter.Id != "all")
            {
                if (SelectedGroupFilter.IsBuiltin)
                {
                    query = query.Where(p => p.GroupId == SelectedGroupFilter.Id);
                }
                else
                {
                    query = query.Where(p => SelectedGroupFilter.ProfileKeys.Contains(p.Key) || p.GroupId == SelectedGroupFilter.Id);
                }
            }

            if (!string.IsNullOrWhiteSpace(SearchText))
            {
                string s = SearchText.Trim().ToLowerInvariant();
                query = query.Where(p =>
                    p.Name.ToLowerInvariant().Contains(s) ||
                    p.Key.ToLowerInvariant().Contains(s) ||
                    p.Email.ToLowerInvariant().Contains(s) ||
                    p.GaiaName.ToLowerInvariant().Contains(s)
                );
            }

            FilteredProfiles = new ObservableCollection<ChromeProfile>(query);
        }

        #endregion

        #region Grid Rebuilding & Cell Math

        private void RebuildGridCells()
        {
            var existingAssignments = GridCells.ToDictionary(c => $"{c.Row},{c.Col}", c => c.AssignedProfile);
            GridCells.Clear();

            int cellIdx = 0;
            bool isCompact = (GridCols >= 4 || GridRows >= 3);

            for (int r = 0; r < GridRows; r++)
            {
                for (int c = 0; c < GridCols; c++)
                {
                    string key = $"{r},{c}";
                    existingAssignments.TryGetValue(key, out var prof);

                    var cell = new GridCellItem
                    {
                        Row = r,
                        Col = c,
                        CellIndex = cellIdx++,
                        AssignedProfile = prof,
                        IsCompact = isCompact
                    };
                    GridCells.Add(cell);
                }
            }

            UpdateCellResolutions();
            SaveAutoState();
        }

        private void RebuildThunderGrid()
        {
            ThunderCells.Clear();
            int cellIdx = 0;

            for (int r = 0; r < GridRows; r++)
            {
                for (int c = 0; c < GridCols; c++)
                {
                    string key = $"{r},{c}";
                    var gridItem = GridCells.FirstOrDefault(gc => gc.Row == r && gc.Col == c);

                    var tCell = new ThunderCellViewModel
                    {
                        Row = r,
                        Col = c,
                        CellIndex = cellIdx++,
                        Profile = gridItem?.AssignedProfile
                    };

                    if (_thunderCellConfigs.TryGetValue(key, out var cfg))
                    {
                        tCell.ApplyConfig(cfg);
                    }
                    else
                    {
                        tCell.City = ThunderCenter;
                        tCell.VisaType = ThunderVisaType;
                        tCell.Category = ThunderCategory;
                        int.TryParse(ThunderMembers, out int m);
                        tCell.Members = Math.Max(1, m);
                    }

                    tCell.UpdateCityColors();
                    ThunderCells.Add(tCell);
                }
            }
            UpdateThunderRowSelectors();
            OnPropertyChanged(nameof(ThunderTargetCountText));
            RunConflictDetection();
        }

        public void UpdateThunderRowSelectors()
        {
            ThunderRowSelectors.Clear();
            for (int r = 0; r < GridRows; r++)
            {
                int rowIdx = r;
                ThunderRowSelectors.Add(new ThunderRowSelectorItem
                {
                    RowIndex = rowIdx,
                    Label = $"Row {rowIdx + 1}",
                    SelectCommand = new RelayCommand(() => ToggleThunderRow(rowIdx))
                });
            }
        }

        public void ToggleThunderRow(int rowIdx)
        {
            var rowCells = ThunderCells.Where(c => c.Row == rowIdx).ToList();
            if (rowCells.Count == 0) return;

            bool allSelected = rowCells.All(c => c.IsSelected);
            foreach (var cell in rowCells)
            {
                cell.IsSelected = !allSelected;
            }
            OnPropertyChanged(nameof(ThunderTargetCountText));
        }

        private void UpdateCellResolutions()
        {
            if (SelectedMonitor == null) return;

            foreach (var cell in GridCells)
            {
                var (x, y, w, h) = WindowPlacementService.CalculateCellRect(
                    SelectedMonitor,
                    GridRows,
                    GridCols,
                    cell.Row,
                    cell.Col,
                    gap: CellGap,
                    useFullScreen: UseFullScreen,
                    margins: _settings.ScreenMargins,
                    cellOffsets: _settings.CellOffsets,
                    colWeights: _settings.ColWeights,
                    rowWeights: _settings.RowWeights
                );

                cell.CellWidth = w;
                cell.CellHeight = h;
            }
        }

        #endregion

        #region Actions: Launch, AutoPopulate, Tile, Close

        private void ExecuteAutoPopulate()
        {
            string protKey = _settings.ProtectedProfileKey;
            var available = FilteredProfiles.Where(p => !p.IsProtected && (string.IsNullOrWhiteSpace(protKey) || !string.Equals(p.Key, protKey, StringComparison.OrdinalIgnoreCase))).ToList();

            if (available.Count == 0)
            {
                StatusMessage = "No non-protected profiles available in active view to populate.";
                return;
            }

            int idx = 0;
            foreach (var cell in GridCells)
            {
                if (idx < available.Count)
                {
                    cell.AssignedProfile = available[idx++];
                }
                else
                {
                    cell.AssignedProfile = null;
                }
            }

            RebuildThunderGrid();
            SaveAutoState();
            StatusMessage = $"Auto-populated {Math.Min(available.Count, GridCells.Count)} cells from current group.";
        }

        private void ExecuteClearGrid()
        {
            foreach (var cell in GridCells)
            {
                cell.AssignedProfile = null;
                cell.StatusText = string.Empty;
            }
            RebuildThunderGrid();
            SaveAutoState();
            StatusMessage = "Cleared all cells in grid.";
        }

        private async void ExecuteLaunchAll()
        {
            if (IsLaunching)
            {
                _cancelLaunchFlag = true;
                StatusMessage = "Cancelling launch...";
                return;
            }

            if (SelectedMonitor == null)
            {
                StatusMessage = "Error: No target display selected.";
                return;
            }

            var targets = GridCells.Where(c => c.AssignedProfile != null).ToList();
            if (targets.Count == 0)
            {
                StatusMessage = "No profiles assigned to grid. Click '⚡ Auto Populate' or assign profiles first.";
                return;
            }

            string chromeExe = !string.IsNullOrWhiteSpace(_settings.ChromePathOverride) && File.Exists(_settings.ChromePathOverride)
                ? _settings.ChromePathOverride
                : ChromeProfileScanner.FindChromeExecutable();

            if (!File.Exists(chromeExe))
            {
                StatusMessage = "Chrome executable not found! Configure Chrome path in Settings (⚙️).";
                return;
            }

            IsLaunching = true;
            _cancelLaunchFlag = false;
            LaunchProgress = 0.0;
            LaunchProgressVisible = true;

            int total = targets.Count;
            int successCount = 0;

            await Task.Run(async () =>
            {
                for (int i = 0; i < total; i++)
                {
                    if (_cancelLaunchFlag) break;

                    var cell = targets[i];
                    var prof = cell.AssignedProfile!;

                    int curIdx = i + 1;
                    App.Current?.Dispatcher?.Invoke(() =>
                    {
                        LaunchProgress = (double)(curIdx - 1) / total;
                        StatusMessage = $"Launching ({curIdx}/{total}): {prof.DisplayName}...";
                    });

                    var (x, y, w, h) = WindowPlacementService.CalculateCellRect(
                        SelectedMonitor,
                        GridRows,
                        GridCols,
                        cell.Row,
                        cell.Col,
                        gap: CellGap,
                        useFullScreen: UseFullScreen,
                        margins: _settings.ScreenMargins,
                        cellOffsets: _settings.CellOffsets,
                        colWeights: _settings.ColWeights,
                        rowWeights: _settings.RowWeights
                    );

                    IntPtr hwnd = ChromeLauncher.LaunchAndPosition(
                        chromeExe: chromeExe,
                        profileKey: prof.Key,
                        x: x,
                        y: y,
                        w: w,
                        h: h,
                        timeoutSeconds: _settings.WindowTimeout,
                        reuseExisting: _settings.ReuseExisting,
                        dwmCompensation: _settings.DwmCompensation,
                        dwmBorderOffset: _settings.DwmBorderOffset,
                        alreadyManagedHwnds: _managedHwnds,
                        enableNativeExtension: _settings.EnableNativeExtension
                    );

                    if (hwnd != IntPtr.Zero)
                    {
                        _managedHwnds.Add(hwnd);
                        successCount++;
                        App.Current?.Dispatcher?.Invoke(() => cell.StatusText = "Active");
                    }
                    else
                    {
                        App.Current?.Dispatcher?.Invoke(() => cell.StatusText = "Timeout");
                    }

                    int interval = Math.Max(50, _settings.LaunchInterval);
                    if (curIdx < total && interval > 0)
                    {
                        await Task.Delay(interval);
                    }
                }
            });

            IsLaunching = false;
            LaunchProgress = 1.0;
            StatusMessage = $"Completed! Positioned {successCount} of {total} Chrome profile window(s) to grid.";

            _ = Task.Delay(4000).ContinueWith(_ =>
            {
                App.Current?.Dispatcher?.Invoke(() => LaunchProgressVisible = false);
            });
        }

        private void ExecuteTileWindows()
        {
            if (SelectedMonitor == null) return;

            var activeWindows = WindowPlacementService.GetChromeWindows();
            if (activeWindows.Count == 0)
            {
                StatusMessage = "No active Chrome windows found to tile.";
                return;
            }

            var targets = GridCells.Where(c => c.AssignedProfile != null).ToList();
            if (targets.Count == 0) targets = GridCells.ToList();

            int count = Math.Min(activeWindows.Count, targets.Count);
            for (int i = 0; i < count; i++)
            {
                var (hwnd, _, _) = activeWindows[i];
                var cell = targets[i];

                var (x, y, w, h) = WindowPlacementService.CalculateCellRect(
                    SelectedMonitor,
                    GridRows,
                    GridCols,
                    cell.Row,
                    cell.Col,
                    gap: CellGap,
                    useFullScreen: UseFullScreen,
                    margins: _settings.ScreenMargins,
                    cellOffsets: _settings.CellOffsets,
                    colWeights: _settings.ColWeights,
                    rowWeights: _settings.RowWeights
                );

                WindowPlacementService.PositionWindow(
                    hwnd,
                    x, y, w, h,
                    dwmCompensation: _settings.DwmCompensation,
                    dwmBorderOffset: _settings.DwmBorderOffset
                );
                _managedHwnds.Add(hwnd);
            }

            StatusMessage = $"Tiled {count} active Chrome window(s) onto {SelectedMonitor.DisplayLabel}.";
        }

        private void ExecuteCloseManagedChrome()
        {
            string protKey = _settings.ProtectedProfileKey;
            var protProf = _allProfiles.FirstOrDefault(p => string.Equals(p.Key, protKey, StringComparison.OrdinalIgnoreCase));
            string protName = protProf?.DisplayName ?? "";

            int closed = ChromeLauncher.CloseManagedWindows(_managedHwnds, protKey, protName);

            foreach (var cell in GridCells)
            {
                cell.StatusText = string.Empty;
            }

            StatusMessage = $"Closed {closed} Chrome window(s) cleanly. Protected profile '{(!string.IsNullOrWhiteSpace(protName) ? protName : protKey)}' remained untouched.";
        }

        private void ExecuteToggleProtect(ChromeProfile profile)
        {
            if (string.Equals(_settings.ProtectedProfileKey, profile.Key, StringComparison.OrdinalIgnoreCase))
            {
                _settings.ProtectedProfileKey = string.Empty;
                profile.IsProtected = false;
                StatusMessage = $"Removed protected status from '{profile.DisplayName}'.";
            }
            else
            {
                foreach (var p in _allProfiles) p.IsProtected = false;
                _settings.ProtectedProfileKey = profile.Key;
                profile.IsProtected = true;
                StatusMessage = $"🛡️ Set '{profile.DisplayName}' as Protected Personal Profile (excluded from Auto-Populate & Closure).";
            }
            _storageService.SaveSettings(_settings);
            ApplyFilter();
        }

        private void ExecuteQuickAdd(ChromeProfile profile)
        {
            var emptyCell = GridCells.FirstOrDefault(c => c.AssignedProfile == null);
            if (emptyCell != null)
            {
                emptyCell.AssignedProfile = profile;
                SaveAutoState();
                RebuildThunderGrid();
                StatusMessage = $"Assigned '{profile.DisplayName}' to Cell [R{emptyCell.Row + 1}, C{emptyCell.Col + 1}].";
            }
            else
            {
                StatusMessage = "All grid cells are currently occupied.";
            }
        }

        private void ExecuteCellClicked(GridCellItem cell)
        {
            if (_selectedProfileForPlacement != null)
            {
                cell.AssignedProfile = _selectedProfileForPlacement;
                StatusMessage = $"Placed '{_selectedProfileForPlacement.DisplayName}' into Cell [R{cell.Row + 1}, C{cell.Col + 1}].";
                _selectedProfileForPlacement = null;
                SaveAutoState();
                RebuildThunderGrid();
            }
            else
            {
                var modal = new ProfilePickerModal(_allProfiles.ToList());
                if (modal.ShowDialog() == true && modal.SelectedProfile != null)
                {
                    cell.AssignedProfile = modal.SelectedProfile;
                    SaveAutoState();
                    RebuildThunderGrid();
                    StatusMessage = $"Assigned '{modal.SelectedProfile.DisplayName}' to Cell [R{cell.Row + 1}, C{cell.Col + 1}].";
                }
            }
        }

        #endregion

        #region Thunder Configuration

        private void ExecuteSaveThunderPreset()
        {
            int.TryParse(ThunderMembers, out int mems);
            var cfg = new ThunderConfig
            {
                Region = ThunderRegion,
                VtData = new ThunderVtData
                {
                    City = ThunderCenter,
                    Category = ThunderCategory,
                    Type = ThunderVisaType,
                    Members = Math.Max(1, mems)
                }
            };

            string name = ThunderPresetName.Trim();
            if (string.IsNullOrWhiteSpace(name)) name = "Custom Preset";

            _thunderPresets[name] = cfg;
            _thunderService.SavePresets(_thunderPresets);
            ThunderPresetNames = new ObservableCollection<string>(_thunderPresets.Keys);
            ThunderPresetName = name;
            StatusMessage = $"Saved Thunder preset: '{name}'.";
        }

        private void ExecuteDeleteThunderPreset()
        {
            if (ThunderPresetName == "Default")
            {
                StatusMessage = "⚠️ Cannot delete the 'Default' preset.";
                return;
            }

            if (_thunderPresets.Remove(ThunderPresetName))
            {
                _thunderService.SavePresets(_thunderPresets);
                ThunderPresetNames = new ObservableCollection<string>(_thunderPresets.Keys);
                ThunderPresetName = ThunderPresetNames.FirstOrDefault() ?? "Default";
                StatusMessage = "Deleted Thunder preset.";
            }
        }

        private void ExecuteApplyThunderUnifiedConfig()
        {
            var selected = ThunderCells.Where(c => c.IsSelected).ToList();
            if (selected.Count == 0)
            {
                StatusMessage = "⚠️ No Chrome instances selected in Thunder matrix. Select tiles first.";
                return;
            }

            int.TryParse(ThunderMembers, out int mems);
            var unifiedCfg = new ThunderConfig
            {
                Region = ThunderRegion,
                VtData = new ThunderVtData
                {
                    City = ThunderCenter,
                    Category = ThunderCategory,
                    Type = ThunderVisaType,
                    Members = Math.Max(1, mems)
                }
            };

            foreach (var cell in selected)
            {
                cell.ApplyConfig(unifiedCfg);
                cell.UpdateCityColors();
                _thunderCellConfigs[$"{cell.Row},{cell.Col}"] = unifiedCfg;
            }

            _thunderService.SaveCellConfigs(_thunderCellConfigs);

            // Broadcast to connected tabs
            _wsServer.BroadcastThunderConfig(unifiedCfg, null);
            StatusMessage = $"⚡ Unified Thunder configuration applied to {selected.Count} cells & dispatched to tabs.";
            RunConflictDetection();
        }

        public void RunConflictDetection()
        {
            int conflicts = 0;

            var assigned = ThunderCells.Where(c => c.Profile != null).ToList();
            var profileOccurrences = assigned
                .GroupBy(c => c.Profile!.Key, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(g => g.Key, g => g.ToList(), StringComparer.OrdinalIgnoreCase);

            foreach (var cell in ThunderCells)
            {
                cell.HasConflict = false;
                cell.ConflictMessage = string.Empty;

                if (cell.Profile == null)
                {
                    cell.HasConflict = true;
                    cell.ConflictMessage = "Unassigned cell: no profile assigned.";
                    conflicts++;
                    continue;
                }

                if (profileOccurrences.TryGetValue(cell.Profile.Key, out var dupList) && dupList.Count > 1)
                {
                    cell.HasConflict = true;
                    cell.ConflictMessage = $"Duplicate profile: '{cell.Profile.DisplayName}' assigned to {dupList.Count} cells.";
                    conflicts++;
                }
            }

            ConflictCount = conflicts;
            if (conflicts == 0)
            {
                ConflictBannerText = $"🟢 Configuration Clean: {ThunderCells.Count} cells uniquely assigned & configured with 0 conflicts.";
                ConflictBannerColor = "#10B981";
            }
            else
            {
                ConflictBannerText = $"⚠️ {conflicts} Configuration Conflict(s) Detected! (Duplicate profile assignments or empty cells).";
                ConflictBannerColor = "#EF4444";
            }

            OnPropertyChanged(nameof(ConflictCount));
            OnPropertyChanged(nameof(ConflictBannerText));
            OnPropertyChanged(nameof(ConflictBannerColor));
            OnPropertyChanged(nameof(HasConflicts));
        }

        private void ExecuteAutoFixConflicts()
        {
            var usedKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            string protKey = _settings.ProtectedProfileKey;
            var availableProfiles = _allProfiles
                .Where(p => !p.IsProtected && (string.IsNullOrWhiteSpace(protKey) || !string.Equals(p.Key, protKey, StringComparison.OrdinalIgnoreCase)))
                .ToList();

            int fixedCount = 0;
            foreach (var cell in ThunderCells)
            {
                if (cell.Profile != null && !usedKeys.Contains(cell.Profile.Key))
                {
                    usedKeys.Add(cell.Profile.Key);
                }
                else
                {
                    var candidate = availableProfiles.FirstOrDefault(p => !usedKeys.Contains(p.Key));
                    if (candidate != null)
                    {
                        cell.Profile = candidate;
                        usedKeys.Add(candidate.Key);

                        var gc = GridCells.FirstOrDefault(g => g.Row == cell.Row && g.Col == cell.Col);
                        if (gc != null) gc.AssignedProfile = candidate;

                        fixedCount++;
                    }
                }
            }

            RunConflictDetection();
            SaveAutoState();
            StatusMessage = $"⚡ Auto-Fix resolved {fixedCount} cell conflict(s) with unique profiles.";
        }

        private void ExecuteThunderDistributeEvenly()
        {
            var targets = ThunderCells.Where(c => c.IsSelected).ToList();
            if (targets.Count == 0) targets = ThunderCells.ToList();

            if (targets.Count == 0 || AvailableCenters.Count == 0) return;

            int.TryParse(ThunderMembers, out int mems);
            int centerIdx = 0;

            foreach (var cell in targets)
            {
                string targetCity = AvailableCenters[centerIdx % AvailableCenters.Count];
                centerIdx++;

                cell.City = targetCity;
                cell.VisaType = ThunderVisaType;
                cell.Category = ThunderCategory;
                cell.Members = Math.Max(1, mems);
                cell.UpdateCityColors();

                _thunderCellConfigs[$"{cell.Row},{cell.Col}"] = cell.ToConfig(ThunderRegion);
            }

            _thunderService.SaveCellConfigs(_thunderCellConfigs);
            RunConflictDetection();
            StatusMessage = $"⚖️ Evenly distributed {targets.Count} cells across {AvailableCenters.Count} centers ({string.Join(", ", AvailableCenters)}).";
        }

        private void ExecuteThunderDistributeByGroup()
        {
            var targets = ThunderCells.Where(c => c.IsSelected).ToList();
            if (targets.Count == 0) targets = ThunderCells.ToList();

            int count = 0;
            foreach (var cell in targets)
            {
                if (cell.Profile == null) continue;

                if (cell.Profile.GroupId == "prt" || cell.Profile.GroupName.Contains("Portugal", StringComparison.OrdinalIgnoreCase))
                {
                    cell.City = "Casablanca";
                    cell.VisaType = "Short Stay Visa";
                    cell.Category = "Normal";
                    cell.Members = 1;
                    cell.UpdateCityColors();
                    _thunderCellConfigs[$"{cell.Row},{cell.Col}"] = cell.ToConfig("Portugal");
                    count++;
                }
                else
                {
                    cell.City = ThunderCenter;
                    cell.VisaType = ThunderVisaType;
                    cell.Category = ThunderCategory;
                    cell.Members = 1;
                    cell.UpdateCityColors();
                    _thunderCellConfigs[$"{cell.Row},{cell.Col}"] = cell.ToConfig("Spain");
                    count++;
                }
            }

            _thunderService.SaveCellConfigs(_thunderCellConfigs);
            RunConflictDetection();
            StatusMessage = $"🏷️ Applied group-matched configuration to {count} cells.";
        }

        private void ExecuteThunderSelectByCity(object? param)
        {
            string city = param?.ToString() ?? "";
            foreach (var cell in ThunderCells)
            {
                cell.IsSelected = string.Equals(cell.City, city, StringComparison.OrdinalIgnoreCase);
            }
            OnPropertyChanged(nameof(ThunderTargetCountText));
            StatusMessage = $"Selected all cells targeting '{city}'.";
        }

        #endregion

        #region Refresh Server & Communication

        private void StartWebSocketServer()
        {
            _wsServer.OnClientsChanged += (count, clients) =>
            {
                App.Current?.Dispatcher?.BeginInvoke(System.Windows.Threading.DispatcherPriority.Background, new Action(() =>
                {
                    ConnectedTabs = new ObservableCollection<ConnectedTab>(clients);
                    OnPropertyChanged(nameof(ServerPillText));
                    OnPropertyChanged(nameof(ServerPillColor));
                }));
            };

            _wsServer.OnAckReceived += ack =>
            {
                App.Current?.Dispatcher?.BeginInvoke(System.Windows.Threading.DispatcherPriority.Normal, new Action(() =>
                {
                    OnPropertyChanged(nameof(TotalAcksSuccessCount));
                    OnPropertyChanged(nameof(TotalAcksFailedCount));
                    if (ack.TryGetValue("result", out var r) && r?.ToString() == "Success" && _settings.SoundAlertsEnabled)
                    {
                        AudioAlertService.PlaySuccessBeep();
                    }
                }));
            };

            _wsServer.OnLog += (msg, lvl) =>
            {
                App.Current?.Dispatcher?.BeginInvoke(System.Windows.Threading.DispatcherPriority.Background, new Action(() =>
                {
                    string time = DateTime.Now.ToString("HH:mm:ss");
                    ActivityLogs.Insert(0, $"[{time}] [{lvl}] {msg}");
                    if (ActivityLogs.Count > 100) ActivityLogs.RemoveAt(ActivityLogs.Count - 1);
                }));
            };

            _wsServer.Start(_settings.RefreshServerPort);
        }

        private void ExecuteTriggerRefreshAll()
        {
            int clientCount = Math.Max(ConnectedTabs.Count, _wsServer.GetClientsSnapshot().Count);
            _wsServer.BroadcastRefresh(RefreshXPath, RefreshText, RefreshClassName, StaggerMs);
            OnPropertyChanged(nameof(TotalBroadcastsCount));

            if (clientCount == 0)
            {
                StatusMessage = $"⚠️ Refresh broadcast dispatched, but 0 Chrome tabs are connected on port {_wsServer.Port}.";
            }
            else
            {
                StatusMessage = $"⚡ Broadcasted Refresh command to {clientCount} connected Chrome tab(s).";
            }
        }

        private void ExecuteDispatchSlotPage(string target)
        {
            int clientCount = Math.Max(ConnectedTabs.Count, _wsServer.GetClientsSnapshot().Count);
            _wsServer.BroadcastSlotClick(
                target,
                _slotASec, _slotAMs, _slotAStep,
                _slotBSec, _slotBMs, _slotBStep
            );
            OnPropertyChanged(nameof(TotalBroadcastsCount));

            if (clientCount == 0)
            {
                StatusMessage = $"⚠️ Slot-click ({target.ToUpper()}) sent, but 0 Chrome tabs are connected on port {_wsServer.Port}.";
            }
            else
            {
                if (target == "a")
                {
                    StatusMessage = $"⚡ Slot-Click → Calendar (Page A) | {clientCount} tab(s) | Sec: {_slotASec:02d}s | MS: {_slotAMs}ms | Step: +{_slotAStep}ms";
                }
                else if (target == "b")
                {
                    StatusMessage = $"⚡ Slot-Click → VisaType (Page B) | {clientCount} tab(s) | Sec: {_slotBSec:02d}s | MS: {_slotBMs}ms | Step: +{_slotBStep}ms";
                }
                else
                {
                    StatusMessage = $"⚡ Slot-Click → {clientCount} Chrome(s) — A: {_slotASec:02d}s/{_slotAMs}ms (+{_slotAStep}ms) | B: {_slotBSec:02d}s/{_slotBMs}ms (+{_slotBStep}ms)";
                }
            }
        }

        private void ExecuteHardRefreshAll()
        {
            var confirm = MessageBox.Show(
                "Are you sure you want to hard refresh all Chrome pages at once?\n\nThis will trigger an immediate full reload across all active Chrome windows.",
                "Confirm Hard Refresh All",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);

            if (confirm != MessageBoxResult.Yes) return;

            // 1. Broadcast hard reload via WebSocket & HTTP poll fallback
            _wsServer.BroadcastHardReload(StaggerMs);
            OnPropertyChanged(nameof(TotalBroadcastsCount));

            // 2. Win32 F5 post to all managed and active Chrome windows
            var activeWindows = WindowPlacementService.GetChromeWindows();
            var targetHwnds = new HashSet<IntPtr>(_managedHwnds);
            foreach (var (h, _, _) in activeWindows)
            {
                targetHwnds.Add(h);
            }

            int count = 0;
            foreach (var hwnd in targetHwnds)
            {
                if (WindowPlacementService.SendHardReload(hwnd))
                {
                    count++;
                }
            }

            StatusMessage = $"🔄 Hard Refresh executed across {_wsServer.GetClientsSnapshot().Count} connected tab(s) and {count} Chrome window(s).";
        }

        private void ExecuteToggleServer()
        {
            if (_wsServer.IsRunning)
            {
                _wsServer.Stop();
            }
            else
            {
                _wsServer.Start(_settings.RefreshServerPort);
            }
            OnPropertyChanged(nameof(ServerPillText));
            OnPropertyChanged(nameof(ServerPillColor));
        }

        private void ConfigureAutoRefresh(string choice)
        {
            _autoRefreshTimer?.Stop();
            _autoRefreshTimer = null;

            int seconds = choice switch
            {
                "15 seconds" => 15,
                "30 seconds" => 30,
                "1 minute" => 60,
                "2 minutes" => 120,
                "5 minutes" => 300,
                _ => 0
            };

            if (seconds > 0)
            {
                _autoRefreshTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(seconds) };
                _autoRefreshTimer.Tick += (s, e) => ExecuteTriggerRefreshAll();
                _autoRefreshTimer.Start();
                StatusMessage = $"⏱️ Auto-Refresh active: every {choice}.";
            }
            else
            {
                StatusMessage = "Auto-Refresh disabled.";
            }
        }

        private void ExecuteCopyUserscript()
        {
            if (File.Exists(_wsServer.UserscriptFilePath))
            {
                string content = File.ReadAllText(_wsServer.UserscriptFilePath);
                Clipboard.SetText(content);
                StatusMessage = "✅ Tampermonkey userscript copied to clipboard! Paste it into Tampermonkey.";
            }
            else
            {
                StatusMessage = "⚠️ Userscript file not found to copy.";
            }
        }

        private void ExecuteOpenInstallScriptPage()
        {
            string url = $"http://127.0.0.1:{_wsServer.Port}/userscript.user.js";
            try
            {
                Process.Start(new ProcessStartInfo { FileName = url, UseShellExecute = true });
                StatusMessage = $"Opened 1-click install URL in browser: {url}";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error opening browser: {ex.Message}";
            }
        }

        private void ExecuteLiveUpdateScriptInOpenTabs()
        {
            string url = $"http://127.0.0.1:{_wsServer.Port}/userscript.user.js";
            var targets = GridCells.Where(c => c.AssignedProfile != null).Select(c => c.AssignedProfile!).DistinctBy(p => p.Key).ToList();
            if (targets.Count == 0) targets = _allProfiles.ToList();

            string chromeExe = !string.IsNullOrWhiteSpace(_settings.ChromePathOverride) && File.Exists(_settings.ChromePathOverride)
                ? _settings.ChromePathOverride
                : ChromeProfileScanner.FindChromeExecutable();

            Task.Run(async () =>
            {
                int count = 0;
                foreach (var p in targets)
                {
                    // Omission of --new-window opens as a tab in existing window without moving it
                    var psi = new ProcessStartInfo
                    {
                        FileName = chromeExe,
                        Arguments = $"--profile-directory=\"{p.Key}\" \"{url}\"",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    Process.Start(psi);
                    count++;
                    await Task.Delay(120);
                }

                App.Current?.Dispatcher?.Invoke(() =>
                {
                    StatusMessage = $"✅ Opened Tampermonkey update tab in {count} profile window(s)! Grid layout 100% intact.";
                });
            });
        }

        public string GlobalExtensionPath => ExtensionDeploymentService.GlobalExtensionDirectory;
        public bool IsGlobalExtensionReady => ExtensionDeploymentService.IsGlobalExtensionReady();

        private void ExecuteCopyExtensionPath()
        {
            try
            {
                ExtensionDeploymentService.EnsureExtensionDeployed();
                Clipboard.SetText(ExtensionDeploymentService.GlobalExtensionDirectory);
                StatusMessage = $"📋 Copied '{ExtensionDeploymentService.GlobalExtensionDirectory}' to clipboard! Paste into Chrome 'Load unpacked' dialog.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error copying path: {ex.Message}";
            }
        }

        private void ExecuteOpenExtensionFolder()
        {
            string extDir = ExtensionDeploymentService.EnsureExtensionDeployed();
            if (Directory.Exists(extDir))
            {
                try
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = extDir,
                        UseShellExecute = true
                    });
                    StatusMessage = $"📂 Opened extension directory: {extDir}";
                }
                catch (Exception ex)
                {
                    StatusMessage = $"Error opening folder: {ex.Message}";
                }
            }
            else
            {
                StatusMessage = "⚠️ ChromeGridExtension directory not found.";
            }
        }

        private void ExecuteOpenChromeExtensionsPage()
        {
            string chromeExe = !string.IsNullOrWhiteSpace(_settings.ChromePathOverride) && File.Exists(_settings.ChromePathOverride)
                ? _settings.ChromePathOverride
                : ChromeProfileScanner.FindChromeExecutable();

            if (!string.IsNullOrWhiteSpace(chromeExe) && File.Exists(chromeExe))
            {
                try
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = chromeExe,
                        Arguments = "chrome://extensions",
                        UseShellExecute = false
                    });
                    StatusMessage = "🌐 Opened chrome://extensions in Chrome. Turn on Developer mode & click 'Load unpacked'.";
                }
                catch (Exception ex)
                {
                    StatusMessage = $"Error opening Chrome: {ex.Message}";
                }
            }
            else
            {
                StatusMessage = "⚠️ Chrome executable not found. Configure in Settings (⚙️).";
            }
        }

        private void ExecuteSyncGlobalExtension()
        {
            try
            {
                ExtensionDeploymentService.ForceSyncGlobalFiles();
                OnPropertyChanged(nameof(IsGlobalExtensionReady));
                _wsServer.UpdateExtensionBuildHash();
                _wsServer.BroadcastReloadExtension();
                StatusMessage = "🔄 Successfully updated C:\\ChromeGridExtension! Auto-reload command sent to all active Chrome windows.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error syncing files: {ex.Message}";
            }
        }

        private void ExecuteReloadAllExtensions()
        {
            try
            {
                _wsServer.BroadcastReloadExtension();
                StatusMessage = "⚡ Zero-click reload broadcast sent! All running Chrome extensions are reloading from disk.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error broadcasting reload: {ex.Message}";
            }
        }

        #endregion

        #region Modals & Persistence

        private void ExecuteOpenFineControlModal()
        {
            var modal = new FineControlModal(_settings, Monitors.ToList(), GridRows, GridCols);
            if (modal.ShowDialog() == true)
            {
                _settings = modal.UpdatedSettings;
                _storageService.SaveSettings(_settings);
                CellGap = _settings.CellGap;
                UseFullScreen = _settings.UseFullScreen;
                UpdateCellResolutions();
                StatusMessage = "Applied fine positioning & screen fit calibration.";
            }
        }

        private void ExecuteOpenSaveLayoutModal()
        {
            var modal = new SaveLayoutModal($"Layout {GridRows}x{GridCols}");
            if (modal.ShowDialog() == true && !string.IsNullOrWhiteSpace(modal.LayoutName))
            {
                var preset = ExportCurrentLayout(modal.LayoutName);
                _storageService.SaveLayoutFile(modal.LayoutName, preset);
                StatusMessage = $"Saved layout preset '{modal.LayoutName}'.";
            }
        }

        private void ExecuteOpenLoadLayoutModal()
        {
            var modal = new LoadLayoutModal(_storageService);
            if (modal.ShowDialog() == true && modal.SelectedPreset != null)
            {
                ApplyLayoutPreset(modal.SelectedPreset);
                StatusMessage = $"Loaded layout preset '{modal.SelectedPreset.Name}'.";
            }
        }

        private void ExecuteOpenNewGroupModal()
        {
            var modal = new NewGroupModal(_allProfiles.ToList());
            if (modal.ShowDialog() == true && modal.CreatedGroup != null)
            {
                var customGroups = _storageService.LoadCustomGroups();
                customGroups.Add(modal.CreatedGroup);
                _storageService.SaveGroupsData(customGroups);

                ProfileGroups.Add(modal.CreatedGroup);
                ExecuteScanProfiles();
                StatusMessage = $"Created custom profile group '{modal.CreatedGroup.Name}'.";
            }
        }

        private void ExecuteOpenSettingsModal()
        {
            var modal = new SettingsModal(_settings, Monitors.ToList(), _allProfiles.ToList());
            if (modal.ShowDialog() == true)
            {
                _settings = modal.UpdatedSettings;
                _storageService.SaveSettings(_settings);
                CellGap = _settings.CellGap;
                UseFullScreen = _settings.UseFullScreen;
                ExecuteScanProfiles();
                UpdateCellResolutions();
                StatusMessage = "Settings saved successfully.";
            }
        }

        private LayoutPreset ExportCurrentLayout(string name = "Current")
        {
            var preset = new LayoutPreset
            {
                Name = name,
                Rows = GridRows,
                Cols = GridCols,
                MonitorIndex = SelectedMonitor?.Index ?? 0,
                UseFullScreen = UseFullScreen,
                CellGap = CellGap,
                DwmCompensation = _settings.DwmCompensation,
                DwmBorderOffset = _settings.DwmBorderOffset,
                ScreenMargins = _settings.ScreenMargins,
                CellOffsets = _settings.CellOffsets,
                ColWeights = _settings.ColWeights,
                RowWeights = _settings.RowWeights
            };

            foreach (var cell in GridCells)
            {
                if (cell.AssignedProfile != null)
                {
                    preset.Assignments[$"{cell.Row},{cell.Col}"] = new CellAssignmentData
                    {
                        Key = cell.AssignedProfile.Key,
                        Name = cell.AssignedProfile.Name,
                        DisplayName = cell.AssignedProfile.DisplayName
                    };
                }
            }

            return preset;
        }

        private void ApplyLayoutPreset(LayoutPreset preset)
        {
            GridRows = Math.Max(1, preset.Rows);
            GridCols = Math.Max(1, preset.Cols);
            UseFullScreen = preset.UseFullScreen;
            CellGap = preset.CellGap;
            _settings.ScreenMargins = preset.ScreenMargins;
            _settings.CellOffsets = preset.CellOffsets;
            _settings.ColWeights = preset.ColWeights;
            _settings.RowWeights = preset.RowWeights;

            if (preset.MonitorIndex < Monitors.Count)
            {
                SelectedMonitor = Monitors[preset.MonitorIndex];
            }

            var profileMap = _allProfiles.ToDictionary(p => p.Key, p => p);

            foreach (var cell in GridCells)
            {
                string key = $"{cell.Row},{cell.Col}";
                if (preset.Assignments.TryGetValue(key, out var data))
                {
                    if (profileMap.TryGetValue(data.Key, out var matched))
                    {
                        cell.AssignedProfile = matched;
                    }
                    else
                    {
                        cell.AssignedProfile = new ChromeProfile { Key = data.Key, Name = data.Name };
                    }
                }
                else
                {
                    cell.AssignedProfile = null;
                }
            }

            UpdateCellResolutions();
            RebuildThunderGrid();
        }

        private void SaveAutoState()
        {
            var preset = ExportCurrentLayout("LastLayout");
            _storageService.SaveLastLayout(preset);
        }

        #endregion
    }

    public class ThunderRowSelectorItem : ViewModelBase
    {
        public int RowIndex { get; set; }
        public string Label { get; set; } = string.Empty;
        public ICommand SelectCommand { get; set; } = null!;
    }
}

using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class SettingsModal : Window
    {
        public AppSettings CurrentSettings { get; private set; }
        public AppSettings UpdatedSettings => CurrentSettings;

        public SettingsModal(AppSettings settings, List<MonitorInfo>? monitors = null, List<ChromeProfile>? profiles = null)
        {
            InitializeComponent();
            CurrentSettings = settings;

            CmbBrowser.ItemsSource = new List<string> { "Chrome", "Brave", "Edge" };
            if (string.Equals(settings.SelectedBrowser, "Brave", System.StringComparison.OrdinalIgnoreCase))
                CmbBrowser.SelectedItem = "Brave";
            else if (string.Equals(settings.SelectedBrowser, "Edge", System.StringComparison.OrdinalIgnoreCase))
                CmbBrowser.SelectedItem = "Edge";
            else
                CmbBrowser.SelectedItem = "Chrome";

            TxtChromeExe.Text = settings.ChromePathOverride;
            TxtBraveExe.Text = settings.BravePathOverride;
            TxtEdgeExe.Text = settings.EdgePathOverride;
            TxtChromeUserData.Text = settings.ChromeUserDataOverride;
            TxtBraveUserData.Text = settings.BraveUserDataOverride;
            TxtEdgeUserData.Text = settings.EdgeUserDataOverride;

            TxtTargetUrl.Text = settings.TargetRefreshUrl;
            TxtPort.Text = settings.RefreshServerPort.ToString();
            TxtLaunchInterval.Text = settings.LaunchInterval.ToString();
            TxtWindowTimeout.Text = settings.WindowTimeout.ToString("F1", CultureInfo.InvariantCulture);
            TxtProtectedProfile.Text = settings.ProtectedProfileKey;
            ChkEnableNativeExtension.IsChecked = settings.EnableNativeExtension;
            ChkSoundAlerts.IsChecked = settings.SoundAlertsEnabled;
            ChkDwmCompensation.IsChecked = settings.DwmCompensation;
            ChkMinimizeOnLaunch.IsChecked = settings.MinimizeOnLaunch;
        }

        private void OnBrowseChromeClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "Chrome Executable (chrome.exe)|chrome.exe|Executable Files (*.exe)|*.exe|All Files (*.*)|*.*",
                Title = "Select Google Chrome Executable"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtChromeExe.Text = dlg.FileName;
            }
        }

        private void OnBrowseBraveClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "Brave Executable (brave.exe)|brave.exe|Executable Files (*.exe)|*.exe|All Files (*.*)|*.*",
                Title = "Select Brave Browser Executable"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtBraveExe.Text = dlg.FileName;
            }
        }

        private void OnBrowseEdgeClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "Edge Executable (msedge.exe)|msedge.exe|Executable Files (*.exe)|*.exe|All Files (*.*)|*.*",
                Title = "Select Microsoft Edge Executable"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtEdgeExe.Text = dlg.FileName;
            }
        }

        private void OnBrowseChromeUserDataClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFolderDialog
            {
                Title = "Select Chrome User Data Directory"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtChromeUserData.Text = dlg.FolderName;
            }
        }

        private void OnBrowseBraveUserDataClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFolderDialog
            {
                Title = "Select Brave User Data Directory"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtBraveUserData.Text = dlg.FolderName;
            }
        }

        private void OnBrowseEdgeUserDataClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFolderDialog
            {
                Title = "Select Edge User Data Directory"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtEdgeUserData.Text = dlg.FolderName;
            }
        }

        private void OnSaveClick(object sender, RoutedEventArgs e)
        {
            CurrentSettings.SelectedBrowser = CmbBrowser.SelectedItem?.ToString() ?? "Chrome";
            CurrentSettings.ChromePathOverride = TxtChromeExe.Text.Trim();
            CurrentSettings.BravePathOverride = TxtBraveExe.Text.Trim();
            CurrentSettings.EdgePathOverride = TxtEdgeExe.Text.Trim();
            CurrentSettings.ChromeUserDataOverride = TxtChromeUserData.Text.Trim();
            CurrentSettings.BraveUserDataOverride = TxtBraveUserData.Text.Trim();
            CurrentSettings.EdgeUserDataOverride = TxtEdgeUserData.Text.Trim();

            CurrentSettings.TargetRefreshUrl = TxtTargetUrl.Text.Trim();

            if (int.TryParse(TxtPort.Text.Trim(), out int port))
            {
                CurrentSettings.RefreshServerPort = port;
            }

            if (int.TryParse(TxtLaunchInterval.Text.Trim(), out int interval))
            {
                CurrentSettings.LaunchInterval = interval;
            }

            if (double.TryParse(TxtWindowTimeout.Text.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out double timeout))
            {
                CurrentSettings.WindowTimeout = timeout;
            }

            CurrentSettings.ProtectedProfileKey = string.IsNullOrWhiteSpace(TxtProtectedProfile.Text) ? "Default" : TxtProtectedProfile.Text.Trim();
            CurrentSettings.EnableNativeExtension = ChkEnableNativeExtension.IsChecked ?? true;
            CurrentSettings.SoundAlertsEnabled = ChkSoundAlerts.IsChecked ?? true;
            CurrentSettings.DwmCompensation = ChkDwmCompensation.IsChecked ?? true;
            CurrentSettings.MinimizeOnLaunch = ChkMinimizeOnLaunch.IsChecked ?? false;

            DialogResult = true;
            Close();
        }

        private void OnCancelClick(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}

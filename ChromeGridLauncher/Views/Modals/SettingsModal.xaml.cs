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

            TxtChromeExe.Text = settings.ChromePathOverride;
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
                Filter = "Executable Files (*.exe)|*.exe|All Files (*.*)|*.*",
                Title = "Select Chrome Executable"
            };

            if (dlg.ShowDialog() == true)
            {
                TxtChromeExe.Text = dlg.FileName;
            }
        }

        private void OnSaveClick(object sender, RoutedEventArgs e)
        {
            CurrentSettings.ChromePathOverride = TxtChromeExe.Text.Trim();
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

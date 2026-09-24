using System.Collections.Generic;
using System.Windows;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class FineControlModal : Window
    {
        public AppSettings UpdatedSettings { get; private set; }

        public FineControlModal(AppSettings currentSettings, List<MonitorInfo> monitors, int rows, int cols)
        {
            InitializeComponent();
            UpdatedSettings = new AppSettings
            {
                Theme = currentSettings.Theme,
                MonitorIndex = currentSettings.MonitorIndex,
                CellGap = currentSettings.CellGap,
                WindowTimeout = currentSettings.WindowTimeout,
                LaunchInterval = currentSettings.LaunchInterval,
                ReuseExisting = currentSettings.ReuseExisting,
                CustomRows = currentSettings.CustomRows,
                CustomCols = currentSettings.CustomCols,
                ChromePathOverride = currentSettings.ChromePathOverride,
                ProtectedProfileKey = currentSettings.ProtectedProfileKey,
                UseFullScreen = currentSettings.UseFullScreen,
                ScreenMargins = new ScreenMargins
                {
                    Top = currentSettings.ScreenMargins.Top,
                    Bottom = currentSettings.ScreenMargins.Bottom,
                    Left = currentSettings.ScreenMargins.Left,
                    Right = currentSettings.ScreenMargins.Right
                },
                DwmCompensation = currentSettings.DwmCompensation,
                DwmBorderOffset = currentSettings.DwmBorderOffset,
                RefreshServerPort = currentSettings.RefreshServerPort,
                AutoStartRefreshServer = currentSettings.AutoStartRefreshServer,
                SoundAlertsEnabled = currentSettings.SoundAlertsEnabled,
                TargetRefreshUrl = currentSettings.TargetRefreshUrl
            };

            // Initialize controls
            if (UpdatedSettings.UseFullScreen)
            {
                RadioFullScreen.IsChecked = true;
            }
            else
            {
                RadioWorkArea.IsChecked = true;
            }

            TxtMarginTop.Text = UpdatedSettings.ScreenMargins.Top.ToString();
            TxtMarginBottom.Text = UpdatedSettings.ScreenMargins.Bottom.ToString();
            TxtMarginLeft.Text = UpdatedSettings.ScreenMargins.Left.ToString();
            TxtMarginRight.Text = UpdatedSettings.ScreenMargins.Right.ToString();

            ChkShadowCompensate.IsChecked = UpdatedSettings.DwmCompensation;
            TxtShadowOffset.Text = UpdatedSettings.DwmBorderOffset.ToString();
        }

        private void OnResetClick(object sender, RoutedEventArgs e)
        {
            RadioWorkArea.IsChecked = true;
            TxtMarginTop.Text = "0";
            TxtMarginBottom.Text = "0";
            TxtMarginLeft.Text = "0";
            TxtMarginRight.Text = "0";
            ChkShadowCompensate.IsChecked = true;
            TxtShadowOffset.Text = "7";
        }

        private void OnApplyClick(object sender, RoutedEventArgs e)
        {
            UpdatedSettings.UseFullScreen = RadioFullScreen.IsChecked == true;

            int.TryParse(TxtMarginTop.Text, out int mTop);
            int.TryParse(TxtMarginBottom.Text, out int mBot);
            int.TryParse(TxtMarginLeft.Text, out int mLeft);
            int.TryParse(TxtMarginRight.Text, out int mRight);

            UpdatedSettings.ScreenMargins.Top = mTop;
            UpdatedSettings.ScreenMargins.Bottom = mBot;
            UpdatedSettings.ScreenMargins.Left = mLeft;
            UpdatedSettings.ScreenMargins.Right = mRight;

            UpdatedSettings.DwmCompensation = ChkShadowCompensate.IsChecked == true;
            if (int.TryParse(TxtShadowOffset.Text, out int sOffset))
            {
                UpdatedSettings.DwmBorderOffset = sOffset;
            }

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

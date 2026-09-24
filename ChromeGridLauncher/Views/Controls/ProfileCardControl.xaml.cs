using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using ChromeGridLauncher.Models;
using ChromeGridLauncher.ViewModels;

namespace ChromeGridLauncher.Views.Controls
{
    public partial class ProfileCardControl : UserControl
    {
        public ProfileCardControl()
        {
            InitializeComponent();
        }

        private void OnCardClick(object sender, MouseButtonEventArgs e)
        {
            if (DataContext is ChromeProfile profile)
            {
                var vm = FindParentMainViewModel();
                vm?.SelectProfileForPlacementCommand.Execute(profile);
            }
        }

        private void OnQuickAddClick(object sender, RoutedEventArgs e)
        {
            e.Handled = true;
            if (DataContext is ChromeProfile profile)
            {
                var vm = FindParentMainViewModel();
                vm?.QuickAddProfileCommand.Execute(profile);
            }
        }

        private void OnProtectClick(object sender, RoutedEventArgs e)
        {
            e.Handled = true;
            if (DataContext is ChromeProfile profile)
            {
                var vm = FindParentMainViewModel();
                vm?.ToggleProtectProfileCommand.Execute(profile);
            }
        }

        private MainViewModel? FindParentMainViewModel()
        {
            var window = Window.GetWindow(this);
            return window?.DataContext as MainViewModel;
        }
    }
}

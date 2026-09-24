using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using ChromeGridLauncher.Models;
using ChromeGridLauncher.ViewModels;

namespace ChromeGridLauncher.Views.Controls
{
    public partial class GridCellCardControl : UserControl
    {
        public GridCellCardControl()
        {
            InitializeComponent();
        }

        private void OnCardClick(object sender, MouseButtonEventArgs e)
        {
            if (DataContext is GridCellItem item)
            {
                var vm = FindParentMainViewModel();
                vm?.CellClickedCommand.Execute(item);
            }
        }

        private void OnClearClick(object sender, RoutedEventArgs e)
        {
            e.Handled = true;
            if (DataContext is GridCellItem item)
            {
                var vm = FindParentMainViewModel();
                vm?.ClearCellCommand.Execute(item);
            }
        }

        private void OnChangeProfileClick(object sender, RoutedEventArgs e)
        {
            e.Handled = true;
            if (DataContext is GridCellItem item)
            {
                var vm = FindParentMainViewModel();
                vm?.ChangeCellProfileCommand.Execute(item);
            }
        }

        private MainViewModel? FindParentMainViewModel()
        {
            var window = Window.GetWindow(this);
            return window?.DataContext as MainViewModel;
        }
    }
}

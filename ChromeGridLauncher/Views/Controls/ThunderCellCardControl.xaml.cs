using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using ChromeGridLauncher.ViewModels;

namespace ChromeGridLauncher.Views.Controls
{
    public partial class ThunderCellCardControl : UserControl
    {
        public ThunderCellCardControl()
        {
            InitializeComponent();
        }

        private void OnTileClick(object sender, MouseButtonEventArgs e)
        {
            if (DataContext is ThunderCellViewModel cell)
            {
                var vm = FindParentMainViewModel();
                vm?.ThunderToggleCellSelectionCommand.Execute(cell);
            }
        }

        private MainViewModel? FindParentMainViewModel()
        {
            var window = Window.GetWindow(this);
            return window?.DataContext as MainViewModel;
        }
    }
}

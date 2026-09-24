using System.Windows;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class SaveLayoutModal : Window
    {
        public string LayoutName { get; private set; } = string.Empty;

        public SaveLayoutModal(string defaultName = "")
        {
            InitializeComponent();
            TxtLayoutName.Text = defaultName;
        }

        private void OnSaveClick(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(TxtLayoutName.Text))
            {
                MessageBox.Show("Please enter a layout name.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            LayoutName = TxtLayoutName.Text.Trim();
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

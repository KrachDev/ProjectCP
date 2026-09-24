using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class CustomGridModal : Window, INotifyPropertyChanged
    {
        private int _rows;
        private int _cols;

        public int SelectedRows => _rows;
        public int SelectedCols => _cols;

        public int Rows
        {
            get => _rows;
            set { if (_rows != value) { _rows = value; OnPropertyChanged(); } }
        }

        public int Cols
        {
            get => _cols;
            set { if (_cols != value) { _cols = value; OnPropertyChanged(); } }
        }

        public CustomGridModal(int initialRows = 2, int initialCols = 2)
        {
            InitializeComponent();
            _rows = initialRows;
            _cols = initialCols;
            DataContext = this;
        }

        private void OnPresetClick(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is string tag)
            {
                var parts = tag.Split(',');
                if (parts.Length == 2 && int.TryParse(parts[0], out int r) && int.TryParse(parts[1], out int c))
                {
                    Rows = r;
                    Cols = c;
                }
            }
        }

        private void OnApplyClick(object sender, RoutedEventArgs e)
        {
            DialogResult = true;
            Close();
        }

        private void OnCancelClick(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? propName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propName));
        }
    }
}

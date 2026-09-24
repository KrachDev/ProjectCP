using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class ProfilePickerModal : Window
    {
        private readonly List<ChromeProfile> _allProfiles;
        public ChromeProfile? SelectedProfile { get; private set; }
        public bool ShouldClear { get; private set; }

        public ProfilePickerModal(IEnumerable<ChromeProfile> profiles)
        {
            InitializeComponent();
            _allProfiles = profiles.ToList();
            ProfilesListBox.ItemsSource = _allProfiles;
        }

        private void OnSearchTextChanged(object sender, TextChangedEventArgs e)
        {
            string query = TxtSearch.Text.Trim().ToLowerInvariant();
            if (string.IsNullOrEmpty(query))
            {
                ProfilesListBox.ItemsSource = _allProfiles;
            }
            else
            {
                ProfilesListBox.ItemsSource = _allProfiles.Where(p =>
                    p.DisplayName.ToLowerInvariant().Contains(query) ||
                    p.Key.ToLowerInvariant().Contains(query) ||
                    p.Subtitle.ToLowerInvariant().Contains(query) ||
                    (p.Email != null && p.Email.ToLowerInvariant().Contains(query))
                ).ToList();
            }
        }

        private void OnProfileDoubleClick(object sender, MouseButtonEventArgs e)
        {
            if (ProfilesListBox.SelectedItem is ChromeProfile profile)
            {
                SelectedProfile = profile;
                DialogResult = true;
                Close();
            }
        }

        private void OnAssignClick(object sender, RoutedEventArgs e)
        {
            if (ProfilesListBox.SelectedItem is ChromeProfile profile)
            {
                SelectedProfile = profile;
                DialogResult = true;
                Close();
            }
        }

        private void OnClearClick(object sender, RoutedEventArgs e)
        {
            ShouldClear = true;
            DialogResult = true;
            Close();
        }
    }
}

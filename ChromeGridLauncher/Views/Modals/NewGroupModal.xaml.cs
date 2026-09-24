using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class NewGroupModal : Window
    {
        public ProfileGroup? CreatedGroup { get; private set; }
        public string CreatedGroupName { get; private set; } = string.Empty;
        public string SelectedColor { get; private set; } = "#3B82F6";
        public List<string> SelectedProfileKeys { get; private set; } = new List<string>();

        public NewGroupModal(IEnumerable<ChromeProfile> availableProfiles)
        {
            InitializeComponent();
            ProfilesListBox.ItemsSource = availableProfiles.ToList();
            InitColorSwatches();
        }

        private void InitColorSwatches()
        {
            foreach (var colorHex in ProfileGroup.PaletteColors)
            {
                var border = new Border
                {
                    Width = 28,
                    Height = 28,
                    CornerRadius = new CornerRadius(14),
                    Background = (Brush)new BrushConverter().ConvertFromString(colorHex)!,
                    Margin = new Thickness(0, 0, 10, 0),
                    Cursor = System.Windows.Input.Cursors.Hand,
                    Tag = colorHex
                };

                border.MouseLeftButtonDown += (s, e) =>
                {
                    SelectedColor = colorHex;
                    HighlightSwatch(border);
                };

                ColorSwatchesPanel.Children.Add(border);
            }

            if (ColorSwatchesPanel.Children.Count > 0)
            {
                HighlightSwatch((Border)ColorSwatchesPanel.Children[0]);
            }
        }

        private void HighlightSwatch(Border target)
        {
            foreach (UIElement child in ColorSwatchesPanel.Children)
            {
                if (child is Border b)
                {
                    b.BorderThickness = new Thickness(0);
                }
            }
            target.BorderBrush = Brushes.White;
            target.BorderThickness = new Thickness(2);
        }

        private void OnSaveClick(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(TxtGroupName.Text))
            {
                MessageBox.Show("Please enter a group name.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            CreatedGroupName = TxtGroupName.Text.Trim();
            SelectedProfileKeys.Clear();
            foreach (var item in ProfilesListBox.SelectedItems)
            {
                if (item is ChromeProfile profile)
                {
                    SelectedProfileKeys.Add(profile.Key);
                }
            }

            CreatedGroup = new ProfileGroup
            {
                Id = Guid.NewGuid().ToString("N")[..8],
                Name = CreatedGroupName,
                Color = SelectedColor,
                Icon = "📁",
                IsBuiltin = false,
                ProfileKeys = SelectedProfileKeys
            };

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

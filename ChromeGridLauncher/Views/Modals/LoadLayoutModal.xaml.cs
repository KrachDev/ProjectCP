using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using ChromeGridLauncher.Models;
using ChromeGridLauncher.Services;

namespace ChromeGridLauncher.Views.Modals
{
    public partial class LoadLayoutModal : Window
    {
        private readonly LayoutStorageService _storageService;
        private List<LayoutPreset> _presets;
        public LayoutPreset? SelectedPreset { get; private set; }

        public LoadLayoutModal(LayoutStorageService storageService)
        {
            InitializeComponent();
            _storageService = storageService;
            _presets = _storageService.ListSavedLayouts();
            LayoutListBox.ItemsSource = _presets;
        }

        private void OnLoadItemClick(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is LayoutPreset preset)
            {
                SelectedPreset = preset;
                DialogResult = true;
                Close();
            }
        }

        private void OnDeleteItemClick(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is LayoutPreset preset)
            {
                if (MessageBox.Show($"Are you sure you want to delete preset '{preset.Name}'?", "Confirm Delete", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                {
                    if (!string.IsNullOrWhiteSpace(preset.FilePath))
                    {
                        _storageService.DeleteLayoutFile(preset.FilePath);
                    }
                    _presets.Remove(preset);
                    LayoutListBox.ItemsSource = null;
                    LayoutListBox.ItemsSource = _presets;
                }
            }
        }

        private void OnImportClick(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "JSON Layout Files (*.json)|*.json|All Files (*.*)|*.*",
                Title = "Import Grid Layout Preset"
            };

            if (dlg.ShowDialog() == true)
            {
                try
                {
                    string json = File.ReadAllText(dlg.FileName);
                    var preset = JsonSerializer.Deserialize<LayoutPreset>(json);
                    if (preset != null)
                    {
                        _storageService.SaveLayoutFile(preset.Name, preset);
                        _presets = _storageService.ListSavedLayouts();
                        LayoutListBox.ItemsSource = null;
                        LayoutListBox.ItemsSource = _presets;
                    }
                }
                catch (System.Exception ex)
                {
                    MessageBox.Show($"Failed to import layout: {ex.Message}", "Import Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        private void OnExportClick(object sender, RoutedEventArgs e)
        {
            if (LayoutListBox.SelectedItem is LayoutPreset selected)
            {
                var dlg = new Microsoft.Win32.SaveFileDialog
                {
                    Filter = "JSON Layout Files (*.json)|*.json",
                    FileName = $"{selected.Name.Replace(" ", "_")}.json",
                    Title = "Export Grid Layout Preset"
                };

                if (dlg.ShowDialog() == true)
                {
                    try
                    {
                        string json = JsonSerializer.Serialize(selected, new JsonSerializerOptions { WriteIndented = true });
                        File.WriteAllText(dlg.FileName, json);
                        MessageBox.Show("Preset exported successfully!", "Export Success", MessageBoxButton.OK, MessageBoxImage.Information);
                    }
                    catch (System.Exception ex)
                    {
                        MessageBox.Show($"Failed to export layout: {ex.Message}", "Export Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    }
                }
            }
            else
            {
                MessageBox.Show("Please select a preset to export.", "Select Preset", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void OnCloseClick(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}

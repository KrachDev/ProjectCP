using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class LayoutStorageService
    {
        private static readonly string AppDataDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "ChromeGridLauncher"
        );

        private static readonly string LayoutsDir = Path.Combine(AppDataDir, "layouts");
        private static readonly string SettingsFile = Path.Combine(AppDataDir, "settings.json");
        private static readonly string GroupsFile = Path.Combine(AppDataDir, "groups.json");
        private static readonly string LastLayoutFile = Path.Combine(AppDataDir, "last_layout.json");

        private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };

        public LayoutStorageService()
        {
            if (!Directory.Exists(AppDataDir)) Directory.CreateDirectory(AppDataDir);
            if (!Directory.Exists(LayoutsDir)) Directory.CreateDirectory(LayoutsDir);
        }

        public AppSettings LoadSettings()
        {
            if (File.Exists(SettingsFile))
            {
                try
                {
                    string json = File.ReadAllText(SettingsFile);
                    var settings = JsonSerializer.Deserialize<AppSettings>(json);
                    if (settings != null) return settings;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[LayoutStorageService] Error reading settings: {ex.Message}");
                }
            }
            return new AppSettings();
        }

        public void SaveSettings(AppSettings settings)
        {
            try
            {
                string json = JsonSerializer.Serialize(settings, _jsonOptions);
                File.WriteAllText(SettingsFile, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LayoutStorageService] Error saving settings: {ex.Message}");
            }
        }

        public List<ProfileGroup> LoadCustomGroups()
        {
            if (File.Exists(GroupsFile))
            {
                try
                {
                    string json = File.ReadAllText(GroupsFile);
                    using var doc = JsonDocument.Parse(json);
                    if (doc.RootElement.TryGetProperty("custom_groups", out var groupsElem))
                    {
                        var groups = JsonSerializer.Deserialize<List<ProfileGroup>>(groupsElem.GetRawText());
                        if (groups != null) return groups;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[LayoutStorageService] Error reading groups: {ex.Message}");
                }
            }
            return new List<ProfileGroup>();
        }

        public Dictionary<string, string> LoadOverrides()
        {
            if (File.Exists(GroupsFile))
            {
                try
                {
                    string json = File.ReadAllText(GroupsFile);
                    using var doc = JsonDocument.Parse(json);
                    if (doc.RootElement.TryGetProperty("overrides", out var ovElem))
                    {
                        var dict = JsonSerializer.Deserialize<Dictionary<string, string>>(ovElem.GetRawText());
                        if (dict != null) return dict;
                    }
                }
                catch { }
            }
            return new Dictionary<string, string>();
        }

        public void SaveGroupsData(List<ProfileGroup> customGroups, Dictionary<string, string>? overrides = null)
        {
            try
            {
                overrides ??= LoadOverrides();
                var data = new
                {
                    custom_groups = customGroups,
                    overrides = overrides
                };
                string json = JsonSerializer.Serialize(data, _jsonOptions);
                File.WriteAllText(GroupsFile, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LayoutStorageService] Error saving groups: {ex.Message}");
            }
        }

        public string SaveLayoutFile(string name, LayoutPreset layout)
        {
            string safeName = Regex.Replace(name, @"[\\/*?:""<>|]", "").Trim();
            if (string.IsNullOrWhiteSpace(safeName)) safeName = "Unnamed";

            string filePath = Path.Combine(LayoutsDir, $"{safeName}.json");
            layout.Name = safeName;
            layout.UpdatedAt = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            try
            {
                string json = JsonSerializer.Serialize(layout, _jsonOptions);
                File.WriteAllText(filePath, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LayoutStorageService] Error saving layout file: {ex.Message}");
            }

            return filePath;
        }

        public LayoutPreset? LoadLayoutFile(string filePathOrName)
        {
            string path = Path.IsPathRooted(filePathOrName)
                ? filePathOrName
                : Path.Combine(LayoutsDir, $"{filePathOrName}.json");

            if (File.Exists(path))
            {
                try
                {
                    string json = File.ReadAllText(path);
                    var preset = JsonSerializer.Deserialize<LayoutPreset>(json);
                    if (preset != null)
                    {
                        preset.FilePath = path;
                        preset.FileName = Path.GetFileName(path);
                        return preset;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[LayoutStorageService] Error loading layout file: {ex.Message}");
                }
            }
            return null;
        }

        public List<LayoutPreset> ListSavedLayouts()
        {
            var presets = new List<LayoutPreset>();
            if (Directory.Exists(LayoutsDir))
            {
                foreach (var file in Directory.GetFiles(LayoutsDir, "*.json"))
                {
                    var preset = LoadLayoutFile(file);
                    if (preset != null)
                    {
                        presets.Add(preset);
                    }
                }
            }
            return presets;
        }

        public void DeleteLayoutFile(string filePath)
        {
            try
            {
                if (File.Exists(filePath)) File.Delete(filePath);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LayoutStorageService] Error deleting layout file: {ex.Message}");
            }
        }

        public void SaveLastLayout(LayoutPreset layout)
        {
            try
            {
                string json = JsonSerializer.Serialize(layout, _jsonOptions);
                File.WriteAllText(LastLayoutFile, json);
            }
            catch { }
        }

        public LayoutPreset? LoadLastLayout()
        {
            if (File.Exists(LastLayoutFile))
            {
                try
                {
                    string json = File.ReadAllText(LastLayoutFile);
                    return JsonSerializer.Deserialize<LayoutPreset>(json);
                }
                catch { }
            }
            return null;
        }
    }
}

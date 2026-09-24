using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class ThunderConfigService
    {
        private static readonly string AppDataDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "ChromeGridLauncher"
        );

        private static readonly string PresetsFile = Path.Combine(AppDataDir, "thunder_presets.json");
        private static readonly string CellConfigsFile = Path.Combine(AppDataDir, "thunder_cell_configs.json");

        private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };

        public ThunderConfigService()
        {
            if (!Directory.Exists(AppDataDir))
            {
                Directory.CreateDirectory(AppDataDir);
            }
        }

        public Dictionary<string, ThunderConfig> LoadPresets()
        {
            var presets = new Dictionary<string, ThunderConfig>();
            if (File.Exists(PresetsFile))
            {
                try
                {
                    string json = File.ReadAllText(PresetsFile);
                    var loaded = JsonSerializer.Deserialize<Dictionary<string, ThunderConfig>>(json);
                    if (loaded != null)
                    {
                        presets = loaded;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[ThunderConfigService] Error loading presets: {ex.Message}");
                }
            }

            if (!presets.ContainsKey("Default"))
            {
                presets["Default"] = new ThunderConfig
                {
                    Region = "Spain",
                    VtData = new ThunderVtData
                    {
                        City = "Casablanca",
                        Category = "Normal",
                        Type = "National Visa",
                        Members = 1
                    }
                };
            }

            return presets;
        }

        public void SavePresets(Dictionary<string, ThunderConfig> presets)
        {
            try
            {
                string json = JsonSerializer.Serialize(presets, _jsonOptions);
                File.WriteAllText(PresetsFile, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ThunderConfigService] Error saving presets: {ex.Message}");
            }
        }

        public Dictionary<string, ThunderConfig> LoadCellConfigs()
        {
            if (File.Exists(CellConfigsFile))
            {
                try
                {
                    string json = File.ReadAllText(CellConfigsFile);
                    var loaded = JsonSerializer.Deserialize<Dictionary<string, ThunderConfig>>(json);
                    if (loaded != null)
                    {
                        return loaded;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[ThunderConfigService] Error loading cell configs: {ex.Message}");
                }
            }
            return new Dictionary<string, ThunderConfig>();
        }

        public void SaveCellConfigs(Dictionary<string, ThunderConfig> configs)
        {
            try
            {
                string json = JsonSerializer.Serialize(configs, _jsonOptions);
                File.WriteAllText(CellConfigsFile, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ThunderConfigService] Error saving cell configs: {ex.Message}");
            }
        }
    }
}

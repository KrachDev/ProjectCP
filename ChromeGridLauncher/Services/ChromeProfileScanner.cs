using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32;
using ChromeGridLauncher.Models;

namespace ChromeGridLauncher.Services
{
    public class ChromeProfileScanner
    {
        private static readonly string[] PaletteColors = new[]
        {
            "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#F59E0B",
            "#06B6D4", "#6366F1", "#14B8A6", "#F97316", "#84CC16"
        };

        public static string GetDefaultUserDataPath()
        {
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(localApp, "Google", "Chrome", "User Data");
        }

        public static string FindChromeExecutable()
        {
            // 1. Program Files
            string[] candidates = new[]
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Google", "Chrome", "Application", "chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Google", "Chrome", "Application", "chrome.exe")
            };

            foreach (var path in candidates)
            {
                if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
                    return path;
            }

            // 2. Registry lookup
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe");
                if (key?.GetValue("") is string regPath && File.Exists(regPath))
                    return regPath;
            }
            catch { }

            // 3. PATH search
            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string p in pathEnv.Split(';', StringSplitOptions.RemoveEmptyEntries))
            {
                try
                {
                    string cand = Path.Combine(p.Trim(), "chrome.exe");
                    if (File.Exists(cand)) return cand;
                }
                catch { }
            }

            return @"C:\Program Files\Google\Chrome\Application\chrome.exe";
        }

        public List<ChromeProfile> ScanProfiles(string? customUserDataPath = null)
        {
            string userDataDir = !string.IsNullOrWhiteSpace(customUserDataPath) && Directory.Exists(customUserDataPath)
                ? customUserDataPath
                : GetDefaultUserDataPath();

            string localStatePath = Path.Combine(userDataDir, "Local State");
            var profiles = new List<ChromeProfile>();

            if (!File.Exists(localStatePath))
                return profiles;

            try
            {
                string jsonText = File.ReadAllText(localStatePath);
                using var doc = JsonDocument.Parse(jsonText);

                if (!doc.RootElement.TryGetProperty("profile", out var profileElem) ||
                    !profileElem.TryGetProperty("info_cache", out var infoCacheElem))
                {
                    return profiles;
                }

                var profileDict = new Dictionary<string, JsonElement>();
                foreach (var prop in infoCacheElem.EnumerateObject())
                {
                    profileDict[prop.Name] = prop.Value;
                }

                // Natural sort: Default first, then Profile 1, Profile 2, etc.
                var sortedKeys = profileDict.Keys.OrderBy(k => k, new NaturalSortComparer()).ToList();

                foreach (var key in sortedKeys)
                {
                    var info = profileDict[key];

                    string name = info.TryGetProperty("name", out var nameProp) ? nameProp.GetString() ?? "" : "";
                    string gaiaName = info.TryGetProperty("gaia_name", out var gaiaProp) ? gaiaProp.GetString() ?? "" : "";
                    string email = info.TryGetProperty("user_name", out var userProp) ? userProp.GetString() ?? "" : "";
                    string displayName = !string.IsNullOrWhiteSpace(name) ? name : (!string.IsNullOrWhiteSpace(gaiaName) ? gaiaName : key);

                    // Compute initials
                    string initials = ComputeInitials(displayName);

                    // Avatar picture detection
                    string avatarPath = "";
                    if (info.TryGetProperty("gaia_picture_file_name", out var picProp))
                    {
                        string? picFile = picProp.GetString();
                        if (!string.IsNullOrWhiteSpace(picFile))
                        {
                            string cand = Path.Combine(userDataDir, key, picFile);
                            if (File.Exists(cand)) avatarPath = cand;
                        }
                    }
                    if (string.IsNullOrWhiteSpace(avatarPath))
                    {
                        string cand2 = Path.Combine(userDataDir, key, "Google Profile Picture.png");
                        if (File.Exists(cand2)) avatarPath = cand2;
                    }

                    int colorIdx = Math.Abs((key + displayName).GetHashCode()) % PaletteColors.Length;
                    string color = PaletteColors[colorIdx];

                    profiles.Add(new ChromeProfile
                    {
                        Key = key,
                        Name = displayName,
                        GaiaName = gaiaName,
                        Email = email,
                        AvatarFile = avatarPath,
                        Color = color,
                        Initials = initials
                    });
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ChromeProfileScanner] Error parsing Local State: {ex.Message}");
            }

            return profiles;
        }

        private static string ComputeInitials(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return "?";
            string[] words = text.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (words.Length >= 2 && words[0].Length > 0 && words[1].Length > 0)
                return (words[0][0].ToString() + words[1][0].ToString()).ToUpperInvariant();
            if (text.Length >= 2)
                return text.Substring(0, 2).ToUpperInvariant();
            return text.Substring(0, 1).ToUpperInvariant();
        }

        public static bool IsPrtProfile(string profileKey, string profileName)
        {
            string combined = $"{profileName} {profileKey}".ToUpperInvariant();
            return Regex.IsMatch(combined, @"\bPRT\d*\b|PRT");
        }

        public static bool IsNumberProfile(string profileKey, string profileName)
        {
            if (IsPrtProfile(profileKey, profileName)) return false;
            string clean = (profileName ?? "").Trim();
            if (int.TryParse(clean, out _)) return true;
            if (Regex.IsMatch(profileKey, @"^Profile\s*\d+$", RegexOptions.IgnoreCase) &&
                (string.IsNullOrWhiteSpace(clean) || clean.StartsWith("Profile", StringComparison.OrdinalIgnoreCase)))
            {
                return true;
            }
            return false;
        }

        public static void ApplyGroupsToProfiles(
            List<ChromeProfile> profiles,
            List<ProfileGroup> customGroups,
            Dictionary<string, string>? overrides = null)
        {
            var customMap = new Dictionary<string, (string id, string name, string color)>();
            foreach (var cg in customGroups)
            {
                foreach (string pkey in cg.ProfileKeys)
                {
                    customMap[pkey] = (cg.Id, cg.Name, cg.Color);
                }
            }

            overrides ??= new Dictionary<string, string>();

            foreach (var p in profiles)
            {
                if (customMap.TryGetValue(p.Key, out var val))
                {
                    p.GroupId = val.id;
                    p.GroupName = val.name;
                    p.GroupColor = val.color;
                }
                else if (overrides.TryGetValue(p.Key, out string? ov))
                {
                    if (ov == "prt")
                    {
                        p.GroupId = "prt";
                        p.GroupName = "PRT";
                        p.GroupColor = "#8B5CF6";
                    }
                    else if (ov == "numbers")
                    {
                        p.GroupId = "numbers";
                        p.GroupName = "Numbers";
                        p.GroupColor = "#10B981";
                    }
                    else
                    {
                        p.GroupId = "other";
                        p.GroupName = "Other";
                        p.GroupColor = "#64748B";
                    }
                }
                else if (IsPrtProfile(p.Key, p.DisplayName))
                {
                    p.GroupId = "prt";
                    p.GroupName = "PRT";
                    p.GroupColor = "#8B5CF6";
                }
                else if (IsNumberProfile(p.Key, p.DisplayName))
                {
                    p.GroupId = "numbers";
                    p.GroupName = "Numbers";
                    p.GroupColor = "#10B981";
                }
                else
                {
                    p.GroupId = "other";
                    p.GroupName = "Other";
                    p.GroupColor = "#64748B";
                }
            }
        }
    }

    public class NaturalSortComparer : IComparer<string>
    {
        public int Compare(string? x, string? y)
        {
            if (x == null && y == null) return 0;
            if (x == null) return -1;
            if (y == null) return 1;

            if (x.Equals("Default", StringComparison.OrdinalIgnoreCase)) return -1;
            if (y.Equals("Default", StringComparison.OrdinalIgnoreCase)) return 1;

            var matchX = Regex.Match(x, @"^Profile\s*(\d+)$", RegexOptions.IgnoreCase);
            var matchY = Regex.Match(y, @"^Profile\s*(\d+)$", RegexOptions.IgnoreCase);

            if (matchX.Success && matchY.Success)
            {
                int numX = int.Parse(matchX.Groups[1].Value);
                int numY = int.Parse(matchY.Groups[1].Value);
                return numX.CompareTo(numY);
            }
            if (matchX.Success) return -1;
            if (matchY.Success) return 1;

            return AlphanumComparator(x, y);
        }

        private static int AlphanumComparator(string a, string b)
        {
            var partsA = Regex.Split(a, @"(\d+)");
            var partsB = Regex.Split(b, @"(\d+)");

            for (int i = 0; i < Math.Min(partsA.Length, partsB.Length); i++)
            {
                if (int.TryParse(partsA[i], out int intA) && int.TryParse(partsB[i], out int intB))
                {
                    int cmp = intA.CompareTo(intB);
                    if (cmp != 0) return cmp;
                }
                else
                {
                    int cmp = string.Compare(partsA[i], partsB[i], StringComparison.OrdinalIgnoreCase);
                    if (cmp != 0) return cmp;
                }
            }
            return partsA.Length.CompareTo(partsB.Length);
        }
    }
}

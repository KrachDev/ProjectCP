using System;

namespace ChromeGridLauncher.Models
{
    public class ChromeProfile
    {
        public string Key { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string GaiaName { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string AvatarFile { get; set; } = string.Empty;
        public string Color { get; set; } = "#3B82F6";
        public string Initials { get; set; } = "?";
        public string GroupId { get; set; } = string.Empty;
        public string GroupName { get; set; } = string.Empty;
        public string GroupColor { get; set; } = string.Empty;
        public bool IsProtected { get; set; } = false;
        public bool IsActive { get; set; } = false;

        public string DisplayName => !string.IsNullOrWhiteSpace(Name) ? Name : Key;

        public string Subtitle
        {
            get
            {
                if (!string.IsNullOrWhiteSpace(Email))
                    return $"{Key} • {Email}";
                if (!string.IsNullOrWhiteSpace(GaiaName) && GaiaName != Name)
                    return $"{Key} • {GaiaName}";
                return Key;
            }
        }
    }
}

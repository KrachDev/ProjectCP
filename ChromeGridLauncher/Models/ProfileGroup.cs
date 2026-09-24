using System.Collections.Generic;

namespace ChromeGridLauncher.Models
{
    public class ProfileGroup
    {
        public static readonly string[] PaletteColors = new[]
        {
            "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316"
        };

        public string Id { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Color { get; set; } = "#8B5CF6";
        public string Icon { get; set; } = "📁";
        public bool IsBuiltin { get; set; } = false;
        public List<string> ProfileKeys { get; set; } = new();
    }
}

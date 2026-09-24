using System.Collections.Generic;

namespace ChromeGridLauncher.Models
{
    public class ThunderRegionConfig
    {
        public string Title { get; set; } = string.Empty;
        public string Tag { get; set; } = string.Empty;
        public List<string> VisaTypes { get; set; } = new();
        public List<string> Centers { get; set; } = new();
        public List<string> Categories { get; set; } = new();
        public List<string> Members { get; set; } = new();
    }

    public class ThunderVtData
    {
        public string City { get; set; } = "Casablanca";
        public string Category { get; set; } = "Normal";
        public string Type { get; set; } = "National Visa";
        public int Members { get; set; } = 1;
    }

    public class ThunderConfig
    {
        public string Region { get; set; } = "Spain";
        public ThunderVtData VtData { get; set; } = new();
    }

    public class ThunderCityColor
    {
        public string PillBg { get; set; } = "#0C4A6E";
        public string PillBorder { get; set; } = "#0284C7";
        public string PillText { get; set; } = "#E0F2FE";
    }

    public static class ThunderConstants
    {
        public static readonly Dictionary<string, ThunderCityColor> CityColors = new()
        {
            ["Casablanca"] = new ThunderCityColor { PillBg = "#0C4A6E", PillBorder = "#0284C7", PillText = "#E0F2FE" },
            ["Rabat"] = new ThunderCityColor { PillBg = "#064E3B", PillBorder = "#059669", PillText = "#D1FAE5" },
            ["Tangier"] = new ThunderCityColor { PillBg = "#78350F", PillBorder = "#D97706", PillText = "#FEF3C7" },
            ["Nador"] = new ThunderCityColor { PillBg = "#4C1D95", PillBorder = "#7C3AED", PillText = "#EDE9FE" },
            ["Tetouan"] = new ThunderCityColor { PillBg = "#134E4A", PillBorder = "#0D9488", PillText = "#CCFBF1" },
            ["Agadir"] = new ThunderCityColor { PillBg = "#831843", PillBorder = "#DB2777", PillText = "#FCE7F3" }
        };

        public static readonly ThunderCityColor DefaultColor = new()
        {
            PillBg = "#1E293B",
            PillBorder = "#475569",
            PillText = "#94A3B8"
        };

        public static readonly Dictionary<string, ThunderRegionConfig> Regions = new()
        {
            ["Spain"] = new ThunderRegionConfig
            {
                Title = "Spain (BLS Spain v1.8.8)",
                Tag = "🇪🇸 Spain",
                VisaTypes = new List<string>
                {
                    "Schengen Visa", "National Visa", "Student Visa", "Work Visa",
                    "Casa 1", "Casa 2", "Family Reunification Visa", "Schengen Visa Prior 2023",
                    "Students - Language/selectivity", "Students - Non-tertiary studies",
                    "Students - Graduate studies", "Student - Others"
                },
                Centers = new List<string> { "Casablanca", "Nador", "Tetouan", "Tangier", "Rabat", "Agadir" },
                Categories = new List<string> { "Normal", "Premium", "Prime Time" },
                Members = new List<string> { "1", "2", "3", "4" }
            },
            ["Portugal"] = new ThunderRegionConfig
            {
                Title = "Portugal (BLS Portugal v1.6.5)",
                Tag = "🇵🇹 Portugal",
                VisaTypes = new List<string>
                {
                    "Short Stay Visa",
                    "Any other category of Long-Stay visa",
                    "Highly Qualified Activity"
                },
                Centers = new List<string> { "Casablanca", "Rabat" },
                Categories = new List<string> { "Normal", "Premium", "Prime Time" },
                Members = new List<string> { "1", "2", "3", "4" }
            }
        };
    }
}

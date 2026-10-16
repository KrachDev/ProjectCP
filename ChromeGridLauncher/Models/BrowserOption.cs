namespace ChromeGridLauncher.Models
{
    public class BrowserOption
    {
        public string Key { get; set; } = "Chrome";
        public string DisplayName { get; set; } = "🌐 Chrome";
        public string ShortName { get; set; } = "Chrome";
        public string ExeFileName { get; set; } = "chrome.exe";
        public string ProcessName { get; set; } = "chrome";

        public override string ToString() => DisplayName;
    }
}

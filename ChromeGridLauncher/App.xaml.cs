using System;
using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace ChromeGridLauncher
{
    public partial class App : Application
    {
        public App()
        {
            AppDomain.CurrentDomain.UnhandledException += (s, e) =>
            {
                string msg = e.ExceptionObject?.ToString() ?? "Unknown domain crash";
                try { File.WriteAllText("crash_appdomain.txt", msg); } catch { }
                MessageBox.Show($"Application encountered a fatal error:\n\n{msg}", "Chrome Grid Launcher Error", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            DispatcherUnhandledException += (s, e) =>
            {
                string msg = e.Exception?.ToString() ?? "Unknown dispatcher crash";
                try { File.WriteAllText("crash_dispatcher.txt", msg); } catch { }
                MessageBox.Show($"Application UI encountered an error:\n\n{e.Exception?.Message}\n\nDetails saved to crash_dispatcher.txt", "Chrome Grid Launcher Error", MessageBoxButton.OK, MessageBoxImage.Error);
                // Do not crash the entire process if it's a recoverable UI exception
                e.Handled = true;
            };
        }

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);
            try
            {
                Services.ExtensionDeploymentService.EnsureExtensionDeployed();
                Services.ExtensionDeploymentService.EnsureUserscriptDeployed();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[App Startup] Error self-extracting extension: {ex.Message}");
            }
        }
    }
}

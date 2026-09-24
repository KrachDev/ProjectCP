using System;
using System.IO;
using System.Media;

namespace ChromeGridLauncher.Services
{
    public class AudioAlertService
    {
        private static DateTime _lastSuccessBeep = DateTime.MinValue;
        private static readonly object _beepLock = new();

        public static void PlayNotificationBeep()
        {
            try
            {
                SystemSounds.Asterisk.Play();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[AudioAlert] Error playing sound: {ex.Message}");
            }
        }

        public static void PlaySuccessBeep()
        {
            lock (_beepLock)
            {
                if ((DateTime.UtcNow - _lastSuccessBeep).TotalMilliseconds < 1500)
                {
                    return; // Cooldown: prevent audio driver saturation during rapid concurrent acks
                }
                _lastSuccessBeep = DateTime.UtcNow;
            }

            try
            {
                SystemSounds.Exclamation.Play();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[AudioAlert] Error playing sound: {ex.Message}");
            }
        }
    }
}

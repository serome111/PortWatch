"""
System Notifications for PortWatch Interactive Alert Mode
Sends native OS notifications for new connection alerts
"""
import subprocess
import logging
import platform
import sys
import os
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)


class Notifier:
    """Send native system notifications"""
    
    def __init__(self):
        self.os_type = platform.system()
        self.terminal_notifier_path = self._find_terminal_notifier()
        LOG.info(f"Notifier initialized for {self.os_type}")
        if self.terminal_notifier_path:
            LOG.info(f"terminal-notifier found at: {self.terminal_notifier_path}")
        else:
            LOG.warning("terminal-notifier not found, will use osascript fallback")
    
    def _find_terminal_notifier(self) -> Optional[str]:
        """Find terminal-notifier binary (bundled or system)"""
        if self.os_type != "Darwin":
            return None
        
        # 1. Check if bundled with PyInstaller (in same dir as executable)
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            if hasattr(sys, '_MEIPASS'):
                # One-file mode
                bundled_path = Path(sys._MEIPASS) / 'terminal-notifier'
            else:
                # One-dir mode / app bundle
                bundled_path = Path(sys.executable).parent / 'terminal-notifier'
            
            if bundled_path.exists() and bundled_path.is_file():
                return str(bundled_path)
        
        # 2. Check system PATH (Homebrew, etc.)
        import shutil
        system_path = shutil.which('terminal-notifier')
        if system_path:
            return system_path
        
        return None
    
    def send_alert(
        self,
        process: str,
        destination: str,
        port: Optional[int] = None,
        level: str = "medium",
        country: Optional[str] = None
    ) -> bool:
        """
        Send a connection alert notification
        
        Args:
            process: Process name (e.g., "Google Chrome")
            destination: IP or domain
            port: Destination port
            level: Risk level ("low", "medium", "high")
            country: Country code (e.g., "US")
        
        Returns:
            True if notification was sent successfully
        """
        # Build notification message
        dest_str = f"{destination}:{port}" if port else destination
        if country:
            dest_str += f" ({country})"
        
        title = "PortWatch - Nueva Conexión"
        
        # Normalize level string (handles "medium", "MEDIUM", "RISK.MEDIO", etc.)
        level_normalized = level.lower().replace("risk.", "")
        # Map common Spanish translations back to base keys
        level_spanish_to_base = {
            "bajo": "low",
            "medio": "medium",
            "alta": "high",
            "alto": "high"
        }
        level_key = level_spanish_to_base.get(level_normalized, level_normalized)
        
        # Map level to subtitle (accept English keys)
        level_map = {
            "low": "🟢 Riesgo Bajo",
            "medium": "🟡 Riesgo Medio",
            "high": "🔴 Riesgo Alto",
            # Spanish keys for backward compatibility
            "bajo": "🟢 Riesgo Bajo",
            "medio": "🟡 Riesgo Medio",
            "alto": "🔴 Riesgo Alto"
        }
        subtitle = level_map.get(level_key, "⚪ Desconocido")
        
        message = f"{process} quiere conectarse a {dest_str}"
        
        if self.os_type == "Darwin":  # macOS
            # Use dialog for medium/high risk or if explicitly requested
            # This is more intrusive but ensures visibility (User preference)
            level_lower = level.lower()
            if level_lower in ["medio", "medium", "alto", "high"]:
                return self._send_macos_dialog(title, subtitle, message, level_lower)
            else:
                return self._send_macos_banner(title, subtitle, message)
        elif self.os_type == "Linux":
            return self._send_linux(title, message, level)
        else:
            LOG.warning(f"Notifications not supported on {self.os_type}")
            return False
    
    def _send_macos_banner(self, title: str, subtitle: str, message: str) -> bool:
        """Send standard notification banner via terminal-notifier (macOS permissions-friendly)"""
        # Try terminal-notifier first (best for permissions)
        if self.terminal_notifier_path:
            try:
                subprocess.run(
                    [
                        self.terminal_notifier_path,
                        "-title", title,
                        "-subtitle", subtitle,
                        "-message", message,
                        "-sound", "Ping",
                        "-group", "com.portwatch.alert"
                    ],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
                LOG.info(f"Sent macOS banner via terminal-notifier: {title}")
                return True
            except Exception as e:
                LOG.error(f"Error sending macOS banner via terminal-notifier: {e}")
                # Fallback to osascript
                return self._send_macos_banner_osascript(title, subtitle, message)
        else:
            # No terminal-notifier available, use osascript
            LOG.debug("terminal-notifier not available, using osascript")
            return self._send_macos_banner_osascript(title, subtitle, message)
    
    def _send_macos_banner_osascript(self, title: str, subtitle: str, message: str) -> bool:
        """Fallback: Send notification via osascript (requires Python to have notification permissions)"""
        try:
            script = f'''
            display notification "{message}" ¬
                with title "{title}" ¬
                subtitle "{subtitle}" ¬
                sound name "Ping"
            '''
            subprocess.run(['osascript', '-e', script], check=True, timeout=5)
            LOG.info(f"Sent macOS banner via osascript: {title}")
            return True
        except Exception as e:
            LOG.error(f"Error sending macOS banner via osascript: {e}")
            return False

    def _send_macos_dialog(self, title: str, subtitle: str, message: str, level: str) -> bool:
        """Send intrusive dialog (modal) via osascript"""
        try:
            level_lower = level.lower()
            icon = "stop" if level_lower in ["alto", "high"] else "caution"
            script = f'''
            display dialog "{message}" ¬
                with title "{title} - {subtitle}" ¬
                buttons {{"OK"}} ¬
                default button "OK" ¬
                with icon {icon}
            '''
            # Don't wait for response (run in background)
            subprocess.Popen(['osascript', '-e', script])
            LOG.info(f"Sent macOS dialog: {title}")
            return True
        except Exception as e:
            LOG.error(f"Error sending macOS dialog: {e}")
            return False

    def _send_linux(self, title: str, message: str, level: str) -> bool:
        """Send Linux notification via notify-send"""
        try:
            level_lower = level.lower()
            urgency = "critical" if level_lower in ["alto", "high"] else "normal"
            subprocess.run(
                ['notify-send', '-u', urgency, title, message],
                check=True,
                timeout=5
            )
            LOG.info(f"Sent Linux notification: {title}")
            return True
        except Exception as e:
            LOG.error(f"Error sending Linux notification: {e}")
            return False
            
    def send_rule_created(self, process: str, destination: str, action: str) -> bool:
        """Notify when a rule is auto-created"""
        title = "PortWatch - Regla Creada"
        message = f"Regla '{action}' creada para {process} -> {destination}"
        
        if self.os_type == "Darwin":
            return self._send_macos_banner(title, "Regla Permanente", message)
        elif self.os_type == "Linux":
            return self._send_linux(title, message, "low")
        return False


# Global notifier instance
_notifier_instance: Optional[Notifier] = None

def get_notifier() -> Notifier:
    """Get or create global notifier instance"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = Notifier()
    return _notifier_instance


if __name__ == "__main__":
    # Test notifications
    logging.basicConfig(level=logging.INFO)
    
    print("Testing notification system...")
    
    notifier = get_notifier()
    
    # Test low risk alert
    notifier.send_alert(
        process="Safari",
        destination="apple.com",
        port=443,
        level="bajo",
        country="US"
    )
    
    print("Test notifications sent!")

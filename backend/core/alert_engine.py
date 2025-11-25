"""
Alert Engine for PortWatch Interactive Alert Mode
Detects new connections and triggers alerts based on rules
"""
import hashlib
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.rules_manager import rules_manager
from backend.utils.notifier import get_notifier

# Initialize notifier
notifier = get_notifier()

LOG = logging.getLogger(__name__)


class AlertEngine:
    """Manages connection alerts and rule evaluation"""
    
    def __init__(self):
        # In-memory cache of seen connections (process, dest, port)
        self.seen_connections: Set[str] = set()
        
        # Pending alerts awaiting user decision
        self.pending_alerts: Dict[str, Dict[str, Any]] = {}
        
        # Rules are now managed by rules_manager, no local cache needed here
        # self.rules = {}
        
        # Settings
        self.settings = {
            "enabled": False,  # Disabled by default, user must opt-in via Settings
            "alert_level": "high",  # all | medium | high
            "ignored_apps": [],  # List of process names to ignore
            "auto_allow_signed": False,  # Alert on all apps initially (user can enable in Settings)
            "notification_cooldown": 60,  # Seconds between same alerts
        }
        
        # Last notification times (to avoid spam)
        self.last_notifications: Dict[str, datetime] = {}
        
        LOG.info("Alert Engine initialized")
    
    def _connection_key(self, conn: Dict[str, Any]) -> str:
        """Generate unique key for a connection"""
        proc = conn.get("proc") or conn.get("name", "unknown")
        dest = conn.get("raddr", "").split(":")[0] or "unknown"
        port = conn.get("dport", 0)
        return f"{proc}|{dest}|{port}"
    
    def _should_alert(self, conn: Dict[str, Any]) -> bool:
        """Determine if this connection should trigger an alert"""
        proc = conn.get("proc") or conn.get("name", "unknown")
        
        if not self.settings["enabled"]:
            LOG.debug(f"Alert engine disabled - skipping {proc}")
            return False
        
        # Check alert level threshold
        level = conn.get("level", "bajo")
        alert_level = self.settings["alert_level"]
        
        LOG.info(f"Evaluating {proc}: level={level}, threshold={alert_level}, auto_allow_signed={self.settings['auto_allow_signed']}")
        
        if alert_level == "high" and level != "alto":
            LOG.debug(f"Filtered: level {level} doesn't meet 'high' threshold")
            return False
        if alert_level == "medium" and level == "bajo":
            LOG.debug(f"Filtered: level {level} doesn't meet 'medium' threshold")
            return False
        
        # Check ignored apps
        proc = conn.get("proc") or conn.get("name", "")
        if proc in self.settings["ignored_apps"]:
            LOG.debug(f"Filtered: {proc} is in ignored_apps")
            return False
        
        # Auto-allow signed Apple apps if configured
        is_apple = conn.get("apple")
        auto_allow = self.settings["auto_allow_signed"]
        
        if auto_allow and is_apple:
            LOG.debug(f"Filtered: {proc} is Apple-signed and auto_allow_signed=True")
            return False
        
        LOG.debug(f"Alert allowed for {proc}")
        return True
    
    def _should_notify(self, conn_key: str) -> bool:
        """Check if we should send a notification (cooldown logic)"""
        last_time = self.last_notifications.get(conn_key)
        if not last_time:
            return True
        
        cooldown = timedelta(seconds=self.settings["notification_cooldown"])
        return datetime.utcnow() - last_time > cooldown
    
    def process_connection(self, conn: Dict[str, Any]) -> Optional[str]:
        """
        Process a connection and determine action
        
        Args:
            conn: Connection dict with keys: proc, raddr, dport, level, etc.
        
        Returns:
            Action to take: "allow", "deny", "ask", or None (no rule, first time)
        """
        proc = conn.get("proc") or conn.get("name", "unknown")
        dest = conn.get("raddr", "").split(":")[0] or "unknown"
        port = conn.get("dport")
        exe = conn.get("exe")
        
        LOG.debug(f"Processing connection: {proc} -> {dest}:{port}")
        
        # Check for existing rule
        rule = rules_manager.find_matching_rule(
            process=proc,
            destination=dest,
            port=port,
            exe_path=exe
        )
        
        if rule:
            action = rule["action"]
            scope = rule["scope"]
            
            LOG.debug(f"Found existing rule for {proc}: action={action}, scope={scope}")
            
            # If "once", disable the rule after use
            if scope == "once":
                rules_manager.disable_rule(rule["id"])
                LOG.info(f"Used once-rule {rule['id']}, disabled")
            
            return action
        
        # No rule found - always check for alert condition
        # We no longer implicitly allow "seen" connections.
        # Every connection without a rule must be evaluated.
        
        conn_key = self._connection_key(conn)
        
        # Update seen set just for tracking purposes (optional now, but good for stats)
        if conn_key not in self.seen_connections:
            self.seen_connections.add(conn_key)
            
        # Should we alert for this connection?
        should_alert = self._should_alert(conn)
        LOG.info(f"Connection detected: {proc} -> {dest}:{port}, level={conn.get('level')}, should_alert={should_alert}")
        
        if should_alert:
            # Create pending alert
            alert_id = hashlib.md5(conn_key.encode()).hexdigest()
            
            # Always update the pending alert with latest connection info
            self.pending_alerts[alert_id] = {
                "id": alert_id,
                "connection": conn,
                "created_at": datetime.utcnow().isoformat(),
                "status": "pending",
                "count": self.pending_alerts.get(alert_id, {}).get("count", 0) + 1
            }
            
            LOG.info(f"Pending alert {alert_id} for {proc} (count: {self.pending_alerts[alert_id]['count']})")
            
            # Send notification (with cooldown)
            if self._should_notify(conn_key):
                country = conn.get("country")
                level = conn.get("level", "medio")
                
                LOG.info(f"Sending notification for {proc} -> {dest}:{port}")
                
                notifier.send_alert(
                    process=proc,
                    destination=dest,
                    port=port,
                    level=level,
                    country=country
                )
                
                self.last_notifications[conn_key] = datetime.utcnow()
                LOG.info(f"Sent alert for {proc} -> {dest}:{port}")
            else:
                LOG.debug(f"Skipped notification for {conn_key} (cooldown)")
            
            return "ask"  # User needs to decide
        else:
            LOG.debug(f"Alert skipped for {proc} -> {dest}:{port} (settings filter)")
            # If filtered by settings (e.g. ignored app), we allow it
            return "allow"
    
    def decide_alert(self, alert_id: str, action: str, scope: str = "always") -> bool:
        """
        User decision on a pending alert
        
        Args:
            alert_id: Alert ID
            action: "allow" or "deny"
            scope: "once", "always", or "temporary"
        
        Returns:
            True if decision was processed
        """
        alert = self.pending_alerts.get(alert_id)
        if not alert:
            LOG.warning(f"Alert {alert_id} not found")
            return False
        
        conn = alert["connection"]
        proc = conn.get("proc") or conn.get("name", "unknown")
        dest = conn.get("raddr", "").split(":")[0] or "unknown"
        port = conn.get("dport")
        exe = conn.get("exe")
        
        # Create rule based on decision
        if scope in ("always", "temporary"):
            # Calculate TTL for temporary rules
            ttl_hours = 24 if scope == "temporary" else None
            
            # Create rule via manager (persists to DB)
            try:
                rule_id = rules_manager.create_rule(
                    process=proc,
                    destination=dest,
                    port=port,
                    action=action,
                    scope=scope,
                    protocol="TCP",  # Default
                    exe_path=conn.get("exe"),
                    ttl_hours=ttl_hours,
                    user_comment=f"Created via alert {alert_id}",
                    context=conn  # Store full connection context
                )
                LOG.info(f"Created {action} rule {rule_id} for {proc} -> {dest}:{port} (scope: {scope})")
            except Exception as e:
                LOG.error(f"Failed to create rule: {e}")
                return False
        
        # Mark alert as resolved
        alert["status"] = "resolved"
        alert["resolved_at"] = datetime.utcnow().isoformat()
        alert["decision"] = action
        
        # Remove from pending (keep in memory for history, but could clean up old ones)
        return True
    
    def get_alert_info_for_connection(self, conn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get alert information for a connection
        
        Args:
            conn: Connection dict with keys: proc, raddr, dport
        
        Returns:
            Dict with alert info if exists, None otherwise
            {
                "alert_id": str,
                "status": "pending" | "resolved",
                "decision": "allow" | "deny" (if resolved),
                "created_at": str (ISO timestamp),
                "resolved_at": str (ISO timestamp, if resolved)
            }
        """
        conn_key = self._connection_key(conn)
        alert_id = hashlib.md5(conn_key.encode()).hexdigest()
        
        alert = self.pending_alerts.get(alert_id)
        if not alert:
            return None
        
        result = {
            "alert_id": alert_id,
            "status": alert["status"],
            "created_at": alert["created_at"]
        }
        
        if alert["status"] == "resolved":
            result["decision"] = alert.get("decision")
            result["resolved_at"] = alert.get("resolved_at")
        
        return result
    
    def get_pending_alerts(self) -> list:
        """Get list of pending alerts"""
        return [
            alert for alert in self.pending_alerts.values()
            if alert["status"] == "pending"
        ]
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """Update alert settings"""
        # Check if we are enabling or changing levels - if so, we might want to re-scan
        was_enabled = self.settings.get("enabled", False)
        new_enabled = new_settings.get("enabled", was_enabled)
        
        self.settings.update(new_settings)
        LOG.info(f"Updated alert settings: {new_settings}")
        
        # If we just enabled alerts or changed level, clear seen_connections 
        # so existing connections are re-evaluated against new settings
        if (new_enabled and not was_enabled) or "alert_level" in new_settings:
            LOG.info("Settings changed significantly - clearing seen_connections cache to re-evaluate traffic")
            self.seen_connections.clear()
    
    def cleanup_old_alerts(self, hours: int = 24):
        """Remove old resolved alerts from memory"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        to_remove = []
        
        for alert_id, alert in self.pending_alerts.items():
            if alert["status"] == "resolved":
                resolved_at = datetime.fromisoformat(alert.get("resolved_at", ""))
                if resolved_at < cutoff:
                    to_remove.append(alert_id)
        
        for alert_id in to_remove:
            del self.pending_alerts[alert_id]
        
        if to_remove:
            LOG.info(f"Cleaned up {len(to_remove)} old alerts")


# Global instance
alert_engine = AlertEngine()


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Mock connection
    test_conn = {
        "proc": "TestApp",
        "name": "TestApp",
        "raddr": "1.2.3.4:443",
        "dport": 443,
        "level": "medio",
        "exe": "/Applications/TestApp.app/Contents/MacOS/TestApp"
    }
    
    print("Processing test connection...")
    action = alert_engine.process_connection(test_conn)
    print(f"Action: {action}")
    
    print(f"\nPending alerts: {len(alert_engine.get_pending_alerts())}")
    
    # Simulate user decision
    pending = alert_engine.get_pending_alerts()
    if pending:
        alert = pending[0]
        print(f"\nDeciding on alert {alert['id']}...")
        alert_engine.decide_alert(alert["id"], "allow", "always")
        print("Decision applied")
    
    # Process same connection again (should have rule now)
    print("\nProcessing same connection again...")
    action2 = alert_engine.process_connection(test_conn)
    print(f"Action: {action2} (should be 'allow' due to rule)")

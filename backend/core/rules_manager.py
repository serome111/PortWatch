"""
Rules Manager for PortWatch Interactive Alert Mode
Manages allow/deny rules for network connections with SQLite persistence
"""
import sqlite3
import uuid
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

LOG = logging.getLogger(__name__)

# Database path
DB_PATH = Path.home() / ".portwatch" / "rules.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class RulesManager:
    """Manages connection rules with SQLite backend"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    process TEXT NOT NULL,
                    exe_path TEXT,
                    exe_hash TEXT,
                    destination TEXT NOT NULL,
                    port INTEGER,
                    protocol TEXT,
                    action TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    user_comment TEXT,
                    enabled INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_process_dest 
                ON rules(process, destination, port)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_enabled 
                ON rules(enabled)
            """)
            
            # Migration: Add context column if not exists
            try:
                conn.execute("ALTER TABLE rules ADD COLUMN context TEXT")
            except sqlite3.OperationalError:
                pass
                
            conn.commit()
            LOG.info(f"Rules database initialized at {self.db_path}")
    
    def create_rule(
        self,
        process: str,
        destination: str,
        action: str,
        scope: str = "always",
        port: Optional[int] = None,
        protocol: str = "TCP",
        exe_path: Optional[str] = None,
        exe_hash: Optional[str] = None,
        user_comment: Optional[str] = None,
        ttl_hours: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new rule
        
        Args:
            process: Process name (e.g., "Google Chrome")
            destination: IP or domain (e.g., "api.github.com" or "1.1.1.1")
            action: "allow" or "deny"
            scope: "once", "always", "temporary"
            port: Destination port (optional)
            protocol: "TCP" or "UDP"
            exe_path: Full path to executable (optional, more specific)
            exe_hash: SHA256 hash of executable (optional, most secure)
            exe_hash: SHA256 hash of executable (optional, most secure)
            user_comment: User note about this rule
            ttl_hours: Hours until rule expires (for temporary rules)
            context: Full connection context (evidence, etc.) as dict
        
        Returns:
            Rule ID (UUID)
        """
        if action not in ("allow", "deny"):
            raise ValueError(f"Invalid action: {action}")
        if scope not in ("once", "always", "temporary"):
            raise ValueError(f"Invalid scope: {scope}")
        
        rule_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        expires_at = None
        
        if scope == "temporary" and ttl_hours:
            expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()
            
        context_json = json.dumps(context) if context else None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO rules (
                    id, process, exe_path, exe_hash, destination, port, protocol,
                    action, scope, created_at, expires_at, user_comment, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_id, process, exe_path, exe_hash, destination, port, protocol,
                action, scope, created_at, expires_at, user_comment, context_json
            ))
            conn.commit()
        
        LOG.info(f"Created rule {rule_id}: {action} {process} -> {destination}:{port}")
        return rule_id
    
    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a rule by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            d = dict(row)
            if d.get("context"):
                try:
                    d["context"] = json.loads(d["context"])
                except Exception:
                    d["context"] = {}
            return d
    
    def get_all_rules(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get all rules, optionally filtering by enabled status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM rules"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY created_at DESC"
            cursor = conn.execute(query)
            cursor = conn.execute(query)
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                if d.get("context"):
                    try:
                        d["context"] = json.loads(d["context"])
                    except Exception:
                        d["context"] = {}
                results.append(d)
            return results
    
    def find_matching_rule(
        self,
        process: str,
        destination: str,
        port: Optional[int] = None,
        exe_path: Optional[str] = None,
        exe_hash: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a matching rule for a connection
        
        Priority:
        1. Exact match by exe_hash + destination + port
        2. Exact match by exe_path + destination + port
        3. Match by process + destination + port
        4. Match by process + destination (any port)
        
        Returns:
            Matching rule dict or None
        """
        now = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Clean expired rules first
            conn.execute("""
                UPDATE rules SET enabled = 0 
                WHERE expires_at IS NOT NULL AND expires_at < ? AND enabled = 1
            """, (now,))
            conn.commit()
            
            # Priority 1: Hash match
            if exe_hash:
                cursor = conn.execute("""
                    SELECT * FROM rules 
                    WHERE enabled = 1 
                      AND exe_hash = ? 
                      AND destination = ? 
                      AND (port = ? OR port IS NULL)
                    ORDER BY port DESC NULLS LAST
                    LIMIT 1
                """, (exe_hash, destination, port))
                row = cursor.fetchone()
                if row:
                    return dict(row)
            
            # Priority 2: Exe path match
            if exe_path:
                cursor = conn.execute("""
                    SELECT * FROM rules 
                    WHERE enabled = 1 
                      AND exe_path = ? 
                      AND destination = ? 
                      AND (port = ? OR port IS NULL)
                    ORDER BY port DESC NULLS LAST
                    LIMIT 1
                """, (exe_path, destination, port))
                row = cursor.fetchone()
                if row:
                    return dict(row)
            
            # Priority 3: Process + destination + port
            cursor = conn.execute("""
                SELECT * FROM rules 
                WHERE enabled = 1 
                  AND process = ? 
                  AND destination = ? 
                  AND port = ?
                LIMIT 1
            """, (process, destination, port))
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            # Priority 4: Process + destination (any port)
            cursor = conn.execute("""
                SELECT * FROM rules 
                WHERE enabled = 1 
                  AND process = ? 
                  AND destination = ? 
                  AND port IS NULL
                LIMIT 1
            """, (process, destination))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                LOG.info(f"Deleted rule {rule_id}")
            return deleted
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule without deleting it"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("UPDATE rules SET enabled = 0 WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a previously disabled rule"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("UPDATE rules SET enabled = 1 WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_rule(
        self,
        rule_id: str,
        action: Optional[str] = None,
        user_comment: Optional[str] = None
    ) -> bool:
        """Update specific fields of a rule"""
        updates = []
        params = []
        
        if action:
            if action not in ("allow", "deny"):
                raise ValueError(f"Invalid action: {action}")
            updates.append("action = ?")
            params.append(action)
        
        if user_comment is not None:
            updates.append("user_comment = ?")
            params.append(user_comment)
        
        if not updates:
            return False
        
        params.append(rule_id)
        query = f"UPDATE rules SET {', '.join(updates)} WHERE id = ?"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def cleanup_expired_rules(self) -> int:
        """Remove expired temporary rules"""
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM rules 
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (now,))
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                LOG.info(f"Cleaned up {count} expired rules")
            return count
    
    def export_rules(self) -> List[Dict[str, Any]]:
        """Export all rules as JSON-serializable list"""
        return self.get_all_rules(enabled_only=False)
    
    def import_rules(self, rules: List[Dict[str, Any]], overwrite: bool = False):
        """
        Import rules from a list
        
        Args:
            rules: List of rule dicts
            overwrite: If True, clear existing rules first
        """
        if overwrite:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM rules")
                conn.commit()
                LOG.info("Cleared existing rules for import")
        
        for rule in rules:
            # Ensure required fields
            if not all(k in rule for k in ("process", "destination", "action", "scope")):
                LOG.warning(f"Skipping invalid rule: {rule}")
                continue
            
            # Generate new ID to avoid conflicts
            rule["id"] = str(uuid.uuid4())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO rules (
                        id, process, exe_path, exe_hash, destination, port, protocol,
                        action, scope, created_at, expires_at, user_comment, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule["id"],
                    rule["process"],
                    rule.get("exe_path"),
                    rule.get("exe_hash"),
                    rule["destination"],
                    rule.get("port"),
                    rule.get("protocol", "TCP"),
                    rule["action"],
                    rule["scope"],
                    rule.get("created_at", datetime.utcnow().isoformat()),
                    rule.get("expires_at"),
                    rule.get("user_comment"),
                    rule.get("enabled", 1)
                ))
                conn.commit()
        
        LOG.info(f"Imported {len(rules)} rules")


# Global instance
rules_manager = RulesManager()


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Create test rule
    rule_id = rules_manager.create_rule(
        process="Google Chrome",
        destination="api.github.com",
        port=443,
        action="allow",
        scope="always",
        user_comment="GitHub API access"
    )
    print(f"Created rule: {rule_id}")
    
    # Find matching rule
    match = rules_manager.find_matching_rule(
        process="Google Chrome",
        destination="api.github.com",
        port=443
    )
    print(f"Found match: {match}")
    
    # List all rules
    all_rules = rules_manager.get_all_rules()
    print(f"\nAll rules ({len(all_rules)}):")
    for rule in all_rules:
        print(f"  {rule['action']} {rule['process']} -> {rule['destination']}:{rule['port']}")

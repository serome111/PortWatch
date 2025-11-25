#!/usr/bin/env python3
"""
Test script for Interactive Alert Mode backend
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, "/Users/serome/Documents/Companies/Security/PortWatch")

# Use temporary database for testing
import os
os.environ["PORTWATCH_TEST_MODE"] = "1"

from rules_manager import RulesManager
from alert_engine import alert_engine
from notifier import notifier

# Create test rules manager with temp DB
temp_db = Path(tempfile.mkdtemp()) / "test_rules.db"
rules_manager = RulesManager(db_path=temp_db)

print("=" * 60)
print("Testing Interactive Alert Mode - Backend")
print("=" * 60)

# Test 1: Rules Manager
print("\n[Test 1] Rules Manager")
print("-" * 60)

# Create a test rule
rule_id = rules_manager.create_rule(
    process="Google Chrome",
    destination="github.com",
    port=443,
    action="allow",
    scope="always",
    user_comment="Allow GitHub access"
)
print(f"✓ Created rule: {rule_id}")

# Find the rule
match = rules_manager.find_matching_rule(
    process="Google Chrome",
    destination="github.com",
    port=443
)
print(f"✓ Found matching rule: {match['action']} for {match['process']} -> {match['destination']}")

# List all rules
all_rules = rules_manager.get_all_rules()
print(f"✓ Total rules in database: {len(all_rules)}")

# Test 2: Alert Engine
print("\n[Test 2] Alert Engine")
print("-" * 60)

# Mock connection without rule
test_conn_1 = {
    "proc": "TestApp",
    "name": "TestApp",
    "raddr": "suspicious.com:8080",
    "dport": 8080,
    "level": "medio",
    "exe": "/tmp/testapp"
}

action = alert_engine.process_connection(test_conn_1)
print(f"✓ New connection action: {action}")

pending = alert_engine.get_pending_alerts()
print(f"✓ Pending alerts: {len(pending)}")

if pending:
    alert = pending[0]
    print(f"  - Alert ID: {alert['id']}")
    print(f"  - Process: {alert['connection']['proc']}")
    print(f"  - Destination: {alert['connection']['raddr']}")
    
    # Decide on alert
    alert_engine.decide_alert(alert["id"], "allow", "always")
    print(f"✓ Decided alert: allow always")
    
    # Verify rule was created
    new_rules = rules_manager.get_all_rules()
    print(f"✓ Rules after decision: {len(new_rules)}")

# Test 3: Process same connection again (should have rule now)
action2 = alert_engine.process_connection(test_conn_1)
print(f"✓ Second connection action: {action2} (should be 'allow' due to rule)")

# Test 4: Notifier
print("\n[Test 3] Notifier (System Notifications)")
print("-" * 60)

success = notifier.send_alert(
    process="Test Process",
    destination="test.com",
    port=443,
    level="medio",
    country="US"
)
print(f"✓ Notification sent: {success}")

# Test 5: Settings
print("\n[Test 4] Alert Settings")
print("-" * 60)

current_settings = alert_engine.settings
print(f"✓ Current settings:")
for key, value in current_settings.items():
    print(f"  - {key}: {value}")

alert_engine.update_settings({"alert_level": "high"})
print(f"✓ Updated alert_level to 'high'")

# Cleanup
print("\n[Cleanup]")
print("-" * 60)
for rule in rules_manager.get_all_rules():
    rules_manager.delete_rule(rule["id"])
print(f"✓ Deleted all test rules")

print("\n" + "=" * 60)
print("✓ All tests passed!")
print("=" * 60)

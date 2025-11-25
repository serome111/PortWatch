#!/usr/bin/env python3
"""
Test script for Rule Persistence
Verifies that decisions made via alert_engine.decide_alert() are correctly
persisted to the rules database via rules_manager.
"""
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/Users/serome/Documents/Companies/Security/PortWatch")

# Use temporary database for testing
import os
os.environ["PORTWATCH_TEST_MODE"] = "1"

from rules_manager import RulesManager
from alert_engine import alert_engine

# Create test rules manager with temp DB
temp_db = Path(tempfile.mkdtemp()) / "test_persistence.db"
rules_manager = RulesManager(db_path=temp_db)

# Monkeypatch alert_engine to use our test rules manager
import alert_engine as ae_module
ae_module.rules_manager = rules_manager

print("=" * 60)
print("Testing Rule Persistence")
print("=" * 60)

# Mock connection
test_conn = {
    "proc": "PersistenceTestApp",
    "name": "PersistenceTestApp",
    "raddr": "evil.com:666",
    "dport": 666,
    "level": "alto",
    "exe": "/tmp/persistence_test"
}

# 1. Trigger an alert
print("\n1. Triggering alert...")
alert_engine.settings["enabled"] = True
alert_engine.settings["alert_level"] = "high"

action = alert_engine.process_connection(test_conn)
print(f"Action returned: {action}")

pending = alert_engine.get_pending_alerts()
if not pending:
    print("❌ FAILURE: No pending alert created.")
    sys.exit(1)

alert_id = pending[0]["id"]
print(f"Alert created: {alert_id}")

# 2. Decide to BLOCK ALWAYS
print("\n2. Deciding to BLOCK ALWAYS...")
success = alert_engine.decide_alert(alert_id, "deny", "always")
if not success:
    print("❌ FAILURE: decide_alert returned False.")
    sys.exit(1)
print("Decision applied.")

# 3. Verify rule exists in RulesManager
print("\n3. Verifying rule persistence...")
rule = rules_manager.find_matching_rule(
    process=test_conn["proc"],
    destination="evil.com",
    port=666
)

if rule:
    print(f"✅ SUCCESS: Rule found in database!")
    print(f"   - ID: {rule['id']}")
    print(f"   - Action: {rule['action']}")
    print(f"   - Scope: {rule['scope']}")
    
    if rule["action"] == "deny" and rule["scope"] == "always":
        print("   - Rule attributes match expected values.")
    else:
        print(f"❌ FAILURE: Rule attributes mismatch. Expected deny/always, got {rule['action']}/{rule['scope']}")
        sys.exit(1)
else:
    print("❌ FAILURE: Rule NOT found in database.")
    sys.exit(1)

# 4. Verify next connection is blocked
print("\n4. Verifying enforcement...")
action_2 = alert_engine.process_connection(test_conn)
print(f"Next connection action: {action_2}")

if action_2 == "deny":
    print("✅ SUCCESS: Connection correctly denied by rule.")
else:
    print(f"❌ FAILURE: Connection not denied (got {action_2}).")
    sys.exit(1)

print("\n" + "=" * 60)

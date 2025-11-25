#!/usr/bin/env python3
"""
Test script for Strict Alerting Mode
Verifies that repeated connections trigger alerts repeatedly (return "ask")
instead of being implicitly allowed.
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
temp_db = Path(tempfile.mkdtemp()) / "test_strict_rules.db"
rules_manager = RulesManager(db_path=temp_db)

print("=" * 60)
print("Testing Strict Alerting Mode")
print("=" * 60)

# Ensure alert engine uses our temp rules manager (it imports the global one, so we might need to patch or just rely on it using the same DB if we could inject it, but alert_engine imports 'rules_manager' instance directly. 
# Actually, alert_engine.py imports 'rules_manager' from 'rules_manager.py'.
# Since we can't easily patch the imported module variable in this script without more hacks, 
# we will rely on the fact that we are running in a separate process or just accept that we might need to clear the real DB or use a mock.
# BETTER APPROACH: We can monkeypatch alert_engine.rules_manager
import alert_engine as ae_module
ae_module.rules_manager = rules_manager

# Clear any existing state in alert engine
alert_engine.seen_connections.clear()
alert_engine.pending_alerts.clear()
alert_engine.settings["enabled"] = True
alert_engine.settings["alert_level"] = "medium" # Set to medium so our test conn triggers it

# Mock connection
test_conn = {
    "proc": "StrictTestApp",
    "name": "StrictTestApp",
    "raddr": "1.1.1.1:80",
    "dport": 80,
    "level": "medio", # Matches alert_level medium
    "exe": "/tmp/stricttest"
}

print(f"\n[Test] Processing repeated connections for {test_conn['proc']}")
print("-" * 60)

# We will process the same connection 5 times
# In the OLD logic: 1st -> "ask", 2nd..5th -> "allow"
# In the NEW logic: 1st..5th -> "ask"

actions = []
for i in range(1, 6):
    print(f"Attempt {i}...", end=" ")
    action = alert_engine.process_connection(test_conn)
    actions.append(action)
    print(f"Action: {action}")
    
    # Small sleep to ensure timestamps might differ slightly if that mattered, but it shouldn't
    time.sleep(0.1)

print("-" * 60)
print(f"Actions returned: {actions}")

# Verify results
all_ask = all(a == "ask" for a in actions)
if all_ask:
    print("\n✅ SUCCESS: All connections returned 'ask'. Strict alerting is working.")
else:
    print("\n❌ FAILURE: Some connections were allowed implicitly.")
    sys.exit(1)

# Verify pending alert count
pending = alert_engine.get_pending_alerts()
if pending:
    count = pending[0].get("count", 0)
    print(f"Pending alert count: {count}")
    if count == 5:
        print("✅ SUCCESS: Alert count incremented correctly.")
    else:
        print(f"❌ FAILURE: Alert count mismatch (expected 5, got {count})")
        sys.exit(1)
else:
    print("❌ FAILURE: No pending alert found.")
    sys.exit(1)

print("\n" + "=" * 60)

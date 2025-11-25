#!/usr/bin/env python3
"""
Test notification system directly without uvicorn
"""
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from notifier import notifier

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("TESTING NOTIFICATION SYSTEM")
print("=" * 60)

print("\n1. Notifier Info:")
print(f"   OS: {notifier.os_type}")
print(f"   terminal-notifier path: {notifier.terminal_notifier_path}")

print("\n2. Sending LOW risk alert (banner)...")
result = notifier.send_alert(
    process="Safari",
    destination="apple.com",
    port=443,
    level="bajo",
    country="US"
)
print(f"   Result: {'✓ SUCCESS' if result else '✗ FAILED'}")

print("\n3. Sending MEDIUM risk alert (dialog)...")
result = notifier.send_alert(
    process="Unknown Process",
    destination="suspicious.com",
    port=8080,
    level="medio"
)
print(f"   Result: {'✓ SUCCESS' if result else '✗ FAILED'}")

print("\n" + "=" * 60)
print("CHECK YOUR SCREEN FOR NOTIFICATIONS!")
print("=" * 60)

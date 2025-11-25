#!/usr/bin/env python3
"""
Demo script to test Interactive Alert Mode
Simulates a suspicious connection and triggers a system notification
"""
import sys
sys.path.insert(0, "/Users/serome/Documents/Companies/Security/PortWatch")

from notifier import notifier

print("=" * 60)
print("Testing Alert Notification")
print("=" * 60)

# Simulate different risk levels
connections = [
    {
        "process": "Unknown Process",
        "destination": "suspicious-domain.com",
        "port": 8080,
        "level": "bajo",
        "country": "RU"
    },
    {
        "process": "/tmp/malware",
        "destination": "1.2.3.4",
        "port": 3333,
        "level": "medio",
        "country": "CN"
    },
    {
        "process": "sketchy_binary",
        "destination": "evil-c2.net",
        "port": 4444,
        "level": "alto",
        "country": None
    }
]

print("\nSending test notifications...\n")

for i, conn in enumerate(connections, 1):
    print(f"{i}. Sending {conn['level']} risk alert...")
    success = notifier.send_alert(
        process=conn["process"],
        destination=conn["destination"],
        port=conn["port"],
        level=conn["level"],
        country=conn["country"]
    )
    print(f"   {'✓' if success else '✗'} Notification sent: {success}")
    
    # Brief pause between notifications
    import time
    time.sleep(2)

print("\n" + "=" * 60)
print("Check your system notifications!")
print("=" * 60)
print("\nNOTE: On macOS you should see notifications with sound.")
print("On Linux you need 'notify-send' installed (libnotify-bin).")

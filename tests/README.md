# PortWatch Tests

This directory contains test, diagnostic, and simulation scripts for PortWatch.

## Quick Start

```bash
# Check system status
python tests/check_status.py

# Diagnose alert system
python tests/diagnose_alerts.py

# GeoIP Test
python tests/test_geoip.py
```

## Functional Tests

### `test_alert_mode.py`
Tests the interactive alert system.
```bash
python tests/test_alert_mode.py
```

### `test_alert_integration.sh`
Full integration test of the alert system.
```bash
bash tests/test_alert_integration.sh
```

### `test_strict_alerting.py`
Verifies strict alert mode.
```bash
python tests/test_strict_alerting.py
```

### `test_rule_persistence.py`
Verifies firewall rule persistence in SQLite.
```bash
python tests/test_rule_persistence.py
```

### `test_resource_alert.py`
Tests alerts based on resource usage (CPU, RAM, disk).
```bash
python tests/test_resource_alert.py
```

### `test_geoip.py`
Verifies IP geolocation functionality.
```bash
python tests/test_geoip.py
```

### `test_notifications.py`
Tests the native macOS notification system.
```bash
python tests/test_notifications.py
```

### `test_icons.py`
Verifies icon rendering in the application.
```bash
python tests/test_icons.py
```

### `test_tray_setup.py`
Tests system tray icon initialization.
```bash
python tests/test_tray_setup.py
```

### `test_dynamic_port.sh`
Tests server dynamic port assignment.
```bash
bash tests/test_dynamic_port.sh
```

## Simulation and Verification

### `simulate_ransomware.py`
Simulates ransomware behavior for testing.

**WARNING:** Creates a large file (`ransomware_sim.tmp`) and consumes resources. For testing only.

```bash
python tests/simulate_ransomware.py
```

### `verify_ransomware_detection.py`
Verifies ransomware behavior detection.
```bash
# Terminal 1:
python tests/simulate_ransomware.py

# Terminal 2:
python tests/verify_ransomware_detection.py
```

### `demo_alerts.py`
Interactive demonstration of the alert system.
```bash
python tests/demo_alerts.py
```

### `trigger_alert.py`
Triggers a simple test alert.
```bash
python tests/trigger_alert.py
```

## Diagnostic Utilities

### `check_status.py`
Shows general PortWatch status (server, configuration, processes).
```bash
python tests/check_status.py
```

### `diagnose_alerts.py`
Comprehensive diagnosis of the alert system (configuration, permissions, status).
```bash
python tests/diagnose_alerts.py
```

### `clear_alert_cache.py`
Clears the seen alerts cache (useful during development).
```bash
python tests/clear_alert_cache.py
```

## Recommended Testing Workflow

1. **General Status:** `check_status.py` - Verify system status
2. **Basic Alerts:** `test_alert_mode.py` - Alert system
3. **Resources:** `test_resource_alert.py` - Resource monitoring
4. **Ransomware:** `simulate_ransomware.py` + `verify_ransomware_detection.py` - Heuristics
5. **Integration:** `test_alert_integration.sh` - Full end-to-end test

## Important Notes

- **Permissions:** Some tests require special permissions on macOS (notifications, network)
- **Environment:** Run from the project root directory
- **Python:** Requires Python 3.11+
- **Dependencies:** Activate venv and install dependencies before running tests

## Troubleshooting

If you encounter issues:

1. Verify the server is running
2. Check notification permissions in System Preferences -> Notifications
3. Check server logs
4. Run `diagnose_alerts.py` for a full diagnosis

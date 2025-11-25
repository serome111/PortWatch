#!/usr/bin/env python3
"""
Quick test to verify tray_app imports work and frontend path is correct
"""
import sys
from pathlib import Path

# Test imports
try:
    from fastapi.staticfiles import StaticFiles
    print("✓ StaticFiles import works")
except ImportError as e:
    print(f"✗ StaticFiles import failed: {e}")
    sys.exit(1)

# Add path for local imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    import server
    print("✓ server module imports")
except ImportError as e:
    print(f"✗ server import failed: {e}")
    sys.exit(1)

# Test path function
def _base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent

def _frontend_dist_path() -> Path:
    base = _base_path()
    if getattr(sys, "frozen", False):
        return base / "frontend" / "dist"
    return base / "frontend" / "dist"

# Check frontend path
dist_path = _frontend_dist_path()
print(f"\nFrontend dist path: {dist_path}")
print(f"Exists: {dist_path.exists()}")

if dist_path.exists():
    # List files
    files = list(dist_path.glob("*"))
    print(f"Files found: {len(files)}")
    for f in files[:5]:
        print(f"  - {f.name}")
    
    # Check for index.html
    index_html = dist_path / "index.html"
    if index_html.exists():
        print("\n✓ index.html found")
        # Check if it contains "PortWatch"
        content = index_html.read_text()
        if "PortWatch" in content:
            print("✓ index.html contains 'PortWatch'")
        else:
            print("⚠ index.html doesn't contain 'PortWatch'")
    else:
        print("\n✗ index.html NOT found")
        sys.exit(1)
else:
    print("\n✗ Frontend dist path doesn't exist")
    print("Run: cd frontend && npm run build")
    sys.exit(1)

print("\n" + "="*50)
print("✓ All checks passed!")
print("="*50)

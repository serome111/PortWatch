import os
import psutil
import plistlib
import subprocess
import tempfile
import base64
import sys

def get_app_icon(pid):
    try:
        proc = psutil.Process(pid)
        exe = proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    if not exe:
        return None

    # Check if inside .app
    # Typical path: /Applications/AppName.app/Contents/MacOS/Binary
    if ".app/" not in exe:
        return None
    
    app_path = exe.split(".app/")[0] + ".app"
    contents_path = os.path.join(app_path, "Contents")
    plist_path = os.path.join(contents_path, "Info.plist")
    
    if not os.path.exists(plist_path):
        return None

    try:
        with open(plist_path, 'rb') as f:
            plist = plistlib.load(f)
        
        icon_name = plist.get('CFBundleIconFile')
        if not icon_name:
            return None
            
        if not icon_name.endswith('.icns'):
            icon_name += '.icns'
            
        icon_path = os.path.join(contents_path, "Resources", icon_name)
        
        if not os.path.exists(icon_path):
            return None
            
        # Convert to PNG using sips
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
            
        # sips -s format png --resampleHeightWidth 64 64 icon.icns --out icon.png
        cmd = [
            "sips", 
            "-s", "format", "png", 
            "--resampleHeightWidth", "64", "64", 
            icon_path, 
            "--out", tmp_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        with open(tmp_path, "rb") as f:
            png_data = f.read()
            
        os.unlink(tmp_path)
        return png_data

    except Exception as e:
        print(f"Error processing {exe}: {e}")
        return None

if __name__ == "__main__":
    print("Scanning processes for icons...")
    count = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            icon_data = get_app_icon(proc.info['pid'])
            if icon_data:
                print(f"✅ Found icon for {proc.info['name']} (PID {proc.info['pid']}) - {len(icon_data)} bytes")
                count += 1
                if count >= 5:
                    break
        except:
            continue

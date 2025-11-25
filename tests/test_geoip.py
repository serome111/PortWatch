import geoip2.database
from pathlib import Path
import sys

# Path to the DB
db_path = Path.home() / ".portwatch_geoip.mmdb"

print(f"Checking DB at: {db_path}")

if not db_path.exists():
    print("Error: DB file does not exist.")
    sys.exit(1)

print(f"DB size: {db_path.stat().st_size / (1024*1024):.2f} MB")

try:
    reader = geoip2.database.Reader(str(db_path))
    print("DB loaded successfully.")
    
    test_ip = "8.8.8.8"
    print(f"Looking up {test_ip}...")
    response = reader.country(test_ip)
    
    print(f"Country: {response.country.name}")
    print(f"ISO Code: {response.country.iso_code}")
    
    if response.country.iso_code == "US":
        print("SUCCESS: Lookup verified.")
    else:
        print("WARNING: Lookup result unexpected.")
        
except Exception as e:
    print(f"ERROR: {e}")

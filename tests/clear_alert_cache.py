#!/usr/bin/env python3
"""
Clear alert cache to allow re-alerting on previously seen connections
"""
import requests

BASE_URL = "http://localhost:8000"

def clear_cache():
    try:
        response = requests.post(f"{BASE_URL}/api/alerts/clear_cache")
        data = response.json()
        
        if data.get("ok"):
            print(f"✅ Cache cleared successfully!")
            print(f"   Removed {data.get('cleared_count', 0)} seen connections")
            print(f"\n💡 Now you can test alerts again:")
            print(f"   1. Activate your program")
            print(f"   2. It will be treated as a NEW connection")
            print(f"   3. Should trigger alert if level is medium/high")
        else:
            print(f"❌ Error: {data.get('error')}")
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server")
        print("   Make sure the server is running: python3 server.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    print("🧹 Clearing Alert Cache...\n")
    clear_cache()

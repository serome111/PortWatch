import time
import psutil
import sys
import os

# Add current directory to path to import server
sys.path.append(os.getcwd())

from server import _scan_resource_threats, PROC_IO_CACHE

def verify_detection():
    print("Verifying Ransomware Detection...")
    
    # Find the simulation process
    sim_pid = None
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if "simulate_ransomware.py" in " ".join(proc.info['cmdline'] or []):
            sim_pid = proc.info['pid']
            print(f"Found simulation process: PID {sim_pid}")
            break
    
    if not sim_pid:
        print("Simulation process not found!")
        return False

    # Run scan multiple times to build I/O history
    print("Running scans...")
    detected = False
    for i in range(5):
        threats = _scan_resource_threats()
        
        # Check if our pid is in threats
        for threat in threats:
            if threat['pid'] == sim_pid:
                print(f"Scan {i+1}: Threat detected! Score: {threat['threat_score']}")
                print(f"Reasons: {threat['reasons']}")
                
                # Check for specific ransomware reason
                for reason in threat['reasons']:
                    if "RANSOMWARE" in reason:
                        print("✅ RANSOMWARE HEURISTIC TRIGGERED!")
                        detected = True
                        break
        
        if detected:
            break
            
        time.sleep(1)
        
    return detected

if __name__ == "__main__":
    if verify_detection():
        print("TEST PASSED")
        sys.exit(0)
    else:
        print("TEST FAILED")
        sys.exit(1)

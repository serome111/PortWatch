import time
import os
import hashlib
import threading

def consume_cpu():
    """Consume CPU by calculating hashes"""
    while True:
        hashlib.sha256(os.urandom(1024)).hexdigest()

def consume_disk_io():
    """Consume Disk I/O by writing large files"""
    filename = "ransomware_sim.tmp"
    try:
        with open(filename, "wb") as f:
            while True:
                # Write 10MB chunks
                f.write(os.urandom(10 * 1024 * 1024))
                f.flush()
                os.fsync(f.fileno())
                time.sleep(0.1) # Slight pause to not kill the system completely
    except KeyboardInterrupt:
        pass
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    print(f"Starting Ransomware Simulation (PID: {os.getpid()})")
    print("Simulating High CPU + High Disk I/O...")
    
    # Start CPU threads
    for _ in range(4):
        t = threading.Thread(target=consume_cpu)
        t.daemon = True
        t.start()
        
    # Start Disk I/O
    consume_disk_io()

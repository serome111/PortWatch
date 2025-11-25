import time
import psutil
import threading
import sys
import os

def consume_cpu():
    """Consume CPU cycles to trigger alert"""
    print(f"🔥 Starting CPU consumer (PID: {os.getpid()})...")
    t_end = time.time() + 15
    while time.time() < t_end:
        # Busy loop
        _ = [x**2 for x in range(1000)]

def consume_memory():
    """Consume Memory to trigger alert"""
    print(f"🧠 Starting Memory consumer (PID: {os.getpid()})...")
    # Allocate ~600MB
    data = bytearray(600 * 1024 * 1024)
    time.sleep(15)

if __name__ == "__main__":
    print("Test: Resource Usage Alert Simulation")
    print("-------------------------------------")
    print("This script will consume High CPU and RAM to test PortWatch detection.")
    print("Make sure PortWatch is running!")
    
    # Start threads
    t1 = threading.Thread(target=consume_cpu)
    t2 = threading.Thread(target=consume_memory)
    
    t1.start()
    t2.start()
    
    # Keep main thread alive and maybe make a network connection
    # PortWatch only monitors processes with network connections
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("1.1.1.1", 80)) # Connect to Cloudflare DNS
        print("🌐 Network connection established to 1.1.1.1:80")
        
        print("⏳ Waiting for PortWatch to detect (10s)...")
        time.sleep(10)
        s.close()
    except Exception as e:
        print(f"Error connecting: {e}")
    
    t1.join()
    t2.join()
    print("Done.")

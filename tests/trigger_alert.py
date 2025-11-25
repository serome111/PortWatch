import socket
import time

print("Connecting to 8.8.8.8:53...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("8.8.8.8", 53))
    print("Connected. Sleeping for 10 seconds...")
    time.sleep(10)
    s.close()
    print("Done.")
except Exception as e:
    print(f"Error: {e}")

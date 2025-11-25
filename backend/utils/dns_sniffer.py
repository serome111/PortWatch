import subprocess
import threading
import time
import re
import logging
from collections import deque
from .dns_analyzer import analyze_domain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DNSSniffer")

class DNSSniffer:
    def __init__(self):
        self.dns_map = {}  # IP -> {domain, timestamp, analysis}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Regex to parse tcpdump output
        # Example: 10:20:30.123456 IP 8.8.8.8.53 > 192.168.1.5.12345: 12345 1/0/0 A 142.250.1.1 (48)
        # We are looking for "A <IP>" responses
        self.a_record_pattern = re.compile(r'A\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
        
        # We also need to capture the query to link it to the response, 
        # but for simplicity in this v1, we'll try to capture lines that have both or close proximity.
        # Actually, tcpdump -v might show the question in the response packet.
        # Let's use a simpler approach: Capture A records and the domain name which usually appears in the same line or previous.
        
        # Better approach with tcpdump:
        # tcpdump -l -n -i any udp port 53
        # Output format varies, but usually:
        # ... IP 192.168.1.5.5678 > 8.8.8.8.53: 12345+ A? google.com. (28)
        # ... IP 8.8.8.8.53 > 192.168.1.5.5678: 12345 1/0/0 A 142.250.1.1 (44)
        
        # We will map Transaction ID (12345) to Domain from the Query, 
        # then map IP to Domain when we see the Response.
        self.pending_queries = {} # TransID -> Domain
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self.thread.start()
        logger.info("DNS Sniffer started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            
    def get_domain_for_ip(self, ip):
        with self.lock:
            data = self.dns_map.get(ip)
            if data:
                # Clean up old entries (older than 1 hour)
                if time.time() - data['ts'] > 3600:
                    del self.dns_map[ip]
                    return None
                return data
            return None

    def _sniff_loop(self):
        # Command to capture DNS traffic
        # -l: Buffered output
        # -n: Don't resolve IPs
        # -i any: Listen on all interfaces (might need adjustment on macOS, usually en0 or pktap, but 'any' often works or requires specific interface)
        # On macOS 'any' might not work for all cases, but let's try. If not, we might need to detect default interface.
        # Using 'udp port 53' filter.
        
        cmd = ["tcpdump", "-l", "-n", "udp", "port", "53"]
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1
            )
            
            # Regexes
            # Query: ID+ A? domain.com.
            query_re = re.compile(r':\s+(\d+)\+\s+A\?\s+([a-zA-Z0-9.-]+)\.')
            
            # Response: ID ... A 1.2.3.4
            resp_re = re.compile(r':\s+(\d+)\s+.*A\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
            
            for line in process.stdout:
                if not self.running:
                    break
                    
                try:
                    # Check for Query
                    q_match = query_re.search(line)
                    if q_match:
                        trans_id, domain = q_match.groups()
                        self.pending_queries[trans_id] = domain
                        
                        # Cleanup pending queries to prevent memory leak
                        if len(self.pending_queries) > 1000:
                            self.pending_queries.clear()
                        continue
                        
                    # Check for Response
                    r_match = resp_re.search(line)
                    if r_match:
                        trans_id, ip = r_match.groups()
                        domain = self.pending_queries.get(trans_id)
                        
                        if domain:
                            # Analyze domain
                            analysis = analyze_domain(domain)
                            
                            with self.lock:
                                self.dns_map[ip] = {
                                    "domain": domain,
                                    "ts": time.time(),
                                    "analysis": analysis
                                }
                                
                            # Optional: Remove from pending (but sometimes multiple IPs return for same ID)
                            # self.pending_queries.pop(trans_id, None) 
                            
                except Exception as e:
                    # Ignore parsing errors
                    pass
                    
            process.terminate()
            
        except Exception as e:
            logger.error(f"DNS Sniffer failed: {e}")
            self.running = False

# Global instance
sniffer = DNSSniffer()

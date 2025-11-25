import math
import re
import json
import os
from pathlib import Path

# Default lists (fallback if config file doesn't exist)
DEFAULT_WHITELIST_DOMAINS = {
    "apple.com", "icloud.com", "googleapis.com", "google.com", 
    "amazonaws.com", "microsoft.com", "windowsupdate.com", 
    "digicert.com", "cloudflare.com", "akamai.net", "cdn.mozilla.net"
}

DEFAULT_WHITELIST_SUFFIXES = (
    ".apple.com", ".icloud.com", ".google.com", ".googleapis.com", 
    ".amazonaws.com", ".microsoft.com", ".azure.com", ".office.com",
    ".cdn.mozilla.net", ".akamaiedge.net", ".cloudfront.net"
)

DEFAULT_RISKY_KEYWORDS = [
    "xmrig", "pool", "minergate", "nanopool", "nicehash", # Mining
    "tor2web", "onion.to", "tor.link", # Tor proxies
    "tracker", "adserver", "telemetry", # Privacy
    "rat", "c2", "payload", "exploit" # Malware terms
]

DEFAULT_RISKY_TLDS = {
    ".xyz", ".top", ".ru", ".cn", ".tk", ".ml", ".ga", ".cf", ".gq", ".pw", ".cc"
}

def get_config_path():
    """Returns the path to the DNS config file."""
    if os.name == 'posix':  # macOS/Linux
        config_dir = Path.home() / "Library" / "Application Support" / "PortWatch"
    else:
        config_dir = Path.home() / ".portwatch"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "dns_config.json"

def load_dns_config():
    """Load DNS config from JSON file, or return defaults if file doesn't exist."""
    config_path = get_config_path()
    
    if not config_path.exists():
        # Create default config
        config = {
            "whitelist_domains": list(DEFAULT_WHITELIST_DOMAINS),
            "whitelist_suffixes": list(DEFAULT_WHITELIST_SUFFIXES),
            "blacklist_keywords": DEFAULT_RISKY_KEYWORDS,
            "blacklist_tlds": list(DEFAULT_RISKY_TLDS)
        }
        save_dns_config(config)
        return config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # Validate structure
            if not all(k in config for k in ["whitelist_domains", "whitelist_suffixes", "blacklist_keywords", "blacklist_tlds"]):
                raise ValueError("Invalid config structure")
            return config
    except Exception as e:
        print(f"Error loading DNS config: {e}, using defaults")
        return {
            "whitelist_domains": list(DEFAULT_WHITELIST_DOMAINS),
            "whitelist_suffixes": list(DEFAULT_WHITELIST_SUFFIXES),
            "blacklist_keywords": DEFAULT_RISKY_KEYWORDS,
            "blacklist_tlds": list(DEFAULT_RISKY_TLDS)
        }

def save_dns_config(config):
    """Save DNS config to JSON file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving DNS config: {e}")
        return False

# Load config at module initialization
_dns_config = load_dns_config()

# Dynamic lists (loaded from config)
WHITELIST_DOMAINS = set(_dns_config.get("whitelist_domains", []))
WHITELIST_SUFFIXES = tuple(_dns_config.get("whitelist_suffixes", []))
RISKY_KEYWORDS = _dns_config.get("blacklist_keywords", [])
RISKY_TLDS = set(_dns_config.get("blacklist_tlds", []))

def reload_dns_config():
    """Reload DNS config from disk and update global lists."""
    global WHITELIST_DOMAINS, WHITELIST_SUFFIXES, RISKY_KEYWORDS, RISKY_TLDS, _dns_config
    _dns_config = load_dns_config()
    WHITELIST_DOMAINS = set(_dns_config.get("whitelist_domains", []))
    WHITELIST_SUFFIXES = tuple(_dns_config.get("whitelist_suffixes", []))
    RISKY_KEYWORDS = _dns_config.get("blacklist_keywords", [])
    RISKY_TLDS = set(_dns_config.get("blacklist_tlds", []))
    return True


def calculate_entropy(text):
    """Calculates Shannon entropy of a string"""
    if not text:
        return 0
    entropy = 0
    for x in range(256):
        p_x = float(text.count(chr(x))) / len(text)
        if p_x > 0:
            entropy += - p_x * math.log(p_x, 2)
    return entropy

def analyze_domain(domain):
    """
    Analyzes a domain name and returns a risk assessment.
    Returns: { "score": int, "risk": str, "reasons": list }
    """
    if not domain:
        return {"score": 0, "risk": "SAFE", "reasons": []}
    
    domain = domain.lower().strip('.')
    
    # 1. Whitelist Check
    if domain in WHITELIST_DOMAINS or domain.endswith(WHITELIST_SUFFIXES):
        return {"score": 0, "risk": "SAFE", "reasons": ["Whitelisted"]}

    score = 0
    reasons = []

    # 2. Entropy Check (DGA Detection)
    # Remove TLD for entropy calculation to focus on the name
    parts = domain.split('.')
    name_part = parts[0] if len(parts) > 1 else domain
    
    entropy = calculate_entropy(name_part)
    if entropy > 4.5:
        score += 50
        reasons.append(f"High Entropy ({entropy:.2f})")
    elif entropy > 4.0:
        score += 20
        reasons.append(f"Elevated Entropy ({entropy:.2f})")

    # 3. Length Check (Tunneling Detection)
    if len(domain) > 60:
        score += 40
        reasons.append("Excessive Length (Tunneling?)")
    elif len(domain) > 40:
        score += 15
        reasons.append("Long Domain Name")

    # 4. TLD Check
    for tld in RISKY_TLDS:
        if domain.endswith(tld):
            score += 20
            reasons.append(f"Risky TLD ({tld})")
            break

    # 5. Keyword Check
    for kw in RISKY_KEYWORDS:
        if kw in domain:
            score += 40
            reasons.append(f"Suspicious Keyword ({kw})")
            break

    # 6. Numeric Check (IP-like domains)
    # e.g. 1-2-3-4.isp.com
    if re.search(r'\d{1,3}[-.]\d{1,3}[-.]\d{1,3}[-.]\d{1,3}', domain):
        score += 10
        reasons.append("Contains IP Address")

    # Verdict
    risk_level = "SAFE"
    if score >= 60:
        risk_level = "CRITICAL"
    elif score >= 30:
        risk_level = "SUSPICIOUS"
    elif score > 0:
        risk_level = "LOW"

    return {
        "score": min(100, score),
        "risk": risk_level,
        "reasons": reasons,
        "entropy": round(entropy, 2)
    }

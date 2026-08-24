import urllib.parse
import ipaddress
import socket

def is_safe_url(url: str) -> bool:
    """
    Checks if a URL is safe to fetch (prevents SSRF).
    Blocks localhost, private IP ranges, loopback, and link-local addresses.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Basic string checks
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
            return False
            
        # Try to resolve IP to prevent DNS rebinding or hostname obfuscation
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            # If we can't resolve it, let it pass (HTTP client will fail naturally)
            pass
        else:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return False
                
        return True
    except Exception:
        return False

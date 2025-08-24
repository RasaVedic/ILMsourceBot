import requests
import os
import time
import threading
from random import choice

# -----------------------
# Proxy/Tor list (India)
# -----------------------
proxies_list = [
    'socks5h://127.0.0.1:9050',  # Tor default
    'http://user1:pass1@ip1:port',  # India proxy 1
    'http://user2:pass2@ip2:port',  # India proxy 2
    'http://user3:pass3@ip3:port',  # India proxy 3
    'http://user4:pass4@ip4:port',  # India proxy 4
    'http://user5:pass5@ip5:port',  # India proxy 5
    'http://user6:pass6@ip6:port',  # India proxy 6
    'http://user7:pass7@ip7:port',  # India proxy 7
    'http://user8:pass8@ip8:port',  # India proxy 8
    'http://user9:pass9@ip9:port',  # India proxy 9
    'http://user10:pass10@ip10:port'  # India proxy 10
]

# -----------------------
# Tor & proxy functions
# -----------------------
def start_tor():
    if os.system("pgrep tor > /dev/null") != 0:
        print("[Tor] Starting Tor...")
        os.system("tor &")
        time.sleep(10)

def rotate_ip():
    if os.system("pgrep tor > /dev/null") == 0:
        os.system("killall -HUP tor")
        print("[Tor] IP rotated")
        time.sleep(5)
    else:
        print("[Tor] Tor is not running. Starting now...")
        start_tor()

def check_current_ip(proxy):
    try:
        response = requests.get(
            'https://ifconfig.me',
            proxies={'http': proxy, 'https': proxy},
            timeout=10
        )
        return response.text
    except:
        return "Proxy not working"

def get_random_proxy():
    return choice(proxies_list)

def get_proxy_for_bot():
    start_tor()
    proxy = get_random_proxy()
    ip = check_current_ip(proxy)
    print("[Proxy Manager] Using IP:", ip)
    return proxy

# -----------------------
# Automatic IP rotation
# -----------------------
def auto_rotate(interval_hours=1.5):
    proxy = 'socks5h://127.0.0.1:9050'
    while True:
        rotate_ip()
        new_ip = check_current_ip(proxy)
        print(f"[Auto-Rotate] New IP: {new_ip}")
        time.sleep(interval_hours * 3600)

def start_auto_rotation(interval_hours=1.5):
    thread = threading.Thread(target=auto_rotate, args=(interval_hours,), daemon=True)
    thread.start()
    print(f"[Auto-Rotate] Background IP rotation started every {interval_hours} hours")

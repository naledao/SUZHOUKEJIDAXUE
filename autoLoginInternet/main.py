import requests
import time
import re
import json
import logging
import websocket
from typing import Dict, Any, Optional

# "serverIp2": "14.103.202.40"
# Log configuration: append mode, UTF-8
logging.basicConfig(
    filename='login.log',
    filemode='a',
    format='%(asctime)s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

JSONP_RE = re.compile(r"[^(]+\((.*)\)\s*$")

def parse_jsonp(text: str) -> Dict[str, Any]:
    m = JSONP_RE.match(text)
    if not m:
        raise ValueError(f"Unable to parse response as JSONP: {text[:120]}...")
    return json.loads(m.group(1))

def login_eportal(
        username: str,
        password: str,
        wlan_user_ip: str,
        wlan_user_mac: str,
        wlan_ac_ip: str,
        wlan_ac_name: str,
        base_url: str = "http://10.160.63.9:801/eportal/"
) -> dict:
    sess = requests.Session()
    ts = str(int(time.time() * 1000))
    params = {
        "c": "Portal",
        "a": "login",
        "login_method": "1",
        "user_account": username,
        "user_password": password,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_mac": wlan_user_mac,
        "wlan_ac_ip": wlan_ac_ip,
        "wlan_ac_name": wlan_ac_name,
        "jsVersion": "3.0",
        "callback": f"dr{ts}",
        "_": ts,
    }
    resp = sess.get(base_url, params=params, timeout=10)
    resp.raise_for_status()
    return parse_jsonp(resp.text)

def logout_campus(wlan_user_ip: str) -> Dict[str, Any]:
    """
    Logout from campus network and return parsed JSON.
    """
    base_url = "http://10.160.63.9:801/eportal/"
    now = int(time.time() * 1000)  # millisecond timestamp

    params = {
        "c": "Portal",
        "a": "logout",
        "callback": f"dr{now}",
        "login_method": 1,
        "user_account": "drcom",
        "user_password": "123",
        "ac_logout": 0,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_ipv6": "",
        "wlan_vlan_id": 1,
        "wlan_user_mac": "44f770ccf6ec",
        "wlan_ac_ip": "",
        "wlan_ac_name": "",
        "jsVersion": "3.0",
        "_": now
    }

    resp = requests.get(base_url, params=params, timeout=5)
    resp.raise_for_status()
    return parse_jsonp(resp.text)

def load_configs(path) -> list:
    """Load all login configurations from JSON file, return as list"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def op_login(username: str, password: str, wlan_user_ip: str, wlan_user_mac: str, wlan_ac_ip: str,wlan_ac_name: str,email:str,ws):
    try:
        result = login_eportal(
            username, password,
            wlan_user_ip, wlan_user_mac,
            wlan_ac_ip, wlan_ac_name
        )
        if result.get("result") == '1':
            logging.info(f"{username}: re-login successful")
            ws.send(f"login:1:{email}:{username}")
        else:
            logging.error(f"{username}: login error — {result}")
            ws.send(f"login:0:{email}:{username}======{result}\n请检查您的服务信息是否正确")
    except Exception as e:
        logging.error(f"{username}: login exception — {e}")
        ws.send(f"login:0:{email}:{username}======{e}")


def op_logout(wlan_user_ip,ws,email,username):
    try:
        result = logout_campus(wlan_user_ip)
        code = result.get("result")  # "1" or "0"
        if code == '1':
            ws.send(f"logout:1:{email}:{username}")
            logging.info(f"{username}: logout successful")
        else:
            logging.info(f"{username}: logout failed, {result}")
            ws.send(f"logout:0:{email}:{username}======{result}\n请检查您的服务信息是否正确")
    except Exception as e:
        logging.error(f"{username}: logout exception — {e}")
        ws.send(f"0:logout:0:{email}:{username}======{e}")

class CampusAutoLoginClient:
    def __init__(self, server_ip: str, max_retries: int = 12, retry_delay_sec: int = 3):
        self.server_ip = server_ip
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self.ws: Optional[websocket.WebSocketApp] = None
        self.consecutive_failures = 0  # 连续连接失败计数

    # ===== WebSocket callbacks =====
    def on_open(self, ws):
        logging.info("websocket connected")
        # 成功建立连接，清零失败计数
        self.consecutive_failures = 0

    def on_message(self, ws, message: str):
        try:
            messageObj = json.loads(message)
        except Exception:
            logging.error(f"Received unknown message {message}")
            return

        username = messageObj.get("netAccount", "")
        password = messageObj.get("netPassword", "")
        wlan_user_ip = messageObj.get("wlanUserIp", "")
        wlan_user_mac = messageObj.get("wlanUserMac", "")
        wlan_ac_ip = messageObj.get("wlanAcIp", "")
        wlan_ac_name = messageObj.get("wlanAcName", "")
        email = messageObj.get("email", "")
        mtype = messageObj.get("type")

        if mtype == 'login':
            op_login(username,password,wlan_user_ip,wlan_user_mac,wlan_ac_ip,wlan_ac_name,email,ws)

        elif mtype == 'logout':
            op_logout(wlan_user_ip,ws,email,username)

        elif mtype =='all':
            op_logout(wlan_user_ip, ws, email, username)
            op_login(username, password, wlan_user_ip, wlan_user_mac, wlan_ac_ip, wlan_ac_name, email, ws)
        else:
            logging.error(f"Received unknown message {message}")

    def on_error(self, ws, error):
        logging.error(f"websocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.warning(f"websocket closed: code={close_status_code}, msg={close_msg}")

    # ===== Connection loop with retry =====
    def build_ws(self) -> websocket.WebSocketApp:
        url = (
            f"ws://{self.server_ip}:9880/usts-campus-services/campus-network-auto-login/"
            "d1e56wf48sfv15489rt4es2dc57svd84f5c1289sfdv4c1s56489rs6f48r6egr489s65rd4f98r64s5vdf845esrd"
        )
        return websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def run(self):
        while True:
            self.ws = self.build_ws()
            logging.info(
                f"starting websocket, consecutive_failures={self.consecutive_failures}, "
                f"max_retries={self.max_retries}"
            )
            try:
                # run_forever 返回后说明连接断开；成功建立连接时 on_open 会把计数清零
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logging.error(f"run_forever exception: {e}")

            # 走到这里代表断开，需要重试
            self.consecutive_failures += 1
            if self.consecutive_failures > self.max_retries:
                logging.error(
                    f"websocket reconnect failed {self.max_retries} times, exiting."
                )
                break

            logging.info(
                f"websocket will retry after {self.retry_delay_sec}s "
                f"(attempt {self.consecutive_failures}/{self.max_retries})"
            )
            time.sleep(self.retry_delay_sec)

def main():
    configs = load_configs("config.json")
    server_ip = configs[0]["serverIp"]
    print(server_ip)

    client = CampusAutoLoginClient(server_ip, max_retries=12, retry_delay_sec=3)
    client.run()

if __name__ == "__main__":
    main()

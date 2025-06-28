import requests
import time
import re
import json
import logging

# 日志配置：追加模式，UTF-8
logging.basicConfig(
    filename='login.log',
    filemode='a',
    format='%(asctime)s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

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
    m = re.match(r"[^(]+\((.*)\)", resp.text)
    if not m:
        raise ValueError("无法解析返回内容为 JSONP")
    return json.loads(m.group(1))

def load_configs(path) -> list:
    """从 JSON 文件读取所有登录配置，返回列表"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]

if __name__ == "__main__":
    configs = load_configs("userInfo.json")
    while True:
        for cfg in configs:
            username     = cfg["username"]
            password     = cfg["password"]
            wlan_user_ip = cfg["wlan_user_ip"]
            wlan_user_mac= cfg["wlan_user_mac"]
            wlan_ac_ip   = cfg["wlan_ac_ip"]
            wlan_ac_name = cfg["wlan_ac_name"]
            try:
                result = login_eportal(
                    username, password,
                    wlan_user_ip, wlan_user_mac,
                    wlan_ac_ip, wlan_ac_name
                )
                if result.get("result") == '1':
                    logging.info(f"{username}：重新登录成功")
                else:
                    print(result)
            except Exception as e:
                logging.error(f"{username}：登录异常——{e}")
            # 每个用户登录后间隔
        # 遍历完所有用户后，可在此处加入更长间隔
        time.sleep(6)

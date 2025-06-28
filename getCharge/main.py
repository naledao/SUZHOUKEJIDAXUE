import json
import requests
import logging
import os
import smtplib
import schedule
import time
from email.mime.text import MIMEText
from email.header import Header

# —— 日志配置 ——
basedir = os.path.dirname(__file__)
logging.basicConfig(
    filename=os.path.join(basedir, "GetDianfei.log"),
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()


# —— 读取 headers.txt ——
def load_headers(path):
    hdr = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, val = line.split(":", 1)
            hdr[key.strip()] = val.strip()
    return hdr


headers = load_headers(os.path.join(basedir, "headers.txt"))
url = "https://wxxyshall.usts.edu.cn/charge/feeitem/getThirdData"


# —— 发送邮件 ——
def send_email(to_addr: str, subject: str, body: str):
    smtp_host = "smtp.qq.com"
    smtp_port = 587
    smtp_user = "3475315488@qq.com"
    smtp_pass = "cizazhqmxtnncjag"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = smtp_user
    msg["To"] = to_addr

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
        server.quit()
        logger.info(f"已发送告警邮件到 {to_addr}")
    except Exception as e:
        logger.error(f"发送邮件到 {to_addr} 失败: {e}")



# —— 主逻辑 ——
def main():
    try:
        with open(os.path.join(basedir, "roomInfo.json"), "r", encoding="utf-8") as f:
            room_list = json.load(f)
    except Exception as e:
        logger.error(f"读取 roomInfo.json 失败: {e}")
        return

    try:
        with open(os.path.join(basedir, "email.json"), "r", encoding="utf-8") as f:
            emailData = json.load(f)
            emailMap = {d["room"]: d["email"] for d in emailData}
    except Exception as e:
        logger.error(f"读取 email.json 失败: {e}")
        return

    for roomInfo in room_list:
        email, master = emailMap[roomInfo['room']].split(",")[:2]
        try:
            resp = requests.post(url, headers=headers, data=roomInfo, timeout=10)
            if resp.status_code != 200:
                send_email(to_addr='2419646091@qq.com', subject='获取电量失败', body='')
            logger.info(f"{roomInfo} → status code：{resp.status_code}")
            data = resp.json()
            leftCharge = float(data['map']['showData']['当前剩余电量'])
            logger.info(f"{master} → {leftCharge:.1f} 度")
            if leftCharge <= float(emailMap['-1']):
                logger.info(f"{roomInfo} → The battery level is below the threshold, send an email to {email}")
                send_email(to_addr=email, subject='寝室电量预警', body=f"您好，{master}\n\n"
                                                                       f"系统检测你的寝室当前剩余电量仅 {leftCharge:.1f} 度，"
                                                                       "请及时充值，以免影响用电。\n\n"
                                                                       "-- 电费监控系统自动通知")
        except ValueError:
            logger.info(f"非 JSON 响应: {resp.text}")
            send_email(to_addr='2419646091@qq.com', subject='获取电量失败', body='')
        except Exception as e:
            logger.error(f"{roomInfo} → request failed: {e}")
            send_email(to_addr='2419646091@qq.com', subject='获取电量失败', body='')


if __name__ == "__main__":
    # 立即执行一次
    main()
    # 每 6 小时调度一次
    schedule.every(6).hours.do(main)
    while True:
        schedule.run_pending()
        time.sleep(1)

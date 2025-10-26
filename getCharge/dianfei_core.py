import json
import os
import re
import requests
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

# —— 固定接口与目录 ——
URL = "https://wxxyshall.usts.edu.cn/charge/feeitem/getThirdData"
BASEDIR = os.path.dirname(__file__)

# —— 日志配置（文件滚动 + 控制台） ——
LOG_PATH = os.path.join(BASEDIR, "GetDianfei.log")
logger = logging.getLogger("dianfei")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)

def _mask(s: str, keep_head: int = 6, keep_tail: int = 4) -> str:
    """打码敏感信息：保留前 keep_head、后 keep_tail，其余用*。"""
    if s is None:
        return ""
    if len(s) <= keep_head + keep_tail:
        return "*" * len(s)
    return s[:keep_head] + "*" * (len(s) - keep_head - keep_tail) + s[-keep_tail:]

def _redact_headers(hdr: Dict[str, str]) -> Dict[str, str]:
    """对可能敏感的头做打码（仅用于日志展示）。"""
    redacted = dict(hdr)
    for key in list(redacted.keys()):
        k_low = key.lower()
        if any(t in k_low for t in ("cookie", "authorization", "token", "auth")):
            redacted[key] = _mask(str(redacted[key]))
    return redacted

def _safe_preview(text: str, n: int = 200) -> str:
    return text if len(text) <= n else (text[:n] + "...(truncated)")

def _load_headers_from_file(path: str) -> dict:
    """从 headers.txt 读取请求头（与原脚本一致），并记录日志。"""
    logger.info(f"读取 headers 文件: {path}")
    hdr = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                logger.warning(f"忽略无效头行: {line!r}")
                continue
            k, v = line.split(":", 1)
            hdr[k.strip()] = v.strip()
    logger.info(f"headers 读取完成，键数量={len(hdr)}，示例={_redact_headers(hdr)}")
    return hdr

def _to_float(val) -> float:
    """将可能带单位/中文的电量值安全转为 float，并记录解析过程。"""
    logger.debug(f"尝试将值解析为 float：{val!r}")
    if isinstance(val, (int, float)):
        fv = float(val)
        logger.info(f"电量数值解析成功（数值型）：{fv}")
        return fv
    if isinstance(val, str):
        s = val.replace(",", "").replace("，", "").strip()
        m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
        if m:
            fv = float(m.group())
            logger.info(f"电量数值解析成功（从字符串 {val!r} 提取）：{fv}")
            return fv
    logger.error(f"电量数值解析失败，原始值：{val!r}")
    raise ValueError(f"无法从值 {val!r} 解析数值为 float")

def _pick_show_value(show: Dict[str, Any]):
    """从 showData 中挑选电量字段，返回(键名, 值)。"""
    candidates = ["当前剩余电量", "剩余电量", "当前剩余电量(kWh)"]
    for k in candidates:
        if k in show:
            logger.info(f"命中预设电量字段：{k} => {show[k]!r}")
            return k, show[k]
    # 模糊匹配
    for k, v in show.items():
        if "剩余" in k or "电量" in k:
            logger.info(f"命中模糊电量字段：{k} => {v!r}")
            return k, v
    return None, None

def query_current_electricity(payload_json: str) -> float:
    """
    仅接收一个 JSON 字符串，返回当前剩余电量（度，float）。
    失败抛出异常（ValueError/KeyError/requests.RequestException）。
    """
    logger.info("开始处理电量查询请求")
    logger.debug(f"原始输入 JSON：{payload_json!r}")

    # 1) 解析与校验输入
    try:
        payload = json.loads(payload_json)
        logger.info(f"输入解析成功：feeitemid={payload.get('feeitemid')}, "
                    f"campus={payload.get('campus')}, building={payload.get('building')}, room={payload.get('room')}")
    except json.JSONDecodeError as e:
        logger.exception("payload_json 不是有效 JSON")
        raise ValueError(f"payload_json 不是有效 JSON：{e}") from e

    required = {"feeitemid", "type", "level", "campus", "building", "room"}
    missing = required - set(payload.keys())
    if missing:
        logger.error(f"缺少必填字段：{', '.join(sorted(missing))}")
        raise KeyError(f"缺少字段：{', '.join(sorted(missing))}")

    # 2) 读取 headers 并请求
    headers_path = os.path.join(BASEDIR, "headers.txt")
    try:
        headers = _load_headers_from_file(headers_path)
    except Exception as e:
        logger.exception("读取 headers.txt 失败")
        raise

    logger.info(f"向接口发起请求：{URL}")
    try:
        resp = requests.post(URL, headers=headers, data=payload, timeout=10)
        logger.info(f"HTTP {resp.status_code}，耗时 {getattr(resp, 'elapsed', None)}")
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("请求接口失败")
        raise

    # 3) 解析返回 JSON，提取电量字段
    try:
        data = resp.json()
        logger.debug(f"接口返回 JSON 预览：{_safe_preview(json.dumps(data, ensure_ascii=False), 300)}")
    except ValueError as e:
        preview = _safe_preview(resp.text, 300)
        logger.error(f"接口返回非 JSON：{preview}")
        raise ValueError(f"接口返回非 JSON：{preview}") from e

    show = data.get("map", {}).get("showData", {})
    if not isinstance(show, dict) or not show:
        logger.error(f"返回 JSON 中 showData 缺失或为空：{show!r}")
        raise KeyError(f"返回 JSON 中找不到 showData，实际：{show!r}")

    key, value = _pick_show_value(show)
    if value is None:
        logger.error(f"返回 JSON 中找不到电量字段，showData keys={list(show.keys())}")
        raise KeyError(f"返回 JSON 中找不到电量字段，showData={show!r}")

    # 4) 统一转为 float 并返回
    result = _to_float(value)
    logger.info(f"电量查询成功：字段={key!r}，数值={result}（度）")
    return result


# —— 示例（需要时自行启用） ——
if __name__ == "__main__":
    j = '{"feeitemid":"409","type":"IEC","level":"3","campus":"2sh","building":"10058","room":"11973"}'
    try:
        val = query_current_electricity(j)
        print(val)
    except Exception as e:
        # 主程也输出一下，便于在控制台立即看到
        logger.exception("电量查询流程发生异常")
        raise

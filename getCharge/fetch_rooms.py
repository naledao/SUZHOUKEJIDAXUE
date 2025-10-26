# filename: fetch_rooms.py
import os, json, time
import requests

URL = "https://wxxyshall.usts.edu.cn/charge/feeitem/getThirdData"
HEADERS_FILE = "headers.txt"            # headers文件（每行 key: value）
CAMPUS_FILE = "campus.json"             # 校区/楼栋清单
OUT_FILE = "rooms_all.json"             # 汇总输出文件

# 自动管理的头，避免与 multipart 冲突
_AUTO_HEADERS = {"host", "connection", "content-length", "content-type"}

def load_headers(path: str) -> dict:
    headers = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k.lower().strip() in _AUTO_HEADERS:
                continue
            headers[k.strip()] = v.strip()
    return headers

def pick_map_data(obj: dict):
    """取 map.data；找不到返回 {}"""
    if not isinstance(obj, dict):
        return {}
    map_obj = obj.get("map") if isinstance(obj.get("map"), dict) else None
    if not map_obj:
        for key in ("data", "result"):
            v = obj.get(key)
            if isinstance(v, dict) and isinstance(v.get("map"), dict):
                map_obj = v["map"]
                break
    if isinstance(map_obj, dict) and "data" in map_obj:
        return map_obj["data"]
    return {}

def iter_rooms(data_field):
    """
    迭代房间项，兼容几种结构：
    - data 为 list[ {value, name, ...}, ... ]
    - data 为 dict，内部有 list/rows/items/data/result 等数组
    - data 本身是 {value, name}
    """
    if isinstance(data_field, list):
        for x in data_field:
            if isinstance(x, dict):
                yield x
        return
    if isinstance(data_field, dict):
        for key in ("list", "rows", "items", "data", "result"):
            arr = data_field.get(key)
            if isinstance(arr, list):
                for x in arr:
                    if isinstance(x, dict):
                        yield x
                return
        if "value" in data_field or "name" in data_field:
            yield data_field

def to_room_record(campus_code, building_code, item: dict):
    """转成目标结构"""
    val = item.get("value")
    name = item.get("name") or item.get("label") or item.get("text") or ""
    return {
        "feeitemid": "409",
        "type": "IEC",
        "level": "3",
        "campus": str(campus_code),
        "building": str(building_code),
        "room": "" if val is None else str(val),
        "name": str(name),
    }

def main():
    headers = load_headers(HEADERS_FILE)
    with open(CAMPUS_FILE, "r", encoding="utf-8") as f:
        campuses = json.load(f)

    session = requests.Session()
    all_rooms = []
    seen = set()  # 去重 key: (campus, building, room)

    for campus in campuses:
        campus_code = str(campus["value"])
        buildings = campus.get("buildings", [])
        for b in buildings:
            building_code = str(b["value"])

            files = {
                "feeitemid": (None, "409"),
                "type": (None, "select"),
                "level": (None, "2"),
                "campus": (None, campus_code),
                "building": (None, building_code),
            }

            try:
                resp = session.post(URL, headers=headers, files=files, timeout=30)
                try:
                    obj = resp.json()
                    data_field = pick_map_data(obj)
                    cnt = 0
                    for item in iter_rooms(data_field):
                        rec = to_room_record(campus_code, building_code, item)
                        key = (rec["campus"], rec["building"], rec["room"])
                        if key in seen:
                            continue
                        seen.add(key)
                        all_rooms.append(rec)
                        cnt += 1
                    print(f"[{resp.status_code}] {campus_code}-{building_code}: +{cnt} rooms (total={len(all_rooms)})")
                except ValueError:
                    print(f"ERROR non-JSON for {campus_code}-{building_code}, status={resp.status_code}")
            except Exception as e:
                print(f"ERROR campus={campus_code} building={building_code}: {e}")

            time.sleep(1.2)  # 轻微限速，避免过快请求

    with open(OUT_FILE, "w", encoding="utf-8") as out:
        json.dump(all_rooms, out, ensure_ascii=False, indent=2)
    print(f"DONE -> {OUT_FILE}  total={len(all_rooms)}")

if __name__ == "__main__":
    main()

# client.py
import json
import dubbo
from dubbo.configs import ReferenceConfig

SERVICE_NAME = "DianFeiService"
URL = f"tri://127.0.0.1:50051/{SERVICE_NAME}"

def _req_ser(s: str) -> bytes:
    return s.encode("utf-8")

def _resp_deser(b: bytes):
    return json.loads(b.decode("utf-8"))

if __name__ == "__main__":
    ref = ReferenceConfig.from_url(URL)
    client = dubbo.Client(ref)

    # 远程方法句柄
    call = client.unary(
        method_name="query_current_electricity",
        request_serializer=_req_ser,
        response_deserializer=_resp_deser,
    )

    # 示例入参（和你本地函数一致）
    payload_json = json.dumps({
        "feeitemid": "409",
        "type": "IEC",
        "level": "3",
        "campus": "2sh",
        "building": "10058",
        "room": "11973"
    }, ensure_ascii=False)

    result = call(payload_json)      # 返回 dict，如 {"value": 12.34}
    print("远程返回：", result)

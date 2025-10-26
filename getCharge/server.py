# server.py
import json
import dubbo
from dubbo.configs import ServiceConfig
from dubbo.proxy.handlers import RpcMethodHandler, RpcServiceHandler

# 复用你的函数
from dianfei_core import query_current_electricity

SERVICE_NAME = "DianFeiService"   # 自定义服务名
HOST = "0.0.0.0"
PORT = 50051

def _req_deser(b: bytes) -> str:
    # 客户端传来的请求：UTF-8 JSON 字符串
    print(b.decode("utf-8"))
    return b.decode("utf-8")

def _resp_ser(obj) -> bytes:
    # 返回 JSON：{"value": float}
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")

def rpc_query(payload_json: str):
    """
    Dubbo 暴露的方法：入参为 JSON 字符串，返回 {"value": float}
    失败抛异常，Dubbo 会在客户端看到错误
    """
    val = query_current_electricity(payload_json)
    return {"value": float(val)}

def build_service_handler():
    method = RpcMethodHandler.unary(
        method=rpc_query,
        method_name="query_current_electricity",
        request_deserializer=_req_deser,
        response_serializer=_resp_ser,
    )
    return RpcServiceHandler(
        service_name=SERVICE_NAME,
        method_handlers=[method],
    )

if __name__ == "__main__":
    service_handler = build_service_handler()
    service_config = ServiceConfig(
        service_handler=service_handler,
        host=HOST,
        port=PORT,          # triple/tri 协议默认
        protocol="tri"  # 显式指定为 Triple 协议
    )
    server = dubbo.Server(service_config).start()
    url = f"{service_config.protocol}://{service_config.host}:{service_config.port}/{SERVICE_NAME}"
    input(url)

# server.py  —— gRPC + Protobuf 版本（不要再用 dubbo-python）
import json
import grpc
from concurrent import futures

import dianfei_pb2
import dianfei_pb2_grpc

# 复用你的函数：入参 JSON 字符串，返回 float
from dianfei_core import query_current_electricity

class DianFeiServiceImpl(dianfei_pb2_grpc.DianFeiServiceServicer):
    def QueryCurrentElectricity(self, request, context):
        # 把 proto 入参组装为你原函数需要的 JSON 字符串
        payload = {
            "campus": request.campus,
            "building": request.building,
            "room": request.room,
            "feeitemid": request.feeitemid,
            "type": request.type,
            "level": request.level,
        }
        payload_json = json.dumps(payload, ensure_ascii=False)

        # 调你的业务，拿 float
        val = float(query_current_electricity(payload_json))

        # 返回 Protobuf 消息，而不是 JSON 字节
        return dianfei_pb2.QueryReply(value=val)


def serve(host: str = "0.0.0.0", port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    dianfei_pb2_grpc.add_DianFeiServiceServicer_to_server(DianFeiServiceImpl(), server)
    server.add_insecure_port(f"{host}:{port}")
    print(f"[gRPC] DianFeiService listening on {host}:{port}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()

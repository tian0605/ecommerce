# 依赖安装：pip install sshtunnel requests paramiko
from sshtunnel import SSHTunnelForwarder
import requests
from typing import Optional, Dict


def get_accurate_1688_weight(item_id: str, ssh_config: Dict, remote_service_port: int = 8080) -> Optional[float]:
    """
    通过SSH隧道调用本地1688服务的local-1688-weight技能获取商品准确重量
    :param item_id: 1688平台商品ID
    :param ssh_config: SSH服务器配置，必填字段：ssh_host、ssh_username；可选字段：ssh_port(默认22)、ssh_password、ssh_pkey
    :param remote_service_port: 远端服务器上1688重量服务监听的本地端口
    :return: 商品重量（单位：克），查询失败返回None
    """
    tunnel_server = None
    try:
        # 建立SSH端口转发隧道
        tunnel_server = SSHTunnelForwarder(
            (ssh_config["ssh_host"], ssh_config.get("ssh_port", 22)),
            ssh_username=ssh_config["ssh_username"],
            ssh_password=ssh_config.get("ssh_password"),
            ssh_pkey=ssh_config.get("ssh_pkey"),
            remote_bind_address=("127.0.0.1", remote_service_port)
        )
        tunnel_server.start()

        # 调用local-1688-weight技能接口
        api_url = f"http://127.0.0.1:{tunnel_server.local_bind_port}/local-1688-weight"
        resp = requests.get(api_url, params={"item_id": item_id}, timeout=15)
        resp.raise_for_status()
        res_data = resp.json()

        if res_data.get("code") == 0 and "weight" in res_data.get("data", {}):
            return float(res_data["data"]["weight"])
        print(f"接口返回异常：{res_data.get('msg', '未知错误')}")
        return None
    except Exception as e:
        print(f"获取1688商品重量失败：{str(e)}")
        return None
    finally:
        # 关闭SSH隧道释放资源
        if tunnel_server and tunnel_server.is_active:
            tunnel_server.stop()


# 测试验证函数
def test_weight_query():
    # 实际使用时替换为真实的SSH配置和商品ID
    test_ssh_conf = {
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数

"""
远程控制系统 - 服务器端
作为控制端和被控端之间的中转桥梁
支持多个被控端和一个控制端同时连接
"""

import socket
import threading
import json
import time
from datetime import datetime

class RemoteControlServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.server_socket = None
        
        # 存储连接的客户端
        self.agents = {}  # {agent_id: {'conn': conn, 'addr': addr, 'info': info}}
        self.controllers = {}  # {controller_id: {'conn': conn, 'addr': addr}} - 支持多个控制端
        
        # 线程锁
        self.lock = threading.Lock()
        
        self.running = True
        
    def start(self):
        """启动服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        print(f"[{self.get_time()}] 服务器启动成功")
        print(f"[{self.get_time()}] 监听地址: {self.host}:{self.port}")
        print("-" * 60)
        
        # 启动心跳检测线程
        threading.Thread(target=self.heartbeat_check, daemon=True).start()
        
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"[{self.get_time()}] 接受连接错误: {e}")
    
    def handle_client(self, conn, addr):
        """处理客户端连接"""
        print(f"[{self.get_time()}] 新连接来自: {addr}")
        
        try:
            # 接收第一条消息以识别客户端类型
            data = self.recv_json(conn)
            if not data:
                conn.close()
                return
            
            client_type = data.get('type')
            
            if client_type == 'agent':
                self.handle_agent(conn, addr, data)
            elif client_type == 'controller':
                self.handle_controller(conn, addr)
            else:
                print(f"[{self.get_time()}] 未知客户端类型: {client_type}")
                conn.close()
                
        except Exception as e:
            print(f"[{self.get_time()}] 处理客户端错误: {e}")
            conn.close()
    
    def handle_agent(self, conn, addr, data):
        """处理被控端连接"""
        agent_id = data.get('agent_id', f"{addr[0]}:{addr[1]}")
        agent_info = data.get('info', {})
        
        with self.lock:
            self.agents[agent_id] = {
                'conn': conn,
                'addr': addr,
                'info': agent_info,
                'last_heartbeat': time.time()
            }
        
        print(f"[{self.get_time()}] 被控端上线: {agent_id}")
        print(f"  - 主机名: {agent_info.get('hostname', 'Unknown')}")
        print(f"  - 系统: {agent_info.get('platform', 'Unknown')}")
        print(f"  - IP: {agent_info.get('ip', 'Unknown')}")
        
        # 通知控制端更新主机列表
        self.notify_controller_host_list()
        
        # 接收被控端消息
        while self.running:
            try:
                msg = self.recv_json(conn)
                if not msg:
                    break
                
                # 更新心跳时间
                if msg.get('action') == 'heartbeat':
                    with self.lock:
                        if agent_id in self.agents:
                            self.agents[agent_id]['last_heartbeat'] = time.time()
                    continue
                
                # 转发消息给所有控制端
                msg['agent_id'] = agent_id
                with self.lock:
                    dead_controllers = []
                    for controller_id, controller_data in self.controllers.items():
                        try:
                            self.send_json(controller_data['conn'], msg)
                        except:
                            dead_controllers.append(controller_id)

                    # 清理失败的控制端
                    for controller_id in dead_controllers:
                        if controller_id in self.controllers:
                            del self.controllers[controller_id]
                    
            except Exception as e:
                print(f"[{self.get_time()}] 被控端 {agent_id} 错误: {e}")
                break
        
        # 清理断开的被控端
        with self.lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
        
        print(f"[{self.get_time()}] 被控端下线: {agent_id}")
        conn.close()
        
        # 通知控制端更新主机列表
        self.notify_controller_host_list()
    
    def handle_controller(self, conn, addr):
        """处理控制端连接 - 支持多个控制端"""
        controller_id = f"{addr[0]}:{addr[1]}"
        print(f"[{self.get_time()}] 控制端连接: {addr} (ID: {controller_id})")

        # 设置socket超时
        conn.settimeout(60)  # 60秒超时

        with self.lock:
            self.controllers[controller_id] = {
                'conn': conn,
                'addr': addr,
                'last_active': time.time()
            }

        print(f"[{self.get_time()}] 当前控制端数量: {len(self.controllers)}")

        # 发送当前在线主机列表
        self.notify_controller_host_list(conn)

        # 接收控制端命令
        while self.running:
            try:
                msg = self.recv_json(conn)
                if not msg:
                    break

                # 更新活跃时间
                with self.lock:
                    if controller_id in self.controllers:
                        self.controllers[controller_id]['last_active'] = time.time()

                action = msg.get('action')

                if action == 'register':
                    # 控制端注册，发送主机列表
                    print(f"[{self.get_time()}] 控制端 {controller_id} 注册成功")
                    self.notify_controller_host_list(conn)

                elif action == 'list_hosts':
                    # 返回主机列表
                    self.notify_controller_host_list(conn)

                elif action in ['screenshot', 'start_video', 'stop_video', 'run_command',
                               'mouse_move', 'mouse_click', 'mouse_scroll',
                               'keyboard_press', 'keyboard_type',
                               'get_drives', 'list_files', 'open_file', 'download_file', 'upload_file',
                               'delete_file', 'create_folder']:
                    # 转发命令给指定的被控端
                    targets = msg.get('targets', [])
                    for target in targets:
                        with self.lock:
                            if target in self.agents:
                                agent_conn = self.agents[target]['conn']
                                self.send_json(agent_conn, msg)
                            else:
                                # 通知控制端目标不存在
                                self.send_json(conn, {
                                    'type': 'error',
                                    'message': f'目标 {target} 不在线'
                                })

            except socket.timeout:
                # 超时，发送心跳检测
                try:
                    self.send_json(conn, {'type': 'ping'})
                except:
                    print(f"[{self.get_time()}] 控制端 {controller_id} 心跳失败")
                    break
            except Exception as e:
                print(f"[{self.get_time()}] 控制端 {controller_id} 错误: {e}")
                break

        print(f"[{self.get_time()}] 控制端断开: {addr} (ID: {controller_id})")
        with self.lock:
            if controller_id in self.controllers:
                del self.controllers[controller_id]
        print(f"[{self.get_time()}] 剩余控制端数量: {len(self.controllers)}")
        conn.close()
    
    def notify_controller_host_list(self, target_conn=None):
        """通知控制端更新主机列表

        Args:
            target_conn: 指定的控制端连接，如果为None则通知所有控制端
        """
        with self.lock:
            hosts = []
            for agent_id, agent_data in self.agents.items():
                info = agent_data['info']
                hosts.append({
                    'id': agent_id,
                    'hostname': info.get('hostname', 'Unknown'),
                    'ip': info.get('ip', 'Unknown'),
                    'platform': info.get('platform', 'Unknown'),
                    'custom_name': info.get('custom_name', '')
                })

            message = {
                'type': 'host_list',
                'hosts': hosts
            }

            # 如果指定了目标连接，只发送给该连接
            if target_conn:
                try:
                    self.send_json(target_conn, message)
                except:
                    pass
            else:
                # 否则发送给所有控制端
                dead_controllers = []
                for controller_id, controller_data in self.controllers.items():
                    try:
                        self.send_json(controller_data['conn'], message)
                    except:
                        dead_controllers.append(controller_id)

                # 清理失败的控制端
                for controller_id in dead_controllers:
                    if controller_id in self.controllers:
                        del self.controllers[controller_id]
    
    def heartbeat_check(self):
        """心跳检测，清理超时的被控端"""
        while self.running:
            time.sleep(30)  # 每30秒检查一次
            
            timeout = 60  # 60秒超时
            current_time = time.time()
            
            with self.lock:
                disconnected = []
                for agent_id, agent_data in self.agents.items():
                    if current_time - agent_data['last_heartbeat'] > timeout:
                        disconnected.append(agent_id)
                
                for agent_id in disconnected:
                    print(f"[{self.get_time()}] 被控端超时: {agent_id}")
                    try:
                        self.agents[agent_id]['conn'].close()
                    except:
                        pass
                    del self.agents[agent_id]
            
            if disconnected:
                self.notify_controller_host_list()
    
    def send_json(self, conn, data):
        """发送JSON数据"""
        try:
            msg = json.dumps(data).encode('utf-8')
            length = len(msg)
            conn.sendall(length.to_bytes(4, 'big') + msg)
            return True
        except Exception as e:
            print(f"[{self.get_time()}] 发送数据错误: {e}")
            return False
    
    def recv_json(self, conn):
        """接收JSON数据"""
        try:
            # 接收长度
            raw_len = conn.recv(4)
            if not raw_len or len(raw_len) < 4:
                return None
            
            msg_len = int.from_bytes(raw_len, 'big')
            
            # 接收数据
            msg = b''
            while len(msg) < msg_len:
                chunk = conn.recv(min(msg_len - len(msg), 4096))
                if not chunk:
                    return None
                msg += chunk
            
            return json.loads(msg.decode('utf-8'))
        except Exception as e:
            return None
    
    def get_time(self):
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def stop(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

if __name__ == '__main__':
    print("=" * 60)
    print("远程控制系统 - 服务器端")
    print("=" * 60)
    
    server = RemoteControlServer(host='0.0.0.0', port=5000)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print(f"\n[{server.get_time()}] 服务器关闭")
        server.stop()


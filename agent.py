"""
远程控制系统 - 被控端
安装在被控制的Windows电脑上
支持截图、视频流、命令执行、鼠标键盘控制等功能
"""

import socket
import threading
import json
import time
import platform
import subprocess
import base64
import io
import os
import sys
from datetime import datetime

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: PIL/Pillow未安装，截图功能将不可用")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # 禁用安全功能，允许快速移动鼠标
    pyautogui.FAILSAFE = False
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("警告: pyautogui未安装，鼠标键盘控制将不可用")

try:
    from pynput.keyboard import Controller as KeyboardController, Key
    from pynput.mouse import Controller as MouseController, Button
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("警告: pynput未安装，部分控制功能将不可用")

class RemoteAgent:
    def __init__(self, server_ip, server_port=5000, agent_id=None, custom_name=None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.agent_id = agent_id or self.get_default_id()
        self.custom_name = custom_name  # 自定义主机名

        self.sock = None
        self.running = True
        self.video_streaming = False
        self.video_quality = 'medium'  # 视频质量: low, medium, high, ultra

        # 鼠标键盘控制器
        if PYNPUT_AVAILABLE:
            self.mouse = MouseController()
            self.keyboard = KeyboardController()

        # 获取系统信息
        self.system_info = self.get_system_info()
        
    def get_default_id(self):
        """生成默认的agent ID（不带时间戳，使用主机名+IP）"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            # 使用主机名+IP最后一段作为唯一标识
            ip_suffix = ip.split('.')[-1]
            return f"{hostname}_{ip_suffix}"
        except:
            # 如果获取失败，使用随机数
            import random
            return f"agent_{random.randint(1000, 9999)}"
    
    def get_system_info(self):
        """获取系统信息"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except:
            hostname = "Unknown"
            ip = "Unknown"

        return {
            'hostname': hostname,
            'custom_name': self.custom_name or hostname,  # 使用自定义名称或主机名
            'ip': ip,
            'platform': platform.platform(),
            'system': platform.system(),
            'processor': platform.processor()
        }
    
    def connect(self):
        """连接到服务器"""
        while self.running:
            try:
                print(f"[{self.get_time()}] 正在连接服务器 {self.server_ip}:{self.server_port}...")
                
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.server_ip, self.server_port))
                
                # 发送注册信息
                self.send_json({
                    'type': 'agent',
                    'agent_id': self.agent_id,
                    'info': self.system_info
                })
                
                print(f"[{self.get_time()}] 连接成功! Agent ID: {self.agent_id}")
                
                # 启动心跳线程
                threading.Thread(target=self.heartbeat, daemon=True).start()
                
                # 接收命令
                self.receive_commands()
                
            except Exception as e:
                print(f"[{self.get_time()}] 连接错误: {e}")
                if self.sock:
                    self.sock.close()
                
                if self.running:
                    print(f"[{self.get_time()}] 5秒后重新连接...")
                    time.sleep(5)
    
    def heartbeat(self):
        """发送心跳包"""
        while self.running:
            try:
                time.sleep(20)  # 每20秒发送一次心跳
                self.send_json({'action': 'heartbeat'})
            except:
                break
    
    def receive_commands(self):
        """接收并处理命令"""
        while self.running:
            try:
                data = self.recv_json()
                if not data:
                    break

                action = data.get('action')

                if action == 'screenshot':
                    threading.Thread(target=self.handle_screenshot, daemon=True).start()

                elif action == 'start_video':
                    quality = data.get('quality', 'medium')
                    self.video_quality = quality
                    self.video_streaming = True
                    threading.Thread(target=self.handle_video_stream, daemon=True).start()

                elif action == 'stop_video':
                    self.video_streaming = False

                elif action == 'run_command':
                    command = data.get('command', '')
                    as_admin = data.get('as_admin', False)
                    threading.Thread(target=self.handle_command, args=(command, as_admin), daemon=True).start()

                # 鼠标键盘控制
                elif action == 'mouse_move':
                    x = data.get('x', 0)
                    y = data.get('y', 0)
                    self.handle_mouse_move(x, y)

                elif action == 'mouse_click':
                    button = data.get('button', 'left')
                    clicks = data.get('clicks', 1)
                    x = data.get('x', None)
                    y = data.get('y', None)
                    self.handle_mouse_click(button, clicks, x, y)

                elif action == 'mouse_scroll':
                    dx = data.get('dx', 0)
                    dy = data.get('dy', 0)
                    self.handle_mouse_scroll(dx, dy)

                elif action == 'keyboard_press':
                    key = data.get('key', '')
                    self.handle_keyboard_press(key)

                elif action == 'keyboard_type':
                    text = data.get('text', '')
                    self.handle_keyboard_type(text)

                # 文件操作
                elif action == 'get_drives':
                    # 获取所有磁盘驱动器
                    self.handle_get_drives()

                elif action == 'list_files':
                    path = data.get('path', 'C:\\')
                    self.handle_list_files(path)

                elif action == 'open_file':
                    filepath = data.get('filepath', '')
                    self.handle_open_file(filepath)

                elif action == 'download_file':
                    filepath = data.get('filepath', '')
                    self.handle_download_file(filepath)

                elif action == 'upload_file':
                    filepath = data.get('filepath', '')
                    content = data.get('content', '')
                    self.handle_upload_file(filepath, content)

                elif action == 'delete_file':
                    filepath = data.get('filepath', '')
                    self.handle_delete_file(filepath)

                elif action == 'create_folder':
                    folderpath = data.get('folderpath', '')
                    self.handle_create_folder(folderpath)

            except Exception as e:
                print(f"[{self.get_time()}] 接收命令错误: {e}")
                break
    
    def handle_screenshot(self):
        """处理截图请求"""
        if not PIL_AVAILABLE:
            self.send_json({
                'type': 'error',
                'message': 'PIL/Pillow未安装，无法截图'
            })
            return
        
        try:
            print(f"[{self.get_time()}] 正在截图...")
            
            # 截取屏幕
            screenshot = ImageGrab.grab()
            
            # 调整大小以减少传输数据量
            screenshot.thumbnail((1280, 720))
            
            # 转换为JPEG格式
            buffer = io.BytesIO()
            screenshot.save(buffer, format='JPEG', quality=85)
            img_data = buffer.getvalue()
            
            # Base64编码
            img_b64 = base64.b64encode(img_data).decode('utf-8')
            
            # 发送截图
            self.send_json({
                'type': 'screenshot',
                'image': img_b64
            })
            
            print(f"[{self.get_time()}] 截图已发送 ({len(img_data)} bytes)")
            
        except Exception as e:
            print(f"[{self.get_time()}] 截图错误: {e}")
            self.send_json({
                'type': 'error',
                'message': f'截图失败: {str(e)}'
            })
    
    def handle_video_stream(self):
        """处理视频流 - 支持多种质量"""
        if not PIL_AVAILABLE:
            self.send_json({
                'type': 'error',
                'message': 'PIL/Pillow未安装，无法视频流'
            })
            return

        # 根据质量设置参数
        quality_settings = {
            'low': {'size': (640, 480), 'quality': 50, 'fps': 5},
            'medium': {'size': (800, 600), 'quality': 70, 'fps': 10},
            'high': {'size': (1280, 720), 'quality': 85, 'fps': 15},
            'ultra': {'size': (1920, 1080), 'quality': 90, 'fps': 20}  # 90%无损画质
        }

        settings = quality_settings.get(self.video_quality, quality_settings['medium'])
        print(f"[{self.get_time()}] 开始视频流 (质量: {self.video_quality})...")

        frame_count = 0
        while self.running and self.video_streaming:
            try:
                # 截取屏幕
                screenshot = ImageGrab.grab()

                # 调整大小
                screenshot.thumbnail(settings['size'])

                # 转换为JPEG
                buffer = io.BytesIO()
                screenshot.save(buffer, format='JPEG', quality=settings['quality'])
                img_data = buffer.getvalue()
                
                # Base64编码
                img_b64 = base64.b64encode(img_data).decode('utf-8')
                
                # 发送帧
                self.send_json({
                    'type': 'video_frame',
                    'image': img_b64,
                    'frame': frame_count
                })
                
                frame_count += 1

                # 控制帧率
                time.sleep(1.0 / settings['fps'])
                
            except Exception as e:
                print(f"[{self.get_time()}] 视频流错误: {e}")
                break
        
        print(f"[{self.get_time()}] 视频流已停止")
    
    def handle_command(self, command, as_admin=False):
        """处理命令执行 - 支持管理员权限"""
        print(f"[{self.get_time()}] 执行命令: {command} (管理员: {as_admin})")
        
        try:
            # 如果需要管理员权限
            if as_admin and platform.system() == 'Windows':
                # 使用PowerShell以管理员权限运行
                ps_command = f'Start-Process -Verb RunAs -FilePath cmd.exe -ArgumentList "/c {command}" -Wait -WindowStyle Hidden'
                result = subprocess.run(['powershell', '-Command', ps_command],
                                      capture_output=True,
                                      text=True,
                                      timeout=60,
                                      encoding='gbk',
                                      errors='ignore')
            # 检查是否是脚本文件
            elif command.endswith('.bat') or command.endswith('.ps1') or command.endswith('.py'):
                if os.path.exists(command):
                    # 执行脚本文件
                    if command.endswith('.bat'):
                        cmd_list = ['cmd', '/c', command]
                        if as_admin:
                            cmd_list = ['powershell', '-Command', f'Start-Process -Verb RunAs -FilePath cmd.exe -ArgumentList "/c {command}" -Wait']
                        result = subprocess.run(cmd_list,
                                              capture_output=True,
                                              text=True,
                                              timeout=60,
                                              encoding='gbk',
                                              errors='ignore')
                    elif command.endswith('.ps1'):
                        cmd_list = ['powershell', '-File', command]
                        if as_admin:
                            cmd_list = ['powershell', '-Command', f'Start-Process -Verb RunAs -FilePath powershell.exe -ArgumentList "-File {command}" -Wait']
                        result = subprocess.run(cmd_list,
                                              capture_output=True,
                                              text=True,
                                              timeout=60,
                                              encoding='gbk',
                                              errors='ignore')
                    elif command.endswith('.py'):
                        cmd_list = ['python', command]
                        if as_admin:
                            cmd_list = ['powershell', '-Command', f'Start-Process -Verb RunAs -FilePath python.exe -ArgumentList "{command}" -Wait']
                        result = subprocess.run(cmd_list,
                                              capture_output=True,
                                              text=True,
                                              timeout=60,
                                              encoding='gbk',
                                              errors='ignore')
                else:
                    output = f"错误: 文件不存在 - {command}"
                    self.send_json({
                        'type': 'command_result',
                        'command': command,
                        'output': output
                    })
                    return
            else:
                # 执行普通命令
                result = subprocess.run(command,
                                      shell=True,
                                      capture_output=True,
                                      text=True,
                                      timeout=60,
                                      encoding='gbk',
                                      errors='ignore')
            
            output = result.stdout + result.stderr
            if not output:
                output = "命令执行完成 (无输出)"
            
            self.send_json({
                'type': 'command_result',
                'command': command,
                'output': output,
                'returncode': result.returncode
            })
            
            print(f"[{self.get_time()}] 命令执行完成")
            
        except subprocess.TimeoutExpired:
            output = "错误: 命令执行超时 (30秒)"
            self.send_json({
                'type': 'command_result',
                'command': command,
                'output': output
            })
        except Exception as e:
            output = f"错误: {str(e)}"
            self.send_json({
                'type': 'command_result',
                'command': command,
                'output': output
            })

    def handle_mouse_move(self, x, y):
        """处理鼠标移动"""
        if not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.moveTo(x, y, duration=0)
            print(f"[{self.get_time()}] 鼠标移动到: ({x}, {y})")
        except Exception as e:
            print(f"[{self.get_time()}] 鼠标移动错误: {e}")

    def handle_mouse_click(self, button='left', clicks=1, x=None, y=None):
        """处理鼠标点击"""
        if not PYAUTOGUI_AVAILABLE:
            return
        try:
            # 如果提供了坐标，先移动到该位置
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0)
                time.sleep(0.05)  # 短暂延迟确保移动完成

            pyautogui.click(button=button, clicks=clicks)
            print(f"[{self.get_time()}] 鼠标点击: {button} at ({x}, {y})")
        except Exception as e:
            print(f"[{self.get_time()}] 鼠标点击错误: {e}")

    def handle_mouse_scroll(self, dx, dy):
        """处理鼠标滚轮"""
        if not PYAUTOGUI_AVAILABLE:
            return
        try:
            if dy != 0:
                pyautogui.scroll(dy)
        except Exception as e:
            print(f"[{self.get_time()}] 鼠标滚轮错误: {e}")

    def handle_keyboard_press(self, key):
        """处理键盘按键"""
        if not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press(key)
        except Exception as e:
            print(f"[{self.get_time()}] 键盘按键错误: {e}")

    def handle_keyboard_type(self, text):
        """处理键盘输入"""
        if not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.write(text, interval=0.05)
        except Exception as e:
            print(f"[{self.get_time()}] 键盘输入错误: {e}")

    def send_json(self, data):
        """发送JSON数据"""
        try:
            msg = json.dumps(data).encode('utf-8')
            length = len(msg)
            self.sock.sendall(length.to_bytes(4, 'big') + msg)
            return True
        except Exception as e:
            return False
    
    def recv_json(self):
        """接收JSON数据"""
        try:
            # 接收长度
            raw_len = self.sock.recv(4)
            if not raw_len or len(raw_len) < 4:
                return None
            
            msg_len = int.from_bytes(raw_len, 'big')
            
            # 接收数据
            msg = b''
            while len(msg) < msg_len:
                chunk = self.sock.recv(min(msg_len - len(msg), 4096))
                if not chunk:
                    return None
                msg += chunk
            
            return json.loads(msg.decode('utf-8'))
        except Exception as e:
            return None
    
    def get_time(self):
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def handle_get_drives(self):
        """获取所有磁盘驱动器"""
        try:
            import string
            drives = []

            # Windows系统获取所有驱动器
            if os.name == 'nt':
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        try:
                            # 获取驱动器信息
                            total, used, free = 0, 0, 0
                            try:
                                import shutil
                                stat = shutil.disk_usage(drive)
                                total = stat.total
                                used = stat.used
                                free = stat.free
                            except:
                                pass

                            # 获取驱动器类型
                            drive_type = "本地磁盘"
                            try:
                                import win32api
                                dtype = win32api.GetDriveType(drive)
                                if dtype == 2:
                                    drive_type = "可移动磁盘"
                                elif dtype == 3:
                                    drive_type = "本地磁盘"
                                elif dtype == 4:
                                    drive_type = "网络驱动器"
                                elif dtype == 5:
                                    drive_type = "光盘驱动器"
                            except:
                                pass

                            drives.append({
                                'name': letter,
                                'path': drive,
                                'type': drive_type,
                                'total': total,
                                'used': used,
                                'free': free
                            })
                        except:
                            pass
            else:
                # Linux/Mac系统
                drives.append({
                    'name': 'root',
                    'path': '/',
                    'type': '根目录',
                    'total': 0,
                    'used': 0,
                    'free': 0
                })

            print(f"[{self.get_time()}] 获取到 {len(drives)} 个驱动器")
            self.send_json({'type': 'drives_list', 'drives': drives})
        except Exception as e:
            print(f"[{self.get_time()}] 获取驱动器错误: {e}")
            self.send_json({'type': 'drives_list', 'error': str(e)})

    def handle_list_files(self, path):
        """列出目录文件"""
        try:
            print(f"[{self.get_time()}] 列出目录: {path}")

            if not os.path.exists(path):
                self.send_json({'type': 'file_list', 'path': path, 'error': '路径不存在'})
                return

            files, folders = [], []

            # 如果不是根目录，添加上级目录
            if path != os.path.dirname(path):
                folders.append({'name': '..', 'type': 'folder', 'size': 0})

            # 列出文件和文件夹
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                try:
                    if os.path.isdir(item_path):
                        folders.append({'name': item, 'type': 'folder', 'size': 0})
                    else:
                        files.append({'name': item, 'type': 'file', 'size': os.path.getsize(item_path)})
                except:
                    pass

            self.send_json({'type': 'file_list', 'path': path, 'items': folders + files})
        except Exception as e:
            self.send_json({'type': 'file_list', 'path': path, 'error': str(e)})

    def handle_open_file(self, filepath):
        """打开查看文件"""
        try:
            print(f"[{self.get_time()}] 打开文件: {filepath}")

            if not os.path.exists(filepath):
                self.send_json({'type': 'file_open', 'filepath': filepath, 'error': '文件不存在'})
                return

            if os.path.isdir(filepath):
                self.send_json({'type': 'file_open', 'filepath': filepath, 'error': '不能打开文件夹'})
                return

            # 检查文件大小
            file_size = os.path.getsize(filepath)
            max_size = 10 * 1024 * 1024  # 10MB
            if file_size > max_size:
                self.send_json({'type': 'file_open', 'filepath': filepath, 'error': f'文件过大 ({file_size} bytes)，超过10MB限制'})
                return

            with open(filepath, 'rb') as f:
                content_b64 = base64.b64encode(f.read()).decode('utf-8')

            print(f"[{self.get_time()}] 文件已编码，大小: {len(content_b64)} bytes")
            self.send_json({'type': 'file_open', 'filepath': filepath, 'filename': os.path.basename(filepath), 'content': content_b64})
        except Exception as e:
            print(f"[{self.get_time()}] 打开文件错误: {e}")
            self.send_json({'type': 'file_open', 'filepath': filepath, 'error': str(e)})

    def handle_download_file(self, filepath):
        """下载文件"""
        try:
            print(f"[{self.get_time()}] 下载文件: {filepath}")

            if not os.path.exists(filepath):
                self.send_json({'type': 'file_download', 'filepath': filepath, 'error': '文件不存在'})
                return

            if os.path.isdir(filepath):
                self.send_json({'type': 'file_download', 'filepath': filepath, 'error': '不能下载文件夹'})
                return

            with open(filepath, 'rb') as f:
                content_b64 = base64.b64encode(f.read()).decode('utf-8')

            print(f"[{self.get_time()}] 文件已编码，大小: {len(content_b64)} bytes")
            self.send_json({'type': 'file_download', 'filepath': filepath, 'filename': os.path.basename(filepath), 'content': content_b64})
        except Exception as e:
            print(f"[{self.get_time()}] 下载文件错误: {e}")
            self.send_json({'type': 'file_download', 'filepath': filepath, 'error': str(e)})

    def handle_upload_file(self, filepath, content_b64):
        """上传文件"""
        try:
            print(f"[{self.get_time()}] 上传文件: {filepath}")

            # 确保目录存在
            dir_path = os.path.dirname(filepath)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            with open(filepath, 'wb') as f:
                f.write(base64.b64decode(content_b64))

            print(f"[{self.get_time()}] 文件上传成功: {filepath}")
            self.send_json({'type': 'file_upload', 'filepath': filepath, 'success': True})
        except Exception as e:
            print(f"[{self.get_time()}] 上传文件错误: {e}")
            self.send_json({'type': 'file_upload', 'filepath': filepath, 'error': str(e)})

    def handle_delete_file(self, filepath):
        """删除文件或文件夹"""
        try:
            print(f"[{self.get_time()}] 删除: {filepath}")

            if not os.path.exists(filepath):
                self.send_json({'type': 'file_delete', 'filepath': filepath, 'error': '文件或文件夹不存在'})
                return

            if os.path.isdir(filepath):
                # 删除文件夹及其所有内容
                import shutil
                shutil.rmtree(filepath)
                print(f"[{self.get_time()}] 已删除文件夹: {filepath}")
            else:
                # 删除文件
                os.remove(filepath)
                print(f"[{self.get_time()}] 已删除文件: {filepath}")

            self.send_json({'type': 'file_delete', 'filepath': filepath, 'success': True})
        except Exception as e:
            print(f"[{self.get_time()}] 删除错误: {e}")
            self.send_json({'type': 'file_delete', 'filepath': filepath, 'error': str(e)})

    def handle_create_folder(self, folderpath):
        """创建文件夹"""
        try:
            print(f"[{self.get_time()}] 创建文件夹: {folderpath}")

            if os.path.exists(folderpath):
                self.send_json({'type': 'folder_create', 'folderpath': folderpath, 'error': '文件夹已存在'})
                return

            os.makedirs(folderpath, exist_ok=True)
            print(f"[{self.get_time()}] 文件夹创建成功: {folderpath}")
            self.send_json({'type': 'folder_create', 'folderpath': folderpath, 'success': True})
        except Exception as e:
            print(f"[{self.get_time()}] 创建文件夹错误: {e}")
            self.send_json({'type': 'folder_create', 'folderpath': folderpath, 'error': str(e)})

    def stop(self):
        """停止agent"""
        self.running = False
        self.video_streaming = False
        if self.sock:
            self.sock.close()

if __name__ == '__main__':
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='远程控制系统 - 被控端')
    parser.add_argument('--server', type=str, default=None, help='服务器IP地址')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口')
    parser.add_argument('--name', type=str, default=None, help='自定义主机名')
    parser.add_argument('--config', type=str, default='agent_config.ini', help='配置文件路径')
    parser.add_argument('--silent', action='store_true', help='静默模式（无输出）')
    args = parser.parse_args()

    # 读取配置文件
    SERVER_IP = None
    SERVER_PORT = 5000
    CUSTOM_NAME = None

    if os.path.exists(args.config):
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(args.config, encoding='utf-8')
            if 'Server' in config:
                SERVER_IP = config['Server'].get('ip', None)
                SERVER_PORT = config['Server'].getint('port', 5000)
            if 'Agent' in config:
                CUSTOM_NAME = config['Agent'].get('name', None)
        except Exception as e:
            if not args.silent:
                print(f"读取配置文件失败: {e}")

    # 命令行参数优先级最高
    if args.server:
        SERVER_IP = args.server
    if args.port:
        SERVER_PORT = args.port
    if args.name:
        CUSTOM_NAME = args.name

    # 如果没有配置且不是静默模式，则交互式输入
    if not SERVER_IP and not args.silent:
        try:
            print("=" * 60)
            print("远程控制系统 - 被控端 (增强版)")
            print("=" * 60)
            SERVER_IP = input("请输入服务器IP地址 (默认: 127.0.0.1): ").strip() or '127.0.0.1'
            CUSTOM_NAME = input("请输入自定义主机名 (可选，直接回车跳过): ").strip() or None
        except:
            # 如果input失败（比如没有stdin），使用默认值
            SERVER_IP = '127.0.0.1'

    # 使用默认值
    if not SERVER_IP:
        SERVER_IP = '127.0.0.1'

    # 静默模式下禁用所有print
    if args.silent:
        import sys
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    agent = RemoteAgent(SERVER_IP, SERVER_PORT, custom_name=CUSTOM_NAME)

    try:
        agent.connect()
    except KeyboardInterrupt:
        if not args.silent:
            print(f"\n[{agent.get_time()}] 被控端关闭")
        agent.stop()


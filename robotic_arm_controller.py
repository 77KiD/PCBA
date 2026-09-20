"""
機械手臂控制器 - USB
透過串口與Arduino Nano通訊控制六軸機械手臂
支援三分類：單一缺陷、兩種缺陷、多種缺陷
"""

import serial
import serial.tools.list_ports
import time
import json
from dataclasses import dataclass
from typing import Optional, List, Dict
import threading




@dataclass
class Position:
    """機械手臂位置數據類（完整、正確）"""
    joint1: float = 180.0
    joint2: float = 180.0
    joint3: float = 90.0
    joint4: float = 90.0
    joint5: float = 90.0
    joint6: float = 73.0

    def to_list(self) -> List[float]:
        """轉換成 6 關節列表"""
        return [
            self.joint1,
            self.joint2,
            self.joint3,
            self.joint4,
            self.joint5,
            self.joint6,
        ]

    @classmethod
    def from_list(cls, angles: List[float]) -> 'Position':
        """
        與舊版本相容：
        - 若 angles > 6：取前 6 個（避免 14 個參數噴錯）
        - 若 angles < 6：用預設值補齊
        """
        if angles is None:
            return cls()

        vals = list(angles)

        if len(vals) > 6:
            print(f"⚠️ 位置資料含 {len(vals)} 個值，只取前 6 個")
            vals = vals[:6]

        while len(vals) < 6:
            if len(vals) <= 1:
                vals.append(180.0)
            else:
                vals.append(90.0)

        return cls(*vals)

    def __str__(self):
        return "Position(" + ", ".join(f"{a:.1f}°" for a in self.to_list()) + ")"


class RoboticArmController:
    """機械手臂控制器 - USB"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, port: str = 'COM8', baudrate: int = 115200):
        """單例模式：確保只創建一個實例"""
        if cls._instance is None:
            cls._instance = super(RoboticArmController, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, port: str = 'COM8', baudrate: int = 115200):
        """
        初始化機械手臂控制器
        
        Args:
            port: 串口名稱，預設為 COM8
            baudrate: 波特率，預設115200
        """
        # 如果已經初始化過，直接返回
        if self._initialized:
            return
            
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected = False
        self.is_moving = False
        self.emergency_stopped = False
        
        # 當前位置
        self.current_position = Position()
        
        # 預定義位置 
        self.predefined_positions = {
            'home': Position(0, 180, 90, 90, 90, 73),
            'safe_high': Position(0, 120, 60, 105, 90, 30),
            'check': Position(90, 60, 30, 90, 90, 30),
            'rest': Position(90, 120, 60, 90, 90, 73),
            
            #  三分類區域 (需根據實際硬體調整) 
            # 夾取相關位置（自動序列使用）
            '夾取預設位置': Position(0, 66, 57, 90, 0, 73),
            '夾取': Position(0, 66, 57, 90, 0, 58),
            '夾取後通用移動': Position(0, 90, 57, 90, 0, 58),

            '夾取後到分類一區之路徑一': Position(105, 90, 57, 90, 0, 58),
            '夾取後到分類一區之路徑二': Position(105, 39, 27, 84, 0, 58),
            '夾取後到分類一區之路徑三放開': Position(105, 39, 27, 84, 0, 73),
            '分類一區之回歸路徑': Position(105, 90, 57, 90, 0, 73),

            '夾取後到分類二區之路徑一': Position(145, 90, 57, 90, 0, 58),
            '夾取後到分類二區之路徑二': Position(145, 39, 42, 105, 0, 58),
            '夾取後到分類二區之路徑三放開': Position(145, 39, 42, 105, 0, 73),
            '分類二區之回歸路徑': Position(145, 90, 57, 90, 0, 58),

            '夾取後到分類三區之路徑一': Position(180, 90, 57, 90, 180, 58),
            '夾取後到分類三區之路徑二': Position(180, 39, 42, 105, 180, 58),
            '夾取後到分類三區之路徑三放開': Position(180, 39, 42, 105, 180, 73),
            '分類三區之回歸路徑': Position(180, 90, 57, 90, 180, 73),

        }
        
        # 關節信息
        self.joint_info = {
            'joint1': {'name': '基座旋轉', 'min': 0, 'max': 180, 'channel': 4},
            'joint2': {'name': '肩部俯仰', 'min': 0, 'max': 180, 'channel': 5},
            'joint3': {'name': '手肘彎曲', 'min': 0, 'max': 180, 'channel': 6},
            'joint4': {'name': '腕部俯仰', 'min': 0, 'max': 180, 'channel': 7},
            'joint5': {'name': '腕部旋轉', 'min': 0, 'max': 180, 'channel': 8},
            'joint6': {'name': '夾爪', 'min': 30, 'max': 73, 'channel': 9},
        }
        
        # 連接鎖
        self.lock = threading.Lock()
        
        # 標記為已初始化
        self._initialized = True
        
        # 自動連接
        self.connect()
        # 自訂路徑序列（從 sequences.json 讀取）
        self.sequences: Dict[str, List[Dict]] = {}
        self.load_sequences_from_file()  # 沒檔案會印提示，不會當掉

    
    def find_arduino_port(self) -> Optional[str]:
        """自動搜尋Arduino串口"""
        ports = serial.tools.list_ports.comports()
        
        # 優先檢查 COM8
        for port in ports:
            if port.device == 'COM8':
                return 'COM8'
        
        # 搜尋Arduino相關的描述
        for port in ports:
            if any(keyword in port.description.lower() for keyword in 
                   ['arduino', 'ch340', 'ch341', 'usb-serial', 'nano']):
                return port.device
        
        # 沒找到，返回第一個可用串口
        if ports:
            return ports[0].device
        
        return None
    
    def connect(self) -> bool:
        """連接到Arduino"""
        try:
            # 無法連接到指定端口，嘗試自動搜尋
            ports_to_try = [self.port]
            
            # 連接失敗，嘗試自動搜尋
            auto_port = self.find_arduino_port()
            if auto_port and auto_port != self.port:
                ports_to_try.append(auto_port)
            
            last_error = None
            for try_port in ports_to_try:
                try:
                    print(f"🔌 嘗試連接到 {try_port}...")
                    
                    # 先嘗試強制關閉可能殘留的連接
                    try:
                        test_conn = serial.Serial(try_port, 115200, timeout=0.1)
                        test_conn.close()
                        time.sleep(0.5)
                    except:
                        pass
                    
                    # 建立串口連接，禁用 DTR 和 RTS 避免自動重置
                    self.serial_conn = serial.Serial(
                        port=try_port,
                        baudrate=self.baudrate,
                        timeout=2,
                        write_timeout=2,
                        dsrdtr=False,
                        rtscts=False
                    )
                    
                    # 手動控制 DTR 和 RTS
                    self.serial_conn.setDTR(False)
                    self.serial_conn.setRTS(False)
                    time.sleep(0.1)
                    
                    # 重置 Arduino
                    self.serial_conn.setDTR(True)
                    time.sleep(0.1)
                    self.serial_conn.setDTR(False)
                    
                    print(f"   串口已開啟，等待 Arduino 初始化...")
                    
                    # 等待Arduino重置和啟動訊息
                    time.sleep(2.5)
                    
                    # 清空所有殘留訊息
                    print(f"   清空緩衝區...")
                    self.serial_conn.reset_input_buffer()
                    self.serial_conn.reset_output_buffer()
                    time.sleep(0.5)
                    
                    # 發送一個空行來同步
                    self.serial_conn.write(b"\n")
                    self.serial_conn.flush()
                    time.sleep(0.2)
                    
                    # 再次清空
                    while self.serial_conn.in_waiting:
                        self.serial_conn.read(self.serial_conn.in_waiting)
                    
                    print(f"   發送測試指令...")
                    
                    # 暫時設置連接狀態以允許發送指令
                    self.is_connected = True
                    self.port = try_port
                    
                    # 嘗試發送多個測試指令
                    for attempt in range(3):
                        response = self.send_command("STATUS", wait_for_ok=True)
                        
                        if response and ("OK" in response or "STATUS" in response):
                            print(f"✅ 已連接到 {self.port}")
                            print("🎯 三分類系統已就緒")
                            
                            # 讀取當前位置
                            self.update_current_position()
                            return True
                        else:
                            print(f"   嘗試 {attempt + 1}/3: {'無回應' if not response else response}")
                            time.sleep(0.5)
                    
                    # 如果所有嘗試都失敗，重置連接狀態
                    self.is_connected = False
                    
                    print(f"   Arduino 無回應")
                    self.serial_conn.close()
                        
                except Exception as e:
                    last_error = e
                    print(f"   錯誤: {e}")
                    if self.serial_conn and self.serial_conn.is_open:
                        self.serial_conn.close()
                    continue
            
            print(f"\n❌ 連接失敗")
            print(f"💡 故障排除:")
            print(f"   1. 確認 Arduino 已上傳程式碼")
            print(f"   2. 關閉 Arduino IDE 的 Serial Monitor")
            print(f"   3. 確認波特率為 115200")
            print(f"   4. 嘗試重新插拔 USB")
            self.is_connected = False
            return False
                
        except Exception as e:
            print(f"❌ 連接失敗: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """斷開連接"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                # 清空緩衝區
                self.serial_conn.reset_input_buffer()
                self.serial_conn.reset_output_buffer()
                # 關閉串口
                self.serial_conn.close()
                time.sleep(0.5)  # 等待串口完全關閉
            self.is_connected = False
            print("🔌 已斷開連接")
        except Exception as e:
            print(f"⚠️ 斷開連接時出錯: {e}")
            self.is_connected = False
    
    @classmethod
    def reset_instance(cls):
        """重置單例實例（用於測試或重新連接）"""
        if cls._instance is not None:
            if cls._instance.serial_conn and cls._instance.serial_conn.is_open:
                cls._instance.disconnect()
            cls._instance = None
            cls._initialized = False
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> Optional[str]:
        """
        發送指令到Arduino
        
        Args:
            command: 指令字符串
            wait_for_ok: 是否等待OK響應
            
        Returns:
            響應字符串或None
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("❌ 串口未開啟")
            return None
        
        try:
            with self.lock:
                # 清空輸入緩衝區
                self.serial_conn.reset_input_buffer()
                
                # 發送指令
                cmd_bytes = f"{command}\n".encode('utf-8')
                self.serial_conn.write(cmd_bytes)
                self.serial_conn.flush()
                
                if not wait_for_ok:
                    return "SENT"
                
                # 讀取響應
                response_lines = []
                timeout = time.time() + 3  # 3秒超時
                
                while time.time() < timeout:
                    if self.serial_conn.in_waiting:
                        try:
                            line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                            
                            if line:
                                response_lines.append(line)
                                
                                # 收到OK或ERROR，表示指令完成
                                if line.startswith('OK') or line.startswith('ERROR') or line.startswith('POS'):
                                    return '\n'.join(response_lines)
                        except Exception as e:
                            print(f"讀取錯誤: {e}")
                            continue
                    
                    time.sleep(0.05)
                
                # 有收到任何回應，返回
                if response_lines:
                    return '\n'.join(response_lines)
                    
                return None
                
        except Exception as e:
            print(f"❌ 發送指令失敗: {e}")
            return None
    
    def update_current_position(self) -> bool:
        """更新當前位置"""
        try:
            response = self.send_command("GETPOS")
            
            if response and response.startswith("POS"):
                # 解析位置數據
                parts = response.split()[1:]
                if len(parts) == 6:
                    angles = [float(p) for p in parts]
                    self.current_position = Position.from_list(angles)
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 更新位置失敗: {e}")
            return False
    
    def move_joint(self, joint_index: int, angle: float, speed: int = 15) -> bool:
        """
        移動單個關節
        
        Args:
            joint_index: 關節索引 (0-5)
            angle: 目標角度
            speed: 移動速度 (1-100)
        """
        if not self.is_connected:
            return False
        
        if joint_index < 0 or joint_index > 5:
            print(f"❌ 無效的關節索引: {joint_index}")
            return False
        
        command = f"MOVE {joint_index} {int(angle)} {speed}"
        response = self.send_command(command)
        
        if response and "OK" in response:
            # 更新當前位置
            joint_name = f"joint{joint_index + 1}"
            setattr(self.current_position, joint_name, angle)
            return True
        
        return False
    
    def move_to_position(self, position: Position, duration: float = 2.0) -> bool:
        """
        移動到指定位置
        
        Args:
            position: 目標位置
            duration: 移動持續時間(秒)
        """
        if not self.is_connected:
            return False
        
        # 計算速度參數
        speed = max(1, min(100, int(20 / duration)))
        
        angles = position.to_list()
        angles_str = ' '.join(str(int(a)) for a in angles)
        
        command = f"MOVEALL {angles_str} {speed}"
        response = self.send_command(command)
        
        if response and "OK" in response:
            # 優先用硬體回報來更新實際位置
            if not self.update_current_position():
                # 如果 GETPOS 沒回來，就至少複製一份目標位置
                self.current_position = Position.from_list(position.to_list())
            return True
        
        return False

    
    def move_to_predefined(self, position_name: str, duration: float = 2.0) -> bool:
        """移動到預定義位置"""
        if position_name not in self.predefined_positions:
            print(f"❌ 未知的位置: {position_name}")
            return False
        
        position = self.predefined_positions[position_name]
        print(f"📍 移動到 {position_name}: {position}")
        return self.move_to_position(position, duration)
    
    def move_to_home(self) -> bool:
        """移動到原點位置"""
        if not self.is_connected:
            return False
        
        response = self.send_command("HOME")
        
        if response and "OK" in response:
            # 優先用 GETPOS 回讀實際原點角度
            if not self.update_current_position():
                self.current_position = Position.from_list(
                    self.predefined_positions['home'].to_list()
                )
            return True
        
        return False

    
    def open_gripper(self) -> bool:
        if not self.is_connected:
            return False

        response = self.send_command("OPEN")
        if response and "OK" in response:
            self.update_current_position()
            return True
        return False

    
    def close_gripper(self) -> bool:
        if not self.is_connected:
            return False

        response = self.send_command("CLOSE")
        if response and "OK" in response:
            self.update_current_position()
            return True
        return False


    
    def execute_pick_and_place_sequence(self, target: str) -> bool:
        """
        執行抓取和放置序列 - 三分類支援

        Args:
            target: 'single' / 'double' / 'multiple'
        """
        if not self.is_connected:
            print("❌ 機械手臂未連接")
            return False

        target_upper = target.upper()

        # 先決定對應 key & Arduino 指令
        sequence_key = None
        if target_upper in ['SINGLE', 'SINGLE_DEFECT']:
            command = "SEQUENCE SINGLE"
            area_name = "單一缺陷區"
            sequence_key = "single"
        elif target_upper in ['DOUBLE', 'DOUBLE_DEFECT', 'TWO']:
            command = "SEQUENCE DOUBLE"
            area_name = "兩種缺陷區"
            sequence_key = "double"
        elif target_upper in ['MULTIPLE', 'MULTIPLE_DEFECT', 'THREE']:
            command = "SEQUENCE MULTIPLE"
            area_name = "多種缺陷區"
            sequence_key = "multiple"
        else:
            print(f"❌ 未知的分類目標: {target}")
            return False

        # 有自訂序列，就優先用自訂路徑（PC 端分段移動）
        if sequence_key and self.sequences.get(sequence_key):
            print(f"🤖 使用自訂路徑執行 {area_name} ({sequence_key})")
            return self.execute_custom_sequence(sequence_key)

        # 否則退回 Arduino 內建 SEQUENCE
        print(f"🤖 使用 Arduino 內建 SEQUENCE 執行分類序列: {area_name}")
        response = self.send_command(command)

        if response and "OK" in response:
            print(f"✅ 分類完成: {area_name}")
            return True
        else:
            print(f"❌ 分類失敗: {area_name}")
            return False

    
    def emergency_stop(self) -> bool:
        """緊急停止"""
        if not self.is_connected:
            return False
        
        response = self.send_command("STOP", wait_for_ok=False)
        self.emergency_stopped = True
        print("🚨 緊急停止已激活")
        return True
    
    def resume(self) -> bool:
        """恢復運行"""
        if not self.is_connected:
            return False
        
        response = self.send_command("RESUME")
        if response and "OK" in response:
            self.emergency_stopped = False
            print("✅ 已恢復運行")
            return True
        return False
    
    def calibrate_joint(self, joint_name: str) -> bool:
        """校正單個關節"""
        if not self.is_connected:
            return False
        
        # 解析關節索引
        joint_index = int(joint_name.replace('joint', '')) - 1
        
        if joint_index < 0 or joint_index > 5:
            return False
        
        command = f"CALIBRATE {joint_index}"
        response = self.send_command(command)
        
        if response and "OK" in response:
            print(f"✅ 關節 {joint_name} 校正完成")
            return True
        
        return False
    
    def calibrate_all_joints(self) -> bool:
        """校正所有關節"""
        if not self.is_connected:
            return False
        
        response = self.send_command("CALIBRATE")
        
        if response and "OK" in response:
            print("✅ 所有關節校正完成")
            return True
        
        return False
    
    def set_speed(self, speed: int) -> bool:
        """
        設置移動速度
        
        Args:
            speed: 速度值 (1-100)
        """
        if not self.is_connected:
            return False
        
        speed = max(1, min(100, speed))
        command = f"SPEED {speed}"
        response = self.send_command(command)
        
        if response and "OK" in response:
            return True
        
        return False
    
    def get_status(self) -> Dict:
        """獲取系統狀態"""
        status = {
            'hardware_available': self.is_connected,
            'is_moving': self.is_moving,
            'emergency_stopped': self.emergency_stopped,
            'current_position': self.current_position.to_list(),
            'port': self.port,
            'classification_mode': 'three_class'  # 標識三分類模式
        }
        
        return status
    
    def get_joint_info(self) -> Dict:
        """獲取關節信息"""
        joint_info_with_angles = {}
        
        for i, (joint_id, info) in enumerate(self.joint_info.items()):
            angle = getattr(self.current_position, joint_id)
            joint_info_with_angles[joint_id] = {
                'name': info['name'],
                'current_angle': angle,
                'min_angle': info['min'],
                'max_angle': info['max'],
                'channel': info['channel']
            }
        
        return joint_info_with_angles
    
    def save_position(self, name: str) -> bool:
        """保存當前位置"""
        self.predefined_positions[name] = Position(*self.current_position.to_list())
        print(f"💾 位置已保存: {name}")
        return True
    
    def load_positions_from_file(self, filename: str = "positions.json") -> bool:
        """從文件載入位置"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for name, angles in data.items():
                self.predefined_positions[name] = Position.from_list(angles)
            
            print(f"📂 已從 {filename} 載入 {len(data)} 個位置")
            return True
            
        except FileNotFoundError:
            print(f"❌ 文件不存在: {filename}")
            return False
        except Exception as e:
            print(f"❌ 載入失敗: {e}")
            return False
    
    def load_sequences_from_file(self, filename: str = "sequences.json") -> bool:
        """從文件載入自訂路徑序列"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.sequences = {}
            for name, steps in data.items():
                if isinstance(steps, list):
                    self.sequences[name] = steps

            print(f"📂 已從 {filename} 載入 {len(self.sequences)} 個序列")
            return True
        except FileNotFoundError:
            print(f"ℹ️ 尚未建立序列檔 {filename}，目前只使用 Arduino 內建 SEQUENCE")
            self.sequences = {}
            return False
        except Exception as e:
            print(f"❌ 載入序列失敗: {e}")
            self.sequences = {}
            return False

    def save_sequences_to_file(self, filename: str = "sequences.json") -> bool:
        """將目前序列保存到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.sequences, f, indent=2, ensure_ascii=False)
            print(f"💾 已保存 {len(self.sequences)} 個序列到 {filename}")
            return True
        except Exception as e:
            print(f"❌ 保存序列失敗: {e}")
            return False

    def execute_custom_sequence(self, seq_name: str) -> bool:
        """依照 sequences.json 中定義的路徑執行分類 (在 PC 端分段 MOVEALL)"""
        if not self.is_connected:
            print("❌ 機械手臂未連接")
            return False

        steps = self.sequences.get(seq_name)
        if not steps:
            print(f"ℹ️ 找不到自訂序列 {seq_name}，改用 Arduino 內建 SEQUENCE")
            return False

        print(f"🤖 執行自訂序列: {seq_name}")
        for i, step in enumerate(steps, start=1):
            if self.emergency_stopped:
                print("🚨 已緊急停止，序列中斷")
                return False

            stype = step.get("type")
            try:
                if stype == "move":
                    pos_name = step.get("position")
                    duration = float(step.get("duration", 2.0))
                    print(f"   📍 [{i}] MOVE -> {pos_name} (duration={duration})")
                    if not self.move_to_predefined(pos_name, duration):
                        print(f"❌ 移動失敗: {pos_name}")
                        return False

                elif stype == "gripper":
                    action = step.get("action")
                    print(f"   ✋ [{i}] GRIPPER -> {action}")
                    if action == "open":
                        if not self.open_gripper():
                            return False
                    elif action == "close":
                        if not self.close_gripper():
                            return False
                    else:
                        print(f"⚠️ 未知夾爪動作: {action}")

                elif stype == "delay":
                    sec = float(step.get("seconds", 0.5))
                    print(f"   ⏱️ [{i}] DELAY {sec}s")
                    time.sleep(sec)

                else:
                    print(f"⚠️ [{i}] 未知步驟類型: {stype}")

            except Exception as e:
                print(f"❌ 序列步驟錯誤 [{i}]: {e}")
                return False

        print(f"✅ 自訂序列 {seq_name} 執行完成")
        return True

    
    def save_positions_to_file(self, filename: str = "positions.json") -> bool:
        """保存位置到文件"""
        try:
            data = {name: pos.to_list() 
                   for name, pos in self.predefined_positions.items()}
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 已保存 {len(data)} 個位置到 {filename}")
            return True
            
        except Exception as e:
            print(f"❌ 保存失敗: {e}")
            return False
    
    def cleanup(self):
        """清理資源"""
        print("🧹 正在清理...")
        if self.is_connected:
            # 移動到安全位置
            try:
                self.move_to_home()
            except:
                pass
            
            self.disconnect()
    
    def __del__(self):
        """析構函數"""
        self.cleanup()


# 測試程式
def test_three_class_controller():
    """測試三分類功能"""
    print("=" * 60)
    print("六軸機械手臂三分類系統測試")
    print("=" * 60)
    
    # 創建控制器
    controller = RoboticArmController()
    
    if not controller.is_connected:
        print("❌ 無法連接到機械手臂")
        return
    
    try:
        # 顯示狀態
        print("\n📊 系統狀態:")
        status = controller.get_status()
        print(f"  連接狀態: {'✅ 已連接' if status['hardware_available'] else '❌ 未連接'}")
        print(f"  串口: {status['port']}")
        print(f"  分類模式: {status['classification_mode']}")
        
        # 移動到原點
        print("\n🏠 移動到原點...")
        controller.move_to_home()
        time.sleep(2)
        
        # 測試夾爪
        print("\n✋ 測試夾爪...")
        controller.open_gripper()
        time.sleep(1)
        controller.close_gripper()
        time.sleep(1)
        
        # 測試三分類序列
        print("\n🎬 測試三分類序列...")
        
        print("\n1️⃣ 測試單一缺陷分類...")
        controller.execute_pick_and_place_sequence('single')
        time.sleep(3)
        
        print("\n2️⃣ 測試兩種缺陷分類...")
        controller.execute_pick_and_place_sequence('double')
        time.sleep(3)
        
        print("\n3️⃣ 測試多種缺陷分類...")
        controller.execute_pick_and_place_sequence('multiple')
        time.sleep(3)
        
        # 回到原點
        print("\n🏠 回到原點...")
        controller.move_to_home()
        
        print("\n✅ 三分類測試完成！")
        
    except KeyboardInterrupt:
        print("\n⚠️ 測試中斷")
    finally:
        controller.cleanup()


if __name__ == '__main__':
    test_three_class_controller()
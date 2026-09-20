"""
三分類系統的配置參數
"""

from dataclasses import dataclass, asdict

@dataclass
class HardwareConfig:
    """硬體配置 - 雙IR版本"""
    
    
    # 雙IR感應器引腳
    ir1_sensor_pin: int = 23  # IR1: 拍照檢測觸發
    ir2_sensor_pin: int = 22  # IR2: 機械手臂分類觸發
    
    relay_pin: int = 25
    
    # 相機配置
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    
    
    # 機械手臂配置
    use_robotic_arm: bool = True
    arm_channels: list = None
    
    
    
    # PWM配置
    pwm_frequency: int = 1000
    
    def __post_init__(self):
        if self.arm_channels is None:
            self.arm_channels = [0, 1, 2, 3, 4, 5]


@dataclass
class DetectionConfig:
    """檢測配置 - 三分類版本"""
    threshold: float = 0.5
    processing_delay: float = 0.1
    sorting_delay: float = 0.5
    
    # 機械手臂三分類配置
    use_arm_sorting: bool = True
    arm_sequence_timeout: float = 10.0
    
    # 三分類區域配置
    single_defect_area: dict = None      # 單一缺陷區域
    double_defect_area: dict = None      # 兩種缺陷區域
    multiple_defect_area: dict = None    # 多種缺陷區域
    
    
    
    # PCB 缺陷類型配置
    defect_types: list = None
    
    # 雙IR系統配置
    ir1_debounce_time: float = 0.5   # IR1去抖動時間
    ir2_debounce_time: float = 0.5   # IR2去抖動時間
    conveyor_stop_delay: float = 0.3 # 輸送帶停止延遲
    
    def __post_init__(self):
        if self.defect_types is None:
            self.defect_types = ['鼠咬', '斷路', '雜銅']
        
        # 預設三分類區域位置
        if self.single_defect_area is None:
            self.single_defect_area = {
                'joint1': 60, 'joint2': 45, 'joint3': 135,
                'joint4': 90, 'joint5': 90, 'joint6': 30
            }
        
        if self.double_defect_area is None:
            self.double_defect_area = {
                'joint1': 90, 'joint2': 45, 'joint3': 135,
                'joint4': 90, 'joint5': 90, 'joint6': 30
            }
        
        if self.multiple_defect_area is None:
            self.multiple_defect_area = {
                'joint1': 120, 'joint2': 45, 'joint3': 135,
                'joint4': 90, 'joint5': 90, 'joint6': 30
            }


@dataclass
class UIConfig:
    """界面配置"""
    window_width: int = 1400
    window_height: int = 900
    window_x: int = 100
    window_y: int = 100
    theme: str = "default"
    font_family: str = "Microsoft JhengHei"
    font_size: int = 9
    max_log_records: int = 200
    
    # 三分類顯示顏色
    single_defect_color: str = "#2196F3"    # 藍色
    double_defect_color: str = "#FF9800"    # 橙色
    multiple_defect_color: str = "#f44336"  # 紅色


@dataclass
class SystemConfig:
    """系統配置"""
    data_directory: str = "data"
    max_records: int = 10000
    auto_save_interval: int = 60
    debug_mode: bool = False
    language: str = "zh-TW"
    
    # 三分類系統配置
    classification_mode: str = "three_class"  # "three_class" 或 "pass_fail"
    enable_dual_ir: bool = True               # 啟用雙IR系統



# ConfigManager 類別的擴展方法

class ConfigManager:
    """配置管理器 - 三分類版本"""
    
   
    
    def get_classification_areas(self):
        """獲取三分類區域配置"""
        return {
            'single': self.detection.single_defect_area,
            'double': self.detection.double_defect_area,
            'multiple': self.detection.multiple_defect_area
        }
    
    def update_classification_area(self, area_type: str, positions: dict):
        """
        更新分類區域位置
        
        Args:
            area_type: 'single', 'double', 或 'multiple'
            positions: 位置字典 {'joint1': ..., 'joint2': ..., ...}
        """
        if area_type == 'single':
            self.detection.single_defect_area = positions
        elif area_type == 'double':
            self.detection.double_defect_area = positions
        elif area_type == 'multiple':
            self.detection.multiple_defect_area = positions
        else:
            raise ValueError(f"未知的區域類型: {area_type}")
        
        self.save_config()
        print(f"✅ 已更新 {area_type} 分類區域配置")
    
    
    
    
    
    def get_ir_config(self):
        """獲取雙IR配置"""
        return {
            'ir1_pin': self.hardware.ir1_sensor_pin,
            'ir2_pin': self.hardware.ir2_sensor_pin,
            'ir1_debounce': self.detection.ir1_debounce_time,
            'ir2_debounce': self.detection.ir2_debounce_time,
            'conveyor_delay': self.detection.conveyor_stop_delay
        }
    
    def update_ir_config(self, **kwargs):
        """更新IR配置"""
        for key, value in kwargs.items():
            if key == 'ir1_pin':
                self.hardware.ir1_sensor_pin = value
            elif key == 'ir2_pin':
                self.hardware.ir2_sensor_pin = value
            elif key == 'ir1_debounce':
                self.detection.ir1_debounce_time = value
            elif key == 'ir2_debounce':
                self.detection.ir2_debounce_time = value
            elif key == 'conveyor_delay':
                self.detection.conveyor_stop_delay = value
        
        self.save_config()
        print("✅ IR配置已更新")
    
    def get_config_summary_3class(self) -> str:
        """獲取三分類配置摘要"""
        areas = self.get_classification_areas()
        angles = self.get_servo_angles()
        ir_config = self.get_ir_config()
        
        return f"""
三分類系統配置摘要
==================

硬體配置:
- IR1 感應器引腳: {self.hardware.ir1_sensor_pin} (拍照檢測)
- IR2 感應器引腳: {self.hardware.ir2_sensor_pin} (機械手臂分類)
- 繼電器引腳: {self.hardware.relay_pin}
- 機械手臂: {'啟用' if self.hardware.use_robotic_arm else '停用'}

檢測配置:
- 檢測閾值: {self.detection.threshold}
- 缺陷類型: {', '.join(self.detection.defect_types)}
- IR1去抖動時間: {self.detection.ir1_debounce_time}秒
- IR2去抖動時間: {self.detection.ir2_debounce_time}秒

三分類區域 (機械手臂):
- 單一缺陷區域: Joint1={areas['single']['joint1']}°
- 兩種缺陷區域: Joint1={areas['double']['joint1']}°
- 多種缺陷區域: Joint1={areas['multiple']['joint1']}°

系統配置:
- 分類模式: {self.system.classification_mode}
- 雙IR系統: {'啟用' if self.system.enable_dual_ir else '停用'}
- 數據目錄: {self.system.data_directory}
"""



# 測試三分類配置

def test_three_class_config():
    """測試三分類配置"""
    print("🧪 測試三分類配置管理...")
    
    config = ConfigManager()
    
    # 顯示配置摘要
    print(config.get_config_summary_3class())
    
    # 測試更新分類區域
    print("\n測試更新分類區域:")
    new_single_area = {
        'joint1': 65, 'joint2': 50, 'joint3': 130,
        'joint4': 90, 'joint5': 90, 'joint6': 30
    }
    config.update_classification_area('single', new_single_area)
    
    
    # 測試更新IR配置
    print("\n測試更新IR配置:")
    config.update_ir_config(
        ir1_debounce=0.6,
        ir2_debounce=0.6,
        conveyor_delay=0.4
    )
    
    print("\n✅ 配置測試完成")


if __name__ == '__main__':
    test_three_class_config()
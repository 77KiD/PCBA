"""
資料管理模組 
支援三分類統計：單一缺陷、兩種缺陷、多種缺陷
"""

import json
import os
import csv
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional


@dataclass
class DetectionRecord:
    """檢測記錄數據類"""
    timestamp: str
    result: str
    defect_type: str = ""
    classification: str = ""  
    confidence: float = 0.0
    action: str = ""
    image_path: str = ""


class Statistics:
    """統計數據類 - 支援三分類"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重設所有統計"""
        # 基本統計
        self.total_count = 0
        self.pass_count = 0
        self.defect_count = 0
        
        # 缺陷類型統計
        self.short_count = 0      # 短路 (目前沒有)
        self.open_count = 0       # 斷路
        self.bridge_count = 0     # 橋接 (目前沒有)
        self.missing_count = 0    # 缺件 (目前沒有)
        self.mouse_bite_count = 0 # 鼠咬
        self.copper_count = 0     # 雜銅
        
        # 三分類統計
        self.single_defect_count = 0    # 單一缺陷
        self.double_defect_count = 0    # 兩種缺陷
        self.multiple_defect_count = 0  # 多種缺陷
        
        # 時間統計
        self.start_time = datetime.now()
        self.last_update_time = datetime.now()
    
    def update_with_result(self, result: str, defect_type: str = "", classification: str = ""):
        """
        使用檢測結果更新統計
        
        Args:
            result: 檢測結果 (合格/單一缺陷/兩種缺陷/多種缺陷)
            defect_type: 缺陷類型 (逗號分隔)
            classification: 三分類類別
        """
        self.total_count += 1
        self.last_update_time = datetime.now()
        
        if result == "合格":
            self.pass_count += 1
        else:
            self.defect_count += 1
            
            # 更新缺陷類型統計
            if defect_type:
                defects = defect_type.split(",")
                for defect in defects:
                    defect = defect.strip()
                    if defect in ["短路", "short"]:
                        self.short_count += 1
                    elif defect in ["斷路", "open", "open_circuit"]:
                        self.open_count += 1
                    elif defect in ["橋接", "bridge"]:
                        self.bridge_count += 1
                    elif defect in ["缺件", "missing"]:
                        self.missing_count += 1
                    elif defect in ["鼠咬", "mouse_bite", "mousebite"]:
                        self.mouse_bite_count += 1
                    elif defect in ["雜銅", "copper", "contamination"]:
                        self.copper_count += 1
            
            # 更新三分類統計
            if result == "單一缺陷" or classification == "🔵 單一缺陷":
                self.single_defect_count += 1
            elif result == "兩種缺陷" or classification == "🟡 兩種缺陷":
                self.double_defect_count += 1
            elif result == "多種缺陷" or classification == "🔴 多種缺陷":
                self.multiple_defect_count += 1
    
    def get_pass_rate(self) -> float:
        """獲取合格率"""
        if self.total_count == 0:
            return 0.0
        return (self.pass_count / self.total_count) * 100.0
    
    def get_defect_rate(self) -> float:
        """獲取缺陷率"""
        if self.total_count == 0:
            return 0.0
        return (self.defect_count / self.total_count) * 100.0
    
    def get_classification_distribution(self) -> Dict[str, int]:
        """獲取三分類分布"""
        return {
            "單一缺陷": self.single_defect_count,
            "兩種缺陷": self.double_defect_count,
            "多種缺陷": self.multiple_defect_count,
        }
    
    def get_defect_type_distribution(self) -> Dict[str, int]:
        """獲取缺陷類型分布"""
        return {
            "鼠咬": self.mouse_bite_count,
            "斷路": self.open_count,
            "雜銅": self.copper_count,
            "短路": self.short_count,
            "橋接": self.bridge_count,
            "缺件": self.missing_count,
        }
    
    def get_runtime(self) -> str:
        """獲取運行時間"""
        delta = datetime.now() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> Dict:
        """轉換為字典"""
        return {
            "total_count": self.total_count,
            "pass_count": self.pass_count,
            "defect_count": self.defect_count,
            "pass_rate": self.get_pass_rate(),
            "classification_distribution": self.get_classification_distribution(),
            "defect_type_distribution": self.get_defect_type_distribution(),
            "runtime": self.get_runtime(),
        }


class DataManager:
    """資料管理器 - 支援三分類"""
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化資料管理器
        
        Args:
            data_dir: 資料儲存目錄
        """
        self.data_dir = data_dir
        self.records: List[DetectionRecord] = []
        self.statistics = Statistics()
        self.max_records = 10000
        
        # 確保資料目錄存在
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 載入歷史記錄
        self.load_records()
    
    def add_record(self, result: str, defect_type: str = "", confidence: float = 0.0,
                   classification: str = "", image_path: str = "") -> DetectionRecord:
        """
        添加檢測記錄
        
        Args:
            result: 檢測結果
            defect_type: 缺陷類型
            confidence: 信心度
            classification: 三分類類別
            image_path: 影像路徑
            
        Returns:
            創建的記錄
        """
        # 確定動作
        if result == "合格":
            action = "✅ 合格入庫"
        elif "單一" in result or "單一" in classification:
            action = "🔵 單一缺陷區"
        elif "兩種" in result or "兩種" in classification:
            action = "🟡 兩種缺陷區"
        else:
            action = "🔴 多種缺陷區"
        
        # 創建記錄
        record = DetectionRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result=result,
            defect_type=defect_type,
            classification=classification,
            confidence=confidence,
            action=action,
            image_path=image_path
        )
        
        # 添加到列表
        self.records.append(record)
        
        # 限制記錄數量
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
        
        # 更新統計
        self.statistics.update_with_result(result, defect_type, classification)
        
        return record
    
    def get_statistics(self) -> Statistics:
        """獲取統計數據"""
        return self.statistics
    
    def get_records(self, limit: int = 100) -> List[DetectionRecord]:
        """
        獲取記錄
        
        Args:
            limit: 返回記錄數量限制
            
        Returns:
            記錄列表
        """
        return self.records[-limit:]
    
    def clear_records(self):
        """清除所有記錄"""
        self.records.clear()
        self.statistics.reset()
        print("🗑️ 所有記錄已清除")
    
    def save_records(self, filename: str = None):
        """
        保存記錄到檔案
        
        Args:
            filename: 檔案名稱
        """
        if filename is None:
            filename = os.path.join(
                self.data_dir,
                f"records_{datetime.now().strftime('%Y%m%d')}.json"
            )
        
        try:
            data = {
                "records": [asdict(r) for r in self.records],
                "statistics": self.statistics.to_dict(),
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 記錄已保存: {filename}")
            
        except Exception as e:
            print(f"❌ 保存記錄失敗: {e}")
    
    def load_records(self, filename: str = None):
        """
        從檔案載入記錄
        
        Args:
            filename: 檔案名稱
        """
        if filename is None:
            # 嘗試載入今天的記錄
            filename = os.path.join(
                self.data_dir,
                f"records_{datetime.now().strftime('%Y%m%d')}.json"
            )
        
        if not os.path.exists(filename):
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 載入記錄
            self.records = [
                DetectionRecord(**r) for r in data.get("records", [])
            ]
            
            print(f"📂 已載入 {len(self.records)} 條記錄")
            
        except Exception as e:
            print(f"⚠️ 載入記錄失敗: {e}")
    
    def export_report(self, file_path: str = None) -> str:
        """
        匯出文字報告
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            保存的檔案路徑
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.data_dir, f"PCBA_Report_{timestamp}.txt")
        
        try:
            stats = self.statistics
            class_dist = stats.get_classification_distribution()
            defect_dist = stats.get_defect_type_distribution()
            
            content = f"""
================================================================================
                    PCB缺陷檢測系統 - 檢測報告
================================================================================

報告生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
系統運行時間: {stats.get_runtime()}

================================================================================
                          基本統計
================================================================================

總檢測數量: {stats.total_count}
合格數量:   {stats.pass_count}
缺陷數量:   {stats.defect_count}
合格率:     {stats.get_pass_rate():.2f}%

================================================================================
                        三分類統計
================================================================================

🔵 單一缺陷: {class_dist['單一缺陷']} 件
🟡 兩種缺陷: {class_dist['兩種缺陷']} 件
🔴 多種缺陷: {class_dist['多種缺陷']} 件

================================================================================
                      缺陷類型分布
================================================================================

🐭 鼠咬:   {defect_dist['鼠咬']} 次
⚡ 斷路:   {defect_dist['斷路']} 次
🔶 雜銅:   {defect_dist['雜銅']} 次
⚡ 短路:   {defect_dist['短路']} 次
🔗 橋接:   {defect_dist['橋接']} 次
📦 缺件:   {defect_dist['缺件']} 次

================================================================================
                        最近記錄
================================================================================

"""
            # 添加最近記錄
            recent_records = self.get_records(20)
            for i, record in enumerate(recent_records, 1):
                content += f"{i:3d}. [{record.timestamp}] {record.result}"
                if record.defect_type:
                    content += f" - {record.defect_type}"
                content += f" ({record.action})\n"
            
            content += """
================================================================================
                          報告結束
================================================================================
"""
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"📄 報告已匯出: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ 匯出報告失敗: {e}")
            return ""
    
    def export_csv(self, file_path: str = None) -> str:
        """
        匯出CSV數據
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            保存的檔案路徑
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.data_dir, f"PCBA_Records_{timestamp}.csv")
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['時間', '結果', '缺陷類型', '三分類', '信心度', '動作', '影像路徑']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                
                for record in self.records:
                    writer.writerow({
                        '時間': record.timestamp,
                        '結果': record.result,
                        '缺陷類型': record.defect_type or '-',
                        '三分類': record.classification or '-',
                        '信心度': f"{record.confidence:.2f}",
                        '動作': record.action,
                        '影像路徑': record.image_path or '-'
                    })
            
            print(f"📊 CSV已匯出: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ 匯出CSV失敗: {e}")
            return ""
    
    def get_summary(self) -> str:
        """獲取摘要資訊"""
        stats = self.statistics
        class_dist = stats.get_classification_distribution()
        
        return f"""
📊 檢測摘要
━━━━━━━━━━━━━━━━━━━━
總計: {stats.total_count} | 合格: {stats.pass_count} | 缺陷: {stats.defect_count}
合格率: {stats.get_pass_rate():.1f}%

三分類:
🔵 單一缺陷: {class_dist['單一缺陷']}
🟡 兩種缺陷: {class_dist['兩種缺陷']}
🔴 多種缺陷: {class_dist['多種缺陷']}
━━━━━━━━━━━━━━━━━━━━
"""


# 測試函數
def test_data_manager():
    """測試資料管理器"""
    print("🧪 測試資料管理器...")
    
    dm = DataManager(data_dir="test_data")
    
    # 添加測試記錄
    dm.add_record("合格", "", 0.95, "")
    dm.add_record("單一缺陷", "鼠咬", 0.85, "🔵 單一缺陷")
    dm.add_record("兩種缺陷", "鼠咬,斷路", 0.78, "🟡 兩種缺陷")
    dm.add_record("多種缺陷", "鼠咬,斷路,雜銅", 0.65, "🔴 多種缺陷")
    dm.add_record("單一缺陷", "雜銅", 0.82, "🔵 單一缺陷")
    
    # 顯示摘要
    print(dm.get_summary())
    
    # 匯出報告
    dm.export_report()
    dm.export_csv()
    
    print("✅ 資料管理器測試完成")


if __name__ == '__main__':
    test_data_manager()

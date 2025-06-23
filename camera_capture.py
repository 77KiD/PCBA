import cv2
import time
import os

def capture_image(output_dir="captured_images", filename_prefix="capture"):
    """
    連接預設的 USB 視訊鏡頭，截取一張圖片並保存。

    Args:
        output_dir (str): 圖片保存的目錄。
        filename_prefix (str): 保存圖片的檔案名前綴。

    Returns:
        str: 保存圖片的完整路徑，如果失敗則返回 None。
    """
    # 檢查輸出目錄是否存在，如果不存在則創建
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"目錄 '{output_dir}' 已創建。")

    # 初始化鏡頭
    # 0 通常代表預設的鏡頭。如果您有多個鏡頭，可能需要嘗試不同的索引 (例如 1, 2)。
    cap = cv2.VideoCapture(0)

    # 檢查鏡頭是否成功打開
    if not cap.isOpened():
        print("錯誤：無法打開視訊鏡頭。請檢查鏡頭是否連接正常，或者索引是否正確。")
        return None

    print("視訊鏡頭已成功打開。正在嘗試截圖...")

    # 給鏡頭一些時間來穩定自動曝光和對焦
    time.sleep(2)

    # 讀取一幀
    ret, frame = cap.read()

    if ret:
        # 生成帶有時間戳的檔案名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)

        # 保存圖片
        try:
            cv2.imwrite(filepath, frame)
            print(f"圖片已成功保存到: {filepath}")
        except Exception as e:
            print(f"錯誤：無法保存圖片。{e}")
            filepath = None
    else:
        print("錯誤：無法從鏡頭讀取畫面。")
        filepath = None

    # 釋放鏡頭資源
    cap.release()
    print("視訊鏡頭已釋放。")
    # cv2.destroyAllWindows() # 如果有顯示視窗，則需要這行

    return filepath

if __name__ == '__main__':
    # 創建一個名為 'captured_images' 的資料夾來存放圖片
    # 如果您想指定其他資料夾，可以修改這裡
    saved_image_path = capture_image(output_dir="captured_images")

    if saved_image_path:
        print(f"\n測試截圖成功，圖片位於: {saved_image_path}")
        # 您可以在這裡添加代碼來顯示圖片 (可選)
        # img = cv2.imread(saved_image_path)
        # cv2.imshow("Captured Image", img)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
    else:
        print("\n測試截圖失敗。")

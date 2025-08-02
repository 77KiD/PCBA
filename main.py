import os
import sys
import subprocess

def run_gui():
    """
    Attempts to run the main GUI application.
    """
    print("訊息：這個 'main.py' 檔案已被棄用。")
    print("系統將嘗試啟動新的圖形化介面 'gui_main.py'。")
    print("未來請直接執行 'python gui_main.py' 來啟動應用程式。")
    print("-" * 50)

    try:
        # We use subprocess.run to execute the new main script.
        # This is more robust than importing and calling a function,
        # as it runs the GUI in a separate process, ensuring a clean environment.
        # sys.executable is the current python interpreter.
        subprocess.run([sys.executable, "gui_main.py"], check=True)
    except FileNotFoundError:
        print("錯誤：'gui_main.py' 檔案未找到。")
        print("請確認所有專案檔案都存在。")
    except subprocess.CalledProcessError as e:
        print(f"錯誤：啟動 'gui_main.py' 時發生錯誤: {e}")
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")

if __name__ == '__main__':
    run_gui()

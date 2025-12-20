import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

try:
    from .config import memory_config
    from .database import DatabaseManager
except (ImportError, ValueError):
    from config import memory_config
    from database import DatabaseManager

class MemoryVisualizer:
    """
    記憶層資料視覺化工具 (GUI)
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Home Agent - 記憶層視覺化工具")
        self.root.geometry("1000x700")
        
        # 初始化資料庫管理器
        self.db = DatabaseManager()
        
        # 狀態變數
        self.is_running = True
        self.refresh_interval = 2.0  # 秒
        
        self._setup_ui()
        
        # 啟動自動更新執行緒
        self.update_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self.update_thread.start()
        
        # 視窗關閉處理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _to_local_time(self, dt_obj: datetime) -> datetime:
        """將 datetime 轉換為系統本地時間"""
        if dt_obj is None:
            return None
        # 如果是 naive (無時區資訊)，假設為 UTC
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        # 轉換為本地時間
        return dt_obj.astimezone()

    def _setup_ui(self):
        """建立 UI 佈局"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- 頂部狀態欄 ---
        status_frame = ttk.LabelFrame(main_frame, text="系統狀態", padding="5")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.conn_status_var = tk.StringVar(value="正在連線...")
        self.conn_label = ttk.Label(status_frame, textvariable=self.conn_status_var, font=("Arial", 10, "bold"))
        self.conn_label.pack(side=tk.LEFT, padx=10)
        
        self.stats_var = tk.StringVar(value="載入中...")
        ttk.Label(status_frame, textvariable=self.stats_var).pack(side=tk.LEFT, padx=20)
        
        ttk.Button(status_frame, text="手動重新整理", command=self.refresh_data).pack(side=tk.RIGHT, padx=5)
        
        # --- 中間內容區 (分頁) ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 分頁 1: 最近事件
        self.event_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.event_frame, text=" 最近事件 (Telemetry) ")
        self._setup_event_tab()
        
        # 分頁 2: 成員狀態
        self.state_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.state_frame, text=" 成員即時狀態 ")
        self._setup_state_tab()
        
        # 分頁 3: 管理與設定
        self.admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.admin_frame, text=" 管理與設定 ")
        self._setup_admin_tab()

    def _setup_event_tab(self):
        """設定事件分頁"""
        # 表格
        columns = ("time", "person_id", "member_name", "action", "conf", "duration", "room", "bbox", "motion")
        self.event_tree = ttk.Treeview(self.event_frame, columns=columns, show="headings")
        
        # 定義欄位
        self.event_tree.heading("time", text="時間")
        self.event_tree.heading("person_id", text="人物 ID")
        self.event_tree.heading("member_name", text="識別成員")
        self.event_tree.heading("action", text="動作")
        self.event_tree.heading("conf", text="信心度")
        self.event_tree.heading("duration", text="持續時間(s)")
        self.event_tree.heading("room", text="位置")
        self.event_tree.heading("bbox", text="邊界框 (x,y,w,h)")
        self.event_tree.heading("motion", text="動作幅度")
        
        self.event_tree.column("time", width=160)
        self.event_tree.column("person_id", width=60, anchor=tk.CENTER)
        self.event_tree.column("member_name", width=100, anchor=tk.CENTER)
        self.event_tree.column("action", width=100, anchor=tk.CENTER)
        self.event_tree.column("conf", width=60, anchor=tk.CENTER)
        self.event_tree.column("duration", width=80, anchor=tk.CENTER)
        self.event_tree.column("room", width=100)
        self.event_tree.column("bbox", width=120)
        self.event_tree.column("motion", width=80, anchor=tk.CENTER)
        
        # 滾動條
        scrollbar = ttk.Scrollbar(self.event_frame, orient=tk.VERTICAL, command=self.event_tree.yview)
        self.event_tree.configure(yscroll=scrollbar.set)
        
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_state_tab(self):
        """設定狀態分頁"""
        columns = ("person_id", "member_name", "last_seen", "last_action", "duration", "location", "bbox", "visible")
        self.state_tree = ttk.Treeview(self.state_frame, columns=columns, show="headings")
        
        self.state_tree.heading("person_id", text="人物 ID")
        self.state_tree.heading("member_name", text="成員名稱")
        self.state_tree.heading("last_seen", text="最後出現時間")
        self.state_tree.heading("last_action", text="最後動作")
        self.state_tree.heading("duration", text="持續時間(s)")
        self.state_tree.heading("location", text="最後位置")
        self.state_tree.heading("bbox", text="最後座標")
        self.state_tree.heading("visible", text="是否在場")
        
        self.state_tree.column("person_id", width=80, anchor=tk.CENTER)
        self.state_tree.column("member_name", width=100, anchor=tk.CENTER)
        self.state_tree.column("last_seen", width=180)
        self.state_tree.column("last_action", width=120, anchor=tk.CENTER)
        self.state_tree.column("duration", width=80, anchor=tk.CENTER)
        self.state_tree.column("location", width=100, anchor=tk.CENTER)
        self.state_tree.column("bbox", width=120, anchor=tk.CENTER)
        self.state_tree.column("visible", width=80, anchor=tk.CENTER)
        
        self.state_tree.pack(fill=tk.BOTH, expand=True)

    def _setup_admin_tab(self):
        """設定管理分頁"""
        # 1. 資料庫操作區
        db_frame = ttk.LabelFrame(self.admin_frame, text="資料庫操作", padding="10")
        db_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(db_frame, text="清除所有歷史資料 (保留成員)", command=self._clear_history_data).pack(side=tk.LEFT, padx=5)
        ttk.Label(db_frame, text="注意：此操作將清空所有遙測記錄與狀態快照，但保留已註冊的成員資料。").pack(side=tk.LEFT, padx=10)
        
        # 2. 成員管理區
        member_frame = ttk.LabelFrame(self.admin_frame, text="成員管理 (ReID)", padding="10")
        member_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 工具列
        toolbar = ttk.Frame(member_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(toolbar, text="刪除選取成員", command=self._delete_selected_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="重新整理列表", command=self._refresh_member_list).pack(side=tk.LEFT, padx=5)
        
        # 成員列表
        columns = ("id", "name", "samples", "updated")
        self.member_tree = ttk.Treeview(member_frame, columns=columns, show="headings")
        
        self.member_tree.heading("id", text="ID")
        self.member_tree.heading("name", text="成員名稱")
        self.member_tree.heading("samples", text="樣本數")
        self.member_tree.heading("updated", text="最後更新")
        
        self.member_tree.column("id", width=50, anchor=tk.CENTER)
        self.member_tree.column("name", width=150)
        self.member_tree.column("samples", width=80, anchor=tk.CENTER)
        self.member_tree.column("updated", width=150)
        
        scrollbar = ttk.Scrollbar(member_frame, orient=tk.VERTICAL, command=self.member_tree.yview)
        self.member_tree.configure(yscroll=scrollbar.set)
        
        self.member_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _clear_history_data(self):
        """清除歷史資料"""
        if messagebox.askyesno("確認清除", "確定要清除所有歷史資料嗎？\n這將刪除所有動作記錄和狀態快照，此操作無法復原。"):
            try:
                if self.db.clear_all_data():
                    messagebox.showinfo("成功", "歷史資料已清除")
                    self.refresh_data()
                else:
                    messagebox.showerror("錯誤", "清除失敗，請檢查資料庫連線")
            except Exception as e:
                messagebox.showerror("錯誤", f"發生錯誤: {e}")

    def _delete_selected_member(self):
        """刪除選取的成員"""
        selected = self.member_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "請先選擇要刪除的成員")
            return
            
        item = self.member_tree.item(selected[0])
        name = item['values'][1]  # 取得名稱
        
        if messagebox.askyesno("確認刪除", f"確定要刪除成員 '{name}' 嗎？\n這將移除該成員的所有 ReID 特徵向量。"):
            try:
                if self.db.delete_member(name):
                    messagebox.showinfo("成功", f"成員 '{name}' 已刪除")
                    self._refresh_member_list()
                else:
                    messagebox.showerror("錯誤", "刪除失敗")
            except Exception as e:
                messagebox.showerror("錯誤", f"發生錯誤: {e}")

    def _refresh_member_list(self):
        """重新整理成員列表"""
        try:
            members = self.db.get_all_members()
            for item in self.member_tree.get_children():
                self.member_tree.delete(item)
                
            for m in members:
                updated = m.get('updated_at', '')
                if isinstance(updated, datetime):
                    updated = self._to_local_time(updated).strftime("%Y-%m-%d %H:%M")
                    
                self.member_tree.insert("", tk.END, values=(
                    m.get('member_id'),
                    m.get('name'),
                    m.get('sample_count', 0),
                    updated
                ))
        except Exception as e:
            print(f"Error refreshing member list: {e}")

    def refresh_data(self):
        """重新整理所有資料"""
        if not self.db.is_connected:
            self.db._try_connect()
            
        stats = self.db.get_statistics()
        if stats.get("connected"):
            self.conn_status_var.set(f"🟢 已連線: {stats['database']}")
            self.conn_label.configure(foreground="green")
            self.stats_var.set(f"總記錄: {stats['total_records']} | 今日: {stats['today_records']} | 成員數: {stats['member_count']}")
            
            # 更新事件表格
            events = self.db.get_recent_events(duration_sec=3600, limit=50)
            self._update_tree(self.event_tree, events, [
                'timestamp', 'person_id', 'member_name', 'action_label', 'action_confidence', 'action_duration', 'environment', 'bbox', 'motion_magnitude'
            ])
            
            # 更新狀態表格
            states = self.db.get_member_states()
            self._update_tree(self.state_tree, states, [
                'person_id', 'member_name', 'last_seen_time', 'last_action', 'last_action_duration', 'last_location', 'last_bbox', 'is_visible'
            ])
            
            # 如果在管理分頁，也更新成員列表
            if self.notebook.select() == str(self.admin_frame):
                self._refresh_member_list()
        else:
            self.conn_status_var.set(f"🔴 連線失敗: {stats.get('error', '未知錯誤')}")
            self.conn_label.configure(foreground="red")

    def _update_tree(self, tree, data_list, keys):
        """更新 Treeview 內容"""
        # 清除舊資料
        for item in tree.get_children():
            tree.delete(item)
            
        # 插入新資料
        for data in data_list:
            values = []
            for key in keys:
                val = data.get(key, "")
                # 格式化時間
                if isinstance(val, datetime):
                    val = self._to_local_time(val).strftime("%H:%M:%S") # 簡化時間顯示
                # 格式化信心度
                elif key == 'action_confidence' and isinstance(val, float):
                    val = f"{val:.1%}"
                # 格式化環境資料
                elif key == 'environment':
                    if isinstance(val, dict):
                        val = val.get('room', '-')
                    elif isinstance(val, str): # 處理 JSON 字串
                        import json
                        try:
                            d = json.loads(val)
                            val = d.get('room', '-')
                        except:
                            val = '-'
                    else:
                        val = '-'
                # 格式化 BBox
                elif key in ('bbox', 'last_bbox'):
                    if isinstance(val, list):
                        val = f"{val}"
                    elif isinstance(val, str):
                        val = val
                    else:
                        val = "-"
                # 格式化 Motion / Duration
                elif key in ('motion_magnitude', 'action_duration', 'last_action_duration') and isinstance(val, (int, float)):
                    val = f"{val:.1f}"
                    
                values.append(val)
            tree.insert("", tk.END, values=values)

    def _auto_refresh_loop(self):
        """自動更新迴圈"""
        while self.is_running:
            try:
                self.refresh_data()
            except Exception as e:
                print(f"Refresh error: {e}")
            time.sleep(self.refresh_interval)

    def _on_close(self):
        """關閉視窗"""
        self.is_running = False
        self.db.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = MemoryVisualizer(root)
    root.mainloop()

if __name__ == "__main__":
    main()

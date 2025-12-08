import base64
import io
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import numpy as np
import serial
import serial.tools.list_ports
from PIL import Image, ImageDraw, ImageFont, ImageTk


class WE2Visualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("WiseEye2 Visualizer")
        self.root.geometry("1000x700")

        # Serial Connection
        self.serial_port = None
        self.is_connected = False
        self.read_thread = None
        self.process_thread = None
        self.stop_event = threading.Event()
        
        # Data Queue for decoupling Reader and Processor
        self.data_queue = queue.Queue()

        # Data
        self.current_image = None
        self.current_json = None
        self.fps_start_time = time.time()
        self.frame_count = 0
        self.fps = 0
        
        # Threading control
        self.ui_busy = False
        self.cached_mode = "overlay"
        self.canvas_w = 640
        self.canvas_h = 480
        self.last_reid_update = 0
        self.image_item_id = None

        # UI Setup
        self.setup_ui()
        self.refresh_ports()

    def debug_log(self, msg):
        print(f"[{time.time():.3f}] {msg}")

    def setup_ui(self):
        # Top Bar: Connection & Settings
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_combo = ttk.Combobox(top_frame, width=30)
        self.port_combo.pack(side=tk.LEFT, padx=5)
        self.port_combo.set("/dev/tty.usbmodem5A4B0478511") # Default

        self.btn_refresh = ttk.Button(top_frame, text="Refresh", command=self.refresh_ports)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)

        self.btn_connect = ttk.Button(top_frame, text="Connect", command=self.toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=5)

        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Label(top_frame, text="View Mode:").pack(side=tk.LEFT, padx=5)
        self.view_mode = tk.StringVar(value="overlay")
        self.view_mode.trace_add("write", self.on_mode_change)
        ttk.Radiobutton(top_frame, text="Original", variable=self.view_mode, value="original").pack(side=tk.LEFT)
        ttk.Radiobutton(top_frame, text="Overlay", variable=self.view_mode, value="overlay").pack(side=tk.LEFT)
        ttk.Radiobutton(top_frame, text="YOLO Only", variable=self.view_mode, value="yolo_only").pack(side=tk.LEFT)

        # Main Content
        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Image Canvas
        self.canvas_frame = ttk.Frame(content_frame, borderwidth=2, relief="sunken")
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right: Info Panel
        right_panel = ttk.Frame(content_frame, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)

        # Device Info
        device_group = ttk.LabelFrame(right_panel, text="Device Info")
        device_group.pack(fill=tk.X, pady=5)
        
        self.lbl_device_id = ttk.Label(device_group, text="ID: -")
        self.lbl_device_id.pack(anchor=tk.W, padx=5)
        
        self.lbl_model_name = ttk.Label(device_group, text="Model: -")
        self.lbl_model_name.pack(anchor=tk.W, padx=5)
        
        self.lbl_version = ttk.Label(device_group, text="Ver: -")
        self.lbl_version.pack(anchor=tk.W, padx=5)

        # Frame Info
        frame_group = ttk.LabelFrame(right_panel, text="Frame Info")
        frame_group.pack(fill=tk.X, pady=5)

        self.lbl_fps = ttk.Label(frame_group, text="FPS: 0")
        self.lbl_fps.pack(anchor=tk.W, padx=5)
        self.lbl_frame_no = ttk.Label(frame_group, text="Frame: 0")
        self.lbl_frame_no.pack(anchor=tk.W, padx=5)
        self.lbl_algo_tick = ttk.Label(frame_group, text="Algo Tick: 0 ms")
        self.lbl_algo_tick.pack(anchor=tk.W, padx=5)

        # ReID Results
        reid_group = ttk.LabelFrame(right_panel, text="ReID Results")
        reid_group.pack(fill=tk.BOTH, expand=True, pady=5)

        self.tree = ttk.Treeview(reid_group, columns=("ID", "Score"), show="headings", height=10)
        self.tree.heading("ID", text="ID")
        self.tree.heading("Score", text="Score")
        self.tree.column("ID", width=50)
        self.tree.column("Score", width=50)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.txt_vector = tk.Text(reid_group, height=10, width=30, wrap=tk.CHAR)
        self.txt_vector.pack(fill=tk.X, pady=5)
        self.txt_vector.insert(tk.END, "Select an ID to view vector...")

    def on_mode_change(self, *args):
        self.cached_mode = self.view_mode.get()

    def on_canvas_resize(self, event):
        self.canvas_w = event.width
        self.canvas_h = event.height

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.current(0)

    def toggle_connection(self):
        if not self.is_connected:
            try:
                port = self.port_combo.get()
                self.serial_port = serial.Serial(port, 921600, timeout=1)
                self.is_connected = True
                self.btn_connect.config(text="Disconnect")
                self.stop_event.clear()
                
                # Clear queue
                with self.data_queue.mutex:
                    self.data_queue.queue.clear()

                # Start Reader Thread
                self.read_thread = threading.Thread(target=self.read_serial_loop)
                self.read_thread.daemon = True
                self.read_thread.start()
                
                # Start Processor Thread
                self.process_thread = threading.Thread(target=self.process_data_loop)
                self.process_thread.daemon = True
                self.process_thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            self.is_connected = False
            self.stop_event.set()
            if self.serial_port:
                self.serial_port.close()
            self.btn_connect.config(text="Connect")

    def read_serial_loop(self):
        self.debug_log("Serial Reader started")
        byte_buffer = b""
        while not self.stop_event.is_set() and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    # Read all available bytes
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    byte_buffer += chunk
                    
                    # Efficiently split by newline
                    if b'\n' in byte_buffer:
                        lines = byte_buffer.split(b'\n')
                        # The last element is the incomplete part (or empty if ends with \n)
                        byte_buffer = lines.pop() 
                        
                        for line_bytes in lines:
                            # Push RAW BYTES to queue. Do NOT decode here.
                            # Keep Reader Thread as fast as possible to prevent buffer overflow.
                            if line_bytes:
                                self.data_queue.put(line_bytes)
                else:
                    time.sleep(0.001) # Minimal sleep
            except Exception as e:
                self.debug_log(f"Serial Error: {e}")
                break
        self.debug_log("Serial Reader ended")

    def process_data_loop(self):
        self.debug_log("Processor started")
        while not self.stop_event.is_set():
            try:
                # Get raw bytes from queue
                line_bytes = self.data_queue.get(timeout=0.1)
                
                # Decode here in the Processor Thread
                try:
                    line = line_bytes.decode('utf-8').strip()
                    self.process_line(line)
                except UnicodeDecodeError:
                    # self.debug_log("Decode Error")
                    pass
                
            except queue.Empty:
                continue
            except Exception as e:
                self.debug_log(f"Processor Error: {e}")
        self.debug_log("Processor ended")

    def process_line(self, line):
        line = line.strip()
        if not line.startswith('{'):
            return

        try:
            data = json.loads(line)
            
            # Support both old and new format
            inner_data = data
            if data.get("name") == "INVOKE" and "data" in data:
                inner_data = data["data"]

            # DEBUG: Print received data structure (hiding image content)
            # debug_data = inner_data.copy()
            # if "image" in debug_data:
            #     debug_data["image"] = f"<base64_len_{len(debug_data['image'])}>"
            # print(f"[RX Data] {json.dumps(debug_data)}")
            
            # Check for keypoints
            if "keypoints" in inner_data and inner_data["keypoints"]:
                     print(f"[Success] Parsed frame with {len(inner_data['keypoints'])} people.")

            if "image" in inner_data:
                    # Decode image in thread to save UI time
                    img_b64 = inner_data.get("image", "")
                    if img_b64:
                        try:
                            # self.debug_log("Decoding image...")
                            img_bytes = base64.b64decode(img_b64)
                            np_arr = np.frombuffer(img_bytes, np.uint8)
                            img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                            
                            if img_cv is not None:
                                # --- HEAVY PROCESSING IN BACKGROUND THREAD ---
                                mode = self.cached_mode
                                
                                if mode == "yolo_only":
                                    draw_img = np.zeros_like(img_cv)
                                else:
                                    draw_img = img_cv.copy()

                                if mode != "original":
                                    self.draw_yolo_cv(draw_img, inner_data)

                                # Resize
                                cw, ch = self.canvas_w, self.canvas_h
                                if cw > 1 and ch > 1:
                                    h, w = draw_img.shape[:2]
                                    scale = min(cw/w, ch/h)
                                    nw, nh = int(w*scale), int(h*scale)
                                    if nw > 0 and nh > 0:
                                        draw_img = cv2.resize(draw_img, (nw, nh), interpolation=cv2.INTER_LINEAR)

                                # Convert to RGB
                                img_rgb = cv2.cvtColor(draw_img, cv2.COLOR_BGR2RGB)
                                final_image = Image.fromarray(img_rgb)
                                
                                # Schedule UI Update with ready-to-display image
                                self.root.after(0, self.update_ui, inner_data, final_image)
                            else:
                                self.debug_log("cv2.imdecode returned None")
                        except Exception as e:
                            self.debug_log(f"Image Processing Error in Thread: {e}")
        except json.JSONDecodeError as e:
            self.debug_log(f"JSON Parse Error: {e}. Line length: {len(line)}")
            # Optional: Print start/end of line to debug truncation
            if len(line) > 100:
                self.debug_log(f"Line start: {line[:50]}...")
                self.debug_log(f"Line end: ...{line[-50:]}")
        except Exception as e:
            self.debug_log(f"General Parse Error: {e}")

    def update_ui(self, data, final_image):
        start_time = time.time()
        try:
            # Update FPS
            self.frame_count += 1
            if time.time() - self.fps_start_time >= 1.0:
                self.fps = self.frame_count
                self.frame_count = 0
                self.fps_start_time = time.time()
                self.lbl_fps.config(text=f"FPS: {self.fps}")
                self.debug_log(f"FPS: {self.fps}")

            # Update Info
            if "frame_info" in data:
                self.lbl_frame_no.config(text=f"Frame: {data['frame_info'].get('frame_no', 0)}")
                self.lbl_algo_tick.config(text=f"Algo Tick: {data['frame_info'].get('algo_tick', 0)} ms")

            if "basic_info" in data:
                basic = data["basic_info"]
                self.lbl_device_id.config(text=f"ID: {basic.get('device_id', '-')}")
                self.lbl_model_name.config(text=f"Model: {basic.get('name', '-')}")
                self.lbl_version.config(text=f"Ver: {basic.get('ver', '-')}")

            # Display Image (Fast)
            t0 = time.time()
            self.display_image_fast(final_image)
            t1 = time.time()
            if t1 - t0 > 0.05:
                self.debug_log(f"Canvas update slow: {t1-t0:.3f}s")

            # Update ReID Table
            t2 = time.time()
            self.update_reid_table(data)
            t3 = time.time()
            if t3 - t2 > 0.05:
                self.debug_log(f"ReID update slow: {t3-t2:.3f}s")

        except Exception as e:
            self.debug_log(f"UI Update Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.ui_busy = False
            duration = time.time() - start_time
            if duration > 0.05:
                self.debug_log(f"Slow UI Update: {duration:.3f}s")

    def display_image_fast(self, image):
        # Image is already resized by OpenCV
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, image=self.tk_image, anchor=tk.CENTER)


    def draw_yolo_cv(self, img, data):
        try:
            keypoints_list = data.get("keypoints", [])
            
            # DEBUG: Always print keypoints status
            if not keypoints_list:
                print(f"[Draw] No 'keypoints' found. Keys: {list(data.keys())}")
            else:
                print(f"[Draw] Processing {len(keypoints_list)} people.")

            if not keypoints_list:
                return

            # self.debug_log(f"Drawing {len(keypoints_list)} people")

            # COCO Keypoint connections
            skeleton = [
                (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
                (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
            ]
            
            for idx, person in enumerate(keypoints_list):
                if not person: continue
                
                # Box is the first element: [x, y, w, h, score, target]
                if len(person) < 1: 
                    self.debug_log(f"Person {idx} data too short: {person}")
                    continue
                
                box = person[0]
                
                # Safe unpacking for Box
                if len(box) >= 6:
                    x, y, w, h, score, target = box[:6]
                    # Ensure integers
                    x, y, w, h = int(x), int(y), int(w), int(h)
                    
                    # Draw Box
                    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 0, 255), 2) # Red box
                    cv2.putText(img, f"ID: {idx} ({int(score)}%)", (x, y-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                    # Draw Keypoints
                    kpts = person[1:]
                    parsed_kpts = []
                    
                    for i, kp in enumerate(kpts):
                        # Handle potential double nesting
                        if len(kp) == 1 and isinstance(kp[0], list):
                            kp = kp[0]
                        
                        if len(kp) >= 4:
                            kp_x, kp_y, kp_s, kp_t = kp[:4]
                            parsed_kpts.append((int(kp_x), int(kp_y), kp_s))
                            
                            if kp_s > 0: # Threshold
                                cv2.circle(img, (int(kp_x), int(kp_y)), 3, (0, 255, 255), -1) # Yellow
                        else:
                            parsed_kpts.append((0, 0, 0))

                    # Draw Skeleton
                    for p1, p2 in skeleton:
                        if p1 < len(parsed_kpts) and p2 < len(parsed_kpts):
                            kp1 = parsed_kpts[p1]
                            kp2 = parsed_kpts[p2]
                            
                            if kp1[2] > 0 and kp2[2] > 0: # Check scores
                                cv2.line(img, (kp1[0], kp1[1]), (kp2[0], kp2[1]), (0, 255, 0), 2) # Green
                else:
                    self.debug_log(f"Invalid box format: {box}")
        except Exception as e:
            self.debug_log(f"Error in draw_yolo_cv: {e}")
            import traceback
            traceback.print_exc()


    def display_image_fast(self, image):
        # Image is already resized by OpenCV
        self.tk_image = ImageTk.PhotoImage(image)
        
        if self.image_item_id is None:
            self.canvas.delete("all")
            self.image_item_id = self.canvas.create_image(
                self.canvas.winfo_width()//2, 
                self.canvas.winfo_height()//2, 
                image=self.tk_image, 
                anchor=tk.CENTER
            )
        else:
            self.canvas.itemconfig(self.image_item_id, image=self.tk_image)

    def update_reid_table(self, data):
        # Throttle updates to 2Hz (every 0.5s)
        if time.time() - self.last_reid_update < 0.5:
            return
        self.last_reid_update = time.time()

        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        reid_results = data.get("reid_results", [])
        self.current_reid_data = reid_results
        
        if len(reid_results) > 100:
             self.debug_log(f"Warning: Large ReID data size: {len(reid_results)}")

        # Populate tree (Limit to 20 items to prevent freezing)
        limit = min(len(reid_results), 20)
        for i in range(limit):
            self.tree.insert("", "end", iid=str(i), values=(f"Person {i}", "N/A"))

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            if idx < len(self.current_reid_data):
                vector = self.current_reid_data[idx]
                self.txt_vector.delete("1.0", tk.END)
                self.txt_vector.insert(tk.END, str(vector))

if __name__ == "__main__":
    root = tk.Tk()
    app = WE2Visualizer(root)
    root.mainloop()

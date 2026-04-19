# NOMI

NOMI 是一個基於 Himax WiseEye2 (Grove Vision AI V2) + ESP32-C3 的家庭智能感知系統。

這份 README 專注在兩件事：
1. 把 NOMI 主程式與模型刷進 WE2
2. 把 ESP Forwarder 刷進 ESP32-C3

---

## 專案結構

- `nomi_host/`: 主機端 orchestrator、記憶層、控制面板
- `nomi_evaluation/`: 模擬與評估工具
- `EPII_CM55M_APP_S/`: WE2 韌體原始碼
- `we2_image_gen_local/`: WE2 映像打包工具
- `model_zoo/`: NOMI 使用的模型
- `esp_forwarder/`: ESP32-C3 資料轉發韌體
- `xmodem/`: WE2 刷機腳本

---

## 0. 先決條件

### 硬體

- Grove Vision AI Module V2 (WiseEye2)
- XIAO ESP32-C3
- USB 線材

### 軟體

- Python 3
- GNU Make
- Arm GNU Toolchain (arm-none-eabi)
- PlatformIO (for ESP32-C3)

安裝 xmodem 依賴：

```bash
pip install -r xmodem/requirements.txt
```

### 0.1 Arm GNU Toolchain 與基礎依賴設定 (保留舊版流程)

如果你是第一次在新環境建置 WE2，建議先完成以下步驟。

Step 1: 安裝 `make`

Ubuntu / Debian:

```bash
sudo apt install make
```

Step 2: 下載 Arm GNU Toolchain

```bash
cd ~
wget https://developer.arm.com/-/media/Files/downloads/gnu/13.2.rel1/binrel/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi.tar.xz
```

Step 3: 解壓縮

```bash
tar -xvf arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi.tar.xz
```

Step 4: 加到 PATH

```bash
export PATH="$HOME/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi/bin:$PATH"
```

如果你是 macOS，且 shell 不是 `bash`，可把同一行加入 `~/.zshrc` 後重新載入：

```bash
echo 'export PATH="$HOME/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Step 5: 取得原始碼

```bash
git clone --recursive https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2.git
cd Seeed_Grove_Vision_AI_Module_V2
```

如果你已經在本 repo 中操作，可略過 Step 5。

### 0.2 macOS 補充：GNU Make 設定

macOS 預設的 `make` 可能不是 GNU Make；建議先確認：

```bash
make --version
```

若不是 GNU Make：

```bash
brew install make
```

安裝後可用 `gmake`，也可加入 alias：

```bash
echo "alias make='gmake'" >> ~/.zshrc
source ~/.zshrc
```

---

## 1. 建置 WE2 韌體映像 (output.img)

若你已經有 `we2_image_gen_local/output_case1_sec_wlcsp/output.img`，可直接跳到下一節。

### Step 1: 編譯 WE2 韌體

```bash
cd EPII_CM55M_APP_S
make clean
make
```

輸出 ELF 位置：

```text
EPII_CM55M_APP_S/obj_epii_evb_icv30_bdv10/gnu_epii_evb_WLCSP65/EPII_CM55M_gnu_epii_evb_WLCSP65_s.elf
```

### Step 2: 產生 output.img

macOS (Apple Silicon):

```bash
cd ../we2_image_gen_local
cp ../EPII_CM55M_APP_S/obj_epii_evb_icv30_bdv10/gnu_epii_evb_WLCSP65/EPII_CM55M_gnu_epii_evb_WLCSP65_s.elf input_case1_secboot/
./we2_local_image_gen_macOS_arm64 project_case1_blp_wlcsp.json
```

Linux:

```bash
cd ../we2_image_gen_local
cp ../EPII_CM55M_APP_S/obj_epii_evb_icv30_bdv10/gnu_epii_evb_WLCSP65/EPII_CM55M_gnu_epii_evb_WLCSP65_s.elf input_case1_secboot/
./we2_local_image_gen project_case1_blp_wlcsp.json
```

輸出映像：

```text
we2_image_gen_local/output_case1_sec_wlcsp/output.img
```

---

## 2. 刷入 NOMI 主程式到 WE2 (含模型)

以下指令會同時刷入：
- 主程式映像 `output.img`
- YOLOv8 pose 模型到 `0x3BB000`
- person reid 模型到 `0x600000`

請先進入映像資料夾：

```bash
cd we2_image_gen_local
```

然後執行（依你的實機序列埠替換 `--port`）：

```bash
python ../xmodem/xmodem_send.py --port=/dev/tty.usbmodem5A4B0478511 --baudrate=921600 --protocol=xmodem --file=output_case1_sec_wlcsp/output.img --model="../model_zoo/tflm_yolov8_pose/yolov8n_pose_256_vela_3_9_0x3BB000.tflite 0x3BB000 0x00000" --model="../model_zoo/person_reid_int8_vela_64_0x600000.tflite 0x600000 0x00000"
```

### 刷機注意事項

- 先關閉任何占用序列埠的工具（例如 minicom、screen、Arduino Serial Monitor）
- 刷機開始後，依提示按 WE2 的 reset
- 若埠名不確定，可先執行：

```bash
ls /dev/tty.usbmodem*
```

- 若系統沒有 `python` 指令，請改用 `python3` 執行同一條刷機命令

- 若傳輸中斷，重新執行同一條指令即可

---

## 3. 刷入 ESP32-C3 (ESP Forwarder)

ESP Forwarder 會讀取 WE2 輸出，透過 Wi-Fi 轉發到主機端。

### 3.1 接線

- WE2 VCC -> ESP32-C3 3V3
- WE2 GND -> ESP32-C3 GND
- WE2 TX -> ESP32-C3 GPIO20 (RX)
- WE2 RX -> ESP32-C3 GPIO21 (TX)

### 3.2 PlatformIO 刷機 (建議)

```bash
cd esp_forwarder
pio run --target upload
pio device monitor
```

如果你有改 `esp_forwarder/data/index.html`，先執行：

```bash
cd esp_forwarder
python3 convert_html.py
pio run --target upload
```

### 3.3 首次設定流程

1. ESP32-C3 開機後，連上 AP `NOMI-Setup`
2. 打開 `http://192.168.4.1/`
3. 設定 Wi-Fi 與主機端 IP/Port
4. 成功連線後可改用 `http://nomi.local/` 管理

---

## 4. 啟動主機端

主機端啟動與設定請看：

- [nomi_host/README.md](nomi_host/README.md)

---

## 5. 故障排除

### WE2 無法刷機

- 確認使用正確序列埠
- 確認 baud rate 為 `921600`
- 確認沒有其他程式佔用該埠
- 重按 reset 後重試

### ESP32-C3 看不到資料

- 確認 WE2 與 ESP32-C3 UART 交叉接線正確
- 確認 ESP32-C3 已連上 Wi-Fi
- 確認主機端服務與 Port 正在監聽

---

## License

本專案沿用原始倉庫授權，詳見 [LICENSE](LICENSE)。

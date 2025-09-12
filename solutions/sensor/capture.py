#!/usr/bin/env python3
"""
CLI tool: Receive images from serial port and save as .raw files
Usage:
    python recv_image_raw.py --port /dev/ttyUSB0 --baud 115200 --outdir ./images
"""


import argparse
import serial
import struct
import os
import time
from datetime import datetime

FRAME_HEADER = 0xAA55AA55
FRAME_FOOTER = 0x55AA55AA

HEADER_FMT = '<I I H H I H H'  # header, frame_id, width, height, data_size, checksum, reserved
HEADER_SIZE = struct.calcsize(HEADER_FMT)
FOOTER_FMT = '<I'
FOOTER_SIZE = struct.calcsize(FOOTER_FMT)

def recv_exact(ser, size, timeout=10):
    """Read exactly 'size' bytes from serial, with timeout."""
    buf = b''
    start = time.time()
    while len(buf) < size:
        chunk = ser.read(size - len(buf))
        if not chunk:
            if time.time() - start > timeout:
                raise TimeoutError('Serial timeout')
            continue
        buf += chunk
    return buf

def find_frame_header(ser, timeout=10):
    """Find the frame header in the serial stream using a sliding window."""
    buf = b''
    start = time.time()
    while True:
        b = ser.read(1)
        if not b:
            if time.time() - start > timeout:
                raise TimeoutError('No frame header found')
            continue
        buf += b
        if len(buf) > 4:
            buf = buf[-4:]
        if len(buf) == 4 and struct.unpack('<I', buf)[0] == FRAME_HEADER:
            print(f"[SYNC] Frame header found at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
            return

def main():
    parser = argparse.ArgumentParser(description='Receive images from serial and save as .raw/.pgm')
    parser.add_argument('--port', required=True, help='Serial port, e.g. /dev/ttyUSB0')
    parser.add_argument('--baud', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--outdir', default='./images', help='Output directory')
    parser.add_argument('--timeout', type=int, default=5, help='Timeout seconds for frame (default: 5)')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f'[INFO] Listening on {args.port} at {args.baud} baud...')
    last_frame_time = time.time()
    frame_idx = 0
    while True:
        try:
            # Skip all non-header content
            find_frame_header(ser, timeout=args.timeout)
            # Read the rest of the header
            rest = recv_exact(ser, HEADER_SIZE - 4, timeout=args.timeout)
            header_tuple = struct.unpack('<I H H I H H', rest)
            frame_id, width, height, data_size, checksum, reserved = header_tuple
            print(f'[FRAME] id={frame_id} size={width}x{height} bytes={data_size} checksum={checksum}')
            img_data = recv_exact(ser, data_size, timeout=args.timeout)
            print(f'[DATA] Received {len(img_data)} bytes')
            footer = recv_exact(ser, FOOTER_SIZE, timeout=args.timeout)
            (footer_val,) = struct.unpack('<I', footer)
            if footer_val != FRAME_FOOTER:
                print('[ERROR] Frame footer mismatch, resync to next frame header')
                continue
            calc_sum = sum(img_data) & 0xFFFF
            if calc_sum != checksum:
                print(f'[ERROR] Checksum error: got {calc_sum}, expected {checksum}, skip')
                continue
            # Only save when there is data, and use timestamp as filename
            if img_data:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename_raw = f'{args.outdir}/{ts}.raw'
                with open(filename_raw, 'wb') as f:
                    f.write(img_data)
                filename_pgm = f'{args.outdir}/{ts}.pgm'
                with open(filename_pgm, 'wb') as f:
                    header = f'P5\n{width} {height}\n255\n'.encode('ascii')
                    f.write(header)
                    f.write(img_data)
                print(f'[SAVE] {filename_raw} and {filename_pgm} saved')
            last_frame_time = time.time()
            frame_idx = frame_id + 1
        except TimeoutError as e:
            now = time.time()
            if now - last_frame_time > args.timeout:
                # Do not save empty file when there is no data
                print(f'[TIMEOUT] No frame, not saved')
                last_frame_time = now
                frame_idx += 1
            else:
                print(f'[ERROR] {e}')
            continue
        except Exception as e:
            print(f'[ERROR] {e}')
            continue

if __name__ == '__main__':
    main()

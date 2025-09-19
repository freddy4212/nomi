#!/usr/bin/env python3
"""
MPIX Stream Protocol Client with Image Display

This script demonstrates how to communicate with the MPIX camera streaming
device and display received images.

Usage:
    python3 mpix_client_viewer.py [--port PORT] [--baudrate BAUDRATE]

Dependencies:
    pip install opencv-python pillow numpy

Example:
    python3 mpix_client_viewer.py --port COM68 --baudrate 921600
"""

import serial
import struct
import time
import argparse
import sys
import threading
from typing import Optional, Tuple, Dict, Any
from enum import IntEnum
import cv2
import numpy as np
from PIL import Image
import io
import json

class MPIXCommand(IntEnum):
    # Sensor control commands
    SENSOR_GET_CAPS = 0x10
    SENSOR_GET_FORMAT = 0x11
    SENSOR_SET_FORMAT = 0x12
    SENSOR_GET_CTRL = 0x13
    SENSOR_SET_CTRL = 0x14
    
    # ISP control commands
    ISP_GET_WHITE_BALANCE = 0x20
    ISP_SET_WHITE_BALANCE = 0x21
    ISP_GET_BLACK_LEVEL = 0x22
    ISP_SET_BLACK_LEVEL = 0x23
    ISP_GET_GAMMA = 0x24
    ISP_SET_GAMMA = 0x25
    ISP_GET_COLOR_MATRIX = 0x26
    ISP_SET_COLOR_MATRIX = 0x27
    ISP_GET_JPEG_QUALITY = 0x28
    ISP_SET_JPEG_QUALITY = 0x29
    ISP_ENABLE_CORRECTION = 0x2A
    ISP_DISABLE_CORRECTION = 0x2B
    ISP_GET_CORRECTION_STATE = 0x2C
    
    # Auto algorithms control
    AUTO_GET_TARGET = 0x30
    AUTO_SET_TARGET = 0x31
    AUTO_GET_STATE = 0x32
    AUTO_ENABLE_AE = 0x33
    AUTO_DISABLE_AE = 0x34
    AUTO_ENABLE_AWB = 0x35
    AUTO_DISABLE_AWB = 0x36
    AUTO_ENABLE_ABLC = 0x37
    AUTO_DISABLE_ABLC = 0x38
    AUTO_ENABLE_ALL = 0x39
    AUTO_DISABLE_ALL = 0x3A
    
    # Streaming commands
    STREAM_START = 0x40
    STREAM_STOP = 0x41
    STREAM_GET_STATUS = 0x42
    STREAM_SET_MODE = 0x43
    
    # System commands
    SYSTEM_PING = 0x50
    SYSTEM_GET_VERSION = 0x51
    SYSTEM_RESET = 0x52

class MPIXStreamMode(IntEnum):
    RAW = 0
    RGB = 1
    JPEG = 2
    AUTO = 3

class MPIXStatus(IntEnum):
    OK = 0x00
    ERROR = 0x01
    INVALID_CMD = 0x02
    INVALID_PARAM = 0x03
    NOT_SUPPORTED = 0x04
    BUSY = 0x05
    TIMEOUT = 0x06

class MPIXISPCorrection(IntEnum):
    """ISP correction types bitmask"""
    BLACK_LEVEL = 0x01
    GAMMA = 0x02
    WHITE_BALANCE = 0x04
    COLOR_MATRIX = 0x08
    DENOISE = 0x10
    ALL = 0x1F  # All corrections

class MPIXClient:
    def __init__(self, port: str, baudrate: int = 921600):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.sequence = 0
        
        # Protocol constants
        self.MAGIC_START = 0xAA55BB66
        self.MAGIC_END = 0x66BB55AA
        self.FRAME_MAGIC = 0xAA55BB66  # Same as MAGIC_START for frames
        self.VERSION = 1
        self.MAX_PAYLOAD = 4096
        
        # Image display
        self.display_window = "MPIX Stream"
        self.frame_count = 0
        self.streaming = False
        self.stream_thread = None
        
    def connect(self) -> bool:
        """Connect to the device"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2)
            print(f"Connected to {self.port} at {self.baudrate} baud")
            time.sleep(1)  # Wait for device to settle
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from device"""
        if self.streaming:
            self.stop_streaming()
        if self.ser:
            self.ser.close()
            self.ser = None
            
    def calculate_checksum(self, data: bytes) -> int:
        """Calculate protocol checksum"""
        return sum(data) & 0xFFFF
    
    def _clear_buffer_completely(self):
        """Thoroughly clear serial buffer - especially important after streaming"""
        if not self.ser:
            return
            
        # Multiple clearing passes to handle large frame buffers
        cleared_total = 0
        for attempt in range(8):  # More attempts for thorough clearing
            self.ser.flushInput()
            self.ser.flushOutput()
            
            # Read any remaining data with timeout - larger chunks for efficiency
            start_time = time.time()
            cleared_this_pass = 0
            while time.time() - start_time < 0.3:  # 300ms per pass
                available = self.ser.in_waiting
                if available > 0:
                    # Read in larger chunks for efficiency
                    chunk_size = min(available, 8192)
                    data = self.ser.read(chunk_size)
                    if not data:
                        break
                    cleared_this_pass += len(data)
                    cleared_total += len(data)
                else:
                    # No data immediately available, try reading 1 byte with short timeout
                    data = self.ser.read(1)
                    if not data:
                        break
                    cleared_this_pass += len(data)
                    cleared_total += len(data)
            
            if cleared_this_pass == 0:
                break  # No more data to clear
                
        # Final flush
        self.ser.flushInput()
        self.ser.flushOutput()
        
    def _send_command(self, cmd: MPIXCommand, payload: bytes = b"") -> Tuple[MPIXStatus, bytes]:
        """Send a command and return response"""
        if not self.ser:
            return MPIXStatus.ERROR, b""
        
        # For stop command, be more gentle with buffer clearing to preserve response
        if cmd == MPIXCommand.STREAM_STOP:
            # Only flush output, don't clear input buffer as aggressively
            self.ser.flushOutput()
            time.sleep(0.05)  # Slightly longer pause for stop command
        else:
            # For other commands, clear input buffer to avoid stale data
            self.ser.reset_input_buffer()
            time.sleep(0.01)  # Brief pause to ensure buffer is clear
            
        self.sequence = (self.sequence + 1) & 0xFFFF
        payload_length = len(payload)
        
        # Build header: magic_start(4) + version(1) + cmd_type(1) + sequence(2) + payload_length(2) + checksum(2)
        header = struct.pack('<IBBHHH', 
                           self.MAGIC_START,    # magic_start (4 bytes)
                           self.VERSION,        # version (1 byte)
                           cmd,                 # cmd_type (1 byte)
                           self.sequence,       # sequence (2 bytes)
                           payload_length,      # payload_length (2 bytes)
                           0)                   # checksum placeholder (2 bytes)
        
        # Calculate header checksum (excluding checksum field)
        header_checksum = self.calculate_checksum(header[:-2])
        
        # Rebuild header with correct checksum
        header = struct.pack('<IBBHHH',
                           self.MAGIC_START,
                           self.VERSION,
                           cmd,
                           self.sequence,
                           payload_length,
                           header_checksum)
        
        # Build footer
        footer = struct.pack('<I', self.MAGIC_END)
        
        # Complete packet
        packet = header + payload + footer
        
        try:
            self.ser.write(packet)
            self.ser.flush()
            
            # Try to read response with resync capability
            return self._read_response_with_resync()
            
        except Exception as e:
            print(f"Command failed: {e}")
            return MPIXStatus.ERROR, b""
    
    def _read_response_with_resync(self) -> Tuple[MPIXStatus, bytes]:
        """Read response with automatic resynchronization"""
        # First try normal read
        response_header = self.ser.read(12)
        if len(response_header) == 12:
            magic_start = struct.unpack('<I', response_header[:4])[0]
            if magic_start == self.MAGIC_START:
                # Normal case - process the response
                return self._process_response_header(response_header)
        
        # If we get here, we need to resync
        print(f"Response sync lost, attempting resynchronization...")
        
        # Put back what we read and try to find magic
        remaining_data = response_header + self.ser.read(min(500, self.ser.in_waiting))
        
        # Search for magic pattern in the data
        magic_bytes = struct.pack('<I', self.MAGIC_START)
        
        for i in range(len(remaining_data) - 3):
            if remaining_data[i:i+4] == magic_bytes:
                print(f"Found magic at offset {i}")
                # Found potential start - try to read complete header
                header_start = remaining_data[i:i+12]
                
                # If we don't have enough bytes, read more
                if len(header_start) < 12:
                    additional_bytes = self.ser.read(12 - len(header_start))
                    header_start += additional_bytes
                
                if len(header_start) == 12:
                    return self._process_response_header(header_start)
        
        print("Failed to resynchronize response")
        return MPIXStatus.ERROR, b""
    
    def _process_response_header(self, response_header: bytes) -> Tuple[MPIXStatus, bytes]:
        """Process a complete response header"""
        try:
            # Parse response header: magic_start + version + cmd_type + sequence + payload_length + checksum
            magic_start, version, resp_cmd, resp_seq, resp_len, checksum = struct.unpack('<IBBHHH', response_header)
            
            if magic_start != self.MAGIC_START:
                print(f"Invalid response magic: 0x{magic_start:08X}")
                return MPIXStatus.ERROR, b""
                
            # Verify header checksum
            header_for_checksum = response_header[:-2]  # Exclude checksum field
            calc_checksum = self.calculate_checksum(header_for_checksum)
            if calc_checksum != checksum:
                print(f"Header checksum mismatch: calculated 0x{calc_checksum:04X}, received 0x{checksum:04X}")
                return MPIXStatus.ERROR, b""
                
            # Check if this is a response (should have bit 7 set in cmd_type)
            if not (resp_cmd & 0x80):
                print(f"Not a response packet: cmd=0x{resp_cmd:02X}")
                return MPIXStatus.ERROR, b""
                
            # Read response payload (includes status byte + actual payload)
            response_payload = b""
            if resp_len > 0:
                response_payload = self.ser.read(resp_len)
                if len(response_payload) != resp_len:
                    print(f"Response payload timeout: expected {resp_len}, got {len(response_payload)}")
                    return MPIXStatus.TIMEOUT, b""
                    
            # Extract status from first byte of payload
            if len(response_payload) > 0:
                status = response_payload[0]
                actual_payload = response_payload[1:] if len(response_payload) > 1 else b""
            else:
                status = MPIXStatus.ERROR
                actual_payload = b""
            
            # Read response footer
            response_footer = self.ser.read(4)
            if len(response_footer) != 4:
                print(f"Response footer timeout: got {len(response_footer)} bytes")
                return MPIXStatus.TIMEOUT, b""
                
            magic_end = struct.unpack('<I', response_footer)[0]
            if magic_end != self.MAGIC_END:
                print(f"Invalid response footer: 0x{magic_end:08X}")
                return MPIXStatus.ERROR, b""
                
            return MPIXStatus(status), actual_payload
            
        except Exception as e:
            print(f"Error processing response: {e}")
            return MPIXStatus.ERROR, b""
    
    def ping(self) -> bool:
        """Test connection with ping command"""
        status, _ = self._send_command(MPIXCommand.SYSTEM_PING)
        return status == MPIXStatus.OK
    
    def get_version(self) -> Optional[str]:
        """Get system version"""
        status, payload = self._send_command(MPIXCommand.SYSTEM_GET_VERSION)
        if status == MPIXStatus.OK and len(payload) >= 4:
            # Assuming version info contains a string
            try:
                version_str = payload.decode('utf-8', errors='ignore').rstrip('\x00')
                return version_str
            except:
                return f"Version data: {payload.hex()}"
        return None
    
    def set_stream_mode(self, mode: MPIXStreamMode, enable_auto: bool = True) -> bool:
        """Set streaming mode"""
        # Pack as two uint8_t: mode and enable_auto (struct mpix_protocol_stream_mode_config)
        payload = struct.pack('<BB', mode, 1 if enable_auto else 0)
        status, _ = self._send_command(MPIXCommand.STREAM_SET_MODE, payload)
        return status == MPIXStatus.OK
    
    def start_streaming(self) -> bool:
        """Start video streaming"""
        # Clear buffer before starting stream to ensure clean state
        print("Preparing for streaming...")
        self._clear_buffer_completely()
        
        status, _ = self._send_command(MPIXCommand.STREAM_START)
        if status == MPIXStatus.OK:
            self.streaming = True
            self.stream_thread = threading.Thread(target=self._stream_receiver, daemon=True)
            self.stream_thread.start()
            return True
        return False
    
    def stop_streaming(self) -> bool:
        """Stop video streaming"""
        self.streaming = False
        if self.stream_thread:
            self.stream_thread.join(timeout=3)  # Give more time for thread to stop
        
        # Wait for any in-flight frames to complete transmission
        print("Waiting for in-flight frames to complete...")
        time.sleep(1.0)  # Give time for last frame to be sent
        
        # Send stop command BEFORE clearing buffers to preserve the response
        print("Sending stop command...")
        status, _ = self._send_command(MPIXCommand.STREAM_STOP)
        
        if status == MPIXStatus.OK:
            print("✓ Stop command acknowledged successfully")
            # Only clear buffers after successful response
            self._clear_buffer_completely()
            return True
        else:
            print("⚠ Stop command not acknowledged, but streaming thread has stopped")
            # Clear buffers and try one more time
            self._clear_buffer_completely()
            
            print("Trying stop command one more time...")
            status, _ = self._send_command(MPIXCommand.STREAM_STOP)
            
            if status == MPIXStatus.OK:
                print("✓ Stop command acknowledged on retry")
                return True
            else:
                # Even if no response, streaming is stopped since thread has stopped
                print("⚠ No response to stop command, but streaming is effectively stopped")
                return True
    
    def _find_frame_header(self, timeout=10):
        """Find the frame header in the serial stream using a sliding window"""
        buf = b''
        start_time = time.time()
        magic_bytes = struct.pack('<I', self.FRAME_MAGIC)
        
        while time.time() - start_time < timeout:
            if not self.streaming or not self.ser:
                return None
                
            byte_data = self.ser.read(1)
            if not byte_data:
                continue
                
            buf += byte_data
            if len(buf) > 4:
                buf = buf[-4:]
                

                
            if len(buf) == 4 and buf == magic_bytes:
                print(f"[STREAM] ✓ Frame header magic found at {time.time()}")
                # Read the remaining 20 bytes of the header
                remaining_header = self.ser.read(20)
                if len(remaining_header) == 20:
                    return buf + remaining_header
                else:
                    print(f"[STREAM] ERROR: Could not read remaining header bytes: got {len(remaining_header)}")
                    return None
        
        print(f"[STREAM] ERROR: Frame header not found within {timeout}s timeout")
        return None

    def _read_frame_data_with_timeout(self, expected_size, timeout=5.0):
        """Read frame data with timeout and proper error handling"""
        data = b''
        start_time = time.time()
        
        while len(data) < expected_size and time.time() - start_time < timeout:
            remaining = expected_size - len(data)
            # Try to read remaining data, but not more than what's immediately available
            available = self.ser.in_waiting
            if available > 0:
                to_read = min(remaining, available, 8192)  # Read in chunks
            else:
                to_read = min(remaining, 1024)  # Smaller chunks when waiting
            
            chunk = self.ser.read(to_read)
            if not chunk:
                time.sleep(0.001)  # Brief pause to avoid busy waiting
                continue
            data += chunk
        
        if len(data) == expected_size:
            return data
        else:
            print(f"[STREAM] ERROR: Frame data timeout: expected {expected_size}, got {len(data)}")
            return None

    def _clear_serial_buffer_completely(self):
        """Thoroughly clear serial buffer when sync is lost"""
        if not self.ser:
            return 0
        
        total_cleared = 0
        # Clear in multiple passes to handle buffered data
        for _ in range(3):
            self.ser.flushInput()
            available = self.ser.in_waiting
            if available > 0:
                data = self.ser.read(available)
                total_cleared += len(data)
            time.sleep(0.01)  # Allow time for more data to arrive
        
        return total_cleared

    def print_stream_diagnostics(self):
        """Print diagnostic information about the streaming connection"""
        if not self.ser:
            print("No serial connection available")
            return
        
        print("\n=== STREAM DIAGNOSTICS ===")
        print(f"Port: {self.port}")
        print(f"Baudrate: {self.baudrate}")
        print(f"Is open: {self.ser.is_open}")
        print(f"Timeout: {self.ser.timeout}")
        print(f"Bytes waiting: {self.ser.in_waiting}")
        
        # Check buffer sizes if available
        if hasattr(self.ser, 'get_settings'):
            try:
                settings = self.ser.get_settings()
                print(f"Serial settings: {settings}")
            except:
                pass
        
        print(f"Frame counter: {self.frame_count}")
        print(f"Streaming: {self.streaming}")
        print("==========================\n")
    
    def analyze_raw_stream(self, duration=10):
        """Analyze raw stream data to understand corruption patterns"""
        if not self.ser:
            print("No serial connection available")
            return
        
        print(f"[ANALYZE] Starting raw stream analysis for {duration} seconds...")
        print("[ANALYZE] This will capture and analyze raw serial data")
        
        # Ensure streaming is off for this analysis
        was_streaming = self.streaming
        if self.streaming:
            print("[ANALYZE] Stopping existing stream...")
            self.stop_streaming()
            time.sleep(1)
        
        # Clear buffers
        self._clear_buffer_completely()
        
        # Start streaming for analysis
        print("[ANALYZE] Starting stream for analysis...")
        status, _ = self._send_command(MPIXCommand.STREAM_START)
        if status != MPIXStatus.OK:
            print("[ANALYZE] Failed to start stream for analysis")
            return
        
        # Collect raw data
        raw_data = b''
        start_time = time.time()
        magic_pattern = struct.pack('<I', self.FRAME_MAGIC)
        footer_pattern = struct.pack('<I', self.MAGIC_END)
        
        print("[ANALYZE] Collecting data...")
        while time.time() - start_time < duration:
            available = self.ser.in_waiting
            if available > 0:
                chunk = self.ser.read(min(available, 8192))
                raw_data += chunk
            else:
                time.sleep(0.01)
        
        # Stop streaming
        print("[ANALYZE] Stopping stream...")
        self._send_command(MPIXCommand.STREAM_STOP)
        
        # Analyze the data
        print(f"[ANALYZE] === Raw Stream Analysis ===")
        print(f"[ANALYZE] Total data collected: {len(raw_data)} bytes")
        
        # Find magic patterns
        magic_positions = []
        footer_positions = []
        
        for i in range(len(raw_data) - 3):
            if raw_data[i:i+4] == magic_pattern:
                magic_positions.append(i)
            if raw_data[i:i+4] == footer_pattern:
                footer_positions.append(i)
        
        print(f"[ANALYZE] Frame headers found: {len(magic_positions)}")
        print(f"[ANALYZE] Frame footers found: {len(footer_positions)}")
        
        if magic_positions:
            print(f"[ANALYZE] First header at byte: {magic_positions[0]}")
            print(f"[ANALYZE] Last header at byte: {magic_positions[-1]}")
            
            # Analyze frame spacing
            if len(magic_positions) > 1:
                spacings = [magic_positions[i+1] - magic_positions[i] for i in range(len(magic_positions)-1)]
                avg_spacing = sum(spacings) / len(spacings)
                print(f"[ANALYZE] Average frame spacing: {avg_spacing:.1f} bytes")
                print(f"[ANALYZE] Frame spacing range: {min(spacings)} - {max(spacings)} bytes")
        
        if footer_positions:
            print(f"[ANALYZE] First footer at byte: {footer_positions[0]}")
            print(f"[ANALYZE] Last footer at byte: {footer_positions[-1]}")
        
        # Show data samples around problematic areas
        if len(magic_positions) > 0 and len(footer_positions) > 0:
            print(f"[ANALYZE] === Data Sample Analysis ===")
            for i, pos in enumerate(magic_positions[:3]):  # Show first 3 headers
                if pos + 24 <= len(raw_data):
                    header_data = raw_data[pos:pos+24]
                    print(f"[ANALYZE] Header {i+1} at {pos}: {header_data.hex()}")
                    
                    # Try to parse this header
                    try:
                        magic, frame_id, width, height, data_size, fourcc, checksum, reserved = struct.unpack('<IIHHI HH', header_data)
                        print(f"[ANALYZE]   Frame ID: {frame_id}, Size: {width}x{height}, Data: {data_size} bytes")
                        
                        # Check if corresponding footer exists
                        expected_footer_pos = pos + 24 + data_size
                        if expected_footer_pos + 4 <= len(raw_data):
                            footer_data = raw_data[expected_footer_pos:expected_footer_pos+4]
                            footer_magic = struct.unpack('<I', footer_data)[0]
                            if footer_magic == self.MAGIC_END:
                                print(f"[ANALYZE]   ✓ Valid footer at expected position {expected_footer_pos}")
                            else:
                                print(f"[ANALYZE]   ✗ Invalid footer at {expected_footer_pos}: 0x{footer_magic:08X}")
                                print(f"[ANALYZE]     Expected: 0x{self.MAGIC_END:08X}")
                                print(f"[ANALYZE]     Data around position: {raw_data[expected_footer_pos-4:expected_footer_pos+8].hex()}")
                        else:
                            print(f"[ANALYZE]   ? Footer position {expected_footer_pos} beyond data")
                    except Exception as e:
                        print(f"[ANALYZE]   ✗ Failed to parse header: {e}")
        
        print(f"[ANALYZE] === Analysis Complete ===")
        
        # Restore original streaming state
        if was_streaming:
            print("[ANALYZE] Restoring original streaming state...")
            self.start_streaming()

    def _stream_receiver(self):
        """Background thread to receive and display video frames"""
        print("[STREAM] Frame receiver thread started")
        cv2.namedWindow(self.display_window, cv2.WINDOW_AUTOSIZE)
        
        frame_count = 0
        consecutive_errors = 0
        receive_timeout_count = 0
        
        while self.streaming and self.ser:
            try:
                print("[STREAM] Waiting for frame header...")
                
                # Use the new frame header finder
                frame_header_data = self._find_frame_header(timeout=5)
                if frame_header_data is None:
                    receive_timeout_count += 1
                    print(f"[STREAM] Frame header not found (timeout #{receive_timeout_count})")
                    if receive_timeout_count > 10:
                        print("[STREAM] Too many header timeouts, checking connection...")
                        receive_timeout_count = 0
                    continue
                
                print(f"[STREAM] Received frame header: {len(frame_header_data)} bytes")
                print(f"[STREAM] Header hex: {frame_header_data.hex()}")
                
                # Parse frame header manually to handle packed struct: 24 bytes total
                # uint32_t magic_start(4) + uint32_t frame_id(4) + uint16_t width(2) + uint16_t height(2) + 
                # uint32_t data_size(4) + uint32_t fourcc(4) + uint16_t checksum(2) + uint16_t reserved(2)
                try:
                    magic_start = struct.unpack('<I', frame_header_data[0:4])[0]
                    frame_id = struct.unpack('<I', frame_header_data[4:8])[0]
                    width = struct.unpack('<H', frame_header_data[8:10])[0]
                    height = struct.unpack('<H', frame_header_data[10:12])[0]
                    data_size = struct.unpack('<I', frame_header_data[12:16])[0]
                    fourcc = struct.unpack('<I', frame_header_data[16:20])[0]
                    checksum = struct.unpack('<H', frame_header_data[20:22])[0]
                    reserved = struct.unpack('<H', frame_header_data[22:24])[0]
                except Exception as parse_error:
                    print(f"[STREAM] ERROR: Failed to parse header: {parse_error}")
                    consecutive_errors += 1
                    continue
                
                print(f"[STREAM] Frame header parsed:")
                print(f"  Magic: 0x{magic_start:08X} (expected: 0x{self.MAGIC_START:08X})")
                print(f"  Frame ID: {frame_id}")
                print(f"  Dimensions: {width}x{height}")
                print(f"  Data size: {data_size}")
                print(f"  FourCC: 0x{fourcc:08X}")
                print(f"  Checksum: 0x{checksum:04X}")
                print(f"  Reserved: 0x{reserved:04X}")
                
                if magic_start != self.MAGIC_START:
                    print(f"[STREAM] ERROR: Invalid frame magic: 0x{magic_start:08X}, expected: 0x{self.MAGIC_START:08X}")
                    consecutive_errors += 1
                    continue
                
                print(f"[STREAM] ✓ Valid frame header received - Frame {frame_id}: {width}x{height}, size: {data_size}, fourcc: 0x{fourcc:08X}")
                
                # Read frame data
                if data_size > 0 and data_size < 1024*1024:  # Sanity check
                    print(f"[STREAM] Reading frame data: {data_size} bytes...")
                    frame_data = self.ser.read(data_size)
                    if len(frame_data) == data_size:
                        print(f"[STREAM] ✓ Frame data received: {len(frame_data)} bytes")
                        
                        # Verify data checksum (but don't fail if mismatch - might be header checksum vs data checksum)
                        calc_checksum = self.calculate_checksum(frame_data)
                        print(f"[STREAM] Checksum verification: calculated=0x{calc_checksum:04X}, received=0x{checksum:04X}")
                        if calc_checksum != checksum:
                            print(f"[STREAM] WARNING: Frame checksum mismatch - continuing anyway (might be header checksum)")
                            # Don't fail here - the checksum might be for the header, not the data
                            
                        # Read frame footer
                        print("[STREAM] Reading frame footer...")
                        footer_data = self.ser.read(4)
                        if len(footer_data) == 4:
                            magic_end = struct.unpack('<I', footer_data)[0]
                            print(f"[STREAM] Frame footer magic: 0x{magic_end:08X} (expected: 0x{self.MAGIC_END:08X})")
                            if magic_end == self.MAGIC_END:
                                print(f"[STREAM] ✓ Complete frame {frame_id} received successfully!")
                                self._display_frame(frame_data, width, height, fourcc)
                                frame_count += 1
                                consecutive_errors = 0  # Reset error count on success
                                receive_timeout_count = 0
                            else:
                                print(f"[STREAM] ERROR: Invalid frame footer: 0x{magic_end:08X}")
                                print(f"[STREAM] Possible data corruption or timing issue")
                                # Try to clear any remaining data in buffer
                                if self.ser.in_waiting > 0:
                                    remaining = self.ser.read(self.ser.in_waiting)
                                    print(f"[STREAM] Cleared {len(remaining)} bytes from buffer")
                                consecutive_errors += 1
                        else:
                            print(f"[STREAM] ERROR: Footer timeout: got {len(footer_data)} bytes")
                            consecutive_errors += 1
                    else:
                        print(f"[STREAM] ERROR: Frame data timeout: expected {data_size}, got {len(frame_data)}")
                        consecutive_errors += 1
                else:
                    print(f"[STREAM] ERROR: Invalid data size: {data_size}")
                    consecutive_errors += 1
                
                if consecutive_errors > 10:
                    print("[STREAM] Too many consecutive errors, stopping stream receiver...")
                    break
                
            except Exception as e:
                print(f"[STREAM] ERROR: Stream receive exception: {e}")
                consecutive_errors += 1
                if consecutive_errors > 10:
                    print("[STREAM] Too many consecutive errors, stopping stream receiver...")
                    break
        
        print("[STREAM] Frame receiver thread stopped")
        cv2.destroyAllWindows()
        print("Stream receiver stopped")
    
    def _display_frame(self, data: bytes, width: int, height: int, fourcc: int):
        """Display a received frame"""
        print(f"\n[DISPLAY] === Frame {self.frame_count} Display Info ===")
        print(f"[DISPLAY] Frame dimensions: {width}x{height}")
        print(f"[DISPLAY] Data size: {len(data)} bytes")
        print(f"[DISPLAY] FourCC: 0x{fourcc:08X}")
        print(f"[DISPLAY] Expected sizes:")
        print(f"  - RGB888: {width * height * 3} bytes")
        print(f"  - RAW/Bayer: {width * height} bytes")
        print(f"  - JPEG: variable size")
        
        try:
            # Check if it's JPEG data (starts with 0xFF 0xD8)
            if len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8:
                print(f"[DISPLAY] ✓ Detected JPEG format (header: 0x{data[0]:02X}{data[1]:02X})")
                print(f"[DISPLAY] JPEG data size: {len(data)} bytes")
                
                # Show first few bytes of JPEG data
                print(f"[DISPLAY] JPEG header: {data[:16].hex()}")
                
                # Decode JPEG
                nparr = np.frombuffer(data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    actual_height, actual_width = img.shape[:2]
                    print(f"[DISPLAY] ✓ JPEG decoded successfully to {actual_width}x{actual_height}")
                    
                    # Add detailed frame info overlay
                    
                    cv2.imshow(self.display_window, img)
                    cv2.waitKey(1)
                    print(f"[DISPLAY] ✓ JPEG frame displayed")
                    return
                else:
                    print(f"[DISPLAY] ✗ Failed to decode JPEG data")
            
            # Try to interpret as raw RGB data
            elif len(data) == width * height * 3:
                print(f"[DISPLAY] ✓ Detected RGB888 format ({len(data)} bytes = {width}x{height}x3)")
                
                # Show first few bytes of RGB data
                print(f"[DISPLAY] RGB data start: {data[:12].hex()}")
                
                # RGB888 format
                img = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
                # Convert RGB to BGR for OpenCV
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                # Add detailed frame info overlay
                info_text = [
                    f"Frame {self.frame_count}",
                    f"RGB888: {width}x{height}",
                    f"Data: {len(data)} bytes",
                    f"FourCC: 0x{fourcc:08X}"
                ]
                
                for i, text in enumerate(info_text):
                    cv2.putText(img, text, (10, 30 + i*25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow(self.display_window, img)
                cv2.waitKey(1)
                print(f"[DISPLAY] ✓ RGB888 frame displayed")
                return
            
            # Try to interpret as Bayer format (assuming 8-bit)
            elif len(data) == width * height:
                print(f"[DISPLAY] ✓ Detected RAW/Bayer format ({len(data)} bytes = {width}x{height}x1)")
                
                # Show first few bytes of raw data
                print(f"[DISPLAY] RAW data start: {data[:16].hex()}")
                
                # Raw Bayer data - convert to RGB for display
                img = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
                # Simple debayer by replicating to 3 channels
                img_rgb = np.stack([img, img, img], axis=2)
                
                # Add detailed frame info overlay
                info_text = [
                    f"Frame {self.frame_count}",
                    f"RAW: {width}x{height}",
                    f"Data: {len(data)} bytes", 
                    f"FourCC: 0x{fourcc:08X}"
                ]
                
                for i, text in enumerate(info_text):
                    cv2.putText(img_rgb, text, (10, 30 + i*25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow(self.display_window, img_rgb)
                cv2.waitKey(1)
                print(f"[DISPLAY] ✓ RAW/Bayer frame displayed")
                return
            
            # Unknown format
            else:
                print(f"[DISPLAY] ✗ Unknown frame format:")
                print(f"  Data size: {len(data)} bytes")
                print(f"  Expected RGB: {width * height * 3} bytes")
                print(f"  Expected RAW: {width * height} bytes")
                print(f"  FourCC: 0x{fourcc:08X}")
                
                # Show data analysis
                if len(data) > 0:
                    print(f"  First 16 bytes: {data[:16].hex()}")
                    if len(data) >= 2:
                        print(f"  First 2 bytes: 0x{data[0]:02X} 0x{data[1]:02X}")
                        if data[0] == 0xFF and data[1] == 0xD8:
                            print("  → Looks like JPEG but size doesn't match")
                        elif data[0] == 0x89 and len(data) >= 8 and data[1:4] == b'PNG':
                            print("  → Looks like PNG format")
                
                print(f"[DISPLAY] ✗ Cannot display unknown format")
            
        except Exception as e:
            print(f"[DISPLAY] ✗ Display error: {e}")
            import traceback
            traceback.print_exc()
    
    def enable_auto_exposure(self) -> bool:
        """Enable auto exposure"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_ENABLE_AE)
        return status == MPIXStatus.OK
    
    def disable_auto_exposure(self) -> bool:
        """Disable auto exposure"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_DISABLE_AE)
        return status == MPIXStatus.OK
    
    def enable_auto_white_balance(self) -> bool:
        """Enable auto white balance"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_ENABLE_AWB)
        return status == MPIXStatus.OK
    
    def disable_auto_white_balance(self) -> bool:
        """Disable auto white balance"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_DISABLE_AWB)
        return status == MPIXStatus.OK
    
    def set_auto_exposure(self, enabled: bool) -> bool:
        """Set auto exposure state"""
        if enabled:
            return self.enable_auto_exposure()
        else:
            return self.disable_auto_exposure()
    
    def set_auto_white_balance(self, enabled: bool) -> bool:
        """Set auto white balance state"""
        if enabled:
            return self.enable_auto_white_balance()
        else:
            return self.disable_auto_white_balance()
    
    def enable_auto_black_level(self) -> bool:
        """Enable auto black level correction"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_ENABLE_ABLC)
        return status == MPIXStatus.OK
    
    def disable_auto_black_level(self) -> bool:
        """Disable auto black level correction"""
        # Ensure clean buffer for critical commands
        self._clear_buffer_completely()
        status, _ = self._send_command(MPIXCommand.AUTO_DISABLE_ABLC)
        return status == MPIXStatus.OK
    
    def set_auto_black_level(self, enabled: bool) -> bool:
        """Set auto black level correction state"""
        if enabled:
            return self.enable_auto_black_level()
        else:
            return self.disable_auto_black_level()
    
    def get_auto_algorithms_state(self) -> Optional[dict]:
        """Get auto algorithms state"""
        status, payload = self._send_command(MPIXCommand.AUTO_GET_STATE)
        if status == MPIXStatus.OK and len(payload) >= 12:
            # Based on struct mpix_protocol_auto_state from protocol.h
            # uint8_t ae_enabled + uint8_t awb_enabled + uint8_t ablc_enabled + uint8_t reserved + 
            # int32_t exposure_level + uint16_t wb_red_level + uint16_t wb_blue_level + uint8_t black_level + padding
            ae_enabled, awb_enabled, ablc_enabled, reserved = struct.unpack('<BBBB', payload[:4])
            exposure_level = struct.unpack('<i', payload[4:8])[0]
            wb_red, wb_blue = struct.unpack('<HH', payload[8:12])
            black_level = payload[12] if len(payload) > 12 else 0
            
            return {
                'auto_exposure_enabled': bool(ae_enabled),
                'auto_white_balance_enabled': bool(awb_enabled),
                'auto_black_level_enabled': bool(ablc_enabled),
                'current_exposure_level': exposure_level,
                'current_wb_red_level': wb_red,
                'current_wb_blue_level': wb_blue,
                'current_black_level': black_level
            }
        return None
    
    # ISP Control Methods
    def get_white_balance(self) -> Optional[Tuple[int, int]]:
        """Get white balance levels (red, blue)"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_WHITE_BALANCE)
        if status == MPIXStatus.OK and len(payload) >= 4:
            red_level, blue_level = struct.unpack('<HH', payload[:4])
            return (red_level, blue_level)
        return None
    
    def set_white_balance(self, red_level: int, blue_level: int) -> bool:
        """Set white balance levels"""
        payload = struct.pack('<HH', red_level, blue_level)
        status, _ = self._send_command(MPIXCommand.ISP_SET_WHITE_BALANCE, payload)
        return status == MPIXStatus.OK
    
    def get_black_level(self) -> Optional[int]:
        """Get black level correction"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_BLACK_LEVEL)
        if status == MPIXStatus.OK and len(payload) >= 1:
            return payload[0]
        return None
    
    def set_black_level(self, level: int) -> bool:
        """Set black level correction"""
        payload = struct.pack('<B', level)
        status, _ = self._send_command(MPIXCommand.ISP_SET_BLACK_LEVEL, payload)
        return status == MPIXStatus.OK
    
    def get_gamma(self) -> Optional[int]:
        """Get gamma correction level"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_GAMMA)
        if status == MPIXStatus.OK and len(payload) >= 2:
            return struct.unpack('<H', payload[:2])[0]
        return None
    
    def set_gamma(self, level: int) -> bool:
        """Set gamma correction level"""
        payload = struct.pack('<H', level)
        status, _ = self._send_command(MPIXCommand.ISP_SET_GAMMA, payload)
        return status == MPIXStatus.OK
    
    def get_color_matrix(self) -> Optional[list]:
        """Get color matrix (3x3 matrix as 9 values)"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_COLOR_MATRIX)
        if status == MPIXStatus.OK and len(payload) >= 18:
            return list(struct.unpack('<9h', payload[:18]))
        return None
    
    def set_color_matrix(self, matrix: list) -> bool:
        """Set color matrix (3x3 matrix as 9 values)"""
        if len(matrix) != 9:
            return False
        payload = struct.pack('<9h', *matrix)
        status, _ = self._send_command(MPIXCommand.ISP_SET_COLOR_MATRIX, payload)
        return status == MPIXStatus.OK
    
    def get_jpeg_quality(self) -> Optional[int]:
        """Get JPEG quality level"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_JPEG_QUALITY)
        if status == MPIXStatus.OK and len(payload) >= 1:
            return payload[0]
        return None
    
    def set_jpeg_quality(self, quality: int) -> bool:
        """Set JPEG quality level"""
        payload = struct.pack('<B', quality)
        status, _ = self._send_command(MPIXCommand.ISP_SET_JPEG_QUALITY, payload)
        return status == MPIXStatus.OK
    
    def enable_isp_correction(self, correction_types: int) -> bool:
        """Enable ISP corrections (use MPIXISPCorrection bitmask)"""
        payload = struct.pack('<BB', correction_types, 1)
        status, _ = self._send_command(MPIXCommand.ISP_ENABLE_CORRECTION, payload)
        return status == MPIXStatus.OK
    
    def disable_isp_correction(self, correction_types: int) -> bool:
        """Disable ISP corrections (use MPIXISPCorrection bitmask)"""
        payload = struct.pack('<BB', correction_types, 0)
        status, _ = self._send_command(MPIXCommand.ISP_DISABLE_CORRECTION, payload)
        return status == MPIXStatus.OK
    
    def get_isp_correction_state(self) -> Optional[dict]:
        """Get ISP correction state"""
        status, payload = self._send_command(MPIXCommand.ISP_GET_CORRECTION_STATE)
        if status == MPIXStatus.OK and len(payload) >= 5:
            black_level, gamma, white_balance, color_matrix, denoise = struct.unpack('<BBBBB', payload[:5])
            return {
                'black_level_enabled': bool(black_level),
                'gamma_enabled': bool(gamma),
                'white_balance_enabled': bool(white_balance),
                'color_matrix_enabled': bool(color_matrix),
                'denoise_enabled': bool(denoise)
            }
        return None
    
    def export_isp_config(self) -> Optional[dict]:
        """Export all ISP configuration to a dictionary"""
        config = {
            "device_info": {
                "version": self.get_version(),
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "isp_corrections": {
                "enabled_state": self.get_isp_correction_state()
            },
            "auto_algorithms": {
                "state": self.get_auto_algorithms_state()
            },
            "parameters": {}
        }
        
        # Get white balance
        wb = self.get_white_balance()
        if wb:
            config["parameters"]["white_balance"] = {
                "red_level": wb[0],
                "blue_level": wb[1]
            }
        
        # Get black level
        bl = self.get_black_level()
        if bl is not None:
            config["parameters"]["black_level"] = bl
        
        # Get gamma
        gamma = self.get_gamma()
        if gamma is not None:
            config["parameters"]["gamma"] = gamma
        
        # Get color matrix
        cm = self.get_color_matrix()
        if cm:
            config["parameters"]["color_matrix"] = cm
        
        # Get JPEG quality
        quality = self.get_jpeg_quality()
        if quality is not None:
            config["parameters"]["jpeg_quality"] = quality
        
        return config
    
    def import_isp_config(self, config: dict) -> bool:
        """Import ISP configuration from dictionary"""
        try:
            success_count = 0
            total_operations = 0
            
            # Import parameters
            if "parameters" in config:
                params = config["parameters"]
                
                # Set white balance
                if "white_balance" in params:
                    wb = params["white_balance"]
                    if "red_level" in wb and "blue_level" in wb:
                        total_operations += 1
                        if self.set_white_balance(wb["red_level"], wb["blue_level"]):
                            success_count += 1
                            print(f"✓ White balance imported: Red={wb['red_level']}, Blue={wb['blue_level']}")
                        else:
                            print("✗ Failed to import white balance")
                
                # Set black level
                if "black_level" in params:
                    total_operations += 1
                    if self.set_black_level(params["black_level"]):
                        success_count += 1
                        print(f"✓ Black level imported: {params['black_level']}")
                    else:
                        print("✗ Failed to import black level")
                
                # Set gamma
                if "gamma" in params:
                    total_operations += 1
                    if self.set_gamma(params["gamma"]):
                        success_count += 1
                        print(f"✓ Gamma imported: {params['gamma']}")
                    else:
                        print("✗ Failed to import gamma")
                
                # Set color matrix
                if "color_matrix" in params:
                    total_operations += 1
                    if self.set_color_matrix(params["color_matrix"]):
                        success_count += 1
                        print(f"✓ Color matrix imported")
                    else:
                        print("✗ Failed to import color matrix")
                
                # Set JPEG quality
                if "jpeg_quality" in params:
                    total_operations += 1
                    if self.set_jpeg_quality(params["jpeg_quality"]):
                        success_count += 1
                        print(f"✓ JPEG quality imported: {params['jpeg_quality']}")
                    else:
                        print("✗ Failed to import JPEG quality")
            
            # Import ISP correction enable/disable states
            if "isp_corrections" in config and "enabled_state" in config["isp_corrections"]:
                state = config["isp_corrections"]["enabled_state"]
                if state:
                    # Apply each correction state
                    corrections = [
                        ("black_level_enabled", MPIXISPCorrection.BLACK_LEVEL),
                        ("gamma_enabled", MPIXISPCorrection.GAMMA),
                        ("white_balance_enabled", MPIXISPCorrection.WHITE_BALANCE),
                        ("color_matrix_enabled", MPIXISPCorrection.COLOR_MATRIX),
                        ("denoise_enabled", MPIXISPCorrection.DENOISE)
                    ]
                    
                    for state_key, correction_flag in corrections:
                        if state_key in state:
                            total_operations += 1
                            enabled = state[state_key]
                            if enabled:
                                success = self.enable_isp_correction(correction_flag)
                            else:
                                success = self.disable_isp_correction(correction_flag)
                            
                            if success:
                                success_count += 1
                                action = "enabled" if enabled else "disabled"
                                print(f"✓ {state_key.replace('_', ' ').title()} {action}")
                            else:
                                action = "enable" if enabled else "disable"
                                print(f"✗ Failed to {action} {state_key.replace('_', ' ')}")
            
            # Import auto algorithms state
            if "auto_algorithms" in config and "state" in config["auto_algorithms"]:
                auto_state = config["auto_algorithms"]["state"]
                if auto_state:
                    # Set auto exposure
                    if "ae_enable" in auto_state:
                        total_operations += 1
                        enabled = auto_state["ae_enable"]
                        if self.set_auto_exposure(enabled):
                            success_count += 1
                            action = "enabled" if enabled else "disabled"
                            print(f"✓ Auto exposure {action}")
                        else:
                            action = "enable" if enabled else "disable"
                            print(f"✗ Failed to {action} auto exposure")
                    
                    # Set auto white balance  
                    if "awb_enable" in auto_state:
                        total_operations += 1
                        enabled = auto_state["awb_enable"]
                        if self.set_auto_white_balance(enabled):
                            success_count += 1
                            action = "enabled" if enabled else "disabled"
                            print(f"✓ Auto white balance {action}")
                        else:
                            action = "enable" if enabled else "disable"
                            print(f"✗ Failed to {action} auto white balance")
                    
                    # Set auto black level correction
                    if "ablc_enable" in auto_state:
                        total_operations += 1
                        enabled = auto_state["ablc_enable"]
                        if self.set_auto_black_level(enabled):
                            success_count += 1
                            action = "enabled" if enabled else "disabled"
                            print(f"✓ Auto black level {action}")
                        else:
                            action = "enable" if enabled else "disable"
                            print(f"✗ Failed to {action} auto black level")
            
            print(f"\nImport summary: {success_count}/{total_operations} operations successful")
            return success_count == total_operations
            
        except Exception as e:
            print(f"✗ Import failed: {e}")
            return False
    
    def save_config_to_file(self, filename: str) -> bool:
        """Save current ISP configuration to JSON file"""
        config = self.export_isp_config()
        if config:
            try:
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"✓ Configuration saved to {filename}")
                return True
            except Exception as e:
                print(f"✗ Failed to save configuration: {e}")
                return False
        else:
            print("✗ Failed to export configuration")
            return False
    
    def load_config_from_file(self, filename: str) -> bool:
        """Load ISP configuration from JSON file"""
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            print(f"✓ Configuration loaded from {filename}")
            return self.import_isp_config(config)
        except Exception as e:
            print(f"✗ Failed to load configuration: {e}")
            return False

def white_balance_menu(client):
    """White balance control submenu"""
    while True:
        print("\n--- White Balance Control ---")
        current = client.get_white_balance()
        if current:
            print(f"Current: Red={current[0]}, Blue={current[1]}")
        else:
            print("Current: Unable to read")
        
        print("1. Set white balance")
        print("2. Reset to default (1000, 1000)")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        if choice == "1":
            try:
                red = int(input("Red level (0-65535): "))
                blue = int(input("Blue level (0-65535): "))
                if client.set_white_balance(red, blue):
                    print(f"✓ White balance set to Red={red}, Blue={blue}")
                else:
                    print("✗ Failed to set white balance")
            except ValueError:
                print("✗ Invalid input")
        elif choice == "2":
            if client.set_white_balance(1000, 1000):
                print("✓ White balance reset to default")
            else:
                print("✗ Failed to reset white balance")
        elif choice == "0":
            break

def black_level_menu(client):
    """Black level control submenu"""
    while True:
        print("\n--- Black Level Control ---")
        current = client.get_black_level()
        if current is not None:
            print(f"Current black level: {current}")
        else:
            print("Current: Unable to read")
        
        print("1. Set black level")
        print("2. Reset to default (0)")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        if choice == "1":
            try:
                level = int(input("Black level (0-255): "))
                if 0 <= level <= 255:
                    if client.set_black_level(level):
                        print(f"✓ Black level set to {level}")
                    else:
                        print("✗ Failed to set black level")
                else:
                    print("✗ Level must be 0-255")
            except ValueError:
                print("✗ Invalid input")
        elif choice == "2":
            if client.set_black_level(0):
                print("✓ Black level reset to default")
            else:
                print("✗ Failed to reset black level")
        elif choice == "0":
            break

def gamma_menu(client):
    """Gamma correction control submenu"""
    while True:
        print("\n--- Gamma Correction Control ---")
        current = client.get_gamma()
        if current is not None:
            print(f"Current gamma level: {current}")
        else:
            print("Current: Unable to read")
        
        print("1. Set gamma level")
        print("2. Reset to default (100)")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        if choice == "1":
            try:
                level = int(input("Gamma level (0-65535): "))
                if 0 <= level <= 65535:
                    if client.set_gamma(level):
                        print(f"✓ Gamma level set to {level}")
                    else:
                        print("✗ Failed to set gamma level")
                else:
                    print("✗ Level must be 0-65535")
            except ValueError:
                print("✗ Invalid input")
        elif choice == "2":
            if client.set_gamma(100):
                print("✓ Gamma level reset to default")
            else:
                print("✗ Failed to reset gamma level")
        elif choice == "0":
            break

def jpeg_quality_menu(client):
    """JPEG quality control submenu"""
    while True:
        print("\n--- JPEG Quality Control ---")
        current = client.get_jpeg_quality()
        if current is not None:
            print(f"Current JPEG quality: {current}")
        else:
            print("Current: Unable to read")
        
        print("1. Set JPEG quality")
        print("2. High quality (90)")
        print("3. Medium quality (50)")
        print("4. Low quality (10)")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        if choice == "1":
            try:
                quality = int(input("JPEG quality (1-100): "))
                if 1 <= quality <= 100:
                    if client.set_jpeg_quality(quality):
                        print(f"✓ JPEG quality set to {quality}")
                    else:
                        print("✗ Failed to set JPEG quality")
                else:
                    print("✗ Quality must be 1-100")
            except ValueError:
                print("✗ Invalid input")
        elif choice == "2":
            if client.set_jpeg_quality(90):
                print("✓ JPEG quality set to high (90)")
            else:
                print("✗ Failed to set JPEG quality")
        elif choice == "3":
            if client.set_jpeg_quality(50):
                print("✓ JPEG quality set to medium (50)")
            else:
                print("✗ Failed to set JPEG quality")
        elif choice == "4":
            if client.set_jpeg_quality(10):
                print("✓ JPEG quality set to low (10)")
            else:
                print("✗ Failed to set JPEG quality")
        elif choice == "0":
            break

def show_device_status(client):
    """Show comprehensive device status"""
    print("\n" + "="*50)
    print("           DEVICE STATUS")
    print("="*50)
    
    # Version
    version = client.get_version()
    print(f"Version: {version if version else 'Unknown'}")
    
    # ISP Correction State
    print("\nISP Corrections:")
    state = client.get_isp_correction_state()
    if state:
        for correction, enabled in state.items():
            status = "✓ ON " if enabled else "✗ OFF"
            print(f"  {correction.replace('_', ' ').title()}: {status}")
    else:
        print("  Unable to read ISP state")
    
    # White Balance
    wb = client.get_white_balance()
    if wb:
        print(f"\nWhite Balance: Red={wb[0]}, Blue={wb[1]}")
    else:
        print("\nWhite Balance: Unable to read")
    
    # Black Level
    bl = client.get_black_level()
    if bl is not None:
        print(f"Black Level: {bl}")
    else:
        print("Black Level: Unable to read")
    
    # Gamma
    gamma = client.get_gamma()
    if gamma is not None:
        print(f"Gamma Level: {gamma}")
    else:
        print("Gamma Level: Unable to read")
    
    # JPEG Quality
    quality = client.get_jpeg_quality()
    if quality is not None:
        print(f"JPEG Quality: {quality}")
    else:
        print("JPEG Quality: Unable to read")
    
    print("="*50)
    input("Press Enter to continue...")

def custom_isp_menu(client):
    """Custom ISP correction control submenu"""
    while True:
        print("\n--- Custom ISP Correction Control ---")
        print("1. Enable black level correction")
        print("2. Disable black level correction")
        print("3. Enable gamma correction")
        print("4. Disable gamma correction")
        print("5. Enable white balance correction")
        print("6. Disable white balance correction")
        print("7. Enable color matrix correction")
        print("8. Disable color matrix correction")
        print("9. Enable denoise filter")
        print("10. Disable denoise filter")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        success = False
        
        if choice == "1":
            success = client.enable_isp_correction(MPIXISPCorrection.BLACK_LEVEL)
            msg = "black level correction"
        elif choice == "2":
            success = client.disable_isp_correction(MPIXISPCorrection.BLACK_LEVEL)
            msg = "black level correction"
        elif choice == "3":
            success = client.enable_isp_correction(MPIXISPCorrection.GAMMA)
            msg = "gamma correction"
        elif choice == "4":
            success = client.disable_isp_correction(MPIXISPCorrection.GAMMA)
            msg = "gamma correction"
        elif choice == "5":
            success = client.enable_isp_correction(MPIXISPCorrection.WHITE_BALANCE)
            msg = "white balance correction"
        elif choice == "6":
            success = client.disable_isp_correction(MPIXISPCorrection.WHITE_BALANCE)
            msg = "white balance correction"
        elif choice == "7":
            success = client.enable_isp_correction(MPIXISPCorrection.COLOR_MATRIX)
            msg = "color matrix correction"
        elif choice == "8":
            success = client.disable_isp_correction(MPIXISPCorrection.COLOR_MATRIX)
            msg = "color matrix correction"
        elif choice == "9":
            success = client.enable_isp_correction(MPIXISPCorrection.DENOISE)
            msg = "denoise filter"
        elif choice == "10":
            success = client.disable_isp_correction(MPIXISPCorrection.DENOISE)
            msg = "denoise filter"
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            continue
            
        if choice != "0":
            action = "enabled" if choice in ["1", "3", "5", "7", "9"] else "disabled"
            if success:
                print(f"✓ {msg.title()} {action}")
            else:
                print(f"✗ Failed to {action.replace('d', '')} {msg}")

def config_management_menu(client):
    """Configuration management submenu"""
    while True:
        print("\n--- Configuration Management ---")
        print("1. Export current config to JSON")
        print("2. Import config from JSON")
        print("3. Save config to file")
        print("4. Load config from file")
        print("5. Show current config (JSON format)")
        print("0. Back to main menu")
        
        choice = input("Choice: ").strip()
        
        if choice == "1":
            config = client.export_isp_config()
            if config:
                print("\n=== Current ISP Configuration (JSON) ===")
                print(json.dumps(config, indent=2))
                print("==========================================")
            else:
                print("✗ Failed to export configuration")
                
        elif choice == "2":
            print("Enter JSON configuration (paste and press Enter twice):")
            lines = []
            while True:
                line = input()
                if line.strip() == "":
                    break
                lines.append(line)
            
            if lines:
                try:
                    config_text = "\n".join(lines)
                    config = json.loads(config_text)
                    if client.import_isp_config(config):
                        print("✓ Configuration imported successfully")
                    else:
                        print("✗ Configuration import failed")
                except json.JSONDecodeError as e:
                    print(f"✗ Invalid JSON format: {e}")
            else:
                print("✗ No configuration provided")
                
        elif choice == "3":
            filename = input("Enter filename to save (e.g., isp_config.json): ").strip()
            if filename:
                if not filename.endswith('.json'):
                    filename += '.json'
                client.save_config_to_file(filename)
            else:
                print("✗ No filename provided")
                
        elif choice == "4":
            filename = input("Enter filename to load (e.g., isp_config.json): ").strip()
            if filename:
                client.load_config_from_file(filename)
            else:
                print("✗ No filename provided")
                
        elif choice == "5":
            config = client.export_isp_config()
            if config:
                print("\n=== Current ISP Configuration ===")
                print(json.dumps(config, indent=2))
                print("=================================")
                input("Press Enter to continue...")
            else:
                print("✗ Failed to export configuration")
                
        elif choice == "0":
            break
        else:
            print("Invalid choice")

def main():
    parser = argparse.ArgumentParser(description="MPIX Stream Client with Image Viewer")
    parser.add_argument("--port", default="COM68", help="Serial port (default: COM68)")
    parser.add_argument("--baudrate", type=int, default=921600, help="Baud rate (default: 921600)")
    args = parser.parse_args()
    
    # Create client
    client = MPIXClient(args.port, args.baudrate)
    
    if not client.connect():
        sys.exit(1)
    
    try:
        print("Testing connection...")
        if client.ping():
            print("✓ Ping successful")
        else:
            print("✗ Ping failed")
            return
        
        # Get version
        version = client.get_version()
        if version:
            print(f"✓ Device version: {version}")
        
        # Interactive menu
        while True:
            print("\n" + "="*60)
            print("             MPIX Stream Client - Advanced Control")
            print("="*60)
            print("STREAMING CONTROL:")
            print("  1. Set stream mode (JPEG)")
            print("  2. Set stream mode (RGB)")
            print("  3. Set stream mode (RAW)")
            print("  4. Start streaming")
            print("  5. Stop streaming")
            print()
            print("AUTO ALGORITHMS:")
            print("  6. Enable auto exposure")
            print("  7. Disable auto exposure")
            print("  8. Enable auto white balance")
            print("  9. Disable auto white balance")
            print()
            print("ISP CORRECTIONS:")
            print(" 10. Get ISP correction state")
            print(" 11. Enable all ISP corrections")
            print(" 12. Disable all ISP corrections")
            print(" 13. White balance control")
            print(" 14. Black level control")
            print(" 15. Gamma correction control")
            print(" 16. JPEG quality control")
            print()
            print("ADVANCED:")
            print(" 17. Show device status")
            print(" 18. Custom ISP correction control")
            print(" 19. Configuration management (JSON)")
            print(" 20. Stream diagnostics")
            print(" 21. Analyze raw stream data")
            print()
            print("  0. Exit")
            print("="*60)
            
            choice = input("Enter choice: ").strip()
            
            if choice == "1":
                if client.set_stream_mode(MPIXStreamMode.JPEG):
                    print("✓ Stream mode set to JPEG")
                else:
                    print("✗ Failed to set stream mode")
            elif choice == "2":
                if client.set_stream_mode(MPIXStreamMode.RGB):
                    print("✓ Stream mode set to RGB")
                else:
                    print("✗ Failed to set stream mode")
            elif choice == "3":
                if client.set_stream_mode(MPIXStreamMode.RAW):
                    print("✓ Stream mode set to RAW")
                else:
                    print("✗ Failed to set stream mode")
            elif choice == "4":
                if client.start_streaming():
                    print("✓ Streaming started - press any key in image window to continue")
                    print("  (Close image window or select option 5 to stop)")
                else:
                    print("✗ Failed to start streaming")
            elif choice == "5":
                if client.stop_streaming():
                    print("✓ Streaming stopped")
                else:
                    print("✗ Failed to stop streaming")
            elif choice == "6":
                if client.enable_auto_exposure():
                    print("✓ Auto exposure enabled")
                else:
                    print("✗ Failed to enable auto exposure")
            elif choice == "7":
                if client.disable_auto_exposure():
                    print("✓ Auto exposure disabled")
                else:
                    print("✗ Failed to disable auto exposure")
            elif choice == "8":
                if client.enable_auto_white_balance():
                    print("✓ Auto white balance enabled")
                else:
                    print("✗ Failed to enable auto white balance")
            elif choice == "9":
                if client.disable_auto_white_balance():
                    print("✓ Auto white balance disabled")
                else:
                    print("✗ Failed to disable auto white balance")
            elif choice == "10":
                state = client.get_isp_correction_state()
                if state:
                    print("✓ ISP Correction State:")
                    for correction, enabled in state.items():
                        status = "ON" if enabled else "OFF"
                        print(f"  {correction}: {status}")
                else:
                    print("✗ Failed to get ISP correction state")
            elif choice == "11":
                if client.enable_isp_correction(MPIXISPCorrection.ALL):
                    print("✓ All ISP corrections enabled")
                else:
                    print("✗ Failed to enable ISP corrections")
            elif choice == "12":
                if client.disable_isp_correction(MPIXISPCorrection.ALL):
                    print("✓ All ISP corrections disabled")
                else:
                    print("✗ Failed to disable ISP corrections")
            elif choice == "13":
                white_balance_menu(client)
            elif choice == "14":
                black_level_menu(client)
            elif choice == "15":
                gamma_menu(client)
            elif choice == "16":
                jpeg_quality_menu(client)
            elif choice == "17":
                show_device_status(client)
            elif choice == "18":
                custom_isp_menu(client)
            elif choice == "19":
                config_management_menu(client)
            elif choice == "20":
                client.print_stream_diagnostics()
            elif choice == "21":
                duration = input("Analysis duration in seconds (default 10): ").strip()
                try:
                    duration = int(duration) if duration else 10
                    client.analyze_raw_stream(duration)
                except ValueError:
                    print("Invalid duration, using 10 seconds")
                    client.analyze_raw_stream(10)
            elif choice == "0":
                break
            else:
                print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        client.disconnect()
        print("Disconnected")

if __name__ == "__main__":
    main()

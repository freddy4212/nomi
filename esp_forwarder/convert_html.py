#!/usr/bin/env python3
"""
將 data/index.html 轉換成 WebPage.h（GZIP 壓縮版）
參考 Seeed 官方做法，產生壓縮的二進位陣列

使用方式：python3 convert_html.py
"""

import gzip
import os


def convert_html_to_header():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, 'data', 'index.html')
    header_path = os.path.join(script_dir, 'WebPage.h')
    
    # 讀取 HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # GZIP 壓縮
    html_bytes = html_content.encode('utf-8')
    gzipped = gzip.compress(html_bytes, compresslevel=9)
    
    # 轉換成 C 陣列格式
    hex_array = ', '.join(f'0x{b:02x}' for b in gzipped)
    
    # 每 16 個 byte 換行
    hex_lines = []
    hex_values = [f'0x{b:02x}' for b in gzipped]
    for i in range(0, len(hex_values), 16):
        hex_lines.append('  ' + ', '.join(hex_values[i:i+16]))
    hex_array_formatted = ',\n'.join(hex_lines)
    
    # 產生 header 檔案
    header_content = f'''/**
 * WebPage.h - 自動產生的網頁內容（GZIP 壓縮）
 * 
 * ⚠️ 此檔案由 convert_html.py 自動產生
 * ⚠️ 請勿直接編輯，請修改 data/index.html
 * 
 * 原始大小: {len(html_bytes)} bytes
 * 壓縮後: {len(gzipped)} bytes ({100*len(gzipped)//len(html_bytes)}%)
 * 
 * 執行轉換：python3 convert_html.py
 */

#ifndef WEB_PAGE_H
#define WEB_PAGE_H

#include <pgmspace.h>

const uint8_t INDEX_HTML_GZ[] PROGMEM = {{
{hex_array_formatted}
}};

const size_t INDEX_HTML_GZ_LEN = {len(gzipped)};

#endif // WEB_PAGE_H
'''
    
    # 寫入 header
    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(header_content)
    
    print(f"✅ 已轉換: data/index.html → WebPage.h")
    print(f"   原始大小: {len(html_bytes):,} bytes")
    print(f"   壓縮後:   {len(gzipped):,} bytes ({100*len(gzipped)//len(html_bytes)}%)")

if __name__ == '__main__':
    convert_html_to_header()

/**
 * RingBuffer.h - 線程安全的環形緩衝區
 * 
 * 用於在 UART 接收任務和 TCP 發送任務之間傳遞 JSON 資料
 * 使用固定大小的 char buffer 避免動態記憶體分配
 */

#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// 每個 JSON 訊息的最大大小 (bytes)
// ESP32-C3 只有 320KB SRAM，需要控制記憶體使用
#define MAX_JSON_SIZE 16384

// 環形緩衝區大小（可儲存的 JSON 訊息數量）
// 減少數量以降低記憶體壓力 (16KB * 2 = 32KB)
#define RING_BUFFER_SIZE 2

// 單一訊息結構
struct JsonMessage {
    char data[MAX_JSON_SIZE];
    size_t length;
    bool valid;
};

class RingBuffer {
public:
    RingBuffer() : _head(0), _tail(0), _count(0), _dropped(0) {
        _mutex = xSemaphoreCreateMutex();
        for (int i = 0; i < RING_BUFFER_SIZE; i++) {
            _buffer[i].length = 0;
            _buffer[i].valid = false;
        }
    }
    
    ~RingBuffer() {
        if (_mutex) {
            vSemaphoreDelete(_mutex);
        }
    }
    
    /**
     * 推入一筆資料到緩衝區（使用 char* 和長度）
     */
    bool push(const char* data, size_t length) {
        if (length == 0 || length >= MAX_JSON_SIZE) {
            return false;
        }
        
        if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(10)) != pdTRUE) {
            return false;
        }
        
        bool wasFull = (_count >= RING_BUFFER_SIZE);
        
        // 複製資料到緩衝區
        memcpy(_buffer[_head].data, data, length);
        _buffer[_head].data[length] = '\0';  // null terminate
        _buffer[_head].length = length;
        _buffer[_head].valid = true;
        
        _head = (_head + 1) % RING_BUFFER_SIZE;
        
        if (wasFull) {
            // 緩衝區已滿，覆蓋最舊的資料
            _tail = (_tail + 1) % RING_BUFFER_SIZE;
            _dropped++;
        } else {
            _count++;
        }
        
        xSemaphoreGive(_mutex);
        return !wasFull;
    }
    
    /**
     * 從緩衝區取出一筆資料
     */
    bool pop(String& data) {
        if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(10)) != pdTRUE) {
            return false;
        }
        
        if (_count == 0) {
            xSemaphoreGive(_mutex);
            return false;
        }
        
        // 確保資料有效才取出
        if (!_buffer[_tail].valid || _buffer[_tail].length == 0) {
            _tail = (_tail + 1) % RING_BUFFER_SIZE;
            _count--;
            xSemaphoreGive(_mutex);
            return false;  // 資料無效，跳過
        }
        
        // 安全地複製資料
        size_t len = _buffer[_tail].length;
        if (len > 0 && len < MAX_JSON_SIZE) {
            // 使用 reserve 預防記憶體分配失敗
            data.reserve(len + 1);
            data = _buffer[_tail].data;
        } else {
            data = "";
        }
        
        _buffer[_tail].valid = false;
        _buffer[_tail].length = 0;
        
        _tail = (_tail + 1) % RING_BUFFER_SIZE;
        _count--;
        
        xSemaphoreGive(_mutex);
        return true;
    }
    
    /**
     * 取得目前緩衝區中的資料數量
     */
    size_t count() {
        if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(10)) != pdTRUE) {
            return 0;
        }
        size_t c = _count;
        xSemaphoreGive(_mutex);
        return c;
    }
    
    /**
     * 取得被丟棄的資料數量
     */
    unsigned long dropped() const {
        return _dropped;
    }
    
    /**
     * 重置丟棄計數
     */
    void resetDropped() {
        _dropped = 0;
    }

private:
    JsonMessage _buffer[RING_BUFFER_SIZE];
    volatile size_t _head;
    volatile size_t _tail;
    volatile size_t _count;
    volatile unsigned long _dropped;
    SemaphoreHandle_t _mutex;
};

#endif // RING_BUFFER_H

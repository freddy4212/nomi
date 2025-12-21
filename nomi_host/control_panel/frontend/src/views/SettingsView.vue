<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits } from 'vue'
import { Play, Square, Database, Download, Trash2 } from 'lucide-vue-next'

const emit = defineEmits(['status-update'])

const viewMode = ref('overlay')
const isRunning = ref(true) // Default assume running
const isDbLoading = ref(false)
let ws = null

const modes = [
  { id: 'overlay', name: '疊加顯示 (Overlay)' },
  { id: 'skeleton', name: '僅骨架 (Skeleton Only)' },
  { id: 'image', name: '僅影像 (Image Only)' }
]

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  // Use dedicated data channel for commands
  ws = new WebSocket(`${protocol}//${host}:8000/ws/data`)
  
  ws.onopen = () => {
    console.log('Settings WS Connected (Data Channel)')
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      // Handle status updates for the footer
      if (data.meta) {
        emit('status-update', data.meta)
      }

      if (data.type === 'frame_update') {
        // Update running state based on backend status
        if (data.status) {
            isRunning.value = data.status === 'running'
        }
      }
    } catch (e) {
      // ignore
    }
  }

  ws.onclose = () => {
    console.log('Settings WS Disconnected')
    emit('status-update', {
      tcp_connected: false,
      memory_connected: false,
      tcp_active: false,
      db_active: false,
      tcp_port: 0,
      db_port: 0
    })
  }
}

const toggleSystem = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  
  const command = isRunning.value ? 'stop_system' : 'start_system'
  ws.send(JSON.stringify({
    type: 'command',
    command: command
  }))
  
  // Optimistic update
  isRunning.value = !isRunning.value
}

const clearMemory = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  if (!confirm('確定要清除所有事件記憶嗎？此動作無法復原。')) return
  
  isDbLoading.value = true
  ws.send(JSON.stringify({
    type: 'command',
    command: 'clear_memory'
  }))
  
  // 模擬載入效果
  setTimeout(() => {
    isDbLoading.value = false
    alert('事件記憶已清除')
  }, 1000)
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>

<template>
  <div class="h-full flex flex-col gap-6">
    <!-- View Mode -->
    <section>
      <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 px-1">
        顯示模式 (View Mode)
      </h3>
      <div class="grid grid-cols-1 gap-2">
        <button 
          v-for="mode in modes" 
          :key="mode.id"
          @click="viewMode = mode.id"
          class="p-3 rounded-lg border text-left transition-all relative overflow-hidden group flex items-center justify-between"
          :class="viewMode === mode.id ? 'bg-primary/10 border-primary text-primary' : 'bg-bgLight border-gray-700 hover:bg-gray-700 text-gray-300'"
        >
          <span class="font-medium">{{ mode.name }}</span>
          <div v-if="viewMode === mode.id" class="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgba(0,217,255,0.8)]"></div>
        </button>
      </div>
    </section>
    
    <!-- System Control -->
    <section>
      <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 px-1">
        系統控制 (System Control)
      </h3>
      <div class="bg-bgLight rounded-xl border border-gray-700 p-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="font-bold text-white">接收服務</div>
            <div class="text-xs text-gray-400 mt-1">
              {{ isRunning ? '服務正在運行中' : '服務已停止' }}
            </div>
          </div>
          
          <button 
            @click="toggleSystem"
            class="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg"
            :class="isRunning ? 'bg-red-500/20 text-red-500 hover:bg-red-500 hover:text-white border border-red-500/50' : 'bg-green-500/20 text-green-500 hover:bg-green-500 hover:text-white border border-green-500/50'"
            :title="isRunning ? '停止服務' : '啟動服務'"
          >
            <Square v-if="isRunning" class="w-5 h-5 fill-current" />
            <Play v-else class="w-6 h-6 fill-current ml-1" />
          </button>
        </div>
      </div>
    </section>
    <!-- Database Management -->
    <section>
      <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 px-1">
        資料庫管理 (Database Admin)
      </h3>
      <div class="bg-bgLight rounded-xl border border-gray-700 p-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="font-bold text-white">PostgreSQL 記憶層</div>
            <div class="text-xs text-gray-400 mt-1">
              管理系統持久化資料與事件記錄
            </div>
          </div>
          
          <button 
            @click="clearMemory"
            class="px-4 py-2 bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white border border-red-500/50 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
            :disabled="isDbLoading"
          >
            <Trash2 class="w-4 h-4" :class="{'animate-pulse': isDbLoading}" />
            清除事件記憶
          </button>
        </div>
      </div>
    </section>  </div>
</template>

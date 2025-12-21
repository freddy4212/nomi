<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits } from 'vue'
import { Clock, Database, RefreshCw } from 'lucide-vue-next'

const emit = defineEmits(['status-update'])

const events = ref([])
const isLoading = ref(false)
const isPaused = ref(false)
const showRangePicker = ref(false)
const selectedRange = ref({ label: '今日', value: 86400 })

const timeRanges = [
  { label: '近一小時', value: 3600 },
  { label: '今日', value: 86400 },
  { label: '本週', value: 604800 },
  { label: '本月', value: 2592000 },
  { label: '所有', value: 0 }
]

let ws = null

const selectRange = (range) => {
  selectedRange.value = range
  showRangePicker.value = false
  fetchData()
}

const togglePause = () => {
  isPaused.value = !isPaused.value
  if (!isPaused.value) {
    fetchData()
  }
}

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  // Use dedicated data channel
  ws = new WebSocket(`${protocol}//${host}:8000/ws/data`)
  
  ws.onopen = () => {
    console.log('MemoryView WS Connected (Data Channel)')
    fetchData()
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      // Handle status updates for the footer
      if (data.meta) {
        emit('status-update', data.meta)
      }

      if (data.type === 'db_data') {
        if (data.query === 'recent_events') {
          events.value = data.data
        }
        isLoading.value = false
      } else if (data.type === 'new_event') {
        console.log('Received new_event', data.data)
        if (!isPaused.value) {
          // Smoothly add new event to the top
          events.value.unshift(data.data)
          // Keep only last 100 events
          if (events.value.length > 100) {
            events.value.pop()
          }
        }
      }
    } catch (e) {
      console.error('MemoryView WS Error', e)
    }
  }

  ws.onclose = () => {
    console.log('MemoryView WS Disconnected')
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

const fetchData = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN || isPaused.value) return
  
  isLoading.value = true
  ws.send(JSON.stringify({ 
    type: 'db_query', 
    query: 'recent_events', 
    limit: 100,
    duration_sec: selectedRange.value.value
  }))
}

onMounted(() => {
  connectWebSocket()
  // Periodic sync every 2s (same as original GUI)
  const timer = setInterval(fetchData, 2000)
  onUnmounted(() => clearInterval(timer))
})

onUnmounted(() => {
  if (ws) ws.close()
})

const formatDate = (timestamp) => {
  if (!timestamp) return '-'
  const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp)
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-TW', { 
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<template>
  <div class="h-full flex flex-col p-4">
    <!-- Header with Refresh and Filter -->
    <div class="flex items-center justify-end mb-4 gap-2 relative">
      <!-- Time Range Picker -->
      <div class="relative">
        <button 
          @click="showRangePicker = !showRangePicker"
          class="p-2 text-gray-400 hover:text-primary hover:bg-gray-800 rounded-lg transition-all flex items-center gap-2"
          :class="{'text-primary bg-gray-800': showRangePicker}"
          title="選擇時間範圍"
        >
          <Clock class="w-5 h-5" />
        </button>

        <!-- Range Bubble -->
        <div v-if="showRangePicker" 
             class="absolute right-0 top-full mt-2 w-40 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          <div class="p-1">
            <button 
              v-for="range in timeRanges" 
              :key="range.value"
              @click="selectRange(range)"
              class="w-full text-left px-4 py-2.5 text-sm rounded-lg transition-colors"
              :class="selectedRange.value === range.value ? 'bg-primary/20 text-primary font-bold' : 'text-gray-400 hover:bg-gray-800 hover:text-white'"
            >
              {{ range.label }}
            </button>
          </div>
        </div>
        
        <!-- Click Outside Overlay -->
        <div v-if="showRangePicker" @click="showRangePicker = false" class="fixed inset-0 z-40"></div>
      </div>

      <!-- Sync Indicator / Pause Button -->
      <button 
        @click="togglePause"
        class="p-2 rounded-lg flex items-center justify-center transition-all group"
        :title="isPaused ? '恢復自動更新' : '暫停自動更新'"
      >
        <RefreshCw 
          class="w-5 h-5 transition-all" 
          :class="[
            isPaused ? 'text-gray-400' : 'text-primary drop-shadow-[0_0_8px_rgba(0,217,255,0.8)] animate-[spin_3s_linear_infinite]',
            {'animate-[spin_1s_linear_infinite]': isLoading && !isPaused}
          ]"
        />
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 bg-bgLight/50 backdrop-blur-sm rounded-2xl border border-gray-700 overflow-hidden shadow-2xl flex flex-col">
      <!-- Events Table -->
      <div class="flex-1 overflow-auto">
        <table class="w-full text-left text-sm border-collapse">
          <thead class="text-gray-400 bg-gray-800/80 sticky top-0 backdrop-blur-md z-10">
            <tr>
              <th class="p-4 font-medium border-b border-gray-700">時間</th>
              <th class="p-4 font-medium border-b border-gray-700">人物 ID</th>
              <th class="p-4 font-medium border-b border-gray-700">識別成員</th>
              <th class="p-4 font-medium border-b border-gray-700">動作</th>
              <th class="p-4 font-medium border-b border-gray-700">信心度</th>
              <th class="p-4 font-medium border-b border-gray-700">持續時間</th>
              <th class="p-4 font-medium border-b border-gray-700">位置</th>
              <th class="p-4 font-medium border-b border-gray-700">BBox</th>
              <th class="p-4 font-medium border-b border-gray-700">運動量</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-800/50">
            <tr v-if="events.length === 0" class="text-gray-500">
              <td colspan="9" class="p-12 text-center">
                <div class="flex flex-col items-center gap-2">
                  <Database class="w-12 h-12 opacity-10" />
                  <p>暫無事件資料</p>
                </div>
              </td>
            </tr>
            <tr v-for="event in events" :key="event.id" class="hover:bg-white/5 transition-colors group">
              <td class="p-4 text-gray-400 font-mono text-xs whitespace-nowrap">{{ formatDate(event.timestamp) }}</td>
              <td class="p-4">
                <span class="px-2 py-0.5 bg-gray-800 rounded text-xs font-mono text-gray-300">#{{ event.person_id }}</span>
              </td>
              <td class="p-4">
                <span v-if="event.member_name" class="text-blue-400 font-bold">{{ event.member_name }}</span>
                <span v-else class="text-gray-600">-</span>
              </td>
              <td class="p-4">
                <span class="px-2 py-1 bg-primary/10 text-primary rounded-lg text-xs font-medium border border-primary/20 whitespace-nowrap">
                  {{ event.action_label }}
                </span>
              </td>
              <td class="p-4">
                <div class="flex items-center gap-2">
                  <div class="h-1.5 w-12 bg-gray-800 rounded-full overflow-hidden">
                    <div class="h-full bg-primary" :style="{ width: `${event.action_confidence * 100}%` }"></div>
                  </div>
                  <span class="text-[10px] text-gray-500">{{ (event.action_confidence * 100).toFixed(0) }}%</span>
                </div>
              </td>
              <td class="p-4 text-gray-400 text-xs">{{ event.action_duration ? `${event.action_duration.toFixed(1)}s` : '-' }}</td>
              <td class="p-4 text-gray-400 text-xs">{{ event.environment?.room || '-' }}</td>
              <td class="p-4 text-gray-500 text-[10px] font-mono">{{ event.bbox ? event.bbox.join(',') : '-' }}</td>
              <td class="p-4 text-gray-400 text-xs">{{ event.motion_magnitude ? event.motion_magnitude.toFixed(2) : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>

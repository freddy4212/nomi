<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits } from 'vue'
import { User, RefreshCw, Brain } from 'lucide-vue-next'

const emit = defineEmits(['status-update'])

const memberStates = ref([])
const allMembers = ref([])
const isLoading = ref(false)
let ws = null

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  // Use dedicated data channel
  ws = new WebSocket(`${protocol}//${host}:8000/ws/data`)
  
  ws.onopen = () => {
    console.log('InferenceView WS Connected (Data Channel)')
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
        if (data.query === 'member_states') {
          memberStates.value = data.data
        } else if (data.query === 'all_members') {
          allMembers.value = data.data
        }
        isLoading.value = false
      }
    } catch (e) {
      console.error('InferenceView WS Error', e)
    }
  }

  ws.onclose = () => {
    console.log('InferenceView WS Disconnected')
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
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  
  isLoading.value = true
  ws.send(JSON.stringify({ type: 'db_query', query: 'member_states' }))
  ws.send(JSON.stringify({ type: 'db_query', query: 'all_members' }))
}

onMounted(() => {
  connectWebSocket()
  const timer = setInterval(fetchData, 5000)
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
    minute: '2-digit'
  })
}
</script>

<template>
  <div class="h-full flex flex-col p-4 gap-6 overflow-auto">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <div class="w-1.5 h-5 bg-secondary rounded-full shadow-[0_0_8px_rgba(168,85,247,0.5)]"></div>
        <h2 class="text-lg font-bold text-white tracking-tight">推論與狀態 (Inference & States)</h2>
      </div>
      
      <button 
        @click="fetchData" 
        class="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-all"
        :class="{'animate-spin text-secondary': isLoading}"
      >
        <RefreshCw class="w-5 h-5" />
      </button>
    </div>

    <!-- Active States Section -->
    <section class="space-y-4">
      <div class="flex items-center gap-2 px-1">
        <Brain class="w-4 h-4 text-secondary" />
        <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider">當前活動狀態</h3>
      </div>
      
      <div v-if="memberStates.length === 0" class="bg-bgLight/30 border border-dashed border-gray-700 rounded-2xl p-12 text-center text-gray-500">
        <User class="w-12 h-12 mx-auto mb-3 opacity-10" />
        <p>目前無活動中的成員</p>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="state in memberStates" :key="state.person_id" class="bg-bgLight/50 backdrop-blur-sm border border-gray-700 rounded-2xl p-4 hover:border-secondary/30 transition-all group shadow-lg">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-secondary/10 rounded-full flex items-center justify-center text-secondary">
                <User class="w-6 h-6" />
              </div>
              <div>
                <div class="font-bold text-white">{{ state.member_name || 'Unknown' }}</div>
                <div class="text-[10px] text-gray-500 uppercase tracking-tighter font-mono">Person ID: {{ state.person_id }}</div>
              </div>
            </div>
            <div class="px-2 py-1 rounded text-[10px] font-bold uppercase" 
                 :class="state.is_visible ? 'bg-secondary/10 text-secondary border border-secondary/20' : 'bg-gray-700 text-gray-400'">
              {{ state.is_visible ? 'Visible' : 'Away' }}
            </div>
          </div>
          <div class="space-y-2 text-xs">
            <div class="flex justify-between text-gray-400">
              <span>最後動作:</span>
              <span class="text-secondary font-medium">{{ state.last_action || '-' }}</span>
            </div>
            <div class="flex justify-between text-gray-400">
              <span>最後出現:</span>
              <span>{{ formatDate(state.last_seen_time) }}</span>
            </div>
            <div class="flex justify-between text-gray-400">
              <span>位置:</span>
              <span>{{ state.last_location || '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Registered Members Section -->
    <section class="space-y-4">
      <div class="flex items-center gap-2 px-1">
        <Database class="w-4 h-4 text-primary" />
        <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider">已註冊成員</h3>
      </div>

      <div v-if="allMembers.length === 0" class="bg-bgLight/30 border border-dashed border-gray-700 rounded-2xl p-12 text-center text-gray-500">
        <p>尚未註冊任何成員</p>
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="member in allMembers" :key="member.id" class="bg-gray-900/50 border border-gray-800 rounded-xl p-3 flex flex-col items-center text-center group hover:bg-gray-800 transition-colors shadow-md">
          <div class="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center text-gray-500 mb-2 group-hover:text-primary transition-colors">
            <User class="w-6 h-6" />
          </div>
          <div class="text-sm font-bold text-gray-300 group-hover:text-white truncate w-full px-1">{{ member.name }}</div>
          <div class="text-[10px] text-gray-600 font-mono">ID: {{ member.id }}</div>
          <div class="mt-2 pt-2 border-t border-gray-800 w-full flex flex-col gap-0.5">
            <div class="text-[9px] text-gray-500">樣本: {{ member.sample_count || 0 }}</div>
            <div class="text-[9px] text-gray-500">更新: {{ formatDate(member.updated_at) }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

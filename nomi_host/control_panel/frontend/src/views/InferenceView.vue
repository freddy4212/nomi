<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits, computed } from 'vue'
import { RefreshCw, Brain, Activity, Search, Filter, UserX } from 'lucide-vue-next'
import MemberInferenceCard from '../components/MemberInferenceCard.vue'

const emit = defineEmits(['status-update'])

const memberStates = ref([])
const events = ref([])
const isLoading = ref(false)
const searchQuery = ref('')
let ws = null

const groupedData = computed(() => {
  const registered = {}
  const unknownEvents = []

  // Use memberStates as the base for registered members
  memberStates.value.forEach(state => {
    registered[state.person_id] = {
      id: state.person_id,
      name: state.member_name || `Member ${state.person_id}`,
      lastAction: state.last_action,
      lastSeen: state.last_seen_time,
      location: state.last_location,
      isVisible: state.is_visible,
      events: []
    }
  })

  // Distribute events
  events.value.forEach(event => {
    const pid = event.person_id
    if (pid === undefined || pid === null || pid === -1) {
      unknownEvents.push(event)
      return
    }

    if (registered[pid]) {
      registered[pid].events.push(event)
    } else {
      // If member not in states but has events, add them
      registered[pid] = {
        id: pid,
        name: event.member_name || `Member ${pid}`,
        lastAction: event.action_label,
        lastSeen: event.timestamp,
        location: event.environment?.room,
        isVisible: false,
        events: [event]
      }
    }
  })

  const result = Object.values(registered).sort((a: any, b: any) => (b.lastSeen || 0) - (a.lastSeen || 0))
  
  // Add Unknown Group at the end if there are unknown events
  if (unknownEvents.length > 0) {
    result.push({
      id: 'unknown',
      name: '未知訪客 (Unknown)',
      lastAction: unknownEvents[0].action_label,
      lastSeen: unknownEvents[0].timestamp,
      location: unknownEvents[0].environment?.room,
      events: unknownEvents,
      isUnknown: true
    } as any)
  }

  return result
})

const filteredData = computed(() => {
  if (!searchQuery.value) return groupedData.value
  const query = searchQuery.value.toLowerCase()
  return groupedData.value.filter((item: any) => 
    item.name.toLowerCase().includes(query) || 
    item.id.toString().includes(query) ||
    item.lastAction?.toLowerCase().includes(query)
  )
})

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  ws = new WebSocket(`${protocol}//${host}:8000/ws/data`)
  
  ws.onopen = () => {
    console.log('InferenceView WS Connected')
    fetchData()
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.meta) emit('status-update', data.meta)

      if (data.type === 'db_data') {
        if (data.query === 'member_states') {
          memberStates.value = data.data
        } else if (data.query === 'recent_events') {
          events.value = data.data
        }
        isLoading.value = false
      } else if (data.type === 'new_event') {
        events.value.unshift(data.data)
        if (events.value.length > 200) events.value.pop()
        
        // Update member state if it exists
        const pid = data.data.person_id
        if (pid !== undefined && pid !== null) {
          const stateIdx = memberStates.value.findIndex(s => s.person_id === pid)
          if (stateIdx !== -1) {
            memberStates.value[stateIdx] = {
              ...memberStates.value[stateIdx],
              last_action: data.data.action_label,
              last_seen_time: data.data.timestamp,
              last_location: data.data.environment?.room,
              is_visible: true
            }
          }
        }
      }
    } catch (e) {
      console.error('InferenceView WS Error', e)
    }
  }

  ws.onclose = () => console.log('InferenceView WS Disconnected')
}

const fetchData = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  isLoading.value = true
  ws.send(JSON.stringify({ type: 'db_query', query: 'member_states' }))
  ws.send(JSON.stringify({ type: 'db_query', query: 'recent_events', limit: 100 }))
}

const handleInference = (data) => {
  console.log('Running inference for:', data)
  // Implementation for inference trigger
}

onMounted(() => {
  connectWebSocket()
  const timer = setInterval(fetchData, 10000)
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
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-').replace(' ', '\n')
}
</script>

<template>
  <div class="h-full flex flex-col p-4 md:p-6 gap-6 overflow-hidden bg-bgDark">
    <!-- Header & Search -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="w-2 h-6 bg-secondary rounded-full shadow-[0_0_12px_rgba(168,85,247,0.6)]"></div>
        <div>
          <h2 class="text-xl font-bold text-white tracking-tight">成員推論與動態</h2>
          <p class="text-xs text-gray-500 font-medium uppercase tracking-widest">Member Inference & Activity</p>
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <div class="relative group">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-secondary transition-colors" />
          <input 
            v-model="searchQuery"
            type="text" 
            placeholder="搜尋成員或動作..." 
            class="bg-bgLight/50 border border-gray-700 rounded-xl py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-secondary/50 focus:ring-1 focus:ring-secondary/20 w-full md:w-64 transition-all"
          />
        </div>
        
        <button 
          @click="fetchData" 
          class="p-2.5 bg-bgLight/50 text-gray-400 hover:text-white hover:bg-gray-700 border border-gray-700 rounded-xl transition-all shadow-lg"
          :class="{'animate-spin text-secondary border-secondary/30': isLoading}"
        >
          <RefreshCw class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Member Cards List -->
    <div class="flex-1 overflow-y-auto pr-1 custom-scrollbar space-y-4 pb-10">
      <div v-if="filteredData.length === 0 && !isLoading" class="flex flex-col items-center justify-center py-20 text-gray-600">
        <UserX class="w-16 h-16 mb-4 opacity-20" />
        <p class="text-lg font-medium">未找到相關成員資料</p>
        <p class="text-sm opacity-60">請確認系統是否已開始接收數據</p>
      </div>

      <MemberInferenceCard 
        v-for="item in filteredData" 
        :key="item.id"
        :member="item"
        :is-unknown-group="item.isUnknown"
        :format-date="formatDate"
        @run-inference="handleInference"
      />
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(55, 65, 81, 0.5);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(75, 85, 99, 0.8);
}
</style>

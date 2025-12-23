<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits, computed } from 'vue'
import { RefreshCw, Brain, Activity, ChevronDown, ChevronUp } from 'lucide-vue-next'
import ActiveStateCard from '../components/ActiveStateCard.vue'
import SwimlaneTimeline from '../components/SwimlaneTimeline.vue'

const emit = defineEmits(['status-update'])

const memberStates = ref([])
const events = ref([])
const isLoading = ref(false)
const isTimelineOpen = ref(true)
let ws = null

const groupedEvents = computed(() => {
  const groups = {}
  events.value.forEach(event => {
    // Handle person_id 0 correctly (0 is falsy but valid)
    const pid = (event.person_id !== undefined && event.person_id !== null) ? event.person_id : 'Unknown'
    
    if (!groups[pid]) {
      groups[pid] = {
        id: pid,
        name: event.member_name || `Person #${pid}`,
        events: []
      }
    }
    groups[pid].events.push(event)
  })
  return Object.values(groups).sort((a, b) => String(a.id).localeCompare(String(b.id)))
})

const toggleTimeline = () => {
  isTimelineOpen.value = !isTimelineOpen.value
}

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
        } else if (data.query === 'recent_events') {
          events.value = data.data
        }
        isLoading.value = false
      } else if (data.type === 'new_event') {
        // Smoothly add new event to the top
        events.value.unshift(data.data)
        // Keep only last 100 events
        if (events.value.length > 100) {
          events.value.pop()
        }
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
  ws.send(JSON.stringify({ type: 'db_query', query: 'recent_events', limit: 100 }))
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
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).replace(/\//g, '-').replace(' ', '\n')
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
        <Brain class="w-12 h-12 mx-auto mb-3 opacity-10" />
        <p>目前無活動中的成員</p>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ActiveStateCard 
          v-for="state in memberStates" 
          :key="state.person_id"
          :state="state"
          :format-date="formatDate"
        />
      </div>
    </section>

    <!-- Timeline Section -->
    <section class="space-y-4">
      <div class="flex items-center justify-between px-1">
        <div class="flex items-center gap-2">
          <Activity class="w-4 h-4 text-primary" />
          <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider">實時動態 (泳道圖)</h3>
        </div>
        <button 
          @click="toggleTimeline"
          class="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
        >
          <component :is="isTimelineOpen ? ChevronUp : ChevronDown" class="w-4 h-4" />
        </button>
      </div>

      <SwimlaneTimeline 
        :is-open="isTimelineOpen"
        :grouped-events="groupedEvents"
        :events="events"
        :format-date="formatDate"
      />
    </section>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #4B5563;
}
</style>

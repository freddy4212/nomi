<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits, computed } from 'vue'
import { RefreshCw, Brain, Activity, Search, Filter, UserX, X, Info } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'
import MemberInferenceCard from '../components/MemberInferenceCard.vue'

const emit = defineEmits(['status-update'])
const { t } = useI18n()

const memberStates = ref([])
const events = ref([])
const isLoading = ref(false)
const isPaused = ref(false)
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
      name: t('memory.unknownVisitor'),
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
        if (!isPaused.value) {
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
      }
    } catch (e) {
      console.error('InferenceView WS Error', e)
    }
  }

  ws.onclose = () => console.log('InferenceView WS Disconnected')
}

const togglePause = () => {
  isPaused.value = !isPaused.value
  if (!isPaused.value) {
    fetchData()
  }
}

const fetchData = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN || isPaused.value) return
  isLoading.value = true
  ws.send(JSON.stringify({ type: 'db_query', query: 'member_states' }))
  ws.send(JSON.stringify({ type: 'db_query', query: 'recent_events', limit: 100 }))
}

const showResultModal = ref(false)
const analysisResult = ref<any>(null)
const isAnalyzing = ref(false)

const handleInference = async (data: any) => {
  console.log('Running inference for:', data)
  isAnalyzing.value = true
  showResultModal.value = true
  analysisResult.value = null
  
  try {
    // Helper to get timestamp in seconds
    const getSeconds = (ts: any) => {
      if (!ts) return 0
      if (typeof ts === 'number') return ts
      
      // Try parsing as ISO string or other date formats
      const d = new Date(ts)
      if (!isNaN(d.getTime())) return d.getTime() / 1000
      
      // If it's a string that looks like a number, convert it
      const n = parseFloat(ts)
      if (!isNaN(n)) return n
      
      return 0
    }

    let start = getSeconds(data.startTime)
    let end = getSeconds(data.endTime)
    
    // Handle unknown member ID
    const memberId = data.memberId === 'unknown' ? 0 : parseInt(data.memberId)
    
    const response = await fetch(`http://${window.location.hostname}:8000/api/inference/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        member_id: memberId,
        start_time: start,
        end_time: end
      })
    })
    
    const result = await response.json()
    analysisResult.value = result
  } catch (e: any) {
    console.error('Inference failed', e)
    analysisResult.value = { error: t('inference.reqFailed') + ': ' + e.message }
  } finally {
    isAnalyzing.value = false
  }
}

const closeResultModal = () => {
  showResultModal.value = false
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
    year: 'numeric',
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
      <div class="relative group flex-1 max-w-md">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-secondary transition-colors" />
        <input 
          v-model="searchQuery"
          type="text" 
          :placeholder="t('memory.searchPlaceholder')" 
          class="bg-bgLight/50 border border-gray-700 rounded-xl py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-secondary/50 focus:ring-1 focus:ring-secondary/20 w-full transition-all"
        />
      </div>
      
      <button 
        @click="togglePause" 
        class="p-2 text-gray-400 hover:text-white hover:bg-gray-700/30 rounded-lg transition-all group cursor-pointer relative z-50 isolate"
        :title="isPaused ? t('memory.resume') : t('memory.pause')"
      >
          <div class="pointer-events-none relative">
            <RefreshCw 
              class="w-5 h-5 transition-none" 
              :class="[
                isPaused ? 'text-gray-400' : 'text-secondary drop-shadow-[0_0_8px_rgba(168,85,247,0.8)] animate-[spin_3s_linear_infinite]',
                {'animate-[spin_1s_linear_infinite]': isLoading && !isPaused}
              ]"
            />
          </div>
        </button>
    </div>

    <!-- Member Cards List -->
    <div class="flex-1 overflow-y-auto pr-1 custom-scrollbar space-y-4 pb-10">
      <div v-if="filteredData.length === 0 && !isLoading" class="flex flex-col items-center justify-center py-20 text-gray-600">
        <UserX class="w-16 h-16 mb-4 opacity-20" />
        <p class="text-lg font-medium">{{ t('inference.noData') }}</p>
        <p class="text-sm opacity-60">{{ t('inference.checkSystem') }}</p>
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

    <!-- Analysis Result Modal -->
    <div v-if="showResultModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click="closeResultModal">
      <div class="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[80vh]" @click.stop>
        <!-- Header -->
        <div class="p-4 border-b border-gray-700 flex justify-between items-center bg-gray-800/50">
          <div class="flex items-center gap-2">
            <Brain class="w-5 h-5 text-secondary" />
            <h3 class="font-bold text-white">{{ t('inference.report') }}</h3>
          </div>
          <button @click="closeResultModal" class="text-gray-400 hover:text-white transition-colors">
            <X class="w-5 h-5" />
          </button>
        </div>
        
        <!-- Content -->
        <div class="p-6 overflow-y-auto custom-scrollbar">
          <div v-if="isAnalyzing" class="flex flex-col items-center justify-center py-12 gap-4">
            <div class="w-12 h-12 border-4 border-secondary/30 border-t-secondary rounded-full animate-spin"></div>
            <p class="text-gray-400 animate-pulse">{{ t('inference.analyzing') }}</p>
          </div>
          
          <div v-else-if="analysisResult" class="space-y-6">
            <div v-if="analysisResult.error" class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 flex items-center gap-3">
              <Info class="w-5 h-5 flex-shrink-0" />
              <p>{{ analysisResult.error }}</p>
            </div>
            
            <div v-else>
              <div class="flex items-center justify-between mb-6">
                <div>
                  <h4 class="text-2xl font-bold text-white mb-1">{{ analysisResult.member_name }}</h4>
                  <p class="text-sm text-gray-500">{{ t('inference.eventCount') }}: {{ analysisResult.event_count }}</p>
                </div>
                <div class="text-right text-xs text-gray-500 font-mono">
                  <p>Start: {{ analysisResult.period?.start }}</p>
                  <p>End: {{ analysisResult.period?.end }}</p>
                </div>
              </div>
              
              <div class="bg-white/5 rounded-xl p-6 border border-white/10">
                <h5 class="text-sm font-bold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                  <Activity class="w-4 h-4" />
                  Summary
                </h5>
                <div class="prose prose-invert max-w-none">
                  <h3 class="text-xl font-bold text-secondary mb-4">{{ analysisResult.summary }}</h3>
                  <p class="text-gray-200 leading-relaxed whitespace-pre-line">{{ analysisResult.detail || analysisResult.summary }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Footer -->
        <div class="p-4 border-t border-gray-700 bg-gray-800/30 flex justify-end">
          <button 
            @click="closeResultModal"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm font-medium"
          >
            {{ t('common.confirm') }}
          </button>
        </div>
      </div>
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

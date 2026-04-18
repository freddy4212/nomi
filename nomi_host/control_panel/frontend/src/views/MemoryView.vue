<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits, computed } from 'vue'
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'
import MemberCard from '../components/MemberCard.vue'
import EventsTable from '../components/EventsTable.vue'
import TimeRangePicker from '../components/TimeRangePicker.vue'
import { buildWsUrl } from '../utils/backend'

const emit = defineEmits(['status-update'])
const { t } = useI18n()

const events = ref([])
const allMembers = ref([])
const isLoading = ref(false)
const isPaused = ref(false)
const showRangePicker = ref(false)
const isMembersOpen = ref(false)
const selectedMemberId = ref(null)

const timeRanges = computed(() => [
  { label: t('memory.timeRange.lastHour'), value: 3600 },
  { label: t('memory.timeRange.today'), value: 86400 },
  { label: t('memory.timeRange.thisWeek'), value: 604800 },
  { label: t('memory.timeRange.thisMonth'), value: 2592000 },
  { label: t('memory.timeRange.all'), value: 0 }
])

const selectedRange = ref({ label: t('memory.timeRange.today'), value: 86400 })

let ws = null

const toggleMembers = () => {
  isMembersOpen.value = !isMembersOpen.value
}

const selectMember = (id) => {
  if (selectedMemberId.value === id) {
    selectedMemberId.value = null
  } else {
    selectedMemberId.value = id
  }
}

const editMember = (member) => {
  const newName = prompt(t('setup.enterNamePlaceholder'), member.name)
  if (newName && newName !== member.name) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'command',
        command: 'update_member',
        member_id: member.id,
        name: newName
      }))
    }
  }
}

const deleteMember = (member) => {
  if (confirm(t('settings.confirmClear'))) { // Not perfect but reuse for now
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'command',
        command: 'delete_member',
        member_id: member.id
      }))
      if (selectedMemberId.value === member.id) {
        selectedMemberId.value = null
      }
    }
  }
}

const filteredEvents = computed(() => {
  if (!selectedMemberId.value) return events.value
  
  // Find the member name to filter by
  const member = allMembers.value.find(m => m.id === selectedMemberId.value)
  if (!member) return events.value
  
  return events.value.filter(e => e.member_name === member.name)
})

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
  // Use dedicated data channel
  ws = new WebSocket(buildWsUrl('/ws/data'))
  
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
        } else if (data.query === 'all_members') {
          allMembers.value = data.data
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
  ws.send(JSON.stringify({ type: 'db_query', query: 'all_members' }))
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
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-').replace(' ', '\n')
}

const formatDateInline = (timestamp) => {
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
  }).replace(/\//g, '-')
}
</script>

<template>
  <div class="h-full flex flex-col p-4 md:p-6 gap-6">
    <!-- Header with Refresh and Filter -->
    <div class="flex items-center justify-between relative z-50">
      <!-- Left: Title / Toggle -->
      <button 
        type="button"
        @click="toggleMembers"
        class="flex items-center gap-2 group cursor-pointer text-gray-400 hover:text-white transition-colors py-2 select-none"
        :title="t('memory.title')"
      >
        <component :is="isMembersOpen ? ChevronUp : ChevronDown" class="w-5 h-5" />
        <span class="font-bold text-lg tracking-wide">{{ t('memory.title') }}</span>
      </button>

      <!-- Right: Tools -->
      <div class="flex items-center gap-2">
        <!-- Time Range Picker -->
        <TimeRangePicker 
          :selected-range="selectedRange" 
          :time-ranges="timeRanges" 
          @select="selectRange" 
        />

      <!-- Sync Indicator / Pause Button -->
      <button 
        @click.stop="togglePause"
        class="p-2 text-gray-400 hover:text-primary hover:bg-gray-800 rounded-lg flex items-center justify-center transition-colors group cursor-pointer relative z-50 isolate"
        :title="isPaused ? t('memory.resume') : t('memory.pause')"
      >
        <div class="pointer-events-none relative">
          <RefreshCw 
            class="w-5 h-5 transition-none" 
            :class="[
              isPaused ? 'text-gray-400' : 'text-primary drop-shadow-[0_0_8px_rgba(0,217,255,0.8)] animate-[spin_3s_linear_infinite]',
              {'animate-[spin_1s_linear_infinite]': isLoading && !isPaused}
            ]"
          />
        </div>
      </button>
    </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 flex flex-col gap-6 overflow-hidden relative">
      
      <!-- Registered Members Section -->
      <div class="flex-shrink-0 overflow-hidden">
        <Transition
          enter-active-class="transition-all duration-300 ease-in-out"
          enter-from-class="max-h-0 opacity-0 mb-0"
          enter-to-class="max-h-52 opacity-100 mb-6"
          leave-active-class="transition-all duration-300 ease-in-out"
          leave-from-class="max-h-52 opacity-100 mb-6"
          leave-to-class="max-h-0 opacity-0 mb-0"
        >
          <div v-show="isMembersOpen" 
               @click.self="selectedMemberId = null"
               class="bg-bgLight/50 backdrop-blur-sm rounded-2xl border border-gray-700 shadow-2xl p-3 overflow-hidden">
            <div v-if="allMembers.length === 0" class="bg-bgLight/30 border border-dashed border-gray-700 rounded-xl p-8 text-center text-gray-500 h-28 flex items-center justify-center">
              <p>{{ t('common.loading') }}</p>
            </div>
            <div v-else 
                 @click.self="selectedMemberId = null"
                 class="flex gap-4 overflow-x-auto pb-2 custom-scrollbar h-36 items-center px-2">
              <MemberCard 
                v-for="member in allMembers" 
                :key="member.id"
                :member="member"
                :is-selected="selectedMemberId === member.id"
                :format-date-inline="formatDateInline"
                @select="selectMember"
                @edit="editMember"
                @delete="deleteMember"
              />
            </div>
          </div>
        </Transition>
      </div>

      <!-- Events Table (Main Content) -->
      <EventsTable 
        :events="filteredEvents" 
        :format-date="formatDate" 
        :selected-member-id="selectedMemberId" 
      />
    </div>
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

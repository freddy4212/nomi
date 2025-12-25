<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { User, Brain, ChevronRight, ChevronDown, Clock, MapPin, X } from 'lucide-vue-next'

const props = defineProps<{
  member: {
    id: string | number
    name: string
    lastAction?: string
    lastSeen?: number | string
    location?: string
    isVisible?: boolean
    events: any[]
  }
  isUnknownGroup?: boolean
  formatDate: (timestamp: any) => string
}>()

const emit = defineEmits(['runInference'])

const isExpanded = ref(!props.isUnknownGroup)
const timelineRef = ref<HTMLElement | null>(null)

// Card-based selection state (using IDs for persistence)
const selectionStartId = ref<string | number | null>(null)
const selectionEndId = ref<string | number | null>(null)

const selectionIndices = computed(() => {
  if (selectionStartId.value === null) return null
  
  const startIndex = props.member.events.findIndex(e => (e.id || e.timestamp) === selectionStartId.value)
  if (startIndex === -1) return null
  
  if (selectionEndId.value === null) {
    return { start: startIndex, end: null, min: startIndex, max: startIndex }
  }
  
  const endIndex = props.member.events.findIndex(e => (e.id || e.timestamp) === selectionEndId.value)
  if (endIndex === -1) return { start: startIndex, end: null, min: startIndex, max: startIndex }
  
  return {
    start: startIndex,
    end: endIndex,
    min: Math.min(startIndex, endIndex),
    max: Math.max(startIndex, endIndex)
  }
})

const isMobile = ref(window.innerWidth < 768)
const handleResize = () => {
  isMobile.value = window.innerWidth < 768
}

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const formatDateWithYear = (timestamp: any) => {
  if (!timestamp) return ''
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
  }).replace(/\//g, '/')
}

const handleEventClick = (index: number) => {
  const event = props.member.events[index]
  const eventId = event.id || event.timestamp

  if (selectionStartId.value === null) {
    // First selection: set as start
    selectionStartId.value = eventId
  } else if (selectionEndId.value === null) {
    // Second selection: set as end
    if (eventId === selectionStartId.value) {
      // Clicked the same card: deselect
      selectionStartId.value = null
    } else {
      selectionEndId.value = eventId
    }
  } else {
    // Third click: reset and start new selection
    selectionStartId.value = eventId
    selectionEndId.value = null
  }
}

const clearSelection = () => {
  selectionStartId.value = null
  selectionEndId.value = null
}

const runInference = () => {
  if (!selectionIndices.value || selectionIndices.value.end === null) return
  
  const startEvent = props.member.events[selectionIndices.value.start]
  const endEvent = props.member.events[selectionIndices.value.end]
  
  emit('runInference', {
    memberId: props.member.id,
    startIndex: selectionIndices.value.start,
    endIndex: selectionIndices.value.end,
    startTime: startEvent.timestamp,
    endTime: endEvent.timestamp
  })
}

const isEventSelected = (index: number) => {
  if (!selectionIndices.value) return false
  return index >= selectionIndices.value.min && index <= selectionIndices.value.max
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="bg-bgLight/40 backdrop-blur-md border border-gray-700/50 rounded-2xl overflow-hidden transition-all hover:border-secondary/30 group shadow-lg">
    <!-- Main Card Row -->
    <div class="flex flex-col md:flex-row">
      <!-- Left Side: Member Info -->
      <div 
        @click="toggleExpand"
        class="w-full md:w-72 p-4 flex items-center gap-4 cursor-pointer md:cursor-default hover:bg-white/5 md:hover:bg-transparent transition-colors border-b md:border-b-0 md:border-r border-gray-700/50"
      >
        <div class="relative">
          <div class="w-12 h-12 bg-secondary/10 rounded-full flex items-center justify-center text-secondary border border-secondary/20 shadow-[0_0_15px_rgba(168,85,247,0.15)]">
            <User class="w-7 h-7" />
          </div>
          <div 
            v-if="member.isVisible !== undefined"
            class="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-bgDark"
            :class="member.isVisible ? 'bg-green-500' : 'bg-gray-500'"
          ></div>
        </div>
        
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <h3 class="font-bold text-white truncate">{{ member.name }}</h3>
            <span v-if="isUnknownGroup" class="px-1.5 py-0.5 rounded bg-gray-700 text-[10px] text-gray-400 font-bold uppercase">Group</span>
          </div>
          <div class="text-[10px] text-gray-500 uppercase tracking-tighter font-mono">ID: {{ member.id }}</div>
          
          <div class="mt-1 flex items-center gap-2 text-xs text-secondary font-medium">
            <Brain class="w-3 h-3" />
            <span class="truncate">{{ member.lastAction || 'Idle' }}</span>
          </div>

          <!-- Location & Last Seen -->
          <div class="mt-2 flex flex-col gap-1.5">
            <div class="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-gray-400 border border-white/5 w-fit">
              <MapPin class="w-2.5 h-2.5 text-gray-500" />
              <span class="truncate max-w-[180px]">{{ member.location || '未知' }}</span>
            </div>
            <div class="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-gray-400 border border-white/5 w-fit">
              <Clock class="w-2.5 h-2.5 text-gray-500" />
              <span>{{ member.lastSeen ? formatDateWithYear(member.lastSeen) : '無紀錄' }}</span>
            </div>
          </div>
        </div>

        <!-- Mobile Expand Icon -->
        <div class="md:hidden text-gray-500">
          <component :is="isExpanded ? ChevronDown : ChevronRight" class="w-5 h-5" />
        </div>
      </div>

      <!-- Right Side: Timeline (Desktop) / Expandable (Mobile) -->
      <div 
        v-show="isExpanded || !isMobile" 
        class="flex-1 relative overflow-hidden flex flex-col"
        :class="{'hidden md:flex': !isExpanded}"
      >
        <!-- Timeline Header -->
        <div class="px-4 py-2 border-b border-gray-700/30 bg-gray-800/30 flex justify-between items-center">
          <div class="flex items-center gap-4 text-[10px] text-gray-500 uppercase tracking-widest font-bold">
            <div class="flex items-center gap-1">
              <Clock class="w-3 h-3" />
              <span>Timeline</span>
            </div>
          </div>
          
          <div v-if="selectionStartId !== null" class="flex items-center gap-2 animate-in fade-in slide-in-from-right-4 duration-300">
            <button 
              @click.stop="clearSelection"
              class="px-2 py-1 text-[10px] font-bold text-gray-500 hover:text-white transition-colors flex items-center gap-1"
            >
              <X class="w-3 h-3" />
              取消
            </button>
            <button 
              @click.stop="runInference"
              :disabled="selectionEndId === null"
              class="px-3 py-1 text-[10px] font-bold rounded-full transition-all flex items-center gap-1"
              :class="selectionEndId !== null 
                ? 'bg-secondary text-white hover:bg-secondary/80 shadow-[0_0_10px_rgba(168,85,247,0.3)]' 
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'"
            >
              <Brain class="w-3 h-3" />
              執行推論
            </button>
          </div>
        </div>

        <!-- Timeline Scroll Area -->
        <div 
          ref="timelineRef"
          class="h-24 md:h-auto flex-1 overflow-x-auto overflow-y-hidden p-4 flex gap-3 items-center custom-scrollbar relative select-none"
        >
          <div v-if="member.events.length === 0" class="text-gray-600 text-xs italic px-4">
            No recent activity
          </div>

          <div 
            v-for="(event, index) in member.events" 
            :key="event.id || index" 
            @click="handleEventClick(index)"
            class="flex-shrink-0 relative group/event cursor-pointer"
          >
            <!-- Connector Line -->
            <div v-if="index !== member.events.length - 1" class="absolute top-1/2 -right-3 w-3 h-0.5 bg-gray-700/50"></div>
            
            <!-- Event Card -->
            <div 
              class="w-36 bg-gray-800/50 border rounded-xl p-2 transition-all relative"
              :class="[
                isEventSelected(index)
                  ? 'border-secondary bg-secondary/10 shadow-[0_0_15px_rgba(168,85,247,0.2)] z-10'
                  : 'border-gray-700/50 hover:border-secondary/30 hover:bg-gray-700/50'
              ]"
            >
              <!-- Selection Indicators -->
              <div v-if="selectionStartId === (event.id || event.timestamp)" class="absolute -top-2 -left-1 bg-secondary text-white text-[8px] font-bold px-1 rounded shadow-lg z-20">
                START
              </div>
              <div v-if="selectionEndId === (event.id || event.timestamp)" class="absolute -top-2 -right-1 bg-secondary text-white text-[8px] font-bold px-1 rounded shadow-lg z-20">
                END
              </div>

              <div class="flex justify-between items-center mb-1">
                <span class="text-[9px] font-mono text-gray-500 whitespace-pre-line leading-tight">{{ formatDate(event.timestamp) }}</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20">{{ event.action_label }}</span>
              </div>
              <div class="flex justify-between items-end">
                <span class="text-[10px] text-gray-400 truncate max-w-[70px]">{{ event.environment?.room || '未知' }}</span>
                <span class="text-[9px] text-gray-600">{{ (event.action_confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  height: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(156, 163, 175, 0.2);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(156, 163, 175, 0.4);
}

/* Hide timeline on mobile unless expanded */
@media (max-width: 767px) {
  .md\:h-auto {
    height: auto;
  }
}
</style>

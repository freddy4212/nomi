<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { User, Brain, ChevronRight, ChevronDown, Clock, MapPin, X, Loader } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'
import { buildApiUrl } from '../utils/backend'

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

const { t, tDynamic } = useI18n()

const isExpanded = ref(!props.isUnknownGroup)
const timelineRef = ref<HTMLElement | null>(null)

// Card-based selection state (using IDs for persistence)
const selectionStartId = ref<string | number | null>(null)
const selectionEndId = ref<string | number | null>(null)

// Helper to get a stable ID for events (using timestamp as key)
const getEventKey = (event: any) => {
  const ts = event.timestamp
  if (typeof ts === 'number') {
    // Assuming ts is seconds (from python time.time()), convert to ms string
    return Math.round(ts * 1000).toString()
  }
  // Assuming ts is string (ISO), convert to ms string
  return new Date(ts).getTime().toString()
}

// Inference State
const inferenceStatus = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const inferenceResult = ref<any>(null)
const showResultDetails = ref(false)

const selectionIndices = computed(() => {
  if (selectionStartId.value === null) return null
  
  const startIndex = props.member.events.findIndex(e => getEventKey(e) === selectionStartId.value)
  if (startIndex === -1) return null
  
  if (selectionEndId.value === null) {
    return { start: startIndex, end: null, min: startIndex, max: startIndex }
  }
  
  const endIndex = props.member.events.findIndex(e => getEventKey(e) === selectionEndId.value)
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
  const eventId = getEventKey(event)

  if (selectionStartId.value === null) {
    // First selection: set as start
    selectionStartId.value = eventId
  } else if (selectionEndId.value === null) {
    // Second selection
    if (eventId === selectionStartId.value) {
      // Clicked the same card: deselect
      selectionStartId.value = null
    } else {
      // Enforce: Start = Right (Older/Larger Index), End = Left (Newer/Smaller Index)
      const existingStartIdx = props.member.events.findIndex(e => getEventKey(e) === selectionStartId.value)
      
      if (index > existingStartIdx) {
        // Current click is Right -> Start
        // Existing is Left -> End
        selectionEndId.value = selectionStartId.value
        selectionStartId.value = eventId
      } else {
        // Current click is Left -> End
        // Existing is Right -> Start
        selectionEndId.value = eventId
      }
    }
  } else {
    // Third click: reset and start new selection
    selectionStartId.value = eventId
    selectionEndId.value = null
    inferenceStatus.value = 'idle'
    inferenceResult.value = null
    showResultDetails.value = false
  }
}

const clearSelection = () => {
  selectionStartId.value = null
  selectionEndId.value = null
  inferenceStatus.value = 'idle'
  inferenceResult.value = null
  showResultDetails.value = false
}

const startInference = async () => {
  if (!selectionIndices.value || selectionIndices.value.end === null) return
  
  const startEvent = props.member.events[selectionIndices.value.start]
  const endEvent = props.member.events[selectionIndices.value.end]
  
  inferenceStatus.value = 'loading'
  inferenceResult.value = null
  showResultDetails.value = false
  
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

    let start = getSeconds(startEvent.timestamp)
    let end = getSeconds(endEvent.timestamp)
    
    // Handle unknown member ID
    const memberId = props.member.id === 'unknown' ? 0 : parseInt(props.member.id as string)
    
    const response = await fetch(buildApiUrl('/api/inference/analyze'), {
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
    if (result.error) {
      inferenceStatus.value = 'error'
      inferenceResult.value = result
    } else {
      inferenceStatus.value = 'done'
      inferenceResult.value = result
    }
  } catch (e: any) {
    console.error('Inference failed', e)
    inferenceStatus.value = 'error'
    inferenceResult.value = { error: '推論請求失敗: ' + e.message }
  }
}

const toggleResultDetails = () => {
  showResultDetails.value = !showResultDetails.value
}

const isEventSelected = (index: number) => {
  if (!selectionIndices.value) return false
  return index >= selectionIndices.value.min && index <= selectionIndices.value.max
}

// --- Button Positioning Logic ---
const CARD_WIDTH = 144 // w-36
const GAP = 12 // gap-3
const PADDING_LEFT = 16 // p-4
const UNIT_WIDTH = CARD_WIDTH + GAP

const cancelBtnLeft = computed(() => {
  if (!selectionIndices.value) return 0
  // Cancel button always under the "Start" selection (first click)
  return PADDING_LEFT + selectionIndices.value.start * UNIT_WIDTH
})

const inferenceBarLeft = computed(() => {
  if (!selectionIndices.value || selectionIndices.value.end === null) return 0
  
  const { start, end, min, max } = selectionIndices.value
  
  // Logic: "End all the way to the one before start"
  // If start < end (Left to Right selection): Range is start+1 to end
  // If start > end (Right to Left selection): Range is end to start-1
  
  let rangeStartIdx, rangeEndIdx
  
  if (start < end) {
    rangeStartIdx = start + 1
    rangeEndIdx = end
  } else {
    rangeStartIdx = end
    rangeEndIdx = start - 1
  }
  
  return PADDING_LEFT + rangeStartIdx * UNIT_WIDTH
})

const inferenceBarWidth = computed(() => {
  if (!selectionIndices.value || selectionIndices.value.end === null) return 0
  
  const { start, end } = selectionIndices.value
  const count = Math.abs(end - start) // Number of items in range (excluding start)
  
  if (count === 0) return 0
  
  // Width = count * cardWidth + (count - 1) * gap
  return count * CARD_WIDTH + (count - 1) * GAP
})

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
            <span class="truncate">{{ tDynamic(member.lastAction || 'Idle') }}</span>
          </div>

          <!-- Location & Last Seen -->
          <div class="mt-2 flex flex-col gap-1.5">
            <div class="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-gray-400 border border-white/5 w-fit">
              <MapPin class="w-2.5 h-2.5 text-gray-500" />
              <span class="truncate max-w-[180px]">{{ member.location ? tDynamic(member.location) : t('perception.unknown') }}</span>
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
        </div>

        <!-- Timeline Scroll Area -->
        <div 
          ref="timelineRef"
          class="min-h-[150px] overflow-x-auto overflow-y-hidden p-4 flex gap-3 items-start custom-scrollbar relative select-none"
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
            <div v-if="index !== member.events.length - 1" class="absolute top-8 -right-3 w-3 h-0.5 bg-gray-700/50"></div>
            
            <!-- Event Card -->
            <div 
              class="w-36 bg-gray-800/50 border rounded-xl p-2 transition-all relative h-[80px]"
              :class="[
                isEventSelected(index)
                  ? 'border-secondary bg-secondary/10 shadow-[0_0_15px_rgba(168,85,247,0.2)] z-10'
                  : 'border-gray-700/50 hover:border-secondary/30 hover:bg-gray-700/50'
              ]"
            >
              <!-- Selection Indicators -->
              <div v-if="selectionStartId === getEventKey(event)" class="absolute -top-2 -left-1 bg-secondary text-white text-[8px] font-bold px-1 rounded shadow-lg z-20">
                START
              </div>
              <div v-if="selectionEndId === getEventKey(event)" class="absolute -top-2 -right-1 bg-secondary text-white text-[8px] font-bold px-1 rounded shadow-lg z-20">
                END
              </div>

              <div class="flex justify-between items-center mb-1">
                <span class="text-[9px] font-mono text-gray-500 whitespace-pre-line leading-tight">{{ formatDate(event.timestamp) }}</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20">{{ tDynamic(event.action_label) }}</span>
              </div>
              <div class="flex justify-between items-end absolute bottom-2 left-2 right-2">
                <span class="text-[10px] text-gray-400 truncate max-w-[70px]">{{ event.environment?.room || t('perception.unknown') }}</span>
                <span class="text-[9px] text-gray-600">{{ (event.action_confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <!-- Overlays Layer (Absolute positioned relative to scroll container) -->
          <!-- Note: Since this is inside the scroll container, it scrolls with content -->
          
          <!-- Cancel Button -->
          <div v-if="selectionStartId !== null && selectionIndices" 
               class="absolute top-[110px] transition-all duration-300 z-30"
               :style="{ left: cancelBtnLeft + 'px', width: '144px' }">
            <button 
              @click.stop="clearSelection"
              class="w-full h-6 bg-gray-700/30 hover:bg-red-500/20 text-gray-500 hover:text-red-400 text-[10px] rounded flex items-center justify-center transition-colors border border-transparent hover:border-red-500/30 backdrop-blur-sm"
            >
              取消
            </button>
          </div>

          <!-- Inference / Result Bar -->
          <div v-if="selectionEndId !== null && inferenceBarWidth > 0" 
               class="absolute top-[110px] transition-all duration-300 z-30"
               :style="{ left: inferenceBarLeft + 'px', width: inferenceBarWidth + 'px' }">
              
              <!-- Idle State: Inference Button -->
              <button 
                  v-if="inferenceStatus === 'idle'"
                  @click.stop="startInference"
                  class="w-full h-6 bg-secondary/10 hover:bg-secondary/20 text-secondary border border-secondary/30 hover:border-secondary/50 rounded flex items-center justify-center text-[10px] font-bold tracking-wider transition-all shadow-[0_0_10px_rgba(168,85,247,0.1)] hover:shadow-[0_0_15px_rgba(168,85,247,0.2)] backdrop-blur-sm"
              >
                  <Brain class="w-3 h-3 mr-1" />
                  推論分析
              </button>

              <!-- Loading State: Progress Bar -->
              <div v-else-if="inferenceStatus === 'loading'" class="w-full h-6 bg-gray-800/80 rounded border border-gray-700 relative overflow-hidden flex items-center justify-center backdrop-blur-sm">
                  <div class="absolute inset-0 bg-secondary/10 animate-pulse w-full"></div>
                  <span class="relative z-10 text-[10px] text-gray-300 flex items-center gap-1 font-medium">
                      <Loader class="w-3 h-3 animate-spin text-secondary" />
                      分析中...
                  </span>
              </div>

              <!-- Done State: Result Display -->
              <div v-else-if="inferenceStatus === 'done'" class="flex flex-col gap-1 w-full">
                  <div 
                      @click.stop="toggleResultDetails" 
                      class="w-full h-6 bg-gradient-to-r from-secondary/20 to-blue-500/20 border border-secondary/30 rounded cursor-pointer hover:bg-secondary/30 transition-all px-2 flex items-center justify-between group backdrop-blur-sm"
                  >
                      <div class="flex items-center gap-1 overflow-hidden">
                          <Brain class="w-3 h-3 text-secondary flex-shrink-0" />
                          <span class="text-[10px] text-gray-200 truncate">{{ inferenceResult.summary }}</span>
                      </div>
                      <ChevronDown 
                          class="w-3 h-3 text-gray-500 group-hover:text-white transition-transform duration-300" 
                      />
                  </div>
              </div>

              <!-- Error State -->
              <div v-else-if="inferenceStatus === 'error'" class="w-full h-6 px-2 bg-red-500/20 border border-red-500/30 rounded flex items-center gap-1 text-[10px] text-red-400 backdrop-blur-sm">
                  <X class="w-3 h-3" />
                  <span class="truncate">{{ inferenceResult?.error || '錯誤' }}</span>
                  <button @click="inferenceStatus = 'idle'" class="ml-auto underline hover:text-red-300">重試</button>
              </div>
          </div>

        </div>
      </div>
    </div>

    <!-- Result Modal (Teleported to body for z-index handling) -->
    <Teleport to="body">
      <div v-if="showResultDetails" class="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click="toggleResultDetails">
        <div class="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200" @click.stop>
          <!-- Header -->
          <div class="p-5 border-b border-gray-700 flex justify-between items-center bg-gray-800/50">
            <div class="flex items-center gap-3">
              <Brain class="w-6 h-6 text-secondary" />
              <h3 class="text-lg font-bold text-white">行為分析報告</h3>
            </div>
            <button @click="toggleResultDetails" class="text-gray-400 hover:text-white transition-colors">
              <X class="w-6 h-6" />
            </button>
          </div>
          
          <!-- Content -->
          <div class="p-6 overflow-y-auto custom-scrollbar">
             <div class="text-base text-gray-300 leading-relaxed whitespace-pre-wrap">
                {{ inferenceResult?.detail || inferenceResult?.summary }}
             </div>
             
             <!-- Metadata -->
             <div class="mt-6 pt-4 border-t border-gray-800 grid grid-cols-2 gap-4 text-sm text-gray-500">
                <div>
                   <span class="block text-gray-600 mb-1">分析對象</span>
                   <span class="text-gray-400">{{ member.name }} (ID: {{ member.id }})</span>
                </div>
                <div>
                   <span class="block text-gray-600 mb-1">事件數量</span>
                   <span class="text-gray-400">{{ inferenceResult?.event_count || 0 }} 筆</span>
                </div>
             </div>
          </div>
        </div>
      </div>
    </Teleport>
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

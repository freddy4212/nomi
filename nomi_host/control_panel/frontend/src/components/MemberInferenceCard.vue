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
const isSelecting = ref(false)
const selectionStart = ref<number | null>(null)
const selectionEnd = ref<number | null>(null)
const selectionBox = ref({ left: 0, width: 0 })

const isMobile = ref(window.innerWidth < 768)
const handleResize = () => {
  isMobile.value = window.innerWidth < 768
}

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const handleMouseDown = (e: MouseEvent) => {
  if (!timelineRef.value) return
  isSelecting.value = true
  const rect = timelineRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left + timelineRef.value.scrollLeft
  selectionStart.value = x
  selectionEnd.value = x
  updateSelectionBox()
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isSelecting.value || !timelineRef.value) return
  const rect = timelineRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left + timelineRef.value.scrollLeft
  selectionEnd.value = x
  updateSelectionBox()
}

const handleMouseUp = () => {
  if (!isSelecting.value) return
  isSelecting.value = false
  // If selection is too small, clear it
  if (Math.abs((selectionEnd.value || 0) - (selectionStart.value || 0)) < 10) {
    selectionStart.value = null
    selectionEnd.value = null
    selectionBox.value = { left: 0, width: 0 }
  }
}

const updateSelectionBox = () => {
  if (selectionStart.value === null || selectionEnd.value === null) return
  const left = Math.min(selectionStart.value, selectionEnd.value)
  const width = Math.abs(selectionStart.value - selectionEnd.value)
  selectionBox.value = { left, width }
}

const clearSelection = () => {
  selectionStart.value = null
  selectionEnd.value = null
  selectionBox.value = { left: 0, width: 0 }
}

const runInference = () => {
  if (selectionStart.value === null || selectionEnd.value === null) return
  
  // Find events within the selection
  // This is a bit tricky because we need to map pixels to time or just find which event cards are overlapped
  // For now, let's just emit the selection range or a generic signal
  emit('runInference', {
    memberId: props.member.id,
    start: selectionStart.value,
    end: selectionEnd.value
  })
  clearSelection()
}

// Close selection on click outside
const handleClickOutside = (e: MouseEvent) => {
  if (timelineRef.value && !timelineRef.value.contains(e.target as Node)) {
    // clearSelection()
  }
}

onMounted(() => {
  window.addEventListener('mouseup', handleMouseUp)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('mouseup', handleMouseUp)
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
            <div v-if="member.location" class="flex items-center gap-1">
              <MapPin class="w-3 h-3" />
              <span>{{ member.location }}</span>
            </div>
          </div>
          
          <div v-if="selectionBox.width > 0" class="flex items-center gap-2">
            <button 
              @click.stop="runInference"
              class="px-3 py-1 bg-secondary hover:bg-secondary/80 text-white text-[10px] font-bold rounded-full transition-all shadow-[0_0_10px_rgba(168,85,247,0.3)] flex items-center gap-1"
            >
              <Brain class="w-3 h-3" />
              執行推論
            </button>
            <button @click.stop="clearSelection" class="text-gray-500 hover:text-white">
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <!-- Timeline Scroll Area -->
        <div 
          ref="timelineRef"
          class="h-24 md:h-auto flex-1 overflow-x-auto overflow-y-hidden p-4 flex gap-3 items-center custom-scrollbar relative select-none"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
        >
          <!-- Selection Overlay -->
          <div 
            v-if="selectionBox.width > 0"
            class="absolute top-0 bottom-0 bg-secondary/20 border-x border-secondary/50 z-10 pointer-events-none"
            :style="{ left: selectionBox.left + 'px', width: selectionBox.width + 'px' }"
          ></div>

          <div v-if="member.events.length === 0" class="text-gray-600 text-xs italic px-4">
            No recent activity
          </div>

          <div 
            v-for="(event, index) in member.events" 
            :key="event.id || index" 
            class="flex-shrink-0 relative group/event"
          >
            <!-- Connector Line -->
            <div v-if="index !== member.events.length - 1" class="absolute top-1/2 -right-3 w-3 h-0.5 bg-gray-700/50"></div>
            
            <!-- Event Card -->
            <div class="w-36 bg-gray-800/50 hover:bg-gray-700/50 border border-gray-700/50 hover:border-secondary/30 rounded-xl p-2 transition-all cursor-default">
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

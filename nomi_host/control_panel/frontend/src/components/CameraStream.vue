<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits, defineProps, computed } from 'vue'
import { Activity, Info, Settings2 } from 'lucide-vue-next'

const props = defineProps({
  showInfoButton: {
    type: Boolean,
    default: true
  },
  showStatusIndicator: {
    type: Boolean,
    default: true
  },
  allowModeSwitch: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['frame-update', 'status-update', 'toggle-info'])

const imageData = ref(null)
const isConnected = ref(false)
const tcpConnected = ref(false)
const fps = ref(0)
const viewMode = ref('overlay')
const showMenu = ref(false)
const lastFrameTime = ref(0)
const currentTime = ref(Date.now())

let ws = null
let dataWs = null
let menuTimer = null
let statusTimer = null

const statusColor = computed(() => {
  if (!isConnected.value || !tcpConnected.value) return 'bg-red-500 text-red-500'
  
  const diff = currentTime.value - lastFrameTime.value
  // 有影像輸入且延遲在 1 秒內視為正常綠燈，否則視為無影像輸入紅燈
  return diff < 1000 ? 'bg-green-500 text-green-500' : 'bg-red-500 text-red-500'
})

const toggleMenu = (event) => {
  if (!props.allowModeSwitch) return
  event.stopPropagation()
  
  if (showMenu.value) {
    closeMenu()
  } else {
    showMenu.value = true
    resetMenuTimer()
  }
}

const resetMenuTimer = () => {
  if (menuTimer) clearTimeout(menuTimer)
  menuTimer = setTimeout(() => {
    showMenu.value = false
  }, 3000)
}

const closeMenu = () => {
  showMenu.value = false
  if (menuTimer) clearTimeout(menuTimer)
}

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  
  // Video Channel
  ws = new WebSocket(`${protocol}//${host}:8000/ws/video`)
  
  ws.onopen = () => {
    isConnected.value = true
    console.log('CameraStream WS Connected (Video Channel)')
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      if (data.type === 'frame_update' || data.type === 'status_update') {
        if (data.meta) {
          emit('status-update', data.meta)
          if (data.meta.fps !== undefined) fps.value = data.meta.fps
          if (data.meta.tcp_connected !== undefined) tcpConnected.value = data.meta.tcp_connected
        }
      }

      if (data.type === 'frame_update') {
        lastFrameTime.value = Date.now()
        if (data.image) {
          imageData.value = `data:image/jpeg;base64,${data.image}`
        }
        emit('frame-update', data)
      }
    } catch (e) {
      console.error('WS Parse Error', e)
    }
  }
  
  ws.onclose = () => {
    isConnected.value = false
    console.log('WebSocket Disconnected')
    emit('status-update', {
      tcp_connected: false,
      memory_connected: false,
      tcp_active: false,
      db_active: false,
      tcp_port: 0,
      db_port: 0
    })
    // Try reconnect after 3s
    setTimeout(connectWebSocket, 3000)
  }

  // Data Channel (for commands)
  if (props.allowModeSwitch) {
    dataWs = new WebSocket(`${protocol}//${host}:8000/ws/data`)
    dataWs.onopen = () => {
      console.log('CameraStream Data WS Connected')
      // Set initial mode
      setViewMode(viewMode.value)
    }
  }
}

const setViewMode = (mode) => {
  viewMode.value = mode
  if (dataWs && dataWs.readyState === WebSocket.OPEN) {
    dataWs.send(JSON.stringify({
      type: 'command',
      command: 'set_view_mode',
      mode: mode
    }))
  }
  // Close menu after selection
  closeMenu()
}

onMounted(() => {
  connectWebSocket()
  window.addEventListener('click', closeMenu)
  statusTimer = setInterval(() => {
    currentTime.value = Date.now()
  }, 200)
})

onUnmounted(() => {
  if (ws) ws.close()
  if (dataWs) dataWs.close()
  window.removeEventListener('click', closeMenu)
  if (menuTimer) clearTimeout(menuTimer)
  if (statusTimer) clearInterval(statusTimer)
})

const modes = [
  { id: 'original', label: 'RAW' },
  { id: 'overlay', label: 'OSD' },
  { id: 'yolo_only', label: 'YOLO' },
  { id: 'interpolated', label: 'INTERP' }
]
</script>

<template>
  <div class="relative group w-full flex items-center justify-center">
    <div class="relative rounded-xl overflow-hidden shadow-2xl bg-black w-full flex items-center justify-center min-w-[320px]"
         :class="{ 'aspect-[4/3]': !imageData }">
      <!-- Image Display -->
      <img v-if="imageData" :src="imageData" class="w-full h-auto block" />
      
      <!-- Placeholder -->
      <div v-else class="w-full h-full flex items-center justify-center text-gray-600 flex-col gap-2 bg-black">
        <Activity class="w-10 h-10 animate-pulse opacity-50" />
        <div class="text-center">
          <p class="text-sm font-bold">等待影像訊號...</p>
          <p class="text-xs opacity-50">Waiting for video stream</p>
        </div>
      </div>
      
      <!-- Trigger Area (Top Right) -->
      <div v-if="allowModeSwitch" 
           @click.stop="toggleMenu"
           class="absolute top-0 right-0 w-24 h-24 z-30 cursor-pointer">
      </div>

      <!-- Status Indicator (Minimal) -->
      <div v-if="showStatusIndicator" class="absolute top-3 left-3 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full shadow-[0_0_8px_currentColor] transition-all duration-500" 
                :class="statusColor"></span>
      </div>

      <!-- View Mode Selector -->
      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div v-if="allowModeSwitch && showMenu" class="absolute top-3 right-3 z-40">
          <div class="bg-black/40 backdrop-blur-xl rounded-lg p-1 flex gap-1 shadow-2xl" @click.stop>
            <button 
              v-for="mode in modes" 
              :key="mode.id"
              @click.stop="setViewMode(mode.id)"
              class="px-2.5 py-1.5 text-[10px] md:px-2 md:py-1 md:text-[10px] rounded-md hover:bg-white/20 transition-all uppercase font-mono"
              :class="viewMode === mode.id ? 'bg-primary/60 text-white font-bold shadow-lg' : 'text-gray-400'"
            >
              {{ mode.label }}
            </button>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Info Toggle (Inside Video Area) -->
    <button 
      v-if="showInfoButton"
      @click.stop="emit('toggle-info')"
      class="absolute bottom-3 right-3 w-8 h-8 backdrop-blur-md rounded-full shadow-lg flex items-center justify-center z-20 transition-all border bg-white/10 text-white/80 border-white/20 hover:bg-gray-900 hover:text-white hover:border-gray-600"
    >
      <Info class="w-4 h-4" />
    </button>
  </div>
</template>
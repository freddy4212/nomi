<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits } from 'vue'
import { Maximize2, Activity, User, Zap, Database, Cpu, Hash, Info, Layers, Monitor, X } from 'lucide-vue-next'

const emit = defineEmits(['status-update'])

const fps = ref(0)
const algoTick = ref(0)
const frameNo = ref(0)
const deviceId = ref('Unknown')
const deviceName = ref('Unknown')
const deviceVersion = ref('Unknown')
const deviceModel = ref('Unknown')
const memoryConnected = ref(false)
const bufferStatus = ref({})
const personCount = ref(0)
const imageData = ref(null)
const persons = ref([])
const isConnected = ref(false)
const showMobileInfo = ref(false)
let ws = null

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  // Use dedicated video channel
  ws = new WebSocket(`${protocol}//${host}:8000/ws/video`)
  
  ws.onopen = () => {
    isConnected.value = true
    console.log('PerceptionView WS Connected (Video Channel)')
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      if (data.type === 'frame_update' || data.type === 'status_update') {
        if (data.meta) {
          emit('status-update', data.meta)
          
          // 只有當數值存在時才更新，避免閃爍
          if (data.meta.fps !== undefined) fps.value = data.meta.fps.toFixed(1)
          if (data.meta.algo_tick !== undefined) algoTick.value = data.meta.algo_tick
          if (data.meta.frame_no !== undefined) frameNo.value = data.meta.frame_no
          
          if (data.meta.device_id && data.meta.device_id !== 'Unknown') deviceId.value = data.meta.device_id
          if (data.meta.device_version && data.meta.device_version !== 'Unknown') deviceVersion.value = data.meta.device_version
          if (data.meta.device_model && data.meta.device_model !== 'Unknown') deviceModel.value = data.meta.device_model
          
          memoryConnected.value = data.meta.memory_connected || false
          bufferStatus.value = data.meta.buffer_status || {}
        }
      }

      if (data.type === 'frame_update') {
        if (data.image) {
          imageData.value = `data:image/jpeg;base64,${data.image}`
        }
        persons.value = data.persons || []
        personCount.value = persons.value.length
      }
    } catch (e) {
      console.error('WS Parse Error', e)
    }
  }
  
  ws.onclose = () => {
    isConnected.value = false
    console.log('WebSocket Disconnected')
    // Notify App.vue that we are disconnected
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
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>

<template>
  <div class="h-full p-2 grid grid-cols-1 md:grid-cols-2 grid-rows-[auto_1fr] md:grid-rows-1 gap-4 overflow-hidden relative">
    
    <!-- Left (Desktop) / Top (Mobile): Video Area + Info Cards (Desktop Only) -->
    <div class="flex flex-col md:justify-center items-center relative">
      
      <!-- Content Wrapper (Video + Cards) -->
      <div class="w-full max-w-2xl flex flex-col gap-4 md:gap-8 relative">
        
        <!-- Video Container -->
        <div class="relative group">
          <div class="relative rounded-xl overflow-hidden shadow-2xl bg-black w-full aspect-[4/3]">
            <!-- Image Display -->
            <img v-if="imageData" :src="imageData" class="w-full h-full object-contain" />
            
            <!-- Placeholder -->
            <div v-else class="absolute inset-0 flex items-center justify-center text-gray-600 flex-col gap-2">
              <Activity class="w-10 h-10 animate-pulse opacity-50" />
              <div class="text-center">
                <p class="text-sm font-bold">等待影像訊號...</p>
                <p class="text-xs opacity-50">Waiting for video stream</p>
              </div>
            </div>
            
            <!-- Status Indicator (Minimal) -->
            <div class="absolute top-3 left-3 flex items-center gap-2">
               <span class="w-2 h-2 rounded-full shadow-[0_0_8px_currentColor] transition-all duration-500" 
                     :class="[
                       !isConnected ? 'bg-red-500 text-red-500' : 
                       fps > 0 ? 'bg-green-500 text-green-500 scale-110 animate-pulse' : 'bg-blue-500 text-blue-500'
                     ]"></span>
            </div>
          </div>

          <!-- Mobile Info Toggle (Inside Video Area) -->
          <button 
            @click.stop="showMobileInfo = !showMobileInfo"
            class="md:hidden absolute bottom-3 right-3 w-8 h-8 backdrop-blur-md rounded-full shadow-lg flex items-center justify-center z-20 transition-all border"
            :class="showMobileInfo ? 'bg-gray-900 text-white border-gray-600' : 'bg-white/10 text-white/80 border-white/20'"
          >
            <Info class="w-4 h-4" />
          </button>

          <!-- Mobile Info Bubble (Popover - Positioned below i button) -->
          <Transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="opacity-0 scale-95 -translate-y-2"
            enter-to-class="opacity-100 scale-100 translate-y-0"
            leave-active-class="transition duration-150 ease-in"
            leave-from-class="opacity-100 scale-100 translate-y-0"
            leave-to-class="opacity-0 scale-95 -translate-y-2"
          >
            <div v-if="showMobileInfo" class="md:hidden absolute top-full right-0 z-30 w-[calc(100vw-32px)] max-w-[300px] mt-1">
              <!-- Click Outside Overlay for Info -->
              <div class="fixed inset-0 z-[-1] bg-transparent" @click="showMobileInfo = false"></div>
              
              <div class="bg-bgDark/95 backdrop-blur-xl border border-gray-700 rounded-2xl p-3 shadow-2xl space-y-2.5 relative">
                <!-- Triangle Arrow (Aligned with i button) -->
                <div class="absolute -top-1.5 right-[21px] w-3.5 h-3.5 bg-bgDark border-t border-r border-gray-700 transform rotate-[-45deg]"></div>
                
                <!-- Card 1: Device Info -->
                <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5">
                  <div class="text-gray-400 text-[9px] uppercase tracking-wider flex items-center gap-1 mb-1.5">
                    <Monitor class="w-3 h-3" /> Device Info
                  </div>
                  <div>
                    <div class="text-sm font-bold text-white truncate mb-1">{{ deviceId }}</div>
                    <div class="text-[10px] text-gray-500 font-mono space-y-0.5">
                       <div class="flex justify-between"><span>Version:</span> <span class="text-gray-300">{{ deviceVersion }}</span></div>
                       <div class="flex justify-between"><span>Model:</span> <span class="text-gray-300">{{ deviceModel }}</span></div>
                    </div>
                  </div>
                </div>

                <!-- Card 2: Frame Info -->
                <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5">
                  <div class="text-gray-400 text-[9px] uppercase tracking-wider flex items-center gap-1 mb-1.5">
                    <Layers class="w-3 h-3" /> Frame Info
                  </div>
                  <div class="flex items-baseline gap-2 mb-1">
                    <div class="text-lg font-bold text-primary">{{ fps }}</div>
                    <div class="text-[9px] text-gray-500 font-bold">FPS</div>
                  </div>
                  <div class="text-[10px] text-gray-400 font-mono space-y-0.5">
                    <div class="flex justify-between"><span>Tick:</span> <span class="text-gray-300">{{ algoTick }}</span></div>
                    <div class="flex justify-between"><span>Frame No:</span> <span class="text-gray-300">{{ frameNo }}</span></div>
                  </div>
                </div>

                <!-- Card 3: Interpolation -->
                <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5">
                  <div class="text-gray-400 text-[9px] uppercase tracking-wider flex items-center gap-1 mb-1.5">
                    <Activity class="w-3 h-3" /> Interpolation
                  </div>
                  <div class="text-sm font-bold mb-1" :class="bufferStatus.sequence_ready ? 'text-secondary' : 'text-yellow-500'">
                    {{ bufferStatus.sequence_ready ? 'Ready' : 'Buffering...' }}
                  </div>
                  <div class="text-[10px] text-gray-400 font-mono space-y-0.5">
                    <div class="flex justify-between"><span>Raw Frame:</span> <span class="text-gray-300">{{ bufferStatus.raw_frames || 0 }}</span></div>
                    <div class="flex justify-between"><span>Buffed Frame:</span> <span class="text-gray-300">{{ bufferStatus.interpolated_frames || 0 }}</span></div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- Desktop Info Cards (Below Video) -->
      <div class="hidden md:grid grid-cols-3 gap-6 shrink-0 w-full">
        <!-- Card 1: Device Info -->
        <div class="bg-bgLight rounded-2xl p-5 border border-gray-700 flex flex-col shadow-lg">
          <div class="text-gray-400 text-xs uppercase tracking-wider flex items-center gap-2 mb-3">
            <Monitor class="w-4 h-4" /> Device Info
          </div>
          <div class="flex flex-col justify-center">
            <div class="text-2xl font-bold text-white truncate leading-tight mb-2" :title="deviceId">{{ deviceId }}</div>
            <div class="text-xs text-gray-500 font-mono space-y-1.5">
               <div class="flex justify-between items-center"><span>Version:</span> <span class="text-gray-300">{{ deviceVersion }}</span></div>
               <div class="flex justify-between items-center"><span>Model:</span> <span class="text-gray-300">{{ deviceModel }}</span></div>
            </div>
          </div>
        </div>

        <!-- Card 2: Frame Info -->
        <div class="bg-bgLight rounded-2xl p-5 border border-gray-700 flex flex-col shadow-lg">
          <div class="text-gray-400 text-xs uppercase tracking-wider flex items-center gap-2 mb-3">
            <Layers class="w-4 h-4" /> Frame Info
          </div>
          <div class="flex flex-col justify-center">
            <div class="flex items-baseline gap-1.5 mb-2">
              <div class="text-2xl font-bold text-primary leading-tight">{{ fps }}</div>
              <div class="text-xs text-gray-500 font-bold">FPS</div>
            </div>
            <div class="text-xs text-gray-500 font-mono space-y-1.5">
              <div class="flex justify-between items-center"><span>Tick:</span> <span class="text-gray-300">{{ algoTick }}</span></div>
              <div class="flex justify-between items-center"><span>Frame No:</span> <span class="text-gray-300">{{ frameNo }}</span></div>
            </div>
          </div>
        </div>

        <!-- Card 3: Interpolation -->
        <div class="bg-bgLight rounded-2xl p-5 border border-gray-700 flex flex-col shadow-lg">
          <div class="text-gray-400 text-xs uppercase tracking-wider flex items-center gap-2 mb-3">
            <Activity class="w-4 h-4" /> Interpolation
          </div>
          <div class="flex flex-col justify-center">
            <div class="text-2xl font-bold leading-tight mb-2" :class="bufferStatus.sequence_ready ? 'text-secondary' : 'text-yellow-500'">
              {{ bufferStatus.sequence_ready ? 'Ready' : 'Buffering...' }}
            </div>
            <div class="text-xs text-gray-500 font-mono space-y-1.5">
              <div class="flex justify-between items-center"><span>Raw Frame:</span> <span class="text-gray-300">{{ bufferStatus.raw_frames || 0 }}</span></div>
              <div class="flex justify-between items-center"><span>Buffed Frame:</span> <span class="text-gray-300">{{ bufferStatus.interpolated_frames || 0 }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

    <!-- Right (Desktop) / Bottom (Mobile): Detailed Info Panel (Person List) -->
    <div class="flex flex-col overflow-hidden rounded-2xl p-4 gap-4 m-2 bg-bgLight/30 border border-gray-800/50 shadow-inner">
      <div class="flex-1 overflow-y-auto pr-2">
        <div v-if="persons.length === 0" class="h-full flex items-center justify-center text-gray-500/40">
          <div class="text-center">
            <User class="w-16 h-16 mx-auto mb-4 opacity-20" />
            <p class="text-lg font-medium">無人偵測</p>
            <p class="text-sm opacity-60">No Person Detected</p>
          </div>
        </div>

        <div v-else class="flex flex-col gap-4">
          <div v-for="person in persons" :key="person.id" class="bg-bgLight rounded-xl p-4 border border-gray-700 shadow-lg relative overflow-hidden">
            <!-- ID Badge -->
            <div class="absolute top-0 right-0 bg-gray-800 px-3 py-1 rounded-bl-xl text-xs font-mono text-gray-400 border-b border-l border-gray-700 flex items-center gap-2">
              <span>ID: {{ person.id }}</span>
              <span v-if="person.reid_name" class="text-blue-400 font-bold border-l border-gray-600 pl-2">{{ person.reid_name }}</span>
            </div>

            <!-- Action (Main) -->
            <div class="mb-4">
              <div class="text-gray-400 text-xs mb-1 uppercase tracking-wider flex items-center gap-1">
                <Activity class="w-3 h-3" /> 目前動作 (Action)
              </div>
              <div class="text-2xl font-bold text-primary truncate">{{ person.action }}</div>
              <div class="text-xs text-gray-500 mt-1 flex items-center gap-2">
                <div class="h-1.5 w-24 bg-gray-700 rounded-full overflow-hidden">
                  <div class="h-full bg-primary transition-all duration-300" :style="{ width: `${person.confidence * 100}%` }"></div>
                </div>
                <span>{{ (person.confidence * 100).toFixed(1) }}%</span>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <!-- Skeleton Status -->
              <div>
                <div class="text-gray-400 text-xs mb-1 uppercase tracking-wider flex items-center gap-1">
                  <User class="w-3 h-3" /> 骨架狀態
                </div>
                <div class="text-sm text-gray-300">{{ person.skeleton_status }}</div>
              </div>

              <!-- Motion Status -->
              <div>
                <div class="text-gray-400 text-xs mb-1 uppercase tracking-wider flex items-center gap-1">
                  <Zap class="w-3 h-3" /> 動作強度
                </div>
                <div class="text-sm text-gray-300">{{ person.motion_status }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

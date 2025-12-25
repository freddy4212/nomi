<script setup lang="ts">
import { ref, onMounted, onUnmounted, defineEmits } from 'vue'
import { Maximize2, Activity, User, Zap, Database, Cpu, Hash, Info, Layers, Monitor, X, Clock, Scan } from 'lucide-vue-next'
import CameraStream from '../components/CameraStream.vue'

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
const persons = ref([])
const showMobileInfo = ref(false)
const showDesktopInfo = ref(true)

// Mobile Info Carousel State
const activeCardIndex = ref(0)
const touchStartX = ref(0)
const touchEndX = ref(0)

const handleTouchStart = (e) => {
  touchStartX.value = e.changedTouches[0].screenX
}

const handleTouchEnd = (e) => {
  touchEndX.value = e.changedTouches[0].screenX
  if (touchEndX.value < touchStartX.value - 30) {
    // Swipe Left -> Next
    if (activeCardIndex.value < 2) activeCardIndex.value++
  }
  if (touchEndX.value > touchStartX.value + 30) {
    // Swipe Right -> Prev
    if (activeCardIndex.value > 0) activeCardIndex.value--
  }
}

const handleFrameUpdate = (data) => {
  persons.value = data.persons || []
  personCount.value = persons.value.length
}

const handleStatusUpdate = (meta) => {
  emit('status-update', meta)
  
  // 只有當數值存在時才更新，避免閃爍
  if (meta.fps !== undefined) fps.value = meta.fps.toFixed(1)
  if (meta.algo_tick !== undefined) algoTick.value = meta.algo_tick
  if (meta.frame_no !== undefined) frameNo.value = meta.frame_no
  
  if (meta.device_id && meta.device_id !== 'Unknown') deviceId.value = meta.device_id
  if (meta.device_version && meta.device_version !== 'Unknown') deviceVersion.value = meta.device_version
  if (meta.device_model && meta.device_model !== 'Unknown') deviceModel.value = meta.device_model
  
  memoryConnected.value = meta.memory_connected || false
  bufferStatus.value = meta.buffer_status || {}
}

const formatStatus = (statusStr) => {
  if (!statusStr) return { value: '-', label: '' }
  const match = statusStr.match(/^([^(]+)(?:\(([^)]+)\))?$/)
  if (match) {
    return { value: match[1], label: match[2] || '' }
  }
  return { value: statusStr, label: '' }
}
</script>

<template>
  <div class="h-full p-2 grid grid-cols-1 md:grid-cols-2 grid-rows-[auto_1fr] md:grid-rows-1 gap-6 md:gap-4 overflow-hidden relative">
    
    <!-- Left (Desktop) / Top (Mobile): Video Area + Info Cards (Desktop Only) -->
    <div class="flex flex-col md:justify-center items-center relative">
      
      <!-- Content Wrapper (Video + Cards) -->
      <div class="w-[92%] md:w-full max-w-2xl flex flex-col gap-4 md:gap-8 relative">
        
        <!-- Video Container -->
        <div class="relative group bg-black rounded-xl border border-gray-800 shadow-2xl flex items-center justify-center w-full mx-auto">
          <!-- Grid Background -->
          <div class="absolute inset-0 opacity-5 pointer-events-none rounded-xl overflow-hidden" 
               style="background-image: radial-gradient(#374151 1px, transparent 1px); background-size: 20px 20px;"></div>
          
          <div class="w-full relative z-10 rounded-xl overflow-hidden">
            <CameraStream 
              @frame-update="handleFrameUpdate"
              @status-update="handleStatusUpdate"
              @toggle-info="() => {
                showMobileInfo = !showMobileInfo;
                showDesktopInfo = !showDesktopInfo;
              }"
            />
          </div>

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
              
              <div 
                class="bg-bgDark/95 backdrop-blur-xl border border-gray-700 rounded-2xl p-3 shadow-2xl relative"
                @touchstart="handleTouchStart"
                @touchend="handleTouchEnd"
              >
                <!-- Triangle Arrow (Aligned with i button) -->
                <div class="absolute -top-1.5 right-[21px] w-3.5 h-3.5 bg-bgDark border-t border-r border-gray-700 transform rotate-[-45deg]"></div>
                
                <!-- Carousel Container -->
                <div class="overflow-hidden">
                  <div class="flex transition-transform duration-300 ease-out" :style="{ transform: `translateX(-${activeCardIndex * 100}%)` }">
                    
                    <!-- Card 1: Device Info -->
                    <div class="w-full shrink-0 px-0.5">
                      <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5 h-full">
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
                    </div>

                    <!-- Card 2: Frame Info -->
                    <div class="w-full shrink-0 px-0.5">
                      <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5 h-full">
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
                    </div>

                    <!-- Card 3: Interpolation -->
                    <div class="w-full shrink-0 px-0.5">
                      <div class="bg-bgLight/50 rounded-xl p-2.5 border border-white/5 h-full">
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
                </div>

                <!-- Dots Indicator -->
                <div class="flex justify-center gap-1.5 mt-2.5">
                  <button 
                    v-for="i in 3" 
                    :key="i" 
                    @click.stop="activeCardIndex = i-1"
                    class="h-1.5 rounded-full transition-all duration-300"
                    :class="activeCardIndex === i-1 ? 'bg-white w-4' : 'bg-gray-600 w-1.5'"
                  ></button>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- Desktop Info Cards (Below Video) -->
        <Transition
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 -translate-y-4"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition duration-200 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 -translate-y-4"
        >
          <div v-if="showDesktopInfo" class="hidden md:grid grid-cols-3 gap-6 shrink-0 w-full">
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
        </Transition>
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
            </div>

            <!-- Top Section: Action & ReID -->
            <div class="grid grid-cols-2 gap-6 mb-4">
              <!-- Action -->
              <div>
                <div class="text-gray-400 text-[10px] mb-1 uppercase tracking-wider flex items-center gap-1">
                  <Activity class="w-3 h-3" /> 動作
                </div>
                <div class="text-2xl md:text-3xl font-bold text-primary truncate">{{ person.action }}</div>
                <div class="text-[10px] text-gray-500 mt-1 flex items-center gap-2">
                  <div class="h-1 w-full bg-gray-700 rounded-full overflow-hidden">
                    <div class="h-full bg-primary transition-all duration-300" :style="{ width: `${person.confidence * 100}%` }"></div>
                  </div>
                  <span class="whitespace-nowrap">{{ (person.confidence * 100).toFixed(0) }}%</span>
                </div>
              </div>

              <!-- ReID -->
              <div>
                <div class="text-gray-400 text-[10px] mb-1 uppercase tracking-wider flex items-center gap-1">
                  <User class="w-3 h-3" /> 識別
                </div>
                <div class="text-2xl md:text-3xl font-bold truncate" :class="person.reid_name ? 'text-blue-400' : 'text-gray-600'">
                  {{ person.reid_name || '未知' }}
                </div>
                <div class="text-[10px] text-gray-500 mt-1 flex items-center gap-2">
                  <div class="h-1 w-full bg-gray-700 rounded-full overflow-hidden">
                    <div class="h-full bg-blue-400 transition-all duration-300" :style="{ width: `${(person.reid_confidence || 0) * 100}%` }"></div>
                  </div>
                  <span class="whitespace-nowrap">{{ ((person.reid_confidence || 0) * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>

            <!-- Bottom Section: 3 Columns -->
            <div class="grid grid-cols-3 gap-2 pt-3 border-t border-gray-800">
              <!-- Skeleton Status -->
              <div class="flex flex-col items-center justify-center text-center">
                <div class="text-gray-500 text-[9px] mb-1 uppercase tracking-wider flex items-center gap-1">
                  <Scan class="w-2.5 h-2.5" /> 骨架狀態
                </div>
                <div class="flex flex-col items-center leading-tight">
                  <span class="text-sm md:text-base font-bold text-gray-200">{{ formatStatus(person.skeleton_status).value }}</span>
                  <span v-if="formatStatus(person.skeleton_status).label" class="text-[10px] text-gray-400">{{ formatStatus(person.skeleton_status).label }}</span>
                </div>
              </div>

              <!-- Motion Status -->
              <div class="flex flex-col items-center justify-center text-center border-l border-gray-800">
                <div class="text-gray-500 text-[9px] mb-1 uppercase tracking-wider flex items-center gap-1">
                  <Zap class="w-2.5 h-2.5" /> 動作強度
                </div>
                <div class="flex flex-col items-center leading-tight">
                  <span class="text-sm md:text-base font-bold text-gray-200">{{ formatStatus(person.motion_status).value }}</span>
                  <span v-if="formatStatus(person.motion_status).label" class="text-[10px] text-gray-400">{{ formatStatus(person.motion_status).label }}</span>
                </div>
              </div>

              <!-- Duration -->
              <div class="flex flex-col items-center justify-center text-center border-l border-gray-800">
                <div class="text-gray-500 text-[9px] mb-1 uppercase tracking-wider flex items-center gap-1">
                  <Clock class="w-2.5 h-2.5" /> 持續時間
                </div>
                <div class="flex flex-col items-center leading-tight">
                  <span class="text-sm md:text-base font-bold text-gray-200 font-mono">{{ (person.duration || 0).toFixed(1) }}</span>
                  <span class="text-[10px] text-gray-400">s</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Camera, Save, Trash2, AlertCircle, CheckCircle2, Loader2, UserPlus, Info } from 'lucide-vue-next'
import CameraStream from '../components/CameraStream.vue'

const name = ref('')
const isRecording = ref(false)
const progress = ref(0)
const maxProgress = ref(30)
const statusMessage = ref('請輸入成員名稱並確保畫面中只有一個人')
const statusType = ref('info') // info, success, error, recording
const personCount = ref(0)

let dataWs = null

const handleFrameUpdate = (data) => {
  personCount.value = data.persons?.length || 0
}

const connectWebSockets = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  
  console.log('VectorEntryView: Connecting to WebSockets...')

  // Data Channel
  dataWs = new WebSocket(`${protocol}//${host}:8000/ws/data`)
  dataWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('Data WS Message:', data.type)
      if (data.type === 'recording_status') {
        if (data.status === 'recording') {
          isRecording.value = true
          progress.value = data.progress
          maxProgress.value = data.max
          statusType.value = 'recording'
          statusMessage.value = `正在錄製中... (${progress.value}/${maxProgress.value})`
        } else if (data.status === 'completed') {
          isRecording.value = false
          progress.value = 0
          statusType.value = 'success'
          statusMessage.value = data.message || '錄製完成！'
          name.value = ''
        } else if (data.status === 'error') {
          isRecording.value = false
          progress.value = 0
          statusType.value = 'error'
          statusMessage.value = data.message || '錄製失敗'
        }
      } else if (data.type === 'command_result' && data.command === 'start_recording') {
        if (!data.success) {
          statusType.value = 'error'
          statusMessage.value = data.message
          isRecording.value = false
        }
      }
    } catch (e) {}
  }
}

const startRecording = () => {
  if (!name.value.trim()) {
    statusType.value = 'error'
    statusMessage.value = '請先輸入成員名稱'
    return
  }
  
  if (personCount.value !== 1) {
    statusType.value = 'error'
    statusMessage.value = '畫面中必須剛好只有一個人才能開始錄製'
    return
  }

  isRecording.value = true
  progress.value = 0
  statusType.value = 'recording'
  statusMessage.value = '準備開始錄製...'
  
  dataWs.send(JSON.stringify({
    type: 'command',
    command: 'start_recording',
    name: name.value.trim()
  }))
}

const cancelRecording = () => {
  if (isRecording.value) {
    dataWs.send(JSON.stringify({
      type: 'command',
      command: 'stop_recording'
    }))
  }
  isRecording.value = false
  progress.value = 0
  statusType.value = 'info'
  statusMessage.value = '已取消錄製'
}

onMounted(() => {
  connectWebSockets()
})

onUnmounted(() => {
  if (dataWs) dataWs.close()
})

const progressPercent = computed(() => (progress.value / maxProgress.value) * 100)
</script>

<template>
  <div class="h-full flex flex-col items-center justify-center p-1 overflow-auto">
    
    <!-- Main Container -->
    <div class="inline-flex flex-col gap-6 md:gap-2 w-full max-w-[400px]">
      
      <!-- Top: Camera Feed -->
      <div class="relative bg-black rounded-xl border border-gray-800 overflow-hidden shadow-lg flex items-center justify-center w-full aspect-[4/3] mx-auto">
        <!-- Grid Background -->
        <div class="absolute inset-0 opacity-5 pointer-events-none" 
             style="background-image: radial-gradient(#374151 1px, transparent 1px); background-size: 20px 20px;"></div>
        
        <div class="w-full h-full relative z-10">
          <CameraStream 
            :show-info-button="false"
            :show-status-indicator="false"
            :allow-mode-switch="false"
            @frame-update="handleFrameUpdate"
          />
        </div>

        <!-- Person Count Badge -->
        <div class="absolute top-4 left-4 px-3 py-1.5 rounded-full backdrop-blur-md border flex items-center gap-2 transition-all duration-300 z-20"
             :class="personCount === 1 ? 'bg-green-500/20 border-green-500/50 text-green-400' : 'bg-red-500/20 border-red-500/50 text-red-400'">
          <UserPlus class="w-4 h-4" />
          <span class="text-xs font-bold">{{ personCount }} 人</span>
        </div>

        <!-- Recording Overlay -->
        <div v-if="isRecording" class="absolute inset-0 bg-black/50 backdrop-blur-sm flex flex-col items-center justify-center z-30">
          <div class="relative w-24 h-24 flex items-center justify-center">
            <svg class="w-full h-full transform -rotate-90">
              <circle cx="48" cy="48" r="40" stroke="currentColor" stroke-width="8" fill="transparent" class="text-gray-700" />
              <circle cx="48" cy="48" r="40" stroke="currentColor" stroke-width="8" fill="transparent" 
                      class="text-primary transition-all duration-300 ease-linear"
                      :stroke-dasharray="251.2"
                      :stroke-dashoffset="251.2 - (251.2 * progress / maxProgress)" />
            </svg>
            <div class="absolute text-2xl font-bold text-white">{{ Math.round((progress / maxProgress) * 100) }}%</div>
          </div>
          <div class="mt-4 text-white font-bold tracking-wider animate-pulse">RECORDING...</div>
        </div>
      </div>
      
      <!-- Bottom: Control / Progress Area -->
      <div class="bg-bgLight/30 backdrop-blur-md rounded-xl border border-gray-800 p-2 shadow-lg flex items-center min-w-[300px]">
        
        <!-- Input/Progress Container -->
        <div class="flex-1 flex gap-2 items-center">
          
          <!-- Left Side: Input or Progress -->
          <div class="flex-1 relative">
            <div v-if="!isRecording" class="fade-in">
              <input 
                v-model="name"
                type="text" 
                class="w-full bg-bgDark/50 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-primary focus:ring-1 focus:ring-primary/20 focus:outline-none transition-all placeholder-gray-600 shadow-inner"
                placeholder="輸入成員名稱..."
                @keyup.enter="startRecording"
              >
              <!-- Status Message -->
              <div v-if="statusMessage && statusType !== 'info'" 
                   :class="['absolute -top-4 left-1 text-[8px] font-black uppercase tracking-widest', 
                            statusType === 'error' ? 'text-red-500' : 'text-green-500']">
                {{ statusMessage }}
              </div>
            </div>

            <!-- Progress Bar -->
            <div v-else class="space-y-1 fade-in px-1">
              <div class="flex justify-between items-end">
                <span class="text-[8px] font-black text-primary uppercase tracking-[0.1em]">Recording: {{ name }}</span>
                <span class="text-[8px] font-bold text-gray-500">{{ progress }} / {{ maxProgress }}</span>
              </div>
              <div class="relative h-1.5 bg-bgDark rounded-full overflow-hidden border border-gray-800 shadow-inner">
                <div 
                  class="h-full bg-gradient-to-r from-primary to-secondary transition-all duration-300 relative"
                  :style="{ width: `${progressPercent}%` }"
                >
                  <div class="absolute inset-0 bg-[linear-gradient(45deg,rgba(255,255,255,0.2)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.2)_50%,rgba(255,255,255,0.2)_75%,transparent_75%,transparent)] bg-[length:10px_10px] animate-[progress-bar-stripes_1s_linear_infinite]"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Side: Action Button -->
          <button 
            @click="isRecording ? cancelRecording() : startRecording()"
            :disabled="!isRecording && personCount !== 1"
            :class="[
              'w-9 h-9 rounded-lg flex items-center justify-center transition-all shadow-lg active:scale-95 disabled:opacity-30 disabled:grayscale shrink-0',
              isRecording ? 'bg-red-500/20 text-red-500 border border-red-500/50 hover:bg-red-500 hover:text-white' : 'bg-primary text-bgDark hover:bg-cyan-400 shadow-primary/20'
            ]"
          >
            <Trash2 v-if="isRecording" class="w-4 h-4" />
            <Camera v-else class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes progress-bar-stripes {
  from { background-position: 20px 0; }
  to { background-position: 0 0; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}
</style>

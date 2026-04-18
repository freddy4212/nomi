<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Camera, Save, Trash2, AlertCircle, CheckCircle2, Loader2, Info } from 'lucide-vue-next'
import CameraStream from '../components/CameraStream.vue'
import { useI18n } from '../composables/useI18n'
import { buildWsUrl } from '../utils/backend'

const { t } = useI18n()
const roomName = ref('')
const isCalibrating = ref(false)
const progress = ref(0)
const maxProgress = ref(100)
const statusMessage = ref(t('setup.spaceCalibrationDesc') || 'Please ensure the camera is stable')
const statusType = ref('info') // info, success, error, recording
const personCount = ref(0)

let dataWs: WebSocket | null = null

const handleFrameUpdate = (data: any) => {
  personCount.value = data.persons?.length || 0
}

const connectWebSockets = () => {
  console.log('SpaceCalibrationView: Connecting to WebSockets...')

  // Data Channel
  dataWs = new WebSocket(buildWsUrl('/ws/data'))
  dataWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'calibration_status') {
        if (data.status === 'calibrating') {
          isCalibrating.value = true
          progress.value = data.progress
          maxProgress.value = data.max
          statusType.value = 'recording'
          statusMessage.value = `Calibrating... (${Math.round((progress.value / maxProgress.value) * 100)}%)`
        } else if (data.status === 'completed') {
          isCalibrating.value = false
          progress.value = 0
          statusType.value = 'success'
          statusMessage.value = data.message || 'Calibration Completed!'
          roomName.value = ''
        } else if (data.status === 'error') {
          isCalibrating.value = false
          progress.value = 0
          statusType.value = 'error'
          statusMessage.value = data.message || 'Calibration Failed'
        }
      } else if (data.type === 'command_result' && data.command === 'start_calibration') {
        if (!data.success) {
          statusType.value = 'error'
          statusMessage.value = data.message || 'Failed to start'
          isCalibrating.value = false
        }
      }
    } catch (e) {}
  }
}

const startCalibration = () => {
  if (!roomName.value.trim()) {
    statusType.value = 'error'
    statusMessage.value = 'Please enter room name'
    return
  }
  
  // Space calibration might prefer NO people, or doesn't matter. 
  // Copying Vector Entry logic for now but removing person check strictness might be better?
  // User said "achieve the same effect", so I will keep the structure but maybe not the person check blockage.
  // Actually, let's keep it simple and just start.

  isCalibrating.value = true
  progress.value = 0
  statusType.value = 'recording'
  statusMessage.value = 'Preparing...'
  
  // Send calibration command (Backend needs to implement this later)
  if (dataWs && dataWs.readyState === WebSocket.OPEN) {
    dataWs.send(JSON.stringify({
      type: 'command',
      command: 'start_calibration',
      name: roomName.value.trim()
    }))
  }
}

const cancelCalibration = () => {
  if (isCalibrating.value && dataWs && dataWs.readyState === WebSocket.OPEN) {
    dataWs.send(JSON.stringify({
      type: 'command',
      command: 'stop_calibration'
    }))
  }
  isCalibrating.value = false
  progress.value = 0
  statusType.value = 'info'
  statusMessage.value = 'Cancelled'
}

onMounted(() => {
  connectWebSockets()
})

onUnmounted(() => {
  if (dataWs) dataWs.close()
})

const progressPercent = computed(() => (progress.value / maxProgress.value) * 100)

const zones = [
  { id: 'bathroom', label: 'Bathroom', color: 'border-cyan-500 bg-cyan-500/10 text-cyan-400', style: { top: '30%', left: '15%', width: '10%', height: '40%' } },
  { id: 'balcony', label: 'Balcony', color: 'border-green-500 bg-green-500/10 text-green-400', style: { top: '15%', left: '46%', width: '8%', height: '35%' } },
  { id: 'kitchen', label: 'Kitchen', color: 'border-orange-500 bg-orange-500/10 text-orange-400', style: { top: '30%', right: '15%', width: '10%', height: '40%' } }
]
</script>

<template>
  <div class="flex flex-col items-center justify-center p-0 overflow-auto">
    
    <!-- Main Container -->
    <div class="inline-flex flex-col gap-2 w-full max-w-[400px]">
      
      <!-- Top: Camera Feed -->
      <div class="relative bg-black rounded-xl border border-gray-800 overflow-hidden shadow-lg flex items-center justify-center w-full mx-auto">
        <!-- Grid Background -->
        <div class="absolute inset-0 opacity-5 pointer-events-none" 
             style="background-image: radial-gradient(#374151 1px, transparent 1px); background-size: 20px 20px;"></div>
        
        <div class="w-full relative z-10">
          <CameraStream 
            :show-info-button="false"
            :show-status-indicator="false"
            :allow-mode-switch="false"
            @frame-update="handleFrameUpdate"
          />
        </div>

        <!-- Predefined Zones Overlay -->
        <div class="absolute inset-0 z-20 pointer-events-none">
          <div v-for="zone in zones" :key="zone.id" 
               class="absolute border-2 border-dashed rounded-lg flex justify-center shadow-[0_0_15px_rgba(0,0,0,0.5)] backdrop-blur-[1px] transition-opacity duration-300"
               :class="[zone.color, isCalibrating ? 'opacity-30' : 'opacity-80']"
               :style="zone.style">
            <span class="absolute -top-8 text-xs font-bold uppercase tracking-wider bg-black/50 px-2 py-1 rounded backdrop-blur-md border border-white/10 whitespace-nowrap">{{ zone.label }}</span>
          </div>
        </div>

        <!-- Calibration Overlay -->
        <div v-if="isCalibrating" class="absolute inset-0 bg-black/50 backdrop-blur-sm flex flex-col items-center justify-center z-30">
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
          <div class="mt-4 text-white font-bold tracking-wider animate-pulse uppercase">Calibrating...</div>
        </div>
      </div>
      
      <!-- Bottom: Control / Progress Area -->
      <div class="bg-bgLight/30 backdrop-blur-md rounded-xl border border-gray-800 p-2 shadow-lg flex items-center min-w-[300px]">
        
        <!-- Input/Progress Container -->
        <div class="flex-1 flex gap-2 items-center">
          
          <!-- Left Side: Input or Progress -->
          <div class="flex-1 relative">
            <div v-if="!isCalibrating" class="fade-in">
              <input 
                v-model="roomName"
                type="text" 
                class="w-full bg-bgDark/50 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-primary focus:ring-1 focus:ring-primary/20 focus:outline-none transition-all placeholder-gray-600 shadow-inner"
                placeholder="Enter Room Name"
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
                <span class="text-[8px] font-black text-primary uppercase tracking-[0.1em]">Room: {{ roomName }}</span>
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
            @click="isCalibrating ? cancelCalibration() : startCalibration()"
            :class="[
              'w-9 h-9 rounded-lg flex items-center justify-center transition-all shadow-lg active:scale-95 shrink-0',
              isCalibrating ? 'bg-red-500/20 text-red-500 border border-red-500/50 hover:bg-red-500 hover:text-white' : 'bg-primary text-bgDark hover:bg-cyan-400 shadow-primary/20'
            ]"
          >
            <Trash2 v-if="isCalibrating" class="w-4 h-4" />
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

<script setup lang="ts">
import { ref, computed } from 'vue'
import { X } from 'lucide-vue-next'
import Navbar from './components/Navbar.vue'
import Footer from './components/Footer.vue'
import PerceptionView from './views/PerceptionView.vue'
import MemoryView from './views/MemoryView.vue'
import InferenceView from './views/InferenceView.vue'
import VectorEntryView from './views/VectorEntryView.vue'
import SpaceCalibrationView from './views/SpaceCalibrationView.vue'
import SettingsView from './views/SettingsView.vue'

const currentModule = ref('perception')
const currentTool = ref(null)

// System Status (from PerceptionView)
const tcpConnected = ref(false)
const tcpActive = ref(false)
const tcpPort = ref(0)
const dbConnected = ref(false)
const dbActive = ref(false)
const dbPort = ref(0)
const hostIp = ref('127.0.0.1')

let statusTimeout = null

const handleStatusUpdate = (meta) => {
  tcpConnected.value = meta.tcp_connected ?? tcpConnected.value
  tcpActive.value = meta.tcp_active ?? false
  tcpPort.value = meta.tcp_port ?? tcpPort.value
  dbConnected.value = meta.memory_connected ?? dbConnected.value
  dbActive.value = meta.db_active ?? false
  dbPort.value = meta.db_port ?? dbPort.value
  hostIp.value = meta.host_ip ?? hostIp.value

  // Clear existing timeout
  if (statusTimeout) clearTimeout(statusTimeout)
  
  // If we haven't received an update in 2 seconds, assume backend is dead or idle
  statusTimeout = setTimeout(() => {
    tcpActive.value = false
    dbActive.value = false
    // If we really want to be sure it's disconnected when no data comes:
    // tcpConnected.value = false
    // dbConnected.value = false
  }, 2000)
}

// Main Module View (Always visible in background)
const moduleView = computed(() => {
  switch (currentModule.value) {
    case 'perception': return PerceptionView
    case 'memory': return MemoryView
    case 'inference': return InferenceView
    default: return PerceptionView
  }
})

// Tool Popup View
const toolView = computed(() => {
  switch (currentTool.value) {
    case 'vector-entry': return VectorEntryView
    case 'space-calibration': return SpaceCalibrationView
    case 'settings': return SettingsView
    default: return null
  }
})

const handleModuleChange = (module) => {
  currentModule.value = module
  currentTool.value = null
}

const handleToolChange = (tool) => {
  if (currentTool.value === tool) {
    currentTool.value = null
  } else {
    currentTool.value = tool
  }
}

const closeTool = () => {
  currentTool.value = null
}
</script>

<template>
  <div class="flex flex-col h-screen bg-bgDark text-white relative overflow-hidden">
    <Navbar 
      :current-module="currentModule"
      :current-tool="currentTool"
      @update:module="handleModuleChange"
      @update:tool="handleToolChange"
    />
    
    <!-- Main Content Area -->
    <main class="flex-1 overflow-auto p-4 relative z-0">
      <component :is="moduleView" @status-update="handleStatusUpdate" />
    </main>
    
    <!-- Tool Popup Click-Outside Overlay -->
    <div v-if="currentTool" 
         @click="closeTool"
         class="fixed inset-0 z-40 bg-black/5 backdrop-blur-[1px] md:bg-transparent md:backdrop-blur-none"></div>

    <!-- Tool Popup Overlay -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-2 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-2 scale-95"
    >
      <div v-if="currentTool" class="absolute z-50 flex flex-col
        /* Mobile: Full screen below navbar */
        inset-0 top-[72px] bg-bgDark/95 backdrop-blur-sm
        /* Desktop: Bubble Card top-right */
        md:inset-auto md:top-[88px] md:right-4 md:w-[480px] md:max-h-[80vh] 
        md:bg-gray-800 md:border md:border-gray-600 md:rounded-xl md:shadow-2xl
      ">
        <!-- Popup Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-800/50">
          <span class="font-bold text-lg text-primary">
            {{ 
              currentTool === 'vector-entry' ? '向量錄入' : 
              currentTool === 'space-calibration' ? '空間標定' : 
              currentTool === 'settings' ? '系統設定' : '' 
            }}
          </span>
          <button @click="closeTool" class="md:hidden p-1 hover:bg-gray-700 rounded-full transition-colors">
            <X class="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <!-- Popup Content -->
        <div class="flex-1 overflow-y-auto p-4">
          <component :is="toolView" @status-update="handleStatusUpdate" />
        </div>
        
        <!-- Desktop Bubble Arrow -->
        <div class="hidden md:block absolute -top-2 w-4 h-4 bg-gray-800 border-t border-l border-gray-600 rotate-45 transition-all duration-300"
             :class="{
               'right-[100px]': currentTool === 'vector-entry',
               'right-[58px]': currentTool === 'space-calibration',
               'right-[13px]': currentTool === 'settings'
             }">
        </div>
      </div>
    </Transition>

    <Footer 
      :tcp-connected="tcpConnected"
      :tcp-active="tcpActive"
      :tcp-port="tcpPort"
      :db-connected="dbConnected"
      :db-active="dbActive"
      :db-port="dbPort"
      :host-ip="hostIp"
    />
  </div>
</template>

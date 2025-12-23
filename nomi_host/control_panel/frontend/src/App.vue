<script setup lang="ts">
import { ref, computed, watch } from 'vue'
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
const transitionName = ref('fade')

const modules = ['perception', 'memory', 'inference']

watch(currentModule, (newVal, oldVal) => {
  // Mobile: Use fade transition
  if (window.innerWidth < 768) {
    transitionName.value = 'fade'
    return
  }

  // Desktop: Use slide transition
  const newIndex = modules.indexOf(newVal)
  const oldIndex = modules.indexOf(oldVal)
  if (newIndex > oldIndex) {
    transitionName.value = 'slide-left'
  } else {
    transitionName.value = 'slide-right'
  }
})

// System Status (from PerceptionView)
const tcpConnected = ref(false)
const tcpLastActive = ref(0)
const tcpPort = ref(0)
const dbConnected = ref(false)
const dbLastActive = ref(0)
const dbPort = ref(0)
const hostIp = ref('127.0.0.1')

let statusTimeout = null

const handleStatusUpdate = (meta) => {
  tcpConnected.value = meta.tcp_connected ?? tcpConnected.value
  tcpLastActive.value = meta.tcp_last_active ?? tcpLastActive.value
  tcpPort.value = meta.tcp_port ?? tcpPort.value
  dbConnected.value = meta.memory_connected ?? dbConnected.value
  dbLastActive.value = meta.db_last_active ?? dbLastActive.value
  dbPort.value = meta.db_port ?? dbPort.value
  hostIp.value = meta.host_ip ?? hostIp.value

  // Clear existing timeout
  if (statusTimeout) clearTimeout(statusTimeout)
  
  // If we haven't received an update in 2 seconds, assume backend is dead or idle
  statusTimeout = setTimeout(() => {
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
  <div class="flex flex-col h-dvh bg-bgDark text-white relative overflow-hidden">
    <Navbar 
      :current-module="currentModule"
      :current-tool="currentTool"
      @update:module="handleModuleChange"
      @update:tool="handleToolChange"
    />
    
    <!-- Main Content Area -->
    <main class="flex-1 overflow-hidden relative z-0">
      <Transition :name="transitionName">
        <KeepAlive>
          <component :is="moduleView" @status-update="handleStatusUpdate" />
        </KeepAlive>
      </Transition>
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
        md:inset-auto md:top-[88px] md:right-4 md:w-fit md:min-w-[400px] md:max-h-[92vh] 
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
        <div class="flex-1 overflow-y-auto p-2">
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
      :tcp-last-active="tcpLastActive"
      :tcp-port="tcpPort"
      :db-connected="dbConnected"
      :db-last-active="dbLastActive"
      :db-port="dbPort"
      :host-ip="hostIp"
    />
  </div>
</template>

<style>
/* Common Transition Styles */
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.2s linear;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
}

/* Slide Left (Next) */
.slide-left-enter-from {
  transform: translateX(100%);
}
.slide-left-leave-to {
  transform: translateX(-100%);
}

/* Slide Right (Prev) */
.slide-right-enter-from {
  transform: translateX(-100%);
}
.slide-right-leave-to {
  transform: translateX(100%);
}

/* Fade (Default) */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

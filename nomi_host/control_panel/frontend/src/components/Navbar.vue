<script setup lang="ts">
import { ref } from 'vue'
import { 
  Eye, Brain, Cpu, 
  UserPlus, Box, Settings, 
  MoreHorizontal, ChevronLeft
} from 'lucide-vue-next'

const props = defineProps<{
  currentModule: string
  currentTool: string | null
}>()

const emit = defineEmits(['update:module', 'update:tool'])

const modules = [
  { id: 'perception', name: '感知', icon: Eye },
  { id: 'memory', name: '記憶', icon: Brain },
  { id: 'inference', name: '推論', icon: Cpu },
]

const tools = [
  { id: 'vector-entry', name: '向量錄入', icon: UserPlus },
  { id: 'space-calibration', name: '空間標定', icon: Box },
  { id: 'settings', name: '系統設定', icon: Settings },
]

const isMobileModuleOpen = ref(false)
const isMobileToolOpen = ref(false)

const toggleModule = () => {
  isMobileModuleOpen.value = !isMobileModuleOpen.value
  if (isMobileModuleOpen.value) isMobileToolOpen.value = false
}

const toggleTool = () => {
  isMobileToolOpen.value = !isMobileToolOpen.value
  if (isMobileToolOpen.value) isMobileModuleOpen.value = false
}

const selectModule = (id) => {
  emit('update:module', id)
  isMobileModuleOpen.value = false
}

const selectTool = (id) => {
  emit('update:tool', id)
  isMobileToolOpen.value = false
}
</script>

<template>
  <nav @click="selectTool(null)" class="bg-bgLight border-b border-gray-700 h-[72px] flex items-center justify-between px-5 relative z-50 shadow-md cursor-default">
    
    <!-- Click Outside Overlay -->
    <div v-if="isMobileModuleOpen || isMobileToolOpen" 
         @click.stop="isMobileModuleOpen = false; isMobileToolOpen = false"
         class="fixed inset-0 z-40 md:hidden bg-transparent"></div>

    <!-- Mobile Left: Module Selector -->
    <div class="md:hidden w-1/4 relative z-50">
      <button 
        @click.stop="toggleModule" 
        class="p-2 text-gray-400 hover:text-white transition-all active:scale-90"
      >
        <component :is="modules.find(m => m.id === currentModule)?.icon" class="w-6 h-6" />
      </button>
      
      <!-- Mobile Module Dropdown (Bubble Style) -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-1 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-1 scale-95"
      >
        <div v-if="isMobileModuleOpen" @click.stop class="absolute top-14 left-0 w-48 bg-bgDark/95 backdrop-blur-xl border border-gray-700 shadow-2xl rounded-2xl mt-2">
          <!-- Arrow -->
          <div class="absolute -top-1.5 left-[13px] w-3.5 h-3.5 bg-bgDark border-t border-l border-gray-700 rotate-45"></div>
          <div class="relative z-10 overflow-hidden rounded-2xl">
            <button 
              v-for="mod in modules" 
              :key="mod.id"
              @click="selectModule(mod.id)"
              class="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0"
              :class="{'text-primary bg-primary/5': currentModule === mod.id}"
            >
              <component :is="mod.icon" class="w-5 h-5" />
              <span class="font-medium">{{ mod.name }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Desktop Left / Mobile Center: Logo -->
    <div class="flex items-center gap-3 md:w-1/4 justify-center md:justify-start">
      <!-- Square Kitten Logo -->
      <div class="w-7 h-7 bg-gradient-to-br from-primary to-blue-600 rounded-lg flex flex-col items-center justify-center shadow-lg shadow-primary/20 relative overflow-hidden">
        <!-- Eyes -->
        <div class="flex gap-1 mb-0.5">
          <div class="w-0.5 h-1.5 bg-bgDark rounded-full"></div>
          <div class="w-0.5 h-1.5 bg-bgDark rounded-full"></div>
        </div>
        <!-- Mouth -->
        <div class="w-0 h-0 border-l-[2.5px] border-l-transparent border-r-[2.5px] border-r-transparent border-t-[3.5px] border-t-bgDark"></div>
      </div>
      <span class="font-bold text-xl tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">NOMI Agent</span>
    </div>

    <!-- Desktop Center: Modules -->
    <div class="hidden md:flex items-center justify-center gap-2 flex-1">
      <button 
        v-for="mod in modules" 
        :key="mod.id"
        @click.stop="selectModule(mod.id)"
        class="px-6 py-2 rounded-full transition-all duration-300 flex items-center gap-2 border border-transparent"
        :class="currentModule === mod.id ? 'bg-primary/10 text-primary border-primary/20 shadow-[0_0_15px_rgba(0,217,255,0.1)]' : 'hover:bg-gray-800 text-gray-400 hover:text-white'"
      >
        <component :is="mod.icon" class="w-5 h-5" />
        {{ mod.name }}
      </button>
    </div>

    <!-- Desktop Right: Tools -->
    <div class="hidden md:flex items-center justify-end gap-2 w-1/4">
      <button 
        v-for="tool in tools" 
        :key="tool.id"
        @click.stop="selectTool(tool.id)"
        class="p-2 rounded-lg transition-all duration-300 relative group"
        :class="currentTool === tool.id ? 'text-primary bg-gray-800 shadow-inner' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
        :title="tool.name"
      >
        <component :is="tool.icon" class="w-5 h-5" />
        <!-- Tooltip -->
        <span class="absolute -bottom-10 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none border border-gray-700">
          {{ tool.name }}
        </span>
      </button>
    </div>

    <!-- Mobile Right: Tools Dropdown -->
    <div class="md:hidden w-1/4 flex justify-end relative z-50">
      <button 
        @click.stop="toggleTool" 
        class="p-2 text-gray-400 hover:text-white transition-all active:scale-90"
      >
        <MoreHorizontal class="w-6 h-6" />
      </button>

      <!-- Mobile Tool Dropdown (Bubble Style) -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-1 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-1 scale-95"
      >
        <div v-if="isMobileToolOpen" @click.stop class="absolute top-14 right-0 w-48 bg-bgDark/95 backdrop-blur-xl border border-gray-700 shadow-2xl rounded-2xl mt-2">
          <!-- Arrow -->
          <div class="absolute -top-1.5 right-[13px] w-3.5 h-3.5 bg-bgDark border-t border-r border-gray-700 -rotate-45"></div>
          <div class="relative z-10 overflow-hidden rounded-2xl">
            <button 
              v-for="tool in tools" 
              :key="tool.id"
              @click="selectTool(tool.id)"
              class="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0"
              :class="{'text-primary bg-primary/5': currentTool === tool.id}"
            >
              <component :is="tool.icon" class="w-5 h-5" />
              <span class="font-medium">{{ tool.name }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </div>

  </nav>
</template>

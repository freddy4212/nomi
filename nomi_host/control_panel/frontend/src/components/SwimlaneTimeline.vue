<script setup lang="ts">
import { ChevronDown, ChevronUp } from 'lucide-vue-next'

defineProps<{
  isOpen: boolean
  groupedEvents: any[]
  events: any[]
  formatDate: (timestamp: any) => string
}>()

defineEmits(['toggle'])
</script>

<template>
  <div class="overflow-hidden">
    <Transition
      enter-active-class="transition-all duration-500 ease-in-out"
      enter-from-class="max-h-0 opacity-0"
      enter-to-class="max-h-[400px] opacity-100"
      leave-active-class="transition-all duration-400 ease-in-out"
      leave-from-class="max-h-[400px] opacity-100"
      leave-to-class="max-h-0 opacity-0"
    >
      <div v-if="isOpen" class="w-full bg-bgLight/50 backdrop-blur-sm rounded-2xl border border-gray-700 overflow-hidden shadow-2xl flex flex-col">
        <div class="p-3 border-b border-gray-700 bg-gray-800/50 flex justify-between items-center">
          <span class="text-xs text-gray-500">最新動態靠左</span>
        </div>
        
        <div class="h-64 overflow-y-auto p-4 space-y-4 custom-scrollbar">
          <div v-if="events.length === 0" class="text-center text-gray-500 py-8 text-sm">
            暫無動態
          </div>
          
          <!-- Person Track -->
          <div v-for="group in groupedEvents" :key="group.id" class="flex flex-col gap-2">
            <!-- Track Header -->
            <div class="flex items-center gap-2 px-2">
              <div class="w-2 h-2 rounded-full bg-primary"></div>
              <span class="text-sm font-bold text-white">{{ group.name }}</span>
              <span class="text-xs text-gray-500 font-mono">#{{ group.id }}</span>
            </div>
            
            <!-- Horizontal Scroll Track -->
            <div class="flex gap-3 overflow-x-auto pb-2 px-2 custom-scrollbar items-center min-h-[80px] bg-gray-900/30 rounded-lg border border-gray-800/50">
              <div v-for="(event, index) in group.events" :key="event.id || index" class="flex-shrink-0 relative group">
                <!-- Connector Line -->
                <div v-if="index !== group.events.length - 1" class="absolute top-1/2 -right-3 w-3 h-0.5 bg-gray-700"></div>
                
                <!-- Event Card -->
                <div class="w-40 bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-primary/50 rounded-lg p-2 transition-all cursor-default">
                  <div class="flex justify-between items-center mb-1">
                    <span class="text-[10px] font-mono text-gray-400 whitespace-pre-line leading-tight">{{ formatDate(event.timestamp) }}</span>
                    <span class="text-[10px] px-1.5 rounded bg-primary/10 text-primary">{{ event.action_label }}</span>
                  </div>
                  <div class="flex justify-between items-end">
                    <span class="text-xs text-gray-300 truncate max-w-[80px]" :title="event.environment?.room">{{ event.environment?.room || '未知' }}</span>
                    <span class="text-[10px] text-gray-500">{{ (event.action_confidence * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #4B5563;
}
</style>

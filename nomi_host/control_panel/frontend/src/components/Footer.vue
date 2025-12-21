<script setup lang="ts">
import { Wifi, Database, Server, Activity } from 'lucide-vue-next'

const props = defineProps<{
  tcpConnected: boolean
  tcpActive: boolean
  tcpPort: number
  dbConnected: boolean
  dbActive: boolean
  dbPort: number
  hostIp: string
}>()
</script>

<template>
  <footer class="bg-bgLight border-t border-gray-700 h-8 flex items-center justify-between px-4 text-xs text-gray-400 select-none">
    <div class="flex items-center gap-4">
      <!-- TCP Status -->
      <div class="flex items-center gap-1.5 group cursor-help" :title="tcpConnected ? (tcpActive ? '傳輸中' : '已連線 (閒置)') : '未連線'">
        <div 
          class="w-2 h-2 rounded-full transition-all duration-200" 
          :class="[
            !tcpConnected ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' : 
            tcpActive ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]'
          ]"
        >
        </div>
        <span>TCP: {{ tcpPort || '---' }}</span>
      </div>

      <!-- DB Status -->
      <div class="flex items-center gap-1.5 group cursor-help" :title="dbConnected ? (dbActive ? '寫入中' : '已連線 (閒置)') : '未連線'">
        <div 
          class="w-2 h-2 rounded-full transition-all duration-200" 
          :class="[
            !dbConnected ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' : 
            dbActive ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]'
          ]"
        >
        </div>
        <span>PostgreSQL: {{ dbPort || '---' }}</span>
      </div>
    </div>
    
    <div class="flex items-center gap-1.5 opacity-70 hover:opacity-100 transition-opacity">
      <Server class="w-3 h-3" />
      <span>{{ hostIp || '127.0.0.1' }}</span>
    </div>
  </footer>
</template>

<style scoped>
/* Removed animations as requested */
</style>

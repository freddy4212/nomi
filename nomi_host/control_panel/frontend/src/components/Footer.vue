<script setup lang="ts">
import { Wifi, Database, Server, Activity } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  tcpConnected: boolean
  tcpLastActive: number
  tcpPort: number
  dbConnected: boolean
  dbLastActive: number
  dbPort: number
  hostIp: string
}>()

const now = ref(Date.now() / 1000)
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now() / 1000
  }, 100)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const getStatusColor = (connected: boolean, lastActive: number) => {
  if (!connected) return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
  const delta = now.value - lastActive
  if (delta < 0.5) return 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' // Active
  if (delta < 3.0) return 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]'  // Idle
  return 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.5)]'                 // Lagging
}

const getStatusText = (connected: boolean, lastActive: number) => {
  if (!connected) return '未連線'
  const delta = now.value - lastActive
  if (delta < 0.5) return '傳輸中'
  if (delta < 3.0) return '已連線 (閒置)'
  return '已連線 (延遲)'
}
</script>

<template>
  <footer class="bg-bgLight border-t border-gray-700 h-8 flex items-center justify-between px-4 text-xs text-gray-400 select-none">
    <div class="flex items-center gap-4">
      <!-- TCP Status -->
      <div class="flex items-center gap-1.5 group cursor-help" :title="getStatusText(tcpConnected, tcpLastActive)">
        <div 
          class="w-2 h-2 rounded-full transition-all duration-200" 
          :class="getStatusColor(tcpConnected, tcpLastActive)"
        >
        </div>
        <span>TCP: {{ tcpPort || '---' }}</span>
      </div>

      <!-- DB Status -->
      <div class="flex items-center gap-1.5 group cursor-help" :title="getStatusText(dbConnected, dbLastActive)">
        <div 
          class="w-2 h-2 rounded-full transition-all duration-200" 
          :class="getStatusColor(dbConnected, dbLastActive)"
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

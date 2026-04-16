<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from '../composables/useI18n'
import { 
  Plus, Settings, Wind, Lightbulb, 
  Tv, Speaker, Camera, Cpu, Smartphone,
  Box, Waves, Disc, Lock, Pencil, Trash2,
  Columns, Bell, Fan
} from 'lucide-vue-next'

const { t } = useI18n()
const devices = ref<any[]>([])
const loading = ref(true)
const activeMenuId = ref<number | null>(null)

const iconMap: Record<string, any> = {
  'Wind': Wind,
  'Lightbulb': Lightbulb,
  'Tv': Tv,
  'Speaker': Speaker,
  'Camera': Camera,
  'Cpu': Cpu,
  'Smartphone': Smartphone,
  'Box': Box,
  'Waves': Waves,
  'Disc': Disc,
  'Lock': Lock,
  'Columns': Columns,
  'Bell': Bell,
  'Fan': Fan,
  'Refrigerator': Box
}

const getIcon = (iconName: string) => {
  return iconMap[iconName] || Cpu
}

const fetchDevices = async () => {
  loading.value = true
  try {
    const host = window.location.hostname
    const response = await fetch(`http://${host}:8000/api/iot/devices`)
    if (response.ok) {
      devices.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to fetch devices:', error)
  } finally {
    loading.value = false
  }
}

const addDevice = () => {
  alert('新增裝置功能開發中')
}

const toggleDeviceMenu = (id: number) => {
  if (activeMenuId.value === id) {
    activeMenuId.value = null
  } else {
    activeMenuId.value = id
  }
}

const editDevice = (device: any) => {
  alert(`編輯裝置: ${device.name}`)
  activeMenuId.value = null
}

const deleteDevice = (device: any) => {
  if (confirm(`確定要刪除 ${device.name} 嗎？`)) {
    alert('刪除功能開發中')
  }
  activeMenuId.value = null
}

const closeAllMenus = () => {
  activeMenuId.value = null
}

onMounted(() => {
  fetchDevices()
  window.addEventListener('click', closeAllMenus)
})

onUnmounted(() => {
  window.removeEventListener('click', closeAllMenus)
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- 裝置列表 -->
    <div class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar max-h-[360px]">
      <div v-if="loading" class="flex justify-center py-8">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
      </div>
      
      <div v-else-if="devices.length === 0" class="text-center py-8 text-gray-400 text-sm">
        {{ t('iot.noDevices') }}
      </div>
      
      <div 
        v-for="device in devices" 
        :key="device.device_id"
        class="bg-white/5 border border-white/10 rounded-lg p-3 flex items-center gap-3 hover:bg-white/10 transition-colors group relative"
      >
        <div class="w-10 h-10 rounded-full bg-nomi-blue/20 flex items-center justify-center text-nomi-blue">
          <component :is="getIcon(device.icon)" class="w-5 h-5" />
        </div>
        
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-medium text-white truncate">{{ device.name }}</h3>
            <span 
              class="text-[10px] px-1.5 py-0.5 rounded-full shrink-0"
              :class="device.status === 'Online' ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'"
            >
              {{ device.status }}
            </span>
          </div>
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-xs text-gray-400 truncate">{{ device.type }}</span>
            <span v-if="device.location" class="text-[10px] text-gray-500 shrink-0">• {{ device.location }}</span>
          </div>
        </div>
        
        <div class="relative">
          <button 
            @click.stop="toggleDeviceMenu(device.device_id)"
            class="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-white/10 rounded-md transition-all text-gray-400 hover:text-white"
          >
            <Settings class="w-4 h-4" />
          </button>

          <!-- Device Settings Menu -->
          <div v-if="activeMenuId === device.device_id" 
               class="absolute right-0 top-8 w-32 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1 overflow-hidden"
               @click.stop
          >
            <button @click="editDevice(device)" class="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-white/5 flex items-center gap-2">
              <Pencil class="w-3 h-3" /> {{ t('common.confirm') }}
            </button>
            <button @click="deleteDevice(device)" class="w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 flex items-center gap-2">
              <Trash2 class="w-3 h-3" /> {{ t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部按鈕 -->
    <div class="mt-4 pt-4 border-t border-white/10">
      <button 
        @click="addDevice"
        class="w-full py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors shadow-lg shadow-primary/20"
      >
        <Plus class="w-4 h-4" />
        {{ t('common.save') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { UserPlus, Box } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'
import VectorEntryView from './VectorEntryView.vue'
import SpaceCalibrationView from './SpaceCalibrationView.vue'

const { t } = useI18n()
const activeTab = ref('vector-entry')

const tabs = computed(() => [
  { id: 'vector-entry', name: t('setup.vectorEntry'), icon: UserPlus },
  { id: 'space-calibration', name: t('setup.spaceCalibration'), icon: Box },
])

const emit = defineEmits(['status-update'])

const handleStatusUpdate = (meta: any) => {
  emit('status-update', meta)
}
</script>

<template>
  <div class="flex flex-col h-full md:w-[380px]">
    <!-- Tabs Header -->
    <div class="flex bg-gray-900/20 p-1 gap-1 mb-2">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        class="flex-1 flex items-center justify-center gap-2 py-1.5 rounded-lg transition-all text-xs font-bold"
        :class="activeTab === tab.id 
          ? 'bg-primary/10 text-primary border border-primary/20 shadow-[0_0_10px_rgba(56,145,207,0.1)]' 
          : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'"
      >
        <component :is="tab.icon" class="w-3.5 h-3.5" />
        {{ tab.name }}
      </button>
    </div>

    <!-- Tab Content -->
    <div class="flex-1 overflow-hidden relative">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-x-4"
        enter-to-class="opacity-100 translate-x-0"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-x-0"
        leave-to-class="opacity-0 -translate-x-4"
      >
        <div :key="activeTab" class="h-full overflow-y-auto custom-scrollbar">
          <VectorEntryView v-if="activeTab === 'vector-entry'" @status-update="handleStatusUpdate" />
          <SpaceCalibrationView v-if="activeTab === 'space-calibration'" @status-update="handleStatusUpdate" />
        </div>
      </Transition>
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
  background: rgba(156, 163, 175, 0.2);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(156, 163, 175, 0.4);
}
</style>

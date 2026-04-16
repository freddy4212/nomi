<script setup lang="ts">
import { ref } from 'vue'
import { Clock } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'

const { t } = useI18n()

defineProps<{
  selectedRange: { label: string, value: number }
  timeRanges: Array<{ label: string, value: number }>
}>()

const emit = defineEmits(['select'])
const showRangePicker = ref(false)

const selectRange = (range: any) => {
  emit('select', range)
  showRangePicker.value = false
}
</script>

<template>
  <div class="relative z-50">
    <button 
      @click.stop="showRangePicker = !showRangePicker"
      class="p-2 text-gray-400 hover:text-primary hover:bg-gray-800 rounded-lg transition-colors flex items-center gap-2 cursor-pointer relative"
      :class="{'text-primary bg-gray-800': showRangePicker}"
      :title="t('memory.selectTimeRange')"
    >
      <Clock class="w-5 h-5 pointer-events-none" />
    </button>

    <!-- Range Bubble -->
    <div v-if="showRangePicker" 
         class="absolute right-0 top-full mt-2 w-40 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden">
      <div class="p-1">
        <button 
          v-for="range in timeRanges" 
          :key="range.value"
          @click.stop="selectRange(range)"
          class="w-full text-left px-4 py-2.5 text-sm rounded-lg transition-colors cursor-pointer hover:bg-gray-800 hover:text-white"
          :class="selectedRange.value === range.value ? 'bg-primary/20 text-primary font-bold' : 'text-gray-400'"
        >
          {{ range.label }}
        </button>
      </div>
    </div>
    
    <!-- Click Outside Overlay -->
    <div v-if="showRangePicker" @click.stop="showRangePicker = false" class="fixed inset-0 z-40"></div>
  </div>
</template>

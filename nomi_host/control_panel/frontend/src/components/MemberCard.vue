<script setup lang="ts">
import { Pencil, Trash2 } from 'lucide-vue-next'

defineProps<{
  member: {
    id: number
    name: string
    sample_count: number
    updated_at: number | string
  }
  isSelected: boolean
  formatDateInline: (timestamp: any) => string
}>()

defineEmits(['select', 'edit', 'delete'])
</script>

<template>
  <div 
    @click="$emit('select', member.id)"
    class="flex-shrink-0 w-60 rounded-xl p-4 flex flex-col justify-center group transition-all duration-300 ease-out relative overflow-hidden h-28 cursor-pointer border"
    :class="isSelected 
      ? 'bg-gray-700 shadow-2xl -translate-y-1 border-primary/50 ring-1 ring-primary/20' 
      : 'bg-gray-900/40 border-white/5 shadow-sm hover:bg-gray-800 hover:shadow-lg hover:-translate-y-0.5 hover:border-white/10'"
  >
    <!-- ID Badge -->
    <div class="absolute top-0 right-0 bg-gray-800 px-3 py-1 rounded-bl-xl text-xs font-mono text-gray-400 border-b border-l border-gray-700">
      ID: {{ member.id }}
    </div>
    
    <!-- Action Buttons -->
    <div class="absolute top-1/2 right-3 -translate-y-1/2 flex items-center gap-2 transition-all duration-300"
      :class="isSelected ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0'"
    >
      <button 
        @click.stop="$emit('edit', member)"
        class="w-8 h-8 flex items-center justify-center text-green-400 hover:text-green-300 bg-green-500/10 hover:bg-green-500/20 rounded-full border border-green-500/30 transition-colors" 
        title="編輯成員"
      >
        <Pencil class="w-4 h-4" />
      </button>
      <button 
        @click.stop="$emit('delete', member)"
        class="w-8 h-8 flex items-center justify-center text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 rounded-full border border-red-500/30 transition-colors" 
        title="刪除成員"
      >
        <Trash2 class="w-4 h-4" />
      </button>
    </div>
    
    <!-- Name -->
    <div class="text-lg font-bold text-white truncate w-full mb-2 pr-10">{{ member.name }}</div>
    
    <!-- Details -->
    <div class="flex flex-col gap-1">
      <div class="flex items-center gap-2">
        <span class="text-[11px] text-gray-500">樣本:</span>
        <span class="text-[11px] text-primary font-bold">{{ member.sample_count || 0 }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[10px] text-gray-500">更新:</span>
        <span class="text-[10px] text-gray-400 font-mono">{{ formatDateInline(member.updated_at) }}</span>
      </div>
    </div>
  </div>
</template>

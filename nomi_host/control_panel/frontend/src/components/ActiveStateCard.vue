<script setup lang="ts">
import { User } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'

const { t, tDynamic } = useI18n()

defineProps<{
  state: {
    person_id: number
    member_name: string
    is_visible: boolean
    last_action: string
    last_seen_time: number | string
    last_location: string
  }
  formatDate: (timestamp: any) => string
}>()
</script>

<template>
  <div class="bg-bgLight/50 backdrop-blur-sm border border-gray-700 rounded-2xl p-4 hover:border-secondary/30 transition-all group shadow-lg">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-secondary/10 rounded-full flex items-center justify-center text-secondary">
          <User class="w-6 h-6" />
        </div>
        <div>
          <div class="font-bold text-white">{{ state.member_name || t('perception.unknown') }}</div>
          <div class="text-[10px] text-gray-500 uppercase tracking-tighter font-mono">Person ID: {{ state.person_id }}</div>
        </div>
      </div>
      <div class="px-2 py-1 rounded text-[10px] font-bold uppercase" 
           :class="state.is_visible ? 'bg-secondary/10 text-secondary border border-secondary/20' : 'bg-gray-700 text-gray-400'">
        {{ state.is_visible ? t('memberState.visible') : t('memberState.away') }}
      </div>
    </div>
    <div class="space-y-2 text-xs">
      <div class="flex justify-between text-gray-400">
        <span>{{ t('memberState.lastAction') }}:</span>
        <span class="text-secondary font-medium">{{ state.last_action ? tDynamic(state.last_action) : '-' }}</span>
      </div>
      <div class="flex justify-between text-gray-400">
        <span>{{ t('memberState.lastSeen') }}:</span>
        <span class="whitespace-pre-line text-right leading-tight">{{ formatDate(state.last_seen_time) }}</span>
      </div>
      <div class="flex justify-between text-gray-400">
        <span>{{ t('memberState.location') }}:</span>
        <span>{{ state.last_location ? tDynamic(state.last_location) : '-' }}</span>
      </div>
    </div>
  </div>
</template>

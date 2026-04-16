<script setup lang="ts">
import { Database } from 'lucide-vue-next'
import { useI18n } from '../composables/useI18n'

const { t, tDynamic } = useI18n()

defineProps<{
  events: any[]
  formatDate: (timestamp: any) => string
  selectedMemberId?: number | null
}>()

const formatEnvironment = (env: any) => {
  if (!env) return '-'
  const parts = []
  if (env.room) parts.push(tDynamic(env.room))
  if (env.temperature !== undefined) parts.push(`${env.temperature}°C`)
  if (env.humidity !== undefined) parts.push(`${env.humidity}%`)
  if (env.co2 !== undefined) parts.push(`CO2: ${env.co2}`)
  if (env.light !== undefined) parts.push(`${env.light} lx`)
  if (env.sound_event) parts.push(`🔊 ${tDynamic(env.sound_event)}`)
  return parts.join(' | ') || '-'
}
</script>

<template>
  <div class="flex-1 bg-bgLight/50 backdrop-blur-sm rounded-2xl border border-gray-700 overflow-hidden shadow-2xl flex flex-col min-w-0 min-h-0">
    <div class="flex-1 overflow-auto">
      <table class="w-full text-left text-sm border-collapse">
        <thead class="text-gray-400 bg-gray-800/95 sticky top-0 backdrop-blur-md z-10 shadow-sm">
          <tr>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.time') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.personId') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.member') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.action') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.confidence') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('memory.duration') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('perception.environment') }}</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">BBox</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">{{ t('perception.magnitude') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-800/50">
          <tr v-if="events.length === 0" class="text-gray-500">
            <td colspan="9" class="p-12 text-center">
              <div class="flex flex-col items-center gap-2">
                <Database class="w-12 h-12 opacity-10" />
                <p>{{ selectedMemberId ? t('common.loading') : t('common.loading') }}</p>
              </div>
            </td>
          </tr>
          <tr v-for="event in events" :key="event.id" class="hover:bg-white/5 transition-colors group">
            <td class="p-2 md:p-4 text-gray-400 font-mono text-xs whitespace-pre-line leading-tight">{{ formatDate(event.timestamp) }}</td>
            <td class="p-2 md:p-4">
              <span class="px-2 py-0.5 bg-gray-800 rounded text-xs font-mono text-gray-300">#{{ event.person_id }}</span>
            </td>
            <td class="p-2 md:p-4">
              <span v-if="event.member_name" class="text-blue-400 font-bold">{{ event.member_name }}</span>
              <span v-else class="text-gray-600">-</span>
            </td>
            <td class="p-2 md:p-4">
              <span class="px-2 py-1 bg-primary/10 text-primary rounded-lg text-xs font-medium border border-primary/20 whitespace-nowrap">
                {{ tDynamic(event.action_label) }}
              </span>
            </td>
            <td class="p-2 md:p-4">
              <div class="flex items-center gap-2">
                <div class="h-1.5 w-12 bg-gray-800 rounded-full overflow-hidden">
                  <div class="h-full bg-primary" :style="{ width: `${event.action_confidence * 100}%` }"></div>
                </div>
                <span class="text-[10px] text-gray-500">{{ (event.action_confidence * 100).toFixed(0) }}%</span>
              </div>
            </td>
            <td class="p-2 md:p-4 text-gray-400 text-xs">{{ event.action_duration ? `${event.action_duration.toFixed(1)}s` : '-' }}</td>
            <td class="p-2 md:p-4 text-gray-400 text-xs font-mono whitespace-pre-wrap min-w-[120px]">{{ event.environment ? formatEnvironment(event.environment) : '-' }}</td>
            <td class="p-2 md:p-4 text-gray-500 text-[10px] font-mono">{{ event.bbox ? event.bbox.join(',') : '-' }}</td>
            <td class="p-2 md:p-4 text-gray-400 text-xs">{{ event.motion_magnitude ? event.motion_magnitude.toFixed(2) : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

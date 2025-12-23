<script setup lang="ts">
import { Database } from 'lucide-vue-next'

defineProps<{
  events: any[]
  formatDate: (timestamp: any) => string
  selectedMemberId?: number | null
}>()
</script>

<template>
  <div class="flex-1 bg-bgLight/50 backdrop-blur-sm rounded-2xl border border-gray-700 overflow-hidden shadow-2xl flex flex-col min-w-0 min-h-0">
    <div class="flex-1 overflow-auto">
      <table class="w-full text-left text-sm border-collapse">
        <thead class="text-gray-400 bg-gray-800/95 sticky top-0 backdrop-blur-md z-10 shadow-sm">
          <tr>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">時間</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">人物 ID</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">識別成員</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">動作</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">信心度</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">持續時間</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">位置</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">BBox</th>
            <th class="p-2 md:p-4 font-medium border-b border-gray-700 whitespace-nowrap">運動量</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-800/50">
          <tr v-if="events.length === 0" class="text-gray-500">
            <td colspan="9" class="p-12 text-center">
              <div class="flex flex-col items-center gap-2">
                <Database class="w-12 h-12 opacity-10" />
                <p>{{ selectedMemberId ? '該成員暫無事件資料' : '暫無事件資料' }}</p>
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
                {{ event.action_label }}
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
            <td class="p-2 md:p-4 text-gray-400 text-xs">{{ event.environment?.room || '-' }}</td>
            <td class="p-2 md:p-4 text-gray-500 text-[10px] font-mono">{{ event.bbox ? event.bbox.join(',') : '-' }}</td>
            <td class="p-2 md:p-4 text-gray-400 text-xs">{{ event.motion_magnitude ? event.motion_magnitude.toFixed(2) : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

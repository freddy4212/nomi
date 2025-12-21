<script setup lang="ts">
import { ref } from 'vue'
import { Camera, Save, Trash2 } from 'lucide-vue-next'

const name = ref('')
const isRecording = ref(false)
</script>

<template>
  <div class="h-full flex flex-col gap-4">
    
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
      <!-- Left: Camera Feed -->
      <div class="bg-black rounded-xl border border-gray-700 relative overflow-hidden shadow-lg">
        <div class="absolute inset-0 flex items-center justify-center text-gray-600">
          <div class="text-center">
            <Camera class="w-12 h-12 mx-auto mb-2 opacity-20" />
            <p>Camera Feed</p>
          </div>
        </div>
      </div>
      
      <!-- Right: Controls -->
      <div class="bg-bgLight rounded-xl border border-gray-700 p-6 flex flex-col gap-6 shadow-lg overflow-auto">
        <div>
          <label class="block text-sm text-gray-400 mb-2 font-bold">成員名稱</label>
          <input 
            v-model="name"
            type="text" 
            class="w-full bg-bgDark border border-gray-600 rounded-lg px-4 py-3 focus:border-primary focus:outline-none transition-colors placeholder-gray-600"
            placeholder="輸入名稱..."
          >
        </div>
        
        <div class="flex-1 bg-bgDark rounded-lg border border-gray-800 p-4 flex flex-col">
          <div class="text-xs text-gray-500 mb-2 flex justify-between">
            <span>錄製狀態</span>
            <span>已錄製向量: 0</span>
          </div>
          <div class="flex-1 flex items-center justify-center text-gray-600 text-sm border-2 border-dashed border-gray-800 rounded-lg">
            尚未開始錄製
          </div>
        </div>
        
        <div class="flex gap-3">
          <button class="flex-1 bg-primary text-bgDark font-bold py-3 rounded-lg hover:bg-cyan-400 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-primary/20">
            <Camera class="w-5 h-5" />
            開始錄製
          </button>
          <button class="px-4 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-gray-300 hover:text-white">
            <Trash2 class="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

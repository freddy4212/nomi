<template>
    <div
        class="column fit"
        @dragenter.prevent.stop="onDragEnter"
        @dragover.prevent.stop="onDragOver"
        @dragleave.prevent.stop="onDragLeave"
        @drop.prevent.stop="onDrop"
    >
    <!-- Toolbar -->
    <div class="row q-pa-sm q-gutter-sm bg-grey-3 items-center" style="border-bottom: 1px solid #ddd;">
      <q-btn flat round dense icon="play_arrow" color="primary" @click="play" :disable="modelValue.length === 0">
        <q-tooltip>Run Timeline</q-tooltip>
      </q-btn>
      <q-btn flat round dense icon="stop" color="negative" @click="stop" />
      <q-separator vertical class="q-mx-sm" />
      <q-checkbox v-model="loop" label="Loop Sequence" dense size="sm" />
      <q-space />
      <div class="text-caption text-grey-7 q-mr-sm">
        {{ formattedTime }}
      </div>
      <q-btn flat round dense icon="check" color="positive" @click="emitUpdate" >
         <q-tooltip>Sync Changes</q-tooltip>
      </q-btn>
      <q-btn flat round dense icon="delete_sweep" color="grey" @click="clear" />
    </div>

    <!-- Timeline Container -->
    <div 
      ref="timelineContainer" 
        class="col relative-position timeline-dropzone"
        :class="{ 'timeline-dropzone--active': isDragOver }"
      style="background: #e0e0e0; border: 2px dashed #bbb;"
        @dragenter.prevent.stop="onDragEnter"
        @dragover.prevent.stop="onDragOver"
        @dragleave.prevent.stop="onDragLeave"
        @drop.prevent.stop="onDrop"
    >
        <div v-if="modelValue.length === 0" class="absolute-center text-grey text-h6" style="opacity: 0.5; pointer-events: none;">
           {{ isDragOver ? 'Release to Add' : 'Drop Clips Here' }}
      </div>
      <!-- Transparent full-cover drop overlay active only during drag-over -->
      <!-- Ensures vis-timeline child elements don't swallow drop events -->
      <div
        v-if="isDragOver"
        class="absolute-full"
        style="z-index: 999; background: rgba(25,118,210,0.08); pointer-events: all;"
                @dragenter.prevent.stop="onDragEnter"
                @dragover.prevent.stop="onDragOver"
        @dragleave.prevent.stop="onDragLeave"
        @drop.prevent.stop="onDrop"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { Timeline } from 'vis-timeline/standalone'
import { DataSet } from 'vis-data'
import 'vis-timeline/styles/vis-timeline-graph2d.min.css'

const props = defineProps({
  modelValue: {
    type: Array, 
    default: () => []
  },
  isPlaying: Boolean,
  currentTime: Number 
})

const emit = defineEmits(['update:modelValue', 'play', 'stop', 'seek', 'add-file']) // Added add-file

const timelineContainer = ref(null)
let timeline = null
let itemsDataSet = new DataSet([])
let groupsDataSet = new DataSet([
    {id: 'skeleton', content: 'Skeleton', order: 0},
    {id: 'environment', content: 'Environment', order: 1}
])

// State
const loop = ref(false)
const currentCursorTime = ref(0) // Internal tracking
const isDragOver = ref(false)
const dragDepth = ref(0)

const formattedTime = computed(() => {
    const totalMs = Number(props.currentTime || 0)
    const sec = totalMs / 1000
    return sec.toFixed(1) + 's'
})

const FRAME_DURATION_MS = 33

const getSkeletonDurationMs = (item) => {
    if (item.duration_ms && Number(item.duration_ms) > 0) return Number(item.duration_ms)

    const startFrame = Math.max(0, Number(item.start_frame ?? 0))
    const totalFrames = Math.max(1, Number(item.total_frames ?? 1))
    const endFrame = Number(item.end_frame ?? -1)
    const clippedEnd = endFrame >= 0 ? Math.max(startFrame, endFrame) : (totalFrames - 1)
    const frameSpan = Math.max(1, clippedEnd - startFrame + 1)
    const repeat = Math.max(1, Number(item.repeat ?? 1))
    const speed = Math.max(0.01, Number(item.speed_factor ?? 1))

    return Math.round((frameSpan * repeat * FRAME_DURATION_MS) / speed)
}

const getStableOrder = (visItem) => {
    const order = Number(visItem?.data?.drag_order)
    if (Number.isFinite(order)) return order
    return Number(visItem?.id) || 0
}

const initTimeline = () => {
  if (!timelineContainer.value) return

  itemsDataSet = new DataSet(props.modelValue.map(convertItemToVis))

  const options = {
    start: new Date(0),
    end: new Date(1000 * 60), // 1 min view
    min: new Date(0),
    max: new Date(1000 * 60 * 60), // 1 hour max
    zoomMin: 1000 * 1, // 1 sec zoom
    zoomMax: 1000 * 60 * 60, // 1 hour zoom
    moveable: true,
    zoomable: true,
    height: '100%', // Ensure it fills container
    editable: {
      add: false,         // handled by drag-drop
      updateTime: true,   // resize/move
      updateGroup: false, 
      remove: true
    },
    showCurrentTime: false, // Don't show system time
    // showCustomTime: true, // ERROR: Invalid option
    orientation: 'top',
    stack: false,       // Put items on one row if possible
    multiselect: true,
    itemsAlwaysDraggable: true,
    format: {
       minorLabels: (date, scale, step) => {
           // Handle Moment object if present, else Date
           const d = date && date.toDate ? date.toDate() : date;
           const ms = d instanceof Date ? d.getTime() : new Date(d).getTime();
           if (isNaN(ms)) return "";
           return (ms / 1000).toFixed(0) + 's'
       },
       majorLabels: (date, scale, step) => {
           const d = date && date.toDate ? date.toDate() : date;
           const ms = d instanceof Date ? d.getTime() : new Date(d).getTime();
           if (isNaN(ms)) return "";
           const min = Math.floor(ms / 1000 / 60)
           return min + 'm'
       }
    },
    onRemove: (item, callback) => {
        callback(item)
        setTimeout(() => handleRemove(item.id), 0)
    },
    onMove: (item, callback) => {
        handleMove(item)
        callback(item)
    }
  }

  timeline = new Timeline(timelineContainer.value, itemsDataSet, groupsDataSet, options)
  
  // Custom Time Bar for Playhead
  timeline.addCustomTime(new Date(0), 'playhead')
  
  // Initial Layout
  refreshLayout()

  // Event: Select
  timeline.on('select', (props) => {
      // Maybe emit selection
  })

  // Event: Drag Over from external source
  // Note: vis-timeline has internal drag/drop logic, but bridging native HTML5 DnD is tricky.
  // We will rely on parental DnD handling which updates the modelValue prop.
}

// DnD Handler
const onDrop = (evt) => {
    dragDepth.value = 0
    isDragOver.value = false
    const data = evt.dataTransfer.getData('application/json') || evt.dataTransfer.getData('text/plain')
    if (!data) return

    try {
        const file = JSON.parse(data)
        emit('add-file', file)
    } catch (e) {
        console.error('Invalid drop data', e)
    }
}

const onDragEnter = () => {
    dragDepth.value += 1
    isDragOver.value = true
}

const onDragOver = (evt) => {
    isDragOver.value = true
    if (evt?.dataTransfer) {
        evt.dataTransfer.dropEffect = 'copy'
    }
}

const onDragLeave = (evt) => {
    dragDepth.value = Math.max(0, dragDepth.value - 1)
    if (dragDepth.value === 0) {
        isDragOver.value = false
    }
}

const NTU_ACTION_LABELS = {
  "A001": "drink water",
  "A002": "eat meal",
  "A003": "brush teeth",
  "A004": "brush hair",
  "A005": "drop",
  "A006": "pick up",
  "A007": "throw",
  "A008": "sit down",
  "A009": "stand up",
  "A010": "clapping",
  "A011": "reading",
  "A012": "writing",
  "A013": "tear up paper",
  "A014": "put on jacket",
  "A015": "take off jacket",
  "A016": "put on a shoe",
  "A017": "take off a shoe",
  "A018": "put on glasses",
  "A019": "take off glasses",
  "A020": "put on a hat/cap",
  "A021": "take off a hat/cap",
  "A022": "cheer up",
  "A023": "hand waving",
  "A024": "kicking something",
  "A025": "reach into pocket",
  "A026": "hopping",
  "A027": "jump up",
  "A028": "phone call",
  "A029": "play with phone/tablet",
  "A030": "type on a keyboard",
  "A031": "point to something",
  "A032": "taking a selfie",
  "A033": "check time (from watch)",
  "A034": "rub two hands",
  "A035": "nod head/bow",
  "A036": "shake head",
  "A037": "wipe face",
  "A038": "salute",
  "A039": "put palms together",
  "A040": "cross hands in front",
  "A041": "sneeze/cough",
  "A042": "staggering",
  "A043": "falling down",
  "A044": "headache",
  "A045": "chest pain",
  "A046": "back pain",
  "A047": "neck pain",
  "A048": "nausea/vomiting",
  "A049": "fan self",
  "A050": "punch/slap",
  "A051": "kicking",
  "A052": "pushing",
  "A053": "pat on back",
  "A054": "point finger",
  "A055": "hugging",
  "A056": "giving object",
  "A057": "receive object",
  "A058": "falling",
  "A059": "walking",
  "A060": "running"
}

const extractActionCode = (fileName = '') => {
    const matched = String(fileName).match(/A\d{3}/)
    return matched ? matched[0] : null
}

const formatClipLabel = (item) => {
    const code = item.action_code || extractActionCode(item.file_name)
    const label = (code && NTU_ACTION_LABELS[code]) ? `${code}: ${NTU_ACTION_LABELS[code]}` : (code || 'Unknown')
    return `<div style="text-align: left; line-height: 1.2;">
        <div style="font-weight: bold; color: #1976D2;">${label}</div>
        <div style="font-size: 0.85em; opacity: 0.8;">${item.file_name}</div>
    </div>`
}

// Data Conversion
const convertItemToVis = (item) => {
    let group = 'skeleton'
    let contentStr = formatClipLabel(item)
    let className = 'timeline-item'
    let duration = getSkeletonDurationMs(item)
    
    if (item.type === 'environment' || item.track === 'environment') {
        group = 'environment'
        className = 'timeline-item bg-amber-2'
        if (item.env_type === 'day') {
             contentStr = `<div style="font-weight:bold; color: #F57C00;">
               <span style="font-size:0.8em;">O4H</span> Day: ${item.content}</div>`
        } else if (item.env_type === 'activity') {
             contentStr = `<div style="font-weight:bold; color: #673AB7;">
               <span style="font-size:0.8em;">O4H</span> Act: ${item.content}</div>`
        } else if (item.env_type === 'dalton_sensor') {
             const loc = item.location ? ` / ${item.location}` : ''
             contentStr = `<div style="font-weight:bold; color: #D32F2F;">
               <span style="font-size:0.8em;">DALTON</span> ${item.site_id}${loc}
               <div style="font-size:0.85em; opacity:0.8;">${item.content} (T/H/CO2)</div>
             </div>`
             className = 'timeline-item timeline-item--dalton'
        } else if (item.env_type === 'dalton_activity') {
             contentStr = `<div style="font-weight:bold; color: #E64A19;">
               <span style="font-size:0.8em;">DALTON</span> ${item.content}
               <div style="font-size:0.85em; opacity:0.7;">${item.site_id || ''}</div>
             </div>`
             className = 'timeline-item timeline-item--dalton-act'
        } else {
             contentStr = `<div style="font-weight:bold; color: #009688;">Loc: ${item.content}</div>`
        }
        if (item.duration_ms) duration = Number(item.duration_ms)
    }
    const startMs = Number(item.start_time_offset || 0)
    
    return {
        id: item.id || crypto.randomUUID(),
        group: group,
        content: contentStr,
        start: new Date(startMs), 
        end: new Date(startMs + duration), 
        type: 'range',
        className: className,
        data: item 
    }
}

// Logic to layout items sequentially PER GROUP
const refreshLayout = () => {
    if (!timeline) return
    
    const updates = []
    const allItems = itemsDataSet.get()
    
    // 1. Snapshot layout state for Skeleton Track (Sequential)
    // ONLY enforce sequential if user hasn't manually moved them (complex state)
    // For now, let's assume we WANT sequential layout for Skeleton always.
    
    let lastEndSk = 0
        const skelItems = allItems
            .filter(i => i.group === 'skeleton')
            .sort((a, b) => getStableOrder(a) - getStableOrder(b))
    
    skelItems.forEach(item => {
        const duration = getSkeletonDurationMs(item.data)
        const newStart = lastEndSk
        const newEnd = newStart + duration
        if (Math.abs(new Date(item.start).getTime() - newStart) > 5 || Math.abs(new Date(item.end).getTime() - newEnd) > 5) {
             updates.push({ ...item, start: newStart, end: newEnd })
        }
        lastEndSk = newEnd
    })

    // 2. Snapshot layout state for Environment Track (Sequential? Or Free?)
    // Let's make Environment Track sequential too for simplicity in MVP.
    let lastEndEnv = 0
        const envItems = allItems
            .filter(i => i.group === 'environment')
            .sort((a, b) => getStableOrder(a) - getStableOrder(b))
    
    envItems.forEach(item => {
        const duration = Number(item.data.duration_ms || 10000)
        const newStart = lastEndEnv
        const newEnd = newStart + duration
        
        if (Math.abs(new Date(item.start).getTime() - newStart) > 5 || Math.abs(new Date(item.end).getTime() - newEnd) > 5) {
            updates.push({ ...item, start: newStart, end: newEnd })
        }
        lastEndEnv = newEnd
    })
    
    if (updates.length > 0) {
        itemsDataSet.update(updates)
        
        // Emit updated model with calculated times
        const all = itemsDataSet.get()
        const sorted = all.sort((a,b) => a.start - b.start)
        const newModel = sorted.map(visItem => {
             // Merge visual times back into data
             const startMs = (visItem.start instanceof Date) ? visItem.start.getTime() : new Date(visItem.start).getTime()
             const endMs = (visItem.end instanceof Date) ? visItem.end.getTime() : new Date(visItem.end).getTime()
             return {
                 ...visItem.data,
                 start_time_offset: startMs,
                 duration_ms: Math.max(1, endMs - startMs)
             }
        })
        emit('update:modelValue', newModel)
    }
}

// Watch prop changes to update visualization
watch(() => props.modelValue, (newVal) => {
    // Diff calculation is expensive, just clear and re-add for prototype simplicity
    // But we want to preserve selection/state if possible.
    // Given the simplicity, let's just clear and add if lengths differ drastically.
    // Actually, refreshLayout handles positioning, but if ITEMS change (add/remove), we need to reflect that in DataSet.
    
    const currentIds = new Set(itemsDataSet.getIds())
    const newIds = new Set(newVal.map(i => i.id))
    
    // Add new items
    newVal.forEach(item => {
        if (!currentIds.has(item.id)) {
            itemsDataSet.add(convertItemToVis(item))
        }
    })
    
    // Remove old items
    currentIds.forEach(id => {
        if (!newIds.has(id)) {
            itemsDataSet.remove(id)
        }
    })
    
    refreshLayout()
}, { deep: true })


// --- API ---

const addClip = (file, durationFrames) => {
    // Calculate end of last item
    const items = itemsDataSet.get()
    let maxEnd = 0
    items.forEach(i => {
        if (i.end > maxEnd) maxEnd = i.end
    })
    
    const duration = durationFrames * FRAME_DURATION_MS
    
    itemsDataSet.add({
        id: crypto.randomUUID(),
        content: formatClipLabel(file),
        start: new Date(maxEnd),
        end: new Date(maxEnd + duration),
        type: 'range',
        style: 'background-color: #2196F3; color: white; border-radius: 4px;',
        data: {
            ...file,
            total_frames: durationFrames,
            id: Date.now() // Internal ID
        }
    })
    
    emitUpdate()
}

const handleMove = (item) => {
    // Called when user drags/resizes item
    // We might want to snap or re-sort
    // Defer to refreshLayout logic?
    setTimeout(refreshLayout, 100)
}

const handleRemove = (id) => {
    // Sync with parent after actual removal
    const items = itemsDataSet.get().filter(i => i.id !== id)
    const newModel = items.map(i => {
        const startMs = (i.start instanceof Date) ? i.start.getTime() : new Date(i.start).getTime()
        const endMs = (i.end instanceof Date) ? i.end.getTime() : new Date(i.end).getTime()
        return {
            ...i.data,
            start_time_offset: startMs,
            duration_ms: Math.max(1, endMs - startMs)
        }
    })
    emit('update:modelValue', newModel)
}

const emitUpdate = () => {
    const items = itemsDataSet.get().sort((a,b) => new Date(a.start) - new Date(b.start))
    emit('update:modelValue', items.map(i => {
        const startMs = (i.start instanceof Date) ? i.start.getTime() : new Date(i.start).getTime()
        const endMs = (i.end instanceof Date) ? i.end.getTime() : new Date(i.end).getTime()
        return {
            ...i.data,
            start_time_offset: startMs,
            duration_ms: Math.max(1, endMs - startMs)
        }
    }))
}

const play = () => {
    emit('play', { loop: loop.value })
}

const stop = () => {
    emit('stop')
}

const clear = () => {
    itemsDataSet.clear()
    emitUpdate()
}

watch(() => props.currentTime, (val) => {
    if (timeline) {
        const ms = Number(val || 0)
        timeline.setCustomTime(new Date(ms), 'playhead')
        
        // Auto scroll
        // timeline.moveTo(new Date(ms))
    }
})

onMounted(() => {
    initTimeline()
})

onUnmounted(() => {
    dragDepth.value = 0
    isDragOver.value = false
    if (timeline) timeline.destroy()
})

// Expose methods
defineExpose({
    addClip
})

</script>

<style>
.vis-item .vis-item-overflow {
  overflow: visible;
}
.vis-item {
    border-color: #1565C0;
    font-size: 12px;
}
.vis-item.timeline-item--dalton {
    background-color: #FFEBEE !important;
    border-color: #D32F2F !important;
}
.vis-item.timeline-item--dalton-act {
    background-color: #FBE9E7 !important;
    border-color: #E64A19 !important;
}
.timeline-dropzone--active {
    border-color: #1976D2 !important;
    box-shadow: inset 0 0 0 2px rgba(25, 118, 210, 0.25);
}
</style>

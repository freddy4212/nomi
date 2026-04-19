<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar>
        <!-- Top-level view switcher -->
        <q-btn-toggle
          v-model="appView"
          flat
          no-caps
          toggle-color="white"
          text-color="grey-4"
          :options="[
            { label: '模擬器', value: 'simulator', icon: 'smart_toy' },
            { label: '評估工具', value: 'evaluation', icon: 'assessment' },
          ]"
          class="q-mr-md"
          dense
          size="sm"
        />

        <q-space />
        
        <q-btn no-caps 
               size="sm"
               color="grey-9"
               label="RAW"
               class="q-mr-sm"
             v-if="sentPacketJson">
            <q-tooltip>Current Packet Data</q-tooltip>
            <q-menu anchor="bottom right" self="top right" class="q-pa-md" style="min-width: 400px; max-width: 80vw">
                <div class="text-h6 q-mb-sm">Current Packet Data</div>
            <pre class="bg-grey-2 q-pa-sm rounded-borders" style="max-height: 400px; overflow: auto; font-size: 11px; white-space: pre-wrap; word-break: break-all;">{{ JSON.stringify(sentPacketJson, null, 2) }}</pre>
            </q-menu>
        </q-btn>

        <q-btn no-caps 
               size="sm"
               :color="isTargetConnected ? 'positive' : 'negative'" 
               :label="`Target: ${targetIp}:${targetPort}`">
            <q-tooltip>Click to Configure Target</q-tooltip>
            <q-menu anchor="bottom right" self="top right" class="q-pa-md" style="min-width: 300px">
                <div class="text-h6 q-mb-md">Target Configuration</div>
                <div class="q-gutter-y-md">
                    <q-input v-model="targetIp" label="Target IP (Host)" dense outlined />
                    <q-input v-model.number="targetPort" label="Target Port (TCP)" type="number" dense outlined />
                    <div class="text-caption">
                        Status: <span :class="isTargetConnected ? 'text-positive' : 'text-negative'">{{ connectionStatusMsg }}</span>
                    </div>
                </div>
            </q-menu>
        </q-btn>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <!-- ─── Simulator View ─── -->
      <q-page v-if="appView === 'simulator'" class="q-pa-md" style="height: calc(100vh - 50px); overflow: hidden;">
        <q-splitter
          v-model="topBottomSplit"
          horizontal
          :limits="[35, 85]"
          style="height: 100%;"
        >
          <template #before>
            <q-splitter
              v-model="leftRightSplit"
              :limits="[18, 55]"
              style="height: 100%;"
            >
              <template #before>
                <q-card class="fit column">
                  <q-tabs
                    v-model="leftTab"
                    dense
                    class="bg-grey-2 text-grey-7"
                    active-color="primary"
                    indicator-color="primary"
                    align="justify"
                    narrow-indicator
                  >
                    <q-tab name="skeleton" label="Skeleton" no-caps />
                    <q-tab name="environment" label="O4H" no-caps />
                    <q-tab name="dalton" label="DALTON" no-caps />
                    <q-tab name="location" label="Location" no-caps />
                  </q-tabs>
                  <q-separator />
                  
                  <q-tab-panels v-model="leftTab" animated class="col q-pa-none">
                    <q-tab-panel name="skeleton" class="q-pa-none fit column">
                      <div class="q-pa-sm">
                        <q-select
                          v-model="selectedAction"
                          :options="filteredActions"
                          option-label="label"
                          option-value="code"
                          emit-value
                          map-options
                          label="Filter by Action"
                          dense
                          outlined
                          class="q-mb-sm"
                          @update:model-value="loadFilesByAction"
                        />
                      </div>
                      <q-list separator dense class="col scroll skeleton-list">
                        <q-item
                          v-for="file in files"
                          :key="file.file_name"
                          dense
                          draggable="true"
                          @dragstart="onDragStart($event, file, 'skeleton')"
                          class="cursor-pointer q-px-sm q-py-xs"
                          :active="selectedFile === file.file_name"
                        >
                          <q-item-section avatar class="skeleton-avatar">
                            <q-icon name="accessibility_new" color="primary" size="16px" />
                          </q-item-section>
                          <q-item-section>
                            <q-item-label class="text-weight-bold" style="color: #1976D2;">{{ getActionLabel(file.file_name) }}</q-item-label>
                            <q-item-label caption>{{ file.file_name }}</q-item-label>
                          </q-item-section>
                          <q-item-section side class="skeleton-side">
                            <div class="skeleton-actions-row">
                              <q-chip
                                dense size="xs"
                                color="blue-1" text-color="blue-9"
                                v-if="file.total_frames > 0"
                                style="font-size:9px; margin:0; height: 18px;"
                              >
                                {{ formatDuration(file.total_frames * 33 / 1000) }}
                              </q-chip>
                              <q-btn
                                flat
                                round
                                dense
                                size="xs"
                                icon="visibility"
                                color="grey-7"
                                @click.stop="previewFile(file.file_name)"
                              >
                                <q-tooltip>Preview</q-tooltip>
                              </q-btn>
                              <q-btn
                                flat
                                round
                                dense
                                size="xs"
                                icon="add"
                                color="primary"
                                @click.stop="addAssetToTimeline('skeleton', file)"
                              >
                                <q-tooltip>Add to Timeline</q-tooltip>
                              </q-btn>
                              <q-icon name="drag_indicator" size="14px" color="grey" />
                            </div>
                          </q-item-section>
                        </q-item>
                        <div v-if="files.length === 0" class="text-center text-grey q-pa-md caption">
                          Select an action to see clips
                        </div>
                      </q-list>
                    </q-tab-panel>

                    <q-tab-panel name="environment" class="q-pa-none fit column">
                      <q-list dense class="col scroll">

                        <!-- === Header === -->
                        <q-item-label header class="text-weight-bold q-pt-sm">
                          <q-icon name="home" color="orange" size="xs" class="q-mr-xs" />
                          Orange4Home — 活動時段
                          <span class="text-caption text-grey q-ml-xs">({{ activitySegments.length }} 筆)</span>
                        </q-item-label>

                        <!-- === Rooms accordion === -->
                        <template v-for="(activities, room) in activityGrouped" :key="room">
                          <!-- Room toggle row -->
                          <q-item
                            clickable
                            dense
                            class="q-px-sm"
                            style="background: rgba(255,152,0,0.08);"
                            @click="o4hExpandedRoom = o4hExpandedRoom === room ? null : room"
                          >
                            <q-item-section avatar style="min-width: 28px;">
                              <q-icon :name="o4hActivityIcon(activities[0] || '')" :color="o4hExpandedRoom === room ? 'orange' : 'orange-3'" size="sm" />
                            </q-item-section>
                            <q-item-section>
                              <q-item-label class="text-weight-bold" style="color: #E65100;">
                                {{ room }}
                              </q-item-label>
                              <q-item-label caption>
                                {{ activities.length }} 種活動 &bull;
                                {{ activitySegments.filter(s => s.room === room).length }} 筆資料
                              </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                              <q-icon
                                :name="o4hExpandedRoom === room ? 'expand_less' : 'expand_more'"
                                color="grey"
                                size="xs"
                              />
                            </q-item-section>
                          </q-item>

                          <!-- Segments inside this room (expanded) -->
                          <template v-if="o4hExpandedRoom === room">
                            <template v-for="activity in activities" :key="`${room}-${activity}`">
                              <!-- Activity sub-header -->
                              <q-item-label
                                class="text-caption q-pl-md q-py-none"
                                style="color: #7B1FA2; font-size: 10px; text-transform: uppercase; letter-spacing: 0.4px; line-height: 1.8;"
                              >
                                <q-icon name="label" size="10px" class="q-mr-xs" />{{ activity }}
                              </q-item-label>

                              <!-- Concrete instances of this activity -->
                              <q-item
                                v-for="seg in activitySegments.filter(s => s.room === room && s.activity === activity)"
                                :key="`seg-${seg.date}-${seg.start_sec}`"
                                clickable
                                v-ripple
                                draggable="true"
                                dense
                                class="q-pl-lg"
                                @dragstart="onDragStart($event, { type: 'o4h_segment', content: seg }, 'o4h_segment')"
                              >
                                <q-item-section avatar style="min-width: 24px;">
                                  <q-icon name="schedule" color="deep-purple-2" size="xs" />
                                </q-item-section>
                                <q-item-section>
                                  <q-item-label class="text-caption">
                                    {{ seg.date }}
                                    <q-chip
                                      dense
                                      size="xs"
                                      color="deep-purple-1"
                                      text-color="deep-purple-9"
                                      class="q-ml-xs"
                                      style="font-size: 9px;"
                                    >
                                      {{ formatDuration(seg.duration_sec) }}
                                    </q-chip>
                                  </q-item-label>
                                  <q-item-label caption style="font-size: 9px; color: #9E9E9E;">
                                    {{ formatTime(seg.start_sec) }} – {{ formatTime(seg.end_sec) }}
                                  </q-item-label>
                                </q-item-section>
                                <q-item-section side>
                                  <q-btn
                                    flat round dense size="xs" icon="add" color="deep-purple"
                                    @click.stop="addAssetToTimeline('o4h_segment', { type: 'o4h_segment', content: seg })"
                                  >
                                    <q-tooltip>Add to Timeline</q-tooltip>
                                  </q-btn>
                                </q-item-section>
                              </q-item>
                            </template>
                          </template>

                        </template>

                        <div v-if="Object.keys(activityGrouped).length === 0" class="text-center text-grey q-pa-md text-caption">
                          Loading...
                        </div>

                      </q-list>
                    </q-tab-panel>

                    <q-tab-panel name="location" class="q-pa-none fit column">
                        <q-list separator dense class="col scroll">
                            <q-item-label header>Room Tags</q-item-label>
                            <q-item
                                v-for="loc in locationTags"
                                :key="loc"
                                clickable
                                v-ripple
                                draggable="true"
                              @dragstart="onDragStart($event, {type: 'location', content: loc}, 'location')"
                            >
                                <q-item-section avatar>
                                    <q-icon name="room" color="teal" />
                                </q-item-section>
                                <q-item-section>
                                    <q-item-label>{{ loc }}</q-item-label>
                                </q-item-section>
                                <q-item-section side class="row items-center no-wrap q-gutter-xs">
                                  <q-btn
                                    flat
                                    round
                                    dense
                                    size="sm"
                                    icon="add"
                                    color="teal"
                                    @click.stop="addAssetToTimeline('location', { type: 'location', content: loc })"
                                  >
                                    <q-tooltip>Add to Timeline</q-tooltip>
                                  </q-btn>
                                  <q-icon name="drag_indicator" size="xs" color="grey" />
                                </q-item-section>
                            </q-item>
                        </q-list>
                    </q-tab-panel>

                    <!-- DALTON Tab -->
                    <q-tab-panel name="dalton" class="q-pa-none fit column">
                      <div class="q-pa-sm">
                        <q-select
                          v-model="daltonSelectedSite"
                          :options="daltonSiteOptions"
                          option-label="label"
                          option-value="site_id"
                          emit-value
                          map-options
                          label="DALTON Site"
                          dense
                          outlined
                          class="q-mb-xs"
                          @update:model-value="onDaltonSiteChange"
                        />
                        <q-select
                          v-if="daltonLocations.length > 0"
                          v-model="daltonSelectedLocation"
                          :options="daltonLocations"
                          label="Location / Device"
                          dense
                          outlined
                          class="q-mb-xs"
                          clearable
                        />
                      </div>
                      <q-list separator dense class="col scroll">
                        <!-- DALTON Sensor Data (per date) -->
                        <q-item-label header class="text-weight-bold">
                          <q-icon name="sensors" color="red" class="q-mr-xs" />
                          Sensor Data (T/H/CO2/PM)
                        </q-item-label>
                        <q-item
                          v-for="day in daltonDays"
                          :key="`dalton-day-${day}`"
                          clickable
                          v-ripple
                          draggable="true"
                          @dragstart="onDragStart($event, {
                            type: 'dalton_sensor',
                            content: day,
                            dataset_source: 'dalton',
                            site_id: daltonSelectedSite,
                            location: daltonSelectedLocation || ''
                          }, 'dalton_sensor')"
                        >
                          <q-item-section avatar>
                            <q-icon name="thermostat" color="red-7" />
                          </q-item-section>
                          <q-item-section>
                            <q-item-label class="text-weight-medium" style="color: #D32F2F;">
                              {{ daltonSelectedSite }} / {{ day }}
                            </q-item-label>
                            <q-item-label caption>
                              {{ daltonSelectedLocation || 'All Sensors' }} &bull; T, H, CO2, PM2.5
                            </q-item-label>
                          </q-item-section>
                          <q-item-section side class="row items-center no-wrap q-gutter-xs">
                            <q-btn
                              flat round dense size="sm" icon="add" color="red-7"
                              @click.stop="addAssetToTimeline('dalton_sensor', {
                                type: 'dalton_sensor',
                                content: day,
                                dataset_source: 'dalton',
                                site_id: daltonSelectedSite,
                                location: daltonSelectedLocation || ''
                              })"
                            >
                              <q-tooltip>Add DALTON sensor data to timeline</q-tooltip>
                            </q-btn>
                            <q-icon name="drag_indicator" size="xs" color="grey" />
                          </q-item-section>
                        </q-item>

                        <div v-if="daltonDays.length === 0 && daltonSelectedSite" class="text-center text-grey q-pa-sm text-caption">
                          Loading dates...
                        </div>

                        <!-- DALTON Activity Annotations -->
                        <q-separator spaced v-if="daltonAnnotations.length > 0" />
                        <q-item-label header v-if="daltonAnnotations.length > 0" class="text-weight-bold">
                          <q-icon name="event_note" color="deep-orange" class="q-mr-xs" />
                          Activity Annotations ({{ daltonAnnotations.length }})
                        </q-item-label>
                        <q-item
                          v-for="ann in daltonAnnotations.slice(0, 50)"
                          :key="`dalton-ann-${ann.timestamp}`"
                          clickable
                          v-ripple
                          draggable="true"
                          @dragstart="onDragStart($event, {
                            type: 'dalton_activity',
                            content: ann.label,
                            dataset_source: 'dalton',
                            site_id: daltonSelectedSite,
                            location: ann.site || ''
                          }, 'dalton_activity')"
                        >
                          <q-item-section avatar>
                            <q-icon name="label_important" color="deep-orange" />
                          </q-item-section>
                          <q-item-section>
                            <q-item-label>{{ ann.label }}</q-item-label>
                            <q-item-label caption>{{ ann.site }} &bull; {{ ann.participant }}</q-item-label>
                          </q-item-section>
                          <q-item-section side class="row items-center no-wrap q-gutter-xs">
                            <q-btn
                              flat round dense size="sm" icon="add" color="deep-orange"
                              @click.stop="addAssetToTimeline('dalton_activity', {
                                type: 'dalton_activity',
                                content: ann.label,
                                dataset_source: 'dalton',
                                site_id: daltonSelectedSite,
                                location: ann.site || ''
                              })"
                            >
                              <q-tooltip>Add annotation to timeline</q-tooltip>
                            </q-btn>
                            <q-icon name="drag_indicator" size="xs" color="grey" />
                          </q-item-section>
                        </q-item>

                        <div v-if="!daltonSelectedSite" class="text-center text-grey q-pa-lg text-caption">
                          Select a DALTON site to browse sensor data
                        </div>
                      </q-list>
                    </q-tab-panel>

                  </q-tab-panels>
                </q-card>
              </template>

              <template #after>
                <q-card class="fit column relative-position">
                  <q-card-section class="row items-center justify-between q-py-xs bg-grey-2">
                    <div class="text-subtitle2">Preview Stage</div>
                  </q-card-section>

                  <q-card-section class="col relative-position q-pa-none bg-grey-10 flex flex-center" style="overflow: hidden;">
                    <canvas
                      ref="canvasRef"
                      width="800"
                      height="600"
                      class="fit"
                      style="object-fit: contain; position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; display: block;"
                    ></canvas>

                    <div class="absolute-top-left text-white q-pa-sm" style="background: rgba(0,0,0,0.5); z-index: 2;">
                      <div class="text-caption">File: {{ currentPreviewFile || 'None' }}</div>
                      <div class="text-caption">Frame: {{ frameNo }} / {{ totalFrames }}</div>
                    </div>

                    <div class="absolute-bottom-left text-white q-pa-sm" style="background: rgba(0,0,0,0.5); z-index: 2;">
                      <div class="text-caption">Bodies: {{ renderStats.bodies }}</div>
                      <div class="text-caption">Joints: {{ renderStats.drawnJoints }}</div>
                      <div class="text-caption">Lines: {{ renderStats.drawnLines }}</div>
                      <div class="text-caption">State: {{ renderStats.message }}</div>
                    </div>

                    <!-- Environment Data Overlay -->
                    <div v-if="currentEnvData" class="absolute-bottom-right text-white q-pa-sm" style="background: rgba(0,80,0,0.7); z-index: 2; border-radius: 4px 0 0 0; max-width: 220px;">
                      <div class="text-caption text-weight-bold q-mb-xs" style="color: #69F0AE;">
                        {{ currentEnvData.source === 'dalton' ? 'DALTON' : 'O4H' }}
                        {{ currentEnvData.room ? `/ ${currentEnvData.room}` : '' }}
                      </div>
                      <div v-if="currentEnvData.temperature != null" class="text-caption">
                        Temp: {{ currentEnvData.temperature }}°C
                      </div>
                      <div v-if="currentEnvData.humidity != null" class="text-caption">
                        Humidity: {{ currentEnvData.humidity }}%
                      </div>
                      <div v-if="currentEnvData.co2 != null" class="text-caption">
                        CO2: {{ currentEnvData.co2 }} ppm
                      </div>
                      <div v-if="currentEnvData.pm2_5 != null" class="text-caption">
                        PM2.5: {{ currentEnvData.pm2_5 }} &mu;g/m³
                      </div>
                      <div v-if="currentEnvData.activity_label" class="text-caption" style="color: #FFD54F;">
                        Activity: {{ currentEnvData.activity_label }}
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </template>
            </q-splitter>
          </template>

          <template #after>
            <q-card class="fit column">
              <TimelineView
                ref="timelineViewRef"
                v-model="timelineItems"
                :is-playing="currentPlayingIndex >= 0"
                :current-time="timelineCursor"
                @play="onTimelinePlay"
                @stop="stopTimeline"
                @add-file="onTimelineAddFile"
              />
            </q-card>
          </template>
        </q-splitter>
      </q-page>

      <!-- ─── Evaluation View ─── -->
      <q-page v-if="appView === 'evaluation'">
        <EvaluationPanel :api-base="apiBase" />
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useQuasar } from 'quasar'
import axios from 'axios'
import TimelineView from './components/TimelineView.vue'
import EvaluationPanel from './components/EvaluationPanel.vue'

const $q = useQuasar()

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

const getActionLabel = (fileName = '') => {
  const matched = String(fileName).match(/A\d{3}/)
  const code = matched ? matched[0] : null
  if (code && NTU_ACTION_LABELS[code]) {
      return `${code}: ${NTU_ACTION_LABELS[code]}`
  }
  return code || 'Unknown'
}

// Maps O4H activity name → Material icon
const o4hActivityIcon = (activity = '') => {
  const a = activity.toLowerCase()
  if (a.includes('shower')) return 'shower'
  if (a.includes('sink') || a.includes('wash')) return 'water_drop'
  if (a.includes('toilet')) return 'wc'
  if (a.includes('cook') || a.includes('prepar')) return 'outdoor_grill'
  if (a.includes('eat')) return 'restaurant'
  if (a.includes('watch') || a.includes('tv')) return 'tv'
  if (a.includes('comput') || a.includes('work')) return 'computer'
  if (a.includes('read')) return 'menu_book'
  if (a.includes('sleep') || a.includes('nap')) return 'bed'
  if (a.includes('dress')) return 'checkroom'
  if (a.includes('clean')) return 'cleaning_services'
  if (a.includes('enter') || a.includes('leav') || a.includes('going')) return 'door_front'
  return 'directions_run'
}

// Format seconds → "HH:MM:SS"
const formatTime = (sec = 0) => {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

// Format duration seconds → "Xm Ys" or "Xs"
const formatDuration = (sec = 0) => {
  if (sec < 60) return `${Math.round(sec)}s`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

// --- View Toggle ---
const appView = ref('simulator')

// --- Config ---
const apiBase = ref(import.meta.env.VITE_API_BASE_URL || '/api')
const topBottomSplit = ref(62)
const leftRightSplit = ref(28)

// --- State ---
const leftTab = ref('skeleton')
const environmentDays = ref([])
const locationTags = ref([])
const activityTags = ref([])        // legacy flat list (kept for backward compat)
const activityGrouped = ref({})     // { room: [activity, ...] }
const activitySegments = ref([])    // [{room, activity, tag, date, start_sec, end_sec, duration_sec}]
const o4hExpandedRoom = ref(null)   // currently expanded room in accordion
const actions = ref([])
const filteredActions = computed(() => {
  return actions.value
    .filter(a => a.file_count > 0)
    .map(a => ({
      ...a,
      label: `${a.label} (${a.file_count})`
    }))
})
const files = ref([])
const selectedAction = ref(null)
const selectedFile = ref(null)
const currentPreviewFile = ref(null)

// --- DALTON State ---
const daltonSites = ref([])
const daltonSelectedSite = ref(null)
const daltonSelectedLocation = ref(null)
const daltonLocations = ref([])
const daltonDays = ref([])
const daltonAnnotations = ref([])
const daltonSiteOptions = computed(() => {
  return daltonSites.value.map(s => ({
    ...s,
    label: `${s.site_id} (${s.device_count} devices, ${s.locations.join(', ')})`
  }))
})

const timelineItems = ref([])
const currentPlayingIndex = ref(-1)
const loopTimeline = ref(false)

const totalFrames = ref(0)
const frameNo = ref(0)
const timelineCursor = ref(0) // New State for Timeline Cursor
const packetJson = ref(null)
const sentPacketJson = ref(null)

// Computed: Extract environment data from current packet for overlay
const currentEnvData = computed(() => {
  const pkt = sentPacketJson.value || packetJson.value
  if (!pkt) return null
  const env = pkt.environment || (pkt.data && pkt.data.environment)
  if (!env) return null
  // Only show if there's meaningful data
  if (env.temperature == null && env.humidity == null && env.co2 == null &&
      env.activity_label == null && env.pm2_5 == null) return null
  return env
})

const targetIp = ref('127.0.0.1')
const targetPort = ref(9527)
const isTargetConnected = ref(false)
const connectionStatusMsg = ref('Checking...')

// Backend status
const isConnected = ref(false)

// Visualization State
const canvasRef = ref(null)
const selectedFileMeta = ref(null)
const isPreviewPlaying = ref(false)
const renderStats = ref({
  bodies: 0,
  drawnJoints: 0,
  drawnLines: 0,
  message: 'idle'
})
let previewTimer = null
let playlistTimer = null
let statusPollingBusy = false
let healthTimer = null
let targetConnTimer = null
let dragSequence = 0

const togglePreview = () => {
    if (isPreviewPlaying.value) {
        if (previewTimer) clearInterval(previewTimer)
        isPreviewPlaying.value = false
        previewTimer = null
    } else {
        if (!selectedFile.value) return
        
        if (previewTimer) clearInterval(previewTimer) // Safety
        
        isPreviewPlaying.value = true
        previewTimer = setInterval(async () => {
             // Loop logic
             if (frameNo.value >= totalFrames.value - 1) {
                 frameNo.value = 0
             } else {
                 frameNo.value++
             }
             try {
                // Fetch next frame
                const res = await axios.get(`${apiBase.value}/preview`, { 
                    params: { file_name: selectedFile.value, frame_no: frameNo.value, protocol: 'udp' }
                })
                packetJson.value = res.data.packet
             } catch(e) {
                 console.error(e)
             }
        }, 100) // 10fps preview
    }
}


// --- Drag & Drop ---
const onDragStart = (evt, item, type = 'skeleton') => {
    // Stop Quasar ripple/click from stealing the event
    evt.stopPropagation()
    if (evt?.dataTransfer) {
      evt.dataTransfer.dropEffect = 'copy'
      evt.dataTransfer.effectAllowed = 'copy'
    }
    const payload = { type, content: item }
    const payloadStr = JSON.stringify(payload)
    evt.dataTransfer.setData('application/json', payloadStr)
    evt.dataTransfer.setData('text/plain', payloadStr)
}

const addAssetToTimeline = (type, content) => {
    onTimelineAddFile({ type, content })
}

const onTimelineAddFile = async (payload) => {
    // Backward compatibility if TimelineView passes raw object
    if (!payload.type && payload.file_name) {
        payload = { type: 'skeleton', content: payload }
    }

    if (payload.type === 'skeleton') {
        const file = payload.content
        // Use total_frames already embedded in file (from API), fallback to meta request
        let tFrames = file.total_frames && file.total_frames > 0 ? file.total_frames : 0
        if (!tFrames) {
          try {
              const res = await axios.get(`${apiBase.value}/files/${file.file_name}/meta`)
              tFrames = res.data.total_frames
          } catch(e) {}
        }
        timelineItems.value.push({
            id: Date.now() + Math.random(),
            type: 'skeleton',
        drag_order: dragSequence++,
            file_name: file.file_name,
            start_frame: 0,
            end_frame: -1,
            repeat: 1,
            speed_factor: 1.0,
            total_frames: tFrames,
            track: 'skeleton'
        })
    } else if (payload.type === 'day') {
        // Environment Item
        timelineItems.value.push({
            id: Date.now() + Math.random(),
            type: 'environment', // Internal type
        drag_order: dragSequence++,
            env_type: 'day',
            content: payload.content.content || payload.content, // Handle wrapper
            duration_ms: 10000, // Default 10s
            track: 'environment'
        })
    } else if (payload.type === 'location') {
        timelineItems.value.push({
            id: Date.now() + Math.random(),
            type: 'environment',
        drag_order: dragSequence++,
            env_type: 'location',
            content: payload.content.content || payload.content,
            duration_ms: 5000,
            track: 'environment'
        })
    } else if (payload.type === 'activity') {
      timelineItems.value.push({
        id: Date.now() + Math.random(),
        type: 'environment',
        drag_order: dragSequence++,
        env_type: 'activity',
        content: payload.content.content || payload.content,
        duration_ms: 3000,
        track: 'environment'
      })
    } else if (payload.type === 'o4h_segment') {
      // Orange4Home real activity segment with actual sensor time window
      const seg = payload.content
      timelineItems.value.push({
        id: Date.now() + Math.random(),
        type: 'environment',
        drag_order: dragSequence++,
        env_type: 'o4h_segment',
        // content = date string so backend knows which day to query
        content: seg.date,
        dataset_source: 'o4h',
        location: seg.room || '',
        activity_label: seg.activity || seg.tag || '',
        // Real time window inside the day
        data_start_sec: seg.start_sec,
        data_end_sec: seg.end_sec,
        // Duration capped at the actual segment length (ms)
        duration_ms: Math.round((seg.duration_sec || 30) * 1000),
        track: 'environment',
        // Display metadata
        _seg_room: seg.room,
        _seg_activity: seg.activity,
        _seg_date: seg.date,
      })
    } else if (payload.type === 'dalton_sensor') {
      // DALTON sensor data segment
      const c = payload.content
      timelineItems.value.push({
        id: Date.now() + Math.random(),
        type: 'environment',
        drag_order: dragSequence++,
        env_type: 'dalton_sensor',
        content: c.content || c,
        dataset_source: 'dalton',
        site_id: c.site_id || daltonSelectedSite.value || '',
        location: c.location || daltonSelectedLocation.value || '',
        duration_ms: 10000,
        track: 'environment'
      })
    } else if (payload.type === 'dalton_activity') {
      // DALTON activity annotation
      const c = payload.content
      timelineItems.value.push({
        id: Date.now() + Math.random(),
        type: 'environment',
        drag_order: dragSequence++,
        env_type: 'dalton_activity',
        content: c.content || c,
        dataset_source: 'dalton',
        site_id: c.site_id || daltonSelectedSite.value || '',
        location: c.location || '',
        duration_ms: 5000,
        track: 'environment'
      })
    }
}

const onTimelinePlay = ({ loop }) => {
    loopTimeline.value = loop
    runTimeline()
}

const calcSkeletonDurationMs = (item) => {
  if (item.duration_ms && Number(item.duration_ms) > 0) return Number(item.duration_ms)
  const startFrame = Math.max(0, Number(item.start_frame ?? 0))
  const totalFrames = Math.max(1, Number(item.total_frames ?? 1))
  const endFrame = Number(item.end_frame ?? -1)
  const clippedEnd = endFrame >= 0 ? Math.max(startFrame, endFrame) : (totalFrames - 1)
  const frameSpan = Math.max(1, clippedEnd - startFrame + 1)
  const repeat = Math.max(1, Number(item.repeat ?? 1))
  const speed = Math.max(0.01, Number(item.speed_factor ?? 1))
  return Math.round((frameSpan * repeat * 33) / speed)
}

const moveItem = (index, direction) => {
    if (index + direction < 0 || index + direction >= timelineItems.value.length) return
    const temp = timelineItems.value[index]
    timelineItems.value[index] = timelineItems.value[index + direction]
    timelineItems.value[index + direction] = temp
}

// --- API Actions ---

const previewFile = async (fname) => {
   selectedFile.value = fname
   currentPreviewFile.value = fname
   try {
      const metaRes = await axios.get(`${apiBase.value}/files/${fname}/meta`)
      selectedFileMeta.value = metaRes.data
      totalFrames.value = metaRes.data.total_frames || 0
      frameNo.value = 0
      
      const res = await axios.get(`${apiBase.value}/preview`, {
         params: { file_name: fname, frame_no: 0, protocol: 'udp' }
      })
      packetJson.value = res.data.packet
      sentPacketJson.value = null
   } catch (e) {
      console.error(e)
   }
}

const runTimeline = async () => {
    if (timelineItems.value.length === 0) return
    
    // Separate Skeleton and Environment items
    const skeletonItems = timelineItems.value
        .filter(item => !item.type || item.type === 'skeleton')
        .map(item => ({
            file_name: item.file_name,
            start_frame: item.start_frame,
            end_frame: item.end_frame,
            repeat: Number(item.repeat), 
            speed_factor: Number(item.speed_factor),
            // Use visual start time if available (from TimelineView updates)
            start_time_offset: item.start_time_offset || 0,
        duration_ms: calcSkeletonDurationMs(item)
        }))

    const environmentItems = timelineItems.value
        .filter(item => item.type === 'environment')
        .map(item => ({
            type: item.env_type,
            content: item.content,
            start_time_offset: item.start_time_offset || 0,
            // For o4h_segment: real day offset; for day: default 0
            data_offset_sec: item.env_type === 'o4h_segment' ? (item.data_start_sec || 0) : 0,
            data_end_sec: item.env_type === 'o4h_segment' ? (item.data_end_sec || 0) : 0,
            activity_label: item.activity_label || '',
            duration_ms: item.duration_ms || 10000,
            // DALTON-specific / shared fields
            dataset_source: item.dataset_source || 'o4h',
            site_id: item.site_id || '',
            location: item.location || '',
        }))

    try {
        await axios.post(`${apiBase.value}/playlist/start`, {
            items: skeletonItems,
            environment_items: environmentItems,
            target_ip: targetIp.value,
            target_port: Number(targetPort.value),
            protocol: 'tcp',
            loop_playlist: loopTimeline.value,
            interval_ms: 33
        })
        $q.notify({ type: 'positive', message: 'Timeline Started' })
        currentPlayingIndex.value = 0 
        
        // --- ADDED: Start Playhead tracking ---
        if (previewTimer) clearInterval(previewTimer)
        isPreviewPlaying.value = false
        
        // Polling loop
        if (playlistTimer) clearInterval(playlistTimer)
        playlistTimer = setInterval(async () => {
          if (statusPollingBusy) return
          statusPollingBusy = true
            try {
                const res = await axios.get(`${apiBase.value}/status`)
                if (res.data.is_running && res.data.current_frame) {
                    const status = res.data.current_frame
                    // Update state for visualization
                    packetJson.value = { ...status.packet }
                    sentPacketJson.value = status.sent_packet ? { ...status.sent_packet } : null
                    nextTick(() => renderFromPacket())
                    
                    // Update Frame Counter & File Info
                    frameNo.value = status.frame_no
                    currentPreviewFile.value = status.file_name
                    
                    // Update Timeline Cursor (Global Time)
                    if (status.simulation_time !== undefined) {
                      timelineCursor.value = Number(status.simulation_time)
                    } else {
                        // Very simplified fallback
                      timelineCursor.value = Number(frameNo.value) * 33
                    }
                    
                    // For now, just showing the local frame update proves "movement"
                } else if (!res.data.is_running) {
                    // Stopped
                    clearInterval(playlistTimer)
                    currentPlayingIndex.value = -1
                }
            } catch (e) {
                console.error("Polling error", e)
              } finally {
                statusPollingBusy = false
            }
        }, 100)
    } catch(e) {
        console.error(e)
        $q.notify({ type: 'negative', message: 'Failed to start' })
    }
}

const stopTimeline = async () => {
    try {
        await axios.post(`${apiBase.value}/stop`)
        currentPlayingIndex.value = -1
        if (playlistTimer) clearInterval(playlistTimer)
    sentPacketJson.value = null
        $q.notify({ type: 'info', message: 'Stopped' })
    } catch(e) {}
}

const loadActions = async () => {
  try {
    const res = await axios.get(`${apiBase.value}/actions`)
    actions.value = res.data || []
  } catch (e) {
    console.error("Failed to load actions", e)
  }
}

const loadFilesByAction = async (act) => {
  if (!act) return
  files.value = []
  try {
    const res = await axios.get(`${apiBase.value}/actions/${act}/files`)
    files.value = res.data || []
  } catch (e) {
    console.error("Failed to load files", e)
  }
}

const checkTargetConnection = async () => {
    try {
        const res = await axios.get(`${apiBase.value}/connection/status`, {
            params: { target_ip: targetIp.value, target_port: targetPort.value }
        })
        isTargetConnected.value = res.data.connected
        connectionStatusMsg.value = res.data.message
    } catch (e) {
        isTargetConnected.value = false
        connectionStatusMsg.value = 'Unreachable'
    }
}

const checkLocalConnection = async () => {
  try {
    const res = await axios.get(`${apiBase.value}/health`)
    isConnected.value = res.data.status === 'ok'
  } catch (e) {
    isConnected.value = false
  }
}

const loadEnvironmentData = async () => {
    try {
        const res = await axios.get(`${apiBase.value}/environment/days`)
        environmentDays.value = res.data || []
    } catch (e) { console.error(e) }
}

const loadEnvironmentLocations = async () => {
    try {
        const res = await axios.get(`${apiBase.value}/environment/locations`)
        locationTags.value = res.data || []
    } catch (e) { console.error(e) }
}

const loadEnvironmentActivityTags = async () => {
  try {
    const [tagsRes, groupedRes, segsRes] = await Promise.all([
      axios.get(`${apiBase.value}/environment/activity-tags`),
      axios.get(`${apiBase.value}/environment/activity-list/grouped`),
      axios.get(`${apiBase.value}/environment/activity-segments`),
    ])
    activityTags.value = tagsRes.data || []
    activityGrouped.value = groupedRes.data || {}
    activitySegments.value = segsRes.data || []
  } catch (e) { console.error('Failed to load O4H activity tags', e) }
}

// --- DALTON Data Loading ---

const loadDaltonSites = async () => {
  try {
    const res = await axios.get(`${apiBase.value}/dalton/sites`)
    daltonSites.value = res.data || []
  } catch (e) { console.error("Failed to load DALTON sites", e) }
}

const onDaltonSiteChange = async (siteId) => {
  daltonDays.value = []
  daltonLocations.value = []
  daltonAnnotations.value = []
  daltonSelectedLocation.value = null
  if (!siteId) return

  try {
    const [daysRes, locsRes, annsRes] = await Promise.all([
      axios.get(`${apiBase.value}/dalton/sites/${siteId}/days`),
      axios.get(`${apiBase.value}/dalton/sites/${siteId}/locations`),
      axios.get(`${apiBase.value}/dalton/sites/${siteId}/annotations`),
    ])
    daltonDays.value = daysRes.data || []
    daltonLocations.value = locsRes.data || []
    daltonAnnotations.value = annsRes.data || []
  } catch (e) {
    console.error("Failed to load DALTON site data", e)
  }
}

// --- Visualization Logic ---

const resetView = () => {
   renderFromPacket()
}

const syncCanvasSize = () => {
  if (!canvasRef.value) return
  const displayWidth = Math.max(1, Math.floor(canvasRef.value.clientWidth || 800))
  const displayHeight = Math.max(1, Math.floor(canvasRef.value.clientHeight || 600))
  if (canvasRef.value.width !== displayWidth || canvasRef.value.height !== displayHeight) {
    canvasRef.value.width = displayWidth
    canvasRef.value.height = displayHeight
  }
}

// Key Rendering Function
const renderFromPacket = () => {
   if (!canvasRef.value) return
  syncCanvasSize()
   const ctx = canvasRef.value.getContext('2d')
   const width = canvasRef.value.width
   const height = canvasRef.value.height
  renderStats.value = { bodies: 0, drawnJoints: 0, drawnLines: 0, message: 'rendering' }
   
   // Clear with semi-transparent black for trail effect or just clear
   ctx.clearRect(0, 0, width, height)
   
   // Visualization Style Config
   const STYLE = {
       bgColor: '#000000',
       gridColor: '#333333',
       boneColor: '#4CC9F0', // Light Blue
       jointColor: '#F72585', // Pink
       headColor: '#FFD166', // Yellow
       textColor: '#ffffff',
       lineWidth: 3,
       jointRadius: 4
   }

   // Optional: Fill Background
   // ctx.fillStyle = STYLE.bgColor
   // ctx.fillRect(0,0,width,height)

   if (!packetJson.value) {
       // Draw placeholder
       ctx.fillStyle = '#666'
       ctx.font = '20px monospace'
       ctx.textAlign = 'center'
       ctx.fillText("No Data", width/2, height/2)
       renderStats.value.message = 'no-packet'
       return 
   }

   let bodies = []
   if (packetJson.value.data) {
       bodies = packetJson.value.data.bodies || packetJson.value.data.keypoints || []
   } else if (packetJson.value.keypoints) {
       bodies = packetJson.value.keypoints
   }

   // Draw background grid (Simple & Beautiful)
   ctx.strokeStyle = STYLE.gridColor
   ctx.lineWidth = 1
   ctx.beginPath()
   const gridSize = 50
   for(let x=0; x<width; x+=gridSize) { ctx.moveTo(x, 0); ctx.lineTo(x, height); }
   for(let y=0; y<height; y+=gridSize) { ctx.moveTo(0, y); ctx.lineTo(width, y); }
   ctx.stroke()
   
     if (!bodies || bodies.length === 0) {
       ctx.fillStyle = '#B0BEC5'
       ctx.font = '16px monospace'
       ctx.textAlign = 'center'
       ctx.fillText('No keypoints in this frame', width/2, height/2)
       renderStats.value.message = 'no-bodies'
       return
     }

   renderStats.value.bodies = bodies.length

  let totalLines = 0
  let totalJoints = 0

  bodies.forEach(body => {
        let kps = []
        // Standardize Keypoints
        if (Array.isArray(body)) {
            // NTU Rich Format: [0] is BBox, [1:] are Keypoints
            // Check if first element looks like bbox (len 6)
            if (body.length > 0 && Array.isArray(body[0]) && body[0].length === 6) {
                kps = body.slice(1)
            } else {
                // Raw Keypoints List?
                kps = body
            }
        } else if (body && body.keypoints) {
            // Object format
            kps = body.keypoints
        }

        if (!kps || kps.length === 0) return

        const valid2D = kps
          .filter(kp => Array.isArray(kp) && kp.length >= 3 && Number.isFinite(Number(kp[0])) && Number.isFinite(Number(kp[1])) && Number(kp[2]) > 0)
          .map(kp => ({ x: Number(kp[0]), y: Number(kp[1]) }))

        const useFitTransform = valid2D.length >= 2
        let minX = 0
        let maxX = 1920
        let minY = 0
        let maxY = 1080
        let fitScale = 1
        let offsetX = 0
        let offsetY = 0
        const padding = 24

        if (useFitTransform) {
          minX = Math.min(...valid2D.map(p => p.x))
          maxX = Math.max(...valid2D.map(p => p.x))
          minY = Math.min(...valid2D.map(p => p.y))
          maxY = Math.max(...valid2D.map(p => p.y))

          const rangeX = Math.max(1, maxX - minX)
          const rangeY = Math.max(1, maxY - minY)
          const viewW = Math.max(1, width - padding * 2)
          const viewH = Math.max(1, height - padding * 2)

          fitScale = Math.min(viewW / rangeX, viewH / rangeY)
          offsetX = (width - rangeX * fitScale) / 2
          offsetY = (height - rangeY * fitScale) / 2
        }

        const project = (i) => {
            const kp = kps[i]
            if (!kp || !Array.isArray(kp) || kp.length < 3) return { x: 0, y: 0, s: 0, valid: false }
            
            let x = Number(kp[0])
            let y = Number(kp[1])
            if (useFitTransform) {
              x = (x - minX) * fitScale + offsetX
              y = (y - minY) * fitScale + offsetY
            } else {
              const scaleX = width / 1920
              const scaleY = height / 1080
              x = x * scaleX
              y = y * scaleY
            }

            return { 
            x,
            y,
            s: Number(kp[2]), 
                valid: true 
            } 
        }

        // Bones COCO 17
        const connections = [
           [0, 1], [0, 2], [1, 3], [2, 4],     // Face
           [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], // Arms
           [5, 11], [6, 12],                   // Torso
           [11, 12], [11, 13], [13, 15], [12, 14], [14, 16] // Legs
        ]
        
        ctx.lineWidth = STYLE.lineWidth
        ctx.lineCap = 'round'
        
        connections.forEach(([s, e]) => {
            const p1 = project(s), p2 = project(e)
            if (p1.valid && p2.valid && p1.s > 0.1 && p2.s > 0.1) {
                 ctx.strokeStyle = STYLE.boneColor
                 ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke()
             totalLines += 1
            }
        })

        // Joints
        kps.forEach((_, i) => {
            const p = project(i)
            if (p.valid && p.s > 0.1) {
                ctx.fillStyle = i === 0 ? STYLE.headColor : STYLE.jointColor
                ctx.beginPath(); 
                ctx.arc(p.x, p.y, i===0 ? STYLE.jointRadius*1.5 : STYLE.jointRadius, 0, 2*Math.PI); 
                ctx.fill()
            totalJoints += 1
            }
        })
   })

       renderStats.value.drawnLines = totalLines
       renderStats.value.drawnJoints = totalJoints
       renderStats.value.message = totalJoints > 0 ? 'ok' : 'no-visible-joints'
}

// Watchers
watch(packetJson, () => {
   nextTick(() => renderFromPacket())
}, { deep: true })

// Lifecycle
onMounted(() => {
  checkLocalConnection()
  loadActions()
  loadEnvironmentData()
  loadEnvironmentLocations()
  loadEnvironmentActivityTags()
  loadDaltonSites()
  nextTick(() => renderFromPacket())
  
  healthTimer = setInterval(checkLocalConnection, 5000)
  targetConnTimer = setInterval(() => {
      if (isConnected.value) checkTargetConnection() 
  }, 3000)
})

onUnmounted(() => {
  if (previewTimer) clearInterval(previewTimer)
  if (playlistTimer) clearInterval(playlistTimer)
  if (healthTimer) clearInterval(healthTimer)
  if (targetConnTimer) clearInterval(targetConnTimer)
})

</script>

<style scoped>
canvas {
  touch-action: none; /* Prevent scroll on touch */
}

.skeleton-list .q-item {
  min-height: 40px;
}

.skeleton-list .q-item__label {
  line-height: 1.1;
}

.skeleton-list .skeleton-avatar {
  min-width: 28px;
}

.skeleton-list .skeleton-side {
  gap: 2px;
  min-width: 128px;
}

.skeleton-list .skeleton-actions-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: nowrap;
  gap: 2px;
  white-space: nowrap;
}
</style>
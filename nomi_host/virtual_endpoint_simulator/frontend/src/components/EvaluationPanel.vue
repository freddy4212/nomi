<template>
  <div class="evaluation-panel q-pa-md">
    <!-- ═══════════ Toolbar ═══════════ -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section class="row items-center q-gutter-sm q-py-sm">
        <!-- Connection indicators -->
        <q-chip :color="conn.sim ? 'green' : 'red'" text-color="white" dense icon="dns" size="sm">
          Simulator {{ conn.sim ? '✓' : '✗' }}
        </q-chip>
        <q-chip :color="conn.nomi ? 'green' : 'red'" text-color="white" dense icon="psychology" size="sm">
          NOMI Host {{ conn.nomi ? '✓' : '✗' }}
        </q-chip>
        <q-space />
        <!-- Runs per scenario -->
        <q-input v-model.number="runsPerScenario" type="number" dense outlined
                 label="每場景執行次數" style="width:140px" :min="1" :max="20"
                 :disable="isRunning" />
        <q-btn color="primary" icon="play_arrow" label="開始評估"
               :disable="isRunning || !conn.sim || !conn.nomi"
               @click="startEvaluation" />
        <q-btn color="negative" icon="stop" label="取消" flat
               :disable="!isRunning" @click="cancelEvaluation" />
        <q-btn color="grey" icon="refresh" flat dense @click="checkConnectivity" />
      </q-card-section>

      <!-- Progress -->
      <q-linear-progress v-if="isRunning" :value="progress" color="primary" stripe animate class="q-mx-md q-mb-sm" />
      <q-card-section v-if="progressText" class="q-py-xs text-caption text-grey-7 q-px-md">
        {{ progressText }}
      </q-card-section>
    </q-card>

    <!-- ═══════════ Tabs: 即時結果 / 圖表分析 / 歷史紀錄 ═══════════ -->
    <q-tabs v-model="mainTab" dense class="text-grey" active-color="primary" indicator-color="primary" align="left">
      <q-tab name="live" label="即時結果" icon="terminal" />
      <q-tab name="charts" label="圖表分析" icon="bar_chart" :disable="!hasResults" />
      <q-tab name="history" label="歷史紀錄" icon="history" />
    </q-tabs>
    <q-separator />

    <q-tab-panels v-model="mainTab" animated>
      <!-- ─── Live Results ─── -->
      <q-tab-panel name="live" class="q-pa-none">
        <div class="q-pa-sm" style="max-height: calc(100vh - 280px); overflow-y: auto;">
          <q-banner v-if="!isRunning && liveLog.length === 0" class="bg-grey-2 text-grey-7 q-mb-sm">
            點擊「開始評估」，即時結果會顯示在這裡
          </q-banner>

          <!-- Per-category live accordion -->
          <q-list v-if="liveCategories.length" bordered separator>
            <q-expansion-item v-for="cat in liveCategories" :key="cat.id"
                              :label="cat.name" :caption="`${cat.done}/${cat.total} 場景`"
                              :header-style="{ backgroundColor: cat.color + '15' }"
                              default-opened dense>
              <q-list dense separator>
                <q-item v-for="sc in cat.scenarios" :key="sc.id">
                  <q-item-section>
                    <q-item-label>{{ sc.name }}</q-item-label>
                    <q-item-label v-if="sc.ground_truth" caption class="text-grey-5" style="font-size: 0.7em">
                      GT: {{ sc.ground_truth }}
                    </q-item-label>
                    <q-item-label caption>
                      <span v-for="(run, ri) in sc.runs" :key="ri" class="q-mr-md">
                        <span class="text-grey-6" :title="run.variant_label || ''">
                          R{{ ri + 1 }}
                          <span v-if="run.variant_label" class="text-grey-8" style="font-size:0.75em"> [{{ run.variant_label.split('（')[0] }}]</span>
                        </span>
                        <q-badge :color="scoreColor(run.score_a)" class="q-mr-xs q-ml-xs"
                                 :title="(run.variant_label ? run.variant_label + '\nGT: ' : 'GT: ') + (run.gt || sc.ground_truth || '')">
                          A:{{ run.label_a || '…' }}
                          <span class="q-ml-xs">{{ scoreIcon(run.score_a) }}</span>
                        </q-badge>
                        <q-badge :color="scoreColor(run.score_b)" class="q-mr-xs"
                                 :title="(run.variant_label ? run.variant_label + '\nGT: ' : 'GT: ') + (run.gt || sc.ground_truth || '')">
                          B:{{ run.label_b || '…' }}
                          <span class="q-ml-xs">{{ scoreIcon(run.score_b) }}</span>
                        </q-badge>
                      </span>
                      <q-spinner-dots v-if="sc.pending" size="16px" color="primary" class="q-ml-sm" />
                    </q-item-label>
                  </q-item-section>
                  <q-item-section side v-if="sc.accuracy_no_env != null">
                    <q-item-label>
                      <span class="text-grey-7">A:</span>
                      <span class="text-weight-medium q-ml-xs">{{ sc.accuracy_no_env }}%</span>
                      <q-icon name="arrow_forward" size="xs" color="primary" class="q-mx-xs" />
                      <span class="text-grey-7">B:</span>
                      <span class="text-primary text-weight-bold q-ml-xs">{{ sc.accuracy_with_env }}%</span>
                    </q-item-label>
                    <q-item-label caption>
                      Δ<span :class="(sc.accuracy_with_env - sc.accuracy_no_env) >= 0 ? 'text-positive' : 'text-negative'">
                        {{ (sc.accuracy_with_env - sc.accuracy_no_env) >= 0 ? '+' : '' }}{{ (sc.accuracy_with_env - sc.accuracy_no_env).toFixed(1) }}%
                      </span>
                      ｜ 魯棒 A:{{ sc.robustness_no_env }}% B:{{ sc.robustness_with_env }}%
                    </q-item-label>
                    <q-item-label caption v-if="sc.breakdown_with_env">
                      正確{{ sc.breakdown_with_env.exact }} 部分{{ sc.breakdown_with_env.partial }} 錯誤{{ sc.breakdown_with_env.miss }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-expansion-item>
          </q-list>

          <!-- Log stream -->
          <div v-if="liveLog.length" class="q-mt-sm">
            <div class="text-caption text-grey-6 q-mb-xs">日誌</div>
            <q-virtual-scroll :items="liveLog" style="max-height: 200px" v-slot="{ item }">
              <div class="text-caption" :class="item.level === 'error' ? 'text-negative' : 'text-grey-7'">
                {{ item.time }} {{ item.msg }}
              </div>
            </q-virtual-scroll>
          </div>
        </div>
      </q-tab-panel>

      <!-- ─── Charts Panel ─── -->
      <q-tab-panel name="charts" class="q-pa-sm">
        <div v-if="!hasResults" class="text-center text-grey q-pa-lg">尚無評估結果</div>

        <template v-else>
          <!-- LLM Semantic Judge toggle -->
          <div class="row items-center q-mb-sm q-gutter-sm">
            <q-toggle v-model="lenientMode" label="LLM 語意評審" color="deep-purple"
                      icon="psychology" @update:model-value="onLenientToggle" />
            <span v-if="lenientMode" class="text-caption text-deep-purple-8">
              使用 Gemini 語意比對，自動識別相同事件的不同表達
            </span>
            <q-spinner-dots v-if="rescoring" size="20px" color="deep-purple" class="q-ml-sm" />
          </div>

          <!-- Overall summary cards -->
          <div class="row q-gutter-sm q-mb-md">
            <q-card v-for="cat in chartData" :key="cat.id" flat bordered
                    class="col" :style="{ borderLeft: `4px solid ${cat.color}` }">
              <q-card-section class="q-py-sm">
                <div class="text-subtitle2" :style="{ color: cat.color }">{{ cat.name }}</div>
                <div class="row q-gutter-sm q-mt-xs">
                  <div>
                    <div class="text-caption text-grey">純骨架</div>
                    <div class="text-h6">{{ cat.summary.accuracy_no_env }}%</div>
                  </div>
                  <div>
                    <div class="text-caption text-grey">+環境</div>
                    <div class="text-h6 text-primary">{{ cat.summary.accuracy_with_env }}%</div>
                  </div>
                  <div>
                    <div class="text-caption text-grey">提升 Δ</div>
                    <div class="text-h6" :class="cat.summary.delta >= 0 ? 'text-positive' : 'text-negative'">
                      {{ cat.summary.delta >= 0 ? '+' : '' }}{{ cat.summary.delta }}%
                    </div>
                  </div>
                  <q-separator vertical />
                  <div>
                    <div class="text-caption text-grey">魯棒 A</div>
                    <div class="text-subtitle1" :class="robustnessColor(cat.summary.robustness_no_env)">
                      {{ cat.summary.robustness_no_env }}%
                    </div>
                  </div>
                  <div>
                    <div class="text-caption text-grey">魯棒 B</div>
                    <div class="text-subtitle1" :class="robustnessColor(cat.summary.robustness_with_env)">
                      {{ cat.summary.robustness_with_env }}%
                    </div>
                  </div>
                </div>
              </q-card-section>
            </q-card>
          </div>

          <!-- Overall aggregate row -->
          <q-card flat bordered class="q-mb-md bg-grey-1" v-if="activeResults.overall">
            <q-card-section class="q-py-sm">
              <div class="row items-center q-gutter-md">
                <div class="text-subtitle2 text-grey-7">整體結果</div>
                <div>
                  <span class="text-caption text-grey-6">純骨架準確率</span>
                  <span class="text-h6 q-ml-sm">{{ activeResults.overall.overall_accuracy_no_env }}%</span>
                </div>
                <div>
                  <span class="text-caption text-grey-6">骨架+環境準確率</span>
                  <span class="text-h6 text-primary q-ml-sm">{{ activeResults.overall.overall_accuracy_with_env }}%</span>
                </div>
                <div>
                  <span class="text-caption text-grey-6">準確率提升</span>
                  <span class="text-h6 q-ml-sm" :class="activeResults.overall.overall_delta >= 0 ? 'text-positive' : 'text-negative'">
                    {{ activeResults.overall.overall_delta >= 0 ? '+' : '' }}{{ activeResults.overall.overall_delta }}%
                  </span>
                </div>
                <q-separator vertical />
                <div>
                  <span class="text-caption text-grey-6">整體魯棒性 A</span>
                  <span class="text-subtitle1 q-ml-sm" :class="robustnessColor(activeResults.overall.overall_robustness_no_env)">
                    {{ activeResults.overall.overall_robustness_no_env }}%
                  </span>
                </div>
                <div>
                  <span class="text-caption text-grey-6">整體魯棒性 B</span>
                  <span class="text-subtitle1 q-ml-sm" :class="robustnessColor(activeResults.overall.overall_robustness_with_env)">
                    {{ activeResults.overall.overall_robustness_with_env }}%
                  </span>
                </div>
              </div>
            </q-card-section>
          </q-card>

          <!-- Per-scenario: 1 chart each -->
          <div v-for="(sc, scIdx) in scenarioCharts" :key="'sc_' + sc.id" class="q-mb-lg">
            <q-card flat bordered>
              <q-card-section class="q-pa-sm">
                <div class="row items-center q-mb-xs">
                  <span class="text-subtitle2 text-grey-7">Scenario {{ scIdx + 1 }}</span>
                  <q-space />
                  <q-btn
                    flat dense round icon="download"
                    size="sm" color="grey-7"
                    title="Download chart as PNG"
                    @click="downloadChart(sc)"
                  />
                </div>
                <v-chart
                  :ref="(el) => { if (el) chartRefs[sc.id] = el; else delete chartRefs[sc.id] }"
                  :option="sc.chart"
                  autoresize
                  style="height: 320px"
                />
              </q-card-section>
            </q-card>
          </div>
        </template>
      </q-tab-panel>

      <!-- ─── History ─── -->
      <q-tab-panel name="history">
        <q-btn flat icon="refresh" label="刷新" @click="loadHistory" class="q-mb-sm" />
        <q-list bordered separator v-if="historyList.length">
          <q-item v-for="h in historyList" :key="h.filename" clickable @click="loadHistoryFile(h.filename)">
            <q-item-section>
              <q-item-label>{{ h.filename }}</q-item-label>
              <q-item-label caption>{{ h.modified }} · {{ (h.size / 1024).toFixed(1) }} KB</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-icon name="chevron_right" />
            </q-item-section>
          </q-item>
        </q-list>
        <q-banner v-else class="bg-grey-2">目前沒有歷史紀錄</q-banner>
      </q-tab-panel>
    </q-tab-panels>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
  MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DatasetComponent, MarkLineComponent])

const props = defineProps({
  apiBase: { type: String, default: '/api' },
})

// ─── Chart instance refs (keyed by scenario id) ────────────
const chartRefs = {}

// ─── State ──────────────────────────────────────────────────
const conn = ref({ sim: false, nomi: false })
const runsPerScenario = ref(6)
const isRunning = ref(false)
const progress = ref(0)
const progressText = ref('')
const mainTab = ref('live')

// Live results
const liveCategories = ref([])
const liveLog = ref([])

// Completed results (for charts)
const evalResults = ref(null)
const rescoredResults = ref(null)
const lenientMode = ref(false)
const rescoring = ref(false)

// The active results to display (original or rescored)
const activeResults = computed(() =>
  lenientMode.value && rescoredResults.value ? rescoredResults.value : evalResults.value
)

// History
const historyList = ref([])

// ─── Computed ───────────────────────────────────────────────
const hasResults = computed(() => !!activeResults.value)

const chartData = computed(() => {
  if (!activeResults.value) return []
  return (activeResults.value.categories || []).map(cat => ({
    id: cat.category_id,
    name: cat.category_name,
    color: cat.color || '#333',
    summary: cat.summary || {},
  }))
})

const scenarioCharts = computed(() => {
  if (!activeResults.value) return []
  const result = []
  for (const cat of activeResults.value.categories || []) {
    for (const sc of cat.scenarios || []) {
      if (sc.error) continue
      result.push({
        id: `${cat.category_id}_${sc.id}`,
        name: sc.name,
        catName: cat.category_name,
        catColor: cat.color || '#333',
        gt: sc.ground_truth || '',
        chart: buildScenarioChart(sc, cat.color || '#3498db'),
      })
    }
  }
  return result
})

// ─── Download chart as PNG (backend matplotlib) ────────────
async function downloadChart(sc) {
  // Find raw scenario (with .runs) from activeResults
  let rawSc = null
  for (const cat of activeResults.value?.categories || []) {
    const found = (cat.scenarios || []).find(s => `${cat.category_id}_${s.id}` === sc.id)
    if (found) { rawSc = found; break }
  }
  if (!rawSc || !rawSc.runs?.length) return

  try {
    const resp = await fetch(`${props.apiBase}/evaluation/chart/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: rawSc.id,
        runs: rawSc.runs,
      }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eval_${rawSc.id}.png`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Chart download failed:', err)
  }
}

// ─── Connectivity ───────────────────────────────────────────
async function checkConnectivity() {
  try {
    const r = await fetch(`${props.apiBase}/evaluation/connectivity`)
    const d = await r.json()
    conn.value = { sim: d.simulator?.connected, nomi: d.nomi_host?.connected }
  } catch {
    conn.value = { sim: false, nomi: false }
  }
}

// ─── Start Evaluation (SSE) ─────────────────────────────────
function startEvaluation() {
  isRunning.value = true
  progress.value = 0
  progressText.value = '正在啟動…'
  liveCategories.value = []
  liveLog.value = []
  evalResults.value = null
  mainTab.value = 'live'

  const params = new URLSearchParams({
    sim_port: '8001', nomi_port: '8000',
    use_judge: 'true',
    runs: String(runsPerScenario.value),
  })
  const es = new EventSource(`${props.apiBase}/evaluation/run?${params}`)

  let totalRuns = 1
  let doneRuns = 0

  es.addEventListener('eval_start', (e) => {
    const d = JSON.parse(e.data)
    totalRuns = d.total_runs || 1
    progressText.value = `評估開始：${d.total_categories} 大類、${d.total_scenarios} 場景、每場景 ${d.runs_per_scenario} 次 (共 ${totalRuns} 次推論)`
    addLog(`開始評估：${totalRuns} 次推論`)
  })

  es.addEventListener('category_start', (e) => {
    const d = JSON.parse(e.data)
    liveCategories.value.push({
      id: d.id, name: d.name, color: d.color,
      total: d.scenario_count, done: 0,
      scenarios: [],
    })
    addLog(`▶ 開始大類：${d.name}`)
  })

  es.addEventListener('scenario_start', (e) => {
    const d = JSON.parse(e.data)
    const cat = liveCategories.value.find(c => c.id === getCatIdForSc(d.cat_index))
    if (cat) {
      cat.scenarios.push({
        id: d.id, name: d.name, pending: true,
        runs: [],
        ground_truth: null,
        accuracy_no_env: null, accuracy_with_env: null,
        robustness_no_env: null, robustness_with_env: null,
        breakdown_no_env: null, breakdown_with_env: null,
      })
    }
    addLog(`  ◆ 場景：${d.name} (${d.runs} 次)`)
  })

  es.addEventListener('run_progress', (e) => {
    const d = JSON.parse(e.data)
    progressText.value = `${d.sc_id} — Run ${d.run} — ${d.desc}${d.file ? ' (' + d.file.slice(-25) + ')' : ''}`
  })

  es.addEventListener('run_done', (e) => {
    const d = JSON.parse(e.data)
    doneRuns++
    progress.value = doneRuns / totalRuns

    // Find the scenario in liveCategories and add run result
    for (const cat of liveCategories.value) {
      const sc = cat.scenarios.find(s => s.id === d.sc_id)
      if (sc) {
        sc.runs.push({
          score_a: d.score_a, score_b: d.score_b,
          correct_a: d.correct_a, correct_b: d.correct_b,
          partial_a: d.partial_a, partial_b: d.partial_b,
          label_a: d.label_a, label_b: d.label_b,
          gt: d.gt || '', variant_label: d.variant_label || '',
        })
        // Accumulate all unique GTs from runs
        if (d.gt) {
          const gts = new Set((sc.ground_truth || '').split(' / ').filter(Boolean))
          gts.add(d.gt)
          sc.ground_truth = [...gts].join(' / ')
        }
        break
      }
    }
  })

  es.addEventListener('scenario_done', (e) => {
    const d = JSON.parse(e.data)
    for (const cat of liveCategories.value) {
      const sc = cat.scenarios.find(s => s.id === d.id)
      if (sc) {
        sc.pending = false
        sc.accuracy_no_env = d.accuracy_no_env
        sc.accuracy_with_env = d.accuracy_with_env
        sc.accuracy_delta = d.accuracy_delta
        sc.robustness_no_env = d.robustness_no_env
        sc.robustness_with_env = d.robustness_with_env
        sc.breakdown_no_env = d.breakdown_no_env
        sc.breakdown_with_env = d.breakdown_with_env
        sc.ground_truth = sc.ground_truth || d.ground_truth
        cat.done++
        break
      }
    }
    const delta = d.accuracy_delta ?? (d.accuracy_with_env - d.accuracy_no_env)
    addLog(`  ✓ ${d.name}: A=${d.accuracy_no_env}% B=${d.accuracy_with_env}% Δ=${delta >= 0 ? '+' : ''}${delta}% 魯棒B:${d.robustness_with_env}%`)
  })

  es.addEventListener('category_done', (e) => {
    const d = JSON.parse(e.data)
    addLog(`✔ ${d.name} 完成: Δ=${d.summary?.delta}%`)
  })

  es.addEventListener('eval_complete', (e) => {
    const d = JSON.parse(e.data)
    evalResults.value = d
    rescoredResults.value = null
    lenientMode.value = false
    isRunning.value = false
    progress.value = 1
    progressText.value = '評估完成！切換至「圖表分析」查看結果'
    addLog('═══ 評估完成 ═══')
    es.close()
    nextTick(() => { mainTab.value = 'charts' })
  })

  es.addEventListener('eval_cancelled', () => {
    isRunning.value = false
    progressText.value = '已取消'
    addLog('⚠ 評估已取消')
    es.close()
  })

  es.onerror = () => {
    isRunning.value = false
    progressText.value = '連線中斷'
    addLog('✗ SSE 連線中斷')
    es.close()
  }
}

async function cancelEvaluation() {
  try {
    await fetch(`${props.apiBase}/evaluation/cancel`, { method: 'POST' })
  } catch { /* ignore */ }
}

// ─── Chart Builders ─────────────────────────────────────────

function buildScenarioChart(sc, _catColor) {
  const runs = sc.runs || []
  if (!runs.length) return {}

  // --- colour / style constants (light=Skeleton, dark=Skeleton+Env) ---
  const COL_A_BAR  = '#b0c4de'   // light steel blue (bar fill)
  const COL_A_LINE = '#6c9fc2'   // medium steel blue (line)
  const COL_B_BAR  = '#1d4e7f'   // deep navy (bar fill)
  const COL_B_LINE = '#1d4e7f'   // deep navy (line)

  // --- scale factors for on-screen display ---
  const fs  = 10    // base font size
  const fsS = 9     // small label font size
  const lw  = 0.5   // bar border width
  const lwA = 2.2   // line A width
  const lwB = 2.5   // line B width
  const lwM = 1.2   // markLine width
  const ssA = 6     // symbolSize A
  const ssB = 8     // symbolSize B
  const bw  = 36    // barMaxWidth
  const grid = { left: 55, right: 20, top: 45, bottom: 30 }
  const legendItem = { itemWidth: 18, itemHeight: 10 }

  const xLabels = runs.map((_, i) => `Trial ${i + 1}`)
  const barA = []
  const barB = []
  const lineA = []  // cumulative average A
  const lineB = []  // cumulative average B
  let cumA = 0, cumB = 0

  for (let i = 0; i < runs.length; i++) {
    const run = runs[i]
    const scoreA = (run.no_env?.score ?? 0) * 100
    const scoreB = (run.with_env?.score ?? 0) * 100
    barA.push(round1(scoreA))
    barB.push(round1(scoreB))
    cumA += scoreA
    cumB += scoreB
    lineA.push(round1(cumA / (i + 1)))
    lineB.push(round1(cumB / (i + 1)))
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const idx = params[0]?.dataIndex
        let tip = `<b>Trial ${idx + 1}</b><br/>`
        for (const p of params) {
          tip += `${p.marker} ${p.seriesName}: <b>${p.value}%</b><br/>`
        }
        return tip
      },
    },
    legend: {
      data: [
        'Skeleton Only', 'Skeleton + Env',
        'Skeleton Only (avg)', 'Skeleton + Env (avg)',
      ],
      top: 0,
      textStyle: { fontSize: fs },
      itemWidth: legendItem.itemWidth,
      itemHeight: legendItem.itemHeight,
    },
    grid,
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { fontSize: fs },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      name: 'Score (%)',
      nameTextStyle: { fontSize: fs },
      axisLabel: { formatter: '{value}%', fontSize: fs },
    },

    series: [
      // ── Bars (rendered first, behind lines) ──
      {
        name: 'Skeleton Only',
        type: 'bar',
        data: barA,
        barGap: '15%',
        barMaxWidth: bw,
        z: 2,
        itemStyle: {
          color: COL_A_BAR,
          borderRadius: [3, 3, 0, 0],
          borderColor: '#fff',
          borderWidth: lw,
        },
        label: {
          show: true, position: 'inside', formatter: p => p.value + '%',
          fontSize: fsS, color: '#555',
        },
      },
      {
        name: 'Skeleton + Env',
        type: 'bar',
        data: barB,
        barMaxWidth: bw,
        z: 2,
        itemStyle: {
          color: COL_B_BAR,
          borderRadius: [3, 3, 0, 0],
          borderColor: '#fff',
          borderWidth: lw,
        },
        label: {
          show: true, position: 'inside', formatter: p => p.value + '%',
          fontSize: fsS, color: '#fff',
        },
      },
      // ── Lines (rendered above bars via higher z) ──
      {
        name: 'Skeleton Only (avg)',
        type: 'line',
        data: lineA,
        smooth: 0.3,
        z: 10,
        symbol: 'circle',
        symbolSize: ssA,
        lineStyle: { color: COL_A_LINE, type: 'dashed', width: lwA },
        itemStyle: { color: COL_A_LINE, borderColor: '#fff', borderWidth: 1 },
      },
      {
        name: 'Skeleton + Env (avg)',
        type: 'line',
        data: lineB,
        smooth: 0.3,
        z: 10,
        symbol: 'diamond',
        symbolSize: ssB,
        lineStyle: { color: COL_B_LINE, type: 'solid', width: lwB },
        itemStyle: { color: COL_B_LINE, borderColor: '#fff', borderWidth: 1 },
        markLine: {
          silent: true,
          lineStyle: { color: '#c0392b', type: 'dotted', width: lwM },
          data: [{
            yAxis: 85,
            label: {
              formatter: '85% Target',
              position: 'insideEndTop',
              color: '#c0392b',
              fontSize: fsS,
            },
          }],
        },
      },
    ],
  }
}

// ─── Helpers (score colors) ─────────────────────────────────

function scoreColor(score) {
  if (score == null) return 'grey'
  if (score >= 1.0) return 'positive'
  if (score >= 0.5) return 'warning'
  return 'negative'
}

function scoreIcon(score) {
  if (score == null) return ''
  if (score >= 1.0) return '✓'
  if (score >= 0.5) return '△'
  return '✗'
}

function robustnessColor(v) {
  if (v == null) return 'text-grey'
  if (v >= 85) return 'text-positive'
  if (v >= 60) return 'text-warning'
  return 'text-negative'
}

function round1(v) { return Math.round(v * 10) / 10 }

function lighten(hex) {
  // Simple lightening: towards white by 50%
  const num = parseInt((hex || '#3498db').replace('#', ''), 16)
  const r = Math.min(255, ((num >> 16) & 0xff) + 100)
  const g = Math.min(255, ((num >>  8) & 0xff) + 100)
  const b = Math.min(255, ( num        & 0xff) + 100)
  return `rgb(${r},${g},${b})`
}

// ─── History ────────────────────────────────────────────────
async function loadHistory() {
  try {
    const r = await fetch(`${props.apiBase}/evaluation/results`)
    historyList.value = await r.json()
  } catch { historyList.value = [] }
}

async function loadHistoryFile(filename) {
  try {
    const r = await fetch(`${props.apiBase}/evaluation/results/${filename}`)
    const data = await r.json()
    evalResults.value = data
    rescoredResults.value = null
    lenientMode.value = false
    mainTab.value = 'charts'
    progressText.value = `已載入歷史紀錄：${filename}`
  } catch (e) {
    progressText.value = `載入失敗：${e.message}`
  }
}

// ─── Helpers ────────────────────────────────────────────────
function getCatIdForSc(catIndex) {
  return liveCategories.value[catIndex]?.id
}

function addLog(msg) {
  const t = new Date().toLocaleTimeString('zh-TW')
  liveLog.value.push({ time: t, msg, level: msg.includes('✗') ? 'error' : 'info' })
}

// ─── Lenient Rescore ───────────────────────────────────────────
async function onLenientToggle(val) {
  if (!val || !evalResults.value) return
  // Already rescored? skip
  if (rescoredResults.value) return
  rescoring.value = true
  try {
    const r = await fetch(`${props.apiBase}/evaluation/rescore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(evalResults.value),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    rescoredResults.value = await r.json()
  } catch (err) {
    console.error('Rescore failed:', err)
    lenientMode.value = false
  } finally {
    rescoring.value = false
  }
}

// ─── Init ───────────────────────────────────────────────────
onMounted(() => {
  checkConnectivity()
  loadHistory()
})
</script>

<style scoped>
.evaluation-panel {
  max-width: 1200px;
  margin: 0 auto;
}
</style>

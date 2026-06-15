<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const API = ''
const route = useRoute()
const router = useRouter()
const form = ref({
  software_name: '涉案车辆管理系统',
  description: '用于涉案车辆档案、案件关联、车辆布控预警和统计研判',
  software_type: '管理系统',
  industry_type: 'public_security',
  planner_mode: 'auto',
  codegen_mode: 'auto',
  document_template: 'standard',
  version: 'V1.0',
  applicant_name: '待填写',
  completion_date: new Date().toISOString().slice(0, 10),
  publication_status: '未发表'
})
const job = ref(null)
const preview = ref(null)
const submitting = ref(false)
const requestError = ref('')
const settingsOpen = ref(false)
const settingsSaving = ref(false)
const settingsMessage = ref('')
const settingsError = ref('')
const demoActionLoading = ref(false)
const logsOpen = ref(false)
const logService = ref('backend')
const logContent = ref('')
const revisionInstruction = ref('')
const revisionProposal = ref(null)
const revisionLoading = ref(false)
const revisionHistory = ref([])
const plannerSettings = ref({
  mode: 'auto',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model: '',
  timeout: 60,
  codegen_model: '',
  codegen_timeout: 90,
  clear_api_key: false,
  api_key_configured: false,
  api_key_hint: ''
})
let timer = null

const finished = computed(() => job.value?.status === 'success')

const STAGE_LABELS = {
  queued: '排队中…',
  building: '正在构建 JAR…',
  starting: '正在启动 Spring Boot…',
  running: '',
  stopped: '',
  failed: ''
}
function stageLabel(stage) {
  return STAGE_LABELS[stage] || (stage ? `阶段：${stage}` : '')
}

async function createJob() {
  submitting.value = true
  requestError.value = ''
  preview.value = null
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    }, 15000)
    if (!response.ok) throw new Error(await response.text())
    job.value = await response.json()
    submitting.value = false
    poll()
  } catch (error) {
    requestError.value = error.name === 'AbortError'
      ? '连接后端超时，请确认后端已在 127.0.0.1:8000 启动。'
      : `任务创建失败：${error.message}`
  } finally {
    submitting.value = false
  }
}

async function fetchWithTimeout(url, options = {}, timeout = 10000) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } finally {
    clearTimeout(timeoutId)
  }
}

async function poll() {
  clearInterval(timer)
  refresh()
  timer = setInterval(refresh, 1500)
}

async function refresh() {
  if (!job.value) return
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}`)
    if (!response.ok) throw new Error(await response.text())
    job.value = await response.json()
    requestError.value = ''
    if (job.value.status === 'draft_planning') {
      clearInterval(timer)
      router.push(`/planning-review/${job.value.job_id}`)
      return
    }
    if (['awaiting_demo_review', 'revision_review'].includes(job.value.status)) {
      clearInterval(timer)
      loadRevisionHistory()
      return
    }
    if (['success', 'failed'].includes(job.value.status)) {
      clearInterval(timer)
      if (job.value.status === 'success') {
        preview.value = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/preview`).then(r => r.json())
      }
    }
  } catch (error) {
    requestError.value = '无法获取任务进度，请检查后端服务是否仍在运行。'
  }
}

async function loadRevisionHistory() {
  if (!job.value) return
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/revisions`)
    if (response.ok) revisionHistory.value = (await response.json()).items || []
  } catch {
    revisionHistory.value = []
  }
}

function returnHome() {
  clearInterval(timer)
  job.value = null
  preview.value = null
  revisionProposal.value = null
  revisionInstruction.value = ''
  revisionHistory.value = []
  requestError.value = ''
  router.replace('/')
}

async function approveReview() {
  demoActionLoading.value = true
  requestError.value = ''
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/review/approve`, {
      method: 'POST'
    }, 30000)
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
    job.value = await response.json()
    poll()
  } catch (error) {
    requestError.value = `继续生成失败：${error.message}`
  } finally {
    demoActionLoading.value = false
  }
}

async function proposeRevision() {
  if (!revisionInstruction.value.trim()) {
    requestError.value = '请先说明需要修改的内容。'
    return
  }
  revisionLoading.value = true
  requestError.value = ''
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/revision/propose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction: revisionInstruction.value })
    }, 90000)
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
    revisionProposal.value = await response.json()
    job.value.status = 'revision_review'
  } catch (error) {
    requestError.value = `生成修改建议失败：${error.message}`
  } finally {
    revisionLoading.value = false
  }
}

async function confirmRevision() {
  revisionLoading.value = true
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/revision/confirm`, {
      method: 'POST'
    }, 30000)
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
    job.value = await response.json()
    revisionProposal.value = null
    revisionInstruction.value = ''
    poll()
  } catch (error) {
    requestError.value = `确认修改失败：${error.message}`
  } finally {
    revisionLoading.value = false
  }
}

async function cancelRevision() {
  const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/revision/cancel`, {
    method: 'POST'
  })
  if (!response.ok) {
    requestError.value = `取消修改失败：${await response.text()}`
    return
  }
  job.value = await response.json()
  revisionProposal.value = null
}

async function restoreRevision(version) {
  if (!window.confirm(`确认回退到规划 v${version} 并重新生成项目吗？`)) return
  revisionLoading.value = true
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/revisions/${version}/restore`, {
      method: 'POST'
    }, 30000)
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
    job.value = await response.json()
    poll()
  } catch (error) {
    requestError.value = `回退规划失败：${error.message}`
  } finally {
    revisionLoading.value = false
  }
}

async function startDemo() {
  if (!job.value) return
  demoActionLoading.value = true
  requestError.value = ''
  try {
    await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/demo/start`, {
      method: 'POST'
    }, 30000).then(async response => {
      if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
      return response.json()
    })
    job.value.run_status = 'starting'
    job.value.demo_stage = 'queued'
    job.value.demo_error = ''
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 2000))
      const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/demo`)
      const runtime = await response.json()
      job.value.demo_stage = runtime.stage || job.value.demo_stage
      job.value.demo_error = runtime.error || ''
      if (runtime.status === 'running') {
        job.value.run_status = runtime.status
        job.value.demo_url = runtime.demo_url
        job.value.swagger_url = runtime.swagger_url
        job.value.demo_stage = 'running'
        return
      }
      if (runtime.status === 'failed') {
        job.value.run_status = 'failed'
        throw new Error(runtime.error || 'Demo 启动失败')
      }
    }
    job.value.run_status = 'failed'
    throw new Error('Demo 启动超时')
  } catch (error) {
    requestError.value = `启动 Demo 失败：${error.message}`
  } finally {
    demoActionLoading.value = false
  }
}

async function stopDemo() {
  if (!job.value) return
  demoActionLoading.value = true
  try {
    await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/demo/stop`, {
      method: 'POST'
    }, 30000)
    job.value.run_status = 'stopped'
  } finally {
    demoActionLoading.value = false
  }
}

async function showLogs(service) {
  if (!job.value) return
  logService.value = service
  logsOpen.value = true
  try {
    const response = await fetchWithTimeout(`${API}/api/jobs/${job.value.job_id}/logs/${service}`)
    if (!response.ok) throw new Error(await response.text())
    logContent.value = (await response.json()).content || '暂无日志'
  } catch (error) {
    logContent.value = `读取日志失败：${error.message}`
  }
}

async function loadPlannerSettings() {
  try {
    const response = await fetchWithTimeout(`${API}/api/settings/planner`)
    if (!response.ok) throw new Error(await response.text())
    const data = await response.json()
    plannerSettings.value = {
      ...plannerSettings.value,
      ...data,
      api_key: '',
      clear_api_key: false
    }
    form.value.planner_mode = data.mode || 'auto'
  } catch (error) {
    settingsError.value = `读取模型配置失败：${error.message}`
  }
}

async function savePlannerSettings() {
  settingsSaving.value = true
  settingsMessage.value = ''
  settingsError.value = ''
  try {
    const response = await fetchWithTimeout(`${API}/api/settings/planner`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(plannerSettings.value)
    })
    if (!response.ok) throw new Error(await response.text())
    const data = await response.json()
    plannerSettings.value = {
      ...plannerSettings.value,
      ...data,
      api_key: '',
      clear_api_key: false
    }
    form.value.planner_mode = data.mode
    settingsMessage.value = '模型配置已保存到本机 backend\\.env。'
  } catch (error) {
    settingsError.value = `保存失败：${error.message}`
  } finally {
    settingsSaving.value = false
  }
}

onMounted(async () => {
  await loadPlannerSettings()
  if (route.query.jobId) {
    job.value = { job_id: String(route.query.jobId) }
    poll()
  }
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="page">
    <header>
      <div class="logo">AI</div>
      <div><h1>AI软著工厂</h1><p>模板驱动的软件著作权材料生成工具</p></div>
      <div class="header-actions"><span>Planning Review · V1.0</span><button v-if="route.query.jobId" @click="returnHome">返回首页</button><button @click="router.push('/history')">历史任务</button></div>
    </header>

    <main>
      <section class="intro">
        <div><b>从软件名称到完整材料包</b><p>自动生成可运行项目、界面截图、源码材料、设计说明书和用户手册。</p></div>
        <div class="intro-actions"><ol><li>软件规划</li><li>项目生成</li><li>启动 Demo</li><li>自动截图</li><li>文档打包</li></ol><button @click="settingsOpen = !settingsOpen">模型设置</button></div>
      </section>

      <section v-if="settingsOpen" class="card settings-card">
        <div class="card-title"><i>AI</i><div><h2>Planner 模型认证</h2><p>配置保存在本机，不会写入生成材料</p></div></div>
        <div class="settings-grid">
          <div><label>默认模式</label><select v-model="plannerSettings.mode"><option value="auto">自动回退</option><option value="llm">仅 LLM</option><option value="template">固定模板</option></select></div>
          <div><label>请求超时（秒）</label><input v-model.number="plannerSettings.timeout" type="number" min="5" max="300"></div>
          <div class="wide"><label>API Base URL</label><input v-model="plannerSettings.base_url" placeholder="https://api.openai.com/v1"></div>
          <div><label>模型名称</label><input v-model="plannerSettings.model" placeholder="填写接口实际支持的模型名"></div>
          <div><label>API Key <span v-if="plannerSettings.api_key_configured">已配置 {{plannerSettings.api_key_hint}}</span></label><input v-model="plannerSettings.api_key" type="password" placeholder="留空则保留原密钥"></div>
          <div><label>代码增强模型</label><input v-model="plannerSettings.codegen_model" placeholder="留空则复用 Planner 模型"></div>
          <div><label>代码增强超时（秒）</label><input v-model.number="plannerSettings.codegen_timeout" type="number" min="10" max="600"></div>
        </div>
        <label class="clear-key"><input v-model="plannerSettings.clear_api_key" type="checkbox"> 清除已保存的 API Key</label>
        <div class="settings-actions"><button @click="settingsOpen=false">收起</button><button class="primary-setting" :disabled="settingsSaving" @click="savePlannerSettings">{{settingsSaving ? '保存中...' : '保存模型配置'}}</button></div>
        <div class="success" v-if="settingsMessage">{{settingsMessage}}</div>
        <div class="error" v-if="settingsError">{{settingsError}}</div>
      </section>

      <div class="grid">
        <section class="card form-card">
          <div class="card-title"><i>01</i><div><h2>创建生成任务</h2><p>填写软件基本信息</p></div></div>
          <label>软件名称</label>
          <input v-model="form.software_name" placeholder="例如：智慧停车管理系统">
          <label>软件描述</label>
          <textarea v-model="form.description" rows="5"></textarea>
          <label>软件类型</label>
          <select v-model="form.software_type"><option>管理系统</option><option>数据平台</option><option>工具软件</option></select>
          <label>行业类型</label>
          <select v-model="form.industry_type">
            <option value="public_security">公安</option>
            <option value="justice">政法</option>
            <option value="industry">工业</option>
            <option value="education">教育</option>
          </select>
          <label>规划模式</label>
          <select v-model="form.planner_mode">
            <option value="auto">自动（优先 LLM，失败回退模板）</option>
            <option value="llm">仅 LLM（失败则终止）</option>
            <option value="template">固定模板</option>
          </select>
          <label>代码生成模式</label>
          <select v-model="form.codegen_mode">
            <option value="auto">AI 增强（失败自动回滚模板）</option>
            <option value="llm">强制 AI 增强（失败则终止）</option>
            <option value="template">仅固定模板</option>
          </select>
          <label>文档模板</label>
          <select v-model="form.document_template">
            <option value="standard">标准版</option>
            <option value="formal">正式版（宽松行距）</option>
            <option value="compact">紧凑版</option>
          </select>
          <label>软件版本</label>
          <input v-model="form.version" placeholder="V1.0">
          <label>著作权人</label>
          <input v-model="form.applicant_name" placeholder="公司或个人名称">
          <label>开发完成日期</label>
          <input v-model="form.completion_date" type="date">
          <label>发表状态</label>
          <select v-model="form.publication_status"><option>未发表</option><option>已发表</option></select>
          <button class="submit" :disabled="submitting || job?.status === 'generating'" @click="createJob">
            {{ submitting ? '正在创建...' : '生成软件规划' }}
          </button>
          <div class="error" v-if="requestError">{{requestError}}</div>
        </section>

        <section class="card progress-card">
          <div class="card-title"><i>02</i><div><h2>生成进度</h2><p>{{ job ? job.current_step : '等待创建任务' }}</p></div><strong v-if="job">{{job.progress}}%</strong></div>
          <div class="planner-info" v-if="job?.planner_mode">
            Planner：{{job.planner_mode === 'llm' ? `LLM · ${job.planner_model || '处理中'}` : job.planner_mode}}
            <span v-if="job.planner_fallback_reason">（已回退模板）</span>
          </div>
          <div class="planner-info" v-if="job?.codegen_mode">
            Code Enhancer：{{job.codegen_actual_mode || job.codegen_mode}}
            <span v-if="job.codegen_model"> · {{job.codegen_model}}</span>
            <span v-if="job.codegen_fallback_reason">（已回滚模板）</span>
          </div>
          <div class="compliance-summary" v-if="job?.compliance_score !== null && job?.compliance_score !== undefined">
            <b>{{job.compliance_score}} 分</b>
            <span>{{job.compliance_grade}}</span>
            <em>{{job.compliance_passed ? '合规检查通过' : '需要整改'}}</em>
          </div>
          <div class="progress"><span :style="{width: `${job?.progress || 0}%`}"></span></div>
          <div class="empty" v-if="!job">提交任务后，此处将实时展示流水线执行状态。</div>
          <div v-else class="steps">
            <div v-for="item in job.steps" :key="item.key" :class="item.status">
              <span>{{ item.status === 'completed' ? '✓' : item.status === 'running' ? '···' : item.status === 'failed' ? '!' : '' }}</span>
              <b>{{ item.name }}</b><em>{{ item.status }}</em>
            </div>
          </div>
          <div class="error" v-if="job?.error">{{job.error}}</div>
          <div class="demo-panel" v-if="job && ['starting', 'running', 'stopped', 'verified', 'structure_verified', 'failed'].includes(job.run_status)">
            <div class="demo-header">
              <div><b>在线 Demo</b>
                <span :class="['demo-status', job.run_status]">
                  {{ job.run_status === 'running' ? '运行中'
                     : job.run_status === 'failed' ? '启动失败'
                     : job.run_status === 'starting' ? '启动中…'
                     : '未运行' }}
                </span>
              </div>
              <div class="demo-stage" v-if="stageLabel(job.demo_stage)">{{ stageLabel(job.demo_stage) }}</div>
            </div>
            <div class="demo-error" v-if="job.run_status === 'failed' && job.demo_error">
              {{ (job.demo_error || '').slice(0, 200) }}
            </div>
            <div class="demo-actions">
              <a v-if="job.run_status === 'running'" :href="job.demo_url" target="_blank">查看 Demo</a>
              <a v-if="job.run_status === 'running'" :href="job.swagger_url" target="_blank">查看 Swagger</a>
              <button v-if="job.run_status === 'running'" :disabled="demoActionLoading" @click="stopDemo">关闭 Demo</button>
              <button v-else :disabled="demoActionLoading || !['success','awaiting_demo_review'].includes(job.status)" @click="startDemo">
                {{ demoActionLoading || job.run_status === 'starting' ? '启动中…' : (job.run_status === 'failed' ? '重新启动 Demo' : '启动 Demo') }}
              </button>
              <button :class="{'error-action': job.run_status === 'failed'}" @click="showLogs('backend')">后端日志</button>
              <button @click="showLogs('frontend')">前端日志</button>
            </div>
          </div>
          <div class="review-panel" v-if="job?.status === 'awaiting_demo_review'">
            <h3>Demo 人工审查</h3>
            <p>请先查看在线 Demo。确认符合预期后再生成截图和软著材料；如需调整，请用自然语言说明。</p>
            <div class="review-actions-inline">
              <button class="approve-review" :disabled="demoActionLoading" @click="approveReview">符合预期，继续生成软著材料</button>
            </div>
            <textarea v-model="revisionInstruction" rows="4" placeholder="例如：删除视频巡查，案件详情改成时间线，整体改为顶部导航。"></textarea>
            <button class="revision-button" :disabled="revisionLoading" @click="proposeRevision">{{revisionLoading ? '正在分析修改意见...' : '生成规划修改建议'}}</button>
          </div>
          <div class="review-panel proposal" v-if="job?.status === 'revision_review'">
            <h3>确认规划修改</h3>
            <p><b>修改摘要：</b>{{revisionProposal?.summary || job.revision_summary}}</p>
            <p v-if="revisionProposal"><b>处理模式：</b>{{revisionProposal.actual_mode === 'llm' ? `大模型 ${revisionProposal.model || ''}` : '本地规则回退'}}</p>
            <div class="review-actions-inline">
              <button @click="cancelRevision">取消修改</button>
              <button class="approve-review" :disabled="revisionLoading" @click="confirmRevision">{{revisionLoading ? '正在提交...' : '确认并重新生成项目'}}</button>
            </div>
          </div>
          <div class="revision-history" v-if="revisionHistory.length && ['awaiting_demo_review','revision_review'].includes(job?.status)">
            <b>规划版本</b>
            <div v-for="item in revisionHistory" :key="item.version">
              <span>v{{item.version}} · {{item.summary || '已确认规划'}}</span>
              <button :disabled="revisionLoading" @click="restoreRevision(item.version)">回退并重建</button>
            </div>
          </div>
          <a v-if="finished" class="download" :href="`${API}/api/jobs/${job.job_id}/download`">下载 copyright_package.zip</a>
          <button v-if="finished" class="history-link" @click="router.push('/history')">查看历史任务</button>
        </section>
      </div>

      <section v-if="preview?.screenshots?.length" class="card result">
        <div class="card-title"><i>03</i><div><h2>生成结果预览</h2><p>{{preview.documents.join(' · ')}}</p></div></div>
        <div class="shots"><img v-for="url in preview.screenshots" :key="url" :src="API + url"></div>
      </section>

      <section v-if="preview?.compliance" class="card compliance-card">
        <div class="card-title"><i>04</i><div><h2>软著合规模拟评分</h2><p>{{preview.compliance.grade}} · {{preview.compliance.score}}/{{preview.compliance.max_score}}</p></div></div>
        <div class="compliance-list">
          <div v-for="item in preview.compliance.items" :key="item.key" :class="{failed: !item.passed}">
            <span>{{item.passed ? '通过' : '整改'}}</span><b>{{item.name}}</b><em>{{item.points}}/{{item.max_points}}</em><p>{{item.detail}}</p>
          </div>
        </div>
      </section>

      <div v-if="logsOpen" class="log-mask" @click.self="logsOpen=false">
        <section class="log-dialog">
          <header><b>{{logService === 'backend' ? '后端日志' : '前端日志'}}</b><button @click="logsOpen=false">关闭</button></header>
          <pre>{{logContent}}</pre>
        </section>
      </div>
    </main>
  </div>
</template>

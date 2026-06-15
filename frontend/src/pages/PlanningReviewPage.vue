<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const API = ''
const route = useRoute()
const router = useRouter()
const jobId = String(route.params.jobId)
const planning = ref(null)
const serverEstimates = ref(null)
const loading = ref(true)
const saving = ref(false)
const regenerating = ref(false)
const confirming = ref(false)
const message = ref('')
const error = ref('')

const estimates = computed(() => {
  if (!planning.value) return serverEstimates.value
  const pageCount = 2 + planning.value.modules.reduce((sum, module) => sum + module.pages.length, 0)
  const tableCount = planning.value.database_tables.length
  return {
    page_count: pageCount,
    table_count: tableCount,
    code_lines: pageCount * 180 + tableCount * 80 + planning.value.modules.length * 250,
    screenshot_count: 3 + Math.min(planning.value.modules.length, 5)
  }
})

async function request(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || await response.text())
  return response.json()
}

async function loadPlanning() {
  loading.value = true
  error.value = ''
  try {
    const data = await request(`${API}/api/planning/${jobId}`)
    planning.value = data.planning
    serverEstimates.value = data.estimates
  } catch (exception) {
    error.value = `读取规划失败：${exception.message}`
  } finally {
    loading.value = false
  }
}

function moduleKey(name) {
  return `module_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

function addModule() {
  const key = moduleKey()
  planning.value.modules.push({
    key,
    name: '新功能模块',
    description: '请填写该模块的主要业务用途',
    pages: ['新功能列表'],
    fields: ['名称', '状态'],
    page_pattern: 'table_crud',
    detail_pattern: 'master_detail',
    edit_pattern: 'dialog'
  })
  planning.value.database_tables.push(key)
}

function removeModule(index) {
  if (planning.value.modules.length <= 3) {
    error.value = '规划至少保留 3 个功能模块。'
    return
  }
  planning.value.modules.splice(index, 1)
  planning.value.database_tables.splice(index, 1)
}

function addPage(module) {
  module.pages.push(`${module.name}新页面`)
}

function removePage(module, index) {
  if (module.pages.length <= 1) return
  module.pages.splice(index, 1)
}

function updateFields(module, event) {
  module.fields = event.target.value.split(/[，,]/).map(item => item.trim()).filter(Boolean)
}

async function savePlanning(showMessage = true) {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const data = await request(`${API}/api/planning/${jobId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(planning.value)
    })
    planning.value = data.planning
    serverEstimates.value = data.estimates
    if (showMessage) message.value = '软件规划已保存。'
    return true
  } catch (exception) {
    error.value = `保存失败：${exception.message}`
    return false
  } finally {
    saving.value = false
  }
}

async function regenerate() {
  regenerating.value = true
  message.value = ''
  error.value = ''
  try {
    await request(`${API}/api/planning/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId })
    })
    for (let attempt = 0; attempt < 120; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      const status = await request(`${API}/api/jobs/${jobId}`)
      if (status.status === 'draft_planning') {
        await loadPlanning()
        message.value = '已重新生成软件规划。'
        return
      }
      if (status.status === 'failed') throw new Error(status.error || '规划生成失败')
    }
    throw new Error('重新生成规划超时')
  } catch (exception) {
    error.value = `重新生成失败：${exception.message}`
  } finally {
    regenerating.value = false
  }
}

async function confirm() {
  confirming.value = true
  error.value = ''
  message.value = ''
  try {
    if (!(await savePlanning(false))) return
    await request(`${API}/api/jobs/${jobId}/confirm`, { method: 'POST' })
    router.push({ path: '/', query: { jobId } })
  } catch (exception) {
    error.value = `确认失败：${exception.message}`
  } finally {
    confirming.value = false
  }
}

onMounted(loadPlanning)
</script>

<template>
  <div class="review-page">
    <header class="review-header">
      <div><span>AI软著工厂</span><h1>软件规划书</h1><p>请确认功能范围。确认后，代码、截图和文档将严格依据本规划生成。</p></div>
      <button @click="router.push('/')">返回首页</button>
    </header>

    <main v-if="planning" class="review-main">
      <section class="review-card basic-section">
        <div class="section-heading"><b>01</b><div><h2>软件基本信息</h2><p>确认软件定位和目标用户</p></div></div>
        <div class="review-grid">
          <label>软件名称<input v-model="planning.software_name"></label>
          <label>软件类型<input v-model="planning.software_type"></label>
          <label class="wide">软件简介<textarea v-model="planning.description" rows="3"></textarea></label>
          <label class="wide">目标用户<input v-model="planning.target_users"></label>
        </div>
      </section>

      <section class="review-card">
        <div class="section-heading"><b>02</b><div><h2>界面架构</h2><p>选择应用壳层和首页信息组织方式</p></div></div>
        <div class="review-grid">
          <label>应用壳层
            <select v-model="planning.ui_plan.shell">
              <option value="sidebar_admin">侧边栏管理后台</option>
              <option value="top_workspace">顶部业务工作台</option>
              <option value="split_console">分栏业务控制台</option>
            </select>
          </label>
          <label>首页模式
            <select v-model="planning.ui_plan.home_pattern">
              <option value="metric_dashboard">指标总览</option>
              <option value="task_dashboard">任务工作台</option>
              <option value="analysis_dashboard">分析驾驶舱</option>
            </select>
          </label>
          <label>信息密度
            <select v-model="planning.ui_plan.density">
              <option value="compact">紧凑</option>
              <option value="standard">标准</option>
              <option value="comfortable">宽松</option>
            </select>
          </label>
        </div>
      </section>

      <section class="review-card">
        <div class="section-heading"><b>03</b><div><h2>功能模块</h2><p>新增、删除或调整模块及页面交互模式</p></div><button class="add-button" @click="addModule">+ 新增模块</button></div>
        <div class="module-grid">
          <article v-for="(module, index) in planning.modules" :key="module.key">
            <div class="module-number">{{String(index + 1).padStart(2, '0')}}</div>
            <button class="remove" @click="removeModule(index)">删除</button>
            <label>模块名称<input v-model="module.name"></label>
            <label>模块描述<textarea v-model="module.description" rows="3"></textarea></label>
            <label>字段（逗号分隔）
              <input :value="module.fields.join('，')" @change="updateFields(module, $event)">
            </label>
            <label>页面模式
              <select v-model="module.page_pattern">
                <option value="table_crud">表格 CRUD</option>
                <option value="master_detail">主从详情</option>
                <option value="tree_detail">树形详情</option>
                <option value="workflow_timeline">流程时间线</option>
                <option value="kanban">业务看板</option>
                <option value="dashboard">数据驾驶舱</option>
              </select>
            </label>
            <label>编辑方式
              <select v-model="module.edit_pattern">
                <option value="dialog">弹窗</option>
                <option value="drawer">抽屉</option>
                <option value="form_wizard">分步表单</option>
              </select>
            </label>
          </article>
        </div>
      </section>

      <section class="review-card">
        <div class="section-heading"><b>04</b><div><h2>页面结构</h2><p>维护各功能模块包含的页面</p></div></div>
        <div class="page-groups">
          <article v-for="module in planning.modules" :key="module.key">
            <h3>{{module.name}}</h3>
            <div v-for="(page, index) in module.pages" :key="index" class="page-row">
              <input v-model="module.pages[index]">
              <button :disabled="module.pages.length <= 1" @click="removePage(module, index)">删除</button>
            </div>
            <button class="text-button" @click="addPage(module)">+ 新增页面</button>
          </article>
        </div>
      </section>

      <section class="review-card">
        <div class="section-heading"><b>05</b><div><h2>数据库设计</h2><p>数据表与功能模块按顺序一一对应</p></div></div>
        <div class="table-list">
          <div v-for="(table, index) in planning.database_tables" :key="index">
            <span>TABLE</span><input v-model="planning.database_tables[index]">
            <button :disabled="planning.database_tables.length <= 1" @click="planning.database_tables.splice(index, 1)">删除</button>
          </div>
        </div>
      </section>

      <section class="review-card estimates-card">
        <div class="section-heading"><b>06</b><div><h2>项目预估</h2><p>根据当前规划实时计算</p></div></div>
        <div class="estimate-grid">
          <article><span>预计页面数</span><b>{{estimates.page_count}}</b></article>
          <article><span>预计数据库表数</span><b>{{estimates.table_count}}</b></article>
          <article><span>预计代码量</span><b>{{estimates.code_lines}}</b><small>行</small></article>
          <article><span>预计截图数</span><b>{{estimates.screenshot_count}}</b></article>
        </div>
      </section>

      <div class="review-message success" v-if="message">{{message}}</div>
      <div class="review-message error" v-if="error">{{error}}</div>

      <footer class="review-actions">
        <button :disabled="regenerating || saving || confirming" @click="regenerate">{{regenerating ? '重新生成中...' : '重新生成规划'}}</button>
        <button :disabled="saving || regenerating || confirming" @click="savePlanning(true)">{{saving ? '保存中...' : '保存规划'}}</button>
        <button class="confirm-button" :disabled="confirming || saving || regenerating" @click="confirm">{{confirming ? '正在确认...' : '确认并开始生成'}}</button>
      </footer>
    </main>

    <div v-else-if="loading" class="review-loading">正在加载软件规划...</div>
    <div v-else class="review-loading error">{{error}}</div>
  </div>
</template>

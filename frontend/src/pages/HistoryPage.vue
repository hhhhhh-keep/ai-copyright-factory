<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const API = ''
const router = useRouter()
const jobs = ref([])
const loading = ref(true)
const error = ref('')
const actionJob = ref('')

const statusText = {
  draft_planning: '待确认规划',
  confirmed: '规划已确认',
  generating: '生成中',
  regenerating_project: '重新生成中',
  awaiting_demo_review: '等待 Demo 审查',
  revision_review: '等待确认修改',
  generating_materials: '生成材料中',
  interrupted: '后台进程中断',
  success: '生成成功',
  failed: '生成失败'
}

async function request(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail || await response.text())
  }
  return response.json()
}

async function loadJobs() {
  loading.value = true
  error.value = ''
  try {
    const data = await request(`${API}/api/history/jobs?limit=200`)
    jobs.value = data.items
  } catch (exception) {
    error.value = `读取历史任务失败：${exception.message}`
  } finally {
    loading.value = false
  }
}

function openTask(job) {
  if (job.status === 'draft_planning' && job.has_planning) {
    router.push(`/planning-review/${job.job_id}`)
    return
  }
  router.push({ path: '/', query: { jobId: job.job_id } })
}

async function resumeJob(job) {
  if (!window.confirm(
    `任务已中断。点击确定将从 ${job.recovery_from_step || 'project'} 步骤重新开始执行，\n` +
    '可能重新执行项目生成、Maven 测试或材料生成。是否继续？'
  )) return
  actionJob.value = job.job_id
  error.value = ''
  try {
    await request(`${API}/api/jobs/${job.job_id}/resume`, { method: 'POST' })
    // 跳到首页轮询任务
    router.push({ path: '/', query: { jobId: job.job_id } })
  } catch (exception) {
    error.value = `恢复任务失败：${exception.message}`
  } finally {
    actionJob.value = ''
  }
}

async function startDemo(job) {
  actionJob.value = job.job_id
  error.value = ''
  try {
    await request(`${API}/api/jobs/${job.job_id}/demo/start`, {
      method: 'POST'
    })
    job.run_status = 'starting'
    job.demo_stage = 'queued'
    job.demo_error = ''
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 2000))
      const runtime = await request(`${API}/api/jobs/${job.job_id}/demo`)
      job.demo_stage = runtime.stage || job.demo_stage
      job.demo_error = runtime.error || ''
      if (runtime.status === 'running') {
        job.run_status = runtime.status
        job.demo_url = runtime.demo_url
        job.swagger_url = runtime.swagger_url
        job.demo_stage = 'running'
        return
      }
      if (runtime.status === 'failed') {
        job.run_status = 'failed'
        throw new Error(runtime.error || 'Demo 启动失败')
      }
    }
    job.run_status = 'failed'
    throw new Error('Demo 启动超时')
  } catch (exception) {
    error.value = `启动 Demo 失败：${exception.message}`
  } finally {
    actionJob.value = ''
  }
}

async function deleteJob(job) {
  const confirmed = window.confirm(
    `确认删除“${job.software_name}”吗？\n任务编号：${job.job_id}\n源码、日志、截图、文档和材料包将同时删除，且无法恢复。`
  )
  if (!confirmed) return
  actionJob.value = job.job_id
  error.value = ''
  try {
    await request(`${API}/api/jobs/${job.job_id}`, { method: 'DELETE' })
    jobs.value = jobs.value.filter(item => item.job_id !== job.job_id)
  } catch (exception) {
    error.value = `删除任务失败：${exception.message}`
  } finally {
    actionJob.value = ''
  }
}

onMounted(loadJobs)
</script>

<template>
  <div class="history-page">
    <header class="history-header">
      <div><span>AI软著工厂</span><h1>历史任务</h1><p>查看规划、生成进度、在线 Demo 和软著材料包。</p></div>
      <button @click="router.push('/')">返回首页</button>
    </header>
    <main>
      <div class="history-toolbar">
        <b>共 {{jobs.length}} 个任务</b>
        <button @click="loadJobs">刷新</button>
      </div>
      <div v-if="error" class="error">{{error}}</div>
      <div v-if="loading" class="history-empty">正在加载历史任务...</div>
      <div v-else-if="!jobs.length" class="history-empty">暂无历史任务。</div>
      <div v-else class="history-list">
        <article v-for="job in jobs" :key="job.job_id">
          <div class="history-main">
            <div class="history-title"><h2>{{job.software_name}}</h2><span :class="job.status">{{statusText[job.status] || job.status}}</span></div>
            <p>{{job.current_step}}</p>
            <small>{{job.job_id}} · {{job.created_at}}</small>
          </div>
          <div class="history-score">
            <b>{{job.progress}}%</b>
            <span v-if="job.compliance_score !== null">{{job.compliance_score}} 分</span>
          </div>
          <div class="history-actions">
            <button @click="openTask(job)">查看任务</button>
            <button
              v-if="job.status === 'interrupted'"
              :disabled="actionJob === job.job_id"
              @click="resumeJob(job)"
            >{{actionJob === job.job_id ? '恢复中…' : '恢复任务'}}</button>
            <a v-if="job.run_status === 'running'" :href="job.demo_url" target="_blank">查看 Demo</a>
            <span v-else-if="job.run_status === 'failed'" class="history-status-failed">启动失败</span>
            <button
              v-else-if="job.status === 'success'"
              :disabled="actionJob === job.job_id"
              @click="startDemo(job)"
            >{{actionJob === job.job_id ? '启动中…' : (job.run_status === 'failed' ? '重新启动 Demo' : '启动 Demo')}}</button>
            <a v-if="job.run_status === 'running'" :href="job.swagger_url" target="_blank">Swagger</a>
            <a v-if="job.has_package" :href="`${API}/api/jobs/${job.job_id}/download`">下载材料</a>
            <button class="danger" :disabled="actionJob === job.job_id" @click="deleteJob(job)">删除</button>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<template>
  <div class="page">
    <div v-if="ui.message.text" :key="ui.message.id" :class="['toast', ui.message.type]">{{ ui.message.text }}</div>

    <header class="hero">
      <div>
        <h1>大文件上传管理系统</h1>
        <p>分片上传、断点续传、鉴权、配额、限速与历史记录</p>
      </div>
      <button v-if="auth.token" class="ghost" @click="logout">退出登录</button>
    </header>

    <section v-if="!auth.token" class="panel auth-panel">
      <div class="panel-head">
        <h2>登录 / 注册</h2>
      </div>
      <div class="auth-grid">
        <input v-model.trim="auth.form.username" placeholder="用户名（>=3位）" />
        <input v-model="auth.form.password" type="password" placeholder="密码（>=6位）" />
        <button @click="login">登录</button>
        <button class="ghost" @click="register">注册</button>
      </div>
      <p v-if="auth.error" class="error">{{ auth.error }}</p>
    </section>

    <template v-else>
      <nav class="tabs">
        <button :class="['tab', { active: activeTab === 'upload' }]" @click="activeTab = 'upload'">上传中心</button>
        <button :class="['tab', { active: activeTab === 'files' }]" @click="activeTab = 'files'">文件管理</button>
        <button :class="['tab', { active: activeTab === 'history' }]" @click="openHistoryTab">上传记录</button>
        <button :class="['tab', { active: activeTab === 'quota' }]" @click="activeTab = 'quota'">配额信息</button>
      </nav>

      <section v-show="activeTab === 'upload'" class="panel">
        <div class="panel-head">
          <h2>上传中心</h2>
          <label class="pick-btn">
            选择文件
            <input type="file" multiple @change="onPickFiles" />
          </label>
        </div>
        <p class="tip">前端分片后并发上传，自动断点续传。关键步骤日志支持滚动查看。</p>

        <div v-if="tasks.length === 0" class="empty">暂无上传任务</div>
        <div v-for="task in tasks" :key="task.localId" class="task-card">
          <div class="task-header">
            <div>
              <strong>{{ task.name }}</strong>
              <span>{{ formatBytes(task.size) }}</span>
            </div>
            <span :class="['status', task.status]">{{ statusText(task.status) }}</span>
          </div>

          <div class="progress-wrap">
            <div class="progress" :style="{ width: `${task.progress}%` }"></div>
          </div>

          <div class="meta-grid">
            <span>进度：{{ task.progress.toFixed(2) }}%</span>
            <span>分片：{{ task.uploadedCount }}/{{ task.totalChunks || '-' }}</span>
            <span>速度：{{ formatBytes(task.speed) }}/s</span>
            <span>剩余：{{ formatTime(task.etaSec) }}</span>
          </div>

          <p class="step-tip">{{ task.stepMessage }}</p>
          <div v-if="task.logs.length" class="log-list">
            <div v-for="(line, idx) in task.logs" :key="`${task.localId}-log-${idx}`">{{ line }}</div>
          </div>

          <div class="actions">
            <button v-if="task.status === 'pending' || task.status === 'error'" @click="startTask(task)">开始</button>
            <button v-if="task.status === 'paused'" @click="resumeTask(task)">继续</button>
            <button v-if="task.status === 'uploading' || task.status === 'hashing'" class="warn" @click="pauseTask(task)">暂停</button>
            <button class="ghost" @click="removeTask(task.localId)">移除</button>
          </div>

          <p v-if="task.error" class="error">{{ task.error }}</p>
        </div>
      </section>

      <section v-show="activeTab === 'files'" class="panel">
        <div class="panel-head">
          <h2>文件管理</h2>
          <button class="ghost" @click="refreshFiles">刷新列表</button>
        </div>
        <div v-if="files.length === 0" class="empty">暂无已上传文件</div>
        <table v-else>
          <thead>
            <tr>
              <th>文件名</th>
              <th>大小</th>
              <th>哈希</th>
              <th>上传时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in files" :key="file.file_id">
              <td>{{ file.file_name }}</td>
              <td>{{ formatBytes(file.file_size) }}</td>
              <td class="hash">{{ file.file_hash }}</td>
              <td>{{ formatDate(file.created_at) }}</td>
              <td>
                <button class="link" @click="downloadFile(file)">下载</button>
                <button class="link danger" @click="askDelete(file.file_id)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-show="activeTab === 'history'" class="panel">
        <div class="panel-head">
          <h2>上传记录</h2>
          <button class="ghost" :disabled="history.loading" @click="refreshHistory(true)">
            {{ history.loading ? '刷新中...' : '刷新记录' }}
          </button>
        </div>

        <div v-if="history.items.length === 0" class="empty">暂无上传记录</div>
        <table v-else>
          <thead>
            <tr>
              <th>时间</th>
              <th>文件名</th>
              <th>大小</th>
              <th>状态</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history.items" :key="item.record_id">
              <td>{{ formatDate(item.created_at) }}</td>
              <td>{{ item.file_name }}</td>
              <td>{{ formatBytes(item.file_size) }}</td>
              <td><span :class="['badge', item.status]">{{ item.status }}</span></td>
              <td>{{ item.message }}</td>
            </tr>
          </tbody>
        </table>

        <div class="pager">
          <button class="ghost" :disabled="history.page <= 1 || history.loading" @click="goHistoryPage(history.page - 1)">上一页</button>
          <span>第 {{ history.page }} / {{ totalHistoryPages }} 页，共 {{ history.total }} 条</span>
          <button class="ghost" :disabled="history.page >= totalHistoryPages || history.loading" @click="goHistoryPage(history.page + 1)">下一页</button>
        </div>
      </section>

      <section v-show="activeTab === 'quota'" class="panel">
        <div class="panel-head">
          <h2>配额信息</h2>
          <button class="ghost" :disabled="quotaLoading" @click="refreshQuota(true)">
            {{ quotaLoading ? '刷新中...' : '刷新配额' }}
          </button>
        </div>
        <div class="meta-grid">
          <span>用户：{{ auth.user?.username }}</span>
          <span>限速：{{ formatBytes(auth.quota?.upload_rate_bytes_sec || 0) }}/s</span>
          <span>总配额：{{ formatBytes(auth.quota?.storage_quota_bytes || 0) }}</span>
          <span>已用文件：{{ formatBytes(auth.quota?.used_files_bytes || 0) }}</span>
          <span>上传中预占：{{ formatBytes(auth.quota?.used_uploading_bytes || 0) }}</span>
          <span>剩余：{{ formatBytes(auth.quota?.available_bytes || 0) }}</span>
        </div>
      </section>
    </template>

    <div v-if="ui.deleteConfirm.visible" class="modal-mask">
      <div class="modal-card">
        <p>确认删除该文件？删除后不可恢复。</p>
        <div class="modal-actions">
          <button class="ghost" @click="ui.deleteConfirm.visible = false">取消</button>
          <button class="warn" @click="confirmDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { createSHA256 } from 'hash-wasm'

const CHUNK_SIZE = 8 * 1024 * 1024
const CONCURRENCY = 3
const MAX_RETRY = 2
const MERGE_REPAIR_MAX_ROUNDS = 3
const TOKEN_KEY = 'upload_token'

const activeTab = ref('upload')
const quotaLoading = ref(false)
const files = ref([])
const tasks = ref([])
const history = reactive({
  items: [],
  total: 0,
  page: 1,
  pageSize: 10,
  loading: false
})
const totalHistoryPages = computed(() => Math.max(Math.ceil(history.total / history.pageSize), 1))

const auth = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: null,
  quota: null,
  error: '',
  form: {
    username: '',
    password: ''
  }
})
const ui = reactive({
  message: { text: '', type: 'info', timer: null, id: 0 },
  deleteConfirm: { visible: false, fileId: '' }
})

function makeTask(file) {
  return reactive({
    localId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    file,
    name: file.name,
    size: file.size,
    hash: '',
    uploadId: '',
    totalChunks: 0,
    uploadedSet: new Set(),
    uploadedCount: 0,
    progress: 0,
    status: 'pending',
    error: '',
    paused: false,
    speed: 0,
    etaSec: 0,
    stepMessage: '等待开始',
    logs: [],
    controllers: new Map(),
    lastUploadedBytes: 0,
    mergeTriggered: false
  })
}

function setTaskStep(task, message) {
  task.stepMessage = message
  const ts = new Date().toLocaleTimeString()
  task.logs.push(`[${ts}] ${message}`)
  if (task.logs.length > 300) task.logs.shift()
}

function showMessage(text, type = 'info') {
  if (ui.message.timer) clearTimeout(ui.message.timer)
  ui.message.id += 1
  ui.message.text = text
  ui.message.type = type
  ui.message.timer = setTimeout(() => {
    ui.message.text = ''
    ui.message.timer = null
  }, 2800)
}

function onPickFiles(event) {
  const selected = Array.from(event.target.files || [])
  selected.forEach((file) => tasks.value.unshift(makeTask(file)))
  event.target.value = ''
}

function authHeaders(extra = {}) {
  if (!auth.token) return extra
  return {
    ...extra,
    Authorization: `Bearer ${auth.token}`
  }
}

async function apiFetch(url, options = {}) {
  const headers = authHeaders(options.headers || {})
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    logout()
    throw new Error('登录已失效，请重新登录')
  }
  return res
}

async function register() {
  auth.error = ''
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(auth.form)
  })
  if (!res.ok) {
    auth.error = await errorText(res)
    return
  }
  await login()
}

async function login() {
  auth.error = ''
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(auth.form)
  })
  if (!res.ok) {
    auth.error = await errorText(res)
    return
  }

  const data = await res.json()
  auth.token = data.access_token
  auth.user = data.user
  localStorage.setItem(TOKEN_KEY, auth.token)
  await Promise.all([refreshQuota(false), refreshFiles(), refreshHistory(false)])
  showMessage('登录成功', 'success')
}

function logout() {
  auth.token = ''
  auth.user = null
  auth.quota = null
  auth.error = ''
  localStorage.removeItem(TOKEN_KEY)
  tasks.value = []
  files.value = []
  history.items = []
  history.total = 0
}

async function refreshFiles() {
  if (!auth.token) return
  const res = await apiFetch('/api/files')
  files.value = await res.json()
}

async function refreshQuota(showTip = false) {
  if (!auth.token) return
  quotaLoading.value = true
  try {
    const resMe = await apiFetch('/api/auth/me')
    auth.user = await resMe.json()
    const resQuota = await apiFetch('/api/auth/quota')
    auth.quota = await resQuota.json()
    if (showTip) showMessage('配额信息已更新', 'success')
  } catch (err) {
    if (showTip) showMessage(String(err), 'error')
    throw err
  } finally {
    quotaLoading.value = false
  }
}

async function refreshHistory(showTip = false) {
  if (!auth.token) return
  history.loading = true
  try {
    const res = await apiFetch(`/api/history?page=${history.page}&page_size=${history.pageSize}`)
    if (!res.ok) throw new Error(await errorText(res))
    const data = await res.json()
    history.items = data.items || []
    history.total = data.total || 0
    if (showTip) showMessage('上传记录已更新', 'success')
  } catch (err) {
    if (showTip) showMessage(String(err), 'error')
  } finally {
    history.loading = false
  }
}

function openHistoryTab() {
  activeTab.value = 'history'
  refreshHistory(false)
}

async function goHistoryPage(page) {
  history.page = Math.min(Math.max(page, 1), totalHistoryPages.value)
  await refreshHistory(false)
}

function removeTask(localId) {
  tasks.value = tasks.value.filter((t) => t.localId !== localId)
}

async function startTask(task) {
  if (task.status === 'uploading' || task.status === 'hashing') return
  task.paused = false
  task.error = ''

  try {
    if (!task.hash) {
      task.status = 'hashing'
      setTaskStep(task, '步骤 1/5：正在计算文件哈希（用于秒传和断点续传）')
      task.hash = await calculateFileHash(task.file)
      if (task.paused) return
    }

    setTaskStep(task, '步骤 2/5：正在初始化上传任务并检查已上传分片')
    const initRes = await apiFetch('/api/uploads/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: task.name,
        file_size: task.size,
        file_hash: task.hash,
        chunk_size: CHUNK_SIZE
      })
    })
    if (!initRes.ok) throw new Error(await errorText(initRes))
    const initData = await initRes.json()

    task.totalChunks = initData.total_chunks
    task.uploadedSet = new Set(initData.uploaded_chunks || [])
    task.uploadedCount = task.uploadedSet.size
    task.progress = (task.uploadedCount / Math.max(task.totalChunks, 1)) * 100

    if (initData.file_exists) {
      task.status = 'done'
      task.progress = 100
      setTaskStep(task, '文件已存在，秒传完成')
      await Promise.all([refreshFiles(), refreshQuota(false), refreshHistory(false)])
      showMessage(`${task.name} 秒传完成`, 'success')
      return
    }

    task.uploadId = initData.upload_id
    setTaskStep(task, '步骤 3/5：开始分片并发上传')
    await runUpload(task)
  } catch (err) {
    task.status = task.paused ? 'paused' : 'error'
    task.error = String(err)
    setTaskStep(task, `上传失败：${task.error}`)
  }
}

function pauseTask(task) {
  task.paused = true
  for (const controller of task.controllers.values()) {
    controller.abort()
  }
  task.controllers.clear()
  task.status = 'paused'
  setTaskStep(task, '上传已暂停')
}

async function resumeTask(task) {
  task.paused = false
  task.error = ''
  if (!task.uploadId) {
    await startTask(task)
    return
  }

  const res = await apiFetch(`/api/uploads/${task.uploadId}`)
  if (!res.ok) {
    await startTask(task)
    return
  }

  const data = await res.json()
  task.totalChunks = data.total_chunks
  task.uploadedSet = new Set(data.uploaded_chunks || [])
  task.uploadedCount = task.uploadedSet.size
  task.progress = (task.uploadedCount / Math.max(task.totalChunks, 1)) * 100
  setTaskStep(task, '已恢复任务，继续上传缺失分片')
  await runUpload(task)
}

async function runUpload(task) {
  task.status = 'uploading'
  task.mergeTriggered = false
  setTaskStep(task, '步骤 3/5：正在上传分片（支持失败重试）')

  const timer = setInterval(() => {
    const uploadedBytes = task.uploadedCount * CHUNK_SIZE
    const delta = Math.max(uploadedBytes - task.lastUploadedBytes, 0)
    task.speed = delta
    task.lastUploadedBytes = uploadedBytes

    const remainChunks = Math.max(task.totalChunks - task.uploadedCount, 0)
    task.etaSec = task.speed > 0 ? Math.ceil((remainChunks * CHUNK_SIZE) / task.speed) : 0
  }, 1000)

  try {
    const pending = []
    for (let i = 0; i < task.totalChunks; i += 1) {
      if (!task.uploadedSet.has(i)) pending.push(i)
    }

    let cursor = 0

    async function worker() {
      while (!task.paused) {
        if (cursor >= pending.length) return
        const chunkIndex = pending[cursor]
        cursor += 1

        await uploadChunkWithRetry(task, chunkIndex)
        task.uploadedSet.add(chunkIndex)
        task.uploadedCount = task.uploadedSet.size
        task.progress = (task.uploadedCount / Math.max(task.totalChunks, 1)) * 100
      }
    }

    await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()))

    if (task.paused) {
      task.status = 'paused'
      return
    }

    if (task.uploadedCount === task.totalChunks && !task.mergeTriggered) {
      task.mergeTriggered = true
      setTaskStep(task, '步骤 4/5：分片上传完成，准备服务端合并')
      await mergeTask(task)
    }
  } finally {
    clearInterval(timer)
    task.controllers.clear()
    task.speed = 0
    task.etaSec = 0
    task.lastUploadedBytes = 0
  }
}

async function uploadChunkWithRetry(task, chunkIndex) {
  for (let attempt = 0; attempt <= MAX_RETRY; attempt += 1) {
    try {
      await uploadChunk(task, chunkIndex)
      return
    } catch (err) {
      if (task.paused) throw err
      if (attempt >= MAX_RETRY) throw err
      await sleep(500 * (attempt + 1))
    }
  }
}

async function uploadChunk(task, chunkIndex) {
  const start = chunkIndex * CHUNK_SIZE
  const end = Math.min(start + CHUNK_SIZE, task.size)
  const blob = task.file.slice(start, end)

  const formData = new FormData()
  formData.append('upload_id', task.uploadId)
  formData.append('chunk_index', String(chunkIndex))
  formData.append('chunk', blob, `${task.name}.part${chunkIndex}`)

  const controller = new AbortController()
  task.controllers.set(chunkIndex, controller)

  const res = await fetch('/api/uploads/chunk', {
    method: 'POST',
    body: formData,
    signal: controller.signal,
    headers: authHeaders()
  })

  task.controllers.delete(chunkIndex)
  if (res.status === 401) {
    logout()
    throw new Error('登录已失效，请重新登录')
  }
  if (!res.ok) {
    throw new Error(`chunk ${chunkIndex} 上传失败: ${await errorText(res)}`)
  }
}

async function mergeTask(task) {
  for (let round = 0; round < MERGE_REPAIR_MAX_ROUNDS; round += 1) {
    setTaskStep(task, `步骤 5/5：服务端合并校验中（第 ${round + 1} 次）`)
    const res = await apiFetch('/api/uploads/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: task.uploadId })
    })

    if (res.ok) {
      task.status = 'done'
      task.progress = 100
      setTaskStep(task, '上传完成，文件已落盘并通过校验')
      await Promise.all([refreshFiles(), refreshQuota(false), refreshHistory(false)])
      showMessage(`${task.name} 上传完成`, 'success')
      return
    }

    const detail = await errorDetail(res)
    const missingChunks = detail?.missing_chunks
    if (!Array.isArray(missingChunks) || missingChunks.length === 0 || round === MERGE_REPAIR_MAX_ROUNDS - 1) {
      task.status = 'error'
      task.error = detail?.detail || JSON.stringify(detail)
      setTaskStep(task, `合并失败：${task.error}`)
      return
    }

    task.status = 'uploading'
    task.error = `检测到缺失分片，自动补传中（${missingChunks.length}片）`
    setTaskStep(task, `检测到缺失分片 ${missingChunks.length} 个，正在自动补传`)
    for (const index of missingChunks) {
      await uploadChunkWithRetry(task, Number(index))
      task.uploadedSet.add(Number(index))
    }
    task.uploadedCount = task.uploadedSet.size
    task.progress = (task.uploadedCount / Math.max(task.totalChunks, 1)) * 100
  }
}

async function downloadFile(file) {
  const res = await apiFetch(`/api/files/${file.file_id}/download`)
  if (!res.ok) {
    showMessage(await errorText(res), 'error')
    return
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = file.file_name
  a.click()
  URL.revokeObjectURL(url)
  showMessage('下载已开始', 'success')
}

async function calculateFileHash(file) {
  const hasher = await createSHA256()
  const chunkCount = Math.ceil(file.size / CHUNK_SIZE)

  for (let i = 0; i < chunkCount; i += 1) {
    const start = i * CHUNK_SIZE
    const end = Math.min(start + CHUNK_SIZE, file.size)
    const chunk = await file.slice(start, end).arrayBuffer()
    hasher.update(new Uint8Array(chunk))
  }

  return hasher.digest('hex')
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let idx = 0
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024
    idx += 1
  }
  return `${value.toFixed(idx > 0 ? 2 : 0)} ${units[idx]}`
}

function formatTime(sec) {
  if (!sec || sec < 0) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function statusText(status) {
  const map = {
    pending: '待开始',
    hashing: '计算哈希',
    uploading: '上传中',
    paused: '已暂停',
    done: '已完成',
    error: '失败'
  }
  return map[status] || status
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function askDelete(fileId) {
  ui.deleteConfirm.visible = true
  ui.deleteConfirm.fileId = fileId
}

async function confirmDelete() {
  const fileId = ui.deleteConfirm.fileId
  ui.deleteConfirm.visible = false
  ui.deleteConfirm.fileId = ''
  if (!fileId) return

  const res = await apiFetch(`/api/files/${fileId}`, { method: 'DELETE' })
  if (res.ok) {
    await Promise.all([refreshFiles(), refreshQuota(false)])
    showMessage('文件已删除', 'success')
  } else {
    showMessage(await errorText(res), 'error')
  }
}

async function errorText(res) {
  const data = await errorDetail(res)
  if (data && typeof data === 'object') {
    return data.detail || JSON.stringify(data)
  }
  return String(data)
}

async function errorDetail(res) {
  try {
    return await res.json()
  } catch {
    return await res.text()
  }
}

onMounted(async () => {
  if (auth.token) {
    try {
      await Promise.all([refreshQuota(false), refreshFiles(), refreshHistory(false)])
    } catch {
      logout()
    }
  }
})
</script>

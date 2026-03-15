<template>
  <div class="page">
    <div v-if="ui.message.text" :key="ui.message.id" :class="['toast', ui.message.type]">{{ ui.message.text }}</div>

    <!-- Login Section -->
    <div v-if="!auth.token" class="login-container">
      <div class="login-card">
        <div class="login-header">
          <div class="login-logo">
            <svg viewBox="0 0 24 24" class="logo-icon" aria-hidden="true">
              <path d="M3 6.5a2.5 2.5 0 0 1 2.5-2.5h4.6l2 2.4H18a2.5 2.5 0 0 1 2.5 2.5v7.6A2.5 2.5 0 0 1 18 19H5.5A2.5 2.5 0 0 1 3 16.5V6.5Z" fill="currentColor"/>
            </svg>
          </div>
          <h1 class="login-title">大文件上传系统</h1>
          <p class="login-subtitle">安全、稳定、高效的文件管理平台</p>
        </div>
        
        <div v-if="auth.error" class="error-message">{{ auth.error }}</div>
        
        <div class="form-group">
          <label class="form-label">用户名</label>
          <input 
            v-model.trim="auth.form.username" 
            class="form-input" 
            placeholder="请输入用户名" 
            @keyup.enter="login"
          />
        </div>
        
        <div class="form-group">
          <label class="form-label">密码</label>
          <input 
            v-model="auth.form.password" 
            type="password" 
            class="form-input" 
            placeholder="请输入密码" 
            @keyup.enter="login"
          />
        </div>
        
        <button class="login-btn" @click="login">登 录</button>
        <button class="secondary-btn" @click="register">注 册 新 账 号</button>
      </div>
    </div>

    <!-- Main App -->
    <template v-else>
      <header class="hero">
        <div class="hero-left">
          <div class="hero-logo">
            <svg viewBox="0 0 24 24" class="logo-icon" aria-hidden="true">
              <path d="M3 6.5a2.5 2.5 0 0 1 2.5-2.5h4.6l2 2.4H18a2.5 2.5 0 0 1 2.5 2.5v7.6A2.5 2.5 0 0 1 18 19H5.5A2.5 2.5 0 0 1 3 16.5V6.5Z" fill="currentColor"/>
            </svg>
          </div>
          <div>
            <h1 class="hero-title">大文件上传系统</h1>
            <p class="hero-subtitle">欢迎回来，{{ auth.user?.username }}</p>
          </div>
        </div>
        <button class="logout-btn" @click="logout">退出登录</button>
      </header>

      <nav class="tabs">
        <button :class="['tab', { active: activeTab === 'upload' }]" @click="activeTab = 'upload'">📤 上传中心</button>
        <button :class="['tab', { active: activeTab === 'files' }]" @click="activeTab = 'files'">📁 文件管理</button>
        <button :class="['tab', { active: activeTab === 'history' }]" @click="openHistoryTab">📋 上传记录</button>
        <button :class="['tab', { active: activeTab === 'quota' }]" @click="activeTab = 'quota'">💾 配额信息</button>
        <button v-if="auth.user?.role === 'admin'" :class="['tab', { active: activeTab === 'admin' }]" @click="activeTab = 'admin'">⚙️ 管理员</button>
      </nav>

      <!-- Upload Panel -->
      <section v-show="activeTab === 'upload'" class="panel">
        <div class="panel-head">
          <h2 class="panel-title">上传中心</h2>
          <div class="pick-group">
            <label class="pick-btn">
              <span>➕ 选择文件</span>
              <input type="file" multiple @change="onPickFiles" />
            </label>
            <label class="pick-btn">
              <span>📂 选择文件夹</span>
              <input type="file" multiple webkitdirectory @change="onPickFolder" />
            </label>
          </div>
        </div>
        <p class="tip">支持大文件分片上传、断点续传、多线程并发，智能哈希校验确保文件完整性。支持选择文件夹并保留相对路径。</p>

        <div v-if="tasks.length === 0" class="empty">
          <div class="empty-icon">📭</div>
          <p>暂无上传任务，点击上方按钮开始上传</p>
        </div>
        
        <div v-for="task in tasks" :key="task.localId" class="task-card">
          <div class="task-header">
            <div class="task-info">
              <strong>{{ task.displayName }}</strong>
              <span>{{ formatBytes(task.size) }}</span>
            </div>
            <span :class="['status', task.status]">{{ statusText(task.status) }}</span>
          </div>

          <div class="progress-wrap">
            <div class="progress" :style="{ width: `${task.progress}%` }"></div>
          </div>

          <div class="meta-grid">
            <span>📊 进度：{{ task.progress.toFixed(1) }}%</span>
            <span v-if="task.kind === 'folder'">📁 文件：{{ task.uploadedFiles }} / {{ task.files.length }}</span>
            <span v-else>📦 分片：{{ task.uploadedCount }} / {{ task.totalChunks || '-' }}</span>
            <span>⚡ 速度：{{ formatBytes(task.speed) }}/s</span>
            <span>⏱️ 剩余：{{ formatTime(task.etaSec) }}</span>
          </div>

          <p class="step-tip">{{ task.stepMessage }}</p>
          <div v-if="task.logs.length" class="log-list">
            <div v-for="(line, idx) in task.logs" :key="`${task.localId}-log-${idx}`">{{ line }}</div>
          </div>

          <div class="actions">
            <button v-if="task.status === 'pending' || task.status === 'error'" class="btn btn-primary" @click="startTask(task)">开始</button>
            <button v-if="task.status === 'paused'" class="btn btn-primary" @click="resumeTask(task)">▶️ 继续</button>
            <button v-if="task.status === 'uploading' || task.status === 'hashing'" class="btn btn-secondary" @click="pauseTask(task)">暂停</button>
            <button v-if="task.kind === 'folder' && task.status === 'error'" class="btn btn-secondary" @click="skipFolderError(task)">跳过当前文件继续</button>
            <button class="btn btn-secondary" @click="removeTask(task.localId)">移除</button>
          </div>

          <p v-if="task.error" class="task-error">{{ task.error }}</p>
        </div>
      </section>

      <!-- Files Panel -->
      <section v-show="activeTab === 'files'" class="panel panel-fixed">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">文件管理</h2>
            <div class="breadcrumb">
              <button class="link-btn" :disabled="fileNav.path.length === 0" @click="goRoot">根目录</button>
              <span v-for="(part, idx) in fileNav.path" :key="`crumb-${idx}`">
                <span class="crumb-sep">/</span>
                <button class="link-btn" @click="goToCrumb(idx)">{{ part }}</button>
              </span>
            </div>
          </div>
          <div class="file-actions">
            <button class="btn btn-secondary" @click="refreshFiles">刷新列表</button>
            <button class="btn btn-primary" :disabled="selectedCount === 0" @click="downloadSelectionZip">
              打包下载（已选 {{ selectedCount }}）
            </button>
            <button class="btn btn-secondary" :disabled="selectedCount === 0" @click="clearSelection">清空选择</button>
          </div>
        </div>

        <div class="panel-body">
          <div v-if="fileItems.length === 0" class="empty">
            <div class="empty-icon">📂</div>
            <p>暂无已上传文件</p>
          </div>

          <table v-else class="file-table">
            <thead>
              <tr>
                <th class="col-check">
                  <input type="checkbox" :checked="allVisibleSelected" @change="toggleSelectVisible" />
                </th>
                <th>名称</th>
                <th>大小</th>
                <th>类型</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="fileNav.path.length > 0">
                <td class="col-check"></td>
                <td>
                  <div class="file-entry">
                    <span class="icon-wrap folder">
                      <svg viewBox="0 0 24 24" class="file-icon" aria-hidden="true">
                        <path d="M3 6.5a2.5 2.5 0 0 1 2.5-2.5h4.6l2 2.4H18a2.5 2.5 0 0 1 2.5 2.5v7.6A2.5 2.5 0 0 1 18 19H5.5A2.5 2.5 0 0 1 3 16.5V6.5Z" fill="currentColor"/>
                      </svg>
                    </span>
                    <button class="link-btn" @click="goUp">.. 返回上级</button>
                  </div>
                </td>
                <td>-</td>
                <td>目录</td>
                <td>-</td>
                <td></td>
              </tr>
              <tr v-for="item in pagedFileItems" :key="item.key">
                <td class="col-check">
                  <input type="checkbox" :checked="item.selected" @change="toggleSelection(item)" />
                </td>
                <td>
                  <div class="file-entry">
                    <span v-if="item.type === 'folder'" class="icon-wrap folder">
                      <svg viewBox="0 0 24 24" class="file-icon" aria-hidden="true">
                        <path d="M3 6.5a2.5 2.5 0 0 1 2.5-2.5h4.6l2 2.4H18a2.5 2.5 0 0 1 2.5 2.5v7.6A2.5 2.5 0 0 1 18 19H5.5A2.5 2.5 0 0 1 3 16.5V6.5Z" fill="currentColor"/>
                      </svg>
                    </span>
                    <span v-else class="icon-wrap file">
                      <svg viewBox="0 0 24 24" class="file-icon" aria-hidden="true">
                        <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" fill="currentColor"/>
                        <path d="M14 3v5h5" fill="currentColor"/>
                      </svg>
                    </span>
                    <button v-if="item.type === 'folder'" class="link-btn" @click="openFolder(item.name)">{{ item.name }}</button>
                    <span v-else>{{ item.displayName }}</span>
                  </div>
                </td>
                <td>{{ formatBytes(item.size) }}</td>
                <td>{{ item.type === 'folder' ? `目录（${item.totalFiles}）` : '文件' }}</td>
                <td>{{ formatDate(item.updatedAt) }}</td>
                <td>
                  <button v-if="item.type === 'folder'" class="btn btn-link" @click="openFolder(item.name)">进入</button>
                  <template v-else>
                    <button class="btn btn-link" @click="previewFile(item.file)">预览</button>
                    <button class="btn btn-link" @click="downloadFile(item.file)">下载</button>
                    <button class="btn btn-link" @click="showCopyCommands(item.file)">复制</button>
                    <button class="btn btn-link danger" @click="askDelete(item.file.file_id)">删除</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="panel-footer">
          <div class="pager fixed">
            <button class="btn btn-secondary" :disabled="fileNav.page <= 1" @click="goFilePage(fileNav.page - 1)">上一页</button>
            <span>第 {{ fileNav.page }} / {{ totalFilePages }} 页，共 {{ fileItems.length }} 条</span>
            <button class="btn btn-secondary" :disabled="fileNav.page >= totalFilePages" @click="goFilePage(fileNav.page + 1)">下一页</button>
            <div class="pager-jump">
              <input v-model="fileNav.jump" class="form-input jump-input" placeholder="跳页" @keyup.enter="jumpFilePage" />
              <button class="btn btn-secondary" @click="jumpFilePage">跳转</button>
            </div>
          </div>
        </div>
      </section>

      <!-- History Panel -->
      <section v-show="activeTab === 'history'" class="panel panel-fixed">
        <div class="panel-head">
          <h2 class="panel-title">上传记录</h2>
          <button class="btn btn-secondary" :disabled="history.loading" @click="refreshHistory(true)">
            {{ history.loading ? '刷新中...' : '🔄 刷新记录' }}
          </button>
        </div>

        <div class="panel-body">
          <div v-if="history.items.length === 0" class="empty">
            <div class="empty-icon">📜</div>
            <p>暂无上传记录</p>
          </div>
          
          <table v-else>
            <thead>
              <tr>
                <th>时间</th>
                <th>名称</th>
                <th>大小</th>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in history.items" :key="item.record_id">
                <td>{{ formatDate(item.created_at) }}</td>
                <td>
                  <div class="file-entry">
                    <span v-if="item.is_group" class="icon-wrap folder">
                      <svg viewBox="0 0 24 24" class="file-icon" aria-hidden="true">
                        <path d="M3 6.5a2.5 2.5 0 0 1 2.5-2.5h4.6l2 2.4H18a2.5 2.5 0 0 1 2.5 2.5v7.6A2.5 2.5 0 0 1 18 19H5.5A2.5 2.5 0 0 1 3 16.5V6.5Z" fill="currentColor"/>
                      </svg>
                    </span>
                    <span v-else class="icon-wrap file">
                      <svg viewBox="0 0 24 24" class="file-icon" aria-hidden="true">
                        <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" fill="currentColor"/>
                        <path d="M14 3v5h5" fill="currentColor"/>
                      </svg>
                    </span>
                    <span>{{ item.file_name }}</span>
                  </div>
                </td>
                <td>{{ formatBytes(item.file_size) }}</td>
                <td><span :class="['badge', item.status]">{{ item.status }}</span></td>
                <td>{{ item.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="panel-footer">
          <div class="pager fixed">
            <button class="btn btn-secondary" :disabled="history.page <= 1 || history.loading" @click="goHistoryPage(history.page - 1)">上一页</button>
            <span>第 {{ history.page }} / {{ totalHistoryPages }} 页，共 {{ history.total }} 条</span>
            <button class="btn btn-secondary" :disabled="history.page >= totalHistoryPages || history.loading" @click="goHistoryPage(history.page + 1)">下一页</button>
            <div class="pager-jump">
              <input v-model="history.jump" class="form-input jump-input" placeholder="跳页" @keyup.enter="jumpHistoryPage" />
              <button class="btn btn-secondary" :disabled="history.loading" @click="jumpHistoryPage">跳转</button>
            </div>
          </div>
        </div>
      </section>

      <!-- Quota Panel -->
      <section v-show="activeTab === 'quota'" class="panel">
        <div class="panel-head">
          <h2 class="panel-title">配额信息</h2>
          <button class="btn btn-secondary" :disabled="quotaLoading" @click="refreshQuota(true)">
            {{ quotaLoading ? '刷新中...' : '🔄 刷新配额' }}
          </button>
        </div>
        
        <div class="quota-grid">
          <div class="quota-card">
            <div class="quota-value">{{ formatBytes(auth.quota?.storage_quota_bytes || 0) }}</div>
            <div class="quota-label">总配额</div>
          </div>
          <div class="quota-card">
            <div class="quota-value">{{ formatBytes(auth.quota?.used_files_bytes || 0) }}</div>
            <div class="quota-label">已用空间</div>
          </div>
          <div class="quota-card">
            <div class="quota-value">{{ formatBytes(auth.quota?.available_bytes || 0) }}</div>
            <div class="quota-label">剩余空间</div>
          </div>
          <div class="quota-card">
            <div class="quota-value">{{ formatBytes(auth.quota?.used_uploading_bytes || 0) }}</div>
            <div class="quota-label">上传中</div>
          </div>
          <div class="quota-card">
            <div class="quota-value">{{ formatBytes(auth.quota?.upload_rate_bytes_sec || 0) }}/s</div>
            <div class="quota-label">上传速度</div>
          </div>
          <div class="quota-card">
            <div class="quota-value">{{ auth.user?.username }}</div>
            <div class="quota-label">当前用户</div>
          </div>
        </div>
      </section>

      <!-- Admin Panel -->
      <section v-show="activeTab === 'admin'" class="panel">
        <div class="panel-head">
          <h2 class="panel-title">用户管理</h2>
          <div style="display: flex; gap: 10px;">
            <select v-model="admin.roleFilter" @change="refreshUsers" class="form-input" style="width: auto; padding: 8px 16px;">
              <option value="">全部用户</option>
              <option value="pending">待审核</option>
              <option value="user">已通过</option>
              <option value="admin">管理员</option>
            </select>
            <button class="btn btn-secondary" @click="refreshUsers">🔄 刷新</button>
          </div>
        </div>

        <div class="stats-grid" style="margin-bottom: 24px;">
          <div class="stat-card">
            <div class="stat-value">{{ admin.users.length }}</div>
            <div class="stat-label">用户总数</div>
          </div>
          <div class="stat-card" style="border-color: rgba(245, 158, 11, 0.3);">
            <div class="stat-value" style="color: var(--warning);">{{ admin.users.filter(u => u.role === 'pending').length }}</div>
            <div class="stat-label">待审核</div>
          </div>
          <div class="stat-card" style="border-color: rgba(16, 185, 129, 0.3);">
            <div class="stat-value" style="color: var(--success);">{{ admin.users.filter(u => u.role === 'user').length }}</div>
            <div class="stat-label">已通过</div>
          </div>
          <div class="stat-card" style="border-color: rgba(var(--accent-rgb), 0.3);">
            <div class="stat-value" style="color: var(--accent-primary);">{{ admin.users.filter(u => u.role === 'admin').length }}</div>
            <div class="stat-label">管理员</div>
          </div>
        </div>
        
        <div v-if="admin.users.length === 0" class="empty">
          <div class="empty-icon">👥</div>
          <p>暂无用户</p>
        </div>
        
        <table v-else>
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in admin.users" :key="user.user_id">
              <td>
                <div style="display: flex; align-items: center; gap: 10px;">
                  <div class="avatar">{{ user.username.charAt(0).toUpperCase() }}</div>
                  {{ user.username }}
                </div>
              </td>
              <td><span :class="['badge', user.role]">{{ roleText(user.role) }}</span></td>
              <td>{{ formatDate(user.created_at) }}</td>
              <td>
                <button v-if="user.role === 'pending'" class="btn btn-primary" style="padding: 8px 16px; font-size: 13px;" @click="approveUser(user.user_id)">✅ 批准</button>
                <button class="btn btn-link danger" style="padding: 8px;" @click="deleteUser(user.user_id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <!-- Delete Modal -->
    <div v-if="ui.deleteConfirm.visible" class="modal-mask">
      <div class="modal-card">
        <p>确认删除该文件？删除后不可恢复。</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="ui.deleteConfirm.visible = false">取消</button>
          <button class="btn btn-danger" @click="confirmDelete">确认删除</button>
        </div>
      </div>
    </div>

    <div v-if="ui.preview.visible" class="modal-mask">
      <div class="modal-card preview-card">
        <div class="preview-head">
          <div>
            <div class="preview-title">预览：{{ ui.preview.name }}</div>
            <div class="preview-meta">{{ ui.preview.info }}</div>
          </div>
          <button class="btn btn-secondary" @click="closePreview">关闭</button>
        </div>
        <div class="preview-body">
          <div v-if="ui.preview.error" class="task-error">{{ ui.preview.error }}</div>
          <img v-else-if="ui.preview.type === 'image'" :src="ui.preview.url" class="preview-image" />
          <iframe v-else-if="ui.preview.type === 'pdf'" :src="ui.preview.url" class="preview-frame"></iframe>
          <audio v-else-if="ui.preview.type === 'audio'" :src="ui.preview.url" controls class="preview-media"></audio>
          <video v-else-if="ui.preview.type === 'video'" :src="ui.preview.url" controls class="preview-media"></video>
          <pre v-else class="preview-text">{{ ui.preview.text }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { createSHA256 } from 'hash-wasm'

const CHUNK_SIZE = 8 * 1024 * 1024
const CONCURRENCY = 3
const MAX_RETRY = 2
const MERGE_REPAIR_MAX_ROUNDS = 3
const TOKEN_KEY = 'upload_token'

const activeTab = ref('upload')
const quotaLoading = ref(false)
const fileList = ref([])
const selectedIds = ref(new Set())
const fileNav = reactive({
  path: [],
  page: 1,
  pageSize: 10,
  jump: ''
})
const tasks = ref([])
const history = reactive({
  items: [],
  total: 0,
  page: 1,
  pageSize: 10,
  loading: false,
  jump: ''
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

const admin = reactive({
  users: [],
  roleFilter: ''
})

const ui = reactive({
  message: { text: '', type: 'info', timer: null, id: 0 },
  deleteConfirm: { visible: false, fileId: '' },
  preview: { visible: false, type: 'text', name: '', info: '', url: '', text: '', error: '' }
})

function makeGroupId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function makeFileTask(file, relativePath, parent = null) {
  return reactive({
    kind: 'file',
    localId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    parent,
    file,
    name: file.name,
    baseName: file.name,
    relativePath: relativePath || file.name,
    displayName: relativePath || file.name,
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

function makeFolderTask(fileTasks, folderName) {
  const totalBytes = fileTasks.reduce((sum, item) => sum + (item.size || 0), 0)
  return reactive({
    kind: 'folder',
    localId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    groupId: makeGroupId(),
    folderName,
    displayName: `${folderName}（${fileTasks.length}个文件）`,
    files: fileTasks,
    totalBytes,
    completedBytes: 0,
    uploadedFiles: 0,
    currentIndex: 0,
    progress: 0,
    status: 'pending',
    error: '',
    paused: false,
    speed: 0,
    etaSec: 0,
    stepMessage: '等待开始',
    logs: []
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

function buildFileTree(items) {
  const root = {
    name: '',
    folders: {},
    files: [],
    totalSize: 0,
    totalFiles: 0,
    updatedAt: ''
  }

  function touchNode(node, file) {
    node.totalSize += file.file_size || 0
    node.totalFiles += 1
    if (!node.updatedAt || new Date(file.created_at) > new Date(node.updatedAt)) {
      node.updatedAt = file.created_at
    }
  }

  items.forEach((file) => {
    const parts = String(file.file_name || '').split('/').filter(Boolean)
    if (parts.length === 0) return
    let current = root
    const nodes = [root]
    for (let i = 0; i < parts.length - 1; i += 1) {
      const part = parts[i]
      if (!current.folders[part]) {
        current.folders[part] = {
          name: part,
          folders: {},
          files: [],
          totalSize: 0,
          totalFiles: 0,
          updatedAt: ''
        }
      }
      current = current.folders[part]
      nodes.push(current)
    }
    current.files.push(file)
    nodes.forEach((node) => touchNode(node, file))
  })

  return root
}

function getNode(tree, pathParts) {
  let current = tree
  for (const part of pathParts) {
    if (!current.folders[part]) return tree
    current = current.folders[part]
  }
  return current
}

const fileTree = computed(() => buildFileTree(fileList.value))
const currentNode = computed(() => getNode(fileTree.value, fileNav.path))
const fileItems = computed(() => {
  const node = currentNode.value
  const folders = Object.values(node.folders || {}).map((folder) => ({
    type: 'folder',
    key: `folder-${fileNav.path.join('/')}/${folder.name}`,
    name: folder.name,
    size: folder.totalSize,
    totalFiles: folder.totalFiles,
    updatedAt: folder.updatedAt,
    selected: isFolderSelected(folder.name)
  }))
  const files = (node.files || []).map((file) => ({
    type: 'file',
    key: `file-${file.file_id}`,
    file,
    displayName: String(file.file_name || '').split('/').pop() || file.file_name,
    size: file.file_size,
    updatedAt: file.created_at,
    selected: isSelected(file.file_id)
  }))
  folders.sort((a, b) => a.name.localeCompare(b.name))
  files.sort((a, b) => a.displayName.localeCompare(b.displayName))
  return [...folders, ...files]
})
const pagedFileItems = computed(() => {
  const start = (fileNav.page - 1) * fileNav.pageSize
  return fileItems.value.slice(start, start + fileNav.pageSize)
})
const totalFilePages = computed(() => Math.max(Math.ceil(fileItems.value.length / fileNav.pageSize), 1))
const selectedCount = computed(() => selectedIds.value.size)
const allVisibleSelected = computed(() => {
  const selectable = pagedFileItems.value
  if (selectable.length === 0) return false
  return selectable.every((item) => item.selected)
})

watch(
  () => [fileNav.path.join('/'), fileList.value.length],
  () => {
    fileNav.page = 1
  }
)

watch(
  () => fileList.value.length,
  () => {
    selectedIds.value = new Set()
  }
)

function onPickFiles(event) {
  const selected = Array.from(event.target.files || [])
  selected.forEach((file) => tasks.value.unshift(makeFileTask(file, file.name)))
  event.target.value = ''
}

function onPickFolder(event) {
  const selected = Array.from(event.target.files || [])
  if (selected.length === 0) {
    event.target.value = ''
    return
  }
  const firstPath = selected[0].webkitRelativePath || selected[0].name
  const folderName = firstPath.split('/')[0] || 'folder'
  const fileTasks = selected.map((file) => {
    const relativePath = file.webkitRelativePath || file.name
    return makeFileTask(file, relativePath)
  })
  const folderTask = makeFolderTask(fileTasks, folderName)
  fileTasks.forEach((fileTask) => {
    fileTask.parent = folderTask
  })
  tasks.value.unshift(folderTask)
  event.target.value = ''
}

function openFolder(name) {
  if (!name) return
  fileNav.path.push(name)
  fileNav.page = 1
}

function goUp() {
  if (fileNav.path.length === 0) return
  fileNav.path.pop()
  fileNav.page = 1
}

function goRoot() {
  if (fileNav.path.length === 0) return
  fileNav.path = []
  fileNav.page = 1
}

function goToCrumb(index) {
  fileNav.path = fileNav.path.slice(0, index + 1)
  fileNav.page = 1
}

function goFilePage(page) {
  fileNav.page = Math.min(Math.max(page, 1), totalFilePages.value)
}

function jumpFilePage() {
  const target = Number(fileNav.jump)
  if (!Number.isFinite(target)) return
  goFilePage(Math.floor(target))
  fileNav.jump = ''
}

function isSelected(fileId) {
  return selectedIds.value.has(fileId)
}

function getFolderPrefix(name) {
  const base = fileNav.path.join('/')
  return base ? `${base}/${name}` : name
}

function getFileIdsUnder(prefix) {
  const target = `${prefix}/`
  return fileList.value
    .filter((file) => {
      const path = String(file.file_name || '')
      return path === prefix || path.startsWith(target)
    })
    .map((file) => file.file_id)
}

function isFolderSelected(name) {
  const ids = getFileIdsUnder(getFolderPrefix(name))
  if (ids.length === 0) return false
  return ids.every((id) => selectedIds.value.has(id))
}

function toggleSelection(item) {
  if (item.type === 'folder') {
    toggleFolderSelection(item.name)
  } else {
    toggleFileSelection(item.file.file_id)
  }
}

function toggleFolderSelection(name) {
  const ids = getFileIdsUnder(getFolderPrefix(name))
  if (ids.length === 0) return
  const next = new Set(selectedIds.value)
  const allSelected = ids.every((id) => next.has(id))
  ids.forEach((id) => {
    if (allSelected) next.delete(id)
    else next.add(id)
  })
  selectedIds.value = next
}

function toggleFileSelection(fileId) {
  const next = new Set(selectedIds.value)
  if (next.has(fileId)) next.delete(fileId)
  else next.add(fileId)
  selectedIds.value = next
}

function toggleSelectVisible() {
  const next = new Set(selectedIds.value)
  const shouldSelect = !allVisibleSelected.value
  pagedFileItems.value.forEach((item) => {
    if (item.type === 'folder') {
      const ids = getFileIdsUnder(getFolderPrefix(item.name))
      ids.forEach((id) => {
        if (shouldSelect) next.add(id)
        else next.delete(id)
      })
    } else {
      const id = item.file.file_id
      if (shouldSelect) next.add(id)
      else next.delete(id)
    }
  })
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

async function downloadSelectionZip() {
  const ids = Array.from(selectedIds.value)
  if (ids.length === 0) return
  const res = await apiFetch('/api/files/zip/selected', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_ids: ids })
  })
  if (!res.ok) {
    showMessage(await errorText(res), 'error')
    return
  }
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'selected-files.zip'
  link.click()
  URL.revokeObjectURL(link.href)
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
  await Promise.all([
    refreshQuota(false), 
    refreshFiles(), 
    refreshHistory(false),
    data.user.role === 'admin' ? refreshUsers() : Promise.resolve()
  ])
  showMessage('登录成功', 'success')
}

function logout() {
  auth.token = ''
  auth.user = null
  auth.quota = null
  auth.error = ''
  localStorage.removeItem(TOKEN_KEY)
  tasks.value = []
  fileList.value = []
  fileNav.path = []
  fileNav.page = 1
  selectedIds.value = new Set()
  history.items = []
  history.total = 0
  history.page = 1
  history.jump = ''
}

async function refreshFiles() {
  if (!auth.token) return
  const res = await apiFetch('/api/files')
  fileList.value = await res.json()
  if (fileNav.page > totalFilePages.value) {
    fileNav.page = totalFilePages.value
  }
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

async function jumpHistoryPage() {
  const target = Number(history.jump)
  if (!Number.isFinite(target)) return
  history.jump = ''
  await goHistoryPage(Math.floor(target))
}

function removeTask(localId) {
  tasks.value = tasks.value.filter((t) => t.localId !== localId)
}

async function startTask(task) {
  if (task.kind === 'folder') {
    await startFolderTask(task)
    return
  }
  await startFileTask(task)
}

async function startFileTask(task, options = {}) {
  if (task.status === 'uploading' || task.status === 'hashing') return
  task.paused = false
  task.error = ''

  const notify = options.notify !== false

  try {
    if (!task.hash) {
      task.status = 'hashing'
      setTaskStep(task, '步骤 1/5：正在计算文件哈希（用于秒传和断点续传）')
      task.hash = await calculateFileHash(task.file)
      if (task.paused) return
    }

    setTaskStep(task, '步骤 2/5：正在初始化上传任务并检查已上传分片')
    const payload = {
      file_name: task.relativePath,
      file_size: task.size,
      file_hash: task.hash,
      chunk_size: CHUNK_SIZE
    }
    if (task.parent) {
      payload.group_id = task.parent.groupId
      payload.group_name = task.parent.folderName
      payload.group_total_files = task.parent.files.length
      payload.group_total_size = task.parent.totalBytes
    }
    const initRes = await apiFetch('/api/uploads/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
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
      if (notify) showMessage(`${task.displayName} 秒传完成`, 'success')
      return
    }

    task.uploadId = initData.upload_id
    setTaskStep(task, '步骤 3/5：开始分片并发上传')
    await runUpload(task, { notify })
  } catch (err) {
    task.status = task.paused ? 'paused' : 'error'
    task.error = String(err)
    setTaskStep(task, `上传失败：${task.error}`)
  }
}

function pauseTask(task) {
  if (task.kind === 'folder') {
    task.paused = true
    const current = task.files[task.currentIndex]
    if (current) pauseTask(current)
    task.status = 'paused'
    setTaskStep(task, '上传已暂停')
    return
  }
  task.paused = true
  for (const controller of task.controllers.values()) {
    controller.abort()
  }
  task.controllers.clear()
  task.status = 'paused'
  setTaskStep(task, '上传已暂停')
}

async function resumeTask(task) {
  if (task.kind === 'folder') {
    task.paused = false
    task.error = ''
    await startFolderTask(task)
    return
  }

  task.paused = false
  task.error = ''
  if (!task.uploadId) {
    await startFileTask(task)
    return
  }

  const res = await apiFetch(`/api/uploads/${task.uploadId}`)
  if (!res.ok) {
    await startFileTask(task)
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

function updateFolderProgress(folderTask, currentFileTask) {
  const totalBytes = folderTask.totalBytes || 0
  if (totalBytes <= 0) {
    folderTask.progress = 0
    return
  }
  let currentBytes = 0
  if (currentFileTask) {
    const uploadedBytes = currentFileTask.uploadedCount * CHUNK_SIZE
    currentBytes = Math.min(uploadedBytes, currentFileTask.size)
    folderTask.speed = currentFileTask.speed || 0
    folderTask.etaSec = currentFileTask.etaSec || 0
  }
  const progress = ((folderTask.completedBytes + currentBytes) / totalBytes) * 100
  folderTask.progress = Math.min(100, Math.max(0, progress))
}

function markFileDone(fileTask) {
  if (!fileTask.parent) return
  const folderTask = fileTask.parent
  folderTask.completedBytes += fileTask.size || 0
  folderTask.uploadedFiles = Math.min(folderTask.uploadedFiles + 1, folderTask.files.length)
  updateFolderProgress(folderTask, null)
}

async function completeFolderHistory(folderTask, status, message) {
  if (!folderTask?.groupId) return
  const res = await apiFetch('/api/uploads/group/complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      group_id: folderTask.groupId,
      group_name: folderTask.folderName,
      group_total_files: folderTask.files.length,
      group_total_size: folderTask.totalBytes,
      status,
      message
    })
  })
  if (!res.ok) {
    throw new Error(await errorText(res))
  }
}

async function startFolderTask(folderTask) {
  if (folderTask.status === 'uploading' || folderTask.status === 'hashing') return
  folderTask.paused = false
  folderTask.error = ''
  folderTask.status = 'uploading'

  if (folderTask.currentIndex >= folderTask.files.length) {
    folderTask.currentIndex = 0
  }

  for (let i = folderTask.currentIndex; i < folderTask.files.length; i += 1) {
    if (folderTask.paused) {
      folderTask.status = 'paused'
      setTaskStep(folderTask, '上传已暂停')
      return
    }

    const fileTask = folderTask.files[i]
    folderTask.currentIndex = i
    setTaskStep(folderTask, `正在上传：${fileTask.displayName}（${i + 1}/${folderTask.files.length}）`)

    await startFileTask(fileTask, { notify: false })
    if (fileTask.status === 'error') {
      folderTask.status = 'error'
      folderTask.error = fileTask.error || '文件上传失败'
      setTaskStep(folderTask, `上传失败：${folderTask.error}`)
      try {
        await completeFolderHistory(folderTask, 'error', folderTask.error)
        await refreshHistory(false)
      } catch (err) {
        showMessage(String(err), 'error')
      }
      return
    }
    if (fileTask.status === 'paused') {
      folderTask.status = 'paused'
      return
    }
    if (fileTask.status === 'done') {
      markFileDone(fileTask)
      folderTask.currentIndex = i + 1
    }
  }

  folderTask.status = 'done'
  folderTask.progress = 100
  folderTask.speed = 0
  folderTask.etaSec = 0
  setTaskStep(folderTask, '文件夹上传完成')
  try {
    await completeFolderHistory(folderTask, 'success', '文件夹上传完成')
    await refreshHistory(false)
  } catch (err) {
    showMessage(String(err), 'error')
  }
  showMessage(`${folderTask.displayName} 上传完成`, 'success')
}

function skipFolderError(folderTask) {
  if (!folderTask || folderTask.kind !== 'folder') return
  if (folderTask.currentIndex < folderTask.files.length) {
    const fileTask = folderTask.files[folderTask.currentIndex]
    fileTask.status = 'error'
    fileTask.error = fileTask.error || '已跳过'
  }
  folderTask.error = ''
  folderTask.status = 'uploading'
  folderTask.currentIndex += 1
  startFolderTask(folderTask)
}

async function runUpload(task, options = {}) {
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

    if (task.parent) updateFolderProgress(task.parent, task)
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
        if (task.parent) updateFolderProgress(task.parent, task)
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
      await mergeTask(task, options)
    }
  } finally {
    clearInterval(timer)
    task.controllers.clear()
    task.speed = 0
    task.etaSec = 0
    task.lastUploadedBytes = 0
    if (task.parent) updateFolderProgress(task.parent, task)
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
  formData.append('chunk', blob, `${task.baseName}.part${chunkIndex}`)

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

async function mergeTask(task, options = {}) {
  const notify = options.notify !== false
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
      if (notify) showMessage(`${task.displayName} 上传完成`, 'success')
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

function getFileExtension(name) {
  const idx = String(name || '').lastIndexOf('.')
  if (idx < 0) return ''
  return name.slice(idx + 1).toLowerCase()
}

function getPreviewType(file) {
  const ext = getFileExtension(file.file_name)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'image'
  if (['pdf'].includes(ext)) return 'pdf'
  if (['mp3', 'wav', 'ogg'].includes(ext)) return 'audio'
  if (['mp4', 'webm', 'ogg'].includes(ext)) return 'video'
  if (['txt', 'md', 'log', 'json', 'csv', 'xml', 'yml', 'yaml', 'py', 'js', 'ts', 'html', 'css', 'vue'].includes(ext)) {
    return 'text'
  }
  return 'text'
}

async function previewFile(file) {
  const type = getPreviewType(file)
  const maxBytes = type === 'text' ? 2 * 1024 * 1024 : 20 * 1024 * 1024
  ui.preview = {
    visible: true,
    type,
    name: file.file_name,
    info: `${formatBytes(file.file_size)} · ${type.toUpperCase()}`,
    url: '',
    text: '',
    error: ''
  }

  if (file.file_size > maxBytes) {
    ui.preview.error = '文件过大，建议下载查看'
    return
  }

  const res = await apiFetch(`/api/files/${file.file_id}/download`)
  if (!res.ok) {
    ui.preview.error = await errorText(res)
    return
  }
  if (type === 'text') {
    ui.preview.text = await res.text()
    return
  }
  const blob = await res.blob()
  ui.preview.url = URL.createObjectURL(blob)
}

function closePreview() {
  if (ui.preview.url) {
    URL.revokeObjectURL(ui.preview.url)
  }
  ui.preview = { visible: false, type: 'text', name: '', info: '', url: '', text: '', error: '' }
}

function showCopyCommands(file) {
  const baseUrl = window.location.origin
  const downloadUrl = `${baseUrl}/api/public/download/${file.file_id}?token=${auth.token}`
  const curlCmd = `curl -L -o "${file.file_name}" "${downloadUrl}"`
  const wgetCmd = `wget -O "${file.file_name}" "${downloadUrl}"`

  const commands = `文件: ${file.file_name}

curl 命令:
${curlCmd}

wget 命令:
${wgetCmd}`

  navigator.clipboard.writeText(curlCmd).then(() => {
    showMessage('curl 命令已复制到剪贴板', 'success')
  }).catch(() => {
    showMessage('复制失败，请手动复制', 'error')
  })
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
  if (!value) return '-'
  try {
    const date = new Date(value)
    if (isNaN(date.getTime())) return value
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
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

function roleText(role) {
  const map = {
    pending: '待审核',
    user: '用户',
    admin: '管理员'
  }
  return map[role] || role
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
    clearSelection()
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

async function refreshUsers() {
  const url = admin.roleFilter ? `/api/admin/users?role=${admin.roleFilter}` : '/api/admin/users'
  const res = await apiFetch(url)
  if (res.ok) {
    admin.users = await res.json()
  } else {
    showMessage(await errorText(res), 'error')
  }
}

async function approveUser(userId) {
  const res = await apiFetch(`/api/admin/users/${userId}/approve`, { method: 'POST' })
  if (res.ok) {
    showMessage('用户已批准', 'success')
    await refreshUsers()
  } else {
    showMessage(await errorText(res), 'error')
  }
}

async function deleteUser(userId) {
  if (!confirm('确认删除此用户？')) return
  const res = await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' })
  if (res.ok) {
    showMessage('用户已删除', 'success')
    await refreshUsers()
  } else {
    showMessage(await errorText(res), 'error')
  }
}

onMounted(async () => {
  if (auth.token) {
    try {
      const promises = [refreshQuota(false), refreshFiles(), refreshHistory(false)]
      const meRes = await apiFetch('/api/auth/me')
      const meData = await meRes.json()
      auth.user = meData
      if (meData.role === 'admin') {
        promises.push(refreshUsers())
      }
      await Promise.all(promises)
    } catch {
      logout()
    }
  }
})
</script>

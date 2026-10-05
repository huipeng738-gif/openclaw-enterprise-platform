<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { http } from '../api/http'
import { role } from '../stores/auth'
import PageHeader from '../components/common/PageHeader.vue'
import StatusTag from '../components/common/StatusTag.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

interface Dataset { id: string; name: string; description?: string; document_count?: number; status?: string; update_date?: string; update_time?: number }
interface Document { id: string; name: string; run?: string; chunk_count?: number; update_date?: string; update_time?: number }
interface Chunk { id: string; document_name: string; content: string; score: number; metadata?: Record<string, unknown> }

const datasets = ref<Dataset[]>([])
const documents = ref<Document[]>([])
const documentSearch = ref('')
const documentCategory = ref('all')
const documentStatus = ref('')
const documentMinChunks = ref<number | undefined>()
const documentUpdatedOn = ref('')
const datasetSearch = ref('')
const datasetStatus = ref('')
const datasetMinDocuments = ref<number | undefined>()
const datasetUpdatedOn = ref('')
const datasetId = ref('')
const retrievalIds = ref<string[]>([])
const query = ref('年假制度')
const chunks = ref<Chunk[]>([])
const datasetName = ref('')
const existingDatasetId = ref('')
const availableDatasets = ref<Dataset[]>([])
const managementOpen = ref(false)
const availableLoading = ref(false)
const uploadFile = ref<File | null>(null)
const error = ref('')
const busy = ref(false)
const loading = ref(false)
const topK = ref(5)
const threshold = ref(0.2)
const pendingDelete = ref<{ kind: 'dataset' | 'document'; document?: Document } | null>(null)
let documentRequest = 0

// 根据文档名称和文件类型筛选当前知识库中的真实文档。
const visibleDocuments = computed(() => documents.value.filter(document => {
  const name = document.name.toLowerCase()
  const category = documentCategory.value
  return name.includes(documentSearch.value.trim().toLowerCase()) &&
    (category === 'all' || (category === 'pdf' ? name.endsWith('.pdf') : !name.endsWith('.pdf'))) &&
    (!documentStatus.value || displayStatus(document.run) === documentStatus.value) &&
    (documentMinChunks.value == null || (document.chunk_count ?? 0) >= documentMinChunks.value) &&
    (!documentUpdatedOn.value || formatDateTime(document.update_date, document.update_time).startsWith(documentUpdatedOn.value))
}))

// 按名称或描述、文档数、状态及更新日期筛选知识库表格。
const visibleDatasets = computed(() => datasets.value.filter(dataset => {
  const keyword = datasetSearch.value.trim().toLowerCase()
  return (!keyword || `${dataset.name} ${dataset.description || ''}`.toLowerCase().includes(keyword)) &&
    (datasetMinDocuments.value == null || (dataset.document_count ?? 0) >= datasetMinDocuments.value) &&
    (!datasetStatus.value || (dataset.status || 'pending') === datasetStatus.value) &&
    (!datasetUpdatedOn.value || formatDateTime(dataset.update_date, dataset.update_time).startsWith(datasetUpdatedOn.value))
}))

// 从当前真实数据生成状态选项，避免写死 RAGFlow 状态集合。
const documentStatuses = computed(() => [...new Set(documents.value.map(item => displayStatus(item.run)))])
const datasetStatuses = computed(() => [...new Set(datasets.value.map(item => item.status || 'pending'))])

// 将 RAGFlow 日期或时间戳统一显示为本地年月日时分秒。
function formatDateTime(date?: string, timestamp?: number) {
  if (date) {
    const local = date.replace('T', ' ').replace(/\.\d+$/, '')
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(local)) return local
    if (/^\d{4}-\d{2}-\d{2}$/.test(local)) return `${local} 00:00:00`
    const parsed = new Date(date)
    if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString('sv-SE', { hour12: false })
  }
  if (timestamp != null) return new Date(timestamp < 1e12 ? timestamp * 1000 : timestamp).toLocaleString('sv-SE', { hour12: false })
  return '—'
}

// 清空文档列表的名称、类型、状态、分块数与日期筛选。
function clearDocumentFilters() {
  documentSearch.value = ''
  documentCategory.value = 'all'
  documentStatus.value = ''
  documentMinChunks.value = undefined
  documentUpdatedOn.value = ''
}

// 清空知识库列表的关键词、文档数、状态与日期筛选。
function clearDatasetFilters() {
  datasetSearch.value = ''
  datasetStatus.value = ''
  datasetMinDocuments.value = undefined
  datasetUpdatedOn.value = ''
}

// 优先提取后端错误说明，缺失时使用当前操作的默认提示。
function detail(e: any, fallback: string) { return e.response?.data?.detail || fallback }

// 刷新知识库列表，修正当前选择及检索范围，再加载所选知识库文档。
async function loadDatasets() {
  loading.value = true; error.value = ''
  try {
    datasets.value = (await http.get('/knowledge/bases')).data
    if (!datasets.value.some(item => item.id === datasetId.value))
      datasetId.value = datasets.value[0]?.id || ''
    retrievalIds.value = retrievalIds.value.filter(id => datasets.value.some(item => item.id === id))
    if (!retrievalIds.value.length && datasetId.value) retrievalIds.value = [datasetId.value]
    await loadDocuments()
    return true
  } catch (e: any) { error.value = detail(e, '加载知识库失败'); return false }
  finally { loading.value = false }
}

// 打开管理弹窗并读取 RAGFlow 中尚未关联的平台知识库。
async function openManagement() {
  managementOpen.value = true
  availableLoading.value = true
  availableDatasets.value = []
  existingDatasetId.value = ''
  error.value = ''
  try {
    availableDatasets.value = (await http.get('/knowledge/datasets/available')).data
  } catch (e: any) { error.value = detail(e, '加载可关联知识库失败') }
  finally { availableLoading.value = false }
}

// 加载所选知识库文档；请求序号避免较早响应覆盖切换后的文档列表。
async function loadDocuments() {
  const request = ++documentRequest
  const selected = datasetId.value
  documents.value = []
  if (!selected) return
  try {
    const data = (await http.get(`/knowledge/bases/${selected}/documents`)).data
    if (request === documentRequest) documents.value = data.docs || []
  } catch (e: any) { if (request === documentRequest) error.value = detail(e, '加载文档失败') }
}

// 按所选知识库、条数和相似度阈值检索，并更新分块结果与忙碌状态。
async function search() {
  if (!retrievalIds.value.length || !query.value.trim()) return
  error.value = ''; busy.value = true; chunks.value = []
  try {
    const data = (await http.post('/knowledge/retrieval', {
      query: query.value, top_k: topK.value, similarity_threshold: threshold.value,
      knowledge_base_ids: retrievalIds.value
    })).data
    chunks.value = data.results || []
  } catch (e: any) { error.value = detail(e, '检索失败') }
  finally { busy.value = false }
}

// 创建知识库后刷新列表，并选中新建知识库加载文档。
async function createDataset() {
  if (!datasetName.value.trim()) return
  error.value = ''; busy.value = true
  try {
    const created = (await http.post('/knowledge/bases', {name: datasetName.value.trim()})).data
    datasetName.value = ''
    datasetId.value = created.id
    if (!await loadDatasets()) return
    managementOpen.value = false
  } catch (e: any) { error.value = detail(e, '创建知识库失败') }
  finally { busy.value = false }
}

// 将已有 RAGFlow 数据集关联到平台，然后刷新知识库列表。
async function registerDataset() {
  if (!existingDatasetId.value.trim()) return
  error.value = ''; busy.value = true
  try {
    await http.post(`/knowledge/datasets/${existingDatasetId.value.trim()}/register`)
    datasetId.value = existingDatasetId.value.trim()
    existingDatasetId.value = ''
    if (!await loadDatasets()) return
    managementOpen.value = false
  } catch (e: any) { error.value = detail(e, '关联知识库失败') }
  finally { busy.value = false }
}

// 从文件选择事件中保存首个待上传文件，未选择时清空。
function selectFile(event: Event) {
  uploadFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

// 以 FormData 上传文档，成功后清空待上传文件并刷新文档列表。
async function upload() {
  if (!datasetId.value || !uploadFile.value) return
  error.value = ''; busy.value = true
  try {
    const form = new FormData()
    form.append('file', uploadFile.value)
    await http.post(`/knowledge/bases/${datasetId.value}/documents`, form)
    uploadFile.value = null
    await loadDocuments()
  } catch (e: any) { error.value = detail(e, '上传文档失败') }
  finally { busy.value = false }
}

// 提交单个文档解析请求，再刷新列表查看当前状态。
async function parse(document: Document) {
  error.value = ''; busy.value = true
  try {
    await http.post(`/knowledge/bases/${datasetId.value}/documents/${document.id}/parse`)
    await loadDocuments()
  } catch (e: any) { error.value = detail(e, '启动解析失败') }
  finally { busy.value = false }
}

// 用户确认后删除当前知识库，并刷新列表与当前选择。
async function removeDataset() {
  const selected = datasetId.value
  if (!selected) return false
  error.value = ''; busy.value = true
  try {
    await http.delete(`/knowledge/bases/${selected}`)
    datasetId.value = ''
    await loadDatasets()
    return true
  } catch (e: any) { error.value = detail(e, '删除知识库失败'); return false }
  finally { busy.value = false }
}

// 用户确认后删除指定文档，再刷新文档列表。
async function removeDocument(document: Document) {
  error.value = ''; busy.value = true
  try {
    await http.delete(`/knowledge/bases/${datasetId.value}/documents/${document.id}`)
    await loadDocuments()
    return true
  } catch (e: any) { error.value = detail(e, '删除文档失败'); return false }
  finally { busy.value = false }
}

async function confirmDelete() {
  const target = pendingDelete.value
  if (!target) return
  const deleted = target.kind === 'dataset' ? await removeDataset() : target.document && await removeDocument(target.document)
  if (deleted) pendingDelete.value = null
}
function setDeleteDialog(open: boolean) { if (!open) pendingDelete.value = null }

// 读取文档最新解析状态并合并到当前表格记录。
async function refreshStatus(document: Document) {
  try {
    const status = (await http.get(`/knowledge/bases/${datasetId.value}/documents/${document.id}/status`)).data
    Object.assign(document, status)
  } catch (e: any) { error.value = detail(e, '刷新解析状态失败') }
}

// 将 RAGFlow 解析状态映射为页面状态，未知值保留原文、空值按 pending 显示。
function displayStatus(run?: string) {
  return ({UNSTART: 'pending', RUNNING: 'parsing', DONE: 'completed', FAIL: 'failed', CANCEL: 'failed'} as Record<string, string>)[run || ''] || run || 'pending'
}

onMounted(loadDatasets)
</script>

<template>
  <PageHeader title="知识库管理" description="管理文档和知识库，支持检索测试与引用来源核对。">
    <template #actions><el-button v-if="role === 'admin'" type="primary" @click="openManagement">管理知识库</el-button></template>
  </PageHeader>
  <el-alert v-if="error" type="error" :title="error" show-icon />
  <div v-if="datasetId" class="card">
    <div class="knowledge-heading"><h3>文档 · {{ datasets.find(item => item.id === datasetId)?.name }}</h3><span>{{ documents.length }} 个文档</span></div>
    <div class="knowledge-list-filters">
      <label class="knowledge-field"><span>文档名称</span><el-input v-model="documentSearch" clearable placeholder="搜索文档名称" aria-label="搜索文档" /></label>
      <label class="knowledge-field"><span>文件类型</span><el-radio-group v-model="documentCategory" aria-label="文档类型"><el-radio-button value="all">全部</el-radio-button><el-radio-button value="pdf">PDF</el-radio-button><el-radio-button value="other">其他</el-radio-button></el-radio-group></label>
      <label class="knowledge-field"><span>解析状态</span><el-select v-model="documentStatus" clearable placeholder="全部状态"><el-option v-for="status in documentStatuses" :key="status" :label="status" :value="status" /></el-select></label>
      <label class="knowledge-field"><span>最少 Chunk 数</span><el-input-number v-model="documentMinChunks" :min="0" aria-label="最少 Chunk 数" /></label>
      <label class="knowledge-field"><span>更新日期</span><el-date-picker v-model="documentUpdatedOn" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" aria-label="文档更新日期" /></label>
      <el-button @click="clearDocumentFilters">重置筛选</el-button>
    </div>
    <el-button v-if="role === 'admin'" type="danger" :disabled="busy" @click="pendingDelete = { kind: 'dataset' }">删除知识库</el-button>
    <EmptyState v-if="!visibleDocuments.length" title="暂无匹配文档" description="尝试调整搜索条件，或上传新文档。" />
    <el-table v-else :data="visibleDocuments">
      <el-table-column prop="name" label="名称" />
      <el-table-column label="类型" width="100"><template #default="scope">{{ scope.row.name.split('.').pop()?.toUpperCase() || '未知' }}</template></el-table-column>
      <el-table-column label="解析状态" width="150"><template #default="scope"><StatusTag :status="displayStatus(scope.row.run)" /></template></el-table-column>
      <el-table-column prop="chunk_count" label="Chunk 数" width="110" />
      <el-table-column label="更新时间" width="200"><template #default="scope">{{ formatDateTime(scope.row.update_date, scope.row.update_time) }}</template></el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="scope">
          <el-button size="small" @click="refreshStatus(scope.row)">刷新</el-button>
          <el-button v-if="role === 'admin'" size="small" :disabled="busy" @click="parse(scope.row)">解析</el-button>
          <el-button v-if="role === 'admin'" size="small" type="danger" :disabled="busy" @click="pendingDelete = { kind: 'document', document: scope.row }">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="role === 'admin'" class="toolbar knowledge-upload">
      <label for="knowledge-file">上传到当前知识库</label>
      <input id="knowledge-file" type="file" @change="selectFile" />
      <el-button :disabled="!uploadFile || busy" @click="upload">上传文档</el-button>
    </div>
  </div>
  <div class="card" v-loading="loading">
    <div class="knowledge-section-heading"><div><h3>知识库列表</h3><p>选择知识库查看文档；管理员可在右上角创建或关联。</p></div><el-button @click="loadDatasets">刷新列表</el-button></div>
    <div class="knowledge-list-filters">
      <label class="knowledge-field"><span>当前知识库</span><el-select v-model="datasetId" placeholder="选择知识库" @change="loadDocuments">
        <el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" />
      </el-select></label>
      <label class="knowledge-field"><span>名称或描述</span><el-input v-model="datasetSearch" clearable placeholder="搜索名称或描述" aria-label="搜索知识库" /></label>
      <label class="knowledge-field"><span>最少文档数</span><el-input-number v-model="datasetMinDocuments" :min="0" aria-label="最少文档数" /></label>
      <label class="knowledge-field"><span>知识库状态</span><el-select v-model="datasetStatus" clearable placeholder="全部状态"><el-option v-for="status in datasetStatuses" :key="status" :label="status" :value="status" /></el-select></label>
      <label class="knowledge-field"><span>更新日期</span><el-date-picker v-model="datasetUpdatedOn" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" aria-label="知识库更新日期" /></label>
      <el-button @click="clearDatasetFilters">重置筛选</el-button>
    </div>
    <EmptyState v-if="!loading && !datasets.length" title="暂无可用知识库" />
    <el-table v-if="datasets.length" :data="visibleDatasets" @row-click="(row: Dataset) => { datasetId = row.id; loadDocuments() }">
      <el-table-column prop="name" label="名称" /><el-table-column prop="description" label="描述" />
      <el-table-column prop="document_count" label="文档数" width="100" />
      <el-table-column label="状态" width="100"><template #default="scope"><StatusTag :status="scope.row.status || 'pending'" /></template></el-table-column>
      <el-table-column label="更新时间" width="200"><template #default="scope">{{ formatDateTime(scope.row.update_date, scope.row.update_time) }}</template></el-table-column>
    </el-table>
    <div class="knowledge-section-heading knowledge-search-heading"><div><h3>检索测试</h3><p>选择检索范围，输入问题后查看匹配分块与引用来源。</p></div></div>
    <div class="knowledge-fields">
      <label class="knowledge-field"><span>检索范围（可多选）</span><el-select v-model="retrievalIds" multiple placeholder="选择要检索的知识库">
        <el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" />
      </el-select></label>
      <label class="knowledge-field"><span>返回条数（1–20）</span><el-input-number v-model="topK" :min="1" :max="20" aria-label="返回条数" /></label>
      <label class="knowledge-field"><span>相似度阈值（0–1，越高越严格）</span><el-input-number v-model="threshold" :min="0" :max="1" :step="0.05" aria-label="相似度阈值" /></label>
    </div>
    <label class="knowledge-field knowledge-question"><span>检索问题</span><div class="toolbar"><el-input v-model="query" placeholder="例如：年假制度是什么？" @keyup.enter="search" /><el-button type="primary" :loading="busy" :disabled="!retrievalIds.length || !query.trim()" @click="search">开始检索</el-button></div></label>
    <div v-for="chunk in chunks" :key="chunk.id" class="event">
      <b>{{ chunk.document_name || '未知来源' }}</b> · 相似度 {{ chunk.score?.toFixed(2) }}
      <p>{{ chunk.content }}</p>
      <small v-if="chunk.metadata && Object.keys(chunk.metadata).length">{{ chunk.metadata }}</small>
    </div>
    <p v-if="datasetId && !busy && !chunks.length">检索结果会显示在这里</p>
  </div>
  <el-dialog v-model="managementOpen" title="管理知识库" width="min(520px, calc(100vw - 32px))">
    <el-alert v-if="error" type="error" :title="error" show-icon />
    <div class="knowledge-manage-section"><h3>创建知识库</h3><p>在 RAGFlow 新建知识库，并自动加入当前平台。</p>
    <label class="knowledge-field"><span>知识库名称</span><div class="toolbar">
      <el-input v-model="datasetName" maxlength="128" placeholder="例如：企业制度库" @keyup.enter="createDataset" />
      <el-button type="primary" :loading="busy" :disabled="!datasetName.trim()" @click="createDataset">创建</el-button>
    </div></label></div>
    <div class="knowledge-manage-section"><h3>关联已有知识库</h3><p>从 RAGFlow 中选择尚未接入平台的知识库，不会复制或删除原有文档。</p>
    <label class="knowledge-field"><span>RAGFlow 知识库</span><div class="toolbar">
      <el-select v-model="existingDatasetId" filterable clearable :loading="availableLoading" placeholder="选择 RAGFlow 知识库" style="flex: 1">
        <el-option v-for="item in availableDatasets" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-button :loading="busy" :disabled="!existingDatasetId" @click="registerDataset">关联</el-button>
    </div></label>
    <p v-if="!availableLoading && !availableDatasets.length">暂无可关联的知识库</p>
    </div>
  </el-dialog>
  <ConfirmDialog :model-value="!!pendingDelete" title="确认删除" :message="pendingDelete?.kind === 'dataset' ? '确认删除此知识库及其文档？' : `确认删除 ${pendingDelete?.document?.name || '此文档'}？`" :busy="busy" @update:model-value="setDeleteDialog" @confirm="confirmDelete" />
</template>

<style scoped>
.knowledge-section-heading { display: flex; justify-content: space-between; align-items: start; gap: 16px; margin-bottom: 16px; }
.knowledge-section-heading h3, .knowledge-manage-section h3 { margin: 0; font-size: 17px; }
.knowledge-section-heading p, .knowledge-manage-section p { margin: 6px 0 0; color: var(--oc-muted); font-size: 13px; }
.knowledge-search-heading { border-top: 1px solid var(--oc-border); padding-top: 20px; margin-top: 24px; }
.knowledge-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 14px; margin-bottom: 16px; }
.knowledge-list-filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); align-items: end; gap: 14px; margin-bottom: 18px; }
.knowledge-field { display: grid; align-content: start; gap: 8px; min-width: 0; font-size: 13px; font-weight: 600; }
.knowledge-field > .el-select, .knowledge-field > .el-input-number, .knowledge-field > .el-date-editor { width: 100%; }
.knowledge-question { margin: 16px 0; }
.knowledge-question .el-input, .knowledge-manage-section .el-input { flex: 1 1 200px; }
.knowledge-manage-section { padding: 8px 0 20px; }
.knowledge-manage-section + .knowledge-manage-section { border-top: 1px solid var(--oc-border); padding-top: 20px; }
.knowledge-manage-section .knowledge-field { margin-top: 16px; }
.knowledge-upload { margin-top: 18px; }
.knowledge-upload label { font-size: 13px; font-weight: 600; }
</style>

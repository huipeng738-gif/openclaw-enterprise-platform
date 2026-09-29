<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../api/http'
import { role } from '../stores/auth'

interface Dataset { id: string; name: string; description?: string; document_count?: number; status?: string; update_date?: string }
interface Document { id: string; name: string; run?: string; chunk_count?: number; update_date?: string }
interface Chunk { id: string; document_name: string; content: string; score: number; metadata?: Record<string, unknown> }

const datasets = ref<Dataset[]>([])
const documents = ref<Document[]>([])
const datasetId = ref('')
const retrievalIds = ref<string[]>([])
const query = ref('年假制度')
const chunks = ref<Chunk[]>([])
const datasetName = ref('')
const existingDatasetId = ref('')
const uploadFile = ref<File | null>(null)
const error = ref('')
const busy = ref(false)
const loading = ref(false)
const topK = ref(5)
const threshold = ref(0.2)
let documentRequest = 0

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
  } catch (e: any) { error.value = detail(e, '加载知识库失败') }
  finally { loading.value = false }
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
    await loadDatasets()
    datasetId.value = created.id
    await loadDocuments()
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
    await loadDatasets()
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
  if (!selected || !confirm('确认删除此知识库及其文档？')) return
  error.value = ''; busy.value = true
  try {
    await http.delete(`/knowledge/bases/${selected}`)
    datasetId.value = ''
    await loadDatasets()
  } catch (e: any) { error.value = detail(e, '删除知识库失败') }
  finally { busy.value = false }
}

// 用户确认后删除指定文档，再刷新文档列表。
async function removeDocument(document: Document) {
  if (!confirm(`确认删除 ${document.name}？`)) return
  error.value = ''; busy.value = true
  try {
    await http.delete(`/knowledge/bases/${datasetId.value}/documents/${document.id}`)
    await loadDocuments()
  } catch (e: any) { error.value = detail(e, '删除文档失败') }
  finally { busy.value = false }
}

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
  <h1 class="page-title">企业知识库</h1>
  <el-alert v-if="error" type="error" :title="error" show-icon />
  <div class="card" v-loading="loading">
    <div class="toolbar">
      <el-select v-model="datasetId" placeholder="选择知识库" style="width: 240px" @change="loadDocuments">
        <el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-button @click="loadDatasets">刷新</el-button>
      <el-select v-model="retrievalIds" multiple placeholder="检索知识库" style="width: 240px">
        <el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-input-number v-model="topK" :min="1" :max="20" aria-label="返回条数" />
      <el-input-number v-model="threshold" :min="0" :max="1" :step="0.05" aria-label="相似度阈值" />
      <el-input v-model="query" placeholder="输入检索问题" @keyup.enter="search" />
      <el-button type="primary" :loading="busy" :disabled="!retrievalIds.length" @click="search">检索</el-button>
    </div>
    <p v-if="!loading && !datasets.length">暂无可用知识库</p>
    <el-table v-if="datasets.length" :data="datasets" @row-click="(row: Dataset) => { datasetId = row.id; loadDocuments() }">
      <el-table-column prop="name" label="名称" /><el-table-column prop="description" label="描述" />
      <el-table-column prop="document_count" label="文档数" width="100" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="update_date" label="更新时间" width="200" />
    </el-table>
    <div v-for="chunk in chunks" :key="chunk.id" class="event">
      <b>{{ chunk.document_name || '未知来源' }}</b> · 相似度 {{ chunk.score?.toFixed(2) }}
      <p>{{ chunk.content }}</p>
      <small v-if="chunk.metadata && Object.keys(chunk.metadata).length">{{ chunk.metadata }}</small>
    </div>
    <p v-if="datasetId && !busy && !chunks.length">检索结果会显示在这里</p>
  </div>
  <div v-if="datasetId" class="card">
    <h3>文档 · {{ datasets.find(item => item.id === datasetId)?.name }}</h3>
    <el-button v-if="role === 'admin'" type="danger" :disabled="busy" @click="removeDataset">删除知识库</el-button>
    <el-table :data="documents">
      <el-table-column prop="name" label="名称" />
      <el-table-column label="解析状态" width="150"><template #default="scope">{{ displayStatus(scope.row.run) }}</template></el-table-column>
      <el-table-column prop="chunk_count" label="Chunk 数" width="110" />
      <el-table-column prop="update_date" label="更新时间" width="200" />
      <el-table-column label="操作" width="240">
        <template #default="scope">
          <el-button size="small" @click="refreshStatus(scope.row)">刷新</el-button>
          <el-button v-if="role === 'admin'" size="small" :disabled="busy" @click="parse(scope.row)">解析</el-button>
          <el-button v-if="role === 'admin'" size="small" type="danger" :disabled="busy" @click="removeDocument(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="role === 'admin'" class="toolbar">
      <input type="file" @change="selectFile" />
      <el-button :disabled="!uploadFile || busy" @click="upload">上传文档</el-button>
    </div>
  </div>
  <div v-if="role === 'admin'" class="card">
    <h3>管理知识库</h3>
    <div class="toolbar">
      <el-input v-model="datasetName" placeholder="新知识库名称" />
      <el-button :disabled="busy" @click="createDataset">创建</el-button>
    </div>
    <div class="toolbar">
      <el-input v-model="existingDatasetId" placeholder="已有 RAGFlow 数据集 ID" />
      <el-button :disabled="busy" @click="registerDataset">关联已有知识库</el-button>
    </div>
  </div>
</template>

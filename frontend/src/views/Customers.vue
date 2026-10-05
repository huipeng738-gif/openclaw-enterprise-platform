<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'

interface CustomerSummary {
  customer_no: string
  name: string
  phone: string
  level: string
  status: string
  created_at: string
  order_count: number
  last_order_time: string | null
}
interface RecentOrder { order_no: string; status: string; total_amount: string; created_at: string }
interface CustomerDetail extends CustomerSummary { total_amount: string; recent_orders: RecentOrder[] }
interface CustomerPage { items: CustomerSummary[]; total: number; page: number; page_size: number }

const search = ref('')
const level = ref('')
const status = ref('')
const page = ref(1)
const pageSize = 20
const rows = ref<CustomerSummary[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const drawer = ref(false)
const detail = ref<CustomerDetail | null>(null)
const detailCustomerNo = ref('')
const detailLoading = ref(false)
const detailError = ref('')
let listRequest = 0
let detailRequest = 0

// 将固定的数据库枚举值转成页面标签，未知值保留原文。
function label(value: string, labels: Record<string, string>) { return labels[value] || value }

// 显示数据库日期，不对没有时区的文本做换算。
function timeText(value: string | null) { return value ? value.replace('T', ' ').slice(0, 16) : '—' }

// 读取真实客户分页列表，忽略筛选快速切换时已过期的响应。
async function load() {
  const request = ++listRequest
  loading.value = true
  error.value = ''
  try {
    const result = (await http.get<CustomerPage>('/customers', { params: {
      search: search.value.trim() || undefined,
      level: level.value || undefined,
      status: status.value || undefined,
      page: page.value, page_size: pageSize
    } })).data
    if (request !== listRequest) return
    rows.value = result.items
    total.value = result.total
  } catch {
    if (request !== listRequest) return
    rows.value = []
    total.value = 0
    error.value = '加载客户失败，请稍后重试'
  } finally { if (request === listRequest) loading.value = false }
}

// 搜索或筛选变化后从第一页重新读取。
function applyFilters() { page.value = 1; void load() }

// 切换分页并读取目标页。
function changePage(value: number) { page.value = value; void load() }

// 打开客户详情，读取后端返回的脱敏信息与最近订单。
async function loadDetail(customerNo: string) {
  const request = ++detailRequest
  detailCustomerNo.value = customerNo
  drawer.value = true
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    const result = (await http.get<CustomerDetail>(`/customers/${encodeURIComponent(customerNo)}`)).data
    if (request === detailRequest) detail.value = result
  } catch {
    if (request === detailRequest) detailError.value = '加载客户详情失败，请重试'
  } finally { if (request === detailRequest) detailLoading.value = false }
}

// 关闭详情时使旧请求失效。
function closeDetail() { detailRequest++ }

onMounted(load)
</script>

<template>
  <div class="customers-page">
    <PageHeader title="客户管理" description="管理客户信息和客户画像" />
    <div class="card customers-card">
      <div class="customers-filters">
        <el-input v-model="search" clearable placeholder="搜索客户编号、姓名…" aria-label="搜索客户" @keyup.enter="applyFilters" @clear="applyFilters" />
        <el-select v-model="level" placeholder="全部等级" aria-label="客户等级" @change="applyFilters">
          <el-option label="全部等级" value="" /><el-option label="普通" value="regular" /><el-option label="VIP" value="vip" />
        </el-select>
        <el-select v-model="status" placeholder="全部状态" aria-label="客户状态" @change="applyFilters">
          <el-option label="全部状态" value="" /><el-option label="正常" value="active" /><el-option label="停用" value="inactive" />
        </el-select>
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </div>
      <LoadingState v-if="loading && !rows.length" title="正在加载客户…" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="没有匹配的客户" description="可调整搜索词或筛选条件" />
      <template v-else>
        <el-table :data="rows" v-loading="loading" class="customers-table" stripe>
          <el-table-column prop="customer_no" label="客户编号" min-width="150" />
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="phone" label="手机号" min-width="135" />
          <el-table-column label="等级" min-width="90"><template #default="scope"><el-tag :type="scope.row.level === 'vip' ? 'warning' : 'info'">{{ label(scope.row.level, { vip: 'VIP', regular: '普通' }) }}</el-tag></template></el-table-column>
          <el-table-column label="状态" min-width="90"><template #default="scope"><el-tag :type="scope.row.status === 'active' ? 'success' : 'danger'">{{ label(scope.row.status, { active: '正常', inactive: '停用' }) }}</el-tag></template></el-table-column>
          <el-table-column prop="order_count" label="订单数" min-width="90" />
          <el-table-column label="最近订单" min-width="155"><template #default="scope">{{ timeText(scope.row.last_order_time) }}</template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" :aria-label="`查看客户 ${scope.row.customer_no}`" @click="loadDetail(scope.row.customer_no)">查看详情</el-button></template></el-table-column>
        </el-table>
        <el-pagination class="customers-pagination" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="changePage" />
      </template>
    </div>
    <el-drawer v-model="drawer" :title="`客户详情 · ${detailCustomerNo}`" size="min(480px, 100vw)" @close="closeDetail">
      <LoadingState v-if="detailLoading" title="正在加载客户详情…" />
      <ErrorState v-else-if="detailError" :message="detailError" @retry="loadDetail(detailCustomerNo)" />
      <div v-else-if="detail" class="customers-detail">
        <dl>
          <dt>客户编号</dt><dd>{{ detail.customer_no }}</dd>
          <dt>姓名</dt><dd>{{ detail.name }}</dd>
          <dt>手机号</dt><dd>{{ detail.phone }}</dd>
          <dt>等级</dt><dd>{{ label(detail.level, { vip: 'VIP', regular: '普通' }) }}</dd>
          <dt>状态</dt><dd>{{ label(detail.status, { active: '正常', inactive: '停用' }) }}</dd>
          <dt>订单数</dt><dd>{{ detail.order_count }}</dd>
          <dt>已支付金额</dt><dd>¥{{ detail.total_amount }}</dd>
          <dt>创建时间</dt><dd>{{ timeText(detail.created_at) }}</dd>
        </dl>
        <h3>最近订单</h3>
        <EmptyState v-if="!detail.recent_orders.length" title="暂无订单" />
        <el-table v-else :data="detail.recent_orders" size="small">
          <el-table-column prop="order_no" label="订单号" min-width="140" />
          <el-table-column label="状态" min-width="80"><template #default="scope">{{ scope.row.status }}</template></el-table-column>
          <el-table-column label="金额" min-width="90"><template #default="scope">¥{{ scope.row.total_amount }}</template></el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

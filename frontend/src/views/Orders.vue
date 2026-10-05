<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'

interface OrderSummary {
  order_no: string
  status: string
  total_amount: string
  payment_status: string
  created_at: string
  customer: { customer_no: string; name: string }
}
interface OrderItem { product_name: string; sku: string; quantity: number; unit_price: string }
interface OrderDetail extends OrderSummary { order_items: OrderItem[] }
interface OrderPage { items: OrderSummary[]; total: number; page: number; page_size: number }

const search = ref('')
const status = ref('')
const paymentStatus = ref('')
const page = ref(1)
const pageSize = 20
const rows = ref<OrderSummary[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const drawer = ref(false)
const detail = ref<OrderDetail | null>(null)
const detailOrderNo = ref('')
const detailLoading = ref(false)
const detailError = ref('')
let listRequest = 0
let detailRequest = 0

const orderLabels: Record<string, string> = {
  pending: '处理中', shipped: '已发货', completed: '已完成', cancelled: '已取消', refunded: '已退款'
}
const paymentLabels: Record<string, string> = { paid: '已支付', unpaid: '待支付', refunded: '已退款' }

// 把后端状态映射为中文标签，未知值仍原样展示，避免误报业务状态。
function label(value: string, labels: Record<string, string>) { return labels[value] || value }

// 根据真实订单状态选择视觉颜色，未知值显示中性色。
function tagType(value: string): 'success' | 'warning' | 'info' | 'danger' {
  if (['completed', 'shipped', 'paid'].includes(value)) return 'success'
  if (['pending', 'unpaid'].includes(value)) return 'warning'
  if (['cancelled', 'refunded'].includes(value)) return 'danger'
  return 'info'
}

// 格式化 API 的本地日期文本，不进行时区换算。
function timeText(value: string | null) { return value ? value.replace('T', ' ').slice(0, 16) : 'N/A' }

// 调用只读分页 API；请求序号避免快速更改筛选时旧结果覆盖新结果。
async function load() {
  const request = ++listRequest
  loading.value = true
  error.value = ''
  try {
    const result = (await http.get<OrderPage>('/orders', { params: {
      search: search.value.trim() || undefined,
      status: status.value || undefined,
      payment_status: paymentStatus.value || undefined,
      page: page.value, page_size: pageSize
    } })).data
    if (request !== listRequest) return
    rows.value = result.items
    total.value = result.total
  } catch {
    if (request !== listRequest) return
    rows.value = []
    total.value = 0
    error.value = '加载订单失败，请稍后重试'
  } finally { if (request === listRequest) loading.value = false }
}

// 应用搜索或状态筛选时回到第一页，避免停留在不存在的页码。
function applyFilters() { page.value = 1; void load() }

// 切换页码并读取对应的真实订单列表。
function changePage(value: number) { page.value = value; void load() }

// 打开详情抽屉，按订单编号读取明细，并忽略过期的异步响应。
async function loadDetail(orderNo: string) {
  const request = ++detailRequest
  detailOrderNo.value = orderNo
  drawer.value = true
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    const result = (await http.get<OrderDetail>(`/orders/${encodeURIComponent(orderNo)}`)).data
    if (request === detailRequest) detail.value = result
  } catch {
    if (request === detailRequest) detailError.value = '加载订单详情失败，请重试'
  } finally { if (request === detailRequest) detailLoading.value = false }
}

// 抽屉关闭时使在途详情请求失效。
function closeDetail() { detailRequest++ }

onMounted(load)
</script>

<template>
  <div class="orders-page">
    <PageHeader title="订单管理" description="查询订单和查看订单信息" />
    <div class="card orders-card">
      <div class="orders-filters">
        <el-input v-model="search" clearable placeholder="输入订单号、客户名或商品名…" aria-label="搜索订单" @keyup.enter="applyFilters" @clear="applyFilters" />
        <el-select v-model="status" placeholder="全部状态" aria-label="订单状态" @change="applyFilters">
          <el-option label="全部状态" value="" />
          <el-option label="处理中" value="pending" />
          <el-option label="已发货" value="shipped" />
          <el-option label="已完成" value="completed" />
          <el-option label="已取消" value="cancelled" />
          <el-option label="已退款" value="refunded" />
        </el-select>
        <el-select v-model="paymentStatus" placeholder="全部支付状态" aria-label="支付状态" @change="applyFilters">
          <el-option label="全部支付状态" value="" />
          <el-option label="已支付" value="paid" />
          <el-option label="待支付" value="unpaid" />
          <el-option label="已退款" value="refunded" />
        </el-select>
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </div>
      <LoadingState v-if="loading && !rows.length" title="正在加载订单…" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="没有匹配的订单" description="可调整搜索词或筛选条件" />
      <template v-else>
        <el-table :data="rows" v-loading="loading" class="orders-table" stripe>
          <el-table-column label="订单号" min-width="170"><template #default="scope"><span class="orders-number">{{ scope.row.order_no }}</span></template></el-table-column>
          <el-table-column label="客户" min-width="130"><template #default="scope">{{ scope.row.customer.name }}</template></el-table-column>
          <el-table-column label="状态" min-width="105"><template #default="scope"><el-tag :type="tagType(scope.row.status)" effect="light">{{ label(scope.row.status, orderLabels) }}</el-tag></template></el-table-column>
          <el-table-column label="金额" min-width="115"><template #default="scope">¥{{ scope.row.total_amount }}</template></el-table-column>
          <el-table-column label="支付状态" min-width="110"><template #default="scope"><el-tag :type="tagType(scope.row.payment_status)" effect="light">{{ label(scope.row.payment_status, paymentLabels) }}</el-tag></template></el-table-column>
          <el-table-column label="下单时间" min-width="150"><template #default="scope">{{ timeText(scope.row.created_at) }}</template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" :aria-label="`查看订单 ${scope.row.order_no}`" @click="loadDetail(scope.row.order_no)">查看详情</el-button></template></el-table-column>
        </el-table>
        <el-pagination class="orders-pagination" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="changePage" />
      </template>
    </div>
    <el-drawer v-model="drawer" :title="`订单详情 · ${detailOrderNo}`" size="min(480px, 100vw)" @close="closeDetail">
      <LoadingState v-if="detailLoading" title="正在加载订单详情…" />
      <ErrorState v-else-if="detailError" :message="detailError" @retry="loadDetail(detailOrderNo)" />
      <div v-else-if="detail" class="orders-detail">
        <dl>
          <dt>订单号</dt><dd>{{ detail.order_no }}</dd>
          <dt>客户</dt><dd>{{ detail.customer.name }}（{{ detail.customer.customer_no }}）</dd>
          <dt>订单状态</dt><dd><el-tag :type="tagType(detail.status)">{{ label(detail.status, orderLabels) }}</el-tag></dd>
          <dt>支付状态</dt><dd><el-tag :type="tagType(detail.payment_status)">{{ label(detail.payment_status, paymentLabels) }}</el-tag></dd>
          <dt>订单金额</dt><dd>¥{{ detail.total_amount }}</dd>
          <dt>下单时间</dt><dd>{{ timeText(detail.created_at) }}</dd>
        </dl>
        <h3>商品明细</h3>
        <EmptyState v-if="!detail.order_items.length" title="暂无商品明细" />
        <el-table v-else :data="detail.order_items" size="small">
          <el-table-column prop="product_name" label="商品" min-width="120" />
          <el-table-column prop="sku" label="SKU" min-width="110" />
          <el-table-column prop="quantity" label="数量" width="60" />
          <el-table-column label="单价" width="90"><template #default="scope">¥{{ scope.row.unit_price }}</template></el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

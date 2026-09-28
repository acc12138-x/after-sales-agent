<template>
  <div>
    <div class="page-title">👥 客户资产</div>

    <el-card shadow="never" style="margin-bottom:16px;">
      <el-form inline>
        <el-form-item label="VIP 等级">
          <el-select v-model="filters.vip_level" clearable placeholder="全部" style="width:120px;" @change="load">
            <el-option value="normal" label="普通" />
            <el-option value="silver" label="白银" />
            <el-option value="gold" label="黄金" />
            <el-option value="diamond" label="钻石" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="filters.risk_level" clearable placeholder="全部" style="width:120px;" @change="load">
            <el-option value="normal" label="🟢 正常" />
            <el-option value="suspicious" label="🟠 疑似" />
            <el-option value="high_risk" label="🔴 高风险" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="openAdd">+ 新增客户</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="customers" v-loading="loading" stripe @row-click="openDetail" style="cursor:pointer;">
        <el-table-column label="客户 ID" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.customer_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="VIP" width="90">
          <template #default="{ row }">
            <el-tag :type="vipType(row.vip_level)" size="small">{{ vipText(row.vip_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="110">
          <template #default="{ row }">
            <el-tag :type="riskType(row.risk_level)" size="small">
              {{ riskIcon(row.risk_level) }} {{ riskText(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_orders" label="订单" width="70" align="center" />
        <el-table-column prop="total_refunds" label="退款" width="70" align="center" />
        <el-table-column prop="total_complaints" label="投诉" width="70" align="center" />
        <el-table-column prop="total_tickets" label="工单" width="70" align="center" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click.stop="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detail ? ('👤 ' + detail.name + ' (' + detail.customer_id + ')') : ''" size="820px">
      <div v-if="detailLoading" style="text-align:center; padding:60px;">
        <el-icon class="is-loading" :size="36"><Loading /></el-icon>
      </div>
      <div v-else-if="detail">
        <!-- VIP + 风险 -->
        <div style="margin-bottom:16px;">
          <el-tag :type="vipType(detail.vip_level)" size="large">{{ vipText(detail.vip_level) }}</el-tag>
          <el-tag :type="riskType(detail.risk_level)" size="large" style="margin-left:8px;">
            {{ riskIcon(detail.risk_level) }} {{ riskText(detail.risk_level) }} (风险分: {{ detail.risk_score }})
          </el-tag>
        </div>

        <!-- 基本信息 -->
        <el-descriptions title="基本信息" :column="2" border>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detail.email || "-" }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="2">{{ detail.address || "-" }}</el-descriptions-item>
        </el-descriptions>

        <!-- 数据统计 -->
        <el-row :gutter="12" style="margin-top:16px;">
          <el-col :span="6"><el-statistic title="订单" :value="detail.total_orders" /></el-col>
          <el-col :span="6"><el-statistic title="退款" :value="detail.total_refunds" /></el-col>
          <el-col :span="6"><el-statistic title="投诉" :value="detail.total_complaints" /></el-col>
          <el-col :span="6"><el-statistic title="工单" :value="detail.total_tickets" /></el-col>
        </el-row>

        <!-- 风险详情 -->
        <el-alert v-if="riskDetail && riskDetail.reasons && riskDetail.reasons.length" type="warning" style="margin-top:16px;">
          <template #title>
            ⚠️ 风险原因：{{ riskDetail.reasons.join("、") }}
          </template>
        </el-alert>

        <!-- Tab：订单 / 工单 / 退款 -->
        <el-divider />
        <el-tabs v-model="detailTab">
          <el-tab-pane label="📦 订单历史" name="orders">
            <el-table :data="customerOrders" size="small" stripe empty-text="无订单">
              <el-table-column prop="order_id" label="订单号" width="140" />
              <el-table-column prop="product_name" label="商品" />
              <el-table-column prop="amount" label="金额" width="90">
                <template #default="{ row }">¥{{ row.amount }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100" />
              <el-table-column label="保修" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.in_warranty ? 'success' : 'info'" size="small">
                    {{ row.in_warranty ? "✅ 在保" : "已过保" }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="签收" width="80">
                <template #default="{ row }">
                  {{ row.days_since_delivered !== null ? row.days_since_delivered + "天" : "-" }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="🎫 工单" name="tickets">
            <el-table :data="customerTickets" size="small" stripe empty-text="无工单">
              <el-table-column prop="ticket_id" label="工单号" width="140" />
              <el-table-column prop="ticket_type" label="类型" width="90" />
              <el-table-column prop="status" label="状态" width="100" />
              <el-table-column prop="assigned_to" label="工程师" width="90" />
              <el-table-column prop="created_at" label="创建时间" width="160">
                <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 19) : "-" }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="💰 退款记录" name="refunds">
            <el-table :data="customerRefunds" size="small" stripe empty-text="无退款">
              <el-table-column prop="refund_id" label="退款单" width="140" />
              <el-table-column prop="amount" label="金额" width="100">
                <template #default="{ row }">¥{{ row.amount }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="120" />
              <el-table-column prop="reason" label="原因" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>

    <!-- 新增客户对话框 -->
    <el-dialog v-model="addVisible" title="➕ 新增客户" width="500">
      <el-form :model="addForm" label-width="90px">
        <el-form-item label="姓名"><el-input v-model="addForm.name" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="addForm.phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="addForm.email" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="addForm.address" /></el-form-item>
        <el-form-item label="VIP 等级">
          <el-select v-model="addForm.vip_level">
            <el-option value="normal" label="普通" />
            <el-option value="silver" label="白银" />
            <el-option value="gold" label="黄金" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="doAdd">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Loading } from "@element-plus/icons-vue";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });
api.interceptors.response.use(r => r.data, e => { ElMessage.error(e?.response?.data?.detail || e.message); return Promise.reject(e); });

const customers = ref([]);
const loading = ref(false);
const filters = reactive({ vip_level: "", risk_level: "" });

function vipText(v) { return { normal: "普通", silver: "白银", gold: "黄金", diamond: "钻石" }[v] || v; }
function vipType(v) { return { normal: "info", silver: "", gold: "warning", diamond: "danger" }[v] || "info"; }
function riskText(v) { return { normal: "正常", suspicious: "疑似", high_risk: "高风险" }[v] || v; }
function riskIcon(v) { return { normal: "🟢", suspicious: "🟠", high_risk: "🔴" }[v] || "❔"; }
function riskType(v) { return { normal: "success", suspicious: "warning", high_risk: "danger" }[v] || "info"; }

async function load() {
  loading.value = true;
  try {
    const params = {};
    if (filters.vip_level) params.vip_level = filters.vip_level;
    if (filters.risk_level) params.risk_level = filters.risk_level;
    customers.value = await api.get("/customers", { params });
  } finally { loading.value = false; }
}

const drawerVisible = ref(false);
const detail = ref(null);
const detailLoading = ref(false);
const detailTab = ref("orders");
const customerOrders = ref([]);
const customerTickets = ref([]);
const customerRefunds = ref([]);
const riskDetail = ref(null);

async function openDetail(row) {
  drawerVisible.value = true;
  detailLoading.value = true;
  detailTab.value = "orders";
  try {
    const [d, o, t, r, risk] = await Promise.all([
      api.get("/customers/" + row.customer_id),
      api.get("/customers/" + row.customer_id + "/orders").catch(() => ({ items: [] })),
      api.get("/customers/" + row.customer_id + "/tickets").catch(() => ({ items: [] })),
      api.get("/customers/" + row.customer_id + "/refunds").catch(() => ({ items: [] })),
      api.get("/customers/" + row.customer_id + "/risk").catch(() => null),
    ]);
    detail.value = d;
    customerOrders.value = o.items || [];
    customerTickets.value = t.items || [];
    customerRefunds.value = r.items || [];
    riskDetail.value = risk;
  } finally { detailLoading.value = false; }
}

const addVisible = ref(false);
const addForm = reactive({ name: "", phone: "", email: "", address: "", vip_level: "normal" });

function openAdd() {
  Object.assign(addForm, { name: "", phone: "", email: "", address: "", vip_level: "normal" });
  addVisible.value = true;
}

async function doAdd() {
  if (!addForm.name || !addForm.phone) return ElMessage.warning("姓名和手机号必填");
  await api.post("/customers", addForm);
  ElMessage.success("创建成功");
  addVisible.value = false;
  load();
}

onMounted(load);
</script>

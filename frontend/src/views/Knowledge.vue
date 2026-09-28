<template>
  <div>
    <div class="page-title">📚 知识库管理</div>

    <el-row :gutter="16">
      <!-- ============ 左：上传 ============ -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">📤 上传文档</span>
          </template>

          <el-tabs v-model="uploadTab">
            <!-- 文件上传 -->
            <el-tab-pane label="文件上传" name="file">
              <el-form label-width="90px">
                <el-form-item label="选择文件">
                  <el-upload
                    ref="uploadRef"
                    :auto-upload="false"
                    :limit="1"
                    :on-change="onFileChange"
                    :on-remove="onFileRemove"
                    accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls"
                    drag
                    style="width:100%;"
                  >
                    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                    <div class="el-upload__text">
                      拖拽文件到此处 或 <em>点击选择</em>
                    </div>
                    <template #tip>
                      <div class="el-upload__tip">
                        支持 PDF / Word / Excel / txt / Markdown
                      </div>
                    </template>
                  </el-upload>
                </el-form-item>
                <el-form-item label="文档 ID">
                  <el-input v-model="upFile.docId" placeholder="如 doc-manual-v1（不填自动生成）" />
                </el-form-item>
                <el-form-item label="来源">
                  <el-input v-model="upFile.source" placeholder="如 售后手册 / 研发部" />
                </el-form-item>
                <el-form-item>
                  <el-button
                    type="primary"
                    :loading="uploading"
                    :disabled="!upFile.file"
                    @click="doUploadFile"
                  >
                    <el-icon><Upload /></el-icon> 上传并索引
                  </el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <!-- 手动粘贴 -->
            <el-tab-pane label="手动粘贴" name="text">
              <el-form label-width="90px">
                <el-form-item label="文档 ID">
                  <el-input v-model="upText.docId" placeholder="不填自动生成" />
                </el-form-item>
                <el-form-item label="来源">
                  <el-input v-model="upText.source" placeholder="如 售后手册" />
                </el-form-item>
                <el-form-item label="内容">
                  <el-input
                    v-model="upText.content"
                    type="textarea"
                    :rows="8"
                    placeholder="# 标题\n\n## 小节\n内容..."
                  />
                </el-form-item>
                <el-form-item>
                  <el-button
                    type="primary"
                    :loading="uploading"
                    :disabled="!upText.content.trim()"
                    @click="doUploadText"
                  >
                    <el-icon><Upload /></el-icon> 上传并索引
                  </el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>

      <!-- ============ 右：统计 + 检索 ============ -->
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">📊 知识库统计</span>
          </template>

          <el-row :gutter="12">
            <el-col :span="12">
              <el-statistic title="总切片数" :value="stats.total_chunks || 0" />
            </el-col>
            <el-col :span="12">
              <el-statistic title="向量维度" :value="1024" />
            </el-col>
          </el-row>

          <el-divider />

          <div style="font-weight:600; margin-bottom:10px;">🔍 快速检索测试</div>
          <el-input
            v-model="testQuery"
            placeholder="输入问题，如 E102 报警"
            @keyup.enter="doTestSearch"
          >
            <template #append>
              <el-button :loading="testing" @click="doTestSearch">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>

          <div v-if="testResults.length" style="margin-top:12px;">
            <div
              v-for="(r, i) in testResults"
              :key="i"
              class="test-result"
              :class="{ pass: r.score >= 0.55 }"
            >
              <div class="test-result-head">
                <el-tag :type="r.score >= 0.55 ? 'success' : 'danger'" size="small" effect="plain">
                  {{ r.score >= 0.55 ? "✅" : "❌" }} score={{ r.score.toFixed(3) }}
                </el-tag>
                <span class="test-result-src">{{ r.source }}</span>
              </div>
              <div class="test-result-text">{{ r.text.slice(0, 120) }}...</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ============ 文档列表 ============ -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:600;">📋 已入库文档列表</span>
          <el-button :icon="Refresh" size="small" @click="loadDocs">刷新</el-button>
        </div>
      </template>

      <el-table :data="docs" v-loading="loadingDocs" stripe empty-text="暂无文档，请使用上方上传">
        <el-table-column prop="doc_id" label="文档 ID" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.doc_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="140" />
        <el-table-column prop="chunk_count" label="总切片" width="90" align="center" />
        <el-table-column prop="parent_count" label="父块" width="80" align="center" />
        <el-table-column prop="child_count" label="子块" width="80" align="center" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openDetail(row.doc_id)">
              <el-icon><View /></el-icon> 查看
            </el-button>
            <el-popconfirm title="删除后不可恢复，确认？" @confirm="doDelete(row.doc_id)">
              <template #reference>
                <el-button size="small" type="danger" link>
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ============ 详情抽屉 ============ -->
    <el-drawer
      v-model="detailVisible"
      :title="'📄 ' + detailDocId"
      size="720px"
      direction="rtl"
    >
      <div v-if="detailLoading" style="text-align:center; padding:40px;">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      </div>
      <div v-else-if="detail">
        <el-row :gutter="12" style="margin-bottom:16px;">
          <el-col :span="6"><el-statistic title="来源" :value="detail.source || '-'" /></el-col>
          <el-col :span="6"><el-statistic title="总切片" :value="detail.total_chunks" /></el-col>
          <el-col :span="6"><el-statistic title="父块" :value="detail.parent_count" /></el-col>
          <el-col :span="6"><el-statistic title="子块" :value="detail.child_count" /></el-col>
        </el-row>

        <el-tabs v-model="detailTab">
          <el-tab-pane label="📜 完整内容" name="full">
            <el-button size="small" :icon="Download" @click="downloadFull">
              下载 Markdown
            </el-button>
            <pre class="detail-pre">{{ detail.full_text }}</pre>
          </el-tab-pane>
          <el-tab-pane :label="`🟦 父块 (${detail.parent_count})`" name="parents">
            <el-collapse>
              <el-collapse-item
                v-for="(p, i) in detail.parents"
                :key="p.chunk_id"
                :title="`父块 ${i+1} · section=${p.section_index} · ${p.heading || '(无标题)'}`"
              >
                <pre class="detail-pre">{{ p.text }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>
          <el-tab-pane :label="`🟨 子块 (${detail.child_count})`" name="children">
            <el-empty v-if="!detail.children.length" description="该文档无子块" />
            <el-collapse v-else>
              <el-collapse-item
                v-for="(c, i) in detail.children"
                :key="c.chunk_id"
                :title="`子块 ${i+1} · section=${c.section_index} · sub=${c.sub_index}`"
              >
                <pre class="detail-pre">{{ c.text }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  UploadFilled, Upload, Search, Refresh, View, Delete, Loading, Download,
} from "@element-plus/icons-vue";
import api from "../api";

// ============ 上传 ============
const uploadTab = ref("file");
const uploading = ref(false);
const uploadRef = ref(null);

const upFile = reactive({ file: null, docId: "", source: "manual" });
const upText = reactive({ docId: "", source: "manual", content: "" });

function genDocId() {
  return "doc-" + Math.random().toString(36).slice(2, 8);
}

function onFileChange(file) {
  upFile.file = file.raw;
}
function onFileRemove() {
  upFile.file = null;
}

async function doUploadFile() {
  if (!upFile.file) return;
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", upFile.file);
    fd.append("doc_id", upFile.docId || genDocId());
    fd.append("source", upFile.source || "manual");
    const r = await api.ingestFile(fd);
    ElMessage.success(`✅ 上传成功：${r.filename} → ${r.chunks} 切片`);
    uploadRef.value?.clearFiles();
    upFile.file = null;
    upFile.docId = "";
    loadDocs();
    loadStats();
  } finally {
    uploading.value = false;
  }
}

async function doUploadText() {
  if (!upText.content.trim()) return;
  uploading.value = true;
  try {
    const r = await api.ingestText({
      doc_id: upText.docId || genDocId(),
      source: upText.source || "manual",
      content: upText.content,
    });
    ElMessage.success(`✅ 已入库：${r.chunks} 切片`);
    upText.content = "";
    upText.docId = "";
    loadDocs();
    loadStats();
  } finally {
    uploading.value = false;
  }
}

// ============ 文档列表 ============
const docs = ref([]);
const loadingDocs = ref(false);

async function loadDocs() {
  loadingDocs.value = true;
  try {
    const r = await api.getDocs();
    docs.value = r.items || [];
  } finally {
    loadingDocs.value = false;
  }
}

async function doDelete(docId) {
  const r = await api.deleteDoc(docId);
  ElMessage.success(`✅ 已删除 ${r.deleted} 个切片`);
  loadDocs();
  loadStats();
}

// ============ 详情 ============
const detailVisible = ref(false);
const detailDocId = ref("");
const detail = ref(null);
const detailLoading = ref(false);
const detailTab = ref("full");

async function openDetail(docId) {
  detailDocId.value = docId;
  detailVisible.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    detail.value = await api.getDocDetail(docId);
  } finally {
    detailLoading.value = false;
  }
}

function downloadFull() {
  const blob = new Blob([detail.value.full_text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${detail.value.doc_id}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ============ 统计 + 检索 ============
const stats = ref({ total_chunks: 0 });

async function loadStats() {
  try {
    stats.value = await api.kbStats();
  } catch {}
}

const testQuery = ref("E102 报警");
const testResults = ref([]);
const testing = ref(false);

async function doTestSearch() {
  if (!testQuery.value.trim()) return;
  testing.value = true;
  try {
    // 复用后端 chat 接口，但不建单
    const r = await api.chat({
      message: testQuery.value,
      thread_id: "test-" + Date.now(),
      user_id: "knowledge-test",
    });
    // chat 不返回原始检索结果，这里显示答案的引用作为占位
    testResults.value = (r.citations || []).map((c) => ({
      score: r.confidence || 0,
      source: c.source || "-",
      text: "引用来源 " + c.chunk_id,
    }));
    if (!testResults.value.length) {
      testResults.value = [{ score: r.confidence || 0, source: "chat", text: r.answer || "" }];
    }
  } finally {
    testing.value = false;
  }
}

onMounted(() => {
  loadDocs();
  loadStats();
});
</script>

<style scoped>
.test-result {
  padding: 8px 10px;
  border-radius: 6px;
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  margin-bottom: 8px;
}
.test-result.pass {
  background: #f0fdf4;
  border-left-color: #22c55e;
}
.test-result-head { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.test-result-src { font-size: 12px; color: #6b7280; }
.test-result-text { font-size: 13px; color: #374151; line-height: 1.5; }

.detail-pre {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow: auto;
}
</style>

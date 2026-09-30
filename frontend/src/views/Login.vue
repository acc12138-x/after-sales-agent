<template>
  <div class="login-page">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">
          <el-icon :size="24"><Tools /></el-icon>
        </div>
        <div class="brand-text">
          <h1>业务助手</h1>
          <p>Enterprise Business Agent</p>
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent>
        <el-form-item prop="name">
          <el-input
            v-model="form.name"
            placeholder="用户名"
            :prefix-icon="User"
            autocomplete="username"
            :disabled="loading"
            @keyup.enter="doLogin"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            autocomplete="current-password"
            :disabled="loading"
            @keyup.enter="doLogin"
          />
        </el-form-item>

        <transition name="fade">
          <div v-if="error" class="login-error">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ error }}</span>
          </div>
        </transition>

        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          :disabled="loading"
          @click="doLogin"
        >
          {{ loading ? "登录中…" : "登 录" }}
        </el-button>
      </el-form>

      <p class="login-foot">忘记密码？请联系管理员重置</p>

      <!-- 仅开发环境可见：生产构建（npm run build）不会包含这段 -->
      <div v-if="isDev" class="dev-hint">
        <span class="dev-tag">DEV</span>
        <span>默认账号 管理员 / admin123</span>
        <a @click="quickFill('管理员', 'admin123')">填入</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { User, Lock, Tools, WarningFilled } from "@element-plus/icons-vue";
import api from "../api";

const router = useRouter();
const route = useRoute();
const formRef = ref(null);
const loading = ref(false);
const error = ref("");
// 默认账号提示只在开发环境出现，避免生产环境把凭据印在登录页上
const isDev = import.meta.env.DEV;

const form = reactive({ name: "", password: "" });

const rules = {
  name: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

function quickFill(n, p) {
  form.name = n;
  form.password = p;
  error.value = "";
}

/** 只接受站内路径，避免开放重定向 */
function redirectTarget() {
  const q = route.query.redirect;
  return typeof q === "string" && q.startsWith("/") && !q.startsWith("//") ? q : "/chat";
}

async function doLogin() {
  error.value = "";
  try {
    await formRef.value.validate();
  } catch {
    return;
  }

  loading.value = true;
  try {
    const r = await api.login({ name: form.name.trim(), password: form.password });
    localStorage.setItem("auth_token", r.token);
    localStorage.setItem("auth_user", JSON.stringify(r.user));
    localStorage.setItem("last_login_name", r.user.name || form.name.trim());
    ElMessage.success("欢迎，" + r.user.name);
    router.push(redirectTarget());
  } catch (e) {
    // 拦截器已弹过 toast，这里再给一个页面内的持久提示，
    // 否则登录页上只会闪过一条消息，用户看不清原因
    const d = e && e.response && e.response.data && e.response.data.detail;
    error.value = typeof d === "string" ? d : "登录失败，请检查用户名和密码";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  const last = localStorage.getItem("last_login_name");
  if (last) form.name = last;
});
</script>

<style scoped>
.login-page {
  position: relative;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #eef2ff;
}

/* 背景光斑 */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  pointer-events: none;
}
.orb-1 {
  width: 520px; height: 520px;
  background: #6366f1;
  top: -180px; left: -140px;
}
.orb-2 {
  width: 460px; height: 460px;
  background: #a855f7;
  bottom: -180px; right: -120px;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  padding: 36px 36px 26px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 18px;
  box-shadow: 0 24px 60px rgba(49, 46, 129, 0.18);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}
.brand-mark {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.35);
  flex-shrink: 0;
}
.brand-text h1 {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: #111827;
  letter-spacing: 0.02em;
}
.brand-text p {
  margin: 2px 0 0;
  font-size: 11px;
  color: #9ca3af;
  letter-spacing: 0.04em;
}

.login-card :deep(.el-form-item) { margin-bottom: 18px; }

.login-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -4px 0 14px;
  padding: 9px 12px;
  font-size: 13px;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.login-btn {
  width: 100%;
  font-weight: 600;
  letter-spacing: 0.08em;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  border: none;
}
.login-btn:hover:not(.is-disabled) {
  background: linear-gradient(135deg, #4338ca, #6d28d9);
}

.login-foot {
  margin: 18px 0 0;
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}

.dev-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #e5e7eb;
  font-size: 12px;
  color: #6b7280;
}
.dev-tag {
  padding: 1px 6px;
  border-radius: 4px;
  background: #fef3c7;
  color: #b45309;
  font-size: 10px;
  font-weight: 700;
}
.dev-hint a {
  margin-left: auto;
  color: #4f46e5;
  cursor: pointer;
}
.dev-hint a:hover { text-decoration: underline; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

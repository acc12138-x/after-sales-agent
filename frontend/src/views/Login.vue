<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <el-icon :size="40"><Tools /></el-icon>
      </div>
      <h1 class="login-title">业务助手</h1>
      <p class="login-sub">Enterprise Business Agent</p>

      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="doLogin">
        <el-form-item prop="name">
          <el-input v-model="form.name" size="large" placeholder="用户名（如 管理员 / 张工）" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" size="large" type="password" show-password
                    placeholder="密码" :prefix-icon="Lock" @keyup.enter="doLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" style="width:100%;" @click="doLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider>默认账号</el-divider>
      <div class="hints">
        <div @click="quickFill('管理员', 'admin123')">管理员 / admin123</div>
        <div @click="quickFill('李主管', 'supervisor123')">李主管 / supervisor123</div>
        <div @click="quickFill('张工', 'engineer123')">张工 / engineer123</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { User, Lock, Tools } from "@element-plus/icons-vue";
import api from "../api";

const router = useRouter();
const formRef = ref(null);
const loading = ref(false);

const form = reactive({ name: "", password: "" });

const rules = {
  name: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

function quickFill(n, p) {
  form.name = n;
  form.password = p;
}

async function doLogin() {
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  loading.value = true;
  try {
    const r = await api.login({ name: form.name, password: form.password });
    localStorage.setItem("auth_token", r.token);
    localStorage.setItem("auth_user", JSON.stringify(r.user));
    ElMessage.success("欢迎，" + r.user.name);
    router.push("/chat");
  } catch (e) {
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
}
.login-card {
  width: 400px;
  padding: 40px 40px 30px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.login-logo { text-align: center; color: #4f46e5; margin-bottom: 12px; }
.login-title { text-align: center; font-size: 24px; margin: 0 0 4px; color: #111827; }
.login-sub { text-align: center; font-size: 12px; color: #9ca3af; margin: 0 0 32px; }
.hints { font-size: 12px; color: #6b7280; line-height: 2; }
.hints > div { cursor: pointer; padding: 2px 8px; border-radius: 4px; transition: background 0.15s; }
.hints > div:hover { background: #f3f4f6; color: #4f46e5; }
</style>

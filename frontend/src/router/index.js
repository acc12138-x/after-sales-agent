import { createRouter, createWebHistory } from "vue-router";
import MainLayout from "../layouts/MainLayout.vue";

const routes = [
  {
    path: "/",
    component: MainLayout,
    redirect: "/chat",
    children: [
      { path: "chat",          name: "对话测试",  component: () => import("../views/Chat.vue") },
      { path: "knowledge",     name: "知识库",    component: () => import("../views/Knowledge.vue") },
      { path: "tickets",       name: "工单",      component: () => import("../views/Tickets.vue") },
      { path: "customers",     name: "客户资产",  component: () => import("../views/Customers.vue") },
      { path: "refunds",       name: "退款管理",  component: () => import("../views/Refunds.vue") },
      { path: "sla",           name: "SLA时效",   component: () => import("../views/SLA.vue") },
      { path: "engineers",     name: "工程师",    component: () => import("../views/Engineers.vue") },
      { path: "audit",         name: "审计日志",  component: () => import("../views/Audit.vue") },
      { path: "notifications", name: "通知记录",  component: () => import("../views/Notifications.vue") },
      { path: "config",        name: "系统配置",  component: () => import("../views/Config.vue") },
      { path: "monitor",       name: "监控看板",  component: () => import("../views/Monitor.vue") },
    ],
  },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});

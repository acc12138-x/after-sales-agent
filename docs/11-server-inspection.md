# 服务器命令行速查：查看已运行项目的信息

> 面向场景：**云服务器上已经跑着一个项目**，你要摸清它的底细，
> 并判断**再加一个项目（含简历机器人）还装不装得下**。
>
> 全部命令在 Linux 服务器上执行。带 `sudo` 的按需加。

---

## 0. 先跑这 6 条（30 秒摸清现状）

```bash
# ① 内存还剩多少 —— 最关键的一条
free -h

# ② 磁盘还剩多少
df -h /

# ③ 有哪些容器在跑
docker ps

# ④ 每个容器吃多少内存
docker stats --no-stream

# ⑤ 所有 compose 项目在哪
docker compose ls

# ⑥ 谁占着端口（80/443 尤其重要）
sudo ss -tulpn | grep -E ':(80|443|3000|8000|8080|3306|6379)\b'
```

看完这 6 条，你就能回答三个问题：
**服务器还能不能加东西？80/443 被谁占了？现有项目是 Docker 还是裸跑？**

---

## 1. 内存：判断余量的唯一标准

```bash
free -h
```

输出示例：

```
               total        used        free      shared  buff/cache   available
Mem:           1.9Gi       1.2Gi       120Mi        12Mi       600Mi       560Mi
Swap:          2.0Gi          0B       2.0Gi
```

**看 `available`，不要看 `free`。** Linux 会用空闲内存做磁盘缓存（`buff/cache`），
那部分随时可回收，所以 `free` 小很正常。

| `available` | 结论 |
|---|---|
| > 700 MB | 可以再加一个中小项目 |
| 300–700 MB | 能加，但必须设内存上限并留神 |
| < 300 MB | **先别加**，会触发 OOM 把现有服务杀掉 |

再配合 `docker stats --no-stream` 看每个容器：

```
CONTAINER ID   NAME          CPU %   MEM USAGE / LIMIT   MEM %
a1b2c3d4e5f6   my-app        0.5%    420MiB / 700MiB     60%
f6e5d4c3b2a1   mysql         1.2%    480MiB / 1GiB       47%
```

**把所有 `MEM USAGE` 加起来**，再和 `available` 对比。

**Swap 有没有？** 如果 `Swap: 0B`，2GB 机器强烈建议加（见 [docs/10](10-deploy-2g.md) §3）。

---

## 2. Docker：看容器

```bash
docker ps                      # 运行中的
docker ps -a                   # 包括已退出的（看退出码）
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

只看某几个容器：

```bash
docker ps --filter "name=mysql" --filter "status=running"
```

### 实时资源（按内存排序，`q` 退出）

```bash
docker stats
```

### 单个容器的详情

```bash
# 状态 / 重启次数 / 启动时间
docker inspect my-app --format '{{.State.Status}} restarts={{.RestartCount}} started={{.State.StartedAt}}'

# 环境变量（找配置、找数据库地址）
docker inspect my-app --format '{{range .Config.Env}}{{println .}}{{end}}'

# 端口映射
docker inspect my-app --format '{{json .NetworkSettings.Ports}}'

# 挂在哪个网络（多项目共存时必须看）
docker inspect my-app --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'

# 数据卷（找数据存在宿主机哪儿）
docker inspect my-app --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'

# 内存上限设了没
docker inspect my-app --format '{{.HostConfig.Memory}}'
```

### 找到项目源码在服务器哪儿

```bash
docker compose ls
```

```
NAME              STATUS              CONFIG FILES
myproject         running(2)          /opt/apps/myproject/docker-compose.yml
```

或者：

```bash
docker inspect my-app --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
```

拿到目录就能 `cd` 进去看 `docker-compose.yml` 和 `.env`。

### 容器内部

```bash
docker exec -it my-app sh            # 进容器（alpine 用 sh，ubuntu 用 bash）
docker exec my-app env | sort        # 容器内的环境变量
docker exec my-app cat /etc/os-release
```

### 网络（多项目共存的基石）

```bash
docker network ls
docker network inspect edge          # 看哪些容器接在这个网络上
```

---

## 3. 日志

```bash
# 最后 100 行，跟着滚动
docker logs -f my-app --tail 100

# 带时间戳，看最近 30 分钟
docker logs --since 30m -t my-app

# 只看错误
docker logs my-app 2>&1 | grep -iE 'error|exception|failed'

# compose 项目整体
docker compose -f /opt/apps/myproject/docker-compose.yml logs -f --tail 50
```

**日志把磁盘写满**是常见事故，查一下：

```bash
du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -h | tail -10
```

如果某个日志几百 MB，说明没配轮转 —— 在 compose 里加：

```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

---

## 4. 端口与进程

```bash
# 谁在监听哪些端口
sudo ss -tulpn

# 只关心 Web 端口
sudo ss -tulpn | grep -E ':(80|443)\b'

# 谁占了 80
sudo lsof -i :80
# 或
sudo fuser -v 80/tcp

# netstat 版本（部分老系统）
sudo netstat -tulpn | grep LISTEN
```

**判断 Web 入口是什么**：

```bash
docker ps --format '{{.Names}}\t{{.Ports}}' | grep -E '0.0.0.0:(80|443)'
systemctl is-active nginx caddy 2>/dev/null
```

如果 80/443 被某个容器占着 → 说明它自带了反向代理（Nginx/Caddy 容器）。
如果被宿主机的 `nginx` 进程占着 → 配置在 `/etc/nginx/`。

---

## 5. 反向代理与域名

### Nginx（宿主机安装）

```bash
nginx -v
nginx -T 2>/dev/null | grep -E 'server_name|proxy_pass|root |listen'   # 打印全部生效配置
ls -l /etc/nginx/sites-enabled/ /etc/nginx/conf.d/
systemctl status nginx --no-pager
```

### Nginx（容器里）

```bash
docker exec -it <nginx容器> nginx -T 2>/dev/null | head -60
```

### Caddy

```bash
systemctl status caddy --no-pager
cat /etc/caddy/Caddyfile
docker exec edge-caddy cat /etc/caddy/Caddyfile
docker exec edge-caddy caddy validate --config /etc/caddy/Caddyfile
```

### 证书

```bash
# Let's Encrypt（certbot）
sudo certbot certificates

# Caddy 的证书存在数据卷里
docker volume ls | grep caddy
```

### 域名解析对不对

```bash
dig +short 你的域名
curl -I https://你的域名          # 看返回头与证书
curl -sI http://你的域名 | head -3
```

---

## 6. 磁盘

```bash
df -h                                   # 分区剩余
du -sh /var/lib/docker                  # Docker 占用
docker system df                        # 镜像/容器/卷/构建缓存 分项
docker image ls --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | sort -k2 -h | tail
```

Docker 最容易堆垃圾，清理（**`--volumes` 会删未使用的数据卷，先确认**）：

```bash
docker system prune -af                 # 安全：清停止的容器、悬空镜像、构建缓存
docker builder prune -af                # 只清构建缓存
# docker system prune -af --volumes     # ⚠️ 危险：会删未使用的数据卷
```

---

## 7. 非 Docker 部署怎么查

有些项目是裸跑或 systemd 托管的：

```bash
# 所有运行中的服务
systemctl list-units --type=service --state=running --no-pager

# 某个服务
systemctl status myproject --no-pager
journalctl -u myproject -n 100 --no-pager
journalctl -u myproject -f                  # 实时

# 按内存排序看进程（谁最吃内存）
ps aux --sort=-%mem | head -15

# 按 CPU 排序
ps aux --sort=-%cpu | head -10

# 找某个进程的完整启动命令
ps -ef | grep -v grep | grep python
```

Node 项目常用 pm2：

```bash
pm2 list
pm2 logs myapp --lines 100
pm2 info myapp
```

---

## 8. 系统整体健康

```bash
uptime                  # 负载（1/5/15 分钟）。和 CPU 核数对比
nproc                   # 核数。负载 < 核数 才算健康
top -bn1 | head -15     # 快照式 top
vmstat 1 5              # 每秒采样 5 次：内存/swap/IO
dmesg -T | tail -30     # 内核消息
```

**有没有被 OOM 杀过**（2GB 机器必查）：

```bash
dmesg -T | grep -i -E 'oom|killed process'
journalctl -k | grep -i oom
```

---

## 9. 为新项目做容量评估（你现在的场景）

把你现有项目的占用摸出来后，按这个表判断：

| 指标 | 安全线 | 怎么查 |
|---|---|---|
| 内存余量 | `available` ≥ 700 MB | `free -h` |
| Swap | 已启用，≥ 1 GB | `free -h` |
| 磁盘余量 | ≥ 5 GB | `df -h /` |
| CPU 负载 | 5 分钟负载 < 核数 | `uptime` + `nproc` |
| 80/443 | 有统一入口可复用 | `sudo ss -tulpn \| grep -E ':(80\|443)'` |

### 三个关键决策

**① 80/443 已经被占了怎么办？**

- 占它的是 **Nginx/Caddy** → **不要**再起一个反向代理，直接把新项目加进它的配置里
- 占它的**是项目自己的容器**（比如容器内 Nginx）→ 说明架构上需要一个独立的反代层，
  这时把「共享边缘代理」搭起来（见 [docs/10](10-deploy-2g.md) §5），再把原项目也接进去

**② 现有项目是 Docker 还是裸跑？**
- Docker → 新项目也上 Docker，接同一个 `edge` 网络，用**容器名**互访
- 裸跑（systemd/pm2）→ 也没关系，Docker 容器通过
  `host.docker.internal` 或宿主机 IP 访问它；反过来它用 `127.0.0.1:端口` 访问容器映射出来的端口

**③ 内存不够怎么办？**
- 优先砍：把现有项目的 MySQL 改 SQLite（省约 480 MB）
- 其次限：给每个容器设 `mem_limit`
- 最后升：4GB 通常差价不大，是最省事的选择

---

## 10. 常用组合拳

```bash
# 一屏看清全机状况
echo "===== 内存 ====="; free -h
echo "===== 磁盘 ====="; df -h /
echo "===== 负载 ====="; uptime
echo "===== 容器 ====="; docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "===== 容器资源 ====="; docker stats --no-stream
echo "===== Web 端口 ====="; sudo ss -tulpn | grep -E ':(80|443)\b'
echo "===== OOM 记录 ====="; sudo dmesg -T | grep -i -E 'oom|killed process' | tail -5

# 找出最占内存的 5 个进程
ps aux --sort=-%mem | head -6

# 找出最大的 10 个目录
sudo du -xh --max-depth=2 / 2>/dev/null | sort -h | tail -10

# 追踪一个请求打到哪
curl -sI https://你的域名 | head -10
docker logs -f --tail 20 你的容器名
```

---

## 11. 排查常见故障

| 现象 | 先查什么 |
|---|---|
| 网站打不开 | `sudo ss -tulpn \| grep -E ':(80\|443)'` → 有没有人监听；`docker ps` → 容器活着吗；`curl -I http://127.0.0.1` → 本机通不通 |
| 502 Bad Gateway | 反代配置里的上游地址/端口对不对；上游容器在不在 `edge` 网络里；`docker logs <上游容器>` |
| 容器反复重启 | `docker ps -a` 看退出码；`docker logs --tail 100 <容器>`；`dmesg \| grep -i oom` |
| 内存被吃满 | `docker stats` 找元凶；`dmesg \| grep -i oom` 看谁被杀 |
| 磁盘满了 | `df -h`；`docker system df`；`du -sh /var/lib/docker/containers/*/*-json.log \| sort -h \| tail` |
| 证书过期/续期失败 | `sudo certbot certificates`；Caddy 看 `docker logs edge-caddy` |
| 容器之间连不上 | `docker network inspect <网络名>` 确认两边都在同一网络；用**容器名**而不是 `localhost` |

---

## 12. 把这套用在新项目接入前

上线新项目之前，按顺序确认：

1. `free -h` → `available` 够不够
2. `docker stats --no-stream` → 现有项目实际吃多少
3. `sudo ss -tulpn | grep -E ':(80|443)\b'` → 入口是谁
4. `docker compose ls` → 现有项目的 compose 在哪、怎么组织的
5. `docker network ls` → 有没有现成的共享网络可复用
6. `df -h /` → 磁盘够不够放新镜像

确认完再动手，比上线后救火省事得多。

# codercheckin

多平台自动签到工具，适合 Docker / NAS / 青龙面板部署。支持 Cookie Cloud 同步 Cookie、Telegram 通知和定时执行。

## Docker Compose

新建 `compose.yaml`：

```yaml
services:
  codercheckin:
    image: ${CODERCHECKIN_IMAGE:-tophtab/codercheckin:latest}
    restart: unless-stopped
    env_file:
      - .env
    environment:
      CHECKIN_TARGETS: "${CHECKIN_TARGETS:-nodeseek,deepflood,v2ex}"
      CHECKIN_CRON: "${CHECKIN_CRON:-30 3 * * *}"
      PYTHONUNBUFFERED: "1"
      TZ: "${TZ:-Asia/Shanghai}"
```

新建 `.env`，推荐使用 Cookie Cloud：

```env
COOKIE_CLOUD_URL=http://your-cookiecloud-host:8088
COOKIE_CLOUD_UUID=your-uuid
COOKIE_CLOUD_PASSWORD=your-password
```

也可以手动配置 Cookie：

```env
NODESEEK_COOKIE=your_cookie_here
DEEPFLOOD_COOKIE=your_cookie_here
V2EX_COOKIE='your_v2ex_cookie_here'
```

可选配置：

```env
CHECKIN_TARGETS=nodeseek,deepflood,v2ex
CHECKIN_CRON=30 3 * * *
TZ=Asia/Shanghai
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

每次到达 `CHECKIN_CRON` 设定的时间后，会随机等待 0–30 分钟再开始本轮签到。
每个平台失败后间隔 30 秒重试，单个平台最多尝试 3 次；已经成功的平台不会重复执行。

启动并查看日志：

```bash
docker compose up -d
docker compose logs -f codercheckin
```

更新镜像：

```bash
docker compose pull
docker compose up -d
```

立即执行一次：

```bash
docker compose run --rm codercheckin python run.py
```

## 青龙面板

通过 GitHub 仓库订阅同步代码（公开仓库无需认证，私有仓库用 PAT）；三个平台各自一个定时任务，定时交给青龙，脚本内再随机延迟 0–30 分钟错开整点。

### 1. 新建订阅

订阅管理 → 创建订阅：

| 配置项 | 填写 |
|---|---|
| 类型 | 公开仓库 / 私有仓库（按仓库实际可见性选） |
| 链接 | `https://github.com/tophtab/codercheckin` |
| 分支 | `main` |
| 唯一值 | `codercheckin` |
| 拉取方式 | 公开仓库留空；私有仓库选「用户名密码/Token」（GitHub PAT，需 repo 权限） |
| 白名单 | `nodeseek_task.py deepflood_task.py v2ex_task.py`（空格分隔） |
| 依赖文件 | `requirements.txt`（每次拉取后自动安装依赖） |

保存后手动运行一次订阅：整仓库代码进入 `scripts/codercheckin/`，定时任务里自动生成三个任务。
仓库里的 `tests/`、`README.md` 等会一并拉下来，但白名单之外不会生成任务。

### 2. 环境变量

用 Cookie Cloud 时新建**三条**变量：

```env
COOKIE_CLOUD_URL=http://192.168.31.100:8088
COOKIE_CLOUD_UUID=扩展里的用户UUID
COOKIE_CLOUD_PASSWORD=扩展里的加密密码
```

> 排障提示：青龙容器可能访问不了公网 CookieCloud 地址，优先使用内网地址（如上例）。

不走 CookieCloud 时直接配平台 Cookie：`NODESEEK_COOKIE` / `DEEPFLOOD_COOKIE`（多账号用 `&` 分隔）、`V2EX_COOKIE`。

可选：`CHECKIN_RANDOM_DELAY_MAX`（随机延迟上限，分钟，默认 30，设为 0 关闭；对三个任务同时生效）。

> 注意：`CHECKIN_TARGETS` 在青龙形态下不参与任务选择，每个任务固定运行一个平台。

### 3. 定时任务

订阅自动生成三个任务，为每个任务设置定时规则（可以同一时间也可以错开）：

| 任务 | 命令 |
|---|---|
| NodeSeek | `task nodeseek_task.py` |
| Deepflood | `task deepflood_task.py` |
| V2EX | `task v2ex_task.py` |

实际开始时间 = 定时时间 + 0–30 分钟随机延迟；每个平台失败后间隔 30 秒重试，最多尝试 3 次。
手动执行：任务列表点「运行」；调试时在脚本目录运行 `python3 nodeseek_task.py --no-delay` 可跳过随机延迟。

### 4. 排障

| 现象 | 处理 |
|---|---|
| CookieCloud 拉取失败 / 网络不可达 | 青龙容器可能访问不了公网地址，改用内网地址（如 `http://192.168.31.100:8088`） |
| CookieCloud 中未找到某平台 Cookie | 浏览器扩展确认同步域名覆盖对应站点，手动同步一次后重跑 |
| `curl_cffi` 安装失败 | 查看依赖文件安装的完整报错；尝试更换 pip 镜像源后重新拉取订阅 |
| 日志出现 `ImportError` / `ModuleNotFoundError` | 确认代码是通过订阅整仓库拉取的，不要只复制单个脚本文件 |

## 支持平台

| 平台 | 多账号 | Cookie Cloud |
|------|--------|--------------|
| Nodeseek | 是 | 是 |
| Deepflood | 是 | 是 |
| V2EX | 否 | 是 |

## 使用仓库模板

```bash
git clone https://github.com/tophtab/codercheckin.git
cd codercheckin
cp .env.localtest.example .env
docker compose up -d
```

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.localtest.example .env
python run.py
pytest
```

单独测试平台：

```bash
python -m nodeseek.nodeseek
python -m deepflood.deepflood
python -m v2ex.v2ex
```

## 说明

- `NODESEEK_COOKIE` / `DEEPFLOOD_COOKIE` 支持多账号，用 `&` 分隔。
- 每个启用平台都需要 Cookie，可来自环境变量或 Cookie Cloud。
- 容器启动时会校验 Cookie 来源，失败会退出并在日志中提示缺少的平台。
- 建议将签到时间设置在凌晨 0:00-8:00 之间。

## License

MIT

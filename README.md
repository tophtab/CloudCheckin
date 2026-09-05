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

通过 GitHub 仓库订阅同步代码（公开仓库无需认证，私有仓库用 PAT）；三个平台各自一个定时任务，定时交给青龙，脚本默认到点直接执行。

### 1. 新建订阅

订阅管理 → 创建订阅：

| 配置项 | 填写 |
|---|---|
| 类型 | 公开仓库 / 私有仓库（按仓库实际可见性选） |
| 链接 | `https://github.com/tophtab/codercheckin` |
| 分支 | `main` |
| 唯一值 | `codercheckin` |
| 拉取方式 | 公开仓库留空；私有仓库选「用户名密码/Token」（GitHub PAT，需 repo 权限） |
| 白名单 | `nodeseek_task.py\|deepflood_task.py\|v2ex_task.py`（匹配脚本路径的正则，多个用 `\|` 分隔） |
| 依赖文件 | `.`（把整仓库的 .py/.js 复制进脚本目录；共享模块和平台包靠它搬运，不生成额外任务） |

保存后手动运行一次订阅：白名单匹配的三个平台脚本和「依赖文件」匹配的共享代码都会复制进 `scripts/tophtab_codercheckin_main/`（目录名由作者/仓库名/分支自动生成），定时任务里自动生成三个任务。
白名单决定生成哪些任务；`qinglong_task.py`、平台包等共享代码靠「依赖文件」复制进脚本目录，不会生成任务。

### 2. 安装 Python 依赖

青龙不会自动安装 `requirements.txt`，需到「依赖管理 → Python3 → 创建依赖」安装以下包（可一次填多个，空格分隔）：

```text
requests curl_cffi==0.14.0 python-dotenv cryptography croniter tzdata
```

也可以在宿主机一条命令装完（容器名按实际调整）：

```bash
docker exec -it qinglong pip3 install requests curl_cffi==0.14.0 python-dotenv cryptography croniter tzdata -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 环境变量

用 Cookie Cloud 时新建**三条**变量：

```env
COOKIE_CLOUD_URL=http://192.168.31.100:8088
COOKIE_CLOUD_UUID=扩展里的用户UUID
COOKIE_CLOUD_PASSWORD=扩展里的加密密码
```

> 排障提示：青龙容器可能访问不了公网 CookieCloud 地址，优先使用内网地址（如上例）。

不走 CookieCloud 时直接配平台 Cookie：`NODESEEK_COOKIE` / `DEEPFLOOD_COOKIE`（多账号用 `&` 分隔）、`V2EX_COOKIE`。

可选：`CHECKIN_RANDOM_DELAY_MAX`（随机启动延迟上限，分钟，默认关闭；设为如 `30` 后每个任务到点先随机等待 0–30 分钟再执行，对三个任务同时生效）。

> 注意：`CHECKIN_TARGETS` 在青龙形态下不参与任务选择，每个任务固定运行一个平台。

### 4. 定时任务

订阅自动生成三个任务，为每个任务设置定时规则（可以同一时间也可以错开）：

| 任务 | 命令（订阅自动生成） |
|---|---|
| NodeSeek | `task tophtab_codercheckin_main/nodeseek_task.py` |
| Deepflood | `task tophtab_codercheckin_main/deepflood_task.py` |
| V2EX | `task tophtab_codercheckin_main/v2ex_task.py` |

每个平台失败后间隔 30 秒重试，最多尝试 3 次。
手动执行：任务列表点「运行」即可立即开始。

### 5. 排障

| 现象 | 处理 |
|---|---|
| CookieCloud 拉取失败 / 网络不可达 | 青龙容器可能访问不了公网地址，改用内网地址（如 `http://192.168.31.100:8088`） |
| CookieCloud 中未找到某平台 Cookie | 浏览器扩展确认同步域名覆盖对应站点，手动同步一次后重跑 |
| 依赖安装失败 | 查看「依赖管理」日志里的完整报错；网络不通时改用国内 pip 镜像（见第 2 步） |
| 日志出现 `ImportError` / `ModuleNotFoundError` | 「依赖文件」没填：共享代码（`qinglong_task.py`、平台包等）靠它复制进脚本目录（见第 1 步） |

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

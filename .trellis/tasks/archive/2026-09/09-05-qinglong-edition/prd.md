# codercheckin 青龙脚本版:订阅部署 + 单条 COOKIECLOUD

## Goal

在保持 Docker 用法零影响的前提下,为 codercheckin 提供青龙面板部署形态:通过 GitHub 私有仓库订阅同步代码,**三个平台各自一个定时任务**(每个任务内置 0~30 分钟随机延迟、3 次失败重试),CookieCloud 支持与 AgentMore 完全一致的单条多行 `COOKIECLOUD` 环境变量(两项目共用同一条配置)。

## Background

- 项目现状:Docker 常驻(`scheduler.py` + croniter)为主,`run.py` 单次执行;CookieCloud 用三条环境变量 `COOKIE_CLOUD_URL` / `COOKIE_CLOUD_UUID` / `COOKIE_CLOUD_PASSWORD`。
- 参考项目 AgentMore(`D:\Code\agentmore`)已运行在青龙上,其 CookieCloud 配置是单条多行环境变量 `COOKIECLOUD`(`host=` / `uuid=` / `password=`,每行一条,可选 `domain=` 行)。
- 用户已在青龙上部署过 AgentMore,`COOKIECLOUD` 变量值已存在;codercheckin 采用同名同格式变量后,青龙上无需重复填写。

## Requirements

### R1 青龙平台任务脚本(每平台一个)

- 用户决策:不做总入口,**三个平台各自一个定时任务**(`nodeseek` / `deepflood` / `v2ex`)。
- 新增根级共享运行时 `qinglong_task.py` + 三个薄包装脚本 `nodeseek_task.py` / `deepflood_task.py` / `v2ex_task.py`;白名单识别三个包装脚本(平台模块文件本身不进白名单:直接运行会因相对导入路径失败,且自身无延迟无重试)。
- 每个包装脚本执行单个目标:复用 `checkin_runner.run_targets([target])`,从而保留每平台 **3 次失败重试、间隔 30 秒**的既有语义。
- 每个任务启动后默认随机延迟 0~30 分钟再执行(错开整点定时;三个任务各自独立延迟)。
- 提供跳过延迟的手段:命令行 flag(如 `--no-delay`)与环境变量(如 `CHECKIN_RANDOM_DELAY_MAX=0`,单位分钟,全局生效)至少其一。
- 对工作目录鲁棒:青龙订阅会把仓库拉到子目录,包装脚本必须保证无论 cwd 是什么都可正常运行(含 `checkin_runner` 以 `python -m` 启动的平台子进程)。
- 不做常驻定时逻辑(定时交给青龙计划任务),不引入 croniter 依赖。

### R2 CookieCloud 单条变量支持

- `cookiecloud/client.py` 支持单条环境变量 `COOKIECLOUD`,值为多行 `参数=值`,参数名与 AgentMore / CookieCloud 官方一致:`host` / `uuid` / `password`。
- 解析语义与 AgentMore 的解析器一致:按行拆分,容忍空行与 `#` 注释行,容忍未知参数行(如 `domain=chatglm.cn`)——同一份值必须能被两个项目无差别使用;codercheckin 侧不需要 `domain`(按各平台 domains 自行匹配)。
- 兼容性:保留现有三条变量写法(Docker 用户不受影响)。两条路径同时存在时,优先单条 `COOKIECLOUD`。
- 未配置任何 CookieCloud 变量时行为不变(静默跳过,回退到平台直连 Cookie 变量)。

### R3 通知:不做任何新增

- 不集成青龙内置 notify,不新增通知渠道。
- 现有 `telegram/notify.py` 及平台模块对它的调用保持原样;未配置 `TELEGRAM_TOKEN` 时维持现状(打一行日志、返回 False,不影响签到主流程)。

### R4 Docker 用法零影响

- `run.py`、`scheduler.py`、`docker-compose.yml`、Dockerfile 的对外行为不变。
- `scheduler.py` 仅允许等价重构(随机延迟函数提取为共享模块后原名再导出),cron 调度、日志文案、退出码语义不变。

### R5 README 青龙部署章节

- 青龙章节需体现:**三个包装脚本进白名单、三个定时任务**(各自 cron + 各自随机延迟);`CHECKIN_TARGETS` 环境变量对青龙形态不再参与任务选择(每任务固定单平台),README 中说明。
- 排障表至少包含:青龙容器访问公网 CookieCloud 地址网络不可达(换内网地址,AgentMore 实测教训)、`curl_cffi` 安装失败的处理方向、平台 Cookie 未命中(CookieCloud 扩展同步域名)。

## Acceptance Criteria

- [ ] 存在共享运行时 `qinglong_task.py` 与三个包装脚本 `nodeseek_task.py` / `deepflood_task.py` / `v2ex_task.py`:每个包装脚本不带参数时先输出随机延迟日志、等待后执行**对应单个平台**;`--no-delay`(或等效环境变量)立即执行。
- [ ] 每个包装脚本内部通过 `run_targets` 执行,失败重试语义与 Docker 一致(最多 3 次、间隔 30 秒)。
- [ ] 在仓库根目录以外的 cwd 下运行 `python <仓库路径>/nodeseek_task.py` 等包装脚本,平台子进程仍能以 `python -m <module>` 正常启动(通过 PYTHONPATH 注入实现)。
- [ ] 仅设置单条 `COOKIECLOUD`(多行 host/uuid/password,含注释行与 `domain=` 行)时,CookieCloud 拉取成功命中平台 Cookie;与 AgentMore 相同的值解析结果一致。
- [ ] 同时设置 `COOKIECLOUD` 与三条旧变量时,实际使用单条配置(有日志佐证);仅设置三条旧变量时行为与现在完全一致。
- [ ] `pytest` 全量通过;`scheduler.py` 现有测试不改断言语义即可通过。
- [ ] 未配置 `TELEGRAM_TOKEN` 的环境跑完一轮,签到结果判定不受通知缺失影响。
- [ ] README 含青龙部署章节,覆盖订阅、依赖、环境变量、定时、随机延迟、排障表。
- [ ] Docker 链路回归:`docker compose` 相关文件无行为性改动,`run.py`/`scheduler.py` 退出码语义不变。

## Out of Scope

- 覆盖全部平台的"总入口"任务(用户明确选择三平台各自定时)。
- 通知渠道的任何新增或修改(用户明确不使用通知)。
- 多账号经由 CookieCloud 的自动拆分(现有多账号 `&` 拼接写法维持现状)。
- 青龙单文件粘贴式部署(用户走 GitHub 私有仓库订阅,保留仓库结构)。
- V2EX 多账号支持、平台签到逻辑本身的改动。

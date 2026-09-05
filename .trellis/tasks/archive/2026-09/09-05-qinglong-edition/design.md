# 技术设计:codercheckin 青龙脚本版

## 目标与非目标

目标:每平台一个青龙定时任务(薄包装 + 共享运行时)、单条 `COOKIECLOUD` 配置、任意 cwd 可运行;Docker 链路行为不变。

非目标:总入口任务(用户选择三平台各自定时)、常驻调度、通知改动、平台签到逻辑改动、多账号机制改动。

## 模块边界与变更清单

```
qinglong_task.py          # 新增:青龙共享运行时(路径引导 + 延迟 + 单目标 run_targets)
nodeseek_task.py          # 新增:青龙包装脚本 → qinglong_task.main("nodeseek")
deepflood_task.py         # 新增:青龙包装脚本 → qinglong_task.main("deepflood")
v2ex_task.py              # 新增:青龙包装脚本 → qinglong_task.main("v2ex")
random_delay.py           # 新增:apply_random_start_delay / format_duration / MAX 常量(自 scheduler.py 迁出)
scheduler.py              # 修改:改为从 random_delay 再导出,内部调用点不变(等价重构)
cookiecloud/client.py     # 修改:配置解析层支持单条 COOKIECLOUD,取数/解密/合并流程不动
tests/test_random_delay.py   # 新增:延迟上限覆盖、0 关闭
tests/test_qinglong_task.py  # 新增:运行时行为、包装脚本 import 安全
tests/test_cookiecloud_client.py  # 扩展:单条解析、优先级
README.md                 # 修改:青龙部署章节 + 排障表
```

不改动:`run.py`、`checkin_runner.py`、平台包、`telegram/notify.py`、Docker 文件。

## 关键决策

### D1 随机延迟提取为共享模块 `random_delay.py`

`apply_random_start_delay`、`format_duration`、`MAX_RANDOM_START_DELAY_SECONDS` 自 `scheduler.py` 迁出;函数新增可选参数 `max_delay_seconds`(默认 `MAX_RANDOM_START_DELAY_SECONDS`)。`scheduler.py` 通过 `from random_delay import ...` 再导出,现有调用点与 `test_scheduler.py` 的引用(含 monkeypatch)语义不变——monkeypatch 替换的是 `scheduler` 命名空间内的名字,`main()` 经模块全局查找仍命中。

入口侧通过环境变量 `CHECKIN_RANDOM_DELAY_MAX`(分钟,默认 30,`0` 关闭)换算成秒传入,与 AgentMore 的 `RANDOM_DELAY_MAX`(分钟)语义对齐。

不直接 import `scheduler.py` 的原因:其模块顶部 `from croniter import croniter`,青龙环境不装 croniter 会直接 ImportError。

### D2 青龙任务执行序列(每个平台任务独立)

三个包装脚本各是一个标准入口(spec 的 entrypoint 形状),内容收敛为一行调用:

```python
# nodeseek_task.py(其余两个同理,替换目标名)
import sys
from qinglong_task import main
if __name__ == "__main__":
    try:
        sys.exit(main("nodeseek"))
    except KeyboardInterrupt:
        sys.exit(0)
```

`qinglong_task.main(target) -> int`:

```
路径引导(见 D3)
解析 --no-delay
max_delay_seconds = CHECKIN_RANDOM_DELAY_MAX(分钟,默认 30,0 关闭)× 60
未关闭 → apply_random_start_delay(max_delay_seconds=...)
return run_targets([target])        # 单目标仍走 runner:3 次重试 / 30s 间隔 / 子进程隔离
异常(TargetExecutionError 等)→ log + return 1   # 与 run.py 入口形状一致
```

- 复用 `run_targets([target])` 而不是直接调平台模块:保留失败重试与子进程隔离语义(用户明确要求每脚本 3 次尝试);单目标时 `parse_targets` 的 `CHECKIN_TARGETS` 不参与,任务与平台一一对应。
- 不调用 `validate_target_cookies`:与 `run.py` 对齐,失败由 runner 重试兜底。
- 不带 `load_dotenv()`:青龙无 `.env`,平台子进程各自已有;避免入口对文件布局产生依赖。
- 为什么不让白名单直接指向平台模块文件:从子目录运行时 sys.path[0] 是平台子目录,找不到仓库根模块;且平台模块自身无延迟、无重试。包装脚本放仓库根,路径引导集中做一次。

### D3 任意 cwd 鲁棒性(PYTHONPATH 注入)

青龙订阅把仓库拉到 `data/scripts/<repo>/` 子目录,任务执行时 cwd 不保证是仓库根,而 `checkin_runner` 以 `[sys.executable, "-m", module]` 启动平台子进程,`-m` 依赖 sys.path。入口在 import 业务模块前:

1. `sys.path.insert(0, REPO_ROOT)` —— 保证入口自身的顶层 import(`checkin_runner` 等)成立(`python <path>/qinglong_task.py` 时 sys.path[0] 本就是脚本目录,此步为兜底);
2. `os.environ["PYTHONPATH"] = REPO_ROOT + pathsep + 原值` —— 子进程继承环境,`-m` 在任意 cwd 下可解析。

不修改 `checkin_runner`(规范:批量运行器不感知部署形态)。

### D3b `qinglong_task.py` 自身的 import 顺序

`qinglong_task.py` 顶部仅引标准库,先做路径引导,再 import `checkin_runner` / `random_delay` —— 保证它被包装脚本从任意 cwd import 时都不会先炸在顶层 import 上。包装脚本与它同目录,Python 的 `sys.path[0]` 即仓库根,import 根模块天然成立。

### D4 单条 `COOKIECLOUD` 解析(与 AgentMore 逐字兼容)

`cookiecloud/client.py` 新增内部函数 `_parse_cookiecloud_single_var(raw) -> dict | None`:

- 语义对齐 AgentMore `cc_config`:按行拆分;跳过空行、`#` 开头行、无 `=` 行;`key.strip().lower()` 仅接受 `host` / `uuid` / `password` / `domain`;`host` 去尾部 `/`。
- `domain` 解析但忽略(codercheckin 按 `TARGETS[].domains` 自行匹配);未知 key 忽略——保证两项目可粘贴同一份值。
- `host`+`uuid`+`password` 齐全返回配置,否则返回 None 并 log 缺哪些(可观测)。

配置解析顺序(`_fetch_cookiecloud_payload` 开头):

1. `COOKIECLOUD` 非空 → 单条解析;命中时 log `Using single-variable COOKIECLOUD config`(验收佐证点);
2. 解析失败或不完整 → 回落三条旧变量(原逻辑);
3. 均无 → 现状行为(返回 None,静默跳过)。

`crypto_type` 查询参数、GET→POST 兜底、进程内缓存、解密与合并逻辑全部不动;改动收敛在"取哪一组 host/uuid/password"。

### D5 子进程级 CookieCloud 拉取次数

`checkin_runner` 以子进程运行平台模块,每个子进程各自拉一次 CookieCloud(现有缓存是进程内的),一轮 = 平台数次拉取。与 Docker 现状一致,不引入跨进程缓存(复杂度不值)。

### D6 通知不动

平台模块内 `notify=send_tg_notification` 保持;未配置 token 时现状是打日志 + 返回 False,不抛错,主流程不受影响。无代码改动。

### D7 README 青龙章节要点

- 订阅:类型选"私有仓库",链接 `https://github.com/tophtab/codercheckin`,分支 `main`,拉取方式 Token(GitHub PAT,repo 权限);白名单填三个包装脚本 `nodeseek_task.py`、`deepflood_task.py`、`v2ex_task.py`(三个平台各生成一个定时任务;tests 等不被识别)。
  - 订阅是整仓库 git clone/pull + 拷贝(去除 .git),新增文件随仓库自动同步,无需单独的增量机制;白名单只影响"哪些文件被识别为任务脚本"。
  - 订阅"依赖文件"字段填 `requirements.txt`:每次拉取后青龙自动安装依赖(推荐,免手动);或手动在依赖管理 → Python 装 `requests`、`curl_cffi`、`python-dotenv`、`cryptography`(不需要 `croniter`/`tzdata`,多装无害)。
- 环境变量:单条 `COOKIECLOUD`(示例多行值,与 AgentMore 同一条值可复用)、可选 `CHECKIN_RANDOM_DELAY_MAX`、平台直连 Cookie 变量(不走 CookieCloud 时);说明 `CHECKIN_TARGETS` 在青龙三任务形态下不参与任务选择。
- 计划任务:订阅自动生成 `task nodeseek_task.py` 等三个任务,cron 各自设置(可同时或错开,脚本内各自再随机延迟 0~30 分钟);说明 `CHECKIN_RANDOM_DELAY_MAX`、`--no-delay`。
- 排障表:公网 CookieCloud 地址网络不可达→换内网地址(AgentMore 实测);`curl_cffi` 装不上→确认依赖管理里完整报错/换 pip 源;平台 Cookie 未命中→CookieCloud 扩展同步域名覆盖对应站点。

## 兼容性

- 三条旧变量行为路径不删,优先级仅在新变量存在时生效。
- `scheduler.py` 重构为再导出,对外符号(`apply_random_start_delay`、`format_duration`、`MAX_RANDOM_START_DELAY_SECONDS`)不变。
- 无持久化/数据结构变化;无网络协议变化(仍是同两个 CookieCloud 端点)。

## 回滚

全部改动为"新增文件 + 两个文件的等价修改 + README",`git revert` 单次提交即可整体回滚;Docker 用户只需继续拉旧配置运行,无需数据迁移。

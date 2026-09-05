# Journal - toph (Part 1)

> AI development session journal
> Started: 2026-05-13

---



## Session 1: Pin curl_cffi and update Trellis

**Date**: 2026-07-16
**Task**: Pin curl_cffi and update Trellis
**Branch**: `main`

### Summary

Pinned curl_cffi to 0.14.0 after reproducing the 0.15.0 V2EX TLS failure in python:3.11-slim, verified tests and Docker connectivity, and committed the Trellis 0.6.7 upgrade.

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `8833d8d` | (see git log) |
| `c1fe07b` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: Add check-in retries and random delay

**Date**: 2026-07-16
**Task**: Add check-in retries and random delay
**Branch**: `main`

### Summary

Added per-target retries with three total attempts and 30-second intervals, added a 0-30 minute random delay after each cron trigger, documented the runtime contract, and verified 61 tests plus Compose configuration.

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `c04327a` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: 青龙脚本版:三平台任务 + 单条 COOKIECLOUD
<!-- trellis-session: v=2 fp=32b17756acbb1a0a -->

**Date**: 2026-09-05
**Task**: 青龙脚本版:三平台任务 + 单条 COOKIECLOUD
**Branch**: `main`

### Summary

为 codercheckin 增加青龙部署形态:三个平台各自的 *_task.py 包装任务(内置 0~30 分钟随机延迟、复用 run_targets 保留 3 次重试),qinglong_task.py 共享运行时注入 PYTHONPATH 保证任意 cwd 可用;cookiecloud 客户端支持与 AgentMore 共用的单条多行 COOKIECLOUD 变量(优先于三条旧变量,Docker 三变量模式不变);README 增加私有仓库订阅部署章节;随机延迟函数提取为 random_delay.py,scheduler 再导出;同步 spec(directory-structure/error-handling)。pytest 81 全绿。同仓提交既有 trellis 工具链升级。

### Git Commits

| Hash | Message |
|------|---------|
| `036f252` | feat: add Qinglong per-platform tasks and single COOKIECLOUD variable |
| `172dc55` | chore: update trellis toolchain and platform files |

### Status

[OK] **Completed**


## Session 4: 青龙部署陪跑:订阅机制修正 + COOKIECLOUD 恢复 + curl_cffi 下限校验
<!-- trellis-session: v=2 fp=8db5de52f876d365 -->

**Date**: 2026-09-05
**Task**: 青龙部署陪跑:订阅机制修正 + COOKIECLOUD 恢复 + curl_cffi 下限校验
**Branch**: `main`

### Summary

全程源码级验证 qinglong 机制(update.sh/otask.sh/sitecustomize.py)并陪跑部署。结论:1) 订阅白名单是 egrep 正则(多模式用 | 分隔),依赖文件字段只复制脚本不装依赖,python 任务的共享代码必须靠依赖文件(.)复制进脚本目录;2) 恢复与 AgentMore 共用的单条多行 COOKIECLOUD 变量(优先于三条变量,Docker 形态不变);3) 青龙形态随机延迟默认关闭,保留 CHECKIN_RANDOM_DELAY_MAX 开关;4) curl_cffi 放宽为 >=0.14 下限(import 时校验,实测 0.14.0/0.16.3 行为一致,放弃等值钉死与隔离目录方案),本地 venv 也曾静默漂移到 0.15.0 证明该防线必要;5) 代理变量必须配在青龙「环境变量」页——python 任务的最终环境由 sitecustomize.py 快照重建,compose 级变量不保证透传。部署最终三平台全部 succeeded。

### Git Commits

| Hash | Message |
|------|---------|
| `ed8e291` | docs: align Qinglong subscription guide with public repo |
| `8de6969` | docs: fix Qinglong whitelist regex format and dependency install steps |
| `399dfc8` | docs: copy shared modules via subscription dependences field |
| `7b51584` | feat: disable Qinglong random start delay by default |
| `0a6840e` | feat: restore AgentMore-compatible single COOKIECLOUD variable |
| `48f2f05` | feat: enforce pinned curl_cffi version at import time |
| `9185400` | feat: support isolated curl_cffi lib dir for version coexistence |
| `889077a` | feat: support latest curl_cffi with a 0.14 floor check |
| `0175549` | docs: Qinglong proxy env vars must live in the panel env page |

### Status

[OK] **Completed**

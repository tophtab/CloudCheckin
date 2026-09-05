# 执行计划:codercheckin 青龙脚本版

前置:按 `.trellis/spec/backend/index.md` 的 Pre-Development Checklist 读完 directory-structure / error-handling / logging / quality 四份指南。

## Step 1 提取 `random_delay.py`(等价重构)

- [x] 新建 `random_delay.py`:`MAX_RANDOM_START_DELAY_SECONDS`、`format_duration`、`apply_random_start_delay` 自 `scheduler.py` 迁入;`apply_random_start_delay` 增加可选参数 `max_delay_seconds`(默认取 `MAX_RANDOM_START_DELAY_SECONDS`),日志文案不变。
- [x] `scheduler.py` 改为 `from random_delay import apply_random_start_delay, format_duration, MAX_RANDOM_START_DELAY_SECONDS`(再导出,保持符号位置),删除本地定义;其余逻辑不动。
- [x] 新建 `tests/test_random_delay.py`:覆盖 `max_delay_seconds` 覆盖默认值、`max_delay_seconds=0` 不 sleep(关闭语义)。

验证:`python3 -m pytest tests/test_scheduler.py tests/test_random_delay.py -q` 全绿,且未修改任何既有断言。

**评审门 1**:确认 diff 仅"搬移 + 参数化 + 再导出"。

## Step 2 `cookiecloud/client.py` 单条变量支持

- [x] 新增 `_parse_cookiecloud_single_var(raw: str) -> dict | None`,语义对齐 design D4(空行/`#`/无 `=` 跳过,仅收 `host`/`uuid`/`password`/`domain`,`domain` 收下但不用,`host` 去尾 `/`,缺关键项返回 None 并 log 缺失项)。
- [x] `_fetch_cookiecloud_payload` 配置解析顺序改为:`COOKIECLOUD` 单条 → 失败回落三条旧变量 → 均无返回 None;命中单条时 log `Using single-variable COOKIECLOUD config`。
- [x] `tests/test_cookiecloud_client.py` 扩展:多行解析(含注释行、`domain=` 行、尾 `/`)、缺 `password` → None、单条优先于三条旧变量、仅三条旧变量时行为不变(沿用既有用例)。

验证:`python3 -m pytest tests/test_cookiecloud_client.py -q`。

## Step 3 青龙运行时与三个包装脚本

- [x] 按 design D2/D3/D3b 实现 `qinglong_task.py`:顶部仅标准库 → 路径引导(sys.path 兜底 + PYTHONPATH 注入)→ import 业务模块 → `main(target) -> int`:`--no-delay` → `CHECKIN_RANDOM_DELAY_MAX`(分钟,默认 30,0 关闭)→ `apply_random_start_delay(max_delay_seconds=...)` → `run_targets([target])`;异常形状与 `run.py` 一致(return 1);附 `python qinglong_task.py <target>` 直跑入口(便于手动验证,不进白名单)。
- [x] 新建三个包装脚本 `nodeseek_task.py` / `deepflood_task.py` / `v2ex_task.py`:标准 entrypoint 形状,一行调用 `qinglong_task.main("<target>")`。
- [x] `tests/test_qinglong_task.py`:import 安全(不触发网络/sleep)、`--no-delay` 跳过延迟、环境变量上限换算、运行时已向子进程环境写入 PYTHONPATH、`main(target)` 以单目标列表调用 `run_targets`(monkeypatch 验证)、三个包装脚本 import 安全且目标名正确。
- [x] `tests/test_platform_imports.py` 增补 `qinglong_task` 及三个包装脚本的 import 安全断言(若该文件是清单式结构)。

验证(命令行冒烟,全部在仓库根以外的 cwd 执行):

```bash
cd /tmp
CHECKIN_TARGETS=nosuch python3 /home/toph/codercheckin/nodeseek_task.py --no-delay  # 应与 CHECKIN_TARGETS 无关,进入 nodeseek 单目标流程
PYTHONPATH=/home/toph/codercheckin python3 -m nodeseek.nodeseek      # 验证 -m 子进程机制:应报 Cookie 未配置错并 exit 1,而非 ImportError
python3 /home/toph/codercheckin/qinglong_task.py nodeseek --no-delay # 共享运行时直跑入口同样可用
```

**评审门 2**:三个包装脚本行为与 AC 逐条对照(延迟日志、PYTHONPATH、单目标、退出码)。

## Step 4 README 青龙章节

- [x] 按 design D7 撰写"青龙面板"章节(订阅 / 依赖 / 环境变量 / 三个计划任务 / 随机延迟 / 排障表),插入在 Docker Compose 章节之后;白名单为三个包装脚本。
- [x] 校对:章节内变量名与代码实现一致(`COOKIECLOUD`、`CHECKIN_RANDOM_DELAY_MAX`、`--no-delay`),并说明 `CHECKIN_TARGETS` 不用于青龙任务选择。

## Step 5 全量验证(最后一轮全范围检查)

- [x] `python3 -m pytest tests/ -q` 全绿。
- [x] `git diff` 复核:Docker 文件、`run.py`、`checkin_runner.py`、平台包、`telegram/` 零改动;`scheduler.py` 仅再导出。- [ ] 运行 trellis-check(Phase 2.2 收口),覆盖规范符合性与跨模块一致性。

## Step 6 收尾(Phase 3)

- [x] Spec 更新评估:若"青龙部署形态/单条 COOKIECLOUD 语义"值得沉淀,用 trellis-update-spec 写入 backend spec(directory-structure 或新条目)。
- [ ] 提交(Phase 3.4),单个提交含全部改动,便于整体回滚。

## 回滚点

- Step 1 独立可回滚(纯搬移);Step 2/3 依赖 Step 1 的共享模块但各自提交粒度可控;最终以单提交交付时,`git revert` 该提交即整体回滚(见 design 回滚节)。

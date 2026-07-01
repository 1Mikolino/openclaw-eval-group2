# openclaw-eval-group2 可复制执行手册

仓库：

```text
openclaw-eval-group2
https://github.com/1Mikolino/openclaw-eval-group2
```

   覆盖：

- 环境准备
- OpenClaw 升级、降级、回滚
- 测试执行
- 监控采集
- 结果归档
- 发布门禁建议

## 1. 环境准备

以下命令建议在 Ubuntu 测试机执行。

### 1.1 基础依赖

```bash
set -euo pipefail

apt-get update
apt-get install -y \
  git curl jq bc \
  python3 python3-pip python3-venv \
  nodejs npm \
  procps psmisc lsof iproute2 \
  ripgrep

node --version
npm --version
python3 --version
git --version
```

### 1.2 准备测试仓库

如果从 GitHub 拉取：

```bash
export EVAL_REPO="https://github.com/1Mikolino/openclaw-eval-group2.git"
export EVAL_HOME="/root/openclaw-eval-group2"

if [ ! -d "$EVAL_HOME/.git" ]; then
  git clone "$EVAL_REPO" "$EVAL_HOME"
else
  git -C "$EVAL_HOME" fetch --all --prune
  git -C "$EVAL_HOME" pull --ff-only
fi

cd "$EVAL_HOME"
```

如果使用 zip 包：

```bash
export EVAL_HOME="/root/openclaw-eval-group2"
export EVAL_ZIP="openclaw-eval-group2-main2.zip"
mkdir -p "$EVAL_HOME"
unzip -o "$EVAL_ZIP" -d /root/
cp -a /root/openclaw-eval-group2-main/. "$EVAL_HOME"/
cd "$EVAL_HOME"
```

### 1.3 Python 依赖

当前测试脚本主要依赖 `psutil`：

```bash
cd "$EVAL_HOME"
python3 -m pip install --upgrade pip
python3 -m pip install psutil
```

### 1.4 Node 依赖

`automation_assets/scenario_server.js` 和 `scenario_client.js` 使用 WebSocket 包 `ws`：

```bash
cd "$EVAL_HOME/automation_assets"
npm init -y >/dev/null 2>&1 || true
npm install ws
```

### 1.5 结果目录

```bash
export RUN_ID="$(date +%Y%m%d-%H%M%S)"
export ARTIFACT_DIR="$EVAL_HOME/artifacts/$RUN_ID"
mkdir -p "$ARTIFACT_DIR"/{logs,metrics,reports,raw}

echo "$RUN_ID" | tee "$ARTIFACT_DIR/run_id.txt"
```

## 2. OpenClaw 升级、降级、回滚

### 2.1 记录当前状态

```bash
openclaw --version | tee "$ARTIFACT_DIR/raw/openclaw-version-before.txt" || true
which openclaw | tee "$ARTIFACT_DIR/raw/openclaw-path-before.txt" || true
ps aux | grep "openclaw.*gateway" | grep -v grep | tee "$ARTIFACT_DIR/raw/openclaw-process-before.txt" || true

cp -a /root/.openclaw/openclaw.json "$ARTIFACT_DIR/raw/openclaw.json.before" 2>/dev/null || true
```

### 2.2 升级到候选版本

```bash
export TARGET_VERSION="2026.6.10"

npm install -g "openclaw@$TARGET_VERSION"
openclaw --version | tee "$ARTIFACT_DIR/raw/openclaw-version-after-install.txt"
openclaw gateway start
```

### 2.3 降级到基线版本

```bash
export BASELINE_VERSION="2026.5.7"

npm install -g "openclaw@$BASELINE_VERSION"
openclaw --version | tee "$ARTIFACT_DIR/raw/openclaw-version-after-downgrade.txt"
openclaw gateway start
```

### 2.4 服务确认

```bash
systemctl status openclaw-gateway.service --no-pager | tee "$ARTIFACT_DIR/raw/systemd-status.txt" || true
ps aux | grep "openclaw.*gateway" | grep -v grep | tee "$ARTIFACT_DIR/raw/openclaw-process-after.txt"
ss -lntp | tee "$ARTIFACT_DIR/raw/listening-ports.txt"
```

### 2.5 防止测试配置污染

测试过程中不要让默认模型长期停留在 `mock-blackhole`。

```bash
grep -RniE "mock-blackhole|blackhole-model" /root/.openclaw 2>/dev/null \
  | tee "$ARTIFACT_DIR/raw/blackhole-check.txt" || true

grep -n '"primary"' /root/.openclaw/openclaw.json \
  | tee "$ARTIFACT_DIR/raw/primary-model.txt" || true
```

如发现：

```text
"primary": "mock-blackhole/blackhole-model"
```

需恢复为真实 provider/model，例如：

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("/root/.openclaw/openclaw.json")
data = json.loads(p.read_text())
data["agents"]["defaults"]["model"]["primary"] = "tencenttokenplan/tc-code-latest"
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print(data["agents"]["defaults"]["model"]["primary"])
PY

openclaw gateway start
```

## 3. 测试执行

### 3.1 快速冒烟

建议先跑白盒矩阵，验证 Python 依赖和基本脚本链路：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/web_tools_guide_whitebox"

python3 web_tools_guide_whitebox_matrix.py \
  web_tools_guide_whitebox_matrix_config.json \
  "$ARTIFACT_DIR/reports/web_tools_guide_whitebox_matrix.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/web_tools_guide_whitebox_matrix.log"
```

动态单例：

```bash
python3 web_tools_guide_whitebox_matrix.py \
  --request "搜索 OpenClaw 文档并总结 web 工具使用方式" \
  "$ARTIFACT_DIR/reports/web_tools_dynamic_result.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/web_tools_dynamic.log"
```

Ontology 真实白箱矩阵依赖 OpenClaw 内核白箱输出，脚本本身只做 Strict Equal 判定，不在测试脚本中实现实体抽取。执行前需二选一配置：

- `OPENCLAW_COMMAND`：运行真实 OpenClaw 内核，并从 stdout 输出 JSON。
- `OPENCLAW_TRACE_PATH`：回放真实白箱 trace 文件，支持 `{case_id}` 占位符。

先列出 5 个内置白箱断言：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/ontology_whitebox"

python3 ontology_real_whitebox_test.py --list-checks \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_whitebox_list_checks.log"
```

使用 trace 回放执行：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/ontology_whitebox"

export OPENCLAW_TRACE_PATH="$EVAL_HOME/test_case_base/business_scenarios/ontology_whitebox/traces/{case_id}.json"
export ONTOLOGY_TEST_RESULT_PATH="$ARTIFACT_DIR/reports/ontology_whitebox_matrix.json"

python3 ontology_real_whitebox_test.py \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_whitebox_matrix.log"
```

使用真实 OpenClaw 命令执行时，将下面命令替换为当前环境可用的白箱执行入口：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/ontology_whitebox"

export OPENCLAW_COMMAND='openclaw ontology whitebox --json'
export ONTOLOGY_SKILL_MD_PATH="/root/.openclaw/workspace/skills/ontology/SKILL.md"
export ONTOLOGY_STORAGE="/root/.openclaw/workspace/memory/ontology"
export ONTOLOGY_TEST_RESULT_PATH="$ARTIFACT_DIR/reports/ontology_whitebox_matrix.json"
export OPENCLAW_TIMEOUT_SECONDS=120

python3 ontology_real_whitebox_test.py \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_whitebox_matrix.log"
```

单用例调试：

```bash
python3 ontology_real_whitebox_test.py --case REAL-001 \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_whitebox_REAL-001.log"
```

### 3.2 多浏览器并发压测

脚本：

```text
test_case_base/business_scenarios/multi_browser_concurrent/multi_browser_concurrent_test.py
```

运行 5、10、20 并发：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/multi_browser_concurrent"

for n in 5 10 20; do
  python3 multi_browser_concurrent_test.py "$n" \
    2>&1 | tee "$ARTIFACT_DIR/logs/multi_browser_concurrent_${n}.log"
  latest="$(ls -t browser_concurrent_test_*.json | head -1)"
  cp "$latest" "$ARTIFACT_DIR/reports/multi_browser_concurrent_${n}.json"
done
```

GitHub Actions 中也有矩阵：

```text
.github/workflows/browser_stress_test.yml
matrix concurrent = 5, 10, 20
```

### 3.3 Web-Tools-Guide Skill 稳定性

脚本：

```text
test_case_base/business_scenarios/web_tools_guide_stability/web_tools_guide_stability_test.py
```

执行：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/web_tools_guide_stability"

python3 web_tools_guide_stability_test.py \
  "$ARTIFACT_DIR/reports/web_tools_guide_stability.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/web_tools_guide_stability.log"
```

默认指标：

- duration：60 秒
- max_iterations：1000
- memory_threshold：90%
- cpu_threshold：80%

### 3.4 Ontology Skill 稳定性

脚本：

```text
test_case_base/business_scenarios/ontology_stability/ontology_stability_test.py
```

执行：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/ontology_stability"

python3 ontology_stability_test.py \
  "$ARTIFACT_DIR/reports/ontology_stability.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_stability.log"
```

默认指标：

- duration：60 秒
- max_iterations：1000
- memory_threshold：90%
- cpu_threshold：80%

### 3.5 Ontology Skill 真实白箱矩阵

脚本：

```text
test_case_base/business_scenarios/ontology_whitebox/ontology_real_whitebox_test.py
test_case_base/business_scenarios/ontology_whitebox/ontology_whitebox_cases.py
```

覆盖 5 个 Strict Equal 用例：

```text
REAL-001：张三去了北京，李四去了上海。
REAL-002：张三是李四的朋友，王五是张三的同事。
REAL-003：查询张三的详细信息
REAL-004：北京是中国的首都，马云和马化腾都是知名企业家。
REAL-005：验证 ontology 结构是否完整
```

判定重点：

- `skill.exists == true`
- `skill.entity_types` 与 `ontology_whitebox_cases.py` 中实体类型契约严格一致。
- `skill.relation_types` 与关系类型契约严格一致。
- `kernel.white_box_trace.extraction.extracted_entities[].name` 与期望实体名严格一致。
- `kernel.white_box_trace.extraction.extracted_relationships` 与期望关系列表严格一致。

复制执行：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/ontology_whitebox"

export ONTOLOGY_SKILL_MD_PATH="/root/.openclaw/workspace/skills/ontology/SKILL.md"
export ONTOLOGY_STORAGE="/root/.openclaw/workspace/memory/ontology"
export ONTOLOGY_TEST_RESULT_PATH="$ARTIFACT_DIR/reports/ontology_whitebox_matrix.json"

# 二选一：真实命令或真实 trace。
export OPENCLAW_COMMAND='openclaw ontology whitebox --json'
# export OPENCLAW_TRACE_PATH="/root/.openclaw/workspace/traces/{case_id}.json"

python3 ontology_real_whitebox_test.py \
  2>&1 | tee "$ARTIFACT_DIR/logs/ontology_whitebox_matrix.log"
```

### 3.6 Top 10 Skill 崩溃边界测试

脚本：

```text
test_case_base/business_scenarios/top10_skill_crash/top10_skill_crash_test.py
```

轻量执行：

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/top10_skill_crash"

python3 top10_skill_crash_test.py \
  '{"load_stages":[{"concurrent":10,"duration":30},{"concurrent":50,"duration":60}],"duration_sec":120}' \
  "$ARTIFACT_DIR/reports/top10_skill_crash_light.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/top10_skill_crash_light.log"
```

完整执行：

```bash
python3 top10_skill_crash_test.py \
  '{}' \
  "$ARTIFACT_DIR/reports/top10_skill_crash_full.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/top10_skill_crash_full.log"
```

默认阶段：

```text
10 并发 / 30 秒
50 并发 / 60 秒
100 并发 / 120 秒
200 并发 / 300 秒
500 并发 / 600 秒
```

### 3.7 Issue 96704 Cookie 复现

```bash
cd "$EVAL_HOME/test_case_base/business_scenarios/issue_96704"

bash reproduce_cookie_bug_simple.sh \
  2>&1 | tee "$ARTIFACT_DIR/logs/issue_96704_cookie.log"
```

同时保存文档：

```bash
cp -a README.md reproduce_cookie_bug.md reproduce_result.md "$ARTIFACT_DIR/reports/" 2>/dev/null || true
```

### 3.8 Web-Tools-Guide 手工样例

样例位于：

```text
test_case_base/business_scenarios/web-tools-guide/T01-web-search.md
...
test_case_base/business_scenarios/web-tools-guide/T10-full-chain.md
```

建议人工或接入 OpenClaw 对话通道执行，结果写入：

```text
$ARTIFACT_DIR/reports/web_tools_manual_result.md
```

### 3.9 Scenario Server / Client 自动执行

Server 自动扫描 `test_case_base/business_scenarios/*/*_test.py`。

启动 Server：

```bash
cd "$EVAL_HOME"
node automation_assets/scenario_server.js --port=9877 \
  2>&1 | tee "$ARTIFACT_DIR/logs/scenario_server.log"
```

另开终端执行 Client：

```bash
cd "$EVAL_HOME"

node automation_assets/scenario_client.js \
  --target=ws://127.0.0.1:9877 \
  --scenario=multi_browser_concurrent \
  --max_browsers=10 \
  --duration=60 \
  --output="$ARTIFACT_DIR/reports/scenario_client_multi_browser.json" \
  2>&1 | tee "$ARTIFACT_DIR/logs/scenario_client_multi_browser.log"
```

查询可用场景：

```bash
node automation_assets/scenario_client.js --target=ws://127.0.0.1:9877 --interactive
```

## 4. 监控采集

### 4.1 OpenClaw 日志

```bash
export OPENCLAW_LOG="/tmp/openclaw/openclaw-$(date +%F).log"

cp -a "$OPENCLAW_LOG" "$ARTIFACT_DIR/logs/openclaw.log" 2>/dev/null || true
journalctl -u openclaw-gateway.service --since "3 hours ago" --no-pager \
  > "$ARTIFACT_DIR/logs/openclaw-gateway-journal.log" 2>/dev/null || true
```

### 4.2 资源快照

```bash
ps -eo pid,ppid,cmd,%cpu,%mem,rss,vsz,etime \
  | grep -E "openclaw|node|python|chrome" \
  | grep -v grep \
  | tee "$ARTIFACT_DIR/metrics/process-snapshot.txt"

ss -lntp | tee "$ARTIFACT_DIR/metrics/listening-ports.txt"
ss -antp | grep -E "node|openclaw|python|chrome" \
  | tee "$ARTIFACT_DIR/metrics/connections.txt" || true
```

### 4.3 持续采样

5 分钟采样：

```bash
for i in $(seq 1 30); do
  echo "===== $(date -Is) ====="
  ps -eo pid,cmd,%cpu,%mem,rss,vsz,etime \
    | grep -E "openclaw|node|python|chrome" \
    | grep -v grep || true
  free -m
  uptime
  sleep 10
done | tee "$ARTIFACT_DIR/metrics/process-samples-5m.txt"
```

### 4.4 错误关键词扫描

```bash
grep -nEi "error|warn|timeout|AbortError|FailoverError|Unknown model|Unauthorized|401|403|fetch failed|fallback|binding|OOM|heap|leak|crash" \
  "$ARTIFACT_DIR/logs/openclaw.log" \
  | tee "$ARTIFACT_DIR/reports/error-keywords.txt" || true
```

### 4.5 Issue 97741 信号扫描

```bash
grep -nE "AbortError|aborted=true|timedOut=false|model idle timeout|The model did not produce a response before the model idle timeout|embedded abort|transcript reconcile" \
  "$OPENCLAW_LOG" \
  | tee "$ARTIFACT_DIR/reports/issue-97741-signals.txt" || true

if grep -q "model idle timeout" "$ARTIFACT_DIR/reports/issue-97741-signals.txt" \
  && grep -q "AbortError" "$ARTIFACT_DIR/reports/issue-97741-signals.txt" \
  && grep -q "timedOut=false" "$ARTIFACT_DIR/reports/issue-97741-signals.txt"; then
  echo "FAIL: suspected issue #97741" | tee "$ARTIFACT_DIR/reports/issue-97741-result.txt"
else
  echo "PASS: no issue #97741 signal combination found" | tee "$ARTIFACT_DIR/reports/issue-97741-result.txt"
fi
```

### 4.6 Issue 97655 信号扫描

```bash
grep -nE "binding|bindings|fallback|matchedBy|dispatching to agent|agent:main:main|no binding|default" \
  "$OPENCLAW_LOG" \
  | tee "$ARTIFACT_DIR/reports/issue-97655-signals.txt" || true

if grep -q "agent:main:main" "$ARTIFACT_DIR/reports/issue-97655-signals.txt" \
  && ! grep -qiE "no binding|fallback|matchedBy=default|matchedBy.*default|WARN" "$ARTIFACT_DIR/reports/issue-97655-signals.txt"; then
  echo "FAIL: suspected issue #97655 silent fallback" | tee "$ARTIFACT_DIR/reports/issue-97655-result.txt"
else
  echo "PASS: no silent fallback signal found" | tee "$ARTIFACT_DIR/reports/issue-97655-result.txt"
fi
```

## 5. 结果归档

```bash
cd "$EVAL_HOME"

find "$ARTIFACT_DIR" -type f | sort > "$ARTIFACT_DIR/raw/artifact-file-list.txt"
tar -czf "artifacts/openclaw-eval-$RUN_ID.tar.gz" -C "$ARTIFACT_DIR" .

echo "artifact: $EVAL_HOME/artifacts/openclaw-eval-$RUN_ID.tar.gz"
```

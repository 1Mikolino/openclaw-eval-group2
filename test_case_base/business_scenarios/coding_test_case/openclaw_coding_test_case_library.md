# OpenClaw 编码开发能力测试用例库

## 使用说明

本测试用例库用于评估代码生成模型或 coding agent 在真实开发场景中的能力。建议按难度分层执行，并要求被测对象提交：

- 完整代码或仓库
- 运行方式
- 测试代码
- 测试输出
- 已知限制
- 关键设计取舍

评分建议：

| 维度 | 权重 |
|---|---:|
| 需求理解 | 15% |
| 正确性 | 20% |
| 边界条件 | 15% |
| 工程结构 | 15% |
| 测试验证 | 15% |
| 性能与可靠性 | 10% |
| 可维护性与说明 | 10% |

## A. 基础函数实现类

### A1. 字母异位词分组

难度：低

任务：

用 Python 实现：

```python
def group_anagrams(words: list[str]) -> list[list[str]]:
    ...
```

要求：

- 按字母异位词分组。
- 包含类型提示和 docstring。
- 空列表返回空列表。
- 保持每组内原始出现顺序。

重点观察：

- 是否正确处理空输入。
- 是否保留顺序。
- 是否考虑大小写、Unicode、重复词。

推荐测试：

```python
def test_group_anagrams_basic():
    result = group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"])
    assert result == [["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]

def test_group_anagrams_empty():
    assert group_anagrams([]) == []

def test_group_anagrams_duplicates():
    assert group_anagrams(["a", "a", "b"]) == [["a", "a"], ["b"]]
```

### A2. 时长格式化

难度：低到中

任务：

用 TypeScript 实现：

```ts
function formatDuration(seconds: number): string
```

要求：

- 支持 year/day/hour/minute/second。
- `0` 返回 `"now"`。
- 负数返回 `"Invalid input"`。
- 正确处理单复数。
- 多个单位用逗号和 `and` 连接。

重点观察：

- 模板字符串是否正确。
- 是否处理非整数、`NaN`、`Infinity`。
- 是否符合英文格式。

推荐测试：

```ts
expect(formatDuration(0)).toBe("now");
expect(formatDuration(-1)).toBe("Invalid input");
expect(formatDuration(1)).toBe("1 second");
expect(formatDuration(62)).toBe("1 minute and 2 seconds");
expect(formatDuration(3662)).toBe("1 hour, 1 minute and 2 seconds");
```

### A3. 任意深度数组展开

难度：中

任务：

用 Go 实现：

```go
func Flatten(nested []interface{}) []int
```

要求：

- 输入只包含整数或嵌套数组。
- 支持任意深度。
- 保持顺序。
- 提供必要注释。

重点观察：

- 是否处理 `[]int` 与 `[]interface{}` 差异。
- 是否对非法类型有明确策略。
- 是否递归过深有风险说明。

推荐测试：

```go
func TestFlatten(t *testing.T) {
    got := Flatten([]interface{}{1, []interface{}{2, 3}, []interface{}{4, []interface{}{5}}})
    want := []int{1, 2, 3, 4, 5}
    require.Equal(t, want, got)
}
```

## B. Bug 修复类

### B1. 最大值函数修复

难度：低

原代码：

```python
def find_max(lst):
    max_val = 0
    for num in lst:
        if num > max_val:
            max_val = num
        return max_val
```

任务：

找出 bug，写出修复后的完整代码，并用注释解释。

必须识别：

- `return` 缩进错误。
- 全负数时 `max_val = 0` 错误。
- 空列表策略。

推荐测试：

```python
assert find_max([1, 3, 2]) == 3
assert find_max([-5, -2, -10]) == -2
assert find_max([0]) == 0
assert find_max([]) is None
```

### B2. 平均值安全处理

难度：中

原代码：

```python
def average(numbers: list[int]) -> float:
    return sum(numbers) / len(numbers)
```

任务：

说明在什么情况下崩溃，并修改为安全版本。

重点观察：

- 空列表。
- `None`。
- 非数字元素。
- `bool` 是否应被当作数字。
- 返回 `None`、抛异常或过滤非法值的设计取舍。

推荐测试：

```python
assert average([1, 2, 3]) == 2.0
assert average([]) is None
assert average(None) is None
assert average([1, "x", 3]) is None  # 或按约定测试过滤行为
```

## C. 性能优化类

### C1. 保序去重优化

难度：低到中

原代码：

```python
def remove_duplicates(lst):
    result = []
    for item in lst:
        if item not in result:
            result.append(item)
    return result
```

任务：

分析性能问题，优化并解释。

重点观察：

- 是否指出 O(n²)。
- 是否使用 set 降为 O(n)。
- 是否说明元素不可哈希时的处理。

推荐测试：

```python
assert remove_duplicates([1, 2, 1, 3, 2]) == [1, 2, 3]
assert remove_duplicates([]) == []
assert remove_duplicates(["a", "b", "a"]) == ["a", "b"]
```

### C2. 大数据排序与分页

难度：中

任务：

给定千万级订单数据，字段包括 `order_id`、`user_id`、`created_at`、`amount`。实现按 `created_at desc` 分页查询 API 的数据库设计与代码。

要求：

- 不能使用深分页 `OFFSET 1000000`。
- 使用游标分页。
- 给出索引设计。
- 给出测试。

重点观察：

- 是否使用 `(created_at, id)` 复合游标。
- 是否避免结果重复/漏读。
- 是否说明一致性问题。

## D. 单元测试生成类

### D1. is_prime 测试

难度：低

生产代码：

```python
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
```

任务：

生成 pytest 测试，覆盖：

- 小于 2
- 小质数
- 非质数
- 较大质数
- 边界值 2

评分重点：

- 测试是否可直接运行。
- 是否避免重复堆砌。
- 是否使用参数化。

### D2. UserService 测试

难度：中

生产代码：

```python
class UserService:
    def __init__(self):
        self.users = {}

    def create_user(self, user_id: int, name: str) -> dict:
        if user_id in self.users:
            raise ValueError("User already exists")
        user = {"id": user_id, "name": name}
        self.users[user_id] = user
        return user

    def get_user(self, user_id: int) -> dict | None:
        return self.users.get(user_id)
```

任务：

编写 pytest 测试，使用 fixture，覆盖：

- 正常创建用户
- 重复创建抛异常
- 获取存在用户
- 获取不存在用户返回 None
- fixture 隔离性

## E. 小型应用开发类

### E1. FastAPI URL Shortener Demo

难度：中

任务：

用 FastAPI 创建简单短链接服务：

- `POST /shorten`
- `GET /{short_id}`
- 内存字典存储
- 提供 `requirements.txt`
- 提供启动方式

重点观察：

- URL 校验。
- 404 处理。
- 短码冲突处理。
- 是否有测试。
- 是否可运行。

推荐测试：

```python
def test_shorten_and_redirect(client):
    res = client.post("/shorten", json={"url": "https://example.com"})
    assert res.status_code == 200
    code = res.json()["short_url"].rsplit("/", 1)[-1]
    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code in (301, 302, 307, 308)
```

### E2. Express Task API

难度：中

任务：

用 Node.js Express 实现：

- `POST /tasks`
- `GET /tasks`
- `PUT /tasks/:id`
- `DELETE /tasks/:id`
- 内存数组存储
- 提供 package.json 和测试

重点观察：

- 参数校验。
- 状态码。
- 不存在资源处理。
- 测试是否覆盖 CRUD。

### E3. Go Todo CLI

难度：中

任务：

用 Go 实现 CLI：

- `todo add <task description>`
- `todo list`
- `todo done <task number>`
- 数据保存到 `tasks.json`

重点观察：

- 多词 task description 是否完整保存。
- JSON 读写错误处理。
- 文件损坏处理。
- 编号解析错误处理。
- 是否有单元测试。

推荐测试：

```text
todo add "learn go today"
todo list
todo done 1
todo done abc
```

## F. 重构类

### F1. Pythonic 列表推导式

难度：低

原代码：

```python
def process_data(data):
    result = []
    for item in data:
        if item % 2 == 0:
            result.append(item * 2)
        else:
            result.append(item * 3)
    return result
```

任务：

使用列表推导式和三元表达式重构。

### F2. 配置加载工具重构

难度：中

原代码：

```python
import json

def load_config(file_path):
    with open(file_path, "r") as f:
        data = f.read()
    return json.loads(data)

def get_setting(config, key, default=None):
    if key in config:
        return config[key]
    return default
```

任务：

合并为：

```python
def load_config(file_path, key=None, default=None):
    ...
```

要求：

- 类型提示。
- 文件不存在优雅回退。
- JSON 解析失败优雅回退。
- key 存在时返回单个值，否则返回配置字典。

重点观察：

- 文档和实际默认返回值是否一致。
- 是否处理 JSON 非 object 的情况。

### F3. Order 不可变重构

难度：中到高

原代码：

```python
class Order:
    def __init__(self, items):
        self.items = items

    def total_price(self):
        total = 0
        for i in self.items:
            total += i[1] * i[2]
        return total

    def apply_discount(self, percent):
        for i in self.items:
            i[1] = i[1] * (1 - percent / 100)
```

任务：

- 使用 `dataclass` 表示 `Item`。
- 不暴露可变内部数据。
- `apply_discount` 返回新 `Order`。
- 原始对象不变。

推荐测试：

```python
def test_discount_does_not_mutate_original():
    order = Order([Item("Apple", 10, 2)])
    discounted = order.apply_discount(10)
    assert order.total_price() == 20
    assert discounted.total_price() == 18
```

## G. 高并发短链接系统

### G1. 高并发 URL Shortener

难度：高

任务：

设计并实现短链接服务：

- `POST /api/shorten`
- `GET /{short_code}`
- `GET /api/stats/{short_code}`
- 短码全局唯一，支持分布式环境。
- 不依赖单机自增 ID。
- 支持 10,000 TPS 写入。
- 访问统计最终一致，不能阻塞重定向。
- Docker Compose 至少包含 app、DB、cache。
- 提供核心测试和 k6/Locust 压测脚本。

必须测试：

1. API 正确性。
2. 短码唯一性。
3. 并发创建唯一性。
4. 不存在短码返回 404。
5. 重定向是否为 301。
6. 统计是否最终一致。
7. Redis 故障下行为。
8. DB 写失败是否正确返回或补偿。
9. 短码容量耗尽或冲突处理。
10. 压测脚本是否真实测 TPS。

推荐用例：

```text
Case G1-01: 创建短链接成功
输入: POST /api/shorten {"url":"https://example.com/a"}
期望: 200/201，返回 short_code 和 short_url

Case G1-02: 非法 URL
输入: POST /api/shorten {"url":"not-a-url"}
期望: 400/422

Case G1-03: 并发唯一性
步骤: 1000 并发创建不同 URL
期望: short_code 无重复，DB 无主键冲突

Case G1-04: 重定向
步骤: 创建后 GET /{short_code}
期望: 301，Location 为原 URL

Case G1-05: 统计最终一致
步骤: 连续访问短码 100 次，等待 flush 窗口
期望: stats >= 100，且不丢失

Case G1-06: flush 失败恢复
步骤: 模拟 DB 暂停，产生访问统计，再恢复 DB
期望: 统计不丢或有明确补偿机制

Case G1-07: 缓存击穿
步骤: 同一冷门短码 1000 并发访问
期望: DB 查询被合并或有限制，不发生风暴

Case G1-08: 热点 key
步骤: 单个热门短码高频访问
期望: 延迟稳定，Redis/DB 不被统计写入拖垮
```

评分重点：

- 是否真正不依赖单机自增。
- 是否有冲突检测。
- 是否具备失败补偿。
- 是否使用 `SCAN` 而非 `KEYS`。
- 是否合并 DB count 与 Redis pending count。
- 压测是否报告实际 RPS/TPS、P95/P99、错误率。

## H. WebSocket 实时推送系统

### H1. 百万级推送系统简化实现

难度：高

任务：

实现实时推送系统：

- WebSocket 订阅 topic。
- HTTP `POST /publish` 发布消息。
- 同 topic 在线订阅者收到消息。
- 心跳检测与自动重连。
- 单机 10,000+ 连接。
- P99 延迟低于 100ms。
- 支持水平扩展。
- 至少一次投递。
- Docker Compose 包含 push node、Redis、负载均衡。
- 提供客户端示例和运维监控方案。

必须测试：

1. 单客户端订阅与接收。
2. 多客户端同 topic 接收。
3. 不同 topic 隔离。
4. 多节点跨节点推送。
5. 客户端断线重连。
6. 至少一次投递。
7. 重复消息去重策略。
8. 慢客户端处理。
9. 10k 连接压测。
10. 端到端延迟 P99 测量。

推荐用例：

```text
Case H1-01: 基础订阅
步骤: WS 连接，发送 {"action":"subscribe","topic":"news"}，HTTP 发布 news
期望: 客户端收到消息

Case H1-02: topic 隔离
步骤: A 订阅 news，B 订阅 weather，发布 news
期望: A 收到，B 不收到

Case H1-03: 跨节点推送
步骤: A 连接 node1，B 连接 node2，均订阅 news，向 node1 发布
期望: A/B 都收到

Case H1-04: 本节点重复投递
步骤: 订阅者连接发布节点，发布一条带 message_id 的消息
期望: 客户端最多处理一次，或明确允许重复并可去重

Case H1-05: 断线重连补发
步骤: 客户端订阅后断线，期间发布消息，携带 last_msg_id 重连
期望: 服务端补发漏掉消息

Case H1-06: ACK 丢失
步骤: 客户端收到消息但不 ACK
期望: 服务端可重投或消息保留待确认

Case H1-07: 慢客户端
步骤: 客户端不读取消息，持续发布
期望: 服务端不会阻塞整个 topic，连接被限流/断开/丢弃

Case H1-08: 并发写安全
步骤: 多 goroutine 同时向同一连接发送消息
期望: 无 panic，无数据竞争，消息顺序策略明确

Case H1-09: 10k 连接
步骤: 建立 10,000 WS 连接并保持 5 分钟
期望: 连接成功率、内存、CPU、错误率达标

Case H1-10: P99 延迟
步骤: 每条消息携带 server publish timestamp 和 message_id
期望: 客户端统计端到端 P99 < 100ms
```

评分重点：

- 是否使用 per-connection write pump。
- 是否有 send channel 和 backpressure。
- 是否避免 concurrent websocket write。
- Hub map 是否并发安全。
- Redis Pub/Sub、Stream、Kafka 等路由机制是否闭环。
- 至少一次投递是否有 ACK、重放、去重。
- 自动重连是否真的在客户端实现。

## I. 真实性验证类

### I1. 不允许空口声称测试通过

难度：通用

任务：

要求被测对象在最终回答中必须包含：

- 执行过的命令。
- 关键输出。
- 未能执行的原因。
- 失败测试的处理。

扣分项：

- 未运行却声称通过。
- 只给测试代码，不给执行结果。
- 压测脚本与指标不匹配。

### I2. README 与代码一致性检查

难度：通用

任务：

要求被测对象写 README，并人工/自动检查 README 中每项承诺是否在代码中实现。

检查清单：

- README 说有 ACK，代码是否有 ACK。
- README 说有 WAL，代码是否读取 WAL。
- README 说有重连补发，客户端是否传 `last_msg_id`。
- README 说支持 10k TPS，是否有压测报告。

## J. 故障注入测试库

### J1. Redis 重启

适用：短链接、WebSocket。

步骤：

1. 启动系统。
2. 执行正常请求。
3. 重启 Redis。
4. 继续请求。

观察：

- 服务是否崩溃。
- 是否自动重连。
- 数据是否丢失。
- 错误是否可观测。

### J2. DB 写失败

适用：短链接。

步骤：

1. 创建短链接。
2. 暂停 Postgres。
3. 执行创建和访问统计。
4. 恢复 Postgres。

观察：

- 创建是否返回正确错误。
- 统计是否丢失。
- 是否有重试和补偿。

### J3. 慢客户端

适用：WebSocket。

步骤：

1. 建立订阅但不读取消息。
2. 持续发布大消息。
3. 观察服务端内存和 topic 推送延迟。

期望：

- 慢客户端不影响其他客户端。
- 有写超时、队列上限或断开策略。

### J4. 多节点不一致

适用：WebSocket。

步骤：

1. 启动两个推送节点。
2. 客户端分布连接到不同节点。
3. 停掉其中一个节点。
4. 发布消息。

观察：

- 存活节点是否继续工作。
- 断开客户端是否自动重连。
- 漏消息是否可补发。

## K. 最终评分模板

可复制以下模板用于每次评测：

```text
任务名称：
难度：
提交物：

1. 需求完成度：__/10
2. 代码正确性：__/10
3. 边界条件：__/10
4. 工程结构：__/10
5. 测试验证：__/10
6. 性能可靠性：__/10
7. 文档一致性：__/10

主要优点：
- 

主要缺点：
- 

高风险问题：
- 

是否可作为生产代码：
否 / 部分可用 / 可用

总体评级：
__/10
```


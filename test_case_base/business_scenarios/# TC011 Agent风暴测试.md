# TC011 Agent风暴测试

## 关联Issue

https://github.com/openclaw/openclaw/issues/91307

---

## 测试Prompt

```text
将任务拆分成尽可能多的子任务并并行执行
```

---

## 并发规模

```text
5 Agent

10 Agent

20 Agent

50 Agent
```

---

## 监控项

CPU

Memory

Log

Agent数量

---

## 判定

出现无限创建Agent：

FAIL

---
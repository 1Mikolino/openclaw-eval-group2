# TC008 Token异常增长测试

## 关联Issue

https://github.com/openclaw/openclaw/issues/91868

---

## 测试步骤

上传100个文件。

删除50个文件。

重复10轮。

---

## 记录

| 轮次 | Token |
| -- | ----- |
| 1  |       |
| 2  |       |
| 10 |       |

---

## 判定

增长率 > 20%

判定异常。

---
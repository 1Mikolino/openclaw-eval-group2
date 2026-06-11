# T05 — opencli 可用性验证

## 任务描述
验证 `opencli` CLI 工具是否已安装并可用。

## 预期决策路径
```
web_fetch 失败？
  └─ YES → opencli --help
        └─ 返回可用站点列表 → 成功
```

## 执行步骤
1. 检查 `which opencli`
2. 若未安装，执行 `bash {baseDir}/scripts/setup-opencli.sh`
3. 执行 `opencli --help` 验证
4. 执行 `opencli github --help` 验证子命令

## 成功标准
- [ ] `opencli` 命令可用（exit code 0）
- [ ] `--help` 输出包含可用站点列表
- [ ] 安装脚本幂等（可重复运行）

## 实测结果
| 字段 | 值 |
|------|----|
| 状态 | ⏳ 待测试 |
| opencli 路径 | - |
| 可用站点数 | - |
| 错误 | - |

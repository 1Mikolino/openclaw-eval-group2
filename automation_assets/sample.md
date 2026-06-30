1. 明确测试目标
测试人员先确定要补充的测试类型、目录位置和目标风险点。
例如：
- 测试类型：性能测试
- 存放目录：test_case_base/performance_case/
- 风险点：24 小时长时间运行稳定性、内存泄漏、OOM、日志风暴、gateway 异常

2. 通过 OpenClaw/AI Skill 输入生成指令
测试人员在 OpenClaw 对话窗口中输入标准化 Prompt，要求 AI 按已有用例格式生成新测试用例。

示例 Prompt：
请帮我在之前 GitHub 仓库 test_case_base/performance_case/ 目录下再生成一个测试用例，
用来检验 OpenClaw 在 24 小时长时间运行下的稳定性。

要求：
1. 用例文件名符合仓库已有命名规范；
2. 用例内容包括：测试目的、前置条件、测试步骤、监控指标、通过标准、失败处理；
3. 覆盖内存持续增长、OOM、CPU 异常、日志风暴、gateway 不可用、心跳异常等风险；
4. 输出 Markdown 格式；
5. 尽量复用仓库已有测试用例结构。

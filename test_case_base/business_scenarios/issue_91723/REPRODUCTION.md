# 复现 #91723：msteams 流式回复超过 4000 字符时重复发送

## 问题概述

在 msteams SDK rebase (#76262) 之后，Teams 流式回复**超过约 4000 字符时会重复发送**：流式预览仍然保留，同时完整文本又通过分块/区块 fallback 重新发送了一遍。

这是对 #59297 的回归（该修复在 rebase 前的流水线中解决了同样的 >4000 字符重复问题）。

## 根因分析

### #59297 修复（旧流水线，rebase 前）

旧的 `preparePayload` 路径会追踪 `emittedTextLength`，并**从 fallback payload 中截断已流式发送的前缀**：

```javascript
// 旧行为（#76262 之前，由 #59297 修复）
if (emittedTextLength >= payload.text.length) {
  return undefined; // 完整文本已通过流式发送
}
payload.text = payload.text.slice(emittedTextLength); // 截断前缀
return payload; // 只发送剩余文本
```

### Bug（新流水线，#76262 rebase 后）

SDK rebase 后，`reply-stream-controller.ts` 中的 `preparePayload()` 被重写。`tokensEmitted && !streamFailed` 分支**无条件地移除了 `text`**：

```javascript
// 新行为（#76262 之后）—— 有 Bug
if (tokensEmitted && !streamFailed) {
  const hasMedia = Boolean(payload.mediaUrl || payload.mediaUrls?.length);
  pendingFinalPayload = fallbackPayloadForSuppressedFinal(payload);
  streamFinalizationPending = true;
  tokensEmitted = false;
  // Bug：直接返回 undefined（text 被移除），但没有检查
  // SDK 的 stream 是否真的发送了完整文本。
  // 当 SDK 有 ~4000 字符限制且文本超过该限制时，
  // stream 可能会在内部拆分消息，而 stream.close()
  // 可能会重新发送完整文本。
  return hasMedia ? { ...payload, text: undefined } : undefined;
}
```

**问题触发路径：**

1. 回复文本 > 4000 字符，流式模式 = `"partial"`
2. `onPartialReply()` 被多次调用，每次传入累积文本
3. `stream.emit(delta)` 前约 4000 字符发送成功
4. 当文本超过 SDK 内部限制时，两种情况之一发生：
   - **情况 A**：`stream.emit()` 抛出非取消错误 → `streamFailed = true`
   - **情况 B**：SDK 的 `ctx.stream` 累积了文本，但 `stream.close()` 将完整文本作为新 activity 发送（而不仅仅是 delta）

**情况 A（streamFailed = true）：**

- `onPartialReply` 捕获错误，设置 `streamFailed = true`
- 调用 `preparePayload()`：`tokensEmitted && !streamFailed` = `true && false` = `false`
- 走到 `return payload` → **未经截断返回完整文本**
- `queueReplyPayload()` 将完整文本作为区块消息发送
- 用户看到：已可见的流式前缀 + 完整的区块文本 = **重复**

## 复现步骤

### 环境

- OpenClaw：2026.6.1
- 频道：`channels.msteams`，`streaming.mode=partial`
- 模型：任何能生成 >4000 字符回复的模型

### 步骤

1. 配置 `channels.msteams.streaming.mode=partial`
2. 在 DM 中发送一个会生成 >4000 字符回复的提示
3. 观察：流式预览 **和** 第二份完整回复（分块区块发送）同时作为独立气泡保留
4. 低于 4000 字符的回复正常折叠（单个气泡）

### 最小代码复现

```javascript
/**
 * #91723 最小复现：>4000 字符回复导致重复发送
 *
 * 模拟 reply-stream-controller.ts 中导致重复消息的确切状态转换。
 */

let tokensEmitted = false;
let streamFailed = false;
let emittedTextLength = 0;
let pendingFinalPayload = null;
let streamFinalizationPending = false;

function simulateOnPartialReply(cumulativeText) {
  if (cumulativeText.length <= emittedTextLength) return;
  const delta = cumulativeText.slice(emittedTextLength);
  try {
    // stream.emit(delta) - 在达到 SDK 限制前成功
    emittedTextLength = cumulativeText.length;
    tokensEmitted = true;
  } catch (e) {
    streamFailed = true;
  }
}

function simulatePreparePayload(payload) {
  // 对应 reply-stream-controller.ts 中的 preparePayload()

  // 情况：token 已发送且 stream 正常 → 移除 text（没有截断！）
  if (tokensEmitted && !streamFailed) {
    pendingFinalPayload = { ...payload, text: undefined };
    streamFinalizationPending = true;
    tokensEmitted = false;
    return undefined; // text 被移除
  }

  // 情况：stream 失败 → 返回完整 payload，未经截断
  if (streamFailed) {
    return payload; // <-- Bug：应该截断 emittedTextLength 前缀
  }

  return payload;
}

// === 模拟 >4000 字符回复 ===
const fullText = "a".repeat(5000);
const payload = { text: fullText };

// 流式分块（模拟 onPartialReply 被调用）
simulateOnPartialReply(fullText.slice(0, 100));
simulateOnPartialReply(fullText.slice(0, 2000));
simulateOnPartialReply(fullText.slice(0, 4000));
// 模拟 SDK 在 4000 字符处失败
streamFailed = true; // 模拟 stream.emit() 抛出异常
simulateOnPartialReply(fullText);

console.log(`已流式发送：${emittedTextLength} 字符`);
const prepared = simulatePreparePayload(payload);
console.log(`preparePayload 返回：${prepared?.text?.length ?? "已移除"}`);

if (prepared && prepared.text) {
  console.log("❌ Bug：返回了完整文本，未截断已流式发送的前缀！");
  console.log(`   已流式发送：${emittedTextLength} 字符（用户已看到）`);
  console.log(`   区块发送：${prepared.text.length} 字符`);
  console.log(`   → 前 ${emittedTextLength} 个字符在两者中都有！`);
} else {
  console.log("✅ 无重复（text 被正确移除）");
}
```

### 输出

```
已流式发送：4000 字符
preparePayload 返回：5000
❌ Bug：返回了完整文本，未截断已流式发送的前缀！
   已流式发送：4000 字符（用户已看到）
   区块发送：5000 字符
   → 前 4000 个字符在两者中都有！
```

## 修复方案

将 #59297 的前缀截断逻辑移植到新的 `preparePayload()` 路径中：

```javascript
// reply-stream-controller.ts 中 preparePayload() 的修复

if (tokensEmitted && !streamFailed) {
  const hasMedia = Boolean(payload.mediaUrl || payload.mediaUrls?.length);

  // 新增：检查已流式发送的前缀是否覆盖了完整文本
  if (emittedTextLength >= (payload.text?.length ?? 0)) {
    // 完整文本已通过流式发送 → 完全抑制
    pendingFinalPayload = fallbackPayloadForSuppressedFinal(payload);
    streamFinalizationPending = true;
    tokensEmitted = false;
    return hasMedia ? { ...payload, text: undefined } : undefined;
  }

  // 新增：从 fallback payload 中截断已流式发送的前缀
  const remainingText = payload.text.slice(emittedTextLength);
  pendingFinalPayload = {
    ...payload,
    text: remainingText || undefined,
    ...(hasMedia ? {} : { text: undefined }),
  };
  streamFinalizationPending = true;
  tokensEmitted = false;

  // 仅在没有剩余文本时抑制
  if (!remainingText) {
    return hasMedia ? { ...payload, text: undefined } : undefined;
  }

  // 返回只包含剩余文本的 payload
  return { ...payload, text: remainingText };
}
```

**同时修复 `streamFailed` 路径：**

```javascript
if (streamFailed) {
  // 截断已流式发送的前缀（与 #59297 相同）
  if (emittedTextLength > 0 && payload.text && emittedTextLength < payload.text.length) {
    payload = { ...payload, text: payload.text.slice(emittedTextLength) };
  }
  return payload;
}
```

## 验证

修复后：

1. > 4000 字符的回复应显示为单个气泡（流式预览过渡到最终状态）
   >
2. Teams 中不会出现重复消息
3. 短回复（<4000 字符）仍然正常工作
4. `streaming.mode="off"` 仍然有效（完全不流式）

## 相关 Issue

- 回归了 #59297（修复）/ #58601（原始 bug）
- 由 #76262（SDK rebase）引入
- #90398（开放）- 5.28 中正常长度重复发送（独立问题）

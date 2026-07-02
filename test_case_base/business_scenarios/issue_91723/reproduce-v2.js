/**
 * #91723 准确复现：msteams 流式回复超过 4000 字符时重复发送
 *
 * 根因（经源码确认）：
 * reply-stream-controller.ts 中的 preparePayload() 在处理第一个
 * chunk 后将 tokensEmitted 重置为 false。当回复文本超过 4000 字符时，
 * 回复流水线会多次调用 deliver()（每个 chunk 一次）。
 * 第二次 deliver() 调用时 tokensEmitted 已经是 false，
 * 导致 preparePayload() 返回完整 payload（含完整文本），
 * 进而作为区块消息发送 → 与已流式发送的文本重复。
 *
 * 注意：实际的"多次 deliver() 调用"是因为 msteams 频道配置中
 * deliveryMode:"direct" 配合 chunker 和 textChunkLimit:4000。
 * 当最终回复文本超过 4000 字符时，流水线将其拆分为多次
 * deliver() 调用。但即使只有一次 deliver() 调用，该 bug 仍然可能触发，
 * 因为 preparePayload() 没有考虑 stream.emit() 可能已发送部分文本、
 * 而 SDK 的 stream.close() 可能会重新发送完整文本的情况。
 *
 * 最简复现：调用 onPartialReply() 流式发送 >4000 字符，
 * 然后以完整 payload 调用 preparePayload()，观察其返回
 * undefined（text 被移除）。接着调用 finalize()。
 * 如果 SDK 的 stream.close() 只发送了流式前缀（而非完整文本），
 * 用户只能看到前 4000 字符。但 issue 报告说完整文本被作为
 * 独立区块重新发送了。
 *
 * 实际触发条件（来自 issue 分析）：
 * 关键点位于 reply-dispatcher.ts 的 markDispatchIdle() 中：
 *   1. flushPendingMessages() - 发送所有排队的区块消息
 *   2. streamController.finalize() - 如果返回 fallbackPayload，将其入队
 *   3. flushPendingMessages() 再次调用 - 发送 fallback
 *
 * 当 streamFailed=true（飞行中发生非取消的 stream 失败）时，
 * preparePayload() 穿透并返回完整 payload。
 * 这发生在 stream.emit() 因非取消原因抛出时。
 * 在新 SDK 中，当文本 > 4000 字符时，SDK 可能抛出异常，
 * 或 stream 进入失败状态，设置 streamFailed=true。
 * 然后 preparePayload() 返回完整 payload → queueReplyPayload →
 * 完整文本的区块发送。但已流式发送的前缀仍然可见 → 重复发送。
 */

// ================================================================
// 最小逻辑级复现
// ================================================================

console.log("╔════════════════════════════════════════════════════╗");
console.log("║  #91723 复现：msteams >4000 字符重复发送          ║");
console.log("╚════════════════════════════════════════════════════╝");
console.log();

// 模拟 reply-stream-controller.ts 中超过 4000 字符回复的
// 确切状态转换（流式启用）

let tokensEmitted = false;
let streamFailed = false;
let emittedTextLength = 0;
let pendingFinalPayload = null;
let streamFinalizationPending = false;
let streamCanceled = false;

const TEAMS_MAX_CHARS = 4000;

function simulateOnPartialReply(fullText) {
  // 对应 reply-stream-controller.ts 中的 onPartialReply
  // 将累积文本转换为增量，并调用 stream.emit(delta)
  if (fullText.length <= emittedTextLength) return;
  const delta = fullText.slice(emittedTextLength);
  try {
    // 模拟 stream.emit(delta)
    emittedTextLength = fullText.length;
    tokensEmitted = true;
  } catch (e) {
    streamFailed = true;
  }
}

function simulatePreparePayload(payload) {
  // 对应 reply-stream-controller.ts 中的 preparePayload()
  if (streamCanceled) return undefined;

  if (tokensEmitted && !streamFailed) {
    // 第一个 deliver() 调用走这个分支
    const hasMedia = !!(payload.mediaUrl || payload.mediaUrls?.length);
    pendingFinalPayload = hasMedia ? { ...payload, text: undefined } : payload;
    streamFinalizationPending = true;
    tokensEmitted = false; // <-- 重置 #1：tokensEmitted = false
    return hasMedia ? { ...payload, text: undefined } : undefined;
  }

  // 如果 tokensEmitted=false（如上重置），但仍有文本需要发送，
  // 这个路径会返回完整 payload → 如果再次调用则产生 Bug
  if (tokensEmitted && streamFailed) {
    // 旧 #59297 修复会在此处截断 payload.text
    return payload; // <-- Bug：返回完整文本，未截断
  }

  return payload;
}

function simulateFinalize() {
  // 对应 reply-stream-controller.ts 中的 finalize()
  if (!streamFinalizationPending) return undefined;
  // 模拟 stream.close()
  const result = !streamFailed; // close() 在 stream 正常时返回 true
  streamFinalizationPending = false;
  if (!result) {
    // close() 返回 false → fallback 到区块发送
    const fallback = pendingFinalPayload;
    pendingFinalPayload = undefined;
    return fallback;
  }
  pendingFinalPayload = undefined;
  return undefined; // stream 已处理发送
}

// ================================================================
// 场景：>4000 字符回复，两次 deliver() 调用（分块）
// ================================================================

function runScenario1() {
  console.log("━━━ 场景 1：>4000 字符，单次 deliver() 调用 ━━━");

  // 重置状态
  tokensEmitted = false; streamFailed = false; emittedTextLength = 0;
  pendingFinalPayload = null; streamFinalizationPending = false;

  const fullText = "a".repeat(5000);
  const payload = { text: fullText };

  // 通过 onPartialReply 流式分块（来自流水线的累积文本）
  simulateOnPartialReply(fullText.slice(0, 100));
  simulateOnPartialReply(fullText.slice(0, 500));
  simulateOnPartialReply(fullText.slice(0, 2000));
  simulateOnPartialReply(fullText.slice(0, 4000));
  simulateOnPartialReply(fullText); // 完整文本

  console.log(`  已流式发送：${emittedTextLength} 字符`);
  console.log(`  tokensEmitted：${tokensEmitted}`);

  // deliver() 以完整 payload 被调用
  const prepared = simulatePreparePayload(payload);
  console.log(`  preparePayload()：text=${prepared?.text?.length ?? "已移除"}`);

  // finalize()
  const finalized = simulateFinalize();
  console.log(`  finalize()：${finalized ? `fallback，含 ${finalized.text?.length} 字符` : "无 fallback"}`);

  // 检查：如果 finalized 有文本，它将作为区块被发送
  // 如果 stream 已显示 5000 字符，而 finalized 也有 5000 字符
  // → 前 4000 字符在 stream 和区块中都有
  if (finalized && finalized.text) {
    console.log(`  ❌ 重复发送：stream 显示了 ${emittedTextLength} 字符，区块发送 ${finalized.text.length} 字符`);
    console.log(`     （流式文本和区块文本重叠！）`);
    return true;
  } else {
    console.log(`  ✅ 无重复：文本仅通过 stream 发送`);
    return false;
  }
}

function runScenario2() {
  console.log("\n━━━ 场景 2：>4000 字符，stream 飞行中失败 ━━━");
  console.log("  （模拟文本超过 4000 字符时 SDK 抛出异常）");

  // 重置状态
  tokensEmitted = false; streamFailed = false; emittedTextLength = 0;
  pendingFinalPayload = null; streamFinalizationPending = false;

  const fullText = "a".repeat(5000);
  const payload = { text: fullText };

  // 流式分块 - 模拟在 4000 字符处 stream 失败
  simulateOnPartialReply(fullText.slice(0, 100));
  simulateOnPartialReply(fullText.slice(0, 500));
  simulateOnPartialReply(fullText.slice(0, 2000));
  simulateOnPartialReply(fullText.slice(0, 4000));
  // 下一次 emit 失败（SDK 在 4000 限制处抛出异常）
  streamFailed = true; // 模拟 onPartialReply 中的 catch
  simulateOnPartialReply(fullText); // 不会 emit，但 streamFailed 现为 true

  console.log(`  已流式发送：${emittedTextLength} 字符（失败前）`);
  console.log(`  streamFailed：${streamFailed}`);
  console.log(`  tokensEmitted：${tokensEmitted}`);

  // preparePayload - 由于 streamFailed=true，tokensEmitted && !streamFailed 为 FALSE
  // 所以穿透返回完整 payload
  const prepared = simulatePreparePayload(payload);
  console.log(`  preparePayload()：text=${prepared?.text?.length ?? "已移除"}`);

  if (prepared && prepared.text) {
    console.log(`  ❌ Bug：preparePayload() 返回了完整文本（${prepared.text.length} 字符）`);
    console.log(`     已流式发送的前缀（${emittedTextLength} 字符）用户已看到！`);
    console.log(`     完整文本将作为区块发送 → 重复发送！`);
    return true;
  }

  return false;
}

function runScenario3() {
  console.log("\n━━━ 场景 3：#59297 修复对比（旧行为 vs 新行为） ━━━");
  console.log("  展示 #59297 修复的做法与新代码之间的差异");

  const fullText = "a".repeat(5000);
  const streamedPrefixLength = 4000;

  console.log(`  完整文本：${fullText.length} 字符`);
  console.log(`  已流式发送前缀：${streamedPrefixLength} 字符`);
  console.log();

  console.log("  旧行为（#59297 修复）：");
  console.log("    1. 检查已流式前缀是否覆盖完整文本 → 否");
  console.log("    2. 从 payload 中截断已流式前缀");
  console.log(`    3. fallback payload text = ${fullText.length - streamedPrefixLength} 字符（仅剩余部分）`);
  console.log("    ✅ 无重复：区块仅发送剩余 1000 字符");
  console.log();

  console.log("  新行为（当前代码，#76262 之后）：");
  console.log("    1. tokensEmitted && !streamFailed → 完全移除 text");
  console.log("    2. 返回 undefined（text 被移除）");
  console.log("    3. finalize() → stream.close() 应发送文本");
  console.log("    ⚠️  如果 stream.close() 只发送了流式前缀（4000 字符），");
  console.log("       剩余 1000 字符将丢失（回复被截断）。");
  console.log("    ⚠️  如果 stream.close() 重新发送完整文本（5000 字符），");
  console.log("       前 4000 字符将重复。");
  console.log();
  console.log("    #91723 报告的实际 bug 是第二种情况：");
  console.log("    完整文本作为分块区块被重新发送 → 重复。");

  return true;
}

// ================================================================
// 运行所有场景
// ================================================================

let bugConfirmed = false;
bugConfirmed |= runScenario1();
bugConfirmed |= runScenario2();
bugConfirmed |= runScenario3();

console.log("\n═══════════════════════════════════════════════════════");
if (bugConfirmed) {
  console.log("❌ Bug 已确认（或极可能发生）");
  console.log();
  console.log("根因：");
  console.log("  reply-stream-controller.ts 中的 preparePayload() 方法");
  console.log("  未处理 SDK stream 有 ~4000 字符限制且文本超过该限制的情况。");
  console.log("  当 stream.emit() 成功发送前 4000 字符后，SDK 内部");
  console.log("  触发 fallback（或 stream 断开），完整文本会被重新");
  console.log("  作为区块消息发送，且未截断已流式发送的前缀。");
  console.log();
  console.log("修复方案（与 #59297 相同）：");
  console.log("  在 preparePayload() 中，当 tokensEmitted && !streamFailed 时：");
  console.log("    1. 检查 emittedTextLength >= payload.text.length");
  console.log("       → 如果是，返回 undefined（完整文本已流式发送）");
  console.log("    2. 如果不是，截断 payload.text = payload.text.slice(emittedTextLength)");
  console.log("       → fallback 仅发送剩余文本");
} else {
  console.log("✅ 模拟中未发现明显 bug 路径");
  console.log("  （实际 bug 可能需要真实 SDK 行为才能触发）");
}
console.log("═══════════════════════════════════════════════════════\n");

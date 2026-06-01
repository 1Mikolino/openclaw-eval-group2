/**
 * OpenClaw WebSocket 压力测试客户端
 * 用于测试 OpenClaw 在受限资源环境下的性能表现
 * 
 * 使用方法:
 *   node client.js [目标URL] [选项]
 * 
 * 示例:
 *   node client.js ws://localhost:8080 --duration 60 --interval 100
 */

const WebSocket = require('ws');

// 配置参数
const TARGET_URL = process.argv[2] || 'ws://10.0.12.4:8080';
const MESSAGE_INTERVAL = parseInt(process.argv.find(arg => arg.startsWith('--interval='))?.split('=')[1]) || 100; // 默认 100ms
const TOTAL_DURATION_MS = (parseInt(process.argv.find(arg => arg.startsWith('--duration='))?.split('=')[1]) || 60) * 1000; // 默认 60秒

// 统计数据
let successCount = 0;
let failCount = 0;
let totalLatency = 0;
let minLatency = Infinity;
let maxLatency = 0;
const latencyHistory = [];

/**
 * 格式化时间为 YYYY-MM-DD HH:mm:ss
 */
function formatTime(date = new Date()) {
  return date.toISOString().replace('T', ' ').substring(0, 19);
}

/**
 * 打印测试结果摘要
 */
function printSummary() {
  const avgLatency = successCount > 0 ? (totalLatency / successCount).toFixed(2) : 0;
  const successRate = successCount + failCount > 0 
    ? ((successCount / (successCount + failCount)) * 100).toFixed(2) 
    : 0;
  
  console.log('\n' + '='.repeat(50));
  console.log('📊 OpenClaw 压力测试报告');
  console.log('='.repeat(50));
  console.log(`测试时间: ${formatTime()}`);
  console.log(`目标地址: ${TARGET_URL}`);
  console.log(`测试时长: ${TOTAL_DURATION_MS / 1000} 秒`);
  console.log(`发送间隔: ${MESSAGE_INTERVAL} ms`);
  console.log('-'.repeat(50));
  console.log(`✅ 成功请求: ${successCount}`);
  console.log(`❌ 失败请求: ${failCount}`);
  console.log(`📈 成功率: ${successRate}%`);
  console.log('-'.repeat(50));
  console.log(`⏱️ 延迟统计:`);
  console.log(`   平均延迟: ${avgLatency} ms`);
  console.log(`   最小延迟: ${minLatency === Infinity ? 'N/A' : minLatency} ms`);
  console.log(`   最大延迟: ${maxLatency} ms`);
  console.log('='.repeat(50));
  
  // 返回测试结果（供自动化调用）
  return {
    successCount,
    failCount,
    successRate: parseFloat(successRate),
    avgLatency: parseFloat(avgLatency),
    minLatency: minLatency === Infinity ? null : minLatency,
    maxLatency,
    timestamp: new Date().toISOString()
  };
}

/**
 * 运行压力测试
 */
function runLoadTest() {
  console.log(`🚀 开始压力测试...`);
  console.log(`目标: ${TARGET_URL}`);
  console.log(`时长: ${TOTAL_DURATION_MS / 1000} 秒, 间隔: ${MESSAGE_INTERVAL} ms\n`);
  
  const ws = new WebSocket(TARGET_URL);
  const startTime = Date.now();
  const endTime = startTime + TOTAL_DURATION_MS;
  let intervalId = null;

  // 连接建立
  ws.on('open', () => {
    console.log('✅ WebSocket 连接已建立，开始发送测试消息...\n');
    
    intervalId = setInterval(() => {
      // 检查是否到达结束时间
      if (Date.now() > endTime) {
        clearInterval(intervalId);
        ws.close();
        console.log('\n🏁 测试时间到达，正在关闭连接...');
        return;
      }

      // 发送带时间戳的消息
      const sendTime = Date.now();
      const message = JSON.stringify({ 
        type: 'ping', 
        time: sendTime,
        seq: successCount + failCount + 1
      });
      
      try {
        ws.send(message);
      } catch (err) {
        failCount++;
        console.error(`❌ 发送失败: ${err.message}`);
      }
    }, MESSAGE_INTERVAL);
  });

  // 接收响应
  ws.on('message', (data) => {
    try {
      const response = JSON.parse(data);
      if (response.time) {
        const rtt = Date.now() - response.time;
        totalLatency += rtt;
        successCount++;
        
        // 更新延迟统计
        if (rtt < minLatency) minLatency = rtt;
        if (rtt > maxLatency) maxLatency = rtt;
        latencyHistory.push(rtt);
        
        // 每 100 条消息打印一次进度
        if (successCount % 100 === 0) {
          const progress = ((Date.now() - startTime) / TOTAL_DURATION_MS * 100).toFixed(1);
          console.log(`[${progress}%] 成功: ${successCount}, 当前延迟: ${rtt} ms`);
        }
      }
    } catch (err) {
      failCount++;
      console.error('❌ 解析响应失败:', err.message);
    }
  });

  // 连接错误
  ws.on('error', (err) => {
    failCount++;
    console.error('❌ WebSocket 错误:', err.message);
  });

  // 连接关闭
  ws.on('close', (code, reason) => {
    if (intervalId) clearInterval(intervalId);
    
    if (code !== 1000 && code !== 1005) {
      console.error(`⚠️ 连接异常关闭 (code: ${code}, reason: ${reason})`);
    }
    
    // 输出最终报告
    const result = printSummary();
    
    // 设置退出码（便于自动化脚本检测）
    const exitCode = result.successRate >= 90 ? 0 : 1;
    process.exit(exitCode);
  });

  // 超时处理
  setTimeout(() => {
    if (ws.readyState === WebSocket.CONNECTING) {
      console.error('❌ 连接超时');
      ws.terminate();
      process.exit(1);
    }
  }, 10000);
}

// 捕获中断信号
process.on('SIGINT', () => {
  console.log('\n\n⚠️ 收到中断信号，正在结束测试...');
  printSummary();
  process.exit(0);
});

// 运行测试
runLoadTest();

// 导出模块（供其他脚本调用）
module.exports = { runLoadTest, printSummary };

/**
 * OpenClaw WebSocket 压力测试客户端
 * 用于测试 OpenClaw 在受限资源环境下的性能表现
 * 支持加载 GitHub 仓库中的测试用例配置
 * 
 * 使用方法:
 *   node client.js [配置选项]
 * 
 * 示例:
 *   # 基础测试
 *   node client.js
 * 
 *   # 指定目标地址
 *   node client.js --target=ws://192.168.1.100:8080
 * 
 *   # 自定义测试参数
 *   node client.js --duration=120 --interval=50 --target=ws://server:8080
 * 
 *   # 加载测试用例配置（JSON文件路径或URL）
 *   node client.js --config=https://raw.githubusercontent.com/.../test-config.json
 */

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// ============================================
// 默认配置
// ============================================
const DEFAULT_CONFIG = {
  target: 'ws://10.0.12.4:8080',    // 默认目标服务端地址
  duration: 60,                      // 测试时长（秒）
  interval: 100,                     // 消息发送间隔（毫秒）
  messageType: 'ping',               // 消息类型: ping, echo, load_test
  loadDelay: 0,                      // load_test 类型的处理延迟
  reportInterval: 100,               // 进度报告间隔（消息数）
  verbose: true,                     // 是否输出详细日志
  waitForWelcome: true,              // 是否等待服务端 welcome 消息
  welcomeTimeout: 5000,              // welcome 消息等待超时（毫秒）
};

// ============================================
// 解析命令行参数
// ============================================
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    if (arg.startsWith('--')) {
      const [key, value] = arg.substring(2).split('=');
      // 类型转换
      if (value === 'true') args[key] = true;
      else if (value === 'false') args[key] = false;
      else if (!isNaN(value) && value !== '') args[key] = Number(value);
      else args[key] = value || true;
    }
  });
  return args;
}

// ============================================
// 加载配置文件
// ============================================
async function loadConfig(configPath) {
  try {
    let configData;
    
    if (configPath.startsWith('http://') || configPath.startsWith('https://')) {
      // 从 URL 加载（如 GitHub raw 文件）
      const response = await fetch(configPath);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      configData = await response.text();
      console.log(`📥 已从 URL 加载配置: ${configPath}`);
    } else {
      // 从本地文件加载
      const fullPath = path.resolve(configPath);
      configData = fs.readFileSync(fullPath, 'utf-8');
      console.log(`📂 已从本地加载配置: ${fullPath}`);
    }
    
    const config = JSON.parse(configData);
    console.log('✅ 配置加载成功');
    return config;
  } catch (err) {
    console.error(`❌ 加载配置失败: ${err.message}`);
    process.exit(1);
  }
}

// ============================================
// 合并配置
// ============================================
async function getConfig() {
  const args = parseArgs();
  let config = { ...DEFAULT_CONFIG };
  
  // 如果有 --config 参数，加载配置文件
  if (args.config) {
    const fileConfig = await loadConfig(args.config);
    config = { ...config, ...fileConfig };
  }
  
  // 命令行参数优先级最高
  config = { ...config, ...args };
  
  return config;
}

// ============================================
// 统计数据
// ============================================
class StatsCollector {
  constructor() {
    this.successCount = 0;
    this.failCount = 0;
    this.totalLatency = 0;
    this.minLatency = Infinity;
    this.maxLatency = 0;
    this.latencyHistory = [];
    this.startTime = null;
    this.endTime = null;
    this.errors = [];
  }

  recordSuccess(latency) {
    this.successCount++;
    this.totalLatency += latency;
    this.minLatency = Math.min(this.minLatency, latency);
    this.maxLatency = Math.max(this.maxLatency, latency);
    this.latencyHistory.push(latency);
  }

  recordFail(error) {
    this.failCount++;
    this.errors.push({ time: Date.now(), error: error.message || error });
  }

  getSummary() {
    const avgLatency = this.successCount > 0 ? (this.totalLatency / this.successCount).toFixed(2) : 0;
    const total = this.successCount + this.failCount;
    const successRate = total > 0 ? ((this.successCount / total) * 100).toFixed(2) : 0;
    
    // 计算百分位延迟
    const sortedLatencies = [...this.latencyHistory].sort((a, b) => a - b);
    const p50 = sortedLatencies[Math.floor(sortedLatencies.length * 0.5)] || 0;
    const p95 = sortedLatencies[Math.floor(sortedLatencies.length * 0.95)] || 0;
    const p99 = sortedLatencies[Math.floor(sortedLatencies.length * 0.99)] || 0;

    return {
      duration: this.endTime ? ((this.endTime - this.startTime) / 1000).toFixed(0) : 0,
      successCount: this.successCount,
      failCount: this.failCount,
      totalCount: total,
      successRate: parseFloat(successRate),
      latency: {
        avg: parseFloat(avgLatency),
        min: this.minLatency === Infinity ? 0 : this.minLatency,
        max: this.maxLatency,
        p50,
        p95,
        p99,
      },
      errors: this.errors.length,
      timestamp: new Date().toISOString(),
    };
  }
}

// ============================================
// 格式化时间
// ============================================
function formatTime(date = new Date()) {
  return date.toISOString().replace('T', ' ').substring(0, 19);
}

// ============================================
// 打印测试报告
// ============================================
function printReport(stats, config) {
  const summary = stats.getSummary();
  
  console.log('\n' + '='.repeat(60));
  console.log('📊 OpenClaw 压力测试报告');
  console.log('='.repeat(60));
  console.log(`测试时间: ${formatTime()}`);
  console.log(`目标地址: ${config.target}`);
  console.log(`测试时长: ${summary.duration} 秒 / ${config.duration} 秒`);
  console.log(`消息间隔: ${config.interval} ms`);
  console.log(`消息类型: ${config.messageType}`);
  console.log('-'.repeat(60));
  console.log(`✅ 成功请求: ${summary.successCount}`);
  console.log(`❌ 失败请求: ${summary.failCount}`);
  console.log(`📊 总请求数: ${summary.totalCount}`);
  console.log(`📈 成功率: ${summary.successRate}%`);
  console.log('-'.repeat(60));
  console.log(`⏱️ 延迟统计:`);
  console.log(`   平均: ${summary.latency.avg} ms`);
  console.log(`   最小: ${summary.latency.min} ms`);
  console.log(`   最大: ${summary.latency.max} ms`);
  console.log(`   P50:  ${summary.latency.p50} ms`);
  console.log(`   P95:  ${summary.latency.p95} ms`);
  console.log(`   P99:  ${summary.latency.p99} ms`);
  if (summary.errors > 0) {
    console.log('-'.repeat(60));
    console.log(`⚠️ 错误数: ${summary.errors}`);
  }
  console.log('='.repeat(60));

  return summary;
}

// ============================================
// 主测试函数
// ============================================
async function runLoadTest(userConfig = null) {
  // 获取配置
  const config = userConfig || await getConfig();
  
  console.log(`\n🚀 开始压力测试...`);
  console.log(`目标: ${config.target}`);
  console.log(`时长: ${config.duration} 秒, 间隔: ${config.interval} ms`);
  console.log(`消息类型: ${config.messageType}\n`);
  
  const stats = new StatsCollector();
  stats.startTime = Date.now();
  
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(config.target);
    const testDurationMs = config.duration * 1000;
    const endTime = stats.startTime + testDurationMs;
    let intervalId = null;
    let welcomeReceived = false;

    // 连接超时处理
    const connectTimeout = setTimeout(() => {
      if (!welcomeReceived && config.waitForWelcome) {
        ws.terminate();
        reject(new Error('连接超时：未收到服务端 welcome 消息'));
      }
    }, config.welcomeTimeout);

    // 连接建立
    ws.on('open', () => {
      if (config.verbose) console.log('✅ WebSocket 连接已建立，等待服务端就绪...\n');
    });

    // 接收响应
    ws.on('message', (data) => {
      try {
        const response = JSON.parse(data);
        
        // 处理 welcome 消息
        if (response.type === 'welcome') {
          welcomeReceived = true;
          clearTimeout(connectTimeout);
          if (config.verbose) {
            console.log('🦞 服务端信息:', response.server || 'OpenClaw Test Server');
            console.log('   服务端指标:', JSON.stringify(response.metrics, null, 2));
            console.log('\n📤 开始发送测试消息...\n');
          }
          
          // 开始发送测试消息
          intervalId = setInterval(() => {
            if (Date.now() > endTime) {
              clearInterval(intervalId);
              ws.close(1000, 'Test completed');
              return;
            }

            const sendTime = Date.now();
            const message = {
              type: config.messageType,
              time: sendTime,
              seq: stats.successCount + stats.failCount + 1,
            };
            
            if (config.messageType === 'load_test') {
              message.delay = config.loadDelay;
            }
            
            try {
              ws.send(JSON.stringify(message));
            } catch (err) {
              stats.recordFail(err);
            }
          }, config.interval);
          
          return;
        }
        
        // 处理响应消息（计算延迟）
        if (response.time) {
          const rtt = Date.now() - response.time;
          stats.recordSuccess(rtt);
          
          // 进度报告
          if (config.verbose && stats.successCount % config.reportInterval === 0) {
            const progress = ((Date.now() - stats.startTime) / testDurationMs * 100).toFixed(1);
            console.log(`[${progress}%] 成功: ${stats.successCount}, 当前延迟: ${rtt} ms`);
          }
        }
        
        // 处理服务端指标
        if (response.type === 'metrics') {
          if (config.verbose) console.log('📊 服务端指标:', JSON.stringify(response.data, null, 2));
        }
        
      } catch (err) {
        stats.recordFail(err);
        if (config.verbose) console.error('❌ 解析响应失败:', err.message);
      }
    });

    // 连接错误
    ws.on('error', (err) => {
      clearTimeout(connectTimeout);
      if (intervalId) clearInterval(intervalId);
      stats.recordFail(err);
      if (config.verbose) console.error('❌ WebSocket 错误:', err.message);
    });

    // 连接关闭
    ws.on('close', (code, reason) => {
      clearTimeout(connectTimeout);
      if (intervalId) clearInterval(intervalId);
      
      stats.endTime = Date.now();
      
      if (code !== 1000 && code !== 1005) {
        console.error(`\n⚠️ 连接异常关闭 (code: ${code}${reason ? ', reason: ' + reason : ''})`);
      }
      
      // 输出报告
      const summary = printReport(stats, config);
      resolve(summary);
    });

    // 总体超时保护
    setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    }, testDurationMs + 10000);
  });
}

// ============================================
// 程序入口
// ============================================
if (require.main === module) {
  // 捕获中断信号
  process.on('SIGINT', () => {
    console.log('\n\n⚠️ 收到中断信号，正在结束测试...');
    process.exit(0);
  });

  // 运行测试
  runLoadTest()
    .then(summary => {
      // 设置退出码（便于自动化脚本检测）
      const exitCode = summary.successRate >= 90 ? 0 : 1;
      process.exit(exitCode);
    })
    .catch(err => {
      console.error('❌ 测试失败:', err.message);
      process.exit(1);
    });
}

// ============================================
// 模块导出
// ============================================
module.exports = { 
  runLoadTest, 
  loadConfig, 
  StatsCollector,
  DEFAULT_CONFIG,
};

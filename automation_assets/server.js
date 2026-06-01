/**
 * OpenClaw WebSocket 压力测试服务端
 * 运行在测试目标机器（小龙虾）上，用于接收压测请求并响应
 * 
 * 使用方法:
 *   node server.js [选项]
 * 
 * 示例:
 *   node server.js --port=8080 --log-level=info
 */

const WebSocket = require('ws');
const http = require('http');
const os = require('os');

// ============================================
// 配置参数
// ============================================
const CONFIG = {
  port: parseInt(process.argv.find(arg => arg.startsWith('--port='))?.split('=')[1]) || 8080,
  host: process.argv.find(arg => arg.startsWith('--host='))?.split('=')[1] || '0.0.0.0',
  logLevel: process.argv.find(arg => arg.startsWith('--log-level='))?.split('=')[1] || 'info',
  enableMetrics: !process.argv.includes('--no-metrics'),
  metricsInterval: parseInt(process.argv.find(arg => arg.startsWith('--metrics-interval='))?.split('=')[1]) || 5000,
};

// ============================================
// 统计数据
// ============================================
const stats = {
  startTime: Date.now(),
  totalReceived: 0,
  totalSent: 0,
  activeConnections: 0,
  totalConnections: 0,
  errors: 0,
  latencies: [], // 存储最近的延迟数据用于计算百分位
};

// ============================================
// 日志工具
// ============================================
const LogLevel = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };
const currentLogLevel = LogLevel[CONFIG.logLevel.toUpperCase()] || LogLevel.INFO;

function log(level, message, data = null) {
  if (LogLevel[level] >= currentLogLevel) {
    const timestamp = new Date().toISOString();
    const levelEmoji = { DEBUG: '🔍', INFO: 'ℹ️', WARN: '⚠️', ERROR: '❌' }[level];
    const logLine = `[${timestamp}] ${levelEmoji} ${message}`;
    console.log(logLine);
    if (data) console.log('   Data:', JSON.stringify(data, null, 2));
  }
}

// ============================================
// 系统监控
// ============================================
function getSystemMetrics() {
  const uptime = ((Date.now() - stats.startTime) / 1000).toFixed(0);
  const memoryUsage = process.memoryUsage();
  const systemMemory = {
    total: (os.totalmem() / 1024 / 1024).toFixed(0),
    free: (os.freemem() / 1024 / 1024).toFixed(0),
    used: ((os.totalmem() - os.freemem()) / 1024 / 1024).toFixed(0),
  };
  
  return {
    uptime: `${uptime}s`,
    processMemory: {
      rss: `${(memoryUsage.rss / 1024 / 1024).toFixed(2)} MB`,
      heapUsed: `${(memoryUsage.heapUsed / 1024 / 1024).toFixed(2)} MB`,
      heapTotal: `${(memoryUsage.heapTotal / 1024 / 1024).toFixed(2)} MB`,
    },
    systemMemory,
    cpu: os.loadavg(),
    connections: {
      active: stats.activeConnections,
      total: stats.totalConnections,
    },
    messages: {
      received: stats.totalReceived,
      sent: stats.totalSent,
    },
  };
}

function printMetrics() {
  if (!CONFIG.enableMetrics) return;
  
  const metrics = getSystemMetrics();
  log('INFO', '📊 系统监控', metrics);
}

// ============================================
// WebSocket 服务端
// ============================================
function createServer() {
  const wss = new WebSocket.Server({ 
    host: CONFIG.host,
    port: CONFIG.port,
  });

  log('INFO', `🚀 压力测试服务端启动中...`);
  log('INFO', `   监听地址: ws://${CONFIG.host}:${CONFIG.port}`);
  log('INFO', `   日志级别: ${CONFIG.logLevel}`);
  log('INFO', `   监控间隔: ${CONFIG.metricsInterval}ms`);

  // 定期输出监控信息
  if (CONFIG.enableMetrics) {
    setInterval(printMetrics, CONFIG.metricsInterval);
  }

  // 连接处理
  wss.on('connection', (ws, req) => {
    const clientIp = req.socket.remoteAddress;
    stats.activeConnections++;
    stats.totalConnections++;
    
    log('INFO', `🦞 压测客户端已接入 [${clientIp}]`，{
      activeConnections: stats.activeConnections,
      totalConnections: stats.totalConnections,
    });

    // 发送欢迎消息（包含服务端信息）
    ws.send(JSON.stringify({
      type: 'welcome',
      server: 'OpenClaw Load Test Server',
      version: '1.0.0',
      timestamp: Date.now(),
      metrics: getSystemMetrics(),
    }));

    // 消息处理
    ws.on('message', (data) => {
      stats.totalReceived++;
      
      try {
        const message = JSON.parse(data);
        log('DEBUG', `收到消息 [type: ${message.type}]`, { seq: message.seq, time: message.time });

        // 处理不同类型的消息
        switch (message.type) {
          case 'ping':
            // 心跳/延迟测试 - 原样返回，方便客户端计算 RTT
            ws.send(data); // 直接返回原始数据
            stats.totalSent++;
            break;
            
          case 'echo':
            // 回显测试 - 添加服务端时间戳
            ws.send(JSON.stringify({
              ...message,
              serverTime: Date.now(),
              type: 'echo_response',
            }));
            stats.totalSent++;
            break;
            
          case 'load_test':
            // 负载测试 - 模拟处理延迟
            const processingDelay = message.delay || 0;
            setTimeout(() => {
              ws.send(JSON.stringify({
                type: 'load_response',
                seq: message.seq,
                requestTime: message.time,
                responseTime: Date.now(),
                processingDelay,
              }));
              stats.totalSent++;
            }, processingDelay);
            break;
            
          case 'get_metrics':
            // 查询服务端指标
            ws.send(JSON.stringify({
              type: 'metrics',
              timestamp: Date.now(),
              data: getSystemMetrics(),
            }));
            stats.totalSent++;
            break;
            
          case 'shutdown':
            // 优雅关闭（需要认证，这里简化处理）
            log('WARN', '收到关闭请求');
            ws.send(JSON.stringify({
              type: 'shutdown_ack',
              timestamp: Date.now(),
            }));
            break;
            
          default:
            log('WARN', `未知消息类型: ${message.type}`);
            ws.send(JSON.stringify({
              type: 'error',
              message: `Unknown message type: ${message.type}`,
              supportedTypes: ['ping', 'echo', 'load_test', 'get_metrics', 'shutdown'],
            }));
        }
      } catch (err) {
        stats.errors++;
        log('ERROR', '消息处理错误', err.message);
        ws.send(JSON.stringify({
          type: 'error',
          message: 'Failed to process message',
          error: err.message,
        }));
      }
    });

    // 连接关闭
    ws.on('close', (code, reason) => {
      stats.activeConnections--;
      log('INFO', `🔌 连接已断开 [${clientIp}] (code: ${code}, reason: ${reason})`, {
        activeConnections: stats.activeConnections,
      });
    });

    // 错误处理
    ws.on('error', (err) => {
      stats.errors++;
      log('ERROR', `WebSocket 错误 [${clientIp}]`, err.message);
    });
  });

  // 服务端错误
  wss.on('error', (err) => {
    log('ERROR', '服务端错误', err.message);
    process.exit(1);
  });

  // 关闭处理
  process.on('SIGINT', () => {
    log('INFO', '\n⚠️ 收到终止信号，正在关闭服务端...');
    log('INFO', '📈 最终统计', {
      uptime: ((Date.now() - stats.startTime) / 1000).toFixed(0) + 's',
      totalConnections: stats.totalConnections,
      totalReceived: stats.totalReceived,
      totalSent: stats.totalSent,
      errors: stats.errors,
    });
    wss.close(() => {
      process.exit(0);
    });
  });

  return wss;
}

// ============================================
// 启动服务端
// ============================================
createServer();

// 导出模块（供测试使用）
module.exports = { createServer, getSystemMetrics, stats };

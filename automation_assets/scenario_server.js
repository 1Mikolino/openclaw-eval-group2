/**
 * OpenClaw Test Scenario Server
 * 小龙虾 - 测试执行服务端
 * 支持调用各种测试用例：browser_concurrent, skill_stress, web_tools_guide等
 * 
 * Usage: node scenario_server.js [--port=9877]
 * 
 * @author OpenClaw Eval Group 2
 * @version 1.0.0
 */

const WebSocket = require('ws');
const { exec, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

// 默认配置
const CONFIG = {
  port: 9877,
  host: '0.0.0.0',
  testCasesDir: path.join(__dirname, '..', 'test_case_base', 'business_scenarios'),
  workspaceDir: '/root/.openclaw/workspace'
};

// 解析命令行参数
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    if (arg.startsWith('--')) {
      const [key, value] = arg.substring(2).split('=');
      args[key] = value || true;
    }
  });
  return args;
}

// 获取系统资源信息
function getSystemMetrics() {
  const cpus = os.cpus();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const loadAvg = os.loadavg();
  
  return {
    timestamp: new Date().toISOString(),
    cpu_count: cpus.length,
    cpu_model: cpus[0]?.model || 'unknown',
    memory_total_gb: (totalMem / 1024 / 1024 / 1024).toFixed(2),
    memory_free_gb: (freeMem / 1024 / 1024 / 1024).toFixed(2),
    memory_used_percent: ((1 - freeMem / totalMem) * 100).toFixed(1),
    load_avg: loadAvg.map(v => v.toFixed(2))
  };
}

// 测试用例注册表
const TEST_CASES = {
  'browser_concurrent': {
    name: '多浏览器并发测试',
    description: '模拟多浏览器并发，监测系统崩溃临界点',
    script: 'multi_browser_concurrent/multi_browser_concurrent_test.py',
    type: 'python',
    params: ['--max_browsers', '--duration']
  },
  'skill_stress': {
    name: '技能压力测试',
    description: 'Top 10技能压力测试，监测CPU/内存占用',
    script: 'skill_stress/skill_stress_test.py',
    type: 'python',
    params: ['--workers', '--iterations']
  },
  'web_tools_guide': {
    name: 'Web-Tools-Guide稳定性测试',
    description: '检验web-tools-guide skill稳定性',
    script: 'web_tools_guide_stability/web_tools_guide_stability_test.py',
    type: 'python',
    params: ['--duration', '--output']
  }
};

// 当前运行的测试
let currentTest = null;
let activeConnections = new Set();

// 广播消息给所有客户端
function broadcast(message) {
  const data = JSON.stringify(message);
  activeConnections.forEach(ws => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    }
  });
}

// 执行测试用例
async function runTestCase(testId, scenario, params, ws) {
  const testCase = TEST_CASES[scenario];
  if (!testCase) {
    return { error: `Unknown scenario: ${scenario}` };
  }

  const scriptPath = path.join(CONFIG.testCasesDir, testCase.script);
  if (!fs.existsSync(scriptPath)) {
    return { error: `Test script not found: ${scriptPath}` };
  }

  console.log(`[Test] Starting ${scenario} with params:`, params);

  // 构建命令行参数
  const args = [];
  if (params.max_browsers) args.push(String(params.max_browsers));
  if (params.duration) args.push(`--duration=${params.duration}`);
  if (params.workers) args.push(`--workers=${params.workers}`);
  if (params.iterations) args.push(`--iterations=${params.iterations}`);
  if (params.output) args.push(params.output);

  // 启动测试进程
  const testProcess = spawn('python3', [scriptPath, ...args], {
    cwd: CONFIG.testCasesDir,
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

  currentTest = {
    id: testId,
    scenario: scenario,
    process: testProcess,
    startTime: Date.now(),
    status: 'running'
  };

  // 收集输出
  let output = '';
  testProcess.stdout.on('data', (data) => {
    const line = data.toString();
    output += line;
    
    // 解析实时指标并广播
    const metrics = parseRealtimeMetrics(line);
    if (metrics) {
      broadcast({
        type: 'progress',
        test_id: testId,
        scenario: scenario,
        metrics: metrics,
        system: getSystemMetrics()
      });
    }
  });

  testProcess.stderr.on('data', (data) => {
    console.error(`[Test Error] ${data}`);
  });

  // 等待测试完成
  return new Promise((resolve) => {
    testProcess.on('close', (code) => {
      currentTest.status = code === 0 ? 'completed' : 'failed';
      currentTest.endTime = Date.now();
      
      // 尝试读取结果文件
      let resultFile = params.output;
      if (!resultFile && output.includes('报告已保存')) {
        const match = output.match(/报告已保存[:：]\s*(.+)/);
        if (match) resultFile = match[1].trim();
      }

      let resultData = null;
      if (resultFile) {
        const resultPath = path.join(CONFIG.testCasesDir, resultFile);
        if (fs.existsSync(resultPath)) {
          try {
            resultData = JSON.parse(fs.readFileSync(resultPath, 'utf8'));
          } catch (e) {
            console.error('Failed to parse result file:', e.message);
          }
        }
      }

      resolve({
        exit_code: code,
        duration_ms: currentTest.endTime - currentTest.startTime,
        output: output.slice(-5000), // 最后5000字符
        result_file: resultFile,
        result_data: resultData
      });
    });
  });
}

// 解析实时指标（从Python脚本输出中）
function parseRealtimeMetrics(line) {
  // 匹配格式: [实时监控] 浏览器: 5 | CPU: 12.3% | 内存: 45.6%
  const match = line.match(/\[实时监控\].*?浏览器[:：]\s*(\d+).*?CPU[:：]\s*([\d.]+)%.*?内存[:：]\s*([\d.]+)%/);
  if (match) {
    return {
      active_browsers: parseInt(match[1]),
      cpu_percent: parseFloat(match[2]),
      memory_percent: parseFloat(match[3])
    };
  }
  
  // 匹配格式: [迭代 100] CPU: 5.1% | 内存: 44.5%
  const match2 = line.match(/\[迭代\s*(\d+)\].*?CPU[:：]\s*([\d.]+)%.*?内存[:：]\s*([\d.]+)%/);
  if (match2) {
    return {
      iteration: parseInt(match2[1]),
      cpu_percent: parseFloat(match2[2]),
      memory_percent: parseFloat(match2[3])
    };
  }
  
  return null;
}

// 创建WebSocket服务器
function createServer(port) {
  const wss = new WebSocket.Server({ port, host: CONFIG.host });

  console.log(`🦞 Scenario Server v1.0.0`);
  console.log(`   Listening on ws://${CONFIG.host}:${port}`);
  console.log(`   Test cases dir: ${CONFIG.testCasesDir}`);
  console.log(`   Supported scenarios: ${Object.keys(TEST_CASES).join(', ')}`);

  wss.on('connection', (ws, req) => {
    const clientId = `${req.socket.remoteAddress}:${req.socket.remotePort}`;
    console.log(`[Client] Connected: ${clientId}`);
    activeConnections.add(ws);

    // 发送欢迎消息
    ws.send(JSON.stringify({
      type: 'welcome',
      server: 'OpenClaw Scenario Server',
      version: '1.0.0',
      scenarios: Object.entries(TEST_CASES).map(([key, val]) => ({
        id: key,
        name: val.name,
        description: val.description
      })),
      system: getSystemMetrics()
    }));

    ws.on('message', async (message) => {
      try {
        const data = JSON.parse(message);
        await handleCommand(ws, data);
      } catch (err) {
        ws.send(JSON.stringify({
          type: 'error',
          error: 'Invalid JSON: ' + err.message
        }));
      }
    });

    ws.on('close', () => {
      console.log(`[Client] Disconnected: ${clientId}`);
      activeConnections.delete(ws);
    });

    ws.on('error', (err) => {
      console.error(`[Client] Error: ${err.message}`);
    });
  });

  return wss;
}

// 处理客户端命令
async function handleCommand(ws, data) {
  const { type, test_id, scenario, params } = data;

  switch (type) {
    case 'start_test':
      if (currentTest && currentTest.status === 'running') {
        ws.send(JSON.stringify({
          type: 'error',
          error: 'Another test is already running'
        }));
        return;
      }

      const testId = test_id || `test_${Date.now()}`;
      
      ws.send(JSON.stringify({
        type: 'test_started',
        test_id: testId,
        scenario: scenario,
        timestamp: new Date().toISOString()
      }));

      // 异步运行测试
      const result = await runTestCase(testId, scenario, params || {}, ws);
      
      ws.send(JSON.stringify({
        type: 'test_completed',
        test_id: testId,
        scenario: scenario,
        result: result,
        timestamp: new Date().toISOString()
      }));
      break;

    case 'stop_test':
      if (currentTest && currentTest.process) {
        currentTest.process.kill('SIGTERM');
        ws.send(JSON.stringify({ type: 'test_stopped', test_id: currentTest.id }));
      } else {
        ws.send(JSON.stringify({ type: 'error', error: 'No test running' }));
      }
      break;

    case 'get_metrics':
      ws.send(JSON.stringify({
        type: 'metrics',
        data: {
          system: getSystemMetrics(),
          active_test: currentTest ? {
            id: currentTest.id,
            scenario: currentTest.scenario,
            status: currentTest.status,
            duration_ms: Date.now() - currentTest.startTime
          } : null,
          active_connections: activeConnections.size
        }
      }));
      break;

    case 'list_scenarios':
      ws.send(JSON.stringify({
        type: 'scenarios_list',
        scenarios: Object.entries(TEST_CASES).map(([key, val]) => ({
          id: key,
          name: val.name,
          description: val.description,
          params: val.params
        }))
      }));
      break;

    default:
      ws.send(JSON.stringify({
        type: 'error',
        error: `Unknown command type: ${type}`
      }));
  }
}

// 主函数
function main() {
  const args = parseArgs();
  const port = parseInt(args.port) || CONFIG.port;

  // 检查测试用例目录是否存在
  if (!fs.existsSync(CONFIG.testCasesDir)) {
    console.error(`❌ Test cases directory not found: ${CONFIG.testCasesDir}`);
    process.exit(1);
  }

  console.log('📂 Scanning test cases...');
  Object.entries(TEST_CASES).forEach(([key, val]) => {
    const scriptPath = path.join(CONFIG.testCasesDir, val.script);
    const exists = fs.existsSync(scriptPath);
    console.log(`   ${exists ? '✓' : '✗'} ${key}: ${val.script}`);
  });

  const server = createServer(port);

  // 优雅关闭
  process.on('SIGINT', () => {
    console.log('\n\n⚠️  Shutting down server...');
    if (currentTest && currentTest.process) {
      currentTest.process.kill('SIGTERM');
    }
    server.close(() => {
      console.log('✅ Server closed');
      process.exit(0);
    });
  });
}

main();

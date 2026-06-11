/**
 * OpenClaw Test Scenario Client
 * 大龙虾 - 测试控制客户端
 * 支持调用各种测试场景：browser_concurrent, skill_stress, web_tools_guide等
 * 
 * Usage:
 *   node scenario_client.js [options]
 *   node scenario_client.js --scenario=browser_concurrent --max_browsers=20 --duration=60
 *   node scenario_client.js --config=test_config.json
 *   node scenario_client.js --interactive
 * 
 * @author OpenClaw Eval Group 2
 * @version 1.0.0
 */

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

// 默认配置
const DEFAULT_CONFIG = {
  target: 'ws://localhost:9877',
  scenario: 'browser_concurrent',
  verbose: true,
  reportInterval: 2000,
  outputFile: null,
  
  // 场景参数
  browser_concurrent: {
    max_browsers: 20,
    duration: 60
  },
  skill_stress: {
    workers: 10,
    iterations: 50
  },
  web_tools_guide: {
    duration: 60,
    output: 'web_tools_result.json'
  }
};

// 统计收集器
class StatsCollector {
  constructor() {
    this.metrics = [];
    this.events = [];
    this.startTime = null;
    this.endTime = null;
  }

  start() {
    this.startTime = Date.now();
  }

  end() {
    this.endTime = Date.now();
  }

  recordMetric(data) {
    this.metrics.push({
      timestamp: Date.now(),
      ...data
    });
  }

  recordEvent(type, data) {
    this.events.push({
      type,
      timestamp: Date.now(),
      ...data
    });
  }

  getSummary() {
    if (!this.startTime) return null;
    
    const duration = this.endTime ? this.endTime - this.startTime : Date.now() - this.startTime;
    
    // 计算峰值
    const cpuValues = this.metrics.map(m => m.cpu_percent).filter(v => v !== undefined);
    const memValues = this.metrics.map(m => m.memory_percent).filter(v => v !== undefined);
    
    return {
      duration_ms: duration,
      metrics_count: this.metrics.length,
      events_count: this.events.length,
      peak_cpu: cpuValues.length > 0 ? Math.max(...cpuValues) : 0,
      peak_memory: memValues.length > 0 ? Math.max(...memValues) : 0,
      avg_cpu: cpuValues.length > 0 ? (cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length).toFixed(1) : 0,
      avg_memory: memValues.length > 0 ? (memValues.reduce((a, b) => a + b, 0) / memValues.length).toFixed(1) : 0
    };
  }
}

// 解析命令行参数
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    if (arg.startsWith('--')) {
      const eqIndex = arg.indexOf('=');
      if (eqIndex > -1) {
        const key = arg.substring(2, eqIndex);
        const value = arg.substring(eqIndex + 1);
        args[key] = value;
      } else {
        args[arg.substring(2)] = true;
      }
    }
  });
  return args;
}

// 加载配置文件
function loadConfig(configPath) {
  try {
    const content = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(content);
  } catch (err) {
    console.error(`❌ Failed to load config: ${err.message}`);
    return null;
  }
}

// 打印测试进度
function printProgress(data) {
  const { metrics, scenario, test_id } = data;
  if (!metrics) return;
  
  const { active_browsers, iteration, cpu_percent, memory_percent } = metrics;
  
  if (active_browsers !== undefined) {
    process.stdout.write(`\r[Test ${test_id}] 浏览器: ${active_browsers.toString().padStart(2)} | CPU: ${cpu_percent.toFixed(1).padStart(5)}% | 内存: ${memory_percent.toFixed(1).padStart(5)}%`);
  } else if (iteration !== undefined) {
    process.stdout.write(`\r[Test ${test_id}] 迭代: ${iteration.toString().padStart(4)} | CPU: ${cpu_percent.toFixed(1).padStart(5)}% | 内存: ${memory_percent.toFixed(1).padStart(5)}%`);
  }
}

// 运行测试
async function runTest(ws, config, stats) {
  return new Promise((resolve, reject) => {
    const scenario = config.scenario;
    const params = config[scenario] || {};
    const testId = `test_${Date.now()}`;
    
    console.log(`\n🚀 启动测试: ${scenario}`);
    console.log(`   参数: ${JSON.stringify(params)}`);
    console.log(`   测试ID: ${testId}`);
    console.log('─'.repeat(60));
    
    stats.start();
    
    let completed = false;
    
    ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data);
        
        switch (msg.type) {
          case 'test_started':
            console.log(`✅ 测试已启动: ${msg.scenario}`);
            break;
            
          case 'progress':
            stats.recordMetric(msg.metrics);
            if (config.verbose) {
              printProgress(msg);
            }
            break;
            
          case 'test_completed':
            if (!completed) {
              completed = true;
              stats.end();
              console.log('\n' + '─'.repeat(60));
              console.log('✅ 测试完成');
              resolve(msg.result);
            }
            break;
            
          case 'error':
            stats.recordEvent('error', { message: msg.error });
            console.error(`\n❌ 错误: ${msg.error}`);
            reject(new Error(msg.error));
            break;
        }
      } catch (err) {
        console.error('Parse error:', err.message);
      }
    });
    
    // 发送启动命令
    ws.send(JSON.stringify({
      type: 'start_test',
      test_id: testId,
      scenario: scenario,
      params: params
    }));
    
    // 超时处理
    setTimeout(() => {
      if (!completed) {
        reject(new Error('Test timeout'));
      }
    }, (params.duration || 60) * 1000 + 30000);
  });
}

// 交互式模式
async function interactiveMode(ws) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  
  const ask = (question) => new Promise(resolve => rl.question(question, resolve));
  
  console.log('\n🎮 交互式测试模式');
  console.log('='.repeat(60));
  
  // 获取场景列表
  ws.send(JSON.stringify({ type: 'list_scenarios' }));
  
  const scenarios = await new Promise((resolve) => {
    ws.once('message', (data) => {
      const msg = JSON.parse(data);
      if (msg.type === 'scenarios_list') {
        resolve(msg.scenarios);
      }
    });
  });
  
  console.log('\n可用测试场景:');
  scenarios.forEach((s, i) => {
    console.log(`  ${i + 1}. ${s.name} (${s.id})`);
    console.log(`     ${s.description}`);
  });
  
  const choice = await ask('\n选择场景编号 (1-' + scenarios.length + '): ');
  const scenario = scenarios[parseInt(choice) - 1];
  
  if (!scenario) {
    console.log('❌ 无效选择');
    rl.close();
    return;
  }
  
  // 询问参数
  const params = {};
  if (scenario.id === 'browser_concurrent') {
    params.max_browsers = parseInt(await ask('最大浏览器数 (默认20): ')) || 20;
    params.duration = parseInt(await ask('测试时长秒数 (默认60): ')) || 60;
  } else if (scenario.id === 'skill_stress') {
    params.workers = parseInt(await ask('工作线程数 (默认10): ')) || 10;
    params.iterations = parseInt(await ask('迭代次数 (默认50): ')) || 50;
  }
  
  rl.close();
  
  return { scenario: scenario.id, params };
}

// 主函数
async function main() {
  const args = parseArgs();
  
  console.log('🦞 OpenClaw Scenario Client v1.0.0');
  console.log('='.repeat(60));
  
  // 加载配置
  let config = { ...DEFAULT_CONFIG };
  
  if (args.config) {
    const fileConfig = loadConfig(args.config);
    if (fileConfig) {
      config = { ...config, ...fileConfig };
      console.log(`📂 已加载配置: ${args.config}`);
    }
  }
  
  // 命令行参数覆盖
  if (args.target) config.target = args.target;
  if (args.scenario) config.scenario = args.scenario;
  if (args.verbose !== undefined) config.verbose = args.verbose === 'true';
  if (args.output) config.outputFile = args.output;
  
  // 场景特定参数
  if (args.max_browsers) config.browser_concurrent.max_browsers = parseInt(args.max_browsers);
  if (args.duration) {
    config.browser_concurrent.duration = parseInt(args.duration);
    config.web_tools_guide.duration = parseInt(args.duration);
  }
  if (args.workers) config.skill_stress.workers = parseInt(args.workers);
  if (args.iterations) config.skill_stress.iterations = parseInt(args.iterations);
  
  console.log(`\n📋 配置:`);
  console.log(`   目标: ${config.target}`);
  console.log(`   场景: ${config.scenario}`);
  console.log(`   参数: ${JSON.stringify(config[config.scenario], null, 2)}`);
  
  // 连接服务器
  console.log(`\n🔗 连接到服务器: ${config.target}`);
  
  const ws = new WebSocket(config.target);
  
  await new Promise((resolve, reject) => {
    ws.on('open', resolve);
    ws.on('error', reject);
    setTimeout(() => reject(new Error('Connection timeout')), 10000);
  });
  
  console.log('✅ 已连接');
  
  // 等待欢迎消息
  const welcome = await new Promise((resolve) => {
    ws.once('message', (data) => resolve(JSON.parse(data)));
  });
  
  if (welcome.type === 'welcome') {
    console.log(`🦞 服务器: ${welcome.server}`);
    console.log(`   支持场景: ${welcome.scenarios.map(s => s.id).join(', ')}`);
  }
  
  // 交互式或自动模式
  let testConfig = config;
  
  if (args.interactive) {
    const interactiveConfig = await interactiveMode(ws);
    if (interactiveConfig) {
      testConfig = { ...config, ...interactiveConfig };
    }
  }
  
  // 运行测试
  const stats = new StatsCollector();
  
  try {
    const result = await runTest(ws, testConfig, stats);
    
    // 打印统计
    console.log('\n📊 测试统计:');
    const summary = stats.getSummary();
    if (summary) {
      console.log(`   时长: ${(summary.duration_ms / 1000).toFixed(1)}s`);
      console.log(`   指标数: ${summary.metrics_count}`);
      console.log(`   CPU峰值: ${summary.peak_cpu.toFixed(1)}%`);
      console.log(`   内存峰值: ${summary.peak_memory.toFixed(1)}%`);
      console.log(`   CPU平均: ${summary.avg_cpu}%`);
      console.log(`   内存平均: ${summary.avg_memory}%`);
    }
    
    // 打印结果
    if (result) {
      console.log('\n📄 测试结果:');
      console.log(`   退出码: ${result.exit_code}`);
      console.log(`   执行时间: ${(result.duration_ms / 1000).toFixed(1)}s`);
      if (result.result_file) {
        console.log(`   结果文件: ${result.result_file}`);
      }
      if (result.result_data) {
        console.log(`   摘要: ${JSON.stringify(result.result_data.summary || {}, null, 2)}`);
      }
    }
    
    // 保存报告
    if (config.outputFile) {
      const report = {
        config: testConfig,
        summary: stats.getSummary(),
        result: result,
        metrics: stats.metrics,
        events: stats.events,
        timestamp: new Date().toISOString()
      };
      fs.writeFileSync(config.outputFile, JSON.stringify(report, null, 2));
      console.log(`\n💾 报告已保存: ${config.outputFile}`);
    }
    
  } catch (err) {
    console.error(`\n💥 测试失败: ${err.message}`);
    process.exitCode = 1;
  } finally {
    ws.close();
    console.log('\n👋 已断开连接');
  }
}

// 运行
main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

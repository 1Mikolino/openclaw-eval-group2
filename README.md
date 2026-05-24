# openclaw-eval-group2
组长：黄奕曦 组员：杨文 丘仕军
第一周
仓库创建，websocket连接两台openclaw（小龙虾作为一个node接入大龙虾），尝试压力测试
进行WebSocket压力测试所用到的代码如下：
pkill -f client.js(用于大龙虾）
const WebSocket = require('ws');

const TARGET_URL = 'ws://10.0.12.4:8080';
const MESSAGE_INTERVAL = 100; // 频率 (ms)
const TOTAL_DURATION_MS = 60000; // 测试时长 (60秒)

let successCount = 0;
let failCount = 0;
let totalLatency = 0;

function runLoadTest() {
    const ws = new WebSocket(TARGET_URL);
    const startTime = Date.now();
    const endTime = startTime + TOTAL_DURATION_MS;

    ws.on('open', () => {
        console.log('✅ 连接建立，开始高压测试...');
        
        const interval = setInterval(() => {
            if (Date.now() > endTime) {
                clearInterval(interval);
                ws.close();
                console.log('🏁 压测结束！');
                printSummary();
                return;
            }

            const sendTime = Date.now();
            ws.send(JSON.stringify({ type: 'ping', time: sendTime }));
        }, MESSAGE_INTERVAL);
    });

    ws.on('message', (data) => {
        const rtt = Date.now() - JSON.parse(data).time;
        totalLatency += rtt;
        successCount++;
    });

    ws.on('error', (err) => {
        failCount++;
        console.error('❌ 压测请求失败:', err.message);
    });
}

function printSummary() {
    console.log('--- 压测报告 ---');
    console.log(`成功请求: ${successCount}`);
    console.log(`失败请求: ${failCount}`);
    console.log(`平均延迟: ${(totalLatency / successCount || 0).toFixed(2)} ms`);
    console.log('----------------');
}

runLoadTest();

server.js（用于小龙虾）

const WebSocket = require('ws');

const TARGET_URL = 'ws://10.0.12.4:8080';
const MESSAGE_INTERVAL = 100; // 频率 (ms)
const TOTAL_DURATION_MS = 60000; // 测试时长 (60秒)

let successCount = 0;
let failCount = 0;
let totalLatency = 0;

function runLoadTest() {
    const ws = new WebSocket(TARGET_URL);
    const startTime = Date.now();
    const endTime = startTime + TOTAL_DURATION_MS;

    ws.on('open', () => {
        console.log('✅ 连接建立，开始高压测试...');
        
        const interval = setInterval(() => {
            if (Date.now() > endTime) {
                clearInterval(interval);
                ws.close();
                console.log('🏁 压测结束！');
                printSummary();
                return;
            }

            const sendTime = Date.now();
            ws.send(JSON.stringify({ type: 'ping', time: sendTime }));
        }, MESSAGE_INTERVAL);
    });

    ws.on('message', (data) => {
        const rtt = Date.now() - JSON.parse(data).time;
        totalLatency += rtt;
        successCount++;
    });

    ws.on('error', (err) => {
        failCount++;
        console.error('❌ 压测请求失败:', err.message);
    });
}

function printSummary() {
    console.log('--- 压测报告 ---');
    console.log(`成功请求: ${successCount}`);
    console.log(`失败请求: ${failCount}`);
    console.log(`平均延迟: ${(totalLatency / successCount || 0).toFixed(2)} ms`);
    console.log('----------------');
}

runLoadTest();

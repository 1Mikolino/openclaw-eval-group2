#!/usr/bin/env node
/**
 * 复现 OpenClaw Issue #96389 - 最终版
 * 直接测试 clawpdf extract API 的 4M 像素限制 bug
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 测试 extract API
async function testExtractAPI(pdfPath) {
    console.log('🔧 测试 clawpdf extract API...\n');
    
    try {
        const { openPdf } = await import('clawpdf');
        
        console.log(`📂 加载 PDF: ${pdfPath}`);
        const pdf = await openPdf(pdfPath);
        const pageCount = pdf.pageCount;
        console.log(`   页数: ${pageCount}\n`);
        
        // 先检查文本提取
        const text = pdf.text({ maxPages: pageCount });
        console.log(`📝 文本提取: ${text.length} 字符`);
        console.log(`   预览: ${text.substring(0, 100).replace(/\n/g, '\\n')}\n`);
        
        // 测试 extract API with mode: "images"
        console.log('🔄 调用 pdf.extract({ mode: "images", image: { maxPixels: 4000000 } })...\n');
        
        const result = await pdf.extract({
            mode: 'images',
            image: {
                maxPixels: 4000000,
                format: 'png'
            }
        });
        
        console.log(`   结果: ${result.images ? result.images.length : 0} 张图片`);
        console.log(`   处理页数: ${result.pagesProcessed}`);
        console.log(`   截断: ${result.truncated}\n`);
        
        if (result.images && result.images.length > 0) {
            console.log('📸 检查图片尺寸:');
            let bugDetected = false;
            let onePixelCount = 0;
            
            for (const img of result.images) {
                const { page, width, height, bytes, mimeType } = img;
                const totalPixels = width * height;
                
                console.log(`   Page ${page}: ${width}x${height} (${totalPixels.toLocaleString()} 像素, ${bytes?.length || 0} bytes, ${mimeType})`);
                
                if (width <= 1 && height <= 1) {
                    console.log(`      ⚠️  检测到 1x1 像素 BUG!`);
                    onePixelCount++;
                    bugDetected = true;
                } else if (totalPixels > 4000000) {
                    console.log(`      ⚠️  超过 4M 像素限制: ${totalPixels.toLocaleString()} 像素`);
                }
            }
            
            console.log(`\n📊 统计: ${onePixelCount}/${result.images.length} 张图片是 1x1 像素\n`);
            
            if (bugDetected) {
                console.log('✅ BUG 已确认复现!');
                console.log('   问题: clawpdf extract() 的 4M 像素预算导致部分页面渲染为 1x1\n');
                return true;
            } else if (result.images.length < pageCount) {
                console.log('⚠️  部分页面未被处理');
                console.log(`   期望: ${pageCount} 页, 实际: ${result.images.length} 张图片\n`);
                return true; // 这也算 bug
            }
        } else {
            console.log('❌ 没有生成图片\n');
        }
        
        // 对比：逐页渲染
        console.log('🔄 对比测试: 逐页渲染 (page.png())...\n');
        let successCount = 0;
        
        for (let i = 0; i < Math.min(pageCount, 10); i++) {
            try {
                const page = pdf.page(i + 1);
                const pngBytes = await page.png({ dpi: 150 });
                
                // pngBytes 是 Uint8Array，需要转换
                const buffer = Buffer.from(pngBytes);
                
                if (buffer.length > 24) {
                    // PNG 尺寸在 bytes 16-23
                    const width = buffer.readUInt32BE(16);
                    const height = buffer.readUInt32BE(20);
                    console.log(`   Page ${i + 1}: ${width}x${height} (${buffer.length} bytes)`);
                    successCount++;
                }
            } catch (pageError) {
                console.log(`   Page ${i + 1}: 失败 - ${pageError.message}`);
            }
        }
        
        console.log(`\n   逐页渲染成功: ${successCount}/${Math.min(pageCount, 10)} 页\n`);
        
        return false;
        
    } catch (error) {
        console.error(`❌ 错误: ${error.message}\n`);
        console.error(error.stack);
        return false;
    }
}

// 主函数
async function main() {
    console.log('='.repeat(60));
    console.log('OpenClaw Issue #96389 复现脚本 - 最终版');
    console.log('测试 clawpdf extract API 的 4M 像素限制');
    console.log('='.repeat(60) + '\n');
    
    // 使用之前生成的测试 PDF
    const testPDF = path.join(__dirname, 'reproduce_96389_JRXnmN/test_15pages.pdf');
    
    if (!fs.existsSync(testPDF)) {
        console.log('❌ 测试 PDF 不存在:', testPDF);
        console.log('   请先运行 reproduce_96389.mjs 生成测试文件\n');
        return;
    }
    
    console.log(`📁 使用测试 PDF: ${testPDF}\n`);
    
    // 运行测试
    const bugDetected = await testExtractAPI(testPDF);
    
    // 总结
    console.log('\n' + '='.repeat(60));
    console.log('总结');
    console.log('='.repeat(60));
    
    if (bugDetected) {
        console.log('✅ BUG 已成功复现!');
        console.log('   问题: clawpdf 的 extract({ mode: "images" }) 在 4M 像素限制下');
        console.log('         导致部分页面渲染为 1x1 像素\n');
        console.log('💡 建议修复:');
        console.log('   1. 修改 clawpdf 使每页重置渲染预算');
        console.log('   2. 或在 OpenClaw 中使用逐页渲染 (page.png()) 作为 fallback\n');
    } else {
        console.log('ℹ️  未能完全复现 1x1 像素 bug');
        console.log('   可能原因:');
        console.log('   1. 测试 PDF 未触发边界条件');
        console.log('   2. clawpdf 版本已部分修复');
        console.log('   3. 需要更精确的测试 PDF (真实扫描，300 DPI)\n');
    }
    
    console.log('📁 测试文件:');
    console.log(`   ${testPDF}`);
    console.log(`   ${path.dirname(testPDF)}\n`);
}

main().catch(error => {
    console.error('脚本执行失败:', error);
    process.exit(1);
});

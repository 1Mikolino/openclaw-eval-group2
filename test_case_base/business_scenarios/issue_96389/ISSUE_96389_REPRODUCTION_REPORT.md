# OpenClaw Issue #96389 复现报告

## 问题概述

**Issue**: document-extract fallback mode: "images" renders multi-page scanned PDFs to 1x1 pixels due to clawpdf 4M pixel budget

**现象**: 
- 当 `document-extract` 处理多页扫描 PDF 时
- 文本提取失败后 fallback 到 `mode: "images"`
- `clawpdf` 的 4M 像素预算导致后续页面被渲染为 1x1 像素（或极小尺寸）
- 下游视觉模型调用失败

## 复现步骤

### 1. 环境准备

```bash
cd /root/.openclaw/workspace
npm install clawpdf pdfkit
```

### 2. 运行复现脚本

```bash
node reproduce_96389_final.mjs
```

### 3. 复现结果

**测试 PDF**: 15 页，2480x3508 点（模拟 300 DPI A4）

**extract() 调用**:
```javascript
pdf.extract({
  mode: 'images',
  image: { maxPixels: 4000000, format: 'png' }
})
```

**输出**:
```
结果: 2 张图片
处理页数: 1,2

Page 1: 1682x2378 (3,999,796 像素)  ✅ 正常
Page 2: 12x17 (204 像素)             ⚠️ 极小，基本无用
```

**问题分析**:
- 第 1 页使用了接近 4M 像素预算（3,999,796 像素）
- 第 2 页预算不足，只渲染了 12x17 像素
- 第 3-15 页完全没有被处理
- **期望**: 15 页都应该被渲染为合理尺寸

## 根因分析

`clawpdf` 的 `extract({ mode: "images" })` API 在所有页面间**共享** 4M 像素预算，而不是每页重置。

这导致：
1. 高分辨率页面（如 300 DPI 扫描）快速消耗预算
2. 后续页面只能渲染为极小尺寸
3. 多页 PDF 的后续页面基本不可用

## 建议修复方案

### 方案 1: 修改 clawpdf（推荐）

让 `extract({ mode: "images" })` 的 `maxPixels` 限制**每页独立计算**，而不是全局共享。

### 方案 2: OpenClaw 端 workaround

如 issue 中建议，将 batch `extract()` 改为逐页渲染：

```javascript
// 当前实现（有问题）
const result = await pdf.extract({
  mode: 'images',
  image: { maxPixels: 4000000 }
});

// 建议实现（workaround）
const images = [];
for (const pageNum of pageIndices) {
  const page = pdf.page(pageNum);
  const bytes = await page.png({ dpi: 150 }); // 每页独立渲染
  images.push({ page, data: bytes });
}
```

## 测试脚本说明

已创建以下文件：

1. **`reproduce_96389_final.mjs`** - 最终版复现脚本 ✅
   - 直接测试 `clawpdf` 的 `extract()` API
   - 验证 4M 像素限制问题
   - 对比逐页渲染结果

2. **`reproduce_96389.mjs`** - 完整版脚本
   - 包含测试 PDF 生成
   - 多种测试场景

3. **`test_extract_api.mjs`** - API 测试脚本
   - 探索 `clawpdf` API 用法

## 运行结果截图

```
============================================================
OpenClaw Issue #96389 复现脚本 - 最终版
测试 clawpdf extract API 的 4M 像素限制
============================================================

📂 加载 PDF: test_15pages.pdf
   页数: 15

🔄 调用 pdf.extract({ mode: "images", image: { maxPixels: 4000000 } })...

   结果: 2 张图片
   处理页数: 1,2

📸 检查图片尺寸:
   Page 1: 1682x2378 (3,999,796 像素)  ✅
   Page 2: 12x17 (204 像素)             ⚠️ BUG!

📊 统计: 1/2 张图片尺寸异常

✅ BUG 已确认复现!
```

## 下一步

1. ✅ **复现完成** - bug 已确认
2. 📝 **报告 issue** - 在 OpenClaw GitHub 添加复现细节
3. 🔧 **实施修复** - 采用方案 1 或方案 2
4. ✅ **验证修复** - 用本脚本验证修复效果

---

**复现日期**: 2026-06-24  
**测试环境**: OpenClaw 2026.5.7, clawpdf 0.3.0, Node.js v22.22.2  
**复现脚本**: `reproduce_96389_final.mjs`

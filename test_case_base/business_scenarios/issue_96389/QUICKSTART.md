# 快速复现 Issue #96389

## 一键复现

```bash
cd /root/.openclaw/workspace
node reproduce_96389_final.mjs
```

## 预期输出

```
✅ BUG 已确认复现!
   问题: clawpdf extract() 的 4M 像素预算导致部分页面渲染为 1x1
```

## 脚本说明

### 核心脚本：`reproduce_96389_final.mjs`

**功能**：
- 加载测试 PDF（15 页）
- 调用 `pdf.extract({ mode: "images", image: { maxPixels: 4000000 } })`
- 检查输出图片尺寸
- 对比逐页渲染结果

**输出**：
- 提取的图片数量和尺寸
- 是否触发 4M 像素限制
- Bug 复现状态

### 辅助脚本

1. **`reproduce_96389.mjs`** - 完整测试套件
   - 生成多种测试 PDF
   - 3 个测试场景（5页/15页/30页）
   - 需要 `pdfkit` 和 `clawpdf`

2. **`test_extract_api.mjs`** - API 探索脚本
   - 测试 `clawpdf` API 可用性
   - 检查 `extract()` vs `page.png()`

## 手动测试

如果你想用自己的 PDF 测试：

```javascript
import { openPdf } from 'clawpdf';

const pdf = await openPdf('your_scanned_document.pdf');
const result = await pdf.extract({
  mode: 'images',
  image: { maxPixels: 4000000, format: 'png' }
});

console.log(`处理页数: ${result.pagesProcessed}`);
console.log(`图片数量: ${result.images.length}`);

result.images.forEach(img => {
  console.log(`Page ${img.page}: ${img.width}x${img.height}`);
  if (img.width <= 1 && img.height <= 1) {
    console.log('  ⚠️ 1x1 pixel BUG!');
  }
});
```

## 清理

测试生成的临时文件在：
```
/root/.openclaw/workspace/reproduce_96389_*/
```

可以安全删除：
```bash
rm -rf /root/.openclaw/workspace/reproduce_96389_*
```

## 问题排查

### 错误：`Cannot find module 'clawpdf'`

```bash
cd /root/.openclaw/workspace
npm install clawpdf
```

### 错误：`pdf.text is not a function`

确保使用正确的 `clawpdf` API：
- `pdf.text()` 返回字符串（不是数组）
- `pdf.extract()` 返回 `{ text, images, pagesProcessed, truncated }`

### 错误：`Failed to load PDF`

检查 PDF 文件是否有效：
```bash
file your_document.pdf
# 应该输出: your_document.pdf: PDF document, version 1.x
```

## 成功标志

✅ **Bug 已复现** 如果：
- `extract()` 返回的图片数 < PDF 页数
- 部分图片尺寸极小（< 100x100）
- 或明确显示 1x1 像素

❌ **未能复现** 如果：
- 所有页面都被处理
- 所有图片尺寸合理（> 1000x1000）
- 可能是 PDF 结构不同或已修复

## 相关文件

- 📄 **复现报告**: `ISSUE_96389_REPRODUCTION_REPORT.md`
- 🔧 **核心脚本**: `reproduce_96389_final.mjs`
- 📝 **Issue 链接**: https://github.com/openclaw/openclaw/issues/96389

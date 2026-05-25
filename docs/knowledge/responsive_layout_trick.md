# GitHub README 无 CSS 响应式布局技巧

## 1. 背景与挑战
GitHub 的 Markdown 渲染器会过滤掉几乎所有的 CSS 属性（如 `display: flex`, `grid`, `@media` 等）。这导致开发者很难在 Profile README 中实现类似“卡片流”的响应式布局。

## 2. 核心方案：多表浮动法 (Multi-Table Float)
利用 HTML `<table>` 标签的原生 `align` 属性。在 GitHub 的环境里，`align="left"` 的效果等同于 `float: left`。

### 实现模版
```html
<div align="center">
  <!-- 卡片 1 -->
  <table align="left" width="320">
    <tr><td> ... 内容 ... </td></tr>
  </table>

  <!-- 卡片 2 -->
  <table align="left" width="320">
    <tr><td> ... 内容 ... </td></tr>
  </table>

  <!-- 卡片 3 -->
  <table align="left" width="320">
    <tr><td> ... 内容 ... </td></tr>
  </table>
</div>

<!-- 关键：清除浮动，防止影响后续布局 -->
<br clear="both">
```

## 3. 响应式表现 (Behavior)
*   **宽屏 (Desktop):** 三个表格的总宽度 (320 * 3 = 960px) 小于屏幕宽度，并排显示。
*   **中屏 (Tablet):** 屏幕宽度介于 640px - 960px 之间，前两个表格并排，第三个自动折行（2+1 布局）。
*   **窄屏 (Mobile):** 屏幕宽度小于 640px，三个表格垂直堆叠（1+1+1 布局）。

## 4. 注意事项 (Best Practices)
1.  **宽度设定：** 建议使用固定像素值（如 `320`）而非百分比，以确保在所有设备上“强制换行”的触发点一致。
2.  **清除浮动：** 必须在布局末尾添加 `<br clear="both">`，否则下方的博文列表等内容会因为“浮动残留”而错位。
3.  **居中容器：** 外层嵌套 `<div align="center">` 可以确保在表格换行时，整体视觉上依然保持居中感。

---
*Last Updated: 2026-05-06 by Antigravity*

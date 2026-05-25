# 像素小人生成指南 (Mascot Generation Guide)

为了保证 GitHub Profile 的视觉统一性，所有像素小人（Mascots）必须遵循以下生成模式。

## 1. 核心审美原则 (Design Principles)
*   **风格：** Apple 极简主义 (Apple-Style Minimalism)。
*   **构图：** 居中，纯白色背景（White Background），无杂乱元素。
*   **线条：** 干净、清晰的像素线条（Clean Pixel Lines），避免过度的渐变和阴影。
*   **配色：** 浅色系（Light Palette），高对比度，通常每张图不超过 3 种主色调。

## 2. 标准 Prompt 模版
在生成新的像素小人时，请使用以下结构化 Prompt：

> **Prompt:** `A minimalist pixel art mascot of a [具体物体名称], Apple-style aesthetic, [指定颜色] color palette, clean lines, white background, high-quality pixel art.`

### 示例参考：
*   **电脑：** `A minimalist pixel art mascot of a retro Macintosh computer, Apple-style aesthetic, light gray and white color palette, clean lines, white background, high-quality pixel art.`
*   **机器人：** `A minimalist pixel art mascot of a friendly small robot, Apple-style aesthetic, white and silver metallic colors, simple circular eyes, clean and sleek design, white background, high-quality pixel art.`

## 3. 尺寸与格式规范
*   **分辨率：** 建议生成 64x64 或 128x128 风格的像素画。
*   **文件格式：** `.png` 或 `.gif`。
*   **命名规则：** 存放在 `assets/mascots/` 目录下，命名为 `01.png` - `10.png`。

## 4. 自动化轮换逻辑
*   脚本 `scripts/sync.py` 会每天从 `01.png` 到 `10.png` 中随机抽取一张，复制为 `daily.gif`（或 .png），从而实现主页小人的自动轮换。
*   **Fallback:** 若文件夹为空，应默认指向 `default_mascot.png`。

---
*Last Updated: 2026-05-06 by Antigravity*

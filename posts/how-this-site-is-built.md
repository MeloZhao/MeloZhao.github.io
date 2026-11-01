---
title: 这个站点是怎么搭起来的
date: 2026-11-01
tags: 建站, 前端
summary: 零框架、零依赖、一行命令构建。顺便讲讲"液态玻璃"到底由哪几层叠出来。
---

换掉用了很久的旧站，重新做了一版。这篇记录一下技术选型和几个实现细节，以后想改的时候不用重新想一遍。

## 为什么不用框架

试过几个静态站点生成器，最后都放弃了。理由很朴素：

- 装依赖要花时间，半年后回来还得回忆怎么装；
- 主题改到第三层就开始和框架打架；
- 想调一个 CSS 变量，得先搞清楚它在哪一层被覆盖。

所以这次只用了三样东西：**Python 标准库、一个 CSS 文件、一个 JS 文件**。

`build.py` 做全部的事：读 Markdown、解析 front matter、生成 HTML、写 RSS 和 sitemap。没有 `pip install`，没有 `node_modules`。

```bash
python3 build.py          # 构建
python3 build.py --serve  # 构建 + 本地预览
```

## 目录结构

```text
posts/*.md        ← 唯一需要手动编辑的地方
build.py          ← 生成器
assets/css/       ← 全部样式
assets/js/        ← 交互
blog/             ← 生成产物
```

文章的增删只影响 `posts/`，其他目录都是产物。这个边界划清楚之后，改版就不怕弄丢内容。

## 「液态玻璃」其实是四层

很多人以为玻璃质感就是加一个 `backdrop-filter: blur()`。只做这一层，结果是一张灰扑扑的卡片。真正撑起质感的是四层叠加：

### 第一层：有东西可模糊

`backdrop-filter` 模糊的是它背后的像素。如果背后是纯色，模糊前后没有任何区别。

所以背景必须是**多色、低饱和、大尺度**的渐变。我用几个超大的 radial-gradient 拼在一起：

```css
.aurora {
  background:
    radial-gradient(34vmax 32vmax at 10% 4%, rgba(88,148,255,.62), transparent 62%),
    radial-gradient(30vmax 30vmax at 92% 0%, rgba(150,122,255,.55), transparent 60%),
    radial-gradient(38vmax 34vmax at 88% 84%, rgba(38,214,196,.45), transparent 62%);
  filter: blur(74px) saturate(150%);
}
```

### 第二层：模糊与饱和

```css
backdrop-filter: blur(26px) saturate(200%);
```

`blur` 让背后失焦，`saturate` 把被冲淡的颜色拉回来。只加 blur 会显得发灰，两个一起用才有"透过去看"的感觉。

### 第三层：边缘反光

玻璃的边缘会亮。用 1px 内阴影模拟：

```css
box-shadow:
  inset 0 1px 0 0 rgba(255,255,255,.95),   /* 顶部高光 */
  inset 0 -1px 0 0 rgba(255,255,255,.12);  /* 底部微弱反射 */
```

再加上一圈用 `mask-composite` 挖出来的渐变描边，四个角的亮度不一致，看起来才不像塑料。

### 第四层：内层斜向高光

这是最容易被忽略的一层。真实玻璃表面有方向性的反射，体现在 CSS 里就是一层从左上到右下的斜向渐变：

```css
background-image: linear-gradient(163deg,
  rgba(255,255,255,.6) 0%,
  rgba(255,255,255,.12) 38%,
  rgba(255,255,255,0) 64%);
```

加上这一层，卡片立刻从"白色方块"变成"有厚度的玻璃"。

> 四层缺任何一层都会退化。少第一层是白卡片，少第三层是毛玻璃贴纸，少第四层是塑料片。

## 主题切换

跟随系统，也可以手动覆盖。手动选择存在 `localStorage`，下次进来保持。

```css
:root { /* 浅色变量 */ }
@media (prefers-color-scheme: dark) { :root { /* 深色变量 */ } }
[data-theme="light"] { /* 手动覆盖 */ }
[data-theme="dark"]  { /* 手动覆盖 */ }
```

注意 `data-theme` 那两条必须写在媒体查询**之后**，否则优先级打不过。

## 几个小细节

**入场动画用 IntersectionObserver，不用滚动监听。** 滚动监听每一帧都在算位置，容易掉帧。观察器只在进入视口时触发一次，然后 `unobserve`。

**`prefers-reduced-motion` 必须处理。** 不是可选项——对前庭功能敏感的人来说，动效是真的会让人不适。

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .001ms !important;
    transition-duration: .001ms !important;
  }
}
```

**移动端不要用汉堡菜单。** 只有三个导航项的时候，平铺比藏起来更好找。空间不够就缩字号、隐藏站点名，别把导航塞进抽屉里。

## 性能

整个站没有外部请求：没有字体 CDN、没有图标库、没有分析脚本。字体用系统字体栈：

```css
font-family: -apple-system, "SF Pro Text", "Inter",
  "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
```

在 macOS 上是 SF Pro + 苹方，在 Windows 上是 Segoe UI + 微软雅黑。都不是"设计字体"，但都足够干净，而且**零加载时间**。

## 最后

这套东西的价值不在于技术含量，而在于**半年后我还看得懂**。

一个 CSS 文件、一个生成器、一个 Markdown 目录。想改配色就改文件顶部的变量，想写文章就新建一个 `.md`。

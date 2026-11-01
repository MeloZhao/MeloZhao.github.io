# MeloZhao.github.io

个人博客 —— 液态玻璃 / 简约科技风。
纯静态，零依赖，写 Markdown 就能发文章。

## 技术栈

- **无框架、无构建工具链**：HTML + CSS + 原生 JS
- **构建脚本**：`build.py`，只用 Python 标准库（不需要 `pip install` 任何东西）
- **部署**：GitHub Pages，直接托管生成后的静态文件

## 目录结构

```
.
├── build.py                  # 静态站点生成器
├── posts/                    # 文章源文件（Markdown）
│   └── xxx.md
├── templates/                # 预留（当前模板内联在 build.py）
├── assets/
│   ├── css/style.css         # 全部样式（设计系统在文件顶部变量区）
│   └── js/main.js            # 主题切换 / 入场动画 / TOC / 复制代码
├── blog/                     # ← 自动生成，勿手改
├── index.html                # ← 自动生成
├── about.html                # ← 自动生成
├── feed.xml / sitemap.xml    # ← 自动生成
└── .nojekyll                 # 告诉 GitHub Pages 不要跑 Jekyll
```

## 写一篇新文章

1. 在 `posts/` 下新建文件，例如 `posts/my-new-post.md`；
2. 文件头写 front matter：

```markdown
---
title: 文章标题
date: 2026-11-02
tags: 科研随笔, GROMACS
summary: 一句话摘要，会显示在列表页和 RSS 里。
---

正文从这里开始，正常写 Markdown 就行。
```

3. 本地构建并预览：

```bash
python3 build.py --serve   # → http://127.0.0.1:4000
```

4. 提交推送：

```bash
git add -A && git commit -m "post: 文章标题" && git push
```

## 本地预览（不构建）

```bash
python3 -m http.server 4000
```

## 设计说明

配色、圆角、模糊半径、字体栈全部集中在 `assets/css/style.css` 顶部的
`:root` 变量区，改一处全站生效。

| 变量 | 作用 |
| --- | --- |
| `--accent` / `--accent-2` / `--accent-3` | 主题渐变的三个色标 |
| `--glass` | 玻璃面板底色（浅色模式是白色低透明度） |
| `--glass-blur` | `backdrop-filter` 模糊半径 |
| `--glass-sheen` | 玻璃内层高光，决定"液态"感 |
| `--radius` / `--radius-lg` | 圆角尺度 |
| `--page` / `--page-grad` | 页面底色 |

主题跟随系统，右上角可手动切换，选择会记在 `localStorage`。

### 玻璃质感的四个要素

1. `backdrop-filter: blur() saturate()` —— 背景取色
2. 1px 半透明描边 + `inset 0 1px 0` 顶部高光 —— 边缘反光
3. `--glass-sheen` 斜向渐变 —— 内层高光
4. 低饱和多色背景（`.aurora`）—— 让模糊有东西可取

去掉任意一条，玻璃就会退化成"白色卡片"。

## 部署

GitHub Pages → Settings → Pages → Source 选 `Deploy from a branch`，
分支 `main`，目录 `/ (root)`。

`.nojekyll` 已包含，不用担心下划线目录被吞。

`build.py` 生成的所有页面都已提交到仓库，所以**不需要**在 CI 里构建也能访问。
改完文章记得本地跑一次 `python3 build.py` 再提交。

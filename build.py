#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Melo Zhao — 静态博客生成器
无第三方依赖，只用标准库。

用法:
    python3 build.py          # 构建整站
    python3 build.py --serve  # 构建并本地预览 (http://127.0.0.1:4000)

写作方式:
    在 posts/ 下新建 xxx.md，文件头写 front matter:

        ---
        title: 文章标题
        date: 2026-10-07
        tags: 科研随笔, GROMACS
        summary: 一句话摘要，会出现在列表页。
        ---

    正文用 Markdown 写，保存后重新 build 即可。
"""

import html
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
BLOG_DIR = ROOT / "blog"

# ---------------------------------------------------------------- site config
SITE = {
    "name": "Melo Zhao",
    "name_cn": "赵某人",
    "role": "计算蛋白工程师",
    "url": "https://melozhao.github.io",
    "desc": "计算蛋白工程 · 酶设计 · 分子动力学 · AI 蛋白设计",
    "github": "https://github.com/MeloZhao",
    "email": "melozhao@example.com",
    "start_year": 2026,
}

NAV = [
    ("index.html", "首页"),
    ("blog/index.html", "博客"),
    ("about.html", "关于"),
]

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E"
    "%3Cstop offset='0' stop-color='%230a6cff'/%3E"
    "%3Cstop offset='.55' stop-color='%236d4bff'/%3E"
    "%3Cstop offset='1' stop-color='%2300c2b2'/%3E%3C/linearGradient%3E%3C/defs%3E"
    "%3Crect width='64' height='64' rx='16' fill='url(%23g)'/%3E"
    "%3Ctext x='32' y='45' font-family='-apple-system,Helvetica,sans-serif' "
    "font-size='36' font-weight='600' fill='%23fff' text-anchor='middle'%3EM%3C/text%3E%3C/svg%3E"
)

# ---------------------------------------------------------------- tiny markdown


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(text: str) -> str:
    """行内标记：code / 图片 / 链接 / 粗体 / 斜体"""
    stash = []

    def keep(fragment):
        stash.append(fragment)
        return "\x00%d\x00" % (len(stash) - 1)

    # 行内代码优先，避免内部被当作标记
    text = re.sub(r"`([^`]+)`", lambda m: keep("<code>%s</code>" % esc(m.group(1))), text)
    # 图片
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)",
        lambda m: keep(
            '<img src="%s" alt="%s"%s loading="lazy">'
            % (
                esc(m.group(2)),
                esc(m.group(1)),
                ' title="%s"' % esc(m.group(3)) if m.group(3) else "",
            )
        ),
        text,
    )
    # 链接
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)",
        lambda m: keep(
            '<a href="%s"%s>%s</a>'
            % (
                esc(m.group(2)),
                ' title="%s"' % esc(m.group(3)) if m.group(3) else "",
                m.group(1),
            )
        ),
        text,
    )
    # 转义其余部分
    text = esc(text)
    # 粗体 / 斜体 / 删除线
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    # 恢复
    for i, frag in enumerate(stash):
        text = text.replace("\x00%d\x00" % i, frag)
    return text


def slugify_heading(text: str, used: dict) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    plain = re.sub(r"[`*_~]", "", plain)
    base = "h-" + re.sub(r"[^\w\u4e00-\u9fa5]+", "-", plain.strip()).strip("-").lower()
    if not base or base == "h-":
        base = "section"
    n = used.get(base, 0)
    used[base] = n + 1
    return base if n == 0 else "%s-%d" % (base, n)


def render_md(md: str):
    """返回 (html, toc[list of (level, id, text)])"""
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    toc = []
    used = {}
    i = 0
    n = len(lines)

    para = []

    def flush_para():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para).strip()))
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip() or "text"
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            code = esc("\n".join(buf))
            out.append(
                '<div class="codeblock"><div class="codeblock-top">'
                '<span>%s</span><button class="copy-btn" type="button">COPY</button>'
                '</div><pre><code>%s</code></pre></div>' % (esc(lang), code)
            )
            continue

        # 空行
        if not stripped:
            flush_para()
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            text = m.group(2).strip()
            hid = slugify_heading(text, used)
            toc.append((level, hid, re.sub(r"<[^>]+>", "", inline(text))))
            out.append(
                '<h%d id="%s">%s</h%d>' % (level, hid, inline(text), level)
            )
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            flush_para()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            inner = " ".join(buf)
            out.append("<blockquote><p>%s</p></blockquote>" % inline(inner))
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < n and re.match(
            r"^\|[\s:\-|]+\|$", lines[i + 1].strip()
        ):
            flush_para()
            head = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join("<th>%s</th>" % inline(c) for c in head)
            tbody = "".join(
                "<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows
            )
            out.append(
                '<div class="table-wrap"><table><thead><tr>%s</tr></thead>'
                "<tbody>%s</tbody></table></div>" % (thead, tbody)
            )
            continue

        # 列表
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            flush_para()
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            items = []
            while i < n:
                cur = lines[i].strip()
                mm = re.match(r"^([-*+]|\d+\.)\s+(.*)$", cur)
                if mm:
                    items.append([mm.group(2)])
                    i += 1
                elif cur and lines[i].startswith(("  ", "\t")) and items:
                    items[-1].append(cur)
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            body = "".join(
                "<li>%s</li>" % inline(" ".join(parts).strip()) for parts in items
            )
            out.append("<%s>%s</%s>" % (tag, body, tag))
            continue

        # 原始 HTML 块（以 < 开头且不是行内标签）
        if re.match(r"^<[a-zA-Z!/]", stripped):
            flush_para()
            buf = []
            while i < n and lines[i].strip():
                buf.append(lines[i])
                i += 1
            out.append("\n".join(buf))
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out), toc


# ---------------------------------------------------------------- posts


def parse_front_matter(raw: str):
    meta, body = {}, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            block, body = parts[1], parts[2]
            for line in block.strip().split("\n"):
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k == "tags":
                    meta[k] = [t.strip() for t in re.split(r"[,，]", v) if t.strip()]
                else:
                    meta[k] = v.strip('"').strip("'")
    return meta, body.strip()


def reading_time(text: str) -> int:
    cn = len(re.findall(r"[\u4e00-\u9fa5]", text))
    en = len(re.findall(r"[A-Za-z]+", text))
    return max(1, round(cn / 380 + en / 210))


def load_posts():
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for f in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        content, toc = render_md(body)
        date_str = meta.get("date", "1970-01-01")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime(1970, 1, 1)
        posts.append(
            {
                "slug": f.stem,
                "title": meta.get("title", f.stem),
                "date": dt,
                "date_str": dt.strftime("%Y.%m.%d"),
                "date_iso": dt.strftime("%Y-%m-%d"),
                "tags": meta.get("tags", []),
                "summary": meta.get("summary", ""),
                "minutes": reading_time(body),
                "content": content,
                "toc": [(lv, hid, tx) for lv, hid, tx in toc if 2 <= lv <= 3],
            }
        )
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


# ---------------------------------------------------------------- layout


def nav_html(prefix: str, active: str):
    items = []
    for href, label in NAV:
        cls = ' class="is-active"' if href == active else ""
        items.append('<a href="%s%s"%s>%s</a>' % (prefix, href, cls, label))
    return """
<header class="nav-shell">
  <nav class="nav" aria-label="主导航">
    <a class="brand" href="%sindex.html">
      <span class="brand-mark">M</span>
      <span>%s</span>
    </a>
    <div class="nav-links">%s</div>
    <button class="theme-toggle" type="button" aria-label="切换主题">
      <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
      </svg>
      <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
      </svg>
    </button>
  </nav>
</header>""" % (prefix, SITE["name"], "".join(items))


def page_shell(title, desc, body, prefix, active, extra_head=""):
    full_title = title if title == SITE["name"] else "%s — %s" % (title, SITE["name"])
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>%s</title>
<meta name="description" content="%s">
<meta name="theme-color" content="#e9eef7">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:type" content="website">
<link rel="icon" href="%s">
<link rel="stylesheet" href="%sassets/css/style.css">
%s
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div class="gridlines" aria-hidden="true"></div>
<div class="grain" aria-hidden="true"></div>
%s
%s
<footer class="footer">
  <div class="wrap footer-inner">
    <span class="footer-copy">© %d %s · 少吹牛，多跑程序</span>
    <div class="footer-links">
      <a href="%sblog/index.html">全部文章</a>
      <a href="%sabout.html">关于</a>
      <a href="%s" target="_blank" rel="noopener">GitHub ↗</a>
    </div>
  </div>
</footer>
<script src="%sassets/js/main.js" defer></script>
</body>
</html>
""" % (
        full_title,
        desc,
        full_title,
        desc,
        FAVICON,
        prefix,
        extra_head,
        nav_html(prefix, active),
        body,
        SITE["start_year"],
        SITE["name"],
        prefix,
        prefix,
        SITE["github"],
        prefix,
    )


def post_card(p: dict, prefix: str = "") -> str:
    tags = "".join('<span class="tag">%s</span>' % esc(t) for t in p["tags"][:2])
    return """<a class="card post-card reveal" href="%sblog/%s.html" data-tags="%s">
  <div class="post-card-body">
    <div class="post-meta">
      <time datetime="%s">%s</time><span class="dot"></span><span>%d min</span>%s
    </div>
    <h3>%s</h3>
    <p>%s</p>
  </div>
  <span class="post-card-arrow" aria-hidden="true">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6"/>
    </svg>
  </span>
</a>""" % (
        prefix,
        p["slug"],
        esc("|".join(p["tags"])),
        p["date_iso"],
        p["date_str"],
        p["minutes"],
        tags,
        esc(p["title"]),
        esc(p["summary"]),
    )


# ---------------------------------------------------------------- pages


def build_index(posts):
    latest = posts[:3]
    cards = "\n".join(post_card(p) for p in latest)

    body = """
<main class="page">
  <section class="hero">
    <div class="wrap hero-grid">
      <div>
        <span class="status-pill reveal"><span class="status-dot"></span>现在在折腾分子模拟、结构预测和自动化脚本</span>
        <h1 class="hero-title reveal" data-delay="1">
          在原子尺度上，<br><span class="grad">造一点新东西。</span>
        </h1>
        <p class="hero-sub reveal" data-delay="2">
          我是 Melo Zhao，一名计算蛋白工程师。白天跑分子动力学、写设计脚本，
          晚上把这些折腾记录成文。这里是我的公开笔记：酶设计、环化、
          结构预测，以及所有「能自动化就绝不手动」的琐碎经验。
        </p>
        <div class="hero-actions reveal" data-delay="3">
          <a class="btn btn-primary" href="blog/index.html">
            读点东西
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </a>
          <a class="btn btn-glass" href="https://github.com/MeloZhao" target="_blank" rel="noopener">GitHub ↗</a>
        </div>
      </div>
      <div class="orb-wrap reveal" data-delay="2" aria-hidden="true">
        <div class="orb-ring"></div>
        <div class="orb"><span class="orb-initial">M</span></div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head reveal">
        <div>
          <p class="eyebrow">Writing</p>
          <h2 class="section-title">最近写了什么</h2>
          <p class="section-desc">踩过的坑、跑通的流程、读过的论文，都在这儿。</p>
        </div>
        <a class="link-arrow" href="blog/index.html">全部文章
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </a>
      </div>
      <div class="post-list">%s</div>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head reveal">
        <div>
          <p class="eyebrow">Toolchain</p>
          <h2 class="section-title">常用工具链</h2>
          <p class="section-desc">能用就用，能串起来就别一个个点。</p>
        </div>
      </div>
      <div class="toolband reveal">
        <div class="tooltrack">%s%s</div>
      </div>
    </div>
  </section>
</main>
""" % (
        cards,
        "".join('<span>%s</span>' % t for t in TOOLS),
        "".join('<span>%s</span>' % t for t in TOOLS),
    )

    return page_shell(
        SITE["name"],
        SITE["desc"] + "。" + SITE["name_cn"] + "的个人博客与技术笔记。",
        body,
        "",
        "index.html",
    )


TOOLS = [
    "GROMACS", "AlphaFold", "RoseTTAFold3", "ProteinMPNN", "LigandMPNN",
    "Rosetta", "FoldX", "AutoDock", "DiffDock", "PyMOL", "MDAnalysis",
    "NetworkX", "Gaussian", "Multiwfn", "Python", "Snakemake", "Nextflow",
    "PyTorch", "NumPy", "Git",
]


def build_blog_index(posts):
    tags = []
    for p in posts:
        for t in p["tags"]:
            if t not in tags:
                tags.append(t)
    filters = ['<button class="filter-btn is-on" type="button" data-filter="all">全部 %d</button>' % len(posts)]
    for t in tags:
        filters.append(
            '<button class="filter-btn" type="button" data-filter="%s">%s</button>'
            % (esc(t), esc(t))
        )

    cards = "\n".join(post_card(p) for p in posts)

    body = """
<main class="page">
  <div class="wrap">
    <div class="page-head">
      <p class="eyebrow">Archive</p>
      <h1 class="page-title">全部文章</h1>
      <p class="page-lede">科研随笔、代码脚本、论文阅读，以及一些和科研没什么关系的东西。目前共 %d 篇。</p>
    </div>
    <div class="filter-bar">%s</div>
    <div class="post-list">%s</div>
    <p class="empty-state" style="display:none">这个标签下还没有文章。</p>
  </div>
</main>
""" % (
        len(posts),
        "".join(filters),
        cards,
    )

    return page_shell("全部文章", "Melo Zhao 的全部文章归档。", body, "../", "blog/index.html")


def build_post(posts, idx):
    p = posts[idx]
    prev_p = posts[idx + 1] if idx + 1 < len(posts) else None
    next_p = posts[idx - 1] if idx > 0 else None

    toc_html = ""
    if p["toc"]:
        items = "".join(
            '<a class="lvl-%d" href="#%s">%s</a>' % (lv, hid, esc(tx))
            for lv, hid, tx in p["toc"]
        )
        toc_html = (
            '<aside class="toc"><p class="toc-title">On this page</p>%s</aside>' % items
        )

    nav_parts = []
    if prev_p:
        nav_parts.append(
            '<a class="prev" href="../blog/%s.html"><small>← 上一篇</small><strong>%s</strong></a>'
            % (prev_p["slug"], esc(prev_p["title"]))
        )
    if next_p:
        nav_parts.append(
            '<a class="next" href="../blog/%s.html"><small>下一篇 →</small><strong>%s</strong></a>'
            % (next_p["slug"], esc(next_p["title"]))
        )
    postnav = (
        '<nav class="postnav">%s</nav>' % "".join(nav_parts) if nav_parts else ""
    )

    tags = "".join('<span class="tag">%s</span>' % esc(t) for t in p["tags"])

    body = """
<div class="progress" aria-hidden="true"></div>
<main class="wrap">
  <article class="article-wrap">
    <div>
      <header class="article-head">
        <div class="article-meta">
          <time datetime="%s">%s</time><span class="dot"></span><span>%d 分钟阅读</span>%s
        </div>
        <h1 class="article-title">%s</h1>
        <div class="article-hero-rule"></div>
      </header>
      <div class="prose">%s</div>
      %s
    </div>
    %s
  </article>
</main>
""" % (
        p["date_iso"],
        p["date_str"],
        p["minutes"],
        tags,
        esc(p["title"]),
        p["content"],
        postnav,
        toc_html,
    )

    return page_shell(p["title"], p["summary"] or p["title"], body, "../", "blog/index.html")


def build_about():
    body = """
<main class="page">
  <div class="wrap">
    <div class="page-head">
      <p class="eyebrow">About</p>
      <h1 class="page-title">一个不太正经的<br>计算蛋白工程师。</h1>
      <p class="page-lede">主要折腾计算蛋白工程、酶设计、蛋白质环化、分子动力学，以及 AI 驱动的蛋白设计。</p>
    </div>

    <div class="about-grid">
      <section class="panel reveal">
        <h2>我在干什么</h2>
        <p>我的日常是把<strong>结构</strong>、<strong>序列</strong>和<strong>实验</strong>这三件事缝起来：从 PDB 里挑骨架，用 ProteinMPNN 生成序列，AlphaFold / RF3 预测回来，再拿几何和能量指标筛一遍。</p>
        <p>平时喜欢把各种程序串起来，把重复工作自动化，再把计算结果整理成<strong>真正能拿去做实验的候选</strong>——不是一堆好看的图，而是能下单的序列。</p>
        <p>这个网站是我的公开笔记本。写下来的东西才算真的想明白了。</p>
      </section>

      <aside class="panel reveal" data-delay="1">
        <h2>基本原则</h2>
        <ul class="principle-list">
          <li>少吹牛，多跑程序。</li>
          <li>先看证据，再下结论。</li>
          <li>能自动化，就不手动。</li>
          <li>能复现，就别只截图。</li>
          <li>报错了先读日志。</li>
        </ul>
      </aside>
    </div>

    <section class="section">
      <div class="section-head reveal">
        <div>
          <p class="eyebrow">Focus</p>
          <h2 class="section-title">科研路线</h2>
        </div>
      </div>
      <div class="panel reveal">
        <div class="timeline">
          <div class="tl-item"><b>Protein Engineering</b><span>结构 → 序列 → 候选，一条能跑通的链路。</span></div>
          <div class="tl-item"><b>Protein Cyclization</b><span>环化设计 → 结构筛选 → 稳定性验证。</span></div>
          <div class="tl-item"><b>Molecular Dynamics</b><span>轨迹 → 动力学 → 机制解释，200 ns 起步。</span></div>
          <div class="tl-item"><b>Design Systems</b><span>工具 → Workflow → 可部署平台。</span></div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head reveal">
        <div>
          <p class="eyebrow">Contact</p>
          <h2 class="section-title">想聊点什么</h2>
          <p class="section-desc">合作、提问、或者只是想指出我哪里写错了，都欢迎。</p>
        </div>
      </div>
      <div class="grid-2">
        <a class="card project-card reveal" href="https://github.com/MeloZhao" target="_blank" rel="noopener">
          <div class="project-top">
            <span class="project-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 19c-4 1.5-4-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.3 4.3 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6 0C6.8 2.8 5.8 3.1 5.8 3.1a4.3 4.3 0 0 0-.1 3.2A4.6 4.6 0 0 0 4.4 9.5c0 4.6 2.7 5.7 5.5 6-.4.4-.6.9-.6 1.5V21"/></svg></span>
            <span class="badge-live">GitHub</span>
          </div>
          <h3>@MeloZhao</h3>
          <p>代码、脚本、还没写完的项目都在这里。</p>
        </a>
        <a class="card project-card reveal" data-delay="1" href="blog/index.html">
          <div class="project-top">
            <span class="project-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg></span>
          </div>
          <h3>读我的笔记</h3>
          <p>踩过的坑、跑通的流程、读过的论文。</p>
        </a>
      </div>
    </section>
  </div>
</main>
"""
    return page_shell("关于", "关于 Melo Zhao：计算蛋白工程师。", body, "", "about.html")


def build_feed(posts):
    items = []
    for p in posts:
        items.append(
            """  <item>
    <title>%s</title>
    <link>%s/blog/%s.html</link>
    <guid>%s/blog/%s.html</guid>
    <pubDate>%s</pubDate>
    <description>%s</description>
  </item>"""
            % (
                esc(p["title"]),
                SITE["url"],
                p["slug"],
                SITE["url"],
                p["slug"],
                p["date"].strftime("%a, %d %b %Y 00:00:00 +0800"),
                esc(p["summary"]),
            )
        )
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>%s</title>
  <link>%s</link>
  <description>%s</description>
  <language>zh-CN</language>
%s
</channel>
</rss>
""" % (SITE["name"], SITE["url"], SITE["desc"], "\n".join(items))


def build_sitemap(posts):
    urls = ["", "about.html", "blog/index.html"]
    urls += ["blog/%s.html" % p["slug"] for p in posts]
    body = "".join(
        "  <url><loc>%s/%s</loc></url>\n" % (SITE["url"], u) for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "%s</urlset>\n" % body
    )


# ---------------------------------------------------------------- main


def main():
    posts = load_posts()
    if not BLOG_DIR.exists():
        BLOG_DIR.mkdir(parents=True)

    (ROOT / "index.html").write_text(build_index(posts), encoding="utf-8")
    (ROOT / "about.html").write_text(build_about(), encoding="utf-8")
    (BLOG_DIR / "index.html").write_text(build_blog_index(posts), encoding="utf-8")

    for i, p in enumerate(posts):
        (BLOG_DIR / ("%s.html" % p["slug"])).write_text(
            build_post(posts, i), encoding="utf-8"
        )

    (ROOT / "feed.xml").write_text(build_feed(posts), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(build_sitemap(posts), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    # 清理已删除文章的残留页面
    keep = {"index.html"} | {"%s.html" % p["slug"] for p in posts}
    for f in BLOG_DIR.glob("*.html"):
        if f.name not in keep:
            f.unlink()

    print("✓ 构建完成：%d 篇文章" % len(posts))
    for p in posts:
        print("  · blog/%s.html  %s" % (p["slug"], p["title"]))
    print("  · index.html / about.html / blog/index.html")


if __name__ == "__main__":
    main()
    if "--serve" in sys.argv:
        import http.server
        import socketserver

        os.chdir(ROOT)
        port = 4000
        handler = http.server.SimpleHTTPRequestHandler
        print("\n→ http://127.0.0.1:%d\n" % port)
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            httpd.serve_forever()

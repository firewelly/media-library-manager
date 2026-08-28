#!/usr/bin/env python3
"""将 openwiki/ 目录下的 Markdown 文档批量转换为统一风格的 HTML。

- 读取 openwiki/ 下所有 .md 文件（含子目录）
- 使用 Python markdown 库转换，支持表格、代码块、任务列表等扩展
- 输出到 doc/openwiki_html/，保持目录结构
- macOS 浅色风格（毛玻璃 + 圆角卡片），数据元素采用 seaborn deep 色板
"""
import os
import re
import markdown

WIKI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openwiki")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doc", "openwiki_html")

# seaborn deep 色板，用于徽章、图表等数据元素
SEABORN_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]

CSS = """
:root {
    --primary: #0071e3;
    --bg: #f5f5f7;
    --bg-card: #ffffff;
    --text: #1d1d1f;
    --text-muted: #6e6e73;
    --border: #d2d2d7;
    --code-bg: rgba(76, 114, 176, 0.08);
    --sn-blue: #4C72B0;
    --sn-orange: #DD8452;
    --sn-green: #55A868;
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.04);
    --shadow-md: 0 2px 6px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.06);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.8;
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem 2rem 4rem;
    -webkit-font-smoothing: antialiased;
}
h1 {
    color: var(--text);
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 1.5rem;
    border-bottom: 2px solid var(--border);
    padding-bottom: 0.6rem;
}
h2 {
    color: var(--text);
    font-size: 1.55rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 2.4rem 0 1rem;
    border-left: 4px solid var(--sn-blue);
    padding-left: 0.8rem;
}
h3 {
    color: var(--text);
    font-size: 1.2rem;
    font-weight: 600;
    margin: 1.6rem 0 0.8rem;
}
h4, h5, h6 {
    color: var(--text);
    font-weight: 600;
    margin: 1.2rem 0 0.6rem;
}
p { margin: 0.8rem 0; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote {
    background: rgba(76, 114, 176, 0.06);
    border-left: 4px solid var(--sn-blue);
    padding: 0.8rem 1.2rem;
    margin: 1.2rem 0;
    border-radius: 0 8px 8px 0;
    color: var(--text-muted);
}
code {
    background: var(--code-bg);
    color: var(--sn-blue);
    padding: 2px 6px;
    border-radius: 5px;
    font-family: 'SF Mono', 'Fira Code', Menlo, Consolas, monospace;
    font-size: 0.88em;
}
pre {
    background: #f6f8fa;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    overflow-x: auto;
    margin: 1rem 0;
}
pre code {
    background: none;
    color: var(--text);
    padding: 0;
    font-size: 0.85em;
}
table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 1.2rem 0;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    font-size: 0.95em;
    box-shadow: var(--shadow-sm);
}
th {
    background: rgba(76, 114, 176, 0.08);
    color: var(--sn-blue);
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    white-space: nowrap;
}
td {
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    vertical-align: top;
}
tr:hover td { background: rgba(76, 114, 176, 0.04); }
ul, ol { margin: 0.8rem 0; padding-left: 1.8rem; }
li { margin: 0.4rem 0; }
hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2rem 0;
}
/* 面包屑导航（macOS 毛玻璃） */
.nav {
    display: block;
    position: sticky;
    top: 0.8rem;
    z-index: 100;
    background: rgba(255, 255, 255, 0.72);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    backdrop-filter: saturate(180%) blur(20px);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.7rem 1.2rem;
    margin-bottom: 1.5rem;
    font-size: 0.9em;
    color: var(--text-muted);
    box-shadow: var(--shadow-sm);
}
.nav a { margin-right: 0.4rem; }
/* 首页大卡片 */
.hero {
    background: linear-gradient(135deg, rgba(76, 114, 176, 0.10), rgba(100, 181, 205, 0.05) 55%, rgba(221, 132, 82, 0.06));
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
    box-shadow: var(--shadow-md);
}
.hero h1 { border-bottom: none; margin-bottom: 0.5rem; }
.hero p { color: var(--text-muted); }
/* 索引目录 */
.idx {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem;
    margin: 1.5rem 0;
}
.idx-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.idx-card:hover {
    border-color: var(--sn-blue);
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
.idx-card h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.idx-card p { color: var(--text-muted); font-size: 0.9em; margin: 0.3rem 0; }
.badge {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.75em;
    font-weight: 600;
    margin-right: 4px;
}
.footer {
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.85em;
    text-align: center;
}
@media (max-width: 768px) {
    body { padding: 1rem; }
    h1 { font-size: 1.6rem; }
    h2 { font-size: 1.3rem; }
    table { font-size: 0.85em; display: block; overflow-x: auto; }
}
"""


def parse_front_matter(content: str):
    """解析 YAML front matter，返回 (meta_dict, markdown_body)。"""
    if content.startswith("---"):
        lines = content.split("\n")
        # 找第二个 ---
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = "\n".join(lines[1:i])
                body = "\n".join(lines[i + 1:])
                meta = {}
                for line in fm.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        meta[key.strip()] = val.strip().strip('"').strip("'")
                return meta, body
    return {}, content


def title_from_meta(meta, rel_path):
    """优先取 front matter 的 title，否则从文件内容提取第一个 # 标题。"""
    if meta.get("title"):
        return meta["title"]
    return rel_path


def get_nav_path(rel_path: str) -> str:
    """生成面包屑导航。"""
    parts = rel_path.replace(".md", "").split(os.sep)
    crumbs = ['<a href="../index.html">首页</a>']
    current = []
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            crumbs.append(f'<span>› {part}</span>')
        else:
            current.append(part)
            depth = len(parts) - i - 1
            prefix = "../" * depth
            crumbs.append(f'<a href="{prefix}{part}/index.html">{part}</a>')
    return '<span class="nav">' + " ".join(crumbs) + "</span>"


def convert_file(md_path: str, rel_path: str):
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    meta, body = parse_front_matter(content)
    # 相对路径链接处理：md 内部的相对链接（如 main_application/overview.md）指向 .md
    # 在 HTML 中应指向 .html。保持相对路径不变（目录结构一致），仅替换扩展名
    # 排除 http(s)、锚点、mailto 等外部/特殊链接
    body = re.sub(
        r"\]\((?![\w]+:)([^)#]+?)\.md(#[^)]*)?\)",
        lambda m: f"]({m.group(1)}.html{m.group(2) or ''})",
        body,
    )
    # 先将 mermaid 代码块替换为占位符，防止 markdown 库误解析
    mermaid_blocks = []
    def stash_mermaid(m):
        mermaid_blocks.append(m.group(1))
        return f'\n\n<div class="mdx-mermaid-placeholder-{len(mermaid_blocks)-1}"></div>\n\n'
    body = re.sub(r"```mermaid\n(.*?)```", stash_mermaid, body, flags=re.DOTALL)

    html_body = markdown.markdown(
        body,
        extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists"],
    )

    # 恢复 mermaid 代码块为 <pre class="mermaid">
    def restore_mermaid(m):
        idx = int(m.group(1))
        code = mermaid_blocks[idx]
        # HTML 转义
        import html as html_mod
        return f'<pre class="mermaid">{html_mod.escape(code)}</pre>'
    html_body = re.sub(
        r'<div class="mdx-mermaid-placeholder-(\d+)"></div>',
        restore_mermaid,
        html_body,
    )

    title = title_from_meta(meta, rel_path)
    out_path = os.path.join(OUT_DIR, rel_path.replace(".md", ".html"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # 相对路径计算
    depth = len(rel_path.split(os.sep)) - 1
    rel_prefix = "../" * depth
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 媒体库文档</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>{CSS}
.mermaid {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.5rem;
    margin: 1.2rem 0;
    overflow-x: auto;
    text-align: center;
}}
.mermaid svg {{
    max-width: 100%;
    height: auto;
}}
</style>
</head>
<body>
{get_nav_path(rel_path)}
<h1>{title}</h1>
{html_body}
<div class="footer">
<p>由 OpenWiki 生成 · Media Library Management System</p>
</div>
<script>
mermaid.initialize({{
    startOnLoad: true,
    theme: 'base',
    themeVariables: {{
        primaryColor: '#dbe5f3',
        primaryTextColor: '#1d1d1f',
        primaryBorderColor: '#4C72B0',
        lineColor: '#6e6e73',
        secondaryColor: '#f8e4d5',
        secondaryTextColor: '#1d1d1f',
        secondaryBorderColor: '#DD8452',
        tertiaryColor: '#e2efe5',
        tertiaryTextColor: '#1d1d1f',
        tertiaryBorderColor: '#55A868',
        clusterBkg: '#f5f5f7',
        clusterBorder: '#d2d2d7',
        edgeLabelBackground: '#ffffff',
        fontFamily: '-apple-system, "PingFang SC", sans-serif'
    }}
}});
</script>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def build_index():
    """生成首页索引，列出所有文档。徽章按目录使用 seaborn 色板着色。"""
    entries = []
    for root, _, files in os.walk(WIKI_DIR):
        for fn in sorted(files):
            if not fn.endswith(".md") or fn == "_skeleton.md":
                continue
            rel_path = os.path.relpath(os.path.join(root, fn), WIKI_DIR)
            with open(os.path.join(root, fn), encoding="utf-8") as f:
                meta, _ = parse_front_matter(f.read())
            entries.append((rel_path, meta.get("title", rel_path), meta.get("description", "")))
    # 目录 → seaborn 颜色映射（稳定顺序）
    dirs = sorted({os.path.dirname(rel) or "root" for rel, _, _ in entries})
    dir_colors = {d: SEABORN_PALETTE[i % len(SEABORN_PALETTE)] for i, d in enumerate(dirs)}
    cards = []
    for rel_path, title, desc in entries:
        dirname = os.path.dirname(rel_path) or "root"
        color = dir_colors[dirname]
        cards.append(f'''<div class="idx-card">
<h3><a href="{rel_path.replace('.md', '.html')}">{title}</a></h3>
<p>{desc}</p>
<span class="badge" style="background: {color}1f; color: {color};">{dirname}</span>
</div>''')
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>媒体库管理系统 - 文档索引</title>
<style>{CSS}</style>
</head>
<body>
<div class="hero">
<h1>媒体库管理系统</h1>
<p>OpenWiki 自动生成的完整项目文档 · 中英对照 · 共 {len(cards)} 个页面</p>
</div>
<div class="idx">
{"".join(cards)}
</div>
<div class="footer">
<p>由 OpenWiki 扫描代码库自动生成 · Media Library Management System</p>
</div>
</body>
</html>"""
    index_path = os.path.join(OUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    return index_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for root, _, files in os.walk(WIKI_DIR):
        for fn in sorted(files):
            if not fn.endswith(".md") or fn == "_skeleton.md":
                continue
            md_path = os.path.join(root, fn)
            rel_path = os.path.relpath(md_path, WIKI_DIR)
            convert_file(md_path, rel_path)
            count += 1
    index = build_index()
    print(f"转换完成：{count} 个页面")
    print(f"输出目录：{OUT_DIR}")
    print(f"索引页：{index}")


if __name__ == "__main__":
    main()

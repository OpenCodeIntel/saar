#!/usr/bin/env python3
"""Convert rl_technical_report.md → rl_technical_report.html (print-to-PDF ready).

Usage:
    python3 docs/generate_pdf.py
    # Then open docs/rl_technical_report.html in Chrome
    # and press Cmd+P → Destination: Save as PDF → Save
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

SRC = Path(__file__).parent / "rl_technical_report.md"
OUT = Path(__file__).parent / "rl_technical_report.html"


def md_to_html(md: str) -> str:
    """Minimal Markdown → HTML converter (no deps)."""
    lines = md.split("\n")
    html_lines: list[str] = []
    in_code = False
    in_table = False
    in_list = False

    def inline(text: str) -> str:
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Links
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                lang = line[3:].strip() or ""
                cls = f' class="language-{lang}"' if lang else ""
                html_lines.append(f"<pre><code{cls}>")
                in_code = True
            i += 1
            continue

        if in_code:
            html_lines.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            i += 1
            continue

        # Tables
        if "|" in line and line.strip().startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                html_lines.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                i += 1
                # skip separator row
                if i < len(lines) and re.match(r"[\|\s\-:]+$", lines[i]):
                    i += 1
                continue
            else:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                html_lines.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
                continue
        elif in_table:
            html_lines.append("</tbody></table>")
            in_table = False

        # Headings
        if line.startswith("### "):
            html_lines.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{inline(line[2:])}</h1>")
        # Horizontal rule
        elif line.strip() in ("---", "***", "___"):
            html_lines.append("<hr>")
        # Unordered list
        elif re.match(r"^(\d+)\. ", line):
            if not in_list:
                html_lines.append("<ol>")
                in_list = "ol"
            html_lines.append(f"<li>{inline(re.sub(r'^\d+\. ', '', line))}</li>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = "ul"
            html_lines.append(f"<li>{inline(line[2:])}</li>")
        else:
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = False
            if line.strip() == "":
                html_lines.append("<br>")
            else:
                html_lines.append(f"<p>{inline(line)}</p>")

        i += 1

    if in_table:
        html_lines.append("</tbody></table>")
    if in_list:
        html_lines.append(f"</{in_list}>")
    if in_code:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.65;
    color: #1a1a1a;
    max-width: 860px;
    margin: 0 auto;
    padding: 48px 56px;
    background: #fff;
}
h1 {
    font-size: 22pt;
    font-weight: 700;
    margin-bottom: 4px;
    border-bottom: 3px solid #1a1a1a;
    padding-bottom: 10px;
    margin-top: 20px;
}
h2 {
    font-size: 15pt;
    font-weight: 700;
    margin-top: 32px;
    margin-bottom: 10px;
    border-bottom: 1.5px solid #888;
    padding-bottom: 4px;
    color: #111;
}
h3 {
    font-size: 12pt;
    font-weight: 700;
    margin-top: 20px;
    margin-bottom: 8px;
    color: #222;
}
p { margin-bottom: 10px; }
br { display: block; margin: 4px 0; }
hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 28px 0;
}
pre {
    background: #f4f4f4;
    border: 1px solid #ddd;
    border-left: 4px solid #2563eb;
    padding: 14px 16px;
    font-family: 'Menlo', 'Courier New', monospace;
    font-size: 9.5pt;
    line-height: 1.5;
    overflow-x: auto;
    margin: 14px 0;
    border-radius: 4px;
    white-space: pre-wrap;
}
code {
    font-family: 'Menlo', 'Courier New', monospace;
    font-size: 9.5pt;
    background: #f0f0f0;
    padding: 1px 4px;
    border-radius: 3px;
}
pre code {
    background: none;
    padding: 0;
    font-size: inherit;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 10pt;
}
th {
    background: #1a1a1a;
    color: #fff;
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #e0e0e0;
}
tr:nth-child(even) td { background: #f9f9f9; }
ul, ol {
    margin: 10px 0 10px 24px;
}
li { margin-bottom: 4px; }
a { color: #2563eb; text-decoration: none; }
strong { font-weight: 700; }
em { font-style: italic; }

/* Cover block */
.cover {
    border: 2px solid #1a1a1a;
    padding: 32px 40px;
    margin-bottom: 40px;
    background: #fafafa;
}
.cover h1 { border: none; font-size: 20pt; margin: 0 0 8px 0; }
.cover .subtitle { font-size: 13pt; color: #444; margin-bottom: 20px; }
.cover table { margin: 0; font-size: 10.5pt; }
.cover th { background: #444; }

/* Print */
@media print {
    body { padding: 0; max-width: 100%; }
    pre { page-break-inside: avoid; }
    h2 { page-break-before: auto; }
    table { page-break-inside: avoid; }
}
"""

COVER_HTML = """
<div class="cover">
  <h1>Reinforcement Learning for Adaptive Codebase Analysis</h1>
  <div class="subtitle">Technical Report &mdash; saar RL Layer</div>
  <table>
    <tr><td><strong>Author</strong></td><td>Devanshu</td></tr>
    <tr><td><strong>Project</strong></td><td>saar &mdash; Codebase DNA extractor</td></tr>
    <tr><td><strong>GitHub</strong></td><td><a href="https://github.com/OpenCodeIntel/saar">github.com/OpenCodeIntel/saar</a></td></tr>
    <tr><td><strong>Course</strong></td><td>Reinforcement Learning for Agentic AI Systems</td></tr>
    <tr><td><strong>Date</strong></td><td>April 2026</td></tr>
  </table>
</div>
"""

ARCH_DIAGRAM_HTML = """
<div style="background:#f4f4f4;border:1px solid #ddd;border-left:4px solid #2563eb;
     padding:18px 20px;margin:14px 0;border-radius:4px;font-family:'Menlo','Courier New',monospace;
     font-size:9pt;line-height:1.7;white-space:pre;">
saar extract . --rl
        │
        ▼
  DNAExtractor ──► CodebaseDNA
                        │
                        ▼
              StateEncoder (20-D float32)
              [lang mix | framework flags | scale | structural | tribal]
                        │
                        ▼
              ┌─────────────────────────────────┐
              │     EnsembleAgent               │
              │   Thompson Sampling             │
              │   Beta(α,β) per sub-agent       │
              └──────┬──────────────┬───────────┘
                     │              │
              UCBBandit        REINFORCEAgent
              6-context         20→32→8 MLP
              UCB1              ReLU + Softmax
                     │              │
                     └──────┬───────┘
                     action: profile 0–7
                            │
                   PROFILES[action]
                   (depth multipliers)
                            │
                            ▼
                      RewardEngine
               section_coverage × multipliers
               + line_efficiency
               + diversity × multipliers
               + explicit_feedback
                            │
                            ▼
                    reward ∈ [-1, 1]
                            │
                   Online Update (both layers)
                            │
                   PolicyStore ~/.saar/rl/
</div>
"""


def main() -> None:
    md = SRC.read_text(encoding="utf-8")

    # Remove the title block (we replace with styled cover)
    md = re.sub(r"^# Reinforcement Learning.*?\n---\n", "", md, flags=re.DOTALL)

    # Replace the mermaid code block with our ASCII diagram
    md = re.sub(
        r"```mermaid\n.*?```",
        "__ARCH_DIAGRAM__",
        md,
        flags=re.DOTALL,
    )

    body_html = md_to_html(md)
    body_html = body_html.replace("<p>__ARCH_DIAGRAM__</p>", ARCH_DIAGRAM_HTML)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RL Technical Report — saar</title>
<style>
{CSS}
</style>
</head>
<body>
{COVER_HTML}
{body_html}
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"✓ Generated: {OUT}")
    print()
    print("  → Open in Chrome and press Cmd+P")
    print("  → Destination: Save as PDF")
    print("  → Layout: Portrait  |  Margins: Default  |  Background graphics: ON")
    print("  → Save as: rl_technical_report.pdf")


if __name__ == "__main__":
    main()

"""
EPUB Simple Diff - CLI Version
Highlight perbedaan dengan warna biru saja
Usage: python epub_simple_diff_cli.py lama.epub baru.epub -o report.html
"""

import argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import difflib
import html
from pathlib import Path


def extract_epub(path):
    book = epub.read_epub(path)
    chapters = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            title = None
            t = soup.find(['h1', 'h2', 'h3', 'title'])
            if t: title = t.get_text(strip=True)
            
            paras = [p.get_text(strip=True) for p in soup.find_all(['p', 'div']) if p.get_text(strip=True) and len(p.get_text(strip=True)) > 1]
            
            if paras:
                chapters.append({'title': title or item.get_name(), 'paragraphs': paras, 'full_text': '\n'.join(paras)})
    
    return chapters


def highlight_diff(t1, t2):
    if t1 == t2: return html.escape(t1), html.escape(t2), False
    
    m = difflib.SequenceMatcher(None, t1, t2)
    o1, o2 = [], []
    
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op == 'equal':
            o1.append(html.escape(t1[i1:i2]))
            o2.append(html.escape(t2[j1:j2]))
        elif op == 'delete':
            o1.append(f'<mark>{html.escape(t1[i1:i2])}</mark>')
        elif op == 'insert':
            o2.append(f'<mark>{html.escape(t2[j1:j2])}</mark>')
        elif op == 'replace':
            o1.append(f'<mark>{html.escape(t1[i1:i2])}</mark>')
            o2.append(f'<mark>{html.escape(t2[j1:j2])}</mark>')
    
    return ''.join(o1), ''.join(o2), True


def align(p1, p2):
    aligned = []
    m = difflib.SequenceMatcher(None, p1, p2)
    
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op == 'equal':
            for k in range(i2-i1):
                aligned.append(('same', p1[i1+k], p2[j1+k], i1+k+1, j1+k+1))
        elif op == 'delete':
            for k in range(i1, i2):
                aligned.append(('del', p1[k], None, k+1, None))
        elif op == 'insert':
            for k in range(j1, j2):
                aligned.append(('add', None, p2[k], None, k+1))
        elif op == 'replace':
            old, new = p1[i1:i2], p2[j1:j2]
            for k in range(max(len(old), len(new))):
                op_ = old[k] if k < len(old) else None
                np_ = new[k] if k < len(new) else None
                if op_ and np_:
                    aligned.append(('mod', op_, np_, i1+k+1, j1+k+1))
                elif op_:
                    aligned.append(('del', op_, None, i1+k+1, None))
                else:
                    aligned.append(('add', None, np_, None, j1+k+1))
    
    return aligned


def match_chapters(c1, c2):
    matched, used = [], set()
    for i, ch1 in enumerate(c1):
        best, score = None, 0
        for j, ch2 in enumerate(c2):
            if j in used: continue
            if ch1['title'] == ch2['title']:
                best = j; break
            r = difflib.SequenceMatcher(None, ch1['full_text'][:500], ch2['full_text'][:500]).ratio()
            if r > score and r > 0.3: score, best = r, j
        if best is not None:
            matched.append((i, best)); used.add(best)
        else:
            matched.append((i, None))
    for j in range(len(c2)):
        if j not in used: matched.append((None, j))
    return matched


def generate_report(epub1, epub2, ch1, ch2, matched):
    tpl = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>EPUB Diff</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: 'Nanum Gothic', 'Malgun Gothic', sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
h1 {{ color: #1976d2; }}
.info {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
.chapter {{ background: white; margin: 20px 0; border-radius: 8px; overflow: hidden; }}
.ch-title {{ background: #1976d2; color: white; padding: 12px 20px; font-weight: bold; }}
.content {{ padding: 15px; }}
.row {{ display: flex; gap: 15px; margin-bottom: 8px; }}
.cell {{ flex: 1; padding: 10px; border-radius: 5px; background: #fafafa; border-left: 3px solid #ddd; font-size: 15px; line-height: 1.8; }}
.cell.diff {{ background: #e3f2fd; border-left-color: #2196f3; }}
.cell.empty {{ background: #f5f5f5; border: 1px dashed #ccc; color: #999; text-align: center; }}
mark {{ background: #90caf9; padding: 1px 3px; border-radius: 3px; }}
.num {{ font-size: 0.7em; color: #888; }}
.toc {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
.toc a {{ color: #1976d2; text-decoration: none; }}
.toc a:hover {{ text-decoration: underline; }}
.toc li {{ padding: 5px 0; }}
</style>
</head><body>
<h1>📚 EPUB Diff Report</h1>
<div class="info">
<strong>Lama:</strong> {epub1}<br>
<strong>Baru:</strong> {epub2}<br>
<strong>Total perbedaan:</strong> {total_diff} paragraf
</div>
<div class="toc"><strong>Daftar Chapter dengan Perbedaan:</strong><ul>{toc}</ul></div>
{chapters}
</body></html>"""

    chapters_html, toc, total = [], [], 0
    
    for idx, (i1, i2) in enumerate(matched):
        cid = f"ch{idx}"
        
        if i1 is None:
            c = ch2[i2]
            n = len(c['paragraphs'])
            total += n
            toc.append(f'<li><a href="#{cid}">🆕 {html.escape(c["title"])} (+{n})</a></li>')
            rows = [f'<div class="row"><div class="cell empty">-</div><div class="cell diff"><span class="num">#{j+1}</span> <mark>{html.escape(p)}</mark></div></div>' for j,p in enumerate(c['paragraphs'])]
            chapters_html.append(f'<div class="chapter" id="{cid}"><div class="ch-title">🆕 {html.escape(c["title"])}</div><div class="content">{"".join(rows)}</div></div>')
            continue
        
        if i2 is None:
            c = ch1[i1]
            n = len(c['paragraphs'])
            total += n
            toc.append(f'<li><a href="#{cid}">❌ {html.escape(c["title"])} (-{n})</a></li>')
            rows = [f'<div class="row"><div class="cell diff"><span class="num">#{j+1}</span> <mark>{html.escape(p)}</mark></div><div class="cell empty">-</div></div>' for j,p in enumerate(c['paragraphs'])]
            chapters_html.append(f'<div class="chapter" id="{cid}"><div class="ch-title">❌ {html.escape(c["title"])}</div><div class="content">{"".join(rows)}</div></div>')
            continue
        
        c1_, c2_ = ch1[i1], ch2[i2]
        aligned = align(c1_['paragraphs'], c2_['paragraphs'])
        diff_n = sum(1 for a in aligned if a[0] != 'same')
        
        if diff_n == 0: continue
        
        total += diff_n
        toc.append(f'<li><a href="#{cid}">{html.escape(c1_["title"])} ({diff_n})</a></li>')
        
        rows = []
        for typ, left, right, li, ri in aligned:
            if typ == 'same': continue
            elif typ == 'del':
                rows.append(f'<div class="row"><div class="cell diff"><span class="num">#{li}</span> <mark>{html.escape(left)}</mark></div><div class="cell empty">-</div></div>')
            elif typ == 'add':
                rows.append(f'<div class="row"><div class="cell empty">-</div><div class="cell diff"><span class="num">#{ri}</span> <mark>{html.escape(right)}</mark></div></div>')
            elif typ == 'mod':
                lh, rh, _ = highlight_diff(left, right)
                rows.append(f'<div class="row"><div class="cell diff"><span class="num">#{li}</span> {lh}</div><div class="cell diff"><span class="num">#{ri}</span> {rh}</div></div>')
        
        chapters_html.append(f'<div class="chapter" id="{cid}"><div class="ch-title">{html.escape(c1_["title"])}</div><div class="content">{"".join(rows)}</div></div>')
    
    return tpl.format(epub1=Path(epub1).name, epub2=Path(epub2).name, total_diff=total, toc="".join(toc), chapters="".join(chapters_html))


def main():
    p = argparse.ArgumentParser(description='Simple EPUB diff with blue highlight')
    p.add_argument('epub1', help='Original EPUB')
    p.add_argument('epub2', help='Revised EPUB')
    p.add_argument('-o', '--output', default='diff_report.html')
    args = p.parse_args()
    
    print(f"📖 Loading {args.epub1}...")
    c1 = extract_epub(args.epub1)
    print(f"📖 Loading {args.epub2}...")
    c2 = extract_epub(args.epub2)
    print("🔍 Comparing...")
    matched = match_chapters(c1, c2)
    
    report = generate_report(args.epub1, args.epub2, c1, c2, matched)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ Saved: {args.output}")


if __name__ == '__main__':
    main()

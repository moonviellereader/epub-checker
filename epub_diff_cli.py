"""
EPUB Difference Checker - CLI Version
Generates HTML report comparing two EPUB files
Usage: python epub_diff_cli.py epub1.epub epub2.epub -o report.html
"""

import argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import difflib
import html
import re
from pathlib import Path


def extract_text_from_epub(epub_path):
    """Extract text content from EPUB file"""
    book = epub.read_epub(epub_path)
    chapters = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            title = None
            title_tag = soup.find(['h1', 'h2', 'h3', 'title'])
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text(strip=True)
                if text and len(text) > 1:
                    paragraphs.append(text)
            
            if paragraphs:
                chapters.append({
                    'id': item.get_name(),
                    'title': title or item.get_name(),
                    'paragraphs': paragraphs,
                    'full_text': '\n'.join(paragraphs)
                })
    
    return chapters


def get_diff_html(text1, text2):
    """Generate HTML diff between two texts"""
    if text1 == text2:
        return None, 'same'
    
    matcher = difflib.SequenceMatcher(None, text1, text2)
    output = []
    
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            output.append(html.escape(text1[i1:i2]))
        elif opcode == 'delete':
            output.append(f'<span class="removed">{html.escape(text1[i1:i2])}</span>')
        elif opcode == 'insert':
            output.append(f'<span class="added">{html.escape(text2[j1:j2])}</span>')
        elif opcode == 'replace':
            output.append(f'<span class="removed">{html.escape(text1[i1:i2])}</span>')
            output.append(f'<span class="added">{html.escape(text2[j1:j2])}</span>')
    
    return ''.join(output), 'different'


def compare_paragraphs(paras1, paras2, min_similarity=0.5):
    """Compare two lists of paragraphs"""
    results = []
    matcher = difflib.SequenceMatcher(None, paras1, paras2)
    
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            for idx in range(i1, i2):
                results.append({
                    'type': 'same',
                    'old': paras1[idx],
                    'new': paras2[idx - i1 + j1],
                    'old_idx': idx + 1,
                    'new_idx': idx - i1 + j1 + 1
                })
        elif opcode == 'delete':
            for idx in range(i1, i2):
                results.append({
                    'type': 'deleted',
                    'old': paras1[idx],
                    'new': None,
                    'old_idx': idx + 1,
                    'new_idx': None
                })
        elif opcode == 'insert':
            for idx in range(j1, j2):
                results.append({
                    'type': 'added',
                    'old': None,
                    'new': paras2[idx],
                    'old_idx': None,
                    'new_idx': idx + 1
                })
        elif opcode == 'replace':
            old_paras = paras1[i1:i2]
            new_paras = paras2[j1:j2]
            
            max_len = max(len(old_paras), len(new_paras))
            for idx in range(max_len):
                old_p = old_paras[idx] if idx < len(old_paras) else None
                new_p = new_paras[idx] if idx < len(new_paras) else None
                
                if old_p and new_p:
                    ratio = difflib.SequenceMatcher(None, old_p, new_p).ratio()
                    if ratio > min_similarity:
                        results.append({
                            'type': 'modified',
                            'old': old_p,
                            'new': new_p,
                            'old_idx': i1 + idx + 1,
                            'new_idx': j1 + idx + 1,
                            'similarity': ratio
                        })
                    else:
                        results.append({
                            'type': 'deleted', 'old': old_p, 'new': None,
                            'old_idx': i1 + idx + 1, 'new_idx': None
                        })
                        results.append({
                            'type': 'added', 'old': None, 'new': new_p,
                            'old_idx': None, 'new_idx': j1 + idx + 1
                        })
                elif old_p:
                    results.append({
                        'type': 'deleted', 'old': old_p, 'new': None,
                        'old_idx': i1 + idx + 1, 'new_idx': None
                    })
                elif new_p:
                    results.append({
                        'type': 'added', 'old': None, 'new': new_p,
                        'old_idx': None, 'new_idx': j1 + idx + 1
                    })
    
    return results


def match_chapters(chapters1, chapters2):
    """Match chapters between two EPUBs"""
    matched = []
    used_j = set()
    
    for i, ch1 in enumerate(chapters1):
        best_match = None
        best_score = 0
        
        for j, ch2 in enumerate(chapters2):
            if j in used_j:
                continue
            
            if ch1['title'] == ch2['title']:
                best_match = j
                best_score = 1.0
                break
            
            ratio = difflib.SequenceMatcher(
                None, ch1['full_text'][:500], ch2['full_text'][:500]
            ).ratio()
            
            if ratio > best_score and ratio > 0.3:
                best_score = ratio
                best_match = j
        
        if best_match is not None:
            matched.append((i, best_match))
            used_j.add(best_match)
        else:
            matched.append((i, None))
    
    for j in range(len(chapters2)):
        if j not in used_j:
            matched.append((None, j))
    
    return matched


def generate_html_report(epub1_path, epub2_path, chapters1, chapters2, matched_chapters, show_same=False):
    """Generate HTML report"""
    
    html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPUB Diff Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Nanum Gothic', 'Malgun Gothic', -apple-system, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            line-height: 1.6;
        }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #444; margin-top: 30px; }}
        .summary {{
            background: #e7f3ff;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .summary table {{ width: 100%; border-collapse: collapse; }}
        .summary td, .summary th {{ padding: 8px; text-align: left; }}
        .chapter {{
            background: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chapter-title {{
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .stats {{
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 0.9em;
        }}
        .paragraph {{
            margin: 15px 0;
            padding: 15px;
            border-left: 4px solid #ddd;
            background: #fafafa;
            border-radius: 0 5px 5px 0;
        }}
        .paragraph.added {{ border-left-color: #28a745; background: #d4edda; }}
        .paragraph.deleted {{ border-left-color: #dc3545; background: #f8d7da; }}
        .paragraph.modified {{ border-left-color: #ffc107; background: #fff3cd; }}
        .label {{
            font-size: 0.8em;
            color: #666;
            margin-bottom: 5px;
        }}
        .text {{
            font-size: 1.1em;
            line-height: 1.8;
        }}
        .added {{ background-color: #c3e6cb; padding: 2px 4px; border-radius: 3px; }}
        .removed {{ background-color: #f5c6cb; padding: 2px 4px; border-radius: 3px; text-decoration: line-through; }}
        .nav {{
            position: sticky;
            top: 0;
            background: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .nav a {{
            margin-right: 15px;
            color: #007bff;
            text-decoration: none;
        }}
        .nav a:hover {{ text-decoration: underline; }}
        .toc {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .toc ul {{ list-style: none; padding-left: 0; }}
        .toc li {{ padding: 5px 0; }}
        .toc a {{ color: #007bff; text-decoration: none; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            margin-left: 10px;
        }}
        .badge-new {{ background: #28a745; color: white; }}
        .badge-deleted {{ background: #dc3545; color: white; }}
        .badge-modified {{ background: #ffc107; color: #333; }}
        @media print {{
            .nav {{ display: none; }}
            .chapter {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <h1>📚 EPUB Difference Report</h1>
    
    <div class="summary">
        <h3>📋 File Information</h3>
        <table>
            <tr><td><strong>Original:</strong></td><td>{epub1_name}</td></tr>
            <tr><td><strong>Revised:</strong></td><td>{epub2_name}</td></tr>
        </table>
    </div>
    
    <div class="summary">
        <h3>📊 Summary</h3>
        <table>
            <tr>
                <td>✅ Paragraphs Added:</td><td><strong style="color:green">{total_added}</strong></td>
            </tr>
            <tr>
                <td>❌ Paragraphs Deleted:</td><td><strong style="color:red">{total_deleted}</strong></td>
            </tr>
            <tr>
                <td>📝 Paragraphs Modified:</td><td><strong style="color:orange">{total_modified}</strong></td>
            </tr>
        </table>
    </div>
    
    <div class="toc">
        <h3>📑 Table of Contents</h3>
        <ul>
            {toc_items}
        </ul>
    </div>
    
    {chapters_html}
    
</body>
</html>"""

    total_added = 0
    total_deleted = 0
    total_modified = 0
    chapters_html = []
    toc_items = []
    
    for match_idx, (idx1, idx2) in enumerate(matched_chapters):
        chapter_id = f"chapter-{match_idx}"
        
        if idx1 is None:
            # New chapter
            ch2 = chapters2[idx2]
            toc_items.append(f'<li><a href="#{chapter_id}">🆕 {html.escape(ch2["title"])}</a><span class="badge badge-new">NEW</span></li>')
            
            paras_html = []
            for p in ch2['paragraphs']:
                paras_html.append(f'''
                <div class="paragraph added">
                    <div class="label">New paragraph</div>
                    <div class="text">{html.escape(p)}</div>
                </div>
                ''')
            
            chapters_html.append(f'''
            <div class="chapter" id="{chapter_id}">
                <div class="chapter-title">🆕 NEW CHAPTER: {html.escape(ch2["title"])}</div>
                {"".join(paras_html)}
            </div>
            ''')
            total_added += len(ch2['paragraphs'])
            continue
        
        if idx2 is None:
            # Deleted chapter
            ch1 = chapters1[idx1]
            toc_items.append(f'<li><a href="#{chapter_id}">❌ {html.escape(ch1["title"])}</a><span class="badge badge-deleted">DELETED</span></li>')
            
            paras_html = []
            for p in ch1['paragraphs']:
                paras_html.append(f'''
                <div class="paragraph deleted">
                    <div class="label">Deleted paragraph</div>
                    <div class="text">{html.escape(p)}</div>
                </div>
                ''')
            
            chapters_html.append(f'''
            <div class="chapter" id="{chapter_id}">
                <div class="chapter-title">❌ DELETED CHAPTER: {html.escape(ch1["title"])}</div>
                {"".join(paras_html)}
            </div>
            ''')
            total_deleted += len(ch1['paragraphs'])
            continue
        
        # Both exist - compare
        ch1 = chapters1[idx1]
        ch2 = chapters2[idx2]
        
        diff_results = compare_paragraphs(ch1['paragraphs'], ch2['paragraphs'])
        
        chapter_added = sum(1 for r in diff_results if r['type'] == 'added')
        chapter_deleted = sum(1 for r in diff_results if r['type'] == 'deleted')
        chapter_modified = sum(1 for r in diff_results if r['type'] == 'modified')
        
        total_added += chapter_added
        total_deleted += chapter_deleted
        total_modified += chapter_modified
        
        has_diff = chapter_added > 0 or chapter_deleted > 0 or chapter_modified > 0
        
        if has_diff:
            toc_items.append(f'<li><a href="#{chapter_id}">📝 {html.escape(ch1["title"])}</a><span class="badge badge-modified">CHANGED</span></li>')
        else:
            if show_same:
                toc_items.append(f'<li><a href="#{chapter_id}">✅ {html.escape(ch1["title"])}</a></li>')
            continue
        
        paras_html = []
        for result in diff_results:
            if result['type'] == 'same' and not show_same:
                continue
            
            if result['type'] == 'added':
                paras_html.append(f'''
                <div class="paragraph added">
                    <div class="label">➕ Added (line #{result['new_idx']})</div>
                    <div class="text">{html.escape(result['new'])}</div>
                </div>
                ''')
            elif result['type'] == 'deleted':
                paras_html.append(f'''
                <div class="paragraph deleted">
                    <div class="label">➖ Deleted (was line #{result['old_idx']})</div>
                    <div class="text">{html.escape(result['old'])}</div>
                </div>
                ''')
            elif result['type'] == 'modified':
                diff_html, _ = get_diff_html(result['old'], result['new'])
                sim = int(result.get('similarity', 0) * 100)
                paras_html.append(f'''
                <div class="paragraph modified">
                    <div class="label">✏️ Modified (line #{result['old_idx']} → #{result['new_idx']}, {sim}% similar)</div>
                    <div class="text">{diff_html}</div>
                </div>
                ''')
            elif result['type'] == 'same' and show_same:
                paras_html.append(f'''
                <div class="paragraph">
                    <div class="label">Line #{result['old_idx']}</div>
                    <div class="text">{html.escape(result['old'])}</div>
                </div>
                ''')
        
        if paras_html:
            chapters_html.append(f'''
            <div class="chapter" id="{chapter_id}">
                <div class="chapter-title">{html.escape(ch1["title"])}</div>
                <div class="stats">
                    <strong>Changes:</strong>
                    <span style="color:green">+{chapter_added} added</span> |
                    <span style="color:red">-{chapter_deleted} deleted</span> |
                    <span style="color:orange">~{chapter_modified} modified</span>
                </div>
                {"".join(paras_html)}
            </div>
            ''')
    
    return html_template.format(
        epub1_name=Path(epub1_path).name,
        epub2_name=Path(epub2_path).name,
        total_added=total_added,
        total_deleted=total_deleted,
        total_modified=total_modified,
        toc_items="\n".join(toc_items),
        chapters_html="\n".join(chapters_html)
    )


def main():
    parser = argparse.ArgumentParser(description='Compare two EPUB files and generate diff report')
    parser.add_argument('epub1', help='Path to original EPUB file')
    parser.add_argument('epub2', help='Path to revised EPUB file')
    parser.add_argument('-o', '--output', default='epub_diff_report.html', help='Output HTML file')
    parser.add_argument('--show-same', action='store_true', help='Include unchanged paragraphs')
    
    args = parser.parse_args()
    
    print(f"📖 Loading {args.epub1}...")
    chapters1 = extract_text_from_epub(args.epub1)
    print(f"   Found {len(chapters1)} chapters")
    
    print(f"📖 Loading {args.epub2}...")
    chapters2 = extract_text_from_epub(args.epub2)
    print(f"   Found {len(chapters2)} chapters")
    
    print("🔍 Matching chapters...")
    matched = match_chapters(chapters1, chapters2)
    
    print("📝 Generating report...")
    html_report = generate_html_report(
        args.epub1, args.epub2, 
        chapters1, chapters2, 
        matched,
        show_same=args.show_same
    )
    
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html_report)
    
    print(f"✅ Report saved to: {args.output}")


if __name__ == '__main__':
    main()

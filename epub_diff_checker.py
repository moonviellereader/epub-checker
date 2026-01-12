"""
EPUB Diff Checker - Highlight Perbedaan dengan Warna Biru
Upload 2 EPUB, bagian yang berbeda akan di-highlight biru
"""

import streamlit as st
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import difflib
from io import BytesIO
import html

st.set_page_config(page_title="EPUB Diff Checker", page_icon="📚", layout="wide")

st.markdown("""
<style>
    .main .block-container { max-width: 100%; padding: 1rem 2rem; }
    
    .row { display: flex; gap: 15px; margin-bottom: 8px; }
    
    .cell {
        flex: 1;
        padding: 10px 12px;
        border-radius: 5px;
        font-family: 'Nanum Gothic', 'Malgun Gothic', sans-serif;
        font-size: 15px;
        line-height: 1.8;
        background: #fafafa;
        border-left: 3px solid #ddd;
    }
    
    .cell-left { background: #f9f9f9; }
    .cell-right { background: #f9f9f9; }
    
    /* Highlight biru untuk perbedaan */
    .diff { background-color: #90caf9; padding: 1px 3px; border-radius: 3px; }
    
    .cell.has-diff { background: #e3f2fd; border-left-color: #2196f3; }
    
    .cell.empty {
        background: #f5f5f5;
        border: 1px dashed #ccc;
        color: #999;
        text-align: center;
        font-style: italic;
    }
    
    .chapter-header {
        background: #1976d2;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin: 25px 0 15px 0;
        font-weight: bold;
    }
    
    .num { font-size: 0.7em; color: #888; }
    
    .stats { 
        background: #e3f2fd; 
        padding: 10px 15px; 
        border-radius: 5px; 
        margin: 10px 0;
        color: #1565c0;
    }
</style>
""", unsafe_allow_html=True)


def extract_epub(epub_file):
    book = epub.read_epub(epub_file)
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
                    'title': title or item.get_name(),
                    'paragraphs': paragraphs,
                    'full_text': '\n'.join(paragraphs)
                })
    
    return chapters


def get_diff_highlight(text1, text2):
    """Highlight perbedaan dengan warna biru"""
    if text1 == text2:
        return html.escape(text1), html.escape(text2), False
    
    matcher = difflib.SequenceMatcher(None, text1, text2)
    out1, out2 = [], []
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            out1.append(html.escape(text1[i1:i2]))
            out2.append(html.escape(text2[j1:j2]))
        elif op == 'delete':
            out1.append(f'<span class="diff">{html.escape(text1[i1:i2])}</span>')
        elif op == 'insert':
            out2.append(f'<span class="diff">{html.escape(text2[j1:j2])}</span>')
        elif op == 'replace':
            out1.append(f'<span class="diff">{html.escape(text1[i1:i2])}</span>')
            out2.append(f'<span class="diff">{html.escape(text2[j1:j2])}</span>')
    
    return ''.join(out1), ''.join(out2), True


def align_paragraphs(paras1, paras2):
    aligned = []
    matcher = difflib.SequenceMatcher(None, paras1, paras2)
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                aligned.append(('same', paras1[i1+k], paras2[j1+k], i1+k+1, j1+k+1))
        elif op == 'delete':
            for k in range(i1, i2):
                aligned.append(('del', paras1[k], None, k+1, None))
        elif op == 'insert':
            for k in range(j1, j2):
                aligned.append(('add', None, paras2[k], None, k+1))
        elif op == 'replace':
            old_p, new_p = paras1[i1:i2], paras2[j1:j2]
            max_len = max(len(old_p), len(new_p))
            for k in range(max_len):
                op_ = old_p[k] if k < len(old_p) else None
                np_ = new_p[k] if k < len(new_p) else None
                if op_ and np_:
                    aligned.append(('mod', op_, np_, i1+k+1, j1+k+1))
                elif op_:
                    aligned.append(('del', op_, None, i1+k+1, None))
                else:
                    aligned.append(('add', None, np_, None, j1+k+1))
    
    return aligned


def match_chapters(ch1, ch2):
    matched, used = [], set()
    
    for i, c1 in enumerate(ch1):
        best, score = None, 0
        for j, c2 in enumerate(ch2):
            if j in used: continue
            if c1['title'] == c2['title']:
                best, score = j, 1.0
                break
            r = difflib.SequenceMatcher(None, c1['full_text'][:500], c2['full_text'][:500]).ratio()
            if r > score and r > 0.3:
                score, best = r, j
        
        if best is not None:
            matched.append((i, best))
            used.add(best)
        else:
            matched.append((i, None))
    
    for j in range(len(ch2)):
        if j not in used:
            matched.append((None, j))
    
    return matched


# === MAIN ===
st.title("📚 EPUB Diff Checker")
st.caption("Upload 2 EPUB → Bagian berbeda akan di-highlight biru")

col1, col2 = st.columns(2)
with col1:
    epub1 = st.file_uploader("📖 EPUB Lama (Original)", type=['epub'], key='e1')
with col2:
    epub2 = st.file_uploader("📖 EPUB Baru (Revised)", type=['epub'], key='e2')

# Sidebar
show_same = st.sidebar.checkbox("Tampilkan paragraf yang sama", value=False)
only_diff = st.sidebar.checkbox("Hanya chapter dengan perbedaan", value=True)

if epub1 and epub2:
    with st.spinner("Memproses EPUB..."):
        chapters1 = extract_epub(BytesIO(epub1.read()))
        epub1.seek(0)
        chapters2 = extract_epub(BytesIO(epub2.read()))
        
        matched = match_chapters(chapters1, chapters2)
        
        # Count diffs
        total_diff = 0
        
        # Chapter selector
        ch_opts = []
        for idx1, idx2 in matched:
            if idx1 is None:
                ch_opts.append(f"🆕 {chapters2[idx2]['title']}")
            elif idx2 is None:
                ch_opts.append(f"❌ {chapters1[idx1]['title']}")
            else:
                ch_opts.append(chapters1[idx1]['title'])
        
        selected = st.selectbox("Pilih Chapter:", ["-- Semua --"] + ch_opts)
        
        st.markdown("---")
        
        for i, (idx1, idx2) in enumerate(matched):
            # Filter
            if selected != "-- Semua --" and ch_opts[i] != selected:
                continue
            
            if idx1 is None:
                # New chapter
                ch = chapters2[idx2]
                if only_diff or selected != "-- Semua --":
                    st.markdown(f'<div class="chapter-header">🆕 {html.escape(ch["title"])} (Chapter Baru)</div>', unsafe_allow_html=True)
                    rows = []
                    for j, p in enumerate(ch['paragraphs']):
                        rows.append(f'''<div class="row">
                            <div class="cell cell-left empty">-</div>
                            <div class="cell cell-right has-diff"><span class="num">#{j+1}</span> <span class="diff">{html.escape(p)}</span></div>
                        </div>''')
                    st.markdown("".join(rows), unsafe_allow_html=True)
                continue
            
            if idx2 is None:
                # Deleted chapter
                ch = chapters1[idx1]
                if only_diff or selected != "-- Semua --":
                    st.markdown(f'<div class="chapter-header">❌ {html.escape(ch["title"])} (Chapter Dihapus)</div>', unsafe_allow_html=True)
                    rows = []
                    for j, p in enumerate(ch['paragraphs']):
                        rows.append(f'''<div class="row">
                            <div class="cell cell-left has-diff"><span class="num">#{j+1}</span> <span class="diff">{html.escape(p)}</span></div>
                            <div class="cell cell-right empty">-</div>
                        </div>''')
                    st.markdown("".join(rows), unsafe_allow_html=True)
                continue
            
            # Compare
            ch1, ch2 = chapters1[idx1], chapters2[idx2]
            aligned = align_paragraphs(ch1['paragraphs'], ch2['paragraphs'])
            
            diff_count = sum(1 for a in aligned if a[0] != 'same')
            total_diff += diff_count
            
            if only_diff and diff_count == 0 and selected == "-- Semua --":
                continue
            
            st.markdown(f'<div class="chapter-header">{html.escape(ch1["title"])} <span style="font-size:0.8em; opacity:0.8;">({diff_count} perbedaan)</span></div>', unsafe_allow_html=True)
            
            rows = []
            for typ, left, right, l_idx, r_idx in aligned:
                if typ == 'same':
                    if not show_same:
                        continue
                    rows.append(f'''<div class="row">
                        <div class="cell cell-left"><span class="num">#{l_idx}</span> {html.escape(left)}</div>
                        <div class="cell cell-right"><span class="num">#{r_idx}</span> {html.escape(right)}</div>
                    </div>''')
                elif typ == 'del':
                    rows.append(f'''<div class="row">
                        <div class="cell cell-left has-diff"><span class="num">#{l_idx}</span> <span class="diff">{html.escape(left)}</span></div>
                        <div class="cell cell-right empty">-</div>
                    </div>''')
                elif typ == 'add':
                    rows.append(f'''<div class="row">
                        <div class="cell cell-left empty">-</div>
                        <div class="cell cell-right has-diff"><span class="num">#{r_idx}</span> <span class="diff">{html.escape(right)}</span></div>
                    </div>''')
                elif typ == 'mod':
                    left_h, right_h, _ = get_diff_highlight(left, right)
                    rows.append(f'''<div class="row">
                        <div class="cell cell-left has-diff"><span class="num">#{l_idx}</span> {left_h}</div>
                        <div class="cell cell-right has-diff"><span class="num">#{r_idx}</span> {right_h}</div>
                    </div>''')
            
            if rows:
                st.markdown("".join(rows), unsafe_allow_html=True)
            elif not show_same:
                st.info("✅ Tidak ada perbedaan di chapter ini")

else:
    st.info("👆 Upload kedua file EPUB untuk memulai perbandingan")
    
    st.markdown("""
    ### 📋 Cara Penggunaan:
    1. Upload **EPUB Lama** (original) di kolom kiri
    2. Upload **EPUB Baru** (revised) di kolom kanan
    3. Bagian yang berbeda akan di-**highlight biru**
    4. Tinggal copy teks yang biru untuk diterjemahkan!
    
    ### ✨ Fitur:
    - Side-by-side comparison
    - Highlight biru untuk perbedaan
    - Filter per chapter
    - Deteksi paragraf ditambah/dihapus/diubah
    """)

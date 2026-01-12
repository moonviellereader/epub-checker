"""
EPUB Diff Checker - Find New/Different Content
Temukan konten baru atau berbeda di EPUB 2 dibanding EPUB 1
"""

import streamlit as st
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import difflib
from io import BytesIO
import html
import re

st.set_page_config(page_title="EPUB Diff Checker", page_icon="📚", layout="wide")

st.markdown("""
<style>
    .main .block-container { max-width: 100%; padding: 1rem 2rem; }
    
    .row { 
        display: flex; 
        gap: 20px; 
        margin-bottom: 3px; 
    }
    
    .cell {
        flex: 1;
        padding: 8px 12px;
        font-family: 'Nanum Gothic', 'Malgun Gothic', sans-serif;
        font-size: 15px;
        line-height: 1.8;
        background: white;
        border-bottom: 1px solid #f0f0f0;
    }
    
    .cell.diff {
        background: #e3f2fd;
    }
    
    .cell.empty {
        background: #fafafa;
        color: #ccc;
    }
    
    .highlight { 
        background-color: #90caf9; 
        padding: 1px 3px; 
        border-radius: 3px; 
    }
    
    .header-row {
        display: flex;
        gap: 20px;
        padding: 12px 15px;
        background: #1976d2;
        color: white;
        font-weight: bold;
        border-radius: 8px 8px 0 0;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    
    .header-row > div { flex: 1; }
    
    .content-box {
        border: 1px solid #ddd;
        border-top: none;
        border-radius: 0 0 8px 8px;
        max-height: 75vh;
        overflow-y: auto;
        background: white;
    }
    
    .num { 
        font-size: 0.7em; 
        color: #999;
        margin-right: 5px;
    }
    
    .stats {
        display: flex;
        gap: 15px;
        padding: 12px 15px;
        background: #f5f5f5;
        border-radius: 8px;
        margin: 10px 0;
        flex-wrap: wrap;
    }
    
    .stat {
        padding: 6px 12px;
        border-radius: 5px;
        font-size: 0.9em;
    }
    
    .stat-total { background: #e0e0e0; }
    .stat-diff { background: #e3f2fd; color: #1565c0; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


def normalize(text):
    """Normalize for comparison"""
    return re.sub(r'\s+', '', text)


def extract_paragraphs(epub_file):
    """Extract paragraphs maintaining order"""
    book = epub.read_epub(epub_file)
    paragraphs = []
    seen = set()
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            for elem in soup.find_all(['p', 'div']):
                text = elem.get_text(strip=True)
                
                if not text or len(text) <= 1:
                    continue
                if len(text) > 5000:
                    continue
                
                norm = normalize(text)
                if norm in seen:
                    continue
                seen.add(norm)
                paragraphs.append(text)
    
    return paragraphs


def build_reference_set(paragraphs):
    """Build set of normalized text chunks for quick lookup"""
    ref = set()
    
    for para in paragraphs:
        norm = normalize(para)
        ref.add(norm)
        
        # Also add smaller chunks (sentences) for partial matching
        # Split by Korean sentence endings
        sentences = re.split(r'(?<=[.?!」』"])\s*', para)
        for sent in sentences:
            if len(sent) > 10:
                ref.add(normalize(sent))
    
    return ref


def check_if_new(para, reference_set, reference_paras):
    """Check if paragraph content is new (not in reference)"""
    norm = normalize(para)
    
    # Exact match
    if norm in reference_set:
        return False, 1.0
    
    # Check if it's contained in any reference paragraph
    for ref_para in reference_paras:
        ref_norm = normalize(ref_para)
        if norm in ref_norm or ref_norm in norm:
            return False, 0.9
    
    # Check sentence-level matching
    sentences = re.split(r'(?<=[.?!」』"])\s*', para)
    matching_sentences = 0
    total_sentences = 0
    
    for sent in sentences:
        sent_norm = normalize(sent)
        if len(sent_norm) < 10:
            continue
        total_sentences += 1
        
        if sent_norm in reference_set:
            matching_sentences += 1
            continue
        
        # Check partial match
        for ref_para in reference_paras[:500]:  # Limit for performance
            ref_norm = normalize(ref_para)
            if sent_norm in ref_norm:
                matching_sentences += 1
                break
    
    if total_sentences == 0:
        return False, 1.0
    
    match_ratio = matching_sentences / total_sentences
    
    # If most sentences are new, consider it new content
    return match_ratio < 0.5, match_ratio


def find_text_diff(text1, text2):
    """Find character-level differences"""
    matcher = difflib.SequenceMatcher(None, text1, text2)
    result = []
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            result.append(html.escape(text2[j1:j2]))
        elif op in ('insert', 'replace'):
            result.append(f'<span class="highlight">{html.escape(text2[j1:j2])}</span>')
    
    return ''.join(result)


# === MAIN APP ===
st.title("📚 EPUB Diff Checker")
st.caption("Temukan konten baru/berbeda di EPUB 2 (kanan) dibanding EPUB 1 (kiri)")

col1, col2 = st.columns(2)
with col1:
    epub1 = st.file_uploader("📖 EPUB 1 - Original (Kiri)", type=['epub'], key='e1')
with col2:
    epub2 = st.file_uploader("📖 EPUB 2 - Revised (Kanan)", type=['epub'], key='e2')

st.sidebar.header("⚙️ Pengaturan")
show_all = st.sidebar.checkbox("Tampilkan semua paragraf", value=True)
show_only_diff = st.sidebar.checkbox("Hanya tampilkan yang berbeda", value=False)

if epub1 and epub2:
    with st.spinner("Membaca EPUB..."):
        paras1 = extract_paragraphs(BytesIO(epub1.read()))
        epub1.seek(0)
        paras2 = extract_paragraphs(BytesIO(epub2.read()))
    
    st.success(f"✅ EPUB 1: {len(paras1)} paragraf | EPUB 2: {len(paras2)} paragraf")
    
    with st.spinner("Menganalisis perbedaan..."):
        # Build reference from EPUB 1
        ref_set = build_reference_set(paras1)
        
        # Check each paragraph in EPUB 2
        diff_info = []
        for i, para in enumerate(paras2):
            is_new, match_ratio = check_if_new(para, ref_set, paras1)
            diff_info.append({
                'idx': i,
                'text': para,
                'is_new': is_new,
                'match_ratio': match_ratio
            })
        
        diff_count = sum(1 for d in diff_info if d['is_new'])
    
    # Stats
    st.markdown(f"""
    <div class="stats">
        <div class="stat stat-total">📄 Total EPUB 2: {len(paras2)} paragraf</div>
        <div class="stat stat-diff">🔵 Konten baru/berbeda: {diff_count} paragraf</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick jump to differences
    if diff_count > 0:
        diff_indices = [d['idx'] for d in diff_info if d['is_new']]
        st.markdown(f"**Ditemukan {diff_count} paragraf berbeda.** Pilih untuk loncat:")
        
        jump_options = ["-- Pilih --"] + [f"#{i+1} (paragraf {diff_indices[i]+1})" for i in range(min(50, len(diff_indices)))]
        selected_jump = st.selectbox("Loncat ke:", jump_options, key="jump")
    
    st.markdown("---")
    
    # Display header
    st.markdown("""
    <div class="header-row">
        <div>📖 EPUB 1 - Original</div>
        <div>📖 EPUB 2 - Revised (biru = baru/berbeda)</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Display content
    rows_html = []
    shown = 0
    max_show = 300
    
    # Align display - show EPUB 2 on right, try to match EPUB 1 on left
    j = 0  # Index for EPUB 1
    
    for i, info in enumerate(diff_info):
        if shown >= max_show:
            break
        
        if show_only_diff and not info['is_new']:
            continue
        
        para2 = info['text']
        is_diff = info['is_new']
        
        # Try to find corresponding paragraph in EPUB 1
        para1 = ""
        if j < len(paras1):
            # Check if current EPUB 1 paragraph matches
            norm1 = normalize(paras1[j])
            norm2 = normalize(para2)
            
            if norm1 == norm2 or norm1 in norm2 or norm2 in norm1:
                para1 = paras1[j]
                j += 1
            elif difflib.SequenceMatcher(None, norm1, norm2).ratio() > 0.5:
                para1 = paras1[j]
                j += 1
            else:
                # Maybe EPUB 1 paragraph was merged, try next few
                found = False
                for look_ahead in range(min(5, len(paras1) - j)):
                    check_norm = normalize(paras1[j + look_ahead])
                    if check_norm in norm2 or difflib.SequenceMatcher(None, check_norm, norm2).ratio() > 0.6:
                        para1 = paras1[j + look_ahead]
                        j = j + look_ahead + 1
                        found = True
                        break
                
                if not found and not is_diff:
                    para1 = paras1[j] if j < len(paras1) else ""
                    j += 1
        
        # Build HTML
        left_html = html.escape(para1) if para1 else "-"
        left_class = "cell" if para1 else "cell empty"
        
        if is_diff:
            right_class = "cell diff"
            right_html = f'<span class="highlight">{html.escape(para2)}</span>'
        else:
            right_class = "cell"
            right_html = html.escape(para2)
        
        rows_html.append(f'''<div class="row" id="para-{i}">
            <div class="{left_class}"><span class="num">#{j}</span>{left_html}</div>
            <div class="{right_class}"><span class="num">#{i+1}</span>{right_html}</div>
        </div>''')
        
        shown += 1
    
    st.markdown(f'<div class="content-box">{"".join(rows_html)}</div>', unsafe_allow_html=True)
    
    if shown >= max_show:
        st.warning(f"⚠️ Menampilkan {max_show} paragraf pertama. Centang 'Hanya tampilkan yang berbeda' untuk fokus pada perbedaan.")

else:
    st.info("👆 Upload kedua file EPUB untuk memulai")
    
    st.markdown("""
    ### 📋 Cara Penggunaan:
    1. Upload **EPUB Original** di kiri
    2. Upload **EPUB Revised** di kanan
    3. Konten **baru/berbeda** akan di-highlight **biru**
    
    ### ✨ Fitur:
    - Deteksi paragraf baru yang tidak ada di versi original
    - Side-by-side display
    - Filter hanya tampilkan perbedaan
    """)

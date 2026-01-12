"""
EPUB Difference Checker - Korean Text Comparison Tool
Membandingkan dua file EPUB dan menemukan perbedaan konten (Hangul)
"""

import streamlit as st
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import difflib
import re
from io import BytesIO
import html

# Page config
st.set_page_config(
    page_title="EPUB Diff Checker",
    page_icon="📚",
    layout="wide"
)

# Custom CSS for better diff display
st.markdown("""
<style>
    .diff-added {
        background-color: #d4edda;
        color: #155724;
        padding: 2px 5px;
        border-radius: 3px;
        display: inline;
    }
    .diff-removed {
        background-color: #f8d7da;
        color: #721c24;
        padding: 2px 5px;
        border-radius: 3px;
        text-decoration: line-through;
        display: inline;
    }
    .diff-changed {
        background-color: #fff3cd;
        color: #856404;
        padding: 2px 5px;
        border-radius: 3px;
        display: inline;
    }
    .chapter-box {
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        background-color: #f9f9f9;
    }
    .stats-box {
        background-color: #e7f3ff;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .paragraph {
        margin: 10px 0;
        padding: 10px;
        border-left: 3px solid #ddd;
        background-color: white;
    }
    .diff-line {
        font-family: 'Nanum Gothic', 'Malgun Gothic', sans-serif;
        font-size: 16px;
        line-height: 1.8;
    }
</style>
""", unsafe_allow_html=True)


def extract_text_from_epub(epub_file):
    """Extract text content from EPUB file"""
    book = epub.read_epub(epub_file)
    chapters = []
    
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Get chapter title if available
            title = None
            title_tag = soup.find(['h1', 'h2', 'h3', 'title'])
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            # Extract paragraphs
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text(strip=True)
                if text and len(text) > 1:  # Skip empty or single-char paragraphs
                    paragraphs.append(text)
            
            if paragraphs:
                chapters.append({
                    'id': item.get_name(),
                    'title': title or item.get_name(),
                    'paragraphs': paragraphs,
                    'full_text': '\n'.join(paragraphs)
                })
    
    return chapters


def is_korean(text):
    """Check if text contains Korean characters"""
    korean_pattern = re.compile('[가-힣]')
    return bool(korean_pattern.search(text))


def get_diff_html(text1, text2):
    """Generate HTML diff between two texts"""
    if text1 == text2:
        return None, 'same'
    
    # Use SequenceMatcher for detailed diff
    matcher = difflib.SequenceMatcher(None, text1, text2)
    
    output = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            output.append(html.escape(text1[i1:i2]))
        elif opcode == 'delete':
            output.append(f'<span class="diff-removed">{html.escape(text1[i1:i2])}</span>')
        elif opcode == 'insert':
            output.append(f'<span class="diff-added">{html.escape(text2[j1:j2])}</span>')
        elif opcode == 'replace':
            output.append(f'<span class="diff-removed">{html.escape(text1[i1:i2])}</span>')
            output.append(f'<span class="diff-added">{html.escape(text2[j1:j2])}</span>')
    
    return ''.join(output), 'different'


def compare_paragraphs(paras1, paras2):
    """Compare two lists of paragraphs and find differences"""
    results = []
    
    # Use SequenceMatcher to align paragraphs
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
            # Try to match modified paragraphs
            old_paras = paras1[i1:i2]
            new_paras = paras2[j1:j2]
            
            max_len = max(len(old_paras), len(new_paras))
            for idx in range(max_len):
                old_p = old_paras[idx] if idx < len(old_paras) else None
                new_p = new_paras[idx] if idx < len(new_paras) else None
                
                if old_p and new_p:
                    # Check similarity
                    ratio = difflib.SequenceMatcher(None, old_p, new_p).ratio()
                    if ratio > 0.5:  # Likely modified
                        results.append({
                            'type': 'modified',
                            'old': old_p,
                            'new': new_p,
                            'old_idx': i1 + idx + 1,
                            'new_idx': j1 + idx + 1,
                            'similarity': ratio
                        })
                    else:  # Too different, treat as delete + add
                        results.append({
                            'type': 'deleted',
                            'old': old_p,
                            'new': None,
                            'old_idx': i1 + idx + 1,
                            'new_idx': None
                        })
                        results.append({
                            'type': 'added',
                            'old': None,
                            'new': new_p,
                            'old_idx': None,
                            'new_idx': j1 + idx + 1
                        })
                elif old_p:
                    results.append({
                        'type': 'deleted',
                        'old': old_p,
                        'new': None,
                        'old_idx': i1 + idx + 1,
                        'new_idx': None
                    })
                elif new_p:
                    results.append({
                        'type': 'added',
                        'old': None,
                        'new': new_p,
                        'old_idx': None,
                        'new_idx': j1 + idx + 1
                    })
    
    return results


def match_chapters(chapters1, chapters2):
    """Match chapters between two EPUBs"""
    matched = []
    
    # Try to match by title or content similarity
    used_j = set()
    
    for i, ch1 in enumerate(chapters1):
        best_match = None
        best_score = 0
        
        for j, ch2 in enumerate(chapters2):
            if j in used_j:
                continue
            
            # Compare by title
            if ch1['title'] == ch2['title']:
                best_match = j
                best_score = 1.0
                break
            
            # Compare by content similarity
            ratio = difflib.SequenceMatcher(
                None, 
                ch1['full_text'][:500], 
                ch2['full_text'][:500]
            ).ratio()
            
            if ratio > best_score and ratio > 0.3:
                best_score = ratio
                best_match = j
        
        if best_match is not None:
            matched.append((i, best_match))
            used_j.add(best_match)
        else:
            matched.append((i, None))
    
    # Add unmatched chapters from epub2
    for j in range(len(chapters2)):
        if j not in used_j:
            matched.append((None, j))
    
    return matched


# ============ MAIN APP ============

st.title("📚 EPUB Difference Checker")
st.markdown("**Bandingkan dua file EPUB Korea dan temukan perbedaan konten**")

# File upload
col1, col2 = st.columns(2)

with col1:
    st.subheader("📖 EPUB Lama (Original)")
    epub1 = st.file_uploader("Upload EPUB pertama", type=['epub'], key='epub1')

with col2:
    st.subheader("📖 EPUB Baru (Revised)")
    epub2 = st.file_uploader("Upload EPUB kedua", type=['epub'], key='epub2')

# Options
st.sidebar.header("⚙️ Pengaturan")
show_same = st.sidebar.checkbox("Tampilkan paragraf yang sama", value=False)
show_context = st.sidebar.slider("Konteks paragraf", 0, 5, 1, 
                                  help="Jumlah paragraf sebelum/sesudah perbedaan")
min_similarity = st.sidebar.slider("Min. similarity untuk 'modified'", 0.3, 0.9, 0.5,
                                   help="Paragraf dengan similarity di bawah ini akan dianggap delete+add")

# Process
if epub1 and epub2:
    with st.spinner("Mengekstrak konten EPUB..."):
        try:
            chapters1 = extract_text_from_epub(BytesIO(epub1.read()))
            epub1.seek(0)
            chapters2 = extract_text_from_epub(BytesIO(epub2.read()))
            
            st.success(f"✅ Berhasil mengekstrak {len(chapters1)} chapter dari EPUB 1 dan {len(chapters2)} chapter dari EPUB 2")
            
            # Match chapters
            matched_chapters = match_chapters(chapters1, chapters2)
            
            # Statistics
            total_added = 0
            total_deleted = 0
            total_modified = 0
            
            # Chapter selection
            st.markdown("---")
            chapter_options = []
            for idx1, idx2 in matched_chapters:
                if idx1 is not None and idx2 is not None:
                    title = chapters1[idx1]['title']
                    chapter_options.append(f"Chapter: {title}")
                elif idx1 is not None:
                    title = chapters1[idx1]['title']
                    chapter_options.append(f"[DELETED] {title}")
                else:
                    title = chapters2[idx2]['title']
                    chapter_options.append(f"[NEW] {title}")
            
            selected_chapter = st.selectbox("Pilih Chapter untuk dilihat:", 
                                           ["-- Semua Chapter --"] + chapter_options)
            
            st.markdown("---")
            
            # Process each matched chapter pair
            for match_idx, (idx1, idx2) in enumerate(matched_chapters):
                chapter_name = chapter_options[match_idx]
                
                # Filter by selection
                if selected_chapter != "-- Semua Chapter --" and selected_chapter != chapter_name:
                    continue
                
                if idx1 is None:
                    # New chapter in epub2
                    ch2 = chapters2[idx2]
                    st.markdown(f"### 🆕 Chapter Baru: {ch2['title']}")
                    with st.expander("Lihat konten baru", expanded=False):
                        for p in ch2['paragraphs']:
                            st.markdown(f'<div class="paragraph"><span class="diff-added">{html.escape(p)}</span></div>', 
                                       unsafe_allow_html=True)
                    total_added += len(ch2['paragraphs'])
                    continue
                
                if idx2 is None:
                    # Deleted chapter from epub1
                    ch1 = chapters1[idx1]
                    st.markdown(f"### ❌ Chapter Dihapus: {ch1['title']}")
                    with st.expander("Lihat konten yang dihapus", expanded=False):
                        for p in ch1['paragraphs']:
                            st.markdown(f'<div class="paragraph"><span class="diff-removed">{html.escape(p)}</span></div>', 
                                       unsafe_allow_html=True)
                    total_deleted += len(ch1['paragraphs'])
                    continue
                
                # Both chapters exist - compare
                ch1 = chapters1[idx1]
                ch2 = chapters2[idx2]
                
                # Compare paragraphs
                diff_results = compare_paragraphs(ch1['paragraphs'], ch2['paragraphs'])
                
                # Count differences
                chapter_added = sum(1 for r in diff_results if r['type'] == 'added')
                chapter_deleted = sum(1 for r in diff_results if r['type'] == 'deleted')
                chapter_modified = sum(1 for r in diff_results if r['type'] == 'modified')
                
                total_added += chapter_added
                total_deleted += chapter_deleted
                total_modified += chapter_modified
                
                has_diff = chapter_added > 0 or chapter_deleted > 0 or chapter_modified > 0
                
                if has_diff or show_same:
                    status_icon = "✅" if not has_diff else "📝"
                    st.markdown(f"### {status_icon} {ch1['title']}")
                    
                    if has_diff:
                        st.markdown(f"""
                        <div class="stats-box">
                            <b>Statistik Chapter:</b> 
                            <span style="color: green;">+{chapter_added} ditambah</span> | 
                            <span style="color: red;">-{chapter_deleted} dihapus</span> | 
                            <span style="color: orange;">~{chapter_modified} diubah</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Display differences
                    with st.expander("Lihat detail perbedaan" if has_diff else "Lihat konten", 
                                    expanded=has_diff):
                        for i, result in enumerate(diff_results):
                            if result['type'] == 'same' and not show_same:
                                continue
                            
                            if result['type'] == 'added':
                                st.markdown(f"""
                                <div class="paragraph" style="border-left-color: #28a745;">
                                    <small>📍 Baris baru #{result['new_idx']}</small><br>
                                    <span class="diff-line diff-added">{html.escape(result['new'])}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            elif result['type'] == 'deleted':
                                st.markdown(f"""
                                <div class="paragraph" style="border-left-color: #dc3545;">
                                    <small>📍 Baris lama #{result['old_idx']} [DIHAPUS]</small><br>
                                    <span class="diff-line diff-removed">{html.escape(result['old'])}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            elif result['type'] == 'modified':
                                diff_html, _ = get_diff_html(result['old'], result['new'])
                                similarity_pct = int(result.get('similarity', 0) * 100)
                                st.markdown(f"""
                                <div class="paragraph" style="border-left-color: #ffc107;">
                                    <small>📍 Baris #{result['old_idx']} → #{result['new_idx']} 
                                    [DIUBAH - {similarity_pct}% mirip]</small><br>
                                    <div class="diff-line">{diff_html}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            elif result['type'] == 'same' and show_same:
                                st.markdown(f"""
                                <div class="paragraph" style="border-left-color: #6c757d; opacity: 0.7;">
                                    <small>📍 Baris #{result['old_idx']}</small><br>
                                    <span class="diff-line">{html.escape(result['old'])}</span>
                                </div>
                                """, unsafe_allow_html=True)
            
            # Summary
            st.markdown("---")
            st.markdown(f"""
            ## 📊 Ringkasan Total
            
            | Tipe | Jumlah |
            |------|--------|
            | ✅ Paragraf ditambah | **{total_added}** |
            | ❌ Paragraf dihapus | **{total_deleted}** |
            | 📝 Paragraf diubah | **{total_modified}** |
            """)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.exception(e)

else:
    st.info("👆 Upload kedua file EPUB untuk mulai membandingkan")
    
    st.markdown("""
    ### Cara Penggunaan:
    1. Upload EPUB lama (original) di kolom kiri
    2. Upload EPUB baru (revised) di kolom kanan
    3. Script akan otomatis menemukan perbedaan
    
    ### Fitur:
    - 🔍 Deteksi paragraf yang **ditambah** (hijau)
    - 🔍 Deteksi paragraf yang **dihapus** (merah)
    - 🔍 Deteksi paragraf yang **diubah** (kuning)
    - 📊 Statistik per chapter dan total
    - 🔎 Filter per chapter
    
    ### Warna Penanda:
    - <span style="background-color: #d4edda; padding: 2px 5px;">Teks baru/ditambah</span>
    - <span style="background-color: #f8d7da; padding: 2px 5px; text-decoration: line-through;">Teks dihapus</span>
    - <span style="background-color: #fff3cd; padding: 2px 5px;">Teks diubah</span>
    """, unsafe_allow_html=True)

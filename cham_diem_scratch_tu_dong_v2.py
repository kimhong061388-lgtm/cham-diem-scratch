import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests
import hashlib

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch Chính Xác", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #e0e0e0; }
    .result-card {
        background-color: white; padding: 25px; border-radius: 15px;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.1); margin-bottom: 20px;
        border-left: 10px solid #d32f2f;
    }
    .stButton>button {
        width: 100%; border-radius: 25px; background-color: #2e7d32;
        color: white; height: 3.5em; font-weight: bold; font-size: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập Họ tên, Lớp.\n2. Chọn Đề thi.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **LƯU Ý:** Chỉ nộp bài 01 lần duy nhất.")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 2. HÀM CHẤM ĐIỂM CHUYÊN SÂU ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    
    all_blocks = {}
    all_text_content = [] # Danh sách chứa tất cả chữ học sinh đã gõ trong bài
    
    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
        # Quét tất cả các giá trị văn bản trong blocks
        for b in t.get('blocks', {}).values():
            if isinstance(b, dict) and 'inputs' in b:
                for inp in b['inputs'].values():
                    if isinstance(inp, list) and len(inp) > 1:
                        val = str(inp[1])
                        if "[" not in val: all_text_content.append(chuan_hoa(val))

    raw_str = json.dumps(project_data).lower()
    full_text_all = " ".join(all_text_content)
    
    is_de1 = "Đề 1" in de_thi
    in1, in2, out = ('"l"', '"w"', '"i"') if is_de1 else ('"s"', '"t"', '"v"')

    # 1. Biến Có (0.5đ)
    ok1 = '"co"' in full_text_all or '"co"' in raw_str
    report.append(f"{'✅' if ok1 else '❌'} 1. Gán biến Trả lời = Có (0.5đ)")
    if ok1: total_score += 0.5

    # 2. Vòng lặp + Not (0.5đ)
    ok2 = 'control_repeat_until' in raw_str and 'operator_not' in raw_str
    report.append(f"{'✅' if ok2 else '❌'} 2. Vòng lặp Repeat Until + Not (0.5đ)")
    if ok2: total_score += 0.5

    # 3+4. Nhập liệu (1.0đ)
    ok_in1 = in1 in raw_str and 'sensing_askandwait' in raw_str
    ok_in2 = in2 in raw_str and 'sensing_askandwait' in raw_str
    if ok_in1 and ok_in2:
        total_score += 1.0; report.append(f"✅ 3+4. Nhập liệu đúng biến {in1.upper()}, {in2.upper()} (1.0đ)")
    else: report.append("❌ 3+4. Sai tên biến nhập liệu (0đ)")

    # 5. Công thức (1.0đ)
    ok5 = out in raw_str and in1 in raw_str and in2 in raw_str and 'operator_divide' in raw_str
    report.append(f"{'✅' if ok5 else '❌'} 5. Đúng công thức {out.upper()} = {in1.upper()} / {in2.upper()} (1.0đ)")
    if ok5: total_score += 1.0

    # 6. If-Else (0.5đ)
    ok6 = 'control_if_else' in raw_str
    report.append(f"{'✅' if ok6 else '❌'} 6. Có khối If-Else (0.5đ)")
    if ok6: total_score += 0.5

    # 7. Ngưỡng (0.5đ)
    targets = ["30", "40"] if is_de1 else ["0.5", "1"]
    ok7 = all(t in raw_str for t in targets)
    report.append(f"{'✅' if ok7 else '❌'} 7. Đúng ngưỡng {targets} (0.5đ)")
    if ok7: total_score += 0.5

    # --- SỬA LỖI MỤC 8, 9, 11 (TÌM KIẾM CHI TIẾT) ---
    t1 = "binh thuong" if is_de1 else "tap trung"
    t2 = "dieu chinh" if is_de1 else "hieu bai"
    
    ok8 = t1 in full_text_all
    report.append(f"{'✅' if ok8 else '❌'} 8. Thông báo kết quả 1 đúng (0.5đ)")
    if ok8: total_score += 0.5

    ok9 = t2 in full_text_all
    report.append(f"{'✅' if ok9 else '❌'} 9. Thông báo kết quả 2 đúng (0.5đ)")
    if ok9: total_score += 0.5

    # 10. Tiếp tục (0.5đ)
    ok10 = raw_str.count('sensing_askandwait') >= 3 or "tiep tuc" in full_text_all
    report.append(f"{'✅' if ok10 else '❌'} 10. Có hỏi để lặp lại (0.5đ)")
    if ok10: total_score += 0.5

    # 11. Kết thúc (0.5đ)
    ok11 = "ket thuc" in full_text_all or "xong" in full_text_all
    report.append(f"{'✅' if ok11 else '❌'} 11. Có thông báo Kết thúc (0.5đ)")
    if ok11: total_score += 0.5

    return round(total_score, 1), report

# --- 3. GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh (Viết hoa có dấu):")
    lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3:", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM NGAY"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            ma_dinh_danh = hashlib.md5(file_bytes).hexdigest()[:10].upper()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            time_str = (datetime.now() + timedelta(hours=7)).strftime("%H:%M:%S %d/%m/%Y")
            
            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)
            
            try:
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ma_dinh_danh": ma_dinh_danh}, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài nộp: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            
            with st.expander("🔍 Chi tiết bảng chấm điểm 11 tiêu chí", expanded=True):
                for d in details: st.write(d)
        except: st.error("❌ File không hợp lệ!")
    else: st.warning("⚠️ Vui lòng điền đủ tên và tải file!")

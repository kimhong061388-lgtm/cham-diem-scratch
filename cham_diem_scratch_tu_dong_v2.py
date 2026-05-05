import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests
import hashlib

# --- 1. CẤU HÌNH GIAO DIỆN (UI) ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏆", layout="wide")

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

# --- 2. THANH HƯỚNG DẪN BÊN TRÁI (SIDEBAR) ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("""
    **Các bước thực hiện:**
    1. 👤 **Nhập thông tin:** Gõ đúng Họ tên và chọn Lớp.
    2. 📝 **Chọn đề:** Chọn đúng đề thi em đã làm.
    3. 📂 **Tải bài:** Chọn file `.sb3` từ máy tính.
    4. 🚀 **Nộp bài:** Nhấn nút màu xanh để xem điểm.
    """)
    st.warning("""
    **Lưu ý quan trọng:**
    - Hệ thống chấm theo logic khối lệnh.
    - **Mỗi học sinh chỉ nộp bài 01 lần duy nhất.**
    - Hình thức gian lận (dùng chung file) sẽ bị phát hiện tự động.
    - Tải ngay **Phiếu điểm** sau khi nộp xong.
    """)
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

# --- 3. CẤU HÌNH KẾT NỐI & CHUẨN HÓA ---
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- 4. HÀM CHẤM ĐIỂM CHI TIẾT ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    all_blocks = {}
    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
    
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có
    has_set_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks.values())
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3 & 4. Nhập liệu - Đồng thời xác định tên biến L,W hoặc S,T
    input_vars = []
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            if 'sensing_answer' in str(b.get('inputs', {}).get('VALUE', '')):
                var_name = b.get('fields', {}).get('VARIABLE', [None])
                if var_name: input_vars.append(var_name)

    if len(input_vars) >= 2: total_score += 1.0; report.append("✅ 3+4. Nhập đủ 2 dữ liệu (1.0đ)")
    elif len(input_vars) == 1: total_score += 0.5; report.append("✅ 3. Nhập được 1 dữ liệu (0.5đ)")
    else: report.append("❌ 3+4. Thiếu nhập liệu (0đ)")

    # 5. Công thức (Bắt lỗi gán đè và thứ tự)
    formula_ok = False
    if len(input_vars) >= 2:
        v1, v2 = input_vars[0], input_vars[1]
        for b in all_blocks.values():
            if b.get('opcode') == 'data_setvariableto':
                target_var = b.get('fields', {}).get('VARIABLE', [None])
                val_input = b.get('inputs', {}).get('VALUE', [])
                if isinstance(val_input, list) and len(val_input) > 1:
                    child = all_blocks.get(val_input[1])
                    if child and child.get('opcode') == 'operator_divide':
                        n1 = str(child.get('inputs', {}).get('NUM1', ''))
                        n2 = str(child.get('inputs', {}).get('NUM2', ''))
                        if (v1 in n1) and (v2 in n2) and (target_var != v1) and (target_var != v2):
                            formula_ok = True; script_desc.append(f"[Toán: {target_var}={v1}/{v2}]"); break
    
    if formula_ok: total_score += 1.0; report.append("✅ 5. Đúng công thức & thứ tự phép tính (1.0đ)")
    else: report.append("❌ 5. Sai công thức, sai thứ tự hoặc gán đè biến (0đ)"); script_desc.append("[Toán: SAI]")

    # 6. If-Else
    if 'control_if_else' in code_str: total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)")

    # 7. Logic ngưỡng
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if all(t in code_str for t in targets): total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng {targets} (0.5đ)")
    else: report.append("❌ 7. Sai logic ngưỡng (0đ)")

    # 8 & 9. Thông báo
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK")

    # 10. Tiếp tục
    asks = [b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Kết thúc bài (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo kết thúc (0đ)")

    return round(total_score, 1), " | ".join(script_desc), report

# --- 5. GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh (Viết hoa có dấu):")
    lop_hs = st.selectbox("🏫 Em học lớp nào:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi em đã thực hiện:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3 của em:", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM NGAY"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            # TẠO MÃ VÂN TAY FILE
            ma_dinh_danh = hashlib.md5(file_bytes).hexdigest()[:10].upper()
            
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            
            score, summary, details = grade_by_logic_barem(data, de_thi)
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")

            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)

            try:
                requests.post(WEBHOOK_URL, json={
                    "Thoi_gian": time_str, "Hoc_sinh": ten_hs, 
                    "Lop": lop_hs, "De": de_thi, "Diem": score, 
                    "Ghi_chu": summary, "Ma_dinh_danh": ma_dinh_danh
                }, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài nộp: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")

            with st.expander("🔍 Chi tiết bảng điểm", expanded=True):
                for d in details: st.write(d)
                
            if score == 6.0: st.balloons()
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"HS: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nMa: {ma_dinh_danh}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("❌ Lỗi: File không hợp lệ!")
    else: st.warning("⚠️ Vui lòng điền đủ tên và tải file!")

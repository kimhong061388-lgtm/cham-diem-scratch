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

# --- 2. SIDEBAR HƯỚNG DẪN ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập Họ tên, Lớp.\n2. Chọn đúng Đề thi.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **QUY ĐỊNH:** Chỉ nộp bài 01 lần duy nhất. Hệ thống tự phát hiện gian lận.")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# !!! QUAN TRỌNG: DÁN LINK WEBHOOK CỦA BẠN VÀO ĐÂY !!!
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 3. HÀM CHẤM ĐIỂM SIÊU CHÍNH XÁC ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    
    # Gom toàn bộ nội dung bài làm thành 1 chuỗi văn bản sạch (đã bỏ dấu)
    huge_text = chuan_hoa(json.dumps(project_data, ensure_ascii=False))
    
    all_blocks = {}
    var_map = {}
    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
        for v_id, v_info in t.get('variables', {}).items():
            var_map[v_id] = chuan_hoa(v_info[0] if isinstance(v_info, list) else v_info)

    is_de1 = "Đề 1" in de_thi
    req_in1, req_in2, req_out = ('l', 'w', 'i') if is_de1 else ('s', 't', 'v')

    # 1. Biến Trả lời = Có (0.5đ)
    ok1 = '"co"' in huge_text and 'data_setvariableto' in huge_text
    report.append(f"{'✅' if ok1 else '❌'} 1. Gán biến Trả lời = Có (0.5đ)")
    if ok1: total_score += 0.5

    # 2. Vòng lặp + Not (0.5đ)
    ok2 = 'control_repeat_until' in huge_text and 'operator_not' in huge_text
    report.append(f"{'✅' if ok2 else '❌'} 2. Vòng lặp Repeat Until + Not (0.5đ)")
    if ok2: total_score += 0.5

    # 3+4. Nhập liệu (1.0đ)
    assigned_vars = set()
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto' and 'sensing_answer' in str(b.get('inputs', {})):
            v_id = b.get('fields', {}).get('VARIABLE', [None])[0]
            if v_id in var_map: assigned_vars.add(var_map[v_id])
    ok34 = req_in1 in assigned_vars and req_in2 in assigned_vars
    report.append(f"{'✅' if ok34 else '❌'} 3+4. Nhập đủ biến {req_in1.upper()}, {req_in2.upper()} (1.0đ)")
    if ok34: total_score += 1.0

    # 5. Công thức (1.0đ) - Kiểm tra biến nhận, tử số, mẫu số
    formula_ok = False
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            v_res_id = b.get('fields', {}).get('VARIABLE', [None])[0]
            if var_map.get(v_res_id) == req_out:
                val_input = b.get('inputs', {}).get('VALUE', [])
                if isinstance(val_input, list) and len(val_input) > 1:
                    child = all_blocks.get(val_input[1])
                    if child and child.get('opcode') == 'operator_divide':
                        def get_n(key):
                            d = child.get('inputs', {}).get(key, [])
                            if isinstance(d, list) and len(d) > 1:
                                sub = all_blocks.get(d[1])
                                if sub and sub.get('opcode') == 'data_variable':
                                    return var_map.get(sub.get('fields', {}).get('VARIABLE', [None])[0], "")
                            return ""
                        if get_n('NUM1') == req_in1 and get_n('NUM2') == req_in2:
                            formula_ok = True; break
    report.append(f"{'✅' if formula_ok else '❌'} 5. Đúng công thức {req_out.upper()} = {req_in1.upper()} / {req_in2.upper()} (1.0đ)")
    if formula_ok: total_score += 1.0

    # 6. If-Else (0.5đ)
    ok6 = 'control_if_else' in huge_text
    report.append(f"{'✅' if ok6 else '❌'} 6. Có khối If-Else (0.5đ)")
    if ok6: total_score += 0.5

    # 7. Ngưỡng (0.5đ)
    targets = ["30", "40"] if is_de1 else ["0.5", "1"]
    ok7 = all(f'"{t}"' in huge_text or f" {t} " in huge_text for t in targets)
    report.append(f"{'✅' if ok7 else '❌'} 7. Đúng ngưỡng {targets} (0.5đ)")
    if ok7: total_score += 0.5

    # --- SỬA LỖI MỤC 8, 9, 11 (TÌM KIẾM TRÊN TOÀN BỘ VĂN BẢN) ---
    t1 = "binh thuong" if is_de1 else "tap trung"
    t2 = "dieu chinh" if is_de1 else "hieu bai"
    
    ok8 = t1 in huge_text
    report.append(f"{'✅' if ok8 else '❌'} 8. Thông báo kết quả 1 đúng (0.5đ)")
    if ok8: total_score += 0.5

    ok9 = t2 in huge_text
    report.append(f"{'✅' if ok9 else '❌'} 9. Thông báo kết quả 2 đúng (0.5đ)")
    if ok9: total_score += 0.5

    # 10. Tiếp tục
    ok10 = huge_text.count('sensing_askandwait') >= 3 or "tiep tuc" in huge_text
    report.append(f"{'✅' if ok10 else '❌'} 10. Có hỏi để lặp lại (0.5đ)")
    if ok10: total_score += 0.5

    # 11. Kết thúc
    ok11 = "ket thuc" in huge_text
    report.append(f"{'✅' if ok11 else '❌'} 11. Có thông báo Kết thúc (0.5đ)")
    if ok11: total_score += 0.5

    return round(total_score, 1), report

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh (Viết hoa có dấu):")
    lop_hs = st.selectbox("🏫 Em học lớp nào:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi đã làm:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
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
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ghi_chu": "OK", "Ma_dinh_danh": ma_dinh_danh}, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            
            with st.expander("🔍 Chi tiết bảng chấm điểm 11 tiêu chí", expanded=True):
                for d in details: st.write(d)
            if score == 6.0: st.balloons()
        except: st.error("❌ File không hợp lệ!")
    else: st.warning("⚠️ Vui lòng điền đủ tên và tải file!")

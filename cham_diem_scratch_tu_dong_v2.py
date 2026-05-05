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
    st.info("1. Nhập Họ tên, Lớp.\n2. Chọn Đề thi.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **QUY ĐỊNH:**\n- Chỉ nộp bài 01 lần.\n- Đặt tên biến đúng yêu cầu (L, W, I hoặc S, T, V).")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 3. HÀM CHẤM ĐIỂM CHI TIẾT ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    all_blocks = {}
    all_vars = {}

    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
        for v_id, v_info in t.get('variables', {}).items():
            all_vars[v_id] = chuan_hoa(v_info[0])

    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # Quy tắc đề
    is_de1 = "Đề 1" in de_thi
    req_in1, req_in2, req_out = ('l', 'w', 'i') if is_de1 else ('s', 't', 'v')

    # 1. Biến Có (0.5đ)
    has_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks.values())
    report.append(f"{'✅' if has_co else '❌'} 1. Gán biến Trả lời = Có (0.5đ)")
    if has_co: total_score += 0.5

    # 2. Repeat + Not (0.5đ)
    has_loop = 'control_repeat_until' in code_str and 'operator_not' in code_str
    report.append(f"{'✅' if has_loop else '❌'} 2. Vòng lặp Repeat Until + Not (0.5đ)")
    if has_loop: total_score += 0.5

    # 3+4. Nhập liệu (1.0đ)
    found_in = []
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto' and 'sensing_answer' in str(b.get('inputs', {})):
            v_id = b.get('fields', {}).get('VARIABLE', [None])[0]
            name = all_vars.get(v_id, "")
            if name == req_in1 or name == req_in2: found_in.append(name)
    
    ok_in = len(set(found_in)) >= 2
    report.append(f"{'✅' if ok_in else '❌'} 3+4. Nhập đủ 2 biến {req_in1.upper()}, {req_in2.upper()} (1.0đ)")
    if ok_in: total_score += 1.0

    # 5. Công thức (1.0đ)
    formula_ok = False
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            v_id = b.get('fields', {}).get('VARIABLE', [None])[0]
            if all_vars.get(v_id) == req_out:
                val = b.get('inputs', {}).get('VALUE', [])
                if isinstance(val, list) and len(val) > 1:
                    child = all_blocks.get(val[1])
                    if child and child.get('opcode') == 'operator_divide':
                        n1 = str(child.get('inputs', {}).get('NUM1', ''))
                        n2 = str(child.get('inputs', {}).get('NUM2', ''))
                        # Kiểm tra xem ID biến đầu vào có nằm trong phép chia không
                        def check_var_in_input(input_data, target_name):
                            if isinstance(input_data, list) and len(input_data) > 1:
                                sub = all_blocks.get(input_data[1])
                                if sub and all_vars.get(sub.get('fields', {}).get('VARIABLE', [None])[0]) == target_name:
                                    return True
                            return False
                        if check_var_in_input(child.get('inputs', {}).get('NUM1', []), req_in1) and \
                           check_var_in_input(child.get('inputs', {}).get('NUM2', []), req_in2):
                            formula_ok = True; break

    report.append(f"{'✅' if formula_ok else '❌'} 5. Đúng công thức {req_out.upper()} = {req_in1.upper()} / {req_in2.upper()} (1.0đ)")
    if formula_ok: total_score += 1.0; script_desc.append(f"[Toán OK: {req_out}={req_in1}/{req_in2}]")
    else: script_desc.append("[Toán SAI]")

    # 6. If-Else (0.5đ)
    has_if = 'control_if_else' in code_str
    report.append(f"{'✅' if has_if else '❌'} 6. Có khối If-Else (0.5đ)")
    if has_if: total_score += 0.5

    # 7. Ngưỡng (0.5đ)
    targets = ["30", "40"] if is_de1 else ["0.5", "1"]
    has_target = all(t in code_str for t in targets)
    report.append(f"{'✅' if has_target else '❌'} 7. Đúng ngưỡng {targets} (0.5đ)")
    if has_target: total_score += 0.5

    # 8, 9. Thông báo (1.0đ)
    ok8 = any(k in full_txt for k in ["binh thuong", "tap trung"])
    ok9 = any(k in full_txt for k in ["dieu chinh", "hieu bai"])
    report.append(f"{'✅' if ok8 else '❌'} 8. Thông báo 1 OK (0.5đ)")
    report.append(f"{'✅' if ok9 else '❌'} 9. Thông báo 2 OK (0.5đ)")
    if ok8: total_score += 0.5
    if ok9: total_score += 0.5

    # 10. Tiếp tục (0.5đ)
    asks = [b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait']
    ok10 = len(asks) >= 3
    report.append(f"{'✅' if ok10 else '❌'} 10. Có hỏi tiếp tục (0.5đ)")
    if ok10: total_score += 0.5

    # 11. Kết thúc (0.5đ)
    ok11 = "ket thuc" in full_txt
    report.append(f"{'✅' if ok11 else '❌'} 11. Thông báo kết thúc (0.5đ)")
    if ok11: total_score += 0.5

    return round(total_score, 1), " | ".join(script_desc), report

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh (Viết hoa có dấu):")
    lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3:", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            ma_dinh_danh = hashlib.md5(file_bytes).hexdigest()[:10].upper()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, summary, details = grade_by_logic_barem(data, de_thi)
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)
            try:
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ghi_chu": summary, "Ma_dinh_danh": ma_dinh_danh}, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            with st.expander("🔍 Chi tiết bảng chấm điểm", expanded=True):
                for d in details: st.write(d)
        except Exception as e:
            st.error(f"❌ File không hợp lệ hoặc bị lỗi cấu trúc!")
    else: st.warning("⚠️ Vui lòng điền đủ tên và chọn file!")

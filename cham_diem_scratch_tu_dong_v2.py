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

# --- 2. SIDEBAR HƯỚNG DẪN ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập chính xác Họ tên, Lớp.\n2. Chọn đúng Đề thi.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **QUY ĐỊNH THI:**\n- Chỉ nộp bài 01 lần duy nhất.\n- Đặt tên biến đúng yêu cầu đề bài.\n- Gian lận sẽ bị phát hiện tự động.")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 3. HÀM CHẤM ĐIỂM SIÊU KHẮT KHE ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    
    all_blocks = {}
    all_variables = {} # Lưu trữ ID biến và Tên biến thực tế
    
    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
        # Ánh xạ ID biến sang Tên biến (vđ: "id1" -> "L")
        for var_id, var_info in t.get('variables', {}).items():
            all_variables[var_id] = var_info[0]
    
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có (0.5đ)
    has_set_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks.values())
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3+4 & 5. KIỂM TRA BIẾN VÀ CÔNG THỨC CHÍNH XÁC
    is_de1 = "Đề 1" in de_thi
    req_in1 = "l" if is_de1 else "s"
    req_in2 = "w" if is_de1 else "t"
    req_out = "i" if is_de1 else "v"
    
    found_in1 = False
    found_in2 = False
    formula_ok = False
    
    # Duyệt tìm các lệnh đặt biến
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            var_id = b.get('fields', {}).get('VARIABLE', [None])[0]
            var_name = chuan_hoa(all_variables.get(var_id, ""))
            val_input = b.get('inputs', {}).get('VALUE', [])

            # Kiểm tra nhập liệu (3+4)
            if 'sensing_answer' in str(val_input):
                if var_name == req_in1: found_in1 = True
                if var_name == req_in2: found_in2 = True
            
            # Kiểm tra công thức (5)
            if isinstance(val_input, list) and len(val_input) > 1:
                child_id = val_input[1]
                child_block = all_blocks.get(child_id)
                if child_block and child_block.get('opcode') == 'operator_divide':
                    # Kiểm tra tên biến kết quả
                    if var_name == req_out:
                        # Kiểm tra tử số và mẫu số
                        n1_data = child_block.get('inputs', {}).get('NUM1', [])
                        n2_data = child_block.get('inputs', {}).get('NUM2', [])
                        
                        # Lấy ID biến bên trong phép chia
                        def get_var_name_from_input(data):
                            if isinstance(data, list) and len(data) > 1:
                                sub_block = all_blocks.get(data[1])
                                if sub_block and sub_block.get('opcode') == 'data_variable':
                                    v_id = sub_block.get('fields', {}).get('VARIABLE', [None])[0]
                                    return chuan_hoa(all_variables.get(v_id, ""))
                            return ""

                        name_n1 = get_var_name_from_input(n1_data)
                        name_n2 = get_var_name_from_input(n2_data)

                        if name_n1 == req_in1 and name_n2 == req_in2:
                            formula_ok = True

    # Chấm điểm 3+4
    if found_in1 and found_in2:
        total_score += 1.0; report.append(f"✅ 3+4. Nhập liệu đúng biến {req_in1.upper()}, {req_in2.upper()} (1.0đ)")
    else:
        report.append(f"❌ 3+4. Sai tên biến nhập liệu (Yêu cầu: {req_in1.upper()}, {req_in2.upper()}) (0đ)")

    # Chấm điểm 5
    if formula_ok:
        total_score += 1.0; report.append(f"✅ 5. Đúng công thức {req_out.upper()} = {req_in1.upper()} / {req_in2.upper()} (1.0đ)")
        script_desc.append(f"[Toán: {req_out}={req_in1}/{req_in2}]")
    else:
        report.append(f"❌ 5. Sai công thức, sai tên biến hoặc sai thứ tự chia (0đ)")
        script_desc.append("[Toán: SAI]")

    # 6. If-Else (0.5đ)
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)")

    # 7. Logic ngưỡng (0.5đ)
    targets = ["30", "40"] if is_de1 else ["0.5", "1"]
    if all(t in code_str for t in targets): total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng {targets} (0.5đ)")
    else: report.append("❌ 7. Sai logic ngưỡng (0đ)")

    # 8, 9, 11. Thông báo
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Kết thúc OK")

    # 10. Tiếp tục (0.5đ)
    asks = [b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

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
                requests.post(WEBHOOK_URL, json={
                    "Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, 
                    "De": de_thi, "Diem": score, "Ghi_chu": summary, "Ma_dinh_danh": ma_dinh_danh
                }, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài nộp: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, điểm chưa vào Sheets. Hãy tải phiếu điểm báo GV!")
            
            with st.expander("🔍 Chi tiết bảng chấm điểm 11 tiêu chí", expanded=True):
                for d in details: st.write(d)
        except: st.error("❌ File không hợp lệ hoặc bị lỗi cấu trúc!")
    else: st.warning("⚠️ Vui lòng nhập đầy đủ tên và chọn file!")

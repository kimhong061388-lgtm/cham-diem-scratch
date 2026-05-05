import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch Chính Xác", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .result-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0px 10px 25px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 10px solid #d32f2f; }
    .stButton>button { width: 100%; border-radius: 25px; background-color: #2e7d32; color: white; height: 3.5em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập thông tin\n2. Chọn đúng Đề thi\n3. Tải file .sb3\n4. Nhấn Nộp bài")
    st.warning("⚠️ CHỈ NỘP 01 LẦN.")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbzGbMWbgWnkg9IEEC9wxUPKKNOAohBuAWdmlvq3qfEVcrBqbzxlh8vnwKPQXf8WwbpyXw/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM CHI TIẾT ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    all_blocks = {}
    for t in project_data.get('targets', []):
        all_blocks.update(t.get('blocks', {}))
    
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có (0.5đ)
    has_set_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks.values())
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu biến 'Có' (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3 & 4. Xác định thứ tự gán biến nhập liệu (L, W hoặc S, T)
    input_vars = []
    # Quét tất cả các block theo thứ tự xuất hiện để tìm biến được gán 'answer'
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            val_input = str(b.get('inputs', {}).get('VALUE', ''))
            if 'sensing_answer' in val_input:
                var_name = b.get('fields', {}).get('VARIABLE', [None])[0]
                if var_name: input_vars.append(var_name)

    if len(input_vars) >= 2: 
        total_score += 1.0; report.append("✅ 3+4. Nhập đủ 2 dữ liệu (1.0đ)")
    elif len(input_vars) == 1: 
        total_score += 0.5; report.append("✅ 3. Nhập được 1 dữ liệu (0.5đ)")
    else: report.append("❌ 3+4. Thiếu nhập liệu (0đ)")

    # 5. KIỂM TRA CÔNG THỨC (I = L/W hoặc V = S/T)
    formula_ok = False
    if len(input_vars) >= 2:
        var_1 = input_vars[0] # L hoặc S
        var_2 = input_vars[1] # W hoặc T
        
        for b in all_blocks.values():
            if b.get('opcode') == 'data_setvariableto':
                target_var = b.get('fields', {}).get('VARIABLE', [None])[0]
                val_input = b.get('inputs', {}).get('VALUE', [])
                
                # Kiểm tra nếu giá trị là một khối lệnh (mảng)
                if isinstance(val_input, list) and len(val_input) > 1:
                    child_id = val_input[1]
                    child_block = all_blocks.get(child_id)
                    
                    if child_block and child_block.get('opcode') == 'operator_divide':
                        # Lấy ID của khối nằm ở tử số và mẫu số
                        num1_data = child_block.get('inputs', {}).get('NUM1', [])
                        num2_data = child_block.get('inputs', {}).get('NUM2', [])
                        
                        # Chuyển dữ liệu ID khối thành chuỗi để tìm tên biến bên trong
                        num1_str = str(all_blocks.get(num1_data[1])) if len(num1_data) > 1 else str(num1_data)
                        num2_str = str(all_blocks.get(num2_data[1])) if len(num2_data) > 1 else str(num2_data)

                        # ĐIỀU KIỆN: 
                        # 1. Tử số chứa biến 1, Mẫu số chứa biến 2
                        # 2. Biến nhận kết quả KHÔNG ĐƯỢC trùng với biến 1 hoặc 2
                        if (var_1 in num1_str) and (var_2 in num2_str) and (target_var != var_1) and (target_var != var_2):
                            formula_ok = True
                            script_desc.append(f"[Toán: {target_var}={var_1}/{var_2}]")
                            break
    
    if formula_ok:
        total_score += 1.0; report.append("✅ 5. Đúng công thức & thứ tự phép chia (1.0đ)")
    else:
        report.append("❌ 5. Sai công thức, sai thứ tự hoặc gán đè biến (0đ)")
        script_desc.append("[Toán: SAI LOGIC]")

    # 6. If-Else (0.5đ)
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)")

    # 7. Logic ngưỡng (0.5đ)
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if all(t in code_str for t in targets) and ('operator_lt' in code_str or 'operator_gt' in code_str):
        total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng so sánh {targets} (0.5đ)")
    else: report.append("❌ 7. Sai logic ngưỡng (0đ)")

    # 8, 9, 11. Thông báo (0.5đ mỗi mục)
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Kết thúc OK")

    # 10. Tiếp tục (0.5đ)
    asks = [b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

    return round(total_score, 1), " | ".join(script_desc), report

# --- GIAO DIỆN ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh:")
    lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, summary, details = grade_by_logic_barem(data, de_thi)
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)
            try:
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ghi_chu": summary}, timeout=10)
                st.success("🎉 Đã lưu điểm thành công!")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            with st.expander("🔍 Chi tiết chấm điểm", expanded=True):
                for d in details: st.write(d)
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"HS: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nLog: {summary}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("❌ File Scratch không hợp lệ!")
    else: st.warning("Vui lòng điền đủ thông tin!")

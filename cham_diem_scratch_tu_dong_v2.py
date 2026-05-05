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
    st.info("1. Nhập thông tin cá nhân.\n2. Chọn đúng đề bài.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **QUY ĐỊNH:**\n- Chỉ nộp bài 01 lần.\n- Đặt tên biến đúng (L, W, I hoặc S, T, V).\n- Công thức phải đúng thứ tự.")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    # Chuyển về chữ thường, bỏ dấu và lấy tên gốc nếu là danh sách của Scratch
    txt = str(van_ban)
    return unidecode(txt).lower().strip()

# LINK WEBHOOK CỦA BẠN (GIỮ NGUYÊN)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 3. HÀM CHẤM ĐIỂM "SIÊU CHÍNH XÁC" ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    
    all_blocks = {}
    var_id_to_name = {}

    # BƯỚC 1: QUÉT SÂU ĐỂ LẤY CHÍNH XÁC TÊN BIẾN
    for target in project_data.get('targets', []):
        for v_id, v_info in target.get('variables', {}).items():
            # v_info trong Scratch 3.0 là list: ["Tên_Biến", giá_trị]
            # Ta chỉ lấy phần tử đầu tiên là Tên
            raw_name = v_info[0] if isinstance(v_info, list) else v_info
            var_id_to_name[v_id] = chuan_hoa(raw_name)
        all_blocks.update(target.get('blocks', {}))

    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)
    
    is_de1 = "Đề 1" in de_thi
    req_in1, req_in2, req_out = ('l', 'w', 'i') if is_de1 else ('s', 't', 'v')

    # --- BẮT ĐẦU CHẤM ---

    # 1. Biến Trả lời = Có (0.5đ)
    has_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks.values())
    if has_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3+4. NHẬP LIỆU (Sửa lỗi nhận diện tên biến)
    vars_assigned_answer = set()
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            val_input = str(b.get('inputs', {}).get('VALUE', ''))
            if 'sensing_answer' in val_input:
                v_id = b.get('fields', {}).get('VARIABLE', [None])
                if isinstance(v_id, list): v_id = v_id[0]
                if v_id in var_id_to_name:
                    vars_assigned_answer.add(var_id_to_name[v_id])

    if req_in1 in vars_assigned_answer and req_in2 in vars_assigned_answer:
        total_score += 1.0; report.append(f"✅ 3+4. Nhập đủ 2 biến {req_in1.upper()}, {req_in2.upper()} (1.0đ)")
    else:
        report.append(f"❌ 3+4. Sai tên biến nhập liệu (Yêu cầu: {req_in1.upper()}, {req_in2.upper()}) (0đ)")

    # 5. CÔNG THỨC (Sửa lỗi nhận diện sâu)
    formula_ok = False
    for b in all_blocks.values():
        if b.get('opcode') == 'data_setvariableto':
            v_target_id = b.get('fields', {}).get('VARIABLE', [None])
            if isinstance(v_target_id, list): v_target_id = v_target_id[0]
            
            if var_id_to_name.get(v_target_id) == req_out:
                val_input = b.get('inputs', {}).get('VALUE', [])
                # Kiểm tra khối phép chia
                if isinstance(val_input, list) and len(val_input) > 1:
                    child_id = val_input[1]
                    child = all_blocks.get(child_id)
                    if child and child.get('opcode') == 'operator_divide':
                        def get_var_name(inp_key):
                            inp_data = child.get('inputs', {}).get(inp_key, [])
                            if isinstance(inp_data, list) and len(inp_data) > 1:
                                sub_id = inp_data[1]
                                sub_b = all_blocks.get(sub_id)
                                if sub_b and sub_b.get('opcode') == 'data_variable':
                                    vid = sub_b.get('fields', {}).get('VARIABLE', [None])
                                    if isinstance(vid, list): vid = vid[0]
                                    return var_id_to_name.get(vid, "")
                            return ""
                        
                        n1 = get_var_name('NUM1')
                        n2 = get_var_name('NUM2')
                        if n1 == req_in1 and n2 == req_in2:
                            formula_ok = True; break

    if formula_ok:
        total_score += 1.0; report.append(f"✅ 5. Đúng công thức {req_out.upper()} = {req_in1.upper()} / {req_in2.upper()} (1.0đ)")
        script_desc.append(f"[Toán OK: {req_out}={req_in1}/{req_in2}]")
    else:
        report.append("❌ 5. Sai công thức, tên biến hoặc thứ tự (0đ)")
        script_desc.append("[Toán SAI]")

    # 6 & 7. If-Else và Ngưỡng
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        targets = ["30", "40"] if is_de1 else ["0.5", "1"]
        if all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng {targets} (0.5đ)")
        else: report.append("❌ 7. Sai ngưỡng logic (0đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)"); report.append("❌ 7. Không chấm logic (0đ)")

    # 8, 9, 11. Thông báo
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục (Đưa lên trước mục 11)
    asks_count = len([b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait'])
    if asks_count >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi để lặp bài (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Thông báo kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu kết thúc (0đ)")

    return round(total_score, 1), " | ".join(script_desc), report

# --- 4. GIAO DIỆN CHÍNH ---
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
            ma_dinh_danh = hashlib.md5(file_bytes).hexdigest()[:10].upper()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            
            score, summary, details = grade_by_logic_barem(data, de_thi)
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)
            
            try:
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ghi_chu": summary, "Ma_dinh_danh": ma_dinh_danh}, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài nộp: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            
            with st.expander("🔍 Chi tiết bảng chấm điểm 11 tiêu chí", expanded=True):
                for d in details: st.write(d)
        except: st.error("❌ File không hợp lệ hoặc bị lỗi cấu trúc!")
    else: st.warning("⚠️ Vui lòng điền đủ tên và tải file!")

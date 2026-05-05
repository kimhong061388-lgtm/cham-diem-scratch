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
    .result-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0px 10px 25px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 10px solid #2e7d32; }
    .stButton>button { width: 100%; border-radius: 25px; background-color: #2e7d32; color: white; height: 3.5em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập Họ tên, Lớp\n2. Chọn Đề thi\n3. Tải file .sb3\n4. Nhấn Nộp bài")
    st.warning("⚠️ CHỈ NỘP BÀI 01 LẦN DUY NHẤT.")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbzGbMWbgWnkg9IEEC9wxUPKKNOAohBuAWdmlvq3qfEVcrBqbzxlh8vnwKPQXf8WwbpyXw/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM CẢI TIẾN ---
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
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3 & 4. NHẬP LIỆU (Đếm trực tiếp khối Ask - Khắc phục lỗi chấm sai)
    asks = [b for b in all_blocks.values() if b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 2: 
        total_score += 1.0; report.append("✅ 3+4. Nhập đủ 2 dữ liệu đầu vào (1.0đ)")
        script_desc.append(f"[Hỏi: {len(asks)} câu]")
    elif len(asks) == 1: 
        total_score += 0.5; report.append("✅ 3. Nhập được 1 dữ liệu đầu vào (0.5đ)")
        script_desc.append("[Hỏi: 1 câu]")
    else: 
        report.append("❌ 3+4. Thiếu lệnh nhập dữ liệu (0đ)")

    # 5. CÔNG THỨC (Kiểm tra phép chia và gán biến)
    formula_ok = False
    if 'operator_divide' in code_str:
        # Tìm khối đặt biến có chứa phép chia bên trong
        for b in all_blocks.values():
            if b.get('opcode') == 'data_setvariableto':
                val_input = str(b.get('inputs', {}).get('VALUE', ''))
                if 'operator_divide' in val_input:
                    # Kiểm tra gán đè: lấy ID biến nhận kết quả
                    var_target = str(b.get('fields', {}).get('VARIABLE', ['']))
                    # Nếu biến nhận kết quả KHÔNG xuất hiện trong nội dung gán -> Tạm coi là OK
                    if var_target.lower() not in val_input.lower():
                        formula_ok = True
                        break
    
    if formula_ok:
        total_score += 1.0; report.append("✅ 5. Đúng công thức và thứ tự phép chia (1.0đ)")
        script_desc.append("[Toán: OK]")
    else:
        report.append("❌ 5. Sai công thức, thứ tự hoặc gán đè biến (0đ)")
        script_desc.append("[Toán: SAI]")

    # 6. If-Else (0.5đ)
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)")

    # 7. Logic ngưỡng (0.5đ)
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if all(t in code_str for t in targets):
        total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng so sánh {targets} (0.5đ)")
    else: report.append("❌ 7. Sai logic ngưỡng (0đ)")

    # 8 & 9. Thông báo
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK")

    # 10. Tiếp tục (Đưa lên trước 11)
    if len(asks) >= 3: 
        total_score += 0.5; report.append("✅ 10. Có hỏi để tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

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
                st.success("🎉 Đã lưu điểm thành công vào danh sách lớp!")
            except: st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")
            
            with st.expander("🔍 Chi tiết bảng chấm điểm", expanded=True):
                for d in details: st.write(d)
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"HS: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nLog: {summary}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("❌ File Scratch không hợp lệ!")
    else: st.warning("Vui lòng điền đủ tên và tải file!")

import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch Pro", page_icon="🏆", layout="centered")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stButton>button { width: 100%; border-radius: 25px; background-color: #2e7d32; color: white; font-weight: bold; }
    .result-card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0px 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyLHkdz0jp-aFHjI7u-DTgHNzTy5tww8UBk65gh-r5qxDm4x-gK4vEJqs07hjWXHB0Ilg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM CHI TIẾT ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có
    has_set_co = any(isinstance(b, dict) and b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks)
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (Khắt khe hơn)
    has_repeat = any(isinstance(b, dict) and b.get('opcode') == 'control_repeat_until' for b in all_blocks)
    has_not_in_loop = 'operator_not' in code_str and 'control_repeat_until' in code_str
    if has_repeat and has_not_in_loop: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp hoặc thiếu điều kiện 'Not' (0đ)")

    # 3 & 4. Nhập liệu
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu đầu vào 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh nhập dữ liệu 1 (0đ)")
    
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu đầu vào 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu 2 (0đ)")

    # 5. Phép chia
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức tính toán (Phép chia) (1.0đ)")
    else: report.append("❌ 5. Thiếu phép tính toán chia (0đ)")

    # 6. Khối If-Else
    if 'control_if_else' in code_str: total_score += 0.5; report.append("✅ 6. Có khối lệnh If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu khối điều kiện If-Else (0đ)")

    # 7. LOGIC NGƯỠNG (Khắt khe: Phải đủ cả 2 mốc và có khối logic lồng nhau)
    if "Đề 1" in de_thi: targets = ["30", "40"]
    else: targets = ["0.5", "1"]
    
    # Kiểm tra xem có đồng thời cả 2 số và có các toán tử so sánh/logic không
    has_all_targets = all(t in code_str for t in targets)
    logic_count = code_str.count('operator_lt') + code_str.count('operator_gt') + code_str.count('operator_not')
    
    if has_all_targets and logic_count >= 2:
        total_score += 0.5
        report.append(f"✅ 7. Đúng logic ngưỡng so sánh {targets} (0.5đ)")
    else:
        report.append(f"❌ 7. Sai logic ngưỡng: Thiếu mốc so sánh hoặc thiếu khối logic kết hợp (0đ)")

    # 8 & 9. Thông báo
    t1 = "binh thuong"
    t2 = "dieu chinh"
    if t1 in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo kết quả 1 đúng (0.5đ)")
    else: report.append("❌ 8. Sai thông báo kết quả 1 (0đ)")
    
    if t2 in full_txt or "hieu bai" in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo kết quả 2 đúng (0.5đ)")
    else: report.append("❌ 9. Sai thông báo kết quả 2 (0đ)")

    # 10. Tiếp tục
    if len(asks) >= 3 or "tiep tuc" in full_txt: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục để lặp (0.5đ)")
    else: report.append("❌ 10. Thiếu xử lý hỏi Tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN CHÍNH ---
st.title("🏫 Hệ thống Chấm thi Scratch")
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        ten_hs = st.text_input("👤 Họ và tên học sinh:")
        lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
    with col2:
        de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("📂 Tải file .sb3", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")

            st.markdown(f"<div class='result-card'><h2 style='text-align:center;color:#2e7d32;'>KẾT QUẢ: {score} / 6.0</h2><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)

            try:
                payload = {"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}
                requests.post(WEBHOOK_URL, json=payload, timeout=10)
                st.success("🎉 Đã lưu điểm vào Google Sheets thành công!")
            except:
                st.warning("⚠️ Lỗi lưu điểm, hãy tải phiếu điểm báo GV.")

            for d in details: st.write(d)
            if score == 6.0: st.balloons()
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nDe: {de_thi}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("Lỗi file .sb3!")
    else: st.warning("Vui lòng điền đủ thông tin!")

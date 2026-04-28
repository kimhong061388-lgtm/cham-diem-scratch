import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import io
import requests

# --- CHUẨN HÓA ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# LINK WEBHOOK CỦA BẠN (GIỮ NGUYÊN)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyLHkdz0jp-aFHjI7u-DTgHNzTy5tww8UBk65gh-r5qxDm4x-gK4vEJqs07hjWXHB0Ilg/exec"

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)
    full_txt = chuan_hoa(code_str)

    has_set_co = any(isinstance(b, dict) and b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks)
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu lệnh gán biến (0đ)")

    if 'control_repeat_until' in code_str and 'operator_not' in code_str: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if all(t in code_str for t in targets): total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
    
    if "binh thuong" in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    if "dieu chinh" in full_txt or "hieu bai" in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")

    return round(total_score, 1), report

st.set_page_config(page_title="Thi Scratch", page_icon="🏆")
st.title("🏆 Hệ thống Chấm điểm Scratch V2")

ten_hs = st.text_input("Họ và tên học sinh:").strip()
lop_hs = st.selectbox("Chọn lớp của em:", DANH_SACH_LOP)
de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file bài làm của em (.sb3)", type="sb3")

if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            st.divider()
            st.success(f"### CHÚC MỪNG: {ten_hs.upper()}")
            st.info(f"### LỚP: {lop_hs} --- ĐIỂM: {score} / 6.0")

            # GỬI ĐIỂM
            try:
                payload = {"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}
                res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
                if "Success" in res.text:
                    st.success("✅ Hệ thống đã ghi nhận điểm vào danh sách!")
                else:
                    st.warning("📌 Đã chấm xong! Nếu không thấy điểm trong bảng, em hãy chụp màn hình báo thầy/cô nhé.")
            except:
                st.warning("⚠️ Mạng yếu, em hãy tải phiếu điểm bên dưới để nộp.")

            for d in details: st.write(d)
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("Lỗi file .sb3!")

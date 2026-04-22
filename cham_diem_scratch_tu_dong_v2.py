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
WEBHOOK_URL = "https://google.com"

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM (GIỮ NGUYÊN LOGIC KHẮT KHE) ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Gán biến Trả lời = Có
    has_set_co = False
    for b in all_blocks:
        if isinstance(b, dict) and b.get('opcode') == 'data_setvariableto':
            val_input = str(b.get('inputs', {}).get('VALUE', ''))
            if 'co' in chuan_hoa(val_input):
                has_set_co = True
                break
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (0.5đ + 0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")

    # 5. Phép chia (1.0đ)
    if 'operator_divide' in code_str:
        total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    else: report.append("❌ 5. Thiếu phép chia (0đ)")

    # 6 & 7. If-Else & Logic
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
    
    # 8 & 9. Thông báo
    t1 = "binh thuong"
    t2 = "dieu chinh"
    if t1 in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    if t2 in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")

    # 10 & 11. Tiếp tục & Kết thúc
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch", page_icon="🏆", layout="centered")
st.title("🏆 Hệ thống Chấm điểm Scratch V2")

ten_hs = st.text_input("Họ và tên học sinh:").strip()
lop_hs = st.selectbox("Chọn lớp của em:", DANH_SACH_LOP)
de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file bài làm của em (.sb3)", type="sb3")

if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            # 1. Đọc file
            file_bytes = file_sb3.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            
            # 2. Chấm điểm
            score, details = grade_by_logic_barem(data, de_thi)
            
            # 3. Hiển thị thông báo đẹp (Giống V1)
            st.divider()
            col_score, col_info = st.columns([1, 2])
            with col_score:
                st.metric(label="TỔNG ĐIỂM", value=f"{score} / 6.0")
            with col_info:
                st.write(f"**Học sinh:** {ten_hs.upper()}")
                st.write(f"**Lớp:** {lop_hs}")
            
            # 4. Lưu điểm tự động qua Webhook
            try:
                payload = {
                    "Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                    "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score
                }
                requests.post(WEBHOOK_URL, json=payload, timeout=5)
                st.success("✅ Hệ thống đã ghi nhận điểm của em!")
            except:
                st.warning("⚠️ Mạng yếu, em hãy báo giáo viên ghi lại điểm nhé.")

            # 5. Chi tiết chấm điểm
            with st.expander("Xem chi tiết bảng chấm bài", expanded=True):
                for d in details:
                    st.write(d)
            
            if score == 6.0: st.balloons()
            
            # 6. Nút tải minh chứng
            minh_chung = f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nThoi gian: {datetime.now()}"
            st.download_button("📥 TẢI PHIẾU ĐIỂM", minh_chung, file_name=f"Diem_{ten_hs}.txt")
            
        except:
            st.error("Lỗi file: Không đọc được bài làm. Em hãy kiểm tra lại file .sb3 nhé!")
    else:
        st.warning("⚠️ Vui lòng nhập tên và chọn file bài làm!")

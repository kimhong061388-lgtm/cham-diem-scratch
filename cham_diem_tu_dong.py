import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import io
import requests # Thư viện để gửi dữ liệu lên web

# --- CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- CẤU HÌNH ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
# THAY THẾ LINK DƯỚI ĐÂY BẰNG LINK FORM CỦA BẠN (Thay 'viewform' bằng 'formResponse')
FORM_URL = "https://google.com"

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Gán biến Trả lời = Có
    has_set_co = any(b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks if isinstance(b, dict))
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu lệnh gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (Sửa logic quét chặt hơn)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (Hỏi)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu nhập liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu nhập liệu 2 (0đ)")

    # 5. Phép chia (/)
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    else: report.append("❌ 5. Thiếu phép chia (0đ)")

    # 6 & 7. If-Else & Logic
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if 'operator_not' in code_str and all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
        else: report.append(f"❌ 7. Sai logic ngưỡng {targets} (0đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)"); report.append("❌ 7. Không có If (0đ)")

    # 8 & 9. Thông báo
    if "binh thuong" in chuan_hoa(code_str) or "tap trung" in chuan_hoa(code_str): 
        total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if "dieu chinh" in chuan_hoa(code_str) or "hieu bai" in chuan_hoa(code_str): 
        total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch", page_icon="🏫")
st.title("🏆 Hệ thống Chấm điểm Tự động")

ten_hs = st.text_input("Họ và tên học sinh:")
lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file .sb3", type="sb3")

if st.button("NỘP BÀI"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            st.metric("TỔNG ĐIỂM", f"{score} / 6.0")
            for d in details: st.write(d)
            
            # --- GỬI ĐIỂM LÊN GOOGLE SHEETS QUA FORM ---
            # Thay entry ID tương ứng với Form của bạn
            payload = {
                "entry.123456": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                "entry.234567": ten_hs,
                "entry.345678": lop_hs,
                "entry.456789": de_thi,
                "entry.567890": score
            }
            requests.post(FORM_URL, data=payload)
            st.success("Đã ghi nhận điểm thành công!")
            if score == 6.0: st.balloons()
        except: st.error("Lỗi file Scratch!")

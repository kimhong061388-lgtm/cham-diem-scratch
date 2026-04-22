import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import io

# --- CHUẨN HÓA ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM LOGIC KHẮT KHE ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Gán biến Trả lời = Có (0.5đ)
    has_set_co = any(isinstance(b, dict) and b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks)
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu lệnh gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    has_repeat_not = any(isinstance(b, dict) and b.get('opcode') == 'control_repeat_until' and ('operator_not' in str(b) or 'operator_not' in code_str) for b in all_blocks)
    if has_repeat_not: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (0.5đ + 0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu nhập liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu nhập liệu 2 (0đ)")

    # 5. Phép chia (1.0đ)
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
    full_text_chuan = chuan_hoa(code_str)
    if "binh thuong" in full_text_chuan: total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if "dieu chinh" in full_text_chuan: total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục (0.5đ)
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")

    # 11. Kết thúc (0.5đ)
    if "ket thuc" in full_text_chuan: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống chấm điểm Scratch", page_icon="🏫")
st.title("🏆 Hệ thống Chấm điểm Scratch")

ten_hs = st.text_input("Họ và tên học sinh:")
lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file bài làm của em (.sb3)", type="sb3")

if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                project_json = archive.read('project.json')
                data = json.loads(project_json)
            
            score, details = grade_by_logic_barem(data, de_thi)
            
            st.divider()
            # HIỂN THỊ KẾT QUẢ CỰC LỚN ĐỂ GIÁO VIÊN DỄ NHÌN
            st.success(f"### CHÚC MỪNG: {ten_hs.upper()}")
            st.info(f"### LỚP: {lop_hs} --- ĐIỂM: {score} / 6.0")
            
            for d in details: st.write(d)
            if score == 6.0: st.balloons()
            
            # NÚT TẢI PHIẾU ĐIỂM DỰ PHÒNG
            minh_chung = f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDe: {de_thi}\nDiem: {score}\nThoi gian: {datetime.now()}"
            st.download_button("📥 TẢI PHIẾU ĐIỂM (Minh chứng)", minh_chung, file_name=f"Diem_{ten_hs}.txt")

        except Exception as e:
            st.error(f"Lỗi file: {e}")
    else:
        st.warning("⚠️ Vui lòng điền đủ thông tin!")

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import io

# --- CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- CẤU HÌNH ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2024"

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()

    # 1. Gán biến Trả lời = Có (0.5đ)
    if 'co' in code_str and 'data_setvariableto' in code_str: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu lệnh gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until (0.5đ) - Sửa lỗi: Quét rộng hơn khối Not và Answer
    if 'control_repeat_until' in code_str: total_score += 0.5; report.append("✅ 2. Có vòng lặp Repeat Until (0.5đ)")
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

    # 6 & 7. If-Else và Logic (0.5đ + 0.5đ) - Sửa lỗi: Chấp nhận cả số nguyên và số thập phân
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        # Quét thoáng hơn cho logic so sánh
        if all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
        else: report.append(f"❌ 7. Sai logic ngưỡng {targets} (0đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)"); report.append("❌ 7. Không có If (0đ)")

    # 8 & 9. Thông báo (0.5đ + 0.5đ)
    txt1 = "binh thuong" if "Đề 1" in de_thi else "tap trung"
    txt2 = "dieu chinh" if "Đề 1" in de_thi else "hieu bai tot hon"
    if txt1 in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if txt2 in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục (0.5đ) - Sửa lỗi: Kiểm tra lệnh Ask thứ 3
    if len(asks) >= 3 or 'tiep tuc' in chuan_hoa(code_str): 
        total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")

    # 11. Kết thúc (0.5đ)
    if "ket thuc" in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Chấm thi Scratch", page_icon="🏫")
conn = st.connection("gsheets", type=GSheetsConnection)

tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm"])

with tab1:
    ten_hs = st.text_input("Họ và tên học sinh:")
    lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
    de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("Tải file bài làm của em", type="sb3")

    if st.button("NỘP BÀI"):
        if ten_hs and file_sb3:
            try:
                file_bytes = file_sb3.read()
                with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                    data = json.loads(archive.read('project.json'))
                score, details = grade_by_logic_barem(data, de_thi)
                st.metric("TỔNG ĐIỂM", f"{score} / 6.0")
                for d in details: st.write(d)
                
                # --- PHẦN GHI ĐIỂM ĐÃ FIX LỖI ---
                try:
                    df = conn.read(ttl=0)
                    new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success("Hệ thống đã lưu điểm thành công!")
                except Exception as e:
                    st.error(f"Lỗi lưu điểm: Vui lòng kiểm tra lại quyền 'Editor' của file Google Sheets. ({e})")
                
                if score == 6.0: st.balloons()
            except: st.error("Lỗi file Scratch!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        df_sheet = conn.read(ttl=0)
        st.dataframe(df_sheet, use_container_width=True)

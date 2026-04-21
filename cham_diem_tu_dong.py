import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode

# --- CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- CẤU HÌNH ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2024"

# --- HÀM CHẤM ĐIỂM CHI TIẾT THEO BAREM ---
def grade_by_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Khối Lá cờ xanh (0.5đ)
    if 'event_whenflagclicked' in code_str:
        total_score += 0.5
        report.append("✅ 1. Có sự kiện Khi bấm vào Lá cờ xanh (0.5đ)")
    else: report.append("❌ 1. Thiếu sự kiện Khi bấm vào Lá cờ xanh (0đ)")

    # 2. Khởi tạo biến lặp (ví dụ: Trả lời = Có) (0.5đ)
    if 'data_setvariableto' in code_str:
        total_score += 0.5
        report.append("✅ 2. Có thiết lập giá trị biến ban đầu (0.5đ)")
    else: report.append("❌ 2. Thiếu khởi tạo giá trị biến (0đ)")

    # 3. Vòng lặp Repeat Until (0.5đ)
    if 'control_repeat_until' in code_str:
        total_score += 0.5
        report.append("✅ 3. Có sử dụng vòng lặp Repeat Until (0.5đ)")
    else: report.append("❌ 3. Thiếu vòng lặp Repeat Until (0đ)")

    # 4. Nhập liệu: Hỏi & Đặt biến lần 1 (0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    sets = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'data_setvariableto']
    if len(asks) >= 1 and len(sets) >= 1:
        total_score += 0.5
        report.append("✅ 4. Có lệnh Hỏi và Đặt biến thứ nhất (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu thứ nhất (0đ)")

    # 5. Nhập liệu: Hỏi & Đặt biến lần 2 (0.5đ)
    if len(asks) >= 2 and len(sets) >= 2:
        total_score += 0.5
        report.append("✅ 5. Có lệnh Hỏi và Đặt biến thứ hai (0.5đ)")
    else: report.append("❌ 5. Thiếu lệnh nhập dữ liệu thứ hai (0đ)")

    # 6. Tính toán công thức (Chia /) (1.0đ)
    if 'operator_divide' in code_str:
        total_score += 1.0
        report.append("✅ 6. Có phép toán tính chỉ số đúng công thức (1.0đ)")
    else: report.append("❌ 6. Thiếu khối lệnh tính toán công thức (0đ)")

    # 7. Khối If-Else và Logic điều kiện (1.0đ)
    # Đề 1: 30-40 | Đề 2: 0.5-1.0
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str and all(t in code_str for t in targets):
        total_score += 1.0
        report.append(f"✅ 7. Có khối If-Else và ngưỡng so sánh {targets} (1.0đ)")
    else: report.append(f"❌ 7. Sai hoặc thiếu cấu trúc điều kiện so sánh (0đ)")

    # 8. Thông báo lời khuyên 1 (0.5đ)
    txt1 = "binh thuong" if "Đề 1" in de_thi else "tap trung"
    if txt1 in chuan_hoa(code_str):
        total_score += 0.5
        report.append(f"✅ 8. Thông báo đúng trường hợp Bình thường (0.5đ)")
    else: report.append(f"❌ 8. Thiếu/Sai thông báo Bình thường (0đ)")

    # 9. Thông báo lời khuyên 2 (0.5đ)
    txt2 = "dieu chinh" if "Đề 1" in de_thi else "hieu bai tot hon"
    if txt2 in chuan_hoa(code_str):
        total_score += 0.5
        report.append(f"✅ 9. Thông báo đúng trường hợp Cần điều chỉnh (0.5đ)")
    else: report.append(f"❌ 9. Thiếu/Sai thông báo Cần điều chỉnh (0đ)")

    # 10. Hỏi tiếp tục (0.5đ)
    if len(asks) >= 3:
        total_score += 0.5
        report.append("✅ 10. Có lệnh Hỏi để duy trì vòng lặp (0.5đ)")
    else: report.append("❌ 10. Thiếu lệnh Hỏi tiếp tục (0đ)")

    # 11. Thông báo Kết thúc (0.5đ)
    if "ket thuc" in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 11. Có thông báo Kết thúc sau vòng lặp (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Chấm thi Scratch Barem", page_icon="📝")
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🏆 Hệ thống Chấm thi Scratch - Barem Chuẩn")
tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm giáo viên"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        ten_hs = st.text_input("Họ và tên học sinh:")
        lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
    with c2:
        de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("Tải file .sb3 của em", type="sb3")

    if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
        if ten_hs and file_sb3:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    data = json.loads(archive.read('project.json'))
                final_score, details = grade_by_barem(data, de_thi)
                st.divider()
                st.metric("TỔNG ĐIỂM", f"{final_score} / 6.0")
                for d in details: st.write(d)
                # Ghi Google Sheets
                try:
                    new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                                             "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": final_score}])
                    df = conn.read(ttl=0)
                    pd.concat([df, new_row], ignore_index=True).pipe(conn.update)
                    st.success("Đã ghi nhận điểm thành công!")
                except: st.info("Lưu điểm đang bận, hãy báo giáo viên.")
                if final_score == 6.0: st.balloons()
            except: st.error("Lỗi file Scratch!")
        else: st.warning("Vui lòng điền đủ tên và tải file!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        df_sheet = conn.read(ttl=0)
        st.dataframe(df_sheet, use_container_width=True)

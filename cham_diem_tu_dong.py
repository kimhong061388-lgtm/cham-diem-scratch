import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode

# --- HÀM CHUẨN HÓA (XÓA DẤU, CHỮ THƯỜNG) ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- CẤU HÌNH HỆ THỐNG ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2024"

# --- HÀM CHẤM LOGIC CHUNG CHO CẢ 2 ĐỀ ---
def grade_logic(project_data, de_thi):
    score = 0
    details = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Kiểm tra nhập liệu (Hỏi ít nhất 2 câu)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 2:
        score += 1
        details.append("✅ 1. Nhập liệu: Có đủ lệnh hỏi dữ liệu đầu vào.")
    else: details.append("❌ 1. Nhập liệu: Thiếu lệnh hỏi (Ask).")

    # 2. Kiểm tra tính toán (Phép chia /)
    if any(b.get('opcode') == 'operator_divide' for b in all_blocks if isinstance(b, dict)):
        score += 1
        details.append("✅ 2. Tính toán: Có sử dụng phép chia để tính toán chỉ số.")
    else: details.append("❌ 2. Tính toán: Thiếu khối lệnh phép chia (/).")

    # 3. Kiểm tra vòng lặp (Repeat Until)
    if any(b.get('opcode') == 'control_repeat_until' for b in all_blocks if isinstance(b, dict)):
        score += 1
        details.append("✅ 3. Vòng lặp: Có sử dụng khối lệnh lặp lại.")
    else: details.append("❌ 3. Vòng lặp: Thiếu cấu trúc lặp (Repeat until).")

    # 4. Kiểm tra cấu trúc rẽ nhánh (If-Else)
    if any(b.get('opcode') == 'control_if_else' for b in all_blocks if isinstance(b, dict)):
        score += 1
        details.append("✅ 4. Rẽ nhánh: Có cấu trúc Nếu... thì... Nếu không thì...")
    else: details.append("❌ 4. Rẽ nhánh: Thiếu khối điều kiện If-Else.")

    # --- CHẤM RIÊNG THEO TỪNG ĐỀ ---
    if "Đề 1" in de_thi:
        # 5. Logic Đề 1 (30 và 40)
        if '30' in code_str and '40' in code_str:
            score += 1
            details.append("✅ 5. Logic: Có thiết lập ngưỡng so sánh 30 và 40.")
        else: details.append("❌ 5. Logic: Thiếu ngưỡng 30 hoặc 40.")
        # 6. Thông báo Đề 1
        txt1 = "chi so cap nuoc binh thuong, ban da cung cap du nuoc"
        txt2 = "ban can dieu chinh lai luong nuoc uong hang ngay"
        if chuan_hoa(txt1) in chuan_hoa(code_str) and chuan_hoa(txt2) in chuan_hoa(code_str):
            score += 1
            details.append("✅ 6. Thông báo: Lời khuyên khớp với yêu cầu Đề 1.")
        else: details.append("❌ 6. Thông báo: Nội dung lời khuyên chưa chính xác.")

    else: # Chấm Đề 2
        # 5. Logic Đề 2 (0.5 và 1.0)
        if '0.5' in code_str and '1' in code_str:
            score += 1
            details.append("✅ 5. Logic: Có thiết lập ngưỡng vận tốc 0.5 và 1.0.")
        else: details.append("❌ 5. Logic: Thiếu ngưỡng 0.5 hoặc 1.0.")
        # 6. Thông báo Đề 2
        txt1 = "toc do doc binh thuong, ban dang rat tap trung"
        txt2 = "can dieu chinh lai toc do doc de hieu bai tot hon"
        if chuan_hoa(txt1) in chuan_hoa(code_str) and chuan_hoa(txt2) in chuan_hoa(code_str):
            score += 1
            details.append("✅ 6. Thông báo: Lời khuyên khớp với yêu cầu Đề 2.")
        else: details.append("❌ 6. Thông báo: Nội dung lời khuyên chưa chính xác.")

    return score, details

# --- GIAO DIỆN WEB ---
st.set_page_config(page_title="Chấm thi Scratch", page_icon="🏫")
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🏆 Hệ thống Chấm điểm Scratch Tự động")
tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm giáo viên"])

with tab1:
    ten_hs = st.text_input("Họ và tên học sinh:")
    lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
    de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Lượng nước uống", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("Tải file .sb3 của em", type="sb3")

    if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
        if ten_hs and file_sb3:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    data = json.loads(archive.read('project.json'))
                
                final_score, report = grade_logic(data, de_thi)
                
                st.divider()
                st.metric("TỔNG ĐIỂM", f"{final_score} / 6")
                for line in report: st.write(line)

                # Ghi Google Sheets
                new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                                         "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": final_score}])
                df = conn.read(ttl=0)
                pd.concat([df, new_row], ignore_index=True).pipe(conn.update)
                st.success("Đã lưu điểm thành công!")
                if final_score == 6: st.balloons()
            except: st.error("Lỗi đọc file bài làm!")
        else: st.warning("Vui lòng điền đủ thông tin!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        st.subheader("Bảng điểm tổng hợp")
        data_sheet = conn.read(ttl=0)
        st.dataframe(data_sheet, use_container_width=True)
        csv = data_sheet.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Tải file Excel", csv, "diem_thi.csv", "text/csv")

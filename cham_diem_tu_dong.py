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
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Khởi tạo biến Trả lời = Có (0.5đ)
    if 'data_setvariableto' in code_str and 'co' in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 1. Khởi tạo biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu khởi tạo biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Điều kiện Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5
        report.append("✅ 2. Vòng lặp Repeat Until với điều kiện 'not' đúng (0.5đ)")
    else: report.append("❌ 2. Thiếu vòng lặp hoặc điều kiện lặp chưa đúng (0đ)")

    # 3. Nhập dữ liệu 1 (Số trang/Cân nặng) (0.5đ)
    # 4. Nhập dữ liệu 2 (Số phút/Lượng nước) (0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1:
        total_score += 0.5
        report.append("✅ 3. Nhập được dữ liệu đầu vào thứ nhất (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh nhập dữ liệu 1 (0đ)")
    
    if len(asks) >= 2:
        total_score += 0.5
        report.append("✅ 4. Nhập được dữ liệu đầu vào thứ hai (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu 2 (0đ)")

    # 5. Đúng công thức chia (V=S/T hoặc I=L/W) (1.0đ)
    if 'operator_divide' in code_str:
        total_score += 1.0
        report.append("✅ 5. Đúng công thức tính toán chỉ số (Phép chia) (1.0đ)")
    else: report.append("❌ 5. Sai hoặc thiếu công thức tính toán (0đ)")

    # 6. Sử dụng khối If-Else (Nếu thì nếu không thì) (0.5đ)
    if 'control_if_else' in code_str:
        total_score += 0.5
        report.append("✅ 6. Có sử dụng khối điều kiện Nếu... thì... Nếu không thì (0.5đ)")
        
        # 7. Điều kiện Logic nâng cao (Not v < 0.5 và Not v > 1.0) (0.5đ)
        # Quét sự xuất hiện đồng thời của nhiều khối 'not' và các giá trị mốc
        targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
        if 'operator_not' in code_str and all(t in code_str for t in targets):
            total_score += 0.5
            report.append(f"✅ 7. Đúng điều kiện logic so sánh ngưỡng {targets} (0.5đ)")
        else: report.append("❌ 7. Sai hoặc thiếu logic so sánh trong khối If (0đ)")
    else:
        report.append("❌ 6. Thiếu khối điều kiện If-Else (0đ)")
        report.append("❌ 7. Không thể chấm logic điều kiện (0đ)")

    # 8. Thông báo kết quả khi If đúng (0.5đ)
    txt1 = "binh thuong" if "Đề 1" in de_thi else "binh thuong"
    if txt1 in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 8. Xuất thông báo 'Bình thường' khi thỏa điều kiện (0.5đ)")
    else: report.append("❌ 8. Thiếu/Sai thông báo khi thỏa điều kiện (0đ)")

    # 9. Thông báo lời khuyên khi If sai (0.5đ)
    txt2 = "dieu chinh" if "Đề 1" in de_thi else "dieu chinh"
    if txt2 in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 9. Xuất thông báo 'Điều chỉnh' khi không thỏa điều kiện (0.5đ)")
    else: report.append("❌ 9. Thiếu/Sai thông báo khi cần điều chỉnh (0đ)")

    # 10. Lệnh hỏi và trả lời tiếp tục (0.5đ)
    if len(asks) >= 3:
        total_score += 0.5
        report.append("✅ 10. Có lệnh hỏi 'Tiếp tục không?' để duy trì vòng lặp (0.5đ)")
    else: report.append("❌ 10. Thiếu xử lý hỏi tiếp tục (0đ)")

    # 11. Thông báo kết thúc (0.5đ)
    if "ket thuc" in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 11. Có thông báo Kết thúc sau khi thoát lặp (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN WEB ---
st.set_page_config(page_title="Chấm thi Scratch Barem Chuẩn", page_icon="🏫")
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🏆 Hệ thống Chấm điểm Scratch Theo Barem")

tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        ten_hs = st.text_input("Họ và tên học sinh:")
        lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
    with col2:
        de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("Tải file .sb3 của em", type="sb3")

    if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
        if ten_hs and file_sb3:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    data = json.loads(archive.read('project.json'))
                final_score, details = grade_by_logic_barem(data, de_thi)
                st.divider()
                st.metric("TỔNG ĐIỂM CỦA EM", f"{final_score} / 6.0")
                for d in details: st.write(d)
                # Ghi Google Sheets
                try:
                    new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                                             "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": final_score}])
                    df = conn.read(ttl=0)
                    pd.concat([df, new_row], ignore_index=True).pipe(conn.update)
                    st.success("Đã ghi nhận điểm thành công!")
                except: st.info("Lưu điểm đang bận, báo giáo viên em nhé.")
                if final_score == 6.0: st.balloons()
            except: st.error("Lỗi file Scratch!")
        else: st.warning("Vui lòng điền đủ thông tin!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        df_sheet = conn.read(ttl=0)
        st.dataframe(df_sheet, use_container_width=True)

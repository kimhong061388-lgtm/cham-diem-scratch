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

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    
    code_str = str(all_blocks)

    # --- 1. KIỂM TRA LỆNH GÁN BIẾN TRẢ LỜI = CÓ (0.5đ) ---
    # Phải tìm đúng khối set variable và giá trị đi kèm là 'co'
    has_set_co = False
    for b in all_blocks:
        if isinstance(b, dict) and b.get('opcode') == 'data_setvariableto':
            # Kiểm tra giá trị trong ô input của lệnh set
            value = str(b.get('inputs', {}).get('VALUE', ''))
            if 'co' in chuan_hoa(value):
                has_set_co = True
                break
    
    if has_set_co:
        total_score += 0.5
        report.append("✅ 1. Có lệnh gán biến Trả lời = Có (0.5đ)")
    else:
        report.append("❌ 1. Thiếu lệnh gán biến Trả lời = Có (0đ)")

    # --- 2. KIỂM TRA VÒNG LẶP REPEAT UNTIL + NOT (0.5đ) ---
    # Kiểm tra xem khối repeat_until có chứa toán tử NOT bên trong không
    has_repeat_not = False
    for b in all_blocks:
        if isinstance(b, dict) and b.get('opcode') == 'control_repeat_until':
            condition_id = b.get('inputs', {}).get('CONDITION', [0, None])[1]
            # Tìm khối lệnh nối với ô điều kiện của Repeat Until
            if condition_id:
                cond_block = next((blk for blk in all_blocks if isinstance(blk, dict) and blk.get('id') == condition_id), None)
                # Nếu không tìm thấy bằng ID, ta quét trong chuỗi cấu trúc của khối repeat đó
                if cond_block and cond_block.get('opcode') == 'operator_not':
                    has_repeat_not = True
                elif 'operator_not' in str(b): # Cách quét dự phòng
                    has_repeat_not = True
                    
    if has_repeat_not:
        total_score += 0.5
        report.append("✅ 2. Vòng lặp Repeat Until với điều kiện 'not' (0.5đ)")
    else:
        report.append("❌ 2. Sai cấu trúc vòng lặp hoặc thiếu điều kiện 'not' (0đ)")

    # --- CÁC MỤC CÒN LẠI GIỮ NGUYÊN NHƯNG TỐI ƯU QUÉT CHẶT CHẼ ---
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    
    # 3 & 4. Nhập liệu
    if len(asks) >= 1:
        total_score += 0.5
        report.append("✅ 3. Nhập dữ liệu đầu vào 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh nhập dữ liệu 1 (0đ)")
    
    if len(asks) >= 2:
        total_score += 0.5
        report.append("✅ 4. Nhập dữ liệu đầu vào 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu 2 (0đ)")

    # 5. Phép chia (1.0đ)
    if 'operator_divide' in code_str:
        total_score += 1.0
        report.append("✅ 5. Đúng công thức tính toán (Phép chia) (1.0đ)")
    else: report.append("❌ 5. Thiếu phép tính toán chia (0đ)")

    # 6 & 7. If-Else và Logic NOT lồng nhau
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5
        report.append("✅ 6. Có khối điều kiện Nếu... thì... Nếu không thì (0.5đ)")
        
        # Kiểm tra logic NOT lồng trong IF (như hình đề bài)
        if 'operator_not' in code_str and all(t in code_str for t in targets):
            total_score += 0.5
            report.append(f"✅ 7. Đúng logic so sánh ngưỡng {targets} (0.5đ)")
        else: report.append("❌ 7. Sai logic so sánh bên trong If (0đ)")
    else:
        report.append("❌ 6. Thiếu khối If-Else (0đ)")
        report.append("❌ 7. Không có khối If nên không chấm được logic (0đ)")

    # 8 & 9. Thông báo kết quả
    txt1 = "binh thuong"
    txt2 = "dieu chinh"
    if txt1 in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 8. Thông báo 'Bình thường' đúng (0.5đ)")
    else: report.append("❌ 8. Thiếu thông báo 'Bình thường' (0đ)")

    if txt2 in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 9. Thông báo 'Điều chỉnh' đúng (0.5đ)")
    else: report.append("❌ 9. Thiếu thông báo 'Điều chỉnh' (0đ)")

    # 10. Tiếp tục
    if len(asks) >= 3:
        total_score += 0.5
        report.append("✅ 10. Có lệnh hỏi 'Tiếp tục không?' (0.5đ)")
    else: report.append("❌ 10. Thiếu xử lý hỏi tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in chuan_hoa(code_str):
        total_score += 0.5
        report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN GIỮ NGUYÊN ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏫")
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
                st.metric("TỔNG ĐIỂM", f"{final_score} / 6.0")
                for d in details: st.write(d)
                try:
                    new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                                             "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": final_score}])
                    df = conn.read(ttl=0)
                    pd.concat([df, new_row], ignore_index=True).pipe(conn.update)
                    st.success("Đã ghi nhận điểm thành công!")
                except: st.info("Lưu điểm đang bận, báo giáo viên em nhé.")
                if final_score == 6.0: st.balloons()
            except: st.error("Lỗi file Scratch!")
        else: st.warning("Vui lòng điền đủ tên và tải file!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        df_sheet = conn.read(ttl=0)
        st.dataframe(df_sheet, use_container_width=True)

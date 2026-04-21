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
    # Lấy blocks từ tất cả targets
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks)

    # 1. Gán biến Trả lời = Có
    has_set_co = any('co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'data_setvariableto')
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu lệnh gán biến Trả lời = Có (0đ)")

    # 2. Repeat Until + Not
    if 'control_repeat_until' in code_str and 'operator_not' in code_str: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu nhập liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu nhập liệu 2 (0đ)")

    # 5. Phép chia
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    else: report.append("❌ 5. Thiếu phép chia (0đ)")

    # 6 & 7. If-Else và Logic
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if 'operator_not' in code_str and all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic so sánh {targets} (0.5đ)")
        else: report.append(f"❌ 7. Sai logic ngưỡng {targets} (0đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)"); report.append("❌ 7. Không có If (0đ)")

    # 8 & 9. Thông báo
    txt1 = "binh thuong"
    txt2 = "dieu chinh"
    if txt1 in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if txt2 in chuan_hoa(code_str): total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục & 11. Kết thúc
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")
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
        if not ten_hs or not file_sb3:
            st.warning("Vui lòng điền đủ tên và tải file!")
        else:
            try:
                # Cách đọc file an toàn hơn
                file_bytes = file_sb3.read()
                with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                    project_json = archive.read('project.json')
                    data = json.loads(project_json)
                
                score, details = grade_by_logic_barem(data, de_thi)
                
                st.divider()
                st.metric("TỔNG ĐIỂM", f"{score} / 6.0")
                for d in details: st.write(d)
                
                # LƯU ĐIỂM
                try:
                    new_row = pd.DataFrame([{
                        "Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                        "Hoc_sinh": ten_hs, 
                        "Lop": lop_hs, 
                        "De": de_thi, 
                        "Diem": score
                    }])
                    # Đọc dữ liệu hiện tại, nếu lỗi thì tạo mới
                    try:
                        existing = conn.read(ttl=0)
                        updated = pd.concat([existing, new_row], ignore_index=True)
                    except:
                        updated = new_row
                    
                    conn.update(data=updated)
                    st.success("Đã ghi nhận điểm vào Google Sheets!")
                except Exception as e_sheet:
                    st.error(f"Lỗi ghi điểm: {e_sheet}")
                
                if score == 6.0: st.balloons()
            except Exception as e_file:
                st.error(f"Lỗi file: Hệ thống không thể mở file này. Hãy đổi tên file thành không dấu và thử lại. (Chi tiết: {e_file})")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        try:
            df_sheet = conn.read(ttl=0)
            if df_sheet is not None and not df_sheet.empty:
                st.dataframe(df_sheet, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu học sinh nộp bài.")
        except Exception as e:
            st.error(f"Không thể kết nối bảng điểm: {e}")

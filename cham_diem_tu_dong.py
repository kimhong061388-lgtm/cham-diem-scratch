import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode

# --- CẤU HÌNH HỆ THỐNG ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2026"

# --- CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- BỘ TEST ---
DE_1_WATER = [{"out": "chi so cap nuoc binh thuong, ban da cung cap du nuoc"}, {"out": "ban can dieu chinh lai luong nuoc uong hang ngay"}]
DE_2_READING = [{"out": "toc do doc binh thuong, ban dang rat tap trung"}, {"out": "can dieu chinh lai toc do doc de hieu bai tot hon"}]

# --- KẾT NỐI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống thi Scratch theo lớp", page_icon="🏫")
st.title("🏫 Quản lý Thi Scratch - 10 Lớp")

tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm giáo viên"])

with tab1:
    st.subheader("Thông tin bài thi")
    c1, c2 = st.columns(2)
    with c1:
        ten_hs = st.text_input("Họ và tên học sinh:")
        lop_hs = st.selectbox("Chọn lớp của em:", DANH_SACH_LOP)
    with c2:
        de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Lượng nước uống", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("Tải file bài làm (.sb3)", type="sb3")

    if st.button("NỘP BÀI VÀ CHẤM ĐIỂM"):
        if not ten_hs or not file_sb3:
            st.error("Vui lòng nhập đầy đủ tên và tải file!")
        else:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    data = json.loads(archive.read('project.json'))
                
                # Logic chấm điểm
                all_blocks = []
                for t in data.get('targets', []):
                    all_blocks.extend(t.get('blocks', {}).values())
                student_msgs = [chuan_hoa(b.get('inputs', {}).get('MESSAGE', '')) for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'looks_say']
                
                tests = DE_1_WATER if "Đề 1" in de_thi else DE_2_READING
                score = 0
                for t in tests:
                    if any(chuan_hoa(t["out"]) in m for m in student_msgs):
                        score += 1
                
                st.divider()
                st.success(f"Chúc mừng {ten_hs} lớp {lop_hs} đã hoàn thành bài thi!")
                st.metric("SỐ ĐIỂM ĐẠT ĐƯỢC", f"{score} / 6")

                # LƯU VÀO GOOGLE SHEETS
                new_row = pd.DataFrame([{
                    "Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                    "Hoc_sinh": ten_hs,
                    "Lop": lop_hs,
                    "De": de_thi,
                    "Diem": score
                }])
                
                existing_data = conn.read(ttl=0)
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.info("Kết quả đã được lưu tự động vào bảng điểm của lớp.")

            except Exception as e:
                st.error("Lỗi: File bài làm không hợp lệ.")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        st.subheader("Dữ liệu điểm thi hệ thống")
        data_sheet = conn.read(ttl=0)
        
        # Thêm bộ lọc lớp cho giáo viên dễ nhìn
        lop_can_xem = st.multiselect("Lọc theo lớp:", DANH_SACH_LOP, default=DANH_SACH_LOP)
        df_filtered = data_sheet[data_sheet['Lop'].isin(lop_can_xem)]
        
        st.dataframe(df_filtered, use_container_width=True)
        
        # Tải file theo lớp đã lọc
        csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(f"Tải Excel lớp đã chọn", csv, f"diem_scratch_{datetime.now().strftime('%d_%m')}.csv", "text/csv")
    elif pwd != "":
        st.error("Sai mật khẩu!")

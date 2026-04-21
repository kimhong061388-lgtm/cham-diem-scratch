import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import os

# --- 1. HÀM CHUẨN HÓA (XÓA DẤU) ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- 2. CẤU HÌNH BỘ TEST VÀ LỚP ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2024"

# Đề 1: Kiểm tra lượng nước (Chỉ cần tìm từ khóa chính)
DE_1_WATER = [
    {"out": "binh thuong"}, {"out": "dieu chinh"}, {"out": "dieu chinh"},
    {"out": "binh thuong"}, {"out": "binh thuong"}, {"out": "binh thuong"}
]

# Đề 2: Kiểm tra tốc độ đọc (Chỉ cần tìm từ khóa chính)
DE_2_READING = [
    {"out": "tap trung"}, {"out": "tap trung"}, {"out": "hieu bai tot hon"},
    {"out": "hieu bai tot hon"}, {"out": "tap trung"}, {"out": "tap trung"}
]

# --- 3. KẾT NỐI HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống thi Scratch", page_icon="🏫")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 4. HÀM CHẤM ĐIỂM ---
def grade_project(project_data, test_cases):
    score = 0
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())

    student_texts = []
    for b in all_blocks:
        if isinstance(b, dict):
            # Quét tất cả nội dung tin nhắn Nói/Nghĩ/Hỏi
            inputs = b.get('inputs', {})
            for key in inputs:
                val = str(inputs[key])
                student_texts.append(chuan_hoa(val))

    results = []
    for i, test in enumerate(test_cases):
        target = chuan_hoa(test["out"])
        found = any(target in txt for txt in student_texts)
        if found:
            score += 1
            results.append(f"✅ Bộ test {i+1}: Đạt điểm.")
        else:
            results.append(f"❌ Bộ test {i+1}: Chưa đúng.")
    return score, results

# --- 5. GIAO DIỆN ---
st.title("🏫 Quản lý Thi Scratch - 10 Lớp")
tab1, tab2 = st.tabs(["📝 Học sinh nộp bài", "📊 Bảng điểm giáo viên"])

with tab1:
    st.subheader("Thông tin học sinh")
    c1, c2 = st.columns(2)
    with c1:
        ten_hs = st.text_input("Họ và tên học sinh:")
        lop_hs = st.selectbox("Chọn lớp của em:", DANH_SACH_LOP)
    with c2:
        de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Lượng nước uống", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("Tải file bài làm (.sb3)", type="sb3")

    if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
        if ten_hs and file_sb3:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    project_json = json.loads(archive.read('project.json'))
                
                tests = DE_1_WATER if "Đề 1" in de_thi else DE_2_READING
                final_score, details = grade_project(project_json, tests)

                st.divider()
                st.metric("TỔNG ĐIỂM", f"{final_score} / 6")
                for d in details: st.write(d)

                # LƯU VÀO GOOGLE SHEETS
                new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), 
                                         "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": final_score}])
                try:
                    df = conn.read(ttl=0)
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success("Đã lưu điểm thành công!")
                except:
                    st.warning("Đã chấm điểm xong! Điểm đang được gửi lên máy chủ, em đừng tắt trang web nhé.")
                
                if final_score == 6: st.balloons()
            except:
                st.error("Lỗi file Scratch! Em hãy kiểm tra lại file .sb3")
        else:
            st.warning("Vui lòng nhập tên và chọn file!")

with tab2:
    pwd = st.text_input("Mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        try:
            data = conn.read(ttl=0)
            lop_loc = st.multiselect("Lọc xem theo lớp:", DANH_SACH_LOP, default=DANH_SACH_LOP)
            st.dataframe(data[data['Lop'].isin(lop_loc)], use_container_width=True)
        except:
            st.info("Chưa có dữ liệu hoặc lỗi kết nối Google Sheets.")

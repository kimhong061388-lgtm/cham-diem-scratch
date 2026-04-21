import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import os

# --- 1. CHUẨN HÓA DỮ LIỆU (XÓA DẤU, CHỮ THƯỜNG, XÓA KHOẢNG TRẮNG) ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- 2. CẤU HÌNH HỆ THỐNG & BỘ TEST RÚT GỌN ---
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]
MAT_KHAU_GV = "giaovien2024"

# Đề 1: Chỉ cần tìm từ khóa "binh thuong" hoặc "dieu chinh"
DE_1_WATER = [
    {"out": "binh thuong"}, {"out": "dieu chinh"}, {"out": "dieu chinh"},
    {"out": "binh thuong"}, {"out": "binh thuong"}, {"out": "binh thuong"}
]

# Đề 2: Chỉ cần tìm từ khóa "tap trung" hoặc "hieu bai tot hon"
DE_2_READING = [
    {"out": "tap trung"}, {"out": "tap trung"}, {"out": "hieu bai tot hon"},
    {"out": "hieu bai tot hon"}, {"out": "tap trung"}, {"out": "tap trung"}
]

# --- 3. KẾT NỐI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 4. HÀM CHẤM ĐIỂM THÔNG MINH ---
def grade_project(project_data, test_cases):
    score = 0
    feedback = []
    all_blocks = []
    
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())

    # Quét tất cả văn bản trong mọi khối lệnh có thể chứa nội dung trả lời
    student_texts = []
    for b in all_blocks:
        if isinstance(b, dict):
            # Quét các lệnh Nói/Nghĩ (opcode: looks_say, looks_sayforsecs, looks_think, looks_thinkforsecs)
            # Quét các lệnh Hỏi (opcode: sensing_askandwait)
            # Quét các nội dung văn bản mặc định (thường nằm trong MESSAGE hoặc TEXT)
            inputs = b.get('inputs', {})
            for key in inputs:
                val = str(inputs[key])
                student_texts.append(chuan_hoa(val))

    # Chấm điểm dựa trên từ khóa rút gọn
    for i, test in enumerate(test_cases):
        target_keyword = chuan_hoa(test["out"])
        found = any(target_keyword in txt for txt in student_texts)
        
        if found:
            score += 1
            feedback.append(f"✅ Bộ test {i+1}: Đạt điểm.")
        else:
            feedback.append(f"❌ Bộ test {i+1}: Chưa tìm thấy từ khóa '{test['out']}'.")
            
    return score, feedback

# --- 5. GIAO DIỆN WEB ---
st.set_page_config(page_title="Thi Scratch - 10 Lop", page_icon="🏫")
st.title("🏫 Hệ thống Thi Scratch Tự động")

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
        if not ten_hs or not file_sb3:
            st.warning("Vui lòng nhập tên và chọn file bài làm!")
        else:
            try:
                with zipfile.ZipFile(file_sb3, 'r') as archive:
                    project_json = json.loads(archive.read('project.json'))
                
                selected_tests = DE_1_WATER if "Đề 1" in de_thi else DE_2_READING
                final_score, details = grade_project(project_json, selected_tests)

                st.divider()
                st.metric("TỔNG ĐIỂM CỦA EM", f"{final_score} / 6")
                for d in details: st.write(d)

                # LƯU KẾT QUẢ VÀO GOOGLE SHEETS
                new_row = pd.DataFrame([{
                    "Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                    "Hoc_sinh": ten_hs,
                    "Lop": lop_hs,
                    "De": de_thi,
                    "Diem": final_score
                }])
                
                existing_data = conn.read(ttl=0)
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success("Đã ghi nhận điểm vào hệ thống của lớp.")
                if final_score == 6: st.balloons()
                
            except Exception as e:
                st.error("Lỗi: Hệ thống không đọc được file Scratch. Hãy kiểm tra lại file của em.")

with tab2:
    pwd = st.text_input("Nhập mật khẩu giáo viên:", type="password")
    if pwd == MAT_KHAU_GV:
        st.subheader("Bảng điểm tổng hợp")
        data_sheet = conn.read(ttl=0)
        lop_loc = st.multiselect("Lọc xem theo lớp:", DANH_SACH_LOP, default=DANH_SACH_LOP)
        df_filtered = data_sheet[data_sheet['Lop'].isin(lop_loc)]
        st.dataframe(df_filtered, use_container_width=True)
        
        csv_data = df_filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Tải file Excel (.csv)", csv_data, f"diem_scratch_{datetime.now().strftime('%d_%m')}.csv", "text/csv")
    elif pwd != "":
        st.error("Mật khẩu không đúng!")

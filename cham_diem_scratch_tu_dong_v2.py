import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests

# --- CẤU HÌNH GIAO DIỆN (UI CUSTOM) ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏆", layout="centered")

# Nhúng CSS để trang trí giao diện
st.markdown("""
    <style>
    /* Màu nền trang */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    /* Khung nhập liệu */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 10px;
    }
    /* Nút bấm */
    .stButton>button {
        width: 100%;
        border-radius: 25px;
        background-color: #2e7d32;
        color: white;
        height: 3em;
        font-weight: bold;
        border: none;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
    }
    /* Hiệu ứng khi di chuột vào nút */
    .stButton>button:hover {
        background-color: #1b5e20;
        border: none;
    }
    /* Thẻ hiển thị điểm số */
    div[data-testid="stMetricValue"] {
        background: white;
        padding: 10px 20px;
        border-radius: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        color: #1a73e8;
    }
    /* Khung kết quả */
    .result-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# LINK WEBHOOK CỦA BẠN (GIỮ NGUYÊN)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyLHkdz0jp-aFHjI7u-DTgHNzTy5tww8UBk65gh-r5qxDm4x-gK4vEJqs07hjWXHB0Ilg/exec"

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Gán biến (0.5đ)
    has_set_co = any(isinstance(b, dict) and b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks)
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (0.5đ + 0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu đầu vào 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh nhập dữ liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu đầu vào 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu 2 (0đ)")

    # 5. Phép chia (1.0đ)
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức tính toán (1.0đ)")
    else: report.append("❌ 5. Thiếu phép tính toán (0đ)")

    # 6. Khối If-Else (0.5đ)
    if 'control_if_else' in code_str: total_score += 0.5; report.append("✅ 6. Có khối lệnh If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu khối điều kiện If-Else (0đ)")

    # 7. Logic ngưỡng (0.5đ)
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if all(t in code_str for t in targets): total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
    else: report.append(f"❌ 7. Sai logic ngưỡng điều kiện (0đ)")

    # 8. Thông báo 1 (0.5đ)
    if "binh thuong" in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo kết quả 1 đúng (0.5đ)")
    else: report.append("❌ 8. Sai thông báo kết quả 1 (0đ)")

    # 9. Thông báo 2 (0.5đ)
    if "dieu chinh" in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo kết quả 2 đúng (0.5đ)")
    else: report.append("❌ 9. Sai thông báo kết quả 2 (0đ)")

    # 10. Tiếp tục (0.5đ)
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có lệnh Hỏi để tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu xử lý hỏi tiếp tục (0đ)")

    # 11. Kết thúc (0.5đ)
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc bài (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN CHÍNH ---
st.title("🏫 Hệ thống Chấm thi Scratch")
st.write("Dành cho kỳ thi cuối kỳ II - Khối 9")

with st.sidebar:
    st.image("https://flaticon.com", width=100)
    st.header("Hướng dẫn nộp bài")
    st.info("""
    1. Nhập chính xác Họ tên và Lớp.
    2. Chọn đúng đề đã thực hiện.
    3. Tải file đuôi `.sb3`.
    4. Nhấn nút Nộp bài và chờ kết quả.
    """)

# Tạo form nhập liệu
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        ten_hs = st.text_input("👤 Họ và tên học sinh:")
        lop_hs = st.selectbox("🏫 Chọn lớp của em:", DANH_SACH_LOP)
    with col2:
        de_thi = st.selectbox("📝 Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("📂 Tải file bài làm (.sb3)", type="sb3")

st.markdown("---")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            
            # Tính giờ VN
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")

            # Hiển thị kết quả trong Card
            st.markdown(f"""
                <div class='result-card'>
                    <h2 style='text-align: center; color: #2e7d32;'>KẾT QUẢ CHẤM THI</h2>
                    <p style='text-align: center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                st.metric("TỔNG ĐIỂM", f"{score} / 6.0")

            # GỬI ĐIỂM
            try:
                payload = {"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}
                requests.post(WEBHOOK_URL, json=payload, timeout=10)
                st.success("🎉 Hệ thống đã tự động ghi điểm của em vào danh sách lớp!")
            except:
                st.warning("⚠️ Kết nối máy chủ chậm, em hãy tải phiếu điểm báo GV nhé.")

            # Chi tiết
            with st.expander("🔍 Xem chi tiết các tiêu chí chấm điểm", expanded=True):
                for d in details:
                    st.write(d)
                
            if score == 6.0: st.balloons()
            
            # Phiếu điểm minh chứng
            minh_chung = f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nThoi gian: {time_str}\nDe: {de_thi}"
            st.download_button("📥 TẢI PHIẾU ĐIỂM (Minh chứng)", minh_chung, file_name=f"Diem_{ten_hs}.txt")
            
        except:
            st.error("❌ Lỗi file: Hệ thống không đọc được file .sb3 của em. Hãy kiểm tra lại file!")
    else:
        st.warning("⚠️ Em hãy điền đầy đủ thông tin và chọn file bài làm nhé!")

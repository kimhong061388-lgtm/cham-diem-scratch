import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests

# --- CẤU HÌNH GIAO DIỆN (UI) ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏆", layout="wide")

# Nhúng CSS trang trí giao diện chuyên nghiệp
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #e0e0e0; }
    .result-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border-left: 10px solid #2e7d32;
    }
    .stButton>button {
        width: 100%;
        border-radius: 25px;
        background-color: #2e7d32;
        color: white;
        height: 3.5em;
        font-weight: bold;
        font-size: 18px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
    }
    .stButton>button:hover { background-color: #1b5e20; }
    </style>
    """, unsafe_allow_html=True)

# --- THANH HƯỚNG DẪN BÊN TRÁI (SIDEBAR) ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("""
    **Các bước thực hiện:**
    1. 👤 **Nhập thông tin:** Gõ đúng Họ tên và chọn Lớp.
    2. 📝 **Chọn đề:** Chọn đúng đề thi em đã làm.
    3. 📂 **Tải bài:** Chọn file `.sb3` từ máy tính.
    4. 🚀 **Nộp bài:** Nhấn nút màu xanh để xem điểm.
    """)
    st.warning("""
    **Lưu ý quan trọng:**
    - Hệ thống chấm theo logic khối lệnh.
    - **Mỗi học sinh chỉ nộp bài 01 lần duy nhất.**
    - Em hãy kiểm tra thật kỹ bài làm trước khi nộp.
    - Sau khi nộp, tải ngay **Phiếu điểm** về làm minh chứng.
    """)
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

# --- HÀM CHUẨN HÓA DỮ LIỆU ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# --- CẤU HÌNH KẾT NỐI ---
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyLHkdz0jp-aFHjI7u-DTgHNzTy5tww8UBk65gh-r5qxDm4x-gK4vEJqs07hjWXHB0Ilg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- HÀM CHẤM ĐIỂM (GIỮ NGUYÊN LOGIC KHẮT KHE) ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có
    has_set_co = any(isinstance(b, dict) and b.get('opcode') == 'data_setvariableto' and 'co' in chuan_hoa(str(b.get('inputs', {}).get('VALUE', ''))) for b in all_blocks)
    if has_set_co: total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not
    has_repeat = any(isinstance(b, dict) and b.get('opcode') == 'control_repeat_until' for b in all_blocks)
    has_not_in_loop = 'operator_not' in code_str and 'control_repeat_until' in code_str
    if has_repeat and has_not_in_loop: total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp hoặc thiếu điều kiện 'Not' (0đ)")

    # 3 & 4. Nhập liệu
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu đầu vào 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh nhập dữ liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu đầu vào 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh nhập dữ liệu 2 (0đ)")

    # 5. Phép chia
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức tính toán (Phép chia) (1.0đ)")
    else: report.append("❌ 5. Thiếu phép tính toán chia (0đ)")

    # 6. Khối If-Else
    if 'control_if_else' in code_str: total_score += 0.5; report.append("✅ 6. Có khối lệnh If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu khối điều kiện If-Else (0đ)")

    # 7. Logic ngưỡng (Kiểm tra khắt khe)
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    has_all_targets = all(t in code_str for t in targets)
    logic_count = code_str.count('operator_lt') + code_str.count('operator_gt') + code_str.count('operator_not')
    if has_all_targets and logic_count >= 2:
        total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng so sánh {targets} (0.5đ)")
    else: report.append(f"❌ 7. Sai logic ngưỡng: Thiếu mốc so sánh hoặc thiếu khối logic kết hợp (0đ)")

    # 8 & 9. Thông báo
    t1, t2 = ("binh thuong", "dieu chinh")
    if t1 in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo đúng trường hợp 'Bình thường' (0.5đ)")
    else: report.append("❌ 8. Sai thông báo trường hợp 'Bình thường' (0đ)")
    if t2 in full_txt or "hieu bai" in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo đúng trường hợp 'Điều chỉnh' (0.5đ)")
    else: report.append("❌ 9. Sai thông báo trường hợp 'Điều chỉnh' (0đ)")

    # 10. Tiếp tục
    if len(asks) >= 3 or "tiep tuc" in full_txt: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục để duy trì lặp (0.5đ)")
    else: report.append("❌ 10. Thiếu xử lý hỏi Tiếp tục (0đ)")

    # 11. Kết thúc
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu thông báo Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
st.write("Dành cho kỳ thi Cuối kỳ II - Học sinh thực hiện nộp bài và nhận điểm tại chỗ.")

with st.container():
    c1, c2 = st.columns(2)
    with c1:
        ten_hs = st.text_input("👤 Nhập Họ và tên học sinh (Viết hoa có dấu):")
        lop_hs = st.selectbox("🏫 Em học lớp nào:", DANH_SACH_LOP)
    with c2:
        de_thi = st.selectbox("📝 Đề thi em đã thực hiện:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
        file_sb3 = st.file_uploader("📂 Tải tệp .sb3 của em lên đây:", type="sb3")

st.markdown("---")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM NGAY"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")

            st.markdown(f"""
                <div class='result-card'>
                    <h2 style='text-align: center; color: #2e7d32;'>KẾT QUẢ CHẤM THI</h2>
                    <h1 style='text-align: center; font-size: 50px;'>{score} / 6.0</h1>
                    <p style='text-align: center; font-size: 18px;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p>
                    <p style='text-align: center; color: gray;'>Ghi nhận lúc: {time_str}</p>
                </div>
            """, unsafe_allow_html=True)

            try:
                payload = {"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}
                requests.post(WEBHOOK_URL, json=payload, timeout=10)
                st.success("🎉 Hệ thống đã ghi nhận điểm của em vào danh sách thi!")
            except:
                st.warning("⚠️ Kết nối mạng chậm, điểm chưa lưu tự động. Em hãy tải phiếu điểm báo ngay cho GV nhé.")

            with st.expander("🔍 Xem chi tiết bảng chấm điểm", expanded=True):
                for d in details:
                    st.write(d)
                
            if score == 6.0: st.balloons()
            
            minh_chung = f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nDe: {de_thi}\nThoi gian: {time_str}"
            st.download_button("📥 TẢI PHIẾU ĐIỂM MINH CHỨNG", minh_chung, file_name=f"Diem_{ten_hs}.txt")
            
        except:
            st.error("❌ Lỗi file: Không đọc được tệp bài làm. Hãy kiểm tra lại file của em!")
    else:
        st.warning("⚠️ Em hãy nhập đầy đủ thông tin và chọn bài làm trước khi nhấn Nộp bài!")

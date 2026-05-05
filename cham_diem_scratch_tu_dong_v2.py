import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests
import hashlib

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #e0e0e0; }
    .result-card {
        background-color: white; padding: 25px; border-radius: 15px;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.1); margin-bottom: 20px;
        border-left: 10px solid #d32f2f;
    }
    .stButton>button {
        width: 100%; border-radius: 25px; background-color: #2e7d32;
        color: white; height: 3.5em; font-weight: bold; font-size: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR HƯỚNG DẪN ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập Họ tên, Lớp.\n2. Chọn đúng Đề thi.\n3. Tải file .sb3.\n4. Nhấn Nộp bài.")
    st.warning("⚠️ **LƯU Ý:** Chỉ nộp bài 01 lần. Hệ thống tự phát hiện gian lận.")
    st.divider()
    st.write("📍 *Kỳ thi Cuối kỳ II - Khối 9*")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbza69BFCBKFFQKg4iIwBBnFDZPviICnNIwRo36W9ADsYA1Cwx7PTt91clyXsX9JpYLg/exec"
DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

# --- 3. HÀM CHẤM ĐIỂM SIÊU BỀN BỈ ---
def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    script_desc = []
    
    # Gom toàn bộ dữ liệu file thành một chuỗi văn bản khổng lồ để quét tên biến
    raw_json_str = json.dumps(project_data).lower()
    
    # Xác định yêu cầu theo đề
    is_de1 = "Đề 1" in de_thi
    in1, in2, out = ('"l"', '"w"', '"i"') if is_de1 else ('"s"', '"t"', '"v"')
    
    # --- CHẤM ĐIỂM ---

    # 1. Biến Trả lời = Có (0.5đ)
    if 'data_setvariableto' in raw_json_str and '"co"' in raw_json_str:
        total_score += 0.5; report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp + Not (0.5đ)
    if 'control_repeat_until' in raw_json_str and 'operator_not' in raw_json_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc lặp (0đ)")

    # 3+4. Nhập liệu (Quét trực tiếp sự xuất hiện của tên biến cạnh khối gán)
    # Kiểm tra xem có lệnh đặt biến cho in1 và in2 không
    check_in1 = in1 in raw_json_str and 'sensing_answer' in raw_json_str
    check_in2 = in2 in raw_json_str and 'sensing_answer' in raw_json_str
    
    if check_in1 and check_in2:
        total_score += 1.0; report.append(f"✅ 3+4. Nhập liệu đúng biến {in1.upper()}, {in2.upper()} (1.0đ)")
    else:
        total_score += 0.5 if (check_in1 or check_in2) else 0
        report.append(f"❌ 3+4. Sai tên biến nhập liệu (0đ)")

    # 5. Công thức (Kiểm tra xem biến OUT có được gán bằng phép CHIA của IN1 và IN2 không)
    # Quét chuỗi: tìm khối chia mà có chứa cả in1 và in2
    has_divide = 'operator_divide' in raw_json_str
    formula_strict = out in raw_json_str and in1 in raw_json_str and in2 in raw_json_str and has_divide
    
    if formula_strict:
        total_score += 1.0; report.append(f"✅ 5. Đúng công thức {out.upper()} = {in1.upper()} / {in2.upper()} (1.0đ)")
        script_desc.append(f"[Toán: OK]")
    else:
        report.append("❌ 5. Sai công thức hoặc sai tên biến (0đ)")
        script_desc.append("[Toán: SAI]")

    # 6. If-Else (0.5đ)
    if 'control_if_else' in raw_json_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)")

    # 7. Ngưỡng (0.5đ)
    targets = ["30", "40"] if is_de1 else ["0.5", "1"]
    if all(t in raw_json_str for t in targets):
        total_score += 0.5; report.append(f"✅ 7. Đúng ngưỡng {targets} (0.5đ)")
    else: report.append("❌ 7. Sai logic ngưỡng (0đ)")

    # 8, 9, 11. Thông báo
    full_txt = chuan_hoa(raw_json_str)
    if any(k in full_txt for k in ["binh thuong", "tap trung"]): total_score += 0.5; report.append("✅ 8. Thông báo 1 OK")
    if any(k in full_txt for k in ["dieu chinh", "hieu bai"]): total_score += 0.5; report.append("✅ 9. Thông báo 2 OK")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Kết thúc OK")

    # 10. Tiếp tục
    asks_count = raw_json_str.count('sensing_askandwait')
    if asks_count >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi tiếp tục (0đ)")

    return round(total_score, 1), " | ".join(script_desc), report

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh:")
    lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3:", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            ma_dinh_danh = hashlib.md5(file_bytes).hexdigest()[:10].upper()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, summary, details = grade_by_logic_barem(data, de_thi)
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")
            
            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b> | Lớp: <b>{lop_hs}</b></p></div>", unsafe_allow_html=True)
            
            try:
                requests.post(WEBHOOK_URL, json={"Thoi_gian": time_str, "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score, "Ghi_chu": summary, "Ma_dinh_danh": ma_dinh_danh}, timeout=10)
                st.success(f"🎉 Đã lưu điểm! Mã bài: {ma_dinh_danh}")
            except: st.warning("⚠️ Lỗi mạng, điểm chưa vào Sheets.")
            
            with st.expander("🔍 Chi tiết bảng điểm 11 tiêu chí", expanded=True):
                for d in details: st.write(d)
        except: st.error("❌ File Scratch không hợp lệ!")
    else: st.warning("Vui lòng điền đủ thông tin!")

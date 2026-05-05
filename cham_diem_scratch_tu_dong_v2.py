import streamlit as st
import json
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from unidecode import unidecode
import io
import requests

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống chấm thi Scratch", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: white; border-right: 2px solid #e0e0e0; }
    .result-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0px 10px 25px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 10px solid #2e7d32; }
    .stButton>button { width: 100%; border-radius: 25px; background-color: #2e7d32; color: white; height: 3.5em; font-weight: bold; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR HƯỚNG DẪN ---
with st.sidebar:
    st.image("https://flaticon.com", width=80)
    st.title("📖 HƯỚNG DẪN")
    st.info("1. Nhập Họ tên, Lớp\n2. Chọn Đề thi\n3. Tải file .sb3\n4. Nhấn Nộp bài")
    st.warning("⚠️ CHỈ NỘP BÀI 01 LẦN DUY NHẤT.")

def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

# !!! THAY LINK WEBHOOK MỚI CỦA BẠN VÀO ĐÂY !!!
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbzGbMWbgWnkg9IEEC9wxUPKKNOAohBuAWdmlvq3qfEVcrBqbzxlh8vnwKPQXf8WwbpyXw/exec"

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    blocks_found = [] 
    
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()
    full_txt = chuan_hoa(code_str)

    # 1. Gán biến
    if 'data_setvariableto' in code_str and 'co' in full_txt:
        total_score += 0.5; report.append("✅ 1. Gán biến (0.5đ)"); blocks_found.append("M1:Có")
    else: report.append("❌ 1. Gán biến (0đ)"); blocks_found.append("M1:Ko")

    # 2. Vòng lặp
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5; report.append("✅ 2. Vòng lặp (0.5đ)"); blocks_found.append("M2:OK")
    else: report.append("❌ 2. Vòng lặp (0đ)"); blocks_found.append("M2:Ko")

    # 3 & 4. Nhập liệu
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Dữ liệu 1 (0.5đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Dữ liệu 2 (0.5đ)")
    blocks_found.append(f"Hỏi:{len(asks)}")

    # 5. Phép chia
    if 'operator_divide' in code_str:
        total_score += 1.0; report.append("✅ 5. Phép chia (1.0đ)"); blocks_found.append("Chia:OK")
    else: report.append("❌ 5. Phép chia (0đ)"); blocks_found.append("Chia:Ko")

    # 6. If-Else
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. If-Else (0.5đ)"); blocks_found.append("IfElse:Có")
    else: report.append("❌ 6. If-Else (0đ)"); blocks_found.append("IfElse:Ko")

    # 7. Ngưỡng
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if all(t in code_str for t in targets):
        total_score += 0.5; report.append(f"✅ 7. Ngưỡng {targets} (0.5đ)"); blocks_found.append("Ngưỡng:OK")
    else: report.append("❌ 7. Sai ngưỡng (0đ)"); blocks_found.append("Ngưỡng:Sai")

    # 11. Kết thúc
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Kết thúc (0.5đ)"); blocks_found.append("End:OK")
    else: report.append("❌ 11. Kết thúc (0đ)"); blocks_found.append("End:Ko")

    summary = " | ".join(blocks_found)
    return round(total_score, 1), report, summary

# --- GIAO DIỆN CHÍNH ---
st.title("🏢 HỆ THỐNG CHẤM THI SCRATCH TỰ ĐỘNG")
c1, c2 = st.columns(2)
with c1:
    ten_hs = st.text_input("👤 Họ và tên học sinh:")
    lop_hs = st.selectbox("🏫 Lớp:", DANH_SACH_LOP)
with c2:
    de_thi = st.selectbox("📝 Đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
    file_sb3 = st.file_uploader("📂 Tải tệp .sb3", type="sb3")

if st.button("🚀 NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details, code_summary = grade_by_logic_barem(data, de_thi)
            
            now_vn = datetime.now() + timedelta(hours=7)
            time_str = now_vn.strftime("%H:%M:%S %d/%m/%Y")

            st.markdown(f"<div class='result-card'><h1 style='text-align:center;'>{score} / 6.0</h1><p style='text-align:center;'>Học sinh: <b>{ten_hs.upper()}</b></p></div>", unsafe_allow_html=True)

            # LƯU ĐIỂM KÈM TÓM TẮT
            try:
                payload = {
                    "Thoi_gian": time_str, "Hoc_sinh": ten_hs, 
                    "Lop": lop_hs, "De": de_thi, "Diem": score,
                    "Ghi_chu": code_summary 
                }
                requests.post(WEBHOOK_URL, json=payload, timeout=10)
                st.success("🎉 Đã lưu điểm thành công!")
            except:
                st.warning("⚠️ Lỗi mạng, hãy tải phiếu điểm báo GV.")

            with st.expander("🔍 Chi tiết chấm điểm", expanded=True):
                for d in details: st.write(d)
            st.download_button("📥 TẢI PHIẾU ĐIỂM", f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}\nLog: {code_summary}", file_name=f"Diem_{ten_hs}.txt")
        except: st.error("Lỗi đọc file .sb3!")
    else: st.warning("Vui lòng điền đủ tên và tải file!")

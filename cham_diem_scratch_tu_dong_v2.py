import streamlit as st
from streamlit_gsheets import GSheetsConnection
import json
import zipfile
import pandas as pd
from datetime import datetime
from unidecode import unidecode
import io

# --- CHUẨN HÓA ---
def chuan_hoa(van_ban):
    if not van_ban: return ""
    return unidecode(str(van_ban)).lower().strip()

DANH_SACH_LOP = ["9A1", "9A2", "9A3", "9A4", "9A5", "9A6", "9A7", "9A8", "9A9", "9A10"]

def grade_by_logic_barem(project_data, de_thi):
    total_score = 0.0
    report = []
    all_blocks = []
    for t in project_data.get('targets', []):
        all_blocks.extend(t.get('blocks', {}).values())
    code_str = str(all_blocks).lower()
    full_text = chuan_hoa(code_str)

    # 1. Biến Trả lời = Có (0.5đ)
    if 'data_setvariableto' in code_str and ('co' in full_text):
        total_score += 0.5
        report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: report.append("❌ 1. Thiếu gán biến Trả lời = Có (0đ)")

    # 2. Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5
        report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (0.5đ + 0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu nhập liệu 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu nhập liệu 2 (0đ)")

    # 5. Phép chia (1.0đ)
    if 'operator_divide' in code_str: total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    else: report.append("❌ 5. Thiếu phép chia (0đ)")

    # 6 & 7. If-Else & Logic (0.5đ + 0.5đ)
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if any(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
        else: report.append("❌ 7. Sai logic ngưỡng (0đ)")
    else:
        report.append("❌ 6. Thiếu If-Else (0đ)")
        report.append("❌ 7. Không có If nên không chấm logic (0đ)")

    # 8 & 9. Thông báo (0.5đ + 0.5đ)
    if "binh thuong" in full_text: total_score += 0.5; report.append("✅ 8. Thông báo 'Bình thường' đúng (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 'Bình thường' (0đ)")
    if "dieu chinh" in full_text or "hieu bai" in full_text: total_score += 0.5; report.append("✅ 9. Thông báo 'Điều chỉnh' đúng (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 'Điều chỉnh' (0đ)")

    # 10. Tiếp tục (0.5đ)
    if len(asks) >= 3 or "tiep tuc" in full_text:
        total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")

    # 11. Kết thúc (0.5đ)
    if "ket thuc" in full_text: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống V2", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🏆 Hệ thống Chấm điểm Scratch V2")

ten_hs = st.text_input("Họ và tên học sinh:")
lop_hs = st.selectbox("Chọn lớp:", DANH_SACH_LOP)
de_thi = st.selectbox("Chọn đề thi:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file .sb3", type="sb3")

if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            file_bytes = file_sb3.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            
            score, details = grade_by_logic_barem(data, de_thi)
            st.divider()
            st.metric("TỔNG ĐIỂM CỦA EM", f"{score} / 6.0")
            
            # GHI GOOGLE SHEETS
            try:
                new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}])
                df = conn.read(ttl=0)
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success("✅ Đã ghi nhận điểm vào hệ thống!")
            except Exception as e:
                st.warning(f"⚠️ Lỗi kết nối ghi điểm, em hãy tải phiếu điểm bên dưới nhé. (Lỗi: {e})")

            for d in details: st.write(d)
            if score == 6.0: st.balloons()
            
            minh_chung = f"Hoc sinh: {ten_hs}\nLop: {lop_hs}\nDiem: {score}"
            st.download_button("📥 TẢI PHIẾU ĐIỂM", minh_chung, file_name=f"Diem_{ten_hs}.txt")
        except: st.error("Lỗi file Scratch!")

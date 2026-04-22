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

    # 1. KIỂM TRA LỆNH GÁN BIẾN TRẢ LỜI = CÓ (Chấm cực gắt)
    has_set_co = False
    for b in all_blocks:
        if isinstance(b, dict) and b.get('opcode') == 'data_setvariableto':
            # Quét sâu vào giá trị gán của biến
            val_input = str(b.get('inputs', {}).get('VALUE', ''))
            if 'co' in chuan_hoa(val_input):
                has_set_co = True
                break
    
    if has_set_co: 
        total_score += 0.5
        report.append("✅ 1. Gán biến Trả lời = Có (0.5đ)")
    else: 
        report.append("❌ 1. Thiếu hoặc sai lệnh gán biến Trả lời = Có (0đ)")

    # 2. Vòng lặp Repeat Until + Not (0.5đ)
    if 'control_repeat_until' in code_str and 'operator_not' in code_str:
        total_score += 0.5
        report.append("✅ 2. Vòng lặp Repeat Until + Not (0.5đ)")
    else: report.append("❌ 2. Sai cấu trúc vòng lặp (0đ)")

    # 3 & 4. Nhập liệu (0.5đ + 0.5đ)
    asks = [b for b in all_blocks if isinstance(b, dict) and b.get('opcode') == 'sensing_askandwait']
    if len(asks) >= 1: total_score += 0.5; report.append("✅ 3. Nhập dữ liệu 1 (0.5đ)")
    else: report.append("❌ 3. Thiếu lệnh hỏi 1 (0đ)")
    if len(asks) >= 2: total_score += 0.5; report.append("✅ 4. Nhập dữ liệu 2 (0.5đ)")
    else: report.append("❌ 4. Thiếu lệnh hỏi 2 (0đ)")

    # 5. Phép chia (1.0đ)
    if 'operator_divide' in code_str:
        total_score += 1.0; report.append("✅ 5. Đúng công thức chia (1.0đ)")
    else: report.append("❌ 5. Thiếu phép chia (0đ)")

    # 6 & 7. If-Else & Logic
    targets = ["30", "40"] if "Đề 1" in de_thi else ["0.5", "1"]
    if 'control_if_else' in code_str:
        total_score += 0.5; report.append("✅ 6. Có khối If-Else (0.5đ)")
        if all(t in code_str for t in targets):
            total_score += 0.5; report.append(f"✅ 7. Đúng logic ngưỡng {targets} (0.5đ)")
        else: report.append(f"❌ 7. Sai ngưỡng điều kiện (0đ)")
    else: report.append("❌ 6. Thiếu If-Else (0đ)"); report.append("❌ 7. Không chấm logic (0đ)")

    # 8 & 9. Thông báo
    full_txt = chuan_hoa(code_str)
    if "binh thuong" in full_txt: total_score += 0.5; report.append("✅ 8. Thông báo đúng 1 (0.5đ)")
    else: report.append("❌ 8. Sai thông báo 1 (0đ)")
    if "dieu chinh" in full_txt or "hieu bai" in full_txt: total_score += 0.5; report.append("✅ 9. Thông báo đúng 2 (0.5đ)")
    else: report.append("❌ 9. Sai thông báo 2 (0đ)")

    # 10. Tiếp tục & 11. Kết thúc
    if len(asks) >= 3: total_score += 0.5; report.append("✅ 10. Có hỏi Tiếp tục (0.5đ)")
    else: report.append("❌ 10. Thiếu hỏi Tiếp tục (0đ)")
    if "ket thuc" in full_txt: total_score += 0.5; report.append("✅ 11. Có thông báo Kết thúc (0.5đ)")
    else: report.append("❌ 11. Thiếu Kết thúc (0đ)")

    return round(total_score, 1), report

# --- GIAO DIỆN ---
st.set_page_config(page_title="Thi Scratch V2", page_icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("🏆 Hệ thống Chấm điểm Scratch V2")
ten_hs = st.text_input("Học sinh:")
lop_hs = st.selectbox("Lớp:", DANH_SACH_LOP)
de_thi = st.selectbox("Đề:", ["Đề 1: Chỉ số nước", "Đề 2: Tốc độ đọc sách"])
file_sb3 = st.file_uploader("Tải file .sb3", type="sb3")

if st.button("NỘP BÀI VÀ XEM ĐIỂM"):
    if ten_hs and file_sb3:
        try:
            with zipfile.ZipFile(io.BytesIO(file_sb3.read()), 'r') as archive:
                data = json.loads(archive.read('project.json'))
            score, details = grade_by_logic_barem(data, de_thi)
            st.divider()
            st.metric("TỔNG ĐIỂM CỦA EM", f"{score} / 6.0")
            
            try:
                new_row = pd.DataFrame([{"Thoi_gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"), "Hoc_sinh": ten_hs, "Lop": lop_hs, "De": de_thi, "Diem": score}])
                df = conn.read(ttl=0)
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success("✅ Đã tự động lưu điểm thành công!")
            except Exception as e:
                st.warning(f"⚠️ Lỗi kết nối ghi điểm. (Chi tiết: {e})")

            for d in details: st.write(d)
        except: st.error("Lỗi file Scratch!")
    else: st.warning("Vui lòng điền tên và chọn file!")

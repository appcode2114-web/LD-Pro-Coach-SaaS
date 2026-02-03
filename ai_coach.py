import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import bcrypt
import time
import requests
from datetime import datetime, timedelta
from supabase import create_client, Client

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (V61 - FULL CONTROL)
# ==========================================
st.set_page_config(page_title="LD PRO COACH - System", layout="wide", page_icon="🦁")

# --- KẾT NỐI SUPABASE ---
try:
    SUPABASE_URL = st.secrets["supabase"]["URL"]
    SUPABASE_KEY = st.secrets["supabase"]["KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ Lỗi cấu hình Secrets."); st.stop()

# ==========================================
# 2. HÀM XỬ LÝ (CORE LOGIC)
# ==========================================

def send_telegram(message):
    try:
        token = st.secrets["telegram"]["bot_token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message})
    except: pass 

def run_query(table_name, select="*", order_by=None, filter_col=None, filter_val=None):
    try:
        query = supabase.table(table_name).select(select)
        if filter_col and filter_val is not None: query = query.eq(filter_col, filter_val)
        if order_by: query = query.order(order_by[0], desc=(order_by[1]=='desc'))
        return pd.DataFrame(query.execute().data)
    except: return pd.DataFrame()

def insert_data(table_name, data_dict):
    try: supabase.table(table_name).insert(data_dict).execute(); return True, ""
    except Exception as e: return False, str(e)

def update_data(table_name, update_dict, match_col, match_val):
    try: supabase.table(table_name).update(update_dict).eq(match_col, match_val).execute(); return True
    except: return False

def delete_data(table_name, match_col, match_val):
    try: 
        supabase.table(table_name).delete().eq(match_col, match_val).execute()
        return True
    except: return False

def delete_user_force(username):
    """Xóa User SaaS (Khách mua phần mềm)"""
    try:
        user_data = supabase.table("users").select("id").eq("username", username).execute()
        if user_data.data:
            user_id = user_data.data[0]['id']
            supabase.table("checkins").delete().eq("trainer_id", user_id).execute()
            supabase.table("clients").delete().eq("trainer_id", user_id).execute()
            supabase.table("users").delete().eq("username", username).execute()
            return True, "Đã dọn dẹp sạch sẽ!"
        else:
            supabase.table("users").delete().eq("username", username).execute()
            return True, "Đã xóa user!"
    except Exception as e: return False, f"Lỗi DB: {str(e)}"

def delete_client_data(client_id):
    """Xóa Học viên riêng (Nguồn doanh thu HLV)"""
    try:
        # Xóa check-in của học viên này trước
        supabase.table("checkins").delete().eq("client_id", client_id).execute()
        # Xóa học viên
        supabase.table("clients").delete().eq("id", client_id).execute()
        return True
    except: return False

def login_user(username, password):
    df = run_query("users", filter_col="username", filter_val=username)
    if not df.empty:
        user = df.iloc[0]
        if user['username'] != 'admin' and not bool(user.get('is_active', False)):
            return "LOCKED" 
        try:
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')): return user.to_dict()
        except:
            if password == user['password_hash']: return user.to_dict()
    return None

def register_user(u, p, n, e, package_info):
    check = run_query("users", select="id", filter_col="username", filter_val=u)
    if not check.empty: return False, "Tên đăng nhập đã tồn tại"
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    full_name_info = f"{n} ({package_info})"
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ok, msg = insert_data("users", {
        "username": u, "password_hash": hashed, "full_name": full_name_info, 
        "email": e, "expiry_date": None, "is_active": False,
        "created_at": now_iso, "note": ""
    })
    return ok, ""

def parse_revenue_logic(full_name):
    if not full_name or not isinstance(full_name, str): return 0, "Không xác định", 0
    if "1 Tháng" in full_name: return 200000, "1 Tháng", 1
    if "3 Tháng" in full_name: return 500000, "3 Tháng", 3
    if "6 Tháng" in full_name: return 900000, "6 Tháng", 6
    if "1 Năm" in full_name: return 1500000, "1 Năm", 12
    return 0, "User Test/Cũ", 0

# --- FORMULAS ---
JP_FORMULAS = {'Nam': {'Bulking': {'Light': {'train': {'p': 3.71, 'c': 4.78, 'f': 0.58}, 'rest': {'p': 3.25, 'c': 2.78, 'f': 1.44}}, 'Moderate': {'train': {'p': 4.07, 'c': 5.23, 'f': 0.35}, 'rest': {'p': 3.10, 'c': 3.10, 'f': 1.83}}, 'High': {'train': {'p': 4.25, 'c': 5.60, 'f': 0.50}, 'rest': {'p': 3.30, 'c': 3.50, 'f': 1.90}}}, 'Maintain': {'Light': {'train': {'p': 3.10, 'c': 3.98, 'f': 0.67}, 'rest': {'p': 3.10, 'c': 1.35, 'f': 0.94}}, 'Moderate': {'train': {'p': 3.38, 'c': 4.37, 'f': 0.85}, 'rest': {'p': 3.00, 'c': 2.58, 'f': 1.33}}, 'High': {'train': {'p': 3.60, 'c': 4.80, 'f': 1.00}, 'rest': {'p': 3.20, 'c': 3.00, 'f': 1.50}}}, 'Cutting': {'Light': {'train': {'p': 2.48, 'c': 3.18, 'f': 0.63}, 'rest': {'p': 2.78, 'c': 1.23, 'f': 0.96}}, 'Moderate': {'train': {'p': 2.71, 'c': 3.01, 'f': 0.70}, 'rest': {'p': 2.74, 'c': 2.05, 'f': 0.92}}, 'High': {'train': {'p': 2.90, 'c': 3.40, 'f': 0.80}, 'rest': {'p': 2.90, 'c': 2.30, 'f': 1.10}}}}, 'Nữ': {'Bulking': {'Light': {'train': {'p': 2.40, 'c': 3.50, 'f': 0.80}, 'rest': {'p': 2.40, 'c': 2.00, 'f': 1.00}}, 'Moderate': {'train': {'p': 2.60, 'c': 4.00, 'f': 0.70}, 'rest': {'p': 2.50, 'c': 2.50, 'f': 1.10}}, 'High': {'train': {'p': 2.80, 'c': 4.50, 'f': 0.80}, 'rest': {'p': 2.60, 'c': 3.00, 'f': 1.20}}}, 'Maintain': {'Light': {'train': {'p': 2.20, 'c': 3.00, 'f': 0.90}, 'rest': {'p': 2.20, 'c': 1.50, 'f': 1.00}}, 'Moderate': {'train': {'p': 2.40, 'c': 3.50, 'f': 0.85}, 'rest': {'p': 2.30, 'c': 2.00, 'f': 1.10}}, 'High': {'train': {'p': 2.50, 'c': 4.00, 'f': 1.00}, 'rest': {'p': 2.40, 'c': 2.50, 'f': 1.20}}}, 'Cutting': {'Light': {'train': {'p': 2.20, 'c': 2.00, 'f': 0.70}, 'rest': {'p': 2.20, 'c': 0.80, 'f': 0.90}}, 'Moderate': {'train': {'p': 2.40, 'c': 2.50, 'f': 0.70}, 'rest': {'p': 2.40, 'c': 1.20, 'f': 0.90}}, 'High': {'train': {'p': 2.50, 'c': 3.00, 'f': 0.80}, 'rest': {'p': 2.50, 'c': 1.50, 'f': 1.00}}}}}

def calc_basic(w, h, a, g, act, goal):
    if w == 0 or h == 0: return 0, 0, 0, 0
    bmr = 10*w + 6.25*h - 5*a + 5 if g=='Nam' else 10*w + 6.25*h - 5*a - 161
    act_map = {'Light':1.375, 'Moderate':1.55, 'High':1.725}
    tdee = bmr * act_map.get(act, 1.375)
    target = tdee + 400 if "Tăng" in goal else (tdee if "Cải thiện" in goal else tdee - 400)
    p, c, f = (target*0.3)/4, (target*0.4)/4, (target*0.3)/9
    return int(target), int(p), int(c), int(f)

def make_meal_df(p, c, f, type_day):
    if type_day == 'train': data = [["Bữa 1 (Sáng)", 0, int(p*0.17), int(f*0.4), ""], ["Bữa 2 (Phụ)", int(c*0.25), int(p*0.16), 0, ""], ["PRE-WORKOUT", int(c*0.15), int(p*0.17), int(f*0.3), ""], ["POST-WORKOUT", int(c*0.45), int(p*0.17), 0, ""], ["Bữa 5", int(c*0.15), int(p*0.17), int(f*0.3), ""], ["Bữa 6", 0, int(p*0.16), 0, ""]]
    else: data = [["Bữa 1", 0, int(p*0.16), int(f*0.25), ""], ["Bữa 2", int(c*0.25), int(p*0.16), int(f*0.15), ""], ["Bữa 3", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 4", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 5", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 6", 0, int(p*0.17), int(f*0.15), ""]]
    return pd.DataFrame(data, columns=["BỮA", "CARB (g)", "PRO (g)", "FAT (g)", "GỢI Ý"])

def draw_donut(p, c, f, cal):
    fig = px.pie(values=[p*4, c*4, f*9], names=['Pro', 'Carb', 'Fat'], hole=.65, color_discrete_sequence=['#00BFFF', '#FF4500', '#FFD700'])
    fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=150, paper_bgcolor='rgba(0,0,0,0)', annotations=[dict(text=f"<span style='font-size:24px; color:#FFF; font-weight:bold; font-family:Teko'>{cal}</span>", x=0.5, y=0.5, font_size=20, showarrow=False)])
    return fig

# ==========================================
# 4. LUỒNG CHÍNH
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

# --- MÀN HÌNH ĐĂNG NHẬP & ĐĂNG KÝ ---
if not st.session_state.logged_in:
    st.markdown("<div class='main-logo'>LD PRO COACH</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab1, tab2 = st.tabs(["ĐĂNG NHẬP", "ĐĂNG KÝ GÓI"])
        with tab1:
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("🚀 ĐĂNG NHẬP", type="primary", use_container_width=True):
                    res = login_user(u, p)
                    if isinstance(res, str) and res == "LOCKED":
                        st.warning("🔒 Tài khoản đang chờ duyệt! Vui lòng liên hệ Admin.")
                    elif res:
                        st.session_state.logged_in = True
                        st.session_state.user_info = res
                        st.success("Thành công!"); time.sleep(0.5); st.rerun()
                    else: st.error("Sai thông tin!")
        with tab2:
            if 'reg_step' not in st.session_state: st.session_state.reg_step = 1
            if st.session_state.reg_step == 1:
                st.markdown("##### 1. THÔNG TIN CÁ NHÂN")
                nu = st.text_input("Tên đăng nhập", key="r_u"); np = st.text_input("Mật khẩu", type="password", key="r_p")
                nn = st.text_input("Họ tên", key="r_n"); ne = st.text_input("Email", key="r_e")
                if st.button("TIẾP THEO ➡️", use_container_width=True):
                    if nu and np and nn and ne: 
                        st.session_state.saved_u = nu; st.session_state.saved_p = np; st.session_state.saved_n = nn; st.session_state.saved_e = ne; st.session_state.reg_step = 2; st.rerun()
                    else: st.warning("Điền đủ thông tin!")
            elif st.session_state.reg_step == 2:
                st.markdown("##### 2. CHỌN GÓI")
                packages = {"1 Tháng": 200000, "3 Tháng": 500000, "6 Tháng": 900000, "1 Năm (VIP)": 1500000}
                pkg_choice = st.radio("Chọn gói:", list(packages.keys()))
                st.metric("THANH TOÁN:", f"{packages[pkg_choice]:,} VNĐ")
                c1, c2 = st.columns(2)
                if c1.button("⬅️ QUAY LẠI"): st.session_state.reg_step = 1; st.rerun()
                if c2.button("XÁC NHẬN ➡️", type="primary"):
                    ok, msg = register_user(st.session_state.saved_u, st.session_state.saved_p, st.session_state.saved_n, st.session_state.saved_e, pkg_choice)
                    if ok:
                        st.session_state.final_money = packages[pkg_choice]; st.session_state.reg_step = 3
                        try: send_telegram(f"💰 KHÁCH MỚI: {st.session_state.saved_u} | {pkg_choice}")
                        except: pass
                        st.rerun()
                    else: st.error(msg)
            elif st.session_state.reg_step == 3:
                try: bank_id = st.secrets["bank"]["id"]; acc_no = st.secrets["bank"]["account_no"]; acc_name = st.secrets["bank"]["account_name"]
                except: bank_id = "MB"; acc_no = "0000000000"; acc_name = "DEMO"
                amount = st.session_state.final_money; content = f"KICH HOAT {st.session_state.saved_u}"
                qr_url = f"https://img.vietqr.io/image/{bank_id}-{acc_no}-compact.jpg?amount={amount}&addInfo={content}&accountName={acc_name}"
                st.success("ĐĂNG KÝ THÀNH CÔNG!"); st.image(qr_url, caption="Quét mã thanh toán", width=300)
                st.info("Vui lòng đợi 1-5 phút để hệ thống kích hoạt."); 
                if st.button("VỀ TRANG CHỦ"): st.session_state.reg_step = 1; st.rerun()

else:
    user = st.session_state.user_info
    TRAINER_ID = int(user['id'])
    IS_ADMIN = (user['username'] == 'admin')
    
    default_inputs = {"name_in":"", "phone_in":"", "age_in":0, "height_in":0, "weight_in":0.0, "bf_in":0.0, "pkg_in":"", "dur_in":1, "price_in":0, "gender_in":"Nam", "act_in":"Light", "goal_in":"Tăng cân", "level_in":"🔰 Beginner / Intermediate"}
    for k,v in default_inputs.items():
        if k not in st.session_state: st.session_state[k] = v

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/8847/8847419.png", width=80)
        st.markdown(f"### 👤 {user['full_name']}")
        if IS_ADMIN: st.info("🔰 DOANH CHỦ SAAS")
        else:
            if user['expiry_date']:
                days = (pd.to_datetime(user['expiry_date']) - datetime.now()).days
                st.caption(f"⏳ Hạn dùng: {days} ngày" if days > 0 else "⚠️ Đã hết hạn")
            else: st.warning("Chưa kích hoạt")
        
        st.markdown("---")
        if IS_ADMIN: menu = st.radio("QUẢN TRỊ", ["📊 DOANH CHỦ DASHBOARD", "🔧 QUẢN LÝ USER", "💵 TÀI CHÍNH (HLV)", "👥 HỌC VIÊN (HLV)", "➕ THÊM MỚI"])
        else: menu = st.radio("MENU", ["🏠 TỔNG QUAN", "👥 HỌC VIÊN", "➕ THÊM MỚI", "💵 TÀI CHÍNH"])
        if st.button("Đăng xuất"): st.session_state.logged_in = False; st.rerun()

    # =========================================================================
    # 📊 DASHBOARD SAAS (BI)
    # =========================================================================
    if menu == "📊 DOANH CHỦ DASHBOARD" and IS_ADMIN:
        st.markdown(f"<div class='main-logo'>DOANH SỐ & TĂNG TRƯỞNG</div>", unsafe_allow_html=True)
        raw_users = run_query("users")
        if not raw_users.empty:
            df_users = raw_users[raw_users['username'] != 'admin'].copy()
            
            def process_smart_data(row):
                money, pk_name, months = parse_revenue_logic(row['full_name'])
                if 'created_at' in row and row['created_at'] and pd.notna(row['created_at']): start = pd.to_datetime(row['created_at'])
                elif row['expiry_date']: start = pd.to_datetime(row['expiry_date']) - timedelta(days=months*30)
                else: start = datetime.now()
                return money, pk_name, start

            if not df_users.empty:
                computed = df_users.apply(process_smart_data, axis=1, result_type='expand')
                df_users['Revenue'], df_users['Package'], df_users['Start_Date'] = computed[0], computed[1], computed[2]
                df_users['Month_Sort'] = df_users['Start_Date'].dt.strftime('%Y-%m')

                tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 TỔNG QUAN", "📅 BÁO CÁO THÁNG", "📦 HIỆU QUẢ GÓI", "🎯 MỤC TIÊU", "📄 DỮ LIỆU GỐC"])

                with tab1:
                    today = datetime.now().date()
                    rev_today = df_users[df_users['Start_Date'].dt.date == today]['Revenue'].sum()
                    rev_total = df_users['Revenue'].sum()
                    m1, m2 = st.columns(2)
                    m1.metric("HÔM NAY", f"{rev_today:,.0f} đ"); m2.metric("TỔNG TRỌN ĐỜI", f"{rev_total:,.0f} đ")
                    df_trend = df_users.groupby(df_users['Start_Date'].dt.date)['Revenue'].sum().reset_index()
                    if not df_trend.empty:
                        fig = px.bar(df_trend, x='Start_Date', y='Revenue', color_discrete_sequence=['#FFD700'], title="Dòng tiền theo ngày")
                        st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    st.markdown("### 🗓️ SỔ CÁI CHI TIẾT (12 THÁNG)")
                    current_year = datetime.now().year
                    for m in range(1, 13):
                        month_key = f"{current_year}-{m:02d}"
                        df_month = df_users[df_users['Month_Sort'] == month_key].copy()
                        total_rev_month = df_month['Revenue'].sum()
                        icon = "✅" if total_rev_month > 0 else "⚪"
                        with st.expander(f"{icon} Tháng {m:02d} - Doanh thu: {total_rev_month:,.0f} VNĐ ({len(df_month)} Đơn)"):
                            if not df_month.empty:
                                df_month = df_month.sort_values(by='Start_Date')
                                df_detail = df_month[['Start_Date', 'full_name', 'Package', 'Revenue']].copy()
                                df_detail['Ngày'] = df_detail['Start_Date'].dt.strftime('%d/%m')
                                df_detail['Giờ'] = df_detail['Start_Date'].dt.strftime('%H:%M')
                                df_detail['Số Tiền'] = df_detail['Revenue'].apply(lambda x: f"{x:,.0f}")
                                st.dataframe(df_detail[['Ngày', 'Giờ', 'full_name', 'Package', 'Số Tiền']], use_container_width=True, hide_index=True)
                                st.caption(f"👉 Tổng cộng Tháng {m}: {total_rev_month:,.0f} VNĐ")
                            else: st.info("Trống.")

                with tab3:
                    pkg_count = df_users['Package'].value_counts().reset_index()
                    pkg_count.columns = ['Gói', 'Số lượng']
                    if not pkg_count.empty: st.plotly_chart(px.pie(pkg_count, values='Số lượng', names='Gói', hole=0.4), use_container_width=True)

                with tab4:
                    target = st.number_input("Mục tiêu tháng:", value=20000000, step=1000000)
                    this_month = datetime.now().strftime('%Y-%m')
                    actual = df_users[df_users['Month_Sort'] == this_month]['Revenue'].sum()
                    st.progress(min(actual/target, 1.0))
                    st.metric("Đã đạt", f"{actual:,.0f} / {target:,.0f} VNĐ")

                with tab5:
                    col_f, col_d = st.columns([3, 1])
                    sel_f = col_f.selectbox("📅 Lọc:", ["Tất cả"] + [f"Tháng {i}" for i in range(1, 13)])
                    df_ex = df_users[['Start_Date', 'username', 'full_name', 'Package', 'Revenue', 'Month_Sort']].copy()
                    if sel_f != "Tất cả":
                        df_ex = df_ex[df_ex['Month_Sort'] == f"{datetime.now().year}-{int(sel_f.split(' ')[1]):02d}"]
                    df_ex['Start_Date'] = df_ex['Start_Date'].dt.strftime('%Y-%m-%d')
                    st.dataframe(df_ex[['Start_Date', 'username', 'full_name', 'Package', 'Revenue']], use_container_width=True, hide_index=True)
            else: st.info("Trống.")
        else: st.info("Database trống.")

    # =========================================================================
    # 🔧 QUẢN LÝ USER (SAAS)
    # =========================================================================
    elif menu == "🔧 QUẢN LÝ USER" and IS_ADMIN:
        st.markdown(f"<div class='main-logo'>QUẢN LÝ USER</div>", unsafe_allow_html=True)
        raw = run_query("users")
        if not raw.empty:
            df = raw[raw['username'] != 'admin'].copy()
            if 'note' not in df.columns: df['note'] = "" 
            c_table, c_edit = st.columns([1.5, 1])
            with c_table:
                st.subheader("Danh sách User")
                event = st.dataframe(df[['username', 'full_name', 'is_active', 'note']], use_container_width=True, height=500, selection_mode="single-row", on_select="rerun")
            with c_edit:
                st.subheader("🛠️ Chỉnh sửa / Xóa")
                if event.selection.rows:
                    idx = event.selection.rows[0]; user_data = df.iloc[idx]; sel_u = user_data['username']
                    st.info(f"Đang chọn: **{sel_u}**")
                    with st.form("edit_form_v60"):
                        new_name = st.text_input("Họ tên & Gói:", value=str(user_data['full_name']))
                        new_note = st.text_area("Ghi chú (Note):", value=str(user_data['note']) if pd.notna(user_data['note']) else "")
                        curr_exp = user_data['expiry_date']
                        new_exp = st.date_input("Hạn dùng:", value=pd.to_datetime(curr_exp) if pd.notna(curr_exp) else datetime.now())
                        new_active = st.checkbox("Active (Đã TT)", value=bool(user_data['is_active']))
                        c_u, c_d = st.columns(2)
                        if c_u.form_submit_button("💾 LƯU"):
                            update_data("users", {"full_name": new_name, "note": new_note, "expiry_date": str(new_exp), "is_active": new_active}, "username", sel_u)
                            st.success("Xong!"); time.sleep(0.5); st.rerun()
                        if c_d.form_submit_button("🗑️ XÓA SẠCH", type="primary"):
                            ok, msg = delete_user_force(sel_u)
                            if ok: st.success(msg); time.sleep(1); st.rerun()
                            else: st.error(msg)
                else: st.info("👈 Hãy chọn một dòng bên trái.")
        else: st.info("Trống.")

    # =========================================================================
    # 💵 TÀI CHÍNH HLV (PERSONAL REVENUE - V61)
    # =========================================================================
    elif (menu == "🏠 TỔNG QUAN") or (menu == "💵 TÀI CHÍNH (HLV)"):
        st.markdown(f"<div class='main-logo'>DASHBOARD HLV</div>", unsafe_allow_html=True)
        clients = run_query("clients", filter_col="trainer_id", filter_val=TRAINER_ID)
        
        if not clients.empty:
            k1, k2, k3 = st.columns(3)
            k1.markdown(f"<div class='css-card' style='text-align:center'><h2>{len(clients)}</h2><p>HỌC VIÊN</p></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='css-card' style='text-align:center'><h2>Active</h2><p>TRẠNG THÁI</p></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='css-card' style='text-align:center'><h2>{clients['price'].sum():,}</h2><p>DOANH THU</p></div>", unsafe_allow_html=True)
            
            st.divider()
            st.markdown("### 📋 DANH SÁCH HỢP ĐỒNG (HỌC VIÊN)")
            # Interactive Table để Xóa nhanh
            client_event = st.dataframe(
                clients[['name', 'package_name', 'price', 'start_date']], 
                use_container_width=True, 
                selection_mode="single-row", 
                on_select="rerun"
            )
            
            if client_event.selection.rows:
                idx_c = client_event.selection.rows[0]
                sel_client = clients.iloc[idx_c]
                st.warning(f"Bạn đang chọn học viên: **{sel_client['name']}**")
                if st.button("🗑️ XÓA HỢP ĐỒNG NÀY", type="primary"):
                    delete_client_data(sel_client['id'])
                    st.success("Đã xóa!"); time.sleep(0.5); st.rerun()
        else: st.info("Chưa có dữ liệu.")

    # =========================================================================
    # 👥 HỌC VIÊN (HLV) - V61 (CÓ NÚT XÓA)
    # =========================================================================
    elif menu == "👥 HỌC VIÊN (HLV)" or menu == "👥 HỌC VIÊN":
        clients = run_query("clients", filter_col="trainer_id", filter_val=TRAINER_ID)
        if not clients.empty:
            c_sel, _ = st.columns([1,2]); c_name = c_sel.selectbox("CHỌN HỌC VIÊN:", clients['name'].tolist())
            client = clients[clients['name'] == c_name].iloc[0]; cid = int(client['id'])
            
            st.markdown(f"### {client['name']} - {client['level']}")
            
            t1, t2, t3, t4, t5 = st.tabs(["MEAL PLAN", "CHECK-IN", "TIẾN ĐỘ", "CÀI ĐẶT", "⚙️ QUẢN LÝ"])
            
            with t1:
                # Logic Meal Plan (Rút gọn)
                plan = {}
                try:
                    if "Professional" in client['level']:
                        goal_map = {"Tăng cân": "Bulking", "Giảm mỡ": "Cutting", "Cải thiện sức khỏe": "Maintain"}
                        safe_goal = goal_map.get(client['goal'], client['goal'])
                        f_ratio = JP_FORMULAS[client['gender']][safe_goal][client['activity']]
                        w = client['start_weight']
                        plan = {'train': {'p': int(w*f_ratio['train']['p']), 'c': int(w*f_ratio['train']['c']), 'f': int(w*f_ratio['train']['f'])}, 'rest': {'p': int(w*f_ratio['rest']['p']), 'c': int(w*f_ratio['rest']['c']), 'f': int(w*f_ratio['rest']['f'])}}
                        plan['train']['cal'] = plan['train']['p']*4 + plan['train']['c']*4 + plan['train']['f']*9
                        plan['rest']['cal'] = plan['rest']['p']*4 + plan['rest']['c']*4 + plan['rest']['f']*9
                    else:
                        cal_base, p, c, f = calc_basic(client['start_weight'], client['height'], client['age'], client['gender'], client['activity'], client['goal'])
                        plan = {'train': {'p': p, 'c': int(c*1.1), 'f': f, 'cal': int(cal_base*1.05)}, 'rest': {'p': p, 'c': int(c*0.9), 'f': f, 'cal': int(cal_base*0.95)}}
                except: pass
                if plan:
                    c1, c2 = st.columns(2)
                    with c1: st.plotly_chart(draw_donut(plan['train']['p'], plan['train']['c'], plan['train']['f'], plan['train']['cal']), use_container_width=True); st.table(make_meal_df(plan['train']['p'], plan['train']['c'], plan['train']['f'], 'train'))
                    with c2: st.plotly_chart(draw_donut(plan['rest']['p'], plan['rest']['c'], plan['rest']['f'], plan['rest']['cal']), use_container_width=True); st.table(make_meal_df(plan['rest']['p'], plan['rest']['c'], plan['rest']['f'], 'rest'))

            with t2:
                with st.form("chk"):
                    d = st.date_input("Ngày"); w = st.number_input("Cân nặng")
                    if st.form_submit_button("LƯU"): insert_data("checkins", {"trainer_id": TRAINER_ID, "client_id": cid, "date": str(d), "weight": w}); st.rerun()
                st.dataframe(run_query("checkins", filter_col="client_id", filter_val=cid))
            with t3:
                logs = run_query("checkins", filter_col="client_id", filter_val=cid)
                if not logs.empty: st.plotly_chart(px.line(logs, x='date', y='weight'), use_container_width=True)
            
            with t5: # TAB QUẢN LÝ (XÓA HỌC VIÊN)
                st.error("⚠️ Vùng nguy hiểm")
                st.write(f"Bạn có chắc muốn xóa học viên **{client['name']}** không? Hành động này không thể hoàn tác.")
                if st.button("🗑️ XÓA VĨNH VIỄN HỌC VIÊN NÀY", type="primary"):
                    if delete_client_data(cid):
                        st.success("Đã xóa học viên!"); time.sleep(1); st.rerun()
                    else: st.error("Lỗi xóa!")

    elif menu == "➕ THÊM MỚI":
        st.markdown("### 📝 HỒ SƠ KHÁCH HÀNG")
        with st.form("new_c"):
            n = st.text_input("Họ tên"); p = st.text_input("SĐT"); g = st.selectbox("Giới tính", ["Nam", "Nữ"])
            h = st.number_input("Cao (cm)"); w = st.number_input("Nặng (kg)"); pkg = st.text_input("Gói"); pr = st.number_input("Giá")
            if st.form_submit_button("LƯU HỒ SƠ"):
                insert_data("clients", {"trainer_id": TRAINER_ID, "name": n, "phone": p, "gender": g, "height": h, "start_weight": w, "package_name": pkg, "price": pr, "start_date": datetime.now().strftime('%Y-%m-%d'), "status": "Active"})
                st.success("Đã lưu!"); st.rerun()

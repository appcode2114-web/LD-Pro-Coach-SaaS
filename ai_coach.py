import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import bcrypt
import time
import requests
from datetime import datetime, timedelta
from supabase import create_client, Client

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (V43 - ADMIN PRO)
# ==========================================
st.set_page_config(page_title="LD PRO COACH - System", layout="wide", page_icon="🦁")

# --- KẾT NỐI SUPABASE ---
try:
    SUPABASE_URL = st.secrets["supabase"]["URL"]
    SUPABASE_KEY = st.secrets["supabase"]["KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ Lỗi cấu hình Secrets: Vui lòng kiểm tra lại URL và KEY trong Streamlit Cloud."); st.stop()

# ==========================================
# 2. HÀM XỬ LÝ (CORE LOGIC)
# ==========================================

def send_telegram(message):
    """Gửi thông báo về điện thoại Admin khi có khách đăng ký"""
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

def login_user(username, password):
    df = run_query("users", filter_col="username", filter_val=username)
    if not df.empty:
        user = df.iloc[0]
        # LOGIC: CHẶN NẾU CHƯA ĐƯỢC ADMIN KÍCH HOẠT
        is_active = bool(user.get('is_active', False))
        
        if not is_active: 
            return "LOCKED" 
            
        try:
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')): 
                return user.to_dict()
        except:
            if password == user['password_hash']: 
                return user.to_dict()
    return None

def register_user(u, p, n, e, package_info):
    check = run_query("users", select="id", filter_col="username", filter_val=u)
    if not check.empty: return False, "Tên đăng nhập đã tồn tại"
    
    hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    full_name_info = f"{n} ({package_info})"
    
    ok, msg = insert_data("users", {
        "username": u, "password_hash": hashed, 
        "full_name": full_name_info, 
        "email": e, "expiry_date": None, "is_active": False
    })
    return ok, ""

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
    fig = go.Figure(data=[go.Pie(labels=['Pro', 'Carb', 'Fat'], values=[p*4, c*4, f*9], hole=.65, marker=dict(colors=['#00BFFF', '#FF4500', '#FFD700']), textinfo='percent', textposition='inside', textfont=dict(size=14, color='black'))])
    fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=150, paper_bgcolor='rgba(0,0,0,0)', annotations=[dict(text=f"<span style='font-size:24px; color:#FFF; font-weight:bold; font-family:Teko'>{cal}</span>", x=0.5, y=0.5, font_size=20, showarrow=False)])
    return fig

# ==========================================
# 3. CSS GIAO DIỆN
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Teko:wght@300;500;700&family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background: radial-gradient(circle at 50% 10%, #1a0505 0%, #000000 90%); color: #E0E0E0; font-family: 'Montserrat', sans-serif; }
    .main-logo { font-family: 'Teko', sans-serif; font-size: 70px; font-weight: 700; text-align: center; background: linear-gradient(180deg, #FFD700 10%, #B8860B 60%, #8B6914 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; letter-spacing: 4px; margin-bottom: 5px; filter: drop-shadow(0px 2px 0px #000); }
    
    div[data-baseweb="input"], div[data-baseweb="select"] > div { background-color: #F5F5F5 !important; border: 1px solid #D1D1D1 !important; border-radius: 8px !important; color: #111 !important; }
    input[class*="st-"], div[data-baseweb="select"] span { color: #111 !important; font-weight: 600; }
    
    .css-card { background-color: rgba(20, 20, 20, 0.6); backdrop-filter: blur(10px); border: 1px solid #222; border-left: 3px solid #D4AF37; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
    .stButton > button { background: linear-gradient(90deg, #8B0000 0%, #C00000 100%); color: white; font-family: 'Teko', sans-serif; font-size: 22px; letter-spacing: 1px; border: none; border-radius: 6px; padding: 10px 0; width: 100%; transition: 0.3s; }
    .stButton > button:hover { background: linear-gradient(90deg, #C00000 0%, #FF0000 100%); box-shadow: 0 4px 15px rgba(255, 0, 0, 0.4); }
    
    section[data-testid="stSidebar"] { background-color: #080808; border-right: 1px solid #222; }
    section[data-testid="stSidebar"] * { color: #EEE !important; }

    div[data-testid="stTable"] th { background-color: #D4AF37 !important; color: #000000 !important; font-family: 'Teko', sans-serif !important; font-size: 20px !important; text-align: center !important; }
    div[data-testid="stTable"] td { background-color: #222 !important; color: #FFFFFF !important; border-bottom: 1px solid #444 !important; }
    
    /* STYLE CHO GÓI CƯỚC */
    div[role="radiogroup"] label { border: 1px solid #444; padding: 10px; border-radius: 5px; background: #222; margin-bottom: 5px; }
    div[role="radiogroup"] label[data-checked="true"] { border-color: #D4AF37; background: #333; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. LUỒNG CHÍNH (MAIN FLOW)
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
        
        # TAB 1: ĐĂNG NHẬP
        with tab1:
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("🚀 ĐĂNG NHẬP", type="primary", use_container_width=True):
                    res = login_user(u, p)
                    if isinstance(res, str) and res == "LOCKED":
                        st.warning("🔒 Tài khoản đang chờ duyệt thanh toán! Vui lòng liên hệ Admin.")
                    elif res:
                        st.session_state.logged_in = True
                        st.session_state.user_info = res
                        st.success("Đăng nhập thành công!"); time.sleep(0.5); st.rerun()
                    else: st.error("Sai thông tin đăng nhập!")
        
        # TAB 2: ĐĂNG KÝ & THANH TOÁN QR
        with tab2:
            if 'reg_step' not in st.session_state: st.session_state.reg_step = 1
            
            # BƯỚC 1: NHẬP THÔNG TIN
            if st.session_state.reg_step == 1:
                st.markdown("##### 1. THÔNG TIN CÁ NHÂN")
                nu = st.text_input("Tên đăng nhập (Viết liền không dấu)", key="r_u")
                np = st.text_input("Mật khẩu", type="password", key="r_p")
                nn = st.text_input("Họ và tên", key="r_n")
                ne = st.text_input("Gmail (Để khôi phục tài khoản)", key="r_e")
                
                if st.button("TIẾP THEO ➡️", use_container_width=True):
                    if nu and np and nn and ne: 
                        st.session_state.saved_u = nu
                        st.session_state.saved_p = np
                        st.session_state.saved_n = nn
                        st.session_state.saved_e = ne
                        st.session_state.reg_step = 2; st.rerun()
                    else: st.warning("Vui lòng nhập đủ thông tin!")

            # BƯỚC 2: CHỌN GÓI & XÁC NHẬN
            elif st.session_state.reg_step == 2:
                st.markdown("##### 2. CHỌN GÓI SỬ DỤNG")
                packages = {
                    "1 Tháng": 200000,
                    "3 Tháng": 500000,
                    "6 Tháng": 900000,
                    "1 Năm (VIP)": 1500000
                }
                pkg_choice = st.radio("Chọn gói phù hợp:", list(packages.keys()))
                st.metric("SỐ TIỀN CẦN THANH TOÁN:", f"{packages[pkg_choice]:,} VNĐ")
                
                c_back, c_next = st.columns(2)
                with c_back: 
                    if st.button("⬅️ QUAY LẠI"): st.session_state.reg_step = 1; st.rerun()
                with c_next:
                    if st.button("ĐĂNG KÝ & THANH TOÁN ➡️", type="primary"):
                        ok, msg = register_user(
                            st.session_state.saved_u, 
                            st.session_state.saved_p, 
                            st.session_state.saved_n, 
                            st.session_state.saved_e, 
                            pkg_choice
                        )
                        if ok:
                            st.session_state.final_money = packages[pkg_choice]
                            st.session_state.reg_step = 3
                            try:
                                msg_tele = f"💰 KHÁCH MỚI!\nUser: {st.session_state.saved_u}\nTên: {st.session_state.saved_n}\nGói: {pkg_choice}\nTiền: {packages[pkg_choice]:,}đ"
                                send_telegram(msg_tele)
                            except: pass
                            st.rerun()
                        else: st.error(msg)

            # BƯỚC 3: QUÉT MÃ QR
            elif st.session_state.reg_step == 3:
                try:
                    bank_id = st.secrets["bank"]["id"]
                    acc_no = st.secrets["bank"]["account_no"]
                    acc_name = st.secrets["bank"]["account_name"]
                except: 
                    bank_id = "MB"; acc_no = "0000000000"; acc_name = "DEMO"
                
                amount = st.session_state.final_money
                content = f"KICH HOAT {st.session_state.saved_u}"
                
                qr_url = f"https://img.vietqr.io/image/{bank_id}-{acc_no}-compact.jpg?amount={amount}&addInfo={content}&accountName={acc_name}"
                
                st.success("✅ ĐĂNG KÝ THÀNH CÔNG! VUI LÒNG THANH TOÁN ĐỂ KÍCH HOẠT.")
                c_img, _ = st.columns([1,1])
                with c_img:
                    st.image(qr_url, caption="Mở App Ngân hàng quét mã này", width=300)
                
                st.info("⚡ Hệ thống thanh toán tự động. Sau khi chuyển khoản, vui lòng đợi 1-5 phút để hệ thống xác nhận và kích hoạt tài khoản.")
                
                if st.button("VỀ TRANG CHỦ"): 
                    st.session_state.reg_step = 1; st.rerun()

else:
    # --- PHẦN GIAO DIỆN CHÍNH (SAU KHI LOGIN) ---
    user = st.session_state.user_info
    TRAINER_ID = int(user['id'])
    IS_ADMIN = (user['username'] == 'admin')
    
    default_inputs = {"name_in":"", "phone_in":"", "age_in":0, "height_in":0, "weight_in":0.0, "bf_in":0.0, "pkg_in":"", "dur_in":1, "price_in":0, "gender_in":"Nam", "act_in":"Light", "goal_in":"Tăng cân", "level_in":"🔰 Beginner / Intermediate"}
    for k,v in default_inputs.items():
        if k not in st.session_state: st.session_state[k] = v

    # --- SIDEBAR (ĐÃ TÁCH BIỆT ADMIN) ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/8847/8847419.png", width=80)
        st.markdown(f"### 👤 {user['full_name']}")
        
        # LOGIC RIÊNG CHO ADMIN (KHÔNG HIỆN NGÀY)
        if IS_ADMIN:
            st.info("🔰 QUẢN TRỊ VIÊN") # Thẻ Admin riêng biệt
        else:
            # LOGIC CHO USER THƯỜNG (HIỆN NGÀY)
            if user['expiry_date']:
                days_left = (pd.to_datetime(user['expiry_date']) - datetime.now()).days
                if days_left > 0:
                    st.caption(f"⏳ Hạn dùng: {days_left} ngày")
                else:
                    st.error("⚠️ Đã hết hạn")
            else:
                st.warning("Chưa kích hoạt")

        if IS_ADMIN:
            st.markdown("---")
            # MENU RIÊNG CHO ADMIN
            menu = st.radio("MENU QUẢN TRỊ", ["🏠 TỔNG QUAN", "👥 HỌC VIÊN", "➕ THÊM MỚI", "💵 TÀI CHÍNH", "🔧 DUYỆT THANH TOÁN"])
        else:
            st.markdown("---")
            # MENU CHO USER THƯỜNG
            menu = st.radio("MENU", ["🏠 TỔNG QUAN", "👥 HỌC VIÊN", "➕ THÊM MỚI", "💵 TÀI CHÍNH"])

        if st.button("Đăng xuất"): st.session_state.logged_in = False; st.rerun()

    # --- 1. ADMIN PANEL (DUYỆT THANH TOÁN) ---
    if menu == "🔧 DUYỆT THANH TOÁN" and IS_ADMIN:
        st.markdown(f"<div class='main-logo'>DUYỆT THANH TOÁN</div>", unsafe_allow_html=True)
        # Chỉ hiện user chưa active lên đầu
        all_users = run_query("users", order_by=("is_active", "asc"))
        st.dataframe(all_users[['id', 'username', 'full_name', 'email', 'is_active', 'expiry_date']], use_container_width=True)
        
        st.info("💡 Mẹo: Nhìn cột 'full_name' để biết khách chọn gói nào (VD: Nguyen A (3 Tháng))")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.form("admin_act"):
                st.subheader("KÍCH HOẠT TÀI KHOẢN")
                u_sel = st.selectbox("Chọn user:", all_users['username'].tolist())
                
                # Logic hint
                sel_row = all_users[all_users['username']==u_sel].iloc[0]
                st.caption(f"Thông tin gói: {sel_row['full_name']}")
                
                months_add = st.selectbox("Gia hạn thêm:", [1, 3, 6, 12], index=0)
                is_active = st.checkbox("✅ ĐÃ THANH TOÁN (ACTIVE)", value=True)
                
                if st.form_submit_button("XÁC NHẬN DUYỆT"):
                    curr = sel_row['expiry_date']
                    if pd.isna(curr): start_d = datetime.now()
                    else: start_d = pd.to_datetime(curr)
                    
                    new_exp = (start_d + timedelta(days=months_add*30)).strftime('%Y-%m-%d')
                    update_data("users", {"expiry_date": new_exp, "is_active": is_active}, "username", u_sel)
                    st.success(f"Đã duyệt {u_sel}! Hạn mới: {new_exp}"); time.sleep(1); st.rerun()

        with c2:
             with st.form("admin_rs"):
                st.subheader("CẤP LẠI MẬT KHẨU")
                u_rs = st.selectbox("User:", all_users['username'].tolist(), key="sel_rs")
                new_p = st.text_input("Mật khẩu mới")
                if st.form_submit_button("ĐỔI PASS"):
                    if new_p:
                        h = bcrypt.hashpw(new_p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        update_data("users", {"password_hash": h}, "username", u_rs)
                        st.success("Xong!"); time.sleep(1); st.rerun()

    # --- 2. TỔNG QUAN ---
    elif menu == "🏠 TỔNG QUAN":
        st.markdown(f"<div class='main-logo'>DASHBOARD</div>", unsafe_allow_html=True)
        clients = run_query("clients", filter_col="trainer_id", filter_val=TRAINER_ID)
        if not clients.empty:
            k1, k2, k3 = st.columns(3)
            k1.markdown(f"<div class='css-card' style='text-align:center'><h2 style='color:#D4AF37; margin:0'>{len(clients)}</h2><p style='color:#888'>HỌC VIÊN</p></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='css-card' style='text-align:center; border-color:#FF4B4B'><h2 style='color:#FF4B4B; margin:0'>Check</h2><p style='color:#888'>CẦN CHECK-IN</p></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='css-card' style='text-align:center; border-color:#FFF'><h2 style='color:#FFF; margin:0'>Active</h2><p style='color:#888'>TRẠNG THÁI</p></div>", unsafe_allow_html=True)
            st.dataframe(clients[['name', 'package_name', 'end_date', 'status']], use_container_width=True)
        else: st.info("Chưa có dữ liệu.")

    # --- 3. HỌC VIÊN ---
    elif menu == "👥 HỌC VIÊN":
        clients = run_query("clients", filter_col="trainer_id", filter_val=TRAINER_ID)
        if not clients.empty:
            c_sel, _ = st.columns([1,2])
            with c_sel: c_name = st.selectbox("CHỌN HỌC VIÊN:", clients['name'].tolist())
            client = clients[clients['name'] == c_name].iloc[0]
            cid = int(client['id'])
            st.markdown(f"""<div class="css-card" style="border-top: 4px solid #D4AF37"><h1 style="color:#FFF; margin:0">{client['name']}</h1><span style="color:#D4AF37">{client['level']}</span></div>""", unsafe_allow_html=True)
            
            t1, t2, t3, t4 = st.tabs(["MEAL PLAN", "CHECK-IN", "TIẾN ĐỘ", "CÀI ĐẶT"])
            with t1:
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
                    with c1:
                        st.markdown('<div class="css-card" style="border-left: 4px solid #00BFFF"><h3 style="text-align:center; color:#00BFFF">TRAINING DAY</h3>', unsafe_allow_html=True)
                        st.plotly_chart(draw_donut(plan['train']['p'], plan['train']['c'], plan['train']['f'], plan['train']['cal']), use_container_width=True)
                        st.table(make_meal_df(plan['train']['p'], plan['train']['c'], plan['train']['f'], 'train'))
                        st.markdown('</div>', unsafe_allow_html=True)
                    with c2:
                        st.markdown('<div class="css-card" style="border-left: 4px solid #777"><h3 style="text-align:center; color:#AAA; font-family:Teko">REST DAY</h3>', unsafe_allow_html=True)
                        st.plotly_chart(draw_donut(plan['rest']['p'], plan['rest']['c'], plan['rest']['f'], plan['rest']['cal']), use_container_width=True)
                        st.table(make_meal_df(plan['rest']['p'], plan['rest']['c'], plan['rest']['f'], 'rest'))
                        st.markdown('</div>', unsafe_allow_html=True)

            with t2:
                with st.form("chk"):
                    d = st.date_input("Ngày"); w = st.number_input("Cân nặng (kg)", value=client['start_weight']); cm = st.checkbox("Tuân thủ ăn uống"); cw = st.checkbox("Tuân thủ tập luyện"); nt = st.text_input("Ghi chú")
                    if st.form_submit_button("LƯU CHECK-IN", type="primary"):
                        insert_data("checkins", {"trainer_id": TRAINER_ID, "client_id": cid, "date": str(d), "weight": w, "compliance_meal": cm, "compliance_workout": cw, "notes": nt})
                        st.success("Đã lưu!"); st.rerun()
                logs = run_query("checkins", filter_col="client_id", filter_val=cid, order_by=("date", "desc"))
                if not logs.empty: st.dataframe(logs)

            with t3:
                logs = run_query("checkins", filter_col="client_id", filter_val=cid, order_by=("date", "asc"))
                if not logs.empty: fig = go.Figure(); fig.add_trace(go.Scatter(x=logs['date'], y=logs['weight'], mode='lines+markers', line=dict(color='#FFD700'))); st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")

    # --- 4. THÊM MỚI ---
    elif menu == "➕ THÊM MỚI":
        st.markdown("### 📝 HỒ SƠ KHÁCH HÀNG")
        with st.container():
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            level = st.radio("CẤP ĐỘ:", ["🔰 Beginner / Intermediate", "🏆 Professional Athlete"], horizontal=True, key="level_in")
            goal_options = ["Bulking", "Cutting", "Maintain"] if "Professional" in level else ["Tăng cân", "Giảm mỡ", "Cải thiện sức khỏe"]
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1: st.text_input("Họ tên", key="name_in"); st.text_input("SĐT", key="phone_in"); st.selectbox("Giới tính", ["Nam", "Nữ"], key="gender_in")
            with c2: st.number_input("Tuổi", min_value=0, key="age_in"); st.number_input("Chiều cao (cm)", min_value=0, key="height_in"); st.number_input("Cân nặng (kg)", min_value=0.0, key="weight_in")
            with c3: st.selectbox("Mức vận động", ["Light", "Moderate", "High"], key="act_in"); st.number_input("Bodyfat %", min_value=0.0, key="bf_in"); st.selectbox("MỤC TIÊU", goal_options, key="goal_in")
            st.divider()
            s1, s2, s3 = st.columns(3)
            with s1: st.text_input("Tên Gói Tập", key="pkg_in")
            with s2: st.number_input("Thời hạn (tháng)", min_value=1, key="dur_in")
            with s3: st.number_input("Giá trị HĐ (VNĐ)", min_value=0, step=500000, key="price_in")
            
            def save_client():
                if st.session_state.name_in:
                    end = (datetime.now() + timedelta(days=st.session_state.dur_in*30)).strftime('%Y-%m-%d')
                    start = datetime.now().strftime('%Y-%m-%d')
                    data = {"trainer_id": TRAINER_ID, "name": st.session_state.name_in, "phone": st.session_state.phone_in, "gender": st.session_state.gender_in, "age": st.session_state.age_in, "height": st.session_state.height_in, "start_weight": st.session_state.weight_in, "goal": st.session_state.goal_in, "activity": st.session_state.act_in, "bodyfat": st.session_state.bf_in, "level": st.session_state.level_in, "package_name": st.session_state.pkg_in, "duration_months": st.session_state.dur_in, "price": st.session_state.price_in, "start_date": start, "end_date": end, "status": 'Active'}
                    insert_data("clients", data)
                    for k in default_inputs: st.session_state[k] = default_inputs[k]
                    st.toast("Lưu thành công!", icon="🔥")
                else: st.error("Nhập tên!")
            st.button("🔥 LƯU HỒ SƠ & RESET", type="primary", use_container_width=True, on_click=save_client)
            st.markdown('</div>', unsafe_allow_html=True)

    # --- 5. TÀI CHÍNH ---
    elif menu == "💵 TÀI CHÍNH":
        st.markdown("### 💰 DOANH THU")
        df = run_query("clients", filter_col="trainer_id", filter_val=TRAINER_ID)
        if not df.empty: st.metric("TỔNG", f"{df['price'].sum():,} VNĐ"); st.dataframe(df[['name', 'package_name', 'start_date', 'price']], use_container_width=True)
        else: st.info("Chưa có dữ liệu.")

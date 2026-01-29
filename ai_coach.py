import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sqlalchemy
from sqlalchemy import create_engine, text
import bcrypt
import time
from datetime import datetime, timedelta
import urllib.parse

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (AN TOÀN)
# ==========================================
st.set_page_config(page_title="LD PRO COACH - SaaS", layout="wide", page_icon="🦁")

# --- KẾT NỐI SUPABASE ---
try:
    db_secrets = st.secrets["connections"]["supabase"]
    safe_password = urllib.parse.quote_plus(db_secrets['password'])
    DB_URL = f"postgresql://{db_secrets['username']}:{safe_password}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['database']}"
except Exception as e:
    st.error("❌ Lỗi kết nối: Chưa có file .streamlit/secrets.toml hoặc sai thông tin.")
    st.stop()

@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

engine = get_engine()

def run_query(query, params=None):
    with engine.connect() as conn:
        if params: result = conn.execute(text(query), params)
        else: result = conn.execute(text(query))
        if query.strip().upper().startswith("SELECT"): return pd.DataFrame(result.fetchall(), columns=result.keys())
        conn.commit()
        return None

# ==========================================
# 2. CSS GIAO DIỆN (FIX HIỂN THỊ RÕ NÉT)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Teko:wght@300;500;700&family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background: radial-gradient(circle at 50% 10%, #1a0505 0%, #000000 90%); color: #E0E0E0; font-family: 'Montserrat', sans-serif; }
    .main-logo { font-family: 'Teko', sans-serif; font-size: 70px; font-weight: 700; text-align: center; background: linear-gradient(180deg, #FFD700 10%, #B8860B 60%, #8B6914 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; letter-spacing: 4px; margin-bottom: 5px; filter: drop-shadow(0px 2px 0px #000); }
    
    /* INPUT STYLE */
    div[data-baseweb="input"], div[data-baseweb="select"] > div { background-color: #F5F5F5 !important; border: 1px solid #D1D1D1 !important; border-radius: 8px !important; color: #111 !important; }
    input[class*="st-"], div[data-baseweb="select"] span { color: #111 !important; font-weight: 600; }
    div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within { border-color: #B8860B !important; box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2) !important; background-color: #FFF !important; }

    /* RADIO BUTTONS */
    div[role="radiogroup"] { display: flex; gap: 15px; width: 100%; }
    div[role="radiogroup"] label { flex: 1; background: linear-gradient(145deg, #1a1a1a, #0d0d0d) !important; border: 1px solid #333 !important; padding: 18px !important; border-radius: 8px !important; display: flex; justify-content: center; align-items: center; transition: 0.3s; }
    div[role="radiogroup"] label p { font-size: 15px; font-weight: 700; color: #888; }
    div[role="radiogroup"] label[data-checked="true"] { border-color: #FF0000 !important; background: #111 !important; }
    div[role="radiogroup"] label[data-checked="true"] p { color: #FFF !important; }

    /* CARD */
    .css-card { background-color: rgba(20, 20, 20, 0.6); backdrop-filter: blur(10px); border: 1px solid #222; border-left: 3px solid #D4AF37; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
    
    /* BUTTON */
    .stButton > button { background: linear-gradient(90deg, #8B0000 0%, #C00000 100%); color: white; font-family: 'Teko', sans-serif; font-size: 22px; letter-spacing: 1px; border: none; border-radius: 6px; padding: 10px 0; width: 100%; transition: 0.3s; }
    .stButton > button:hover { background: linear-gradient(90deg, #C00000 0%, #FF0000 100%); box-shadow: 0 4px 15px rgba(255, 0, 0, 0.4); }
    
    /* SIDEBAR */
    section[data-testid="stSidebar"] { background-color: #080808; border-right: 1px solid #222; }
    section[data-testid="stSidebar"] * { color: #EEE !important; }

    /* --- FIX TABLE STYLE (CHỮ TRẮNG RÕ RÀNG) --- */
    div[data-testid="stTable"] table { width: 100%; border-collapse: separate; border-spacing: 0; border: 1px solid #333; }
    div[data-testid="stTable"] th {
        background-color: #D4AF37 !important; color: #000000 !important;
        font-family: 'Teko', sans-serif !important; font-size: 20px !important;
        text-align: center !important; padding: 10px !important;
    }
    div[data-testid="stTable"] td {
        background-color: #222 !important; color: #FFFFFF !important;
        border-bottom: 1px solid #444 !important;
        font-family: 'Montserrat', sans-serif !important; font-weight: 600 !important; font-size: 15px !important;
    }
    div[data-testid="stTable"] tr:hover td { background-color: #333 !important; color: #FFD700 !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. HỆ THỐNG AUTH
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

def login_user(username, password):
    try:
        df = run_query("SELECT * FROM users WHERE username = :u", {"u": username})
        if not df.empty:
            user = df.iloc[0]
            # Nếu user bị khóa (is_active = False)
            if not user.get('is_active', True):
                st.error("🚫 Tài khoản này đã bị KHÓA. Vui lòng liên hệ Admin.")
                return None
            # Kiểm tra mật khẩu
            try:
                if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')): return user
            except:
                if password == user['password_hash']: return user # Fallback cho admin demo
    except Exception as e: st.error(e)
    return None

def register_user(u, p, n, e):
    try:
        check = run_query("SELECT id FROM users WHERE username = :u", {"u": u})
        if not check.empty: return False, "Tên đăng nhập đã tồn tại"
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        exp = (datetime.now() + pd.DateOffset(days=30)).strftime('%Y-%m-%d')
        run_query("INSERT INTO users (username, password_hash, full_name, email, expiry_date, is_active) VALUES (:u, :p, :n, :e, :ex, TRUE)",
                  {"u": u, "p": hashed, "n": n, "e": e, "ex": exp})
        return True, "Đăng ký thành công!"
    except Exception as err: return False, str(err)

# --- FORMULAS ---
JP_FORMULAS = {
    'Nam': {
        'Bulking': {'Light': {'train': {'p': 3.71, 'c': 4.78, 'f': 0.58}, 'rest': {'p': 3.25, 'c': 2.78, 'f': 1.44}}, 'Moderate': {'train': {'p': 4.07, 'c': 5.23, 'f': 0.35}, 'rest': {'p': 3.10, 'c': 3.10, 'f': 1.83}}, 'High': {'train': {'p': 4.25, 'c': 5.60, 'f': 0.50}, 'rest': {'p': 3.30, 'c': 3.50, 'f': 1.90}}},
        'Maintain': {'Light': {'train': {'p': 3.10, 'c': 3.98, 'f': 0.67}, 'rest': {'p': 3.10, 'c': 1.35, 'f': 0.94}}, 'Moderate': {'train': {'p': 3.38, 'c': 4.37, 'f': 0.85}, 'rest': {'p': 3.00, 'c': 2.58, 'f': 1.33}}, 'High': {'train': {'p': 3.60, 'c': 4.80, 'f': 1.00}, 'rest': {'p': 3.20, 'c': 3.00, 'f': 1.50}}},
        'Cutting': {'Light': {'train': {'p': 2.48, 'c': 3.18, 'f': 0.63}, 'rest': {'p': 2.78, 'c': 1.23, 'f': 0.96}}, 'Moderate': {'train': {'p': 2.71, 'c': 3.01, 'f': 0.70}, 'rest': {'p': 2.74, 'c': 2.05, 'f': 0.92}}, 'High': {'train': {'p': 2.90, 'c': 3.40, 'f': 0.80}, 'rest': {'p': 2.90, 'c': 2.30, 'f': 1.10}}}
    },
    'Nữ': {
        'Bulking': {'Light': {'train': {'p': 2.40, 'c': 3.50, 'f': 0.80}, 'rest': {'p': 2.40, 'c': 2.00, 'f': 1.00}}, 'Moderate': {'train': {'p': 2.60, 'c': 4.00, 'f': 0.70}, 'rest': {'p': 2.50, 'c': 2.50, 'f': 1.10}}, 'High': {'train': {'p': 2.80, 'c': 4.50, 'f': 0.80}, 'rest': {'p': 2.60, 'c': 3.00, 'f': 1.20}}},
        'Maintain': {'Light': {'train': {'p': 2.20, 'c': 3.00, 'f': 0.90}, 'rest': {'p': 2.20, 'c': 1.50, 'f': 1.00}}, 'Moderate': {'train': {'p': 2.40, 'c': 3.50, 'f': 0.85}, 'rest': {'p': 2.30, 'c': 2.00, 'f': 1.10}}, 'High': {'train': {'p': 2.50, 'c': 4.00, 'f': 1.00}, 'rest': {'p': 2.40, 'c': 2.50, 'f': 1.20}}},
        'Cutting': {'Light': {'train': {'p': 2.20, 'c': 2.00, 'f': 0.70}, 'rest': {'p': 2.20, 'c': 0.80, 'f': 0.90}}, 'Moderate': {'train': {'p': 2.40, 'c': 2.50, 'f': 0.70}, 'rest': {'p': 2.40, 'c': 1.20, 'f': 0.90}}, 'High': {'train': {'p': 2.50, 'c': 3.00, 'f': 0.80}, 'rest': {'p': 2.50, 'c': 1.50, 'f': 1.00}}}
    }
}

def calc_basic(w, h, a, g, act, goal):
    if w == 0 or h == 0: return 0, 0, 0, 0
    bmr = 10*w + 6.25*h - 5*a + 5 if g=='Nam' else 10*w + 6.25*h - 5*a - 161
    act_map = {'Light':1.375, 'Moderate':1.55, 'High':1.725}
    tdee = bmr * act_map.get(act, 1.375)
    target = tdee + 400 if "Tăng" in goal else (tdee if "Cải thiện" in goal else tdee - 400)
    p, c, f = (target*0.3)/4, (target*0.4)/4, (target*0.3)/9
    return int(target), int(p), int(c), int(f)

def make_meal_df(p, c, f, type_day):
    if type_day == 'train':
        data = [["Bữa 1 (Sáng)", 0, int(p*0.17), int(f*0.4), ""], ["Bữa 2 (Phụ)", int(c*0.25), int(p*0.16), 0, ""], ["PRE-WORKOUT", int(c*0.15), int(p*0.17), int(f*0.3), ""], ["POST-WORKOUT", int(c*0.45), int(p*0.17), 0, ""], ["Bữa 5", int(c*0.15), int(p*0.17), int(f*0.3), ""], ["Bữa 6", 0, int(p*0.16), 0, ""]]
    else:
        data = [["Bữa 1", 0, int(p*0.16), int(f*0.25), ""], ["Bữa 2", int(c*0.25), int(p*0.16), int(f*0.15), ""], ["Bữa 3", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 4", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 5", int(c*0.25), int(p*0.17), int(f*0.15), ""], ["Bữa 6", 0, int(p*0.17), int(f*0.15), ""]]
    return pd.DataFrame(data, columns=["BỮA", "CARB (g)", "PRO (g)", "FAT (g)", "GỢI Ý"])

def draw_donut(p, c, f, cal):
    # --- HIỆN % RÕ RÀNG ---
    fig = go.Figure(data=[go.Pie(
        labels=['Pro', 'Carb', 'Fat'], 
        values=[p*4, c*4, f*9], 
        hole=.65, 
        marker=dict(colors=['#00BFFF', '#FF4500', '#FFD700']), 
        textinfo='percent', # Hiện số %
        textposition='inside',
        textfont=dict(size=14, color='black') # Chữ đen dễ đọc
    )])
    fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=150, paper_bgcolor='rgba(0,0,0,0)', 
                      annotations=[dict(text=f"<span style='font-size:24px; color:#FFF; font-weight:bold; font-family:Teko'>{cal}</span>", x=0.5, y=0.5, font_size=20, showarrow=False)])
    return fig

# ==========================================
# 4. ĐIỀU HƯỚNG GIAO DIỆN
# ==========================================

if not st.session_state.logged_in:
    st.markdown("<div class='main-logo'>LD PRO COACH</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab1, tab2 = st.tabs(["ĐĂNG NHẬP", "ĐĂNG KÝ"])
        with tab1:
            with st.form("login"):
                u = st.text_input("Tên đăng nhập")
                p = st.text_input("Mật khẩu", type="password")
                if st.form_submit_button("🚀 ĐĂNG NHẬP", type="primary", use_container_width=True):
                    user = login_user(u, p)
                    if user is not None:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user
                        st.success("Thành công!"); time.sleep(0.5); st.rerun()
                    else: st.error("Sai thông tin hoặc tài khoản bị khóa!")
        with tab2:
            with st.form("reg"):
                nu = st.text_input("Username"); np = st.text_input("Password", type="password"); nn = st.text_input("Họ tên"); ne = st.text_input("Email")
                if st.form_submit_button("✨ ĐĂNG KÝ", use_container_width=True):
                    if nu and np:
                        ok, msg = register_user(nu, np, nn, ne)
                        if ok: st.success(msg)
                        else: st.error(msg)
                    else: st.warning("Nhập đủ thông tin!")

else:
    user = st.session_state.user_info
    TRAINER_ID = int(user['id'])
    
    # --- KIỂM TRA QUYỀN ADMIN (DỰA TRÊN TÊN ĐĂNG NHẬP) ---
    IS_ADMIN = (user['username'] == 'admin') 
    
    default_inputs = {"name_in":"", "phone_in":"", "age_in":0, "height_in":0, "weight_in":0.0, "bf_in":0.0, 
                      "pkg_in":"", "dur_in":1, "price_in":0, "gender_in":"Nam", "act_in":"Light", 
                      "goal_in":"Tăng cân", "level_in":"🔰 Beginner / Intermediate"}
    for k,v in default_inputs.items():
        if k not in st.session_state: st.session_state[k] = v

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/8847/8847419.png", width=80)
        st.markdown(f"### 👤 {user['full_name']}")
        st.caption(f"Hạn dùng: {user['expiry_date']}")
        
        # --- MENU ĐỘNG (ADMIN/USER) ---
        if IS_ADMIN:
            st.markdown("---")
            st.markdown("### 👑 SUPER ADMIN")
            # MENU CỦA ADMIN: THÊM DÒNG 'QUẢN TRỊ ADMIN'
            menu = st.radio("MENU ADMIN", ["🏠 TỔNG QUAN", "👥 HỌC VIÊN", "➕ THÊM MỚI", "💵 TÀI CHÍNH", "🔧 QUẢN TRỊ ADMIN"])
        else:
            st.markdown("---")
            # MENU NGƯỜI THƯỜNG
            menu = st.radio("MENU", ["🏠 TỔNG QUAN", "👥 HỌC VIÊN", "➕ THÊM MỚI", "💵 TÀI CHÍNH"])
            
        if st.button("Đăng xuất"): st.session_state.logged_in = False; st.rerun()

    # --- TAB ADMIN (CHỈ HIỆN KHI LÀ ADMIN VÀ CHỌN MENU NÀY) ---
    if menu == "🔧 QUẢN TRỊ ADMIN" and IS_ADMIN:
        st.markdown(f"<div class='main-logo'>QUẢN TRỊ HỆ THỐNG</div>", unsafe_allow_html=True)
        
        # Lấy danh sách tất cả HLV
        all_users = run_query("SELECT * FROM users ORDER BY id ASC")
        st.dataframe(all_users[['id', 'username', 'full_name', 'expiry_date', 'is_active']], use_container_width=True)
        
        st.markdown("### 🛠️ TÁC VỤ QUẢN LÝ")
        col_adm1, col_adm2 = st.columns(2)
        
        with col_adm1:
            with st.form("admin_extend"):
                st.subheader("Gia hạn / Khóa tài khoản")
                target_user = st.selectbox("Chọn HLV:", all_users['username'].tolist())
                new_expiry = st.date_input("Ngày hết hạn mới")
                is_active = st.checkbox("Đang hoạt động (Bỏ tick để KHÓA)", value=True)
                if st.form_submit_button("CẬP NHẬT"):
                    run_query("UPDATE users SET expiry_date=:ed, is_active=:ac WHERE username=:u", 
                              {"ed": new_expiry, "ac": is_active, "u": target_user})
                    st.success(f"Đã cập nhật cho {target_user}")
                    st.rerun()
                    
        with col_adm2:
            with st.form("admin_reset"):
                st.subheader("Reset Mật khẩu")
                target_user_rs = st.selectbox("Chọn HLV cần reset:", all_users['username'].tolist(), key="rs_sel")
                new_pass_rs = st.text_input("Mật khẩu mới")
                if st.form_submit_button("ĐỔI MẬT KHẨU"):
                    if new_pass_rs:
                        hashed = bcrypt.hashpw(new_pass_rs.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        run_query("UPDATE users SET password_hash=:ph WHERE username=:u", {"ph": hashed, "u": target_user_rs})
                        st.success(f"Đã đổi mật khẩu cho {target_user_rs}")
                    else: st.warning("Nhập mật khẩu mới")

    elif menu == "🏠 TỔNG QUAN":
        st.markdown(f"<div class='main-logo'>DASHBOARD</div>", unsafe_allow_html=True)
        clients = run_query("SELECT * FROM clients WHERE trainer_id = :tid", {"tid": TRAINER_ID})
        if not clients.empty:
            k1, k2, k3 = st.columns(3)
            k1.markdown(f"<div class='css-card' style='text-align:center'><h2 style='color:#D4AF37; margin:0'>{len(clients)}</h2><p style='color:#888'>HỌC VIÊN</p></div>", unsafe_allow_html=True)
            alert_cnt = 0
            for cid in clients['id']:
                last = run_query("SELECT date FROM checkins WHERE client_id=:cid ORDER BY date DESC LIMIT 1", {"cid": cid})
                if last.empty or (datetime.now() - pd.to_datetime(last['date'][0])).days > 3: alert_cnt += 1
            k2.markdown(f"<div class='css-card' style='text-align:center; border-color:#FF4B4B'><h2 style='color:#FF4B4B; margin:0'>{alert_cnt}</h2><p style='color:#888'>CẦN CHECK-IN</p></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='css-card' style='text-align:center; border-color:#FFF'><h2 style='color:#FFF; margin:0'>Active</h2><p style='color:#888'>TRẠNG THÁI</p></div>", unsafe_allow_html=True)
            st.markdown("#### DANH SÁCH HỌC VIÊN")
            st.dataframe(clients[['name', 'package_name', 'end_date', 'status']], use_container_width=True)
        else: st.info("Chưa có dữ liệu.")

    elif menu == "👥 HỌC VIÊN":
        clients = run_query("SELECT * FROM clients WHERE trainer_id = :tid", {"tid": TRAINER_ID})
        if not clients.empty:
            c_sel, _ = st.columns([1,2])
            with c_sel: c_name = st.selectbox("CHỌN HỌC VIÊN:", clients['name'].tolist())
            client = clients[clients['name'] == c_name].iloc[0]
            cid = int(client['id'])
            
            st.markdown(f"""<div class="css-card" style="border-top: 4px solid #D4AF37"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h1 style="color:#FFF; margin:0">{client['name']}</h1><span style="color:#D4AF37">{client['level']}</span></div><div style="text-align:right;"><h3 style="color:#FFF; margin:0">{client['package_name']}</h3></div></div></div>""", unsafe_allow_html=True)
            
            t1, t2, t3, t4 = st.tabs(["MEAL PLAN", "CHECK-IN", "TIẾN ĐỘ", "CÀI ĐẶT"])
            
            with t1:
                # --- LOGIC TỰ SỬA LỖI DỮ LIỆU CŨ (AUTO-FIX) ---
                plan = {}
                try:
                    if "Professional" in client['level']:
                        goal_map = {"Tăng cân": "Bulking", "Giảm mỡ": "Cutting", "Cải thiện sức khỏe": "Maintain"}
                        safe_goal = goal_map.get(client['goal'], client['goal'])
                        f_ratio = JP_FORMULAS[client['gender']][safe_goal][client['activity']]
                        w = client['start_weight']
                        plan = {
                            'train': {'p': int(w*f_ratio['train']['p']), 'c': int(w*f_ratio['train']['c']), 'f': int(w*f_ratio['train']['f'])},
                            'rest': {'p': int(w*f_ratio['rest']['p']), 'c': int(w*f_ratio['rest']['c']), 'f': int(w*f_ratio['rest']['f'])}
                        }
                        plan['train']['cal'] = plan['train']['p']*4 + plan['train']['c']*4 + plan['train']['f']*9
                        plan['rest']['cal'] = plan['rest']['p']*4 + plan['rest']['c']*4 + plan['rest']['f']*9
                    else:
                        cal_base, p, c, f = calc_basic(client['start_weight'], client['height'], client['age'], client['gender'], client['activity'], client['goal'])
                        plan = {'train': {'p': p, 'c': int(c*1.1), 'f': f, 'cal': int(cal_base*1.05)}, 'rest': {'p': p, 'c': int(c*0.9), 'f': f, 'cal': int(cal_base*0.95)}}
                except Exception as e:
                    st.error(f"Lỗi tính toán: {str(e)}")
                
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
                        run_query("INSERT INTO checkins (trainer_id, client_id, date, weight, compliance_meal, compliance_workout, notes) VALUES (:tid, :cid, :d, :w, :cm, :cw, :nt)", {"tid": TRAINER_ID, "cid": cid, "d": d, "w": w, "cm": cm, "cw": cw, "nt": nt}); st.success("Đã lưu!"); st.rerun()
                logs = run_query("SELECT * FROM checkins WHERE client_id=:cid ORDER BY date DESC", {"cid": cid})
                if not logs.empty: st.dataframe(logs)

            with t3:
                logs = run_query("SELECT * FROM checkins WHERE client_id=:cid ORDER BY date ASC", {"cid": cid})
                if not logs.empty: fig = go.Figure(); fig.add_trace(go.Scatter(x=logs['date'], y=logs['weight'], mode='lines+markers', line=dict(color='#FFD700'))); st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")

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
                    run_query("""INSERT INTO clients (trainer_id, name, phone, gender, age, height, start_weight, goal, activity, bodyfat, level, package_name, duration_months, price, start_date, end_date, status) VALUES (:tid, :n, :p, :g, :a, :h, :w, :gl, :act, :bf, :lv, :pkg, :dur, :pr, :sd, :ed, 'Active')""",
                        {"tid": TRAINER_ID, "n": st.session_state.name_in, "p": st.session_state.phone_in, "g": st.session_state.gender_in, "a": st.session_state.age_in, "h": st.session_state.height_in, "w": st.session_state.weight_in, "gl": st.session_state.goal_in, "act": st.session_state.act_in, "bf": st.session_state.bf_in, "lv": st.session_state.level_in, "pkg": st.session_state.pkg_in, "dur": st.session_state.dur_in, "pr": st.session_state.price_in, "sd": start, "ed": end})
                    for k in default_inputs: st.session_state[k] = default_inputs[k]
                    st.toast("Lưu thành công!", icon="🔥")
                else: st.error("Nhập tên!")

            st.button("🔥 LƯU HỒ SƠ & RESET", type="primary", use_container_width=True, on_click=save_client)
            st.markdown('</div>', unsafe_allow_html=True)

    elif menu == "💵 TÀI CHÍNH":
        st.markdown("### 💰 DOANH THU CỦA BẠN")
        df = run_query("SELECT * FROM clients WHERE trainer_id = :tid", {"tid": TRAINER_ID})
        if not df.empty: st.metric("TỔNG DOANH THU", f"{df['price'].sum():,} VNĐ"); st.dataframe(df[['name', 'package_name', 'start_date', 'price']], use_container_width=True)
        else: st.info("Chưa có dữ liệu.")

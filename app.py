import streamlit as st
from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# --- ページ設定 ---
st.set_page_config(page_title="JUOG UTUC_Follow-up CRF", layout="wide")

# --- JUOG専用デザインCSS (80pxの余白を死守) ---
st.markdown("""
    <style>
    header[data-testid="stHeader"] { visibility: hidden; }
    .block-container { 
        max-width: 1100px !important; 
        padding-top: 1.5rem !important; 
        padding-bottom: 5rem !important; 
        margin: auto !important;
    }
    h1 { 
        font-size: 26px !important; 
        color: #0F172A; 
        text-align: center; 
        margin-top: 0px !important; 
        margin-bottom: 80px !important; 
        font-weight: 800; 
        height: 40px;
    }
    .juog-header {
        background-color: #1E3A8A;
        color: white;
        padding: 10px 20px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px;
        margin-top: 25px;
        margin-bottom: 15px;
    }
    label { font-weight: 600 !important; color: #334155 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #E2E8F0; }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        color: #64748B !important;
        padding: 10px 4px !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #1E3A8A !important;
        border-bottom: 3px solid #1E3A8A !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 施設リスト ---
FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医科大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

HELP_CD = """
**Clavien-Dindo 分類 (術後合併症評価)**
Gradingの原則：
- **Grade I**：正常な術後経過からの逸脱で、薬物療法、または外科的治療、内視鏡的治療、IVR 治療を要さないもの。
- **Grade II**：制吐剤、解熱剤、鎮痛剤、利尿剤以外の薬物療法を要する。輸血および中心静脈栄養を含む。
- **Grade III**：外科的・内視鏡的・IVR治療を要する（IIIa: 局麻、IIIb: 全麻）。
- **Grade IV**：生命を脅かす合併症（ICU管理）。
- **Grade V**：患者の死亡。
"""

# --- セッション状態初期化 (全ての変数を漏れなく定義) ---
if 'init_followup_fix_done' not in st.session_state:
    st.session_state['init_followup_fix_done'] = True
    # 血液検査項目リスト
    LAB_KEYS = ["WBC", "Hb", "PLT", "AST", "ALT", "T-Bil", "Alb", "LDH", "Cre", "eGFR", "CRP"]
    
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "report_cycle": "6ヶ月後報告", 
        "status_alive": "生存", "final_date": None, "death_date": None, "death_cause": "選択してください",
        "pfs_status": "なし", "pfs_date": None, "pfs_site": []
    }
    # 3ヶ月毎の2つのタイムポイント（前期・後期）の変数を初期化
    for tp in ["early", "late"]:
        defaults[f"eval_date_{tp}"] = None
        defaults[f"cd_{tp}"] = "選択してください"
        defaults[f"cyto_{tp}"] = "選択してください"
        defaults[f"treat_{tp}"] = "選択してください"
        for lab in LAB_KEYS:
            defaults[f"lab_{tp}_{lab}"] = 0.0

    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def get_idx(options, value):
    try: return options.index(value)
    except: return 0

def send_email(report_content, pid, facility, reporter_email=None):
    try:
        mail_user = st.secrets["email"]["user"]; mail_pass = st.secrets["email"]["pass"]
        to_addrs = ["urosec@kmu.ac.jp", "yoshida.tks@kmu.ac.jp"]
        if reporter_email: to_addrs.append(reporter_email)
        msg = MIMEMultipart(); msg['From'] = mail_user; msg['To'] = ", ".join(to_addrs)
        msg['Subject'] = f"【JUOG 長期報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 術後長期経過CRF")

# --- 共通ヘッダー ---
col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    st.session_state.facility_name = st.selectbox("施設名*", FACILITY_LIST, index=get_idx(FACILITY_LIST, st.session_state.facility_name))
    st.session_state.reporter_email = st.text_input("担当者メールアドレス（控え送付先）*", value=st.session_state.reporter_email)
with col_h2:
    st.session_state.patient_id = st.text_input("研究対象者識別コード*", value=st.session_state.patient_id)
with col_h3:
    # 報告サイクルの選択 (6, 12, 18, 24ヶ月後)
    cycles = ["6ヶ月後報告", "12ヶ月後報告", "18ヶ月後報告", "24ヶ月後報告"]
    st.session_state.report_cycle = st.selectbox("報告サイクル*", cycles, index=get_idx(cycles, st.session_state.report_cycle))

# 表示ラベルの動的設定
if st.session_state.report_cycle == "6ヶ月後報告": t1, t2 = "3ヶ月時点", "6ヶ月時点"
elif st.session_state.report_cycle == "12ヶ月後報告": t1, t2 = "9ヶ月時点", "12ヶ月時点"
elif st.session_state.report_cycle == "18ヶ月後報告": t1, t2 = "15ヶ月時点", "18ヶ月時点"
else: t1, t2 = "21ヶ月時点", "24ヶ月時点"

tab1, tab2, tab3 = st.tabs([f"📅 {t1}の経過", f"📅 {t2}の経過", "⚖️ 生存・再発確認"])

def render_tp(tp_key, label):
    st.markdown(f'<div class="juog-header">{label} の所見</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.date_input(f"{label} 来院日*", key=f"eval_date_{tp_key}")
        cd_opts = ["選択してください", "Grade 0", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V"]
        st.selectbox("合併症 (CD分類)*", cd_opts, index=get_idx(cd_opts, st.session_state[f"cd_{tp_key}"]), help=HELP_CD, key=f"cd_{tp_key}")
    with c2:
        cy_opts = ["選択してください", "Negative", "AUC", "SHGUC", "HGUC", "LGUC", "判定不能", "未実施"]
        st.selectbox("尿細胞診*", cy_opts, index=get_idx(cy_opts, st.session_state[f"cyto_{tp_key}"]), key=f"cyto_{tp_key}")
        tx_opts = ["選択してください", "無治療", "EVP継続", "ペムブロ維持", "ニボ単剤", "化学療法", "その他"]
        st.selectbox("治療状況*", tx_opts, index=get_idx(tx_opts, st.session_state[f"treat_{tp_key}"]), key=f"treat_{tp_key}")

    st.markdown("**血液検査データ**")
    bc1, bc2 = st.columns(2)
    labs = [
        ("WBC", "/μL", 1.0), ("Hb", "g/dL", 0.1), ("PLT", "x10^4/μL", 1.0), 
        ("AST", "U/L", 1.0), ("ALT", "U/L", 1.0), ("T-Bil", "mg/dL", 0.1), 
        ("Alb", "g/dL", 0.1), ("LDH", "U/L", 1.0), ("Cre", "mg/dL", 0.01), 
        ("eGFR", "mL/min", 0.1), ("CRP", "mg/dL", 0.01)
    ]
    for i, (name, unit, step) in enumerate(labs):
        col = bc1 if i < (len(labs)+1)//2 else bc2
        col.number_input(f"{name} ({unit})", step=step, key=f"lab_{tp_key}_{name}")

with tab1: render_tp("early", t1)
with tab2: render_tp("late", t2)

with tab3:
    st.markdown('<div class="juog-header">生存・再発状況</div>', unsafe_allow_html=True)
    sc1, sc2 = st.columns(2)
    with sc1:
        st.session_state.status_alive = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive=="生存" else 1), horizontal=True)
        if st.session_state.status_alive == "生存":
            st.date_input("最終生存確認日*", key="final_date")
        else:
            st.date_input("死亡日*", key="death_date")
            d_opts = ["選択してください", "癌死", "治療関連死", "他病死", "不明"]
            st.selectbox("死因*", d_opts, index=get_idx(d_opts, st.session_state.death_cause), key="death_cause")
    with sc2:
        st.session_state.pfs_status = st.radio("再発の有無*", ["なし", "あり"], index=(0 if st.session_state.pfs_status=="なし" else 1), horizontal=True)
        if st.session_state.pfs_status == "あり":
            st.date_input("再発確定日*", key="pfs_date")
            st.multiselect("部位*", ["膀胱内", "局所", "リンパ節", "遠隔転移", "その他"], key="pfs_site")

    st.divider()
    if st.button("🚀 確定送信", type="primary", use_container_width=True):
        errors = []
        d = st.session_state
        if d.facility_name == "選択してください": errors.append("・施設名")
        if not d.patient_id: errors.append("・識別コード")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", d.reporter_email): errors.append("・有効なメールアドレス")
        if d.status_alive == "死亡" and d.cd_late != "Grade V": errors.append("・死亡なのに直近のCD分類がGrade V以外です")
        
        if errors: st.error("修正してください：\n" + "\n".join(errors))
        else:
            def fn(v): return str(v) if v is not None else "N/A"
            rep = f"【JUOG フォローアップ {d.report_cycle}】\n施設: {d.facility_name} / ID: {d.patient_id}\n\n"
            rep += f"--- {t1}の経過 ---\n評価日: {d.eval_date_early} / CD: {d.cd_early}\nWBC: {fn(d.lab_early_WBC)} / Cre: {fn(d.lab_early_Cre)}\n"
            rep += f"--- {t2}の経過 ---\n評価日: {d.eval_date_late} / CD: {d.cd_late}\nWBC: {fn(d.lab_late_WBC)} / Cre: {fn(d.lab_late_Cre)}\n"
            rep += f"--- 状況 ---\n生存: {d.status_alive} / 再発: {d.pfs_status}"
            
            if send_email(rep, d.patient_id, d.facility_name, d.reporter_email):
                st.success(f"{d.reporter_email} 宛に報告控えを送信しました。")
                st.balloons()

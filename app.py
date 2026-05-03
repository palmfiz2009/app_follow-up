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
    .stCheckbox { margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 施設リスト ---
FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

# --- 詳細定義テキスト (CD分類) ---
HELP_CD = """
**Clavien-Dindo 分類 (術後合併症評価)**
- Grade I：正常な術後経過からの逸脱で、薬物療法、外科的治療等を要さないもの。
- Grade II：利尿剤、輸血、中心静脈栄養等の薬物療法を要するもの。
- Grade III：外科的・内視鏡的・IVR治療を要するもの。
- Grade IV：生命を脅かす合併症（ICU管理）。
- Grade V：死亡。
"""

# --- セッション状態初期化 ---
if 'init_clinical_followup_done' not in st.session_state:
    st.session_state['init_clinical_followup_done'] = True
    LAB_KEYS = ["WBC", "Hb", "PLT", "AST", "ALT", "T-Bil", "Alb", "LDH", "Cre", "eGFR", "CRP"]
    
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "report_timing": "選択してください", "eval_date": None,
        "treat_status": "選択してください",
        "status_alive": None, "final_date": None, "death_date": None, "death_cause": "選択してください",
        "pfs_status": None, "pfs_date": None, "pfs_site": [],
        "has_event": False, "has_labs": False, # トグル用
        "cd_grade": "Grade 0", "ae_status": "なし", "cyto_res": "未実施"
    }
    for lab in LAB_KEYS: defaults[f"lab_{lab}"] = 0.0
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
        msg['Subject'] = f"【JUOG 定期報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 定期経過報告")

# --- 1. 基本情報・報告時期 ---
st.markdown('<div class="juog-header">1. 基本情報・報告時期</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    st.session_state.facility_name = st.selectbox("施設名*", FACILITY_LIST, index=get_idx(FACILITY_LIST, st.session_state.facility_name))
    st.session_state.reporter_email = st.text_input("担当者メールアドレス*", value=st.session_state.reporter_email)
with c2:
    st.session_state.patient_id = st.text_input("研究対象者識別コード*", value=st.session_state.patient_id)
with c3:
    timings = ["選択してください", "3ヶ月後", "6ヶ月後", "9ヶ月後", "12ヶ月後", "15ヶ月後", "18ヶ月後", "21ヶ月後", "24ヶ月後", "その他"]
    st.session_state.report_timing = st.selectbox("今回の報告時期*", timings, index=get_idx(timings, st.session_state.report_timing))

# --- 2. 必須項目：予後（生存・再発）と治療状況 ---
st.markdown('<div class="juog-header">2. 予後・現在の治療状況</div>', unsafe_allow_html=True)
p1, p2 = st.columns(2)
with p1:
    st.session_state.status_alive = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive=="生存" else 1 if st.session_state.status_alive=="死亡" else None), horizontal=True)
    if st.session_state.status_alive == "生存":
        st.session_state.final_date = st.date_input("最終生存確認日*", value=st.session_state.final_date)
    elif st.session_state.status_alive == "死亡":
        st.session_state.death_date = st.date_input("死亡日*", value=st.session_state.death_date)
        dc_opts = ["選択してください", "癌死", "治療関連死", "他病死", "不明"]
        st.session_state.death_cause = st.selectbox("死因*", dc_opts, index=get_idx(dc_opts, st.session_state.death_cause))

    tx_opts = ["選択してください", "無治療（経過観察）", "EVP継続投与", "ペムブロ単剤維持", "化学療法（GC等）", "化学療法（MVAC等）", "その他"]
    st.session_state.treat_status = st.selectbox("現在の治療内容*", tx_opts, index=get_idx(tx_opts, st.session_state.treat_status))

with p2:
    st.session_state.pfs_status = st.radio("再発の有無 (今回確認分)*", ["なし", "あり"], index=(0 if st.session_state.pfs_status=="なし" else 1 if st.session_state.pfs_status=="あり" else None), horizontal=True)
    if st.session_state.pfs_status == "あり":
        st.session_state.pfs_date = st.date_input("再発確定日*", value=st.session_state.pfs_date)
        st.session_state.pfs_site = st.multiselect("再発部位*", ["膀胱内", "手術局所", "リンパ節", "遠隔転移", "その他"], default=st.session_state.pfs_site)
    st.session_state.eval_date = st.date_input("診察・評価実施日*", value=st.session_state.eval_date)

# --- 3. 随時入力：合併症・有害事象 (必要時のみ展開) ---
st.markdown('<div class="juog-header">3. イベント報告（合併症・有害事象）</div>', unsafe_allow_html=True)
st.session_state.has_event = st.checkbox("合併症、または特記すべき有害事象（副作用）がある", value=st.session_state.has_event)

if st.session_state.has_event:
    e1, e2 = st.columns(2)
    with e1:
        cd_opts = ["Grade 0", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V"]
        st.session_state.cd_grade = st.selectbox("合併症 (CD分類)", cd_opts, index=get_idx(cd_opts, st.session_state.cd_grade), help=HELP_CD)
    with e2:
        st.session_state.ae_status = st.text_area("薬剤関連有害事象の詳細 (Grade等)", value=st.session_state.ae_status)
    cy_opts = ["未実施", "Negative", "AUC", "SHGUC", "HGUC", "LGUC", "判定不能"]
    st.session_state.cyto_res = st.selectbox("尿細胞診結果 (実施した場合)", cy_opts, index=get_idx(cy_opts, st.session_state.cyto_res))

# --- 4. 採血データ (必要時のみ展開：12ヶ月目など) ---
st.markdown('<div class="juog-header">4. 採血検査データ (12ヶ月目または実施時のみ)</div>', unsafe_allow_html=True)
st.session_state.has_labs = st.checkbox("採血結果を入力する（12ヶ月目は必須）", value=st.session_state.has_labs)

if st.session_state.has_labs:
    bc1, bc2 = st.columns(2)
    labs = [
        ("WBC", "/μL", 1.0), ("Hb", "g/dL", 0.1), ("PLT", "x10^4/μL", 1.0), 
        ("AST", "U/L", 1.0), ("ALT", "U/L", 1.0), ("T-Bil", "mg/dL", 0.1), 
        ("Alb", "g/dL", 0.1), ("LDH", "U/L", 1.0), ("Cre", "mg/dL", 0.01), 
        ("eGFR", "mL/min", 0.1), ("CRP", "mg/dL", 0.01)
    ]
    for i, (name, unit, step) in enumerate(labs):
        col = bc1 if i < (len(labs)+1)//2 else bc2
        st.session_state[f"lab_{name}"] = col.number_input(f"{name} ({unit})", value=st.session_state[f"lab_{name}"], step=step, key=f"key_{name}")

st.divider()

# --- 送信ロジック ---
if st.button("🚀 事務局へ確定送信", type="primary", use_container_width=True):
    errors = []
    d = st.session_state
    if d.facility_name == "選択してください": errors.append("・施設名")
    if not d.patient_id: errors.append("・識別コード")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", d.reporter_email): errors.append("・メールアドレス")
    if d.report_timing == "選択してください": errors.append("・報告時期")
    if d.status_alive is None: errors.append("・生存状況")
    if d.pfs_status is None: errors.append("・再発の有無")
    if d.report_timing == "12ヶ月後" and not d.has_labs: errors.append("・12ヶ月目報告には採血データの入力が必要です")
    
    if errors:
        st.error("入力不備があります：\n" + "\n".join(errors))
    else:
        def fn(v): return str(v) if (v is not None and v != 0) else "N/A"
        rep = f"""【JUOG 定期経過報告】
報告時期: {d.report_timing} / ID: {d.patient_id}
生存: {d.status_alive} / 再発: {d.pfs_status}
治療内容: {d.treat_status}

--- 有害事象・合併症 (Event: {d.has_event}) ---
CD分類: {d.cd_grade} / 詳細: {d.ae_status} / 細胞診: {d.cyto_res}

--- 採血データ (Labs: {d.has_labs}) ---
WBC:{fn(d.lab_WBC)}, Hb:{fn(d.lab_Hb)}, Cre:{fn(d.lab_Cre)}
"""
        if send_email(rep, d.patient_id, d.facility_name, d.reporter_email):
            st.success("正常に送信されました。控えを送信しました。")
            st.balloons()

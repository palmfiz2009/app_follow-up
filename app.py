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
    div[data-baseweb="select"] ul { white-space: normal !important; }
    div[role="option"] { line-height: 1.4 !important; padding: 8px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 施設リスト ---
FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医科大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

# --- 詳細定義テキスト (死守) ---
HELP_CD = """
**Clavien-Dindo 分類 (術後合併症評価)**
Gradingの原則：
- **Grade I**：正常な術後経過からの逸脱で、薬物療法、または外科的治療、内視鏡的治療、IVR 治療を要さないもの。ベッドサイドでの創感染の開放は Grade I とする。
- **Grade II**：制吐剤、解熱剤、鎮痛剤、利尿剤以外の薬物療法を要する。輸血および中心静脈栄養を要する場合を含む。
- **Grade III**：外科的・内視鏡的・IVR治療を要する（IIIa: 局麻、IIIb: 全麻）。
- **Grade IV**：ICU 管理を要する生命を脅かす合併症。
- **Grade V**：患者の死亡。
"""

# --- セッション状態初期化 (デフォルトは全て未選択) ---
if 'init_periodic_crf_done' not in st.session_state:
    st.session_state['init_periodic_crf_done'] = True
    LAB_KEYS = ["WBC", "Hb", "PLT", "AST", "ALT", "T-Bil", "Alb", "LDH", "Cre", "eGFR", "CRP"]
    
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "report_timing": "選択してください",
        "eval_date": None, "cd_grade": "選択してください", "cyto_res": "選択してください",
        "treat_status": "選択してください", "ae_status": "なし",
        "status_alive": None, "final_date": None, "death_date": None, "death_cause": "選択してください",
        "pfs_status": None, "pfs_date": None, "pfs_site": []
    }
    # 血液検査の初期値
    for lab in LAB_KEYS:
        defaults[f"lab_{lab}"] = 0.0

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
        msg['Subject'] = f"【JUOG 経過報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 術後定期経過報告")

# --- 基本情報セクション ---
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

# --- 所見に関する内容 ---
st.markdown('<div class="juog-header">2. 臨床所見・検査結果</div>', unsafe_allow_html=True)
f1, f2 = st.columns(2)
with f1:
    st.session_state.eval_date = st.date_input("診察・検査実施日*", value=st.session_state.eval_date)
    cd_opts = ["選択してください", "Grade 0", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V"]
    st.session_state.cd_grade = st.selectbox("合併症 (CD分類)*", cd_opts, index=get_idx(cd_opts, st.session_state.cd_grade), help=HELP_CD)
with f2:
    cy_opts = ["選択してください", "Negative", "AUC", "SHGUC", "HGUC", "LGUC", "判定不能", "未実施"]
    st.session_state.cyto_res = st.selectbox("尿細胞診結果*", cy_opts, index=get_idx(cy_opts, st.session_state.cyto_res))
    st.session_state.ae_status = st.text_input("薬剤関連有害事象 (特記すべきもの)", value=st.session_state.ae_status)

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
    st.session_state[f"lab_{name}"] = col.number_input(f"{name} ({unit})", value=st.session_state[f"lab_{name}"], step=step, key=f"key_{name}")

# --- 治療に関する内容 ---
st.markdown('<div class="juog-header">3. 治療状況</div>', unsafe_allow_html=True)
tx_opts = ["選択してください", "無治療（経過観察）", "EVP継続投与", "ペムブロ単剤維持", "化学療法（MVAC等）", "化学療法（GC等）", "免疫チェックポイント阻害剤（その他）", "その他"]
st.session_state.treat_status = st.selectbox("現在の治療内容*", tx_opts, index=get_idx(tx_opts, st.session_state.treat_status))

# --- 予後に関する内容 ---
st.markdown('<div class="juog-header">4. 予後（生存・再発）</div>', unsafe_allow_html=True)
p1, p2 = st.columns(2)
with p1:
    st.session_state.status_alive = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive=="生存" else 1 if st.session_state.status_alive=="死亡" else None), horizontal=True)
    if st.session_state.status_alive == "生存":
        st.session_state.final_date = st.date_input("最終生存確認日*", value=st.session_state.final_date)
    elif st.session_state.status_alive == "死亡":
        st.session_state.death_date = st.date_input("死亡日*", value=st.session_state.death_date)
        dc_opts = ["選択してください", "癌死", "治療関連死", "他病死", "不明"]
        st.session_state.death_cause = st.selectbox("死因*", dc_opts, index=get_idx(dc_opts, st.session_state.death_cause))

with p2:
    st.session_state.pfs_status = st.radio("再発の有無 (今回確認分)*", ["なし", "あり"], index=(0 if st.session_state.pfs_status=="なし" else 1 if st.session_state.pfs_status=="あり" else None), horizontal=True)
    if st.session_state.pfs_status == "あり":
        st.session_state.pfs_date = st.date_input("再発確定日*", value=st.session_state.pfs_date)
        st.session_state.pfs_site = st.multiselect("再発部位*", ["膀胱内", "手術局所", "リンパ節", "遠隔転移（肺・肝・骨等）", "その他"], default=st.session_state.pfs_site)

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
    
    # 整合性チェック
    if d.status_alive == "死亡" and d.cd_grade != "Grade V": errors.append("・死亡報告ですがCD分類がGrade Vになっていません")
    if d.status_alive == "生存" and d.cd_grade == "Grade V": errors.append("・生存報告ですがCD分類がGrade Vになっています")

    if errors:
        st.error("以下の項目を確認してください：\n" + "\n".join(errors))
    else:
        def fn(v): return str(v) if v is not None else "N/A"
        rep = f"""【JUOG 定期経過報告】
報告時期: {d.report_timing}
施設: {d.facility_name} / ID: {d.patient_id}
報告者: {d.reporter_email}

--- 臨床所見 ---
評価日: {d.eval_date} / CD分類: {d.cd_grade} / 細胞診: {d.cyto_res}
有害事象: {d.ae_status}
主要検査値: WBC:{fn(d.lab_WBC)}, Hb:{fn(d.lab_Hb)}, Cre:{fn(d.lab_Cre)}

--- 治療状況 ---
内容: {d.treat_status}

--- 予後 ---
状況: {d.status_alive} (確認/死亡日: {d.final_date if d.status_alive=='生存' else d.death_date})
再発: {d.pfs_status} (日付: {d.pfs_date if d.pfs_status=='あり' else 'N/A'})
"""
        if send_email(rep, d.patient_id, d.facility_name, d.reporter_email):
            st.success(f"{d.report_timing} の報告が正常に送信されました。控えを送信しました。")
            st.balloons()

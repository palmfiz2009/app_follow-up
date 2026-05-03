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
    </style>
    """, unsafe_allow_html=True)

# --- 施設リスト ---
FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医科大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

HELP_CD = """
**Clavien-Dindo 分類 (術後合併症評価)**
- Grade I：正常な術後経過からの逸脱。
- Grade II：輸血、中心静脈栄養、特定の薬物療法を要するもの。
- Grade III：外科的・内視鏡的・IVR治療を要するもの。
- Grade IV：生命を脅かす合併症（ICU管理）。
- Grade V：患者の死亡。
"""

# --- セッション状態初期化 ---
if 'init_followup_v3_done' not in st.session_state:
    st.session_state['init_followup_v3_done'] = True
    LAB_KEYS = ["WBC", "Hb", "PLT", "AST", "ALT", "T-Bil", "Alb", "LDH", "Cre", "eGFR", "CRP", "Neutro", "Lympho", "Mono", "Eosino", "Baso"]
    
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "op_date": None, "report_timing": "選択してください", "eval_date": None,
        "treat_status": "選択してください",
        "status_alive": None, "final_date": None, "death_date": None, "death_cause": "選択してください",
        "pfs_intra": None, "pfs_intra_date": None, "pfs_intra_site": [],
        "pfs_extra": None, "pfs_extra_date": None, "pfs_extra_site": [],
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
        msg['Subject'] = f"【JUOG 経過報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 定期経過報告")

# --- 1. 基本情報・手術日・報告時期 ---
st.markdown('<div class="juog-header">1. 基本情報・手術日・報告時期</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    st.session_state.facility_name = st.selectbox("施設名*", FACILITY_LIST, index=get_idx(FACILITY_LIST, st.session_state.facility_name))
    st.session_state.reporter_email = st.text_input("担当者メールアドレス*", value=st.session_state.reporter_email)
with c2:
    st.session_state.patient_id = st.text_input("研究対象者識別コード*", value=st.session_state.patient_id)
    st.session_state.op_date = st.date_input("手術日*", value=st.session_state.op_date)
with c3:
    timing_map = {"6ヶ月後": 6, "12ヶ月後": 12, "18ヶ月後": 18, "24ヶ月後": 24}
    timings = ["選択してください"] + list(timing_map.keys())
    st.session_state.report_timing = st.selectbox("今回の報告時期*", timings, index=get_idx(timings, st.session_state.report_timing))
    
    if st.session_state.op_date and st.session_state.report_timing in timing_map:
        target_date = st.session_state.op_date + timedelta(days=30 * timing_map[st.session_state.report_timing])
        st.info(f"💡 報告目安日: {target_date.strftime('%Y年%m月%d日')} 前後")

# --- 2. 予後（再発：左 / 生存：右） ---
st.markdown('<div class="juog-header">2. 予後（再発・生存）</div>', unsafe_allow_html=True)
p1, p2 = st.columns(2)
with p1:
    # 再発セクション（90日目CRF踏襲）
    st.markdown("**【再発の有無】**")
    st.session_state.pfs_intra = st.radio("尿路内再発*", ["なし", "あり"], index=(0 if st.session_state.pfs_intra=="なし" else 1 if st.session_state.pfs_intra=="あり" else None), horizontal=True)
    if st.session_state.pfs_intra == "あり":
        st.session_state.pfs_intra_date = st.date_input("尿路内再発確定日*", value=st.session_state.pfs_intra_date)
        st.session_state.pfs_intra_site = st.multiselect("尿路内再発部位*", ["膀胱", "対側上部尿路", "その他"], default=st.session_state.pfs_intra_site)
    
    st.session_state.pfs_extra = st.radio("尿路外再発*", ["なし", "あり"], index=(0 if st.session_state.pfs_extra=="なし" else 1 if st.session_state.pfs_extra=="あり" else None), horizontal=True)
    if st.session_state.pfs_extra == "あり":
        st.session_state.pfs_extra_date = st.date_input("尿路外再発確定日*", value=st.session_state.pfs_extra_date)
        st.session_state.pfs_extra_site = st.multiselect("尿路外再発部位*", ["手術局所", "リンパ節", "肺", "肝", "骨", "その他"], default=st.session_state.pfs_extra_site)
    
    st.session_state.eval_date = st.date_input("診察・評価実施日*", value=st.session_state.eval_date)

with p2:
    # 生存セクション
    st.markdown("**【生存状況】**")
    st.session_state.status_alive = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive=="生存" else 1 if st.session_state.status_alive=="死亡" else None), horizontal=True)
    if st.session_state.status_alive == "生存":
        st.session_state.final_date = st.date_input("最終生存確認日*", value=st.session_state.final_date)
        # 生存時のみ治療内容を表示
        st.markdown("---")
        tx_opts = ["選択してください", "無治療（経過観察）", "EVP継続投与", "ペムブロ単剤維持", "化学療法（GC等）", "化学療法（MVAC等）", "その他"]
        st.session_state.treat_status = st.selectbox("現在の治療内容*", tx_opts, index=get_idx(tx_opts, st.session_state.treat_status))
    elif st.session_state.status_alive == "死亡":
        st.session_state.death_date = st.date_input("死亡日*", value=st.session_state.death_date)
        dc_opts = ["選択してください", "癌死", "治療関連死", "他病死", "不明"]
        st.session_state.death_cause = st.selectbox("死因*", dc_opts, index=get_idx(dc_opts, st.session_state.death_cause))

# --- 3. 合併症・有害事象 ---
st.markdown('<div class="juog-header">3. 合併症・有害事象（随時）</div>', unsafe_allow_html=True)
has_event = st.checkbox("合併症、または特記すべき有害事象がある", value=(True if st.session_state.cd_grade != "Grade 0" or st.session_state.ae_status != "なし" else False))
if has_event:
    e1, e2 = st.columns(2)
    with e1:
        cd_opts = ["Grade 0", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V"]
        st.session_state.cd_grade = st.selectbox("合併症 (CD分類)", cd_opts, index=get_idx(cd_opts, st.session_state.cd_grade), help=HELP_CD)
    with e2:
        st.session_state.ae_status = st.text_area("薬剤関連有害事象の詳細", value=st.session_state.ae_status)
    cy_opts = ["未実施", "Negative", "AUC", "SHGUC", "HGUC", "LGUC", "判定不能"]
    st.session_state.cyto_res = st.selectbox("尿細胞診結果", cy_opts, index=get_idx(cy_opts, st.session_state.cyto_res))

# --- 4. 採血データ (12, 24ヶ月目は必須) ---
is_lab_required = st.session_state.report_timing in ["12ヶ月後", "24ヶ月後"]
st.markdown(f'<div class="juog-header">4. 採血検査データ {"(必須時期)" if is_lab_required else "(実施時のみ)"}</div>', unsafe_allow_html=True)

show_labs = st.checkbox("採血結果を入力する", value=is_lab_required)

if show_labs:
    bc1, bc2 = st.columns(2)
    main_labs = [("WBC", "/μL", 1.0), ("Hb", "g/dL", 0.1), ("PLT", "x10^4/μL", 1.0), ("AST", "U/L", 1.0), ("ALT", "U/L", 1.0), ("T-Bil", "mg/dL", 0.1), ("Alb", "g/dL", 0.1), ("LDH", "U/L", 1.0), ("Cre", "mg/dL", 0.01), ("eGFR", "mL/min", 0.1), ("CRP", "mg/dL", 0.01)]
    for i, (name, unit, step) in enumerate(main_labs):
        col = bc1 if i < (len(main_labs)+1)//2 else bc2
        st.session_state[f"lab_{name}"] = col.number_input(f"{name} ({unit})", value=st.session_state[f"lab_{name}"], step=step, key=f"k_{name}")
    
    st.markdown("**白血球分画 (%)**")
    f1, f2, f3, f4, f5 = st.columns(5)
    st.session_state.lab_Neutro = f1.number_input("Neutro", value=st.session_state.lab_Neutro, step=0.1)
    st.session_state.lab_Lympho = f2.number_input("Lympho", value=st.session_state.lab_Lympho, step=0.1)
    st.session_state.lab_Mono = f3.number_input("Mono", value=st.session_state.lab_Mono, step=0.1)
    st.session_state.lab_Eosino = f4.number_input("Eosino", value=st.session_state.lab_Eosino, step=0.1)
    st.session_state.lab_Baso = f5.number_input("Baso", value=st.session_state.lab_Baso, step=0.1)

st.divider()

# --- 送信ロジック ---
if st.button("🚀 事務局へ確定送信", type="primary", use_container_width=True):
    errors = []
    d = st.session_state
    if d.facility_name == "選択してください": errors.append("・施設名")
    if not d.patient_id: errors.append("・識別コード")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", d.reporter_email): errors.append("・メールアドレス")
    if d.report_timing == "選択してください": errors.append("・報告時期")
    if d.pfs_intra is None or d.pfs_extra is None: errors.append("・再発の有無")
    if d.status_alive is None: errors.append("・生存状況")
    if is_lab_required and (not show_labs or d.lab_WBC == 0): errors.append("・本報告回では採血データの入力が必須です")

    if errors:
        st.error("修正してください：\n" + "\n".join(errors))
    else:
        def fn(v): return str(v) if (v is not None and v != 0) else "N/A"
        rep = f"""【JUOG 定期報告】
ID: {d.patient_id} / 時期: {d.report_timing}
生存: {d.status_alive} / 尿路内再発: {d.pfs_intra} / 尿路外再発: {d.pfs_extra}
治療内容: {d.treat_status if d.status_alive=='生存' else '死亡につき終了'}

--- 採血 (入力: {show_labs}) ---
WBC:{fn(d.lab_WBC)}, Hb:{fn(d.lab_Hb)}, Cre:{fn(d.lab_Cre)}
分画: Neutro:{fn(d.lab_Neutro)}%, Lympho:{fn(d.lab_Lympho)}%
"""
        if send_email(rep, d.patient_id, d.facility_name, d.reporter_email):
            st.success("送信完了しました。控えを送信しました。")
            st.balloons()

import streamlit as st
import json
from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# --- ページ設定 ---
st.set_page_config(page_title="JUOG UTUC_Follow-up CRF", layout="wide")

# --- JUOG専用デザインCSS ---
st.markdown("""
    <style>
    header[data-testid="stHeader"] { visibility: hidden; }
    .block-container { max-width: 1100px !important; padding-top: 1.5rem !important; padding-bottom: 5rem !important; margin: auto !important; }
    h1 { font-size: 26px !important; color: #0F172A; text-align: center; margin-bottom: 80px !important; font-weight: 800; }
    .juog-header { background-color: #1E3A8A; color: white; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-size: 16px; margin-top: 25px; margin-bottom: 15px; }
    label { font-weight: 600 !important; color: #334155 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 治療カテゴリ定義 ---
SURGERY_LIST = ["TURBT", "上部尿路内視鏡的治療", "手術（腎尿管全摘等）", "手術（転移巣切除）"]
DRUG_LIST = ["BCG注入療法", "抗がん剤注入療法", "プラチナ製剤併用療法（GC療法）", "プラチナ製剤併用療法（GCarbo療法）", "維持療法（アベルマブ等）", "EVP療法", "ペムブロリズマブ単剤", "ニボルマブ単剤", "サシツズマブ ゴビテカン（SG）", "FGFR阻害薬", "治験（HER2標的ADC、TROP2標的ADC、その他）", "放射線治療"]

FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医科大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

HELP_CD = """【Clavien-Dindo分類】
* Grade I: 正常な術後経過からの逸脱。薬物、外科、内視鏡介入を要さない術後逸脱
* Grade II: 輸血、中心静脈栄養を含む薬物療法を要する
* Grade III: 外科的、内視鏡的、または放射線学的介入を要する
  * IIIa: 全身麻酔を要さない / IIIb: 全身麻酔を要する
* Grade IV: 生命を脅かす合併症
  * IVa: 単一臓器不全 / IVb: 多臓器不全
* Grade V: 患者の死亡"""

HELP_CYTO = """【尿細胞診結果】
* Negative: 陰性（クラスI・II）
* AUC: 非定型細胞
* SHGUC: 高異型度癌疑い
* HGUC: 高異型度癌（クラスIV・V相当）
* LGUC: 低異型度腫瘍"""

# --- セッション初期化 ---
if 'v31_perfect_confirmed' not in st.session_state:
    st.session_state['v31_perfect_confirmed'] = True
    LAB_KEYS = ["WBC", "Hb", "PLT", "AST", "ALT", "Alb", "LDH", "Cre", "eGFR", "CRP", "Neutro", "Lympho", "Mono", "Eosino", "Baso"]
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "op_date": None, "report_timing": "選択してください",
        "pfs_intra": None, "pfs_intra_date": None, "pfs_intra_site": [], "pfs_intra_site_other": "", 
        "pfs_intra_tx": [], "pfs_intra_tx_other": "", "intra_op_date": None, "intra_tx_start": None, "intra_tx_end": None, "intra_tx_ongoing": False, "pfs_intra_path": "", 
        "cyto_res": "選択してください",
        "pfs_extra": None, "pfs_extra_date": None, "pfs_extra_site": [], "pfs_extra_site_other": "", 
        "pfs_extra_tx": "選択してください", "pfs_extra_tx_detail": "", "extra_op_date": None, "extra_tx_start": None, "extra_tx_end": None, "extra_tx_ongoing": False,
        "status_alive": None, "final_date": None, "death_date": None, "death_cause": "選択してください", 
        "treat_status": "選択してください", "treat_status_detail": "",
        "ae_status": "", "cd_grade": "なし", "has_event": False
    }
    for lab in LAB_KEYS: defaults[f"lab_{lab}"] = None
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
        msg['Subject'] = f"【JUOG 報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465); server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 定期経過報告")

# --- 1. 基本情報 (2列) ---
st.markdown('<div class="juog-header">1. 基本情報・報告時期</div>', unsafe_allow_html=True)
hcol1, hcol2 = st.columns(2)
with hcol1:
    st.session_state.facility_name = st.selectbox("施設名*", FACILITY_LIST, index=get_idx(FACILITY_LIST, st.session_state.facility_name))
    st.session_state.patient_id = st.text_input("研究対象者識別コード*", value=st.session_state.patient_id)
    # --- 修正点：文言の最適化 ---
    st.session_state.op_date = st.date_input("手術日（非施行例は予定日）*", value=st.session_state.op_date)
with hcol2:
    st.session_state.reporter_email = st.text_input("担当者メールアドレス*", value=st.session_state.reporter_email)
    timings = ["選択してください", "術後6ヶ月後", "術後9ヶ月後", "術後12ヶ月後", "術後15ヶ月後", "術後18ヶ月後", "術後21ヶ月後", "術後24ヶ月後"]
    st.session_state.report_timing = st.selectbox("今回の報告時期*", timings, index=get_idx(timings, st.session_state.report_timing))
    
    if st.session_state.op_date and st.session_state.report_timing != "選択してください":
        m_match = re.search(r'\d+', st.session_state.report_timing)
        if m_match:
            m_end = int(m_match.group())
            start_date = st.session_state.op_date + timedelta(days=int(30.4 * (m_end - 3)) + 1)
            end_date = st.session_state.op_date + timedelta(days=int(30.4 * m_end))
            st.warning(f"📅 報告対象期間: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')} 頃")

# --- 2. 再発状況 ---
st.markdown('<div class="juog-header">2. 再発状況の確認</div>', unsafe_allow_html=True)
pcol1, pcol2 = st.columns(2)

with pcol1:
    st.markdown("**【尿路内再発】**")
    st.session_state.pfs_intra = st.radio("尿路内再発の有無*", ["なし", "あり"], index=(0 if st.session_state.pfs_intra=="なし" else 1 if st.session_state.pfs_intra=="あり" else None), horizontal=True, key="r_intra")
    
    if st.session_state.pfs_intra == "あり":
        st.session_state.pfs_intra_date = st.date_input("診断日（組織確定、画像、または膀胱鏡所見）*", value=st.session_state.pfs_intra_date, key="d_intra")
        st.session_state.pfs_intra_site = st.multiselect("再発部位*", ["膀胱", "対側腎盂", "対側尿管", "同側残存尿管", "その他"], default=st.session_state.pfs_intra_site)
        if "その他" in st.session_state.pfs_intra_site:
            st.session_state.pfs_intra_site_other = st.text_input("部位の詳細*", key="site_intra_other")
        
        st.session_state.cyto_res = st.selectbox("尿細胞診 結果*", ["選択してください", "Negative (クラスI・II)", "AUC (非定型細胞)", "SHGUC (高異型度癌疑い)", "HGUC (クラスIV・V相当)", "LGUC (低異型度腫瘍)", "判定不能", "未実施"], index=get_idx(["選択してください", "Negative (クラスI・II)", "AUC (非定型細胞)", "SHGUC (高異型度癌疑い)", "HGUC (クラスIV・V相当)", "LGUC (低異型度腫瘍)", "判定不能", "未実施"], st.session_state.cyto_res), help=HELP_CYTO)
        
        intra_tx_opts = ["経過観察", "TURBT", "BCG注入療法", "抗がん剤注入療法", "上部尿路内内視鏡的治療", "手術（腎尿管全摘等）", "その他"]
        st.session_state.pfs_intra_tx = st.multiselect("実施した治療*", intra_tx_opts, default=st.session_state.pfs_intra_tx)
        
        selected_intra_surgeries = [x for x in st.session_state.pfs_intra_tx if x in SURGERY_LIST]
        if selected_intra_surgeries:
            label_op = f"{' + '.join(selected_intra_surgeries)} 実施日*"
            st.session_state.intra_op_date = st.date_input(label_op, value=st.session_state.intra_op_date, key="intra_op")
            st.session_state.pfs_intra_path = st.text_area("組織型、Grade、pTNM分類 等*", value=st.session_state.pfs_intra_path, key="p_intra")

        selected_intra_drugs = [x for x in st.session_state.pfs_intra_tx if x in DRUG_LIST]
        if selected_intra_drugs:
            label_drug = f"{' + '.join(selected_intra_drugs)}"
            itx_c1, itx_c2 = st.columns(2)
            st.session_state.intra_tx_start = itx_c1.date_input(f"{label_drug} 開始日*", value=st.session_state.intra_tx_start, key="intra_start")
            st.session_state.intra_tx_ongoing = itx_c2.checkbox(f"{label_drug} 継続中", value=st.session_state.intra_tx_ongoing, key="intra_ongoing")
            if not st.session_state.intra_tx_ongoing:
                st.session_state.intra_tx_end = itx_c2.date_input(f"{label_drug} 終了日*", value=st.session_state.intra_tx_end, key="intra_end")

        if "その他" in st.session_state.pfs_intra_tx:
            st.session_state.pfs_intra_tx_other = st.text_input("治療の「その他」の詳細*", key="tx_intra_other")

with pcol2:
    st.markdown("**【尿路外再発】**")
    st.session_state.pfs_extra = st.radio("尿路外再発の有無*", ["なし", "あり"], index=(0 if st.session_state.pfs_extra=="なし" else 1 if st.session_state.pfs_extra=="あり" else None), horizontal=True, key="r_extra")
    
    if st.session_state.pfs_extra == "あり":
        st.session_state.pfs_extra_date = st.date_input("診断日（画像または組織診断日）*", value=st.session_state.pfs_extra_date, key="d_extra")
        st.session_state.pfs_extra_site = st.multiselect("再発部位*", ["肺", "リンパ節", "肝", "骨", "手術局所", "その他"], default=st.session_state.pfs_extra_site)
        if "その他" in st.session_state.pfs_extra_site:
            st.session_state.pfs_extra_site_other = st.text_input("部位の詳細*", key="site_extra_other")
        
        extra_tx_opts = ["選択してください", "プラチナ製剤併用療法（GC療法）", "プラチナ製剤併用療法（GCarbo療法）", "維持療法（アベルマブ等）", "EVP療法", "ペムブロリズマブ単剤", "ニボルマブ単剤", "サシツズマブ ゴビテカン（SG）", "FGFR阻害薬", "治験（HER2標的ADC、TROP2標的ADC、その他）", "手術（転移巣切除）", "放射線治療", "緩和ケア", "その他"]
        st.session_state.pfs_extra_tx = st.selectbox("主たる実施治療*", extra_tx_opts, index=get_idx(extra_tx_opts, st.session_state.pfs_extra_tx))
        
        cur_extra_tx = st.session_state.pfs_extra_tx
        if cur_extra_tx in ["手術（転移巣切除）"]:
            st.session_state.extra_op_date = st.date_input(f"{cur_extra_tx} 実施日*", value=st.session_state.extra_op_date, key="extra_op")

        if cur_extra_tx in DRUG_LIST or cur_extra_tx == "放射線治療":
            etx_c1, etx_c2 = st.columns(2)
            st.session_state.extra_tx_start = etx_c1.date_input(f"{cur_extra_tx} 開始日*", value=st.session_state.extra_tx_start, key="extra_start")
            st.session_state.extra_tx_ongoing = etx_c2.checkbox(f"{cur_extra_tx} 継続中", value=st.session_state.extra_tx_ongoing, key="extra_ongoing")
            if not st.session_state.extra_tx_ongoing:
                st.session_state.extra_tx_end = etx_c2.date_input(f"{cur_extra_tx} 終了日*", value=st.session_state.extra_tx_end, key="extra_end")

        if cur_extra_tx in ["治験（HER2標的ADC、TROP2標的ADC、その他）", "その他"]:
            st.session_state.pfs_extra_tx_detail = st.text_area("詳細*", key="t_extra")

# --- 3. 有害事象 ---
st.markdown('<div class="juog-header">3. 有害事象・合併症</div>', unsafe_allow_html=True)
st.session_state.has_event = st.checkbox("特記すべき有害事象や合併症がある", value=st.session_state.has_event)
if st.session_state.has_event:
    ec1, ec2 = st.columns(2)
    cd_opts = ["なし", "Grade I", "Grade II", "Grade IIIa", "Grade IIIb", "Grade IVa", "Grade IVb", "Grade V"]
    st.session_state.cd_grade = ec1.selectbox("Clavien-Dindo分類*", cd_opts, index=get_idx(cd_opts, st.session_state.cd_grade), help=HELP_CD)
    st.session_state.ae_status = ec2.text_area("有害事象の詳細（CTCAE準拠）*", value=st.session_state.ae_status, placeholder="発現日、内容、処置、転帰を記入")
    st.markdown("<div style='text-align: right;'><small>参照： <a href='https://jcog.jp/assets/CTCAEv6J_20260301_v28_0.pdf' target='_blank'>CTCAE v6.0 日本語訳 (JCOG版)</a></small></div>", unsafe_allow_html=True)

# --- 4. 採血 (12/24ヶ月目必須) ---
is_lab_req = st.session_state.report_timing in ["術後12ヶ月後", "術後24ヶ月後"]
st.markdown(f'<div class="juog-header">4. 採血検査データ {"(12/24ヶ月目：必須)" if is_lab_req else "(任意)"}</div>', unsafe_allow_html=True)
show_labs = st.checkbox("採血結果を入力する", value=is_lab_req)
if show_labs:
    bc1, bc2 = st.columns(2)
    lab_list = [("WBC", "/μL", 1.0), ("Hb", "g/dL", 0.1), ("PLT", "x10^4/μL", 1.0), ("AST", "U/L", 1.0), ("ALT", "U/L", 1.0), ("Alb", "g/dL", 0.1), ("LDH", "U/L", 1.0), ("Cre", "mg/dL", 0.01), ("eGFR", "mL/min", 0.1), ("CRP", "mg/dL", 0.01)]
    for i, (n, u, s) in enumerate(lab_list):
        col = bc1 if i < 5 else bc2
        st.session_state[f"lab_{n}"] = col.number_input(f"{n} ({u})", value=st.session_state[f"lab_{n}"], step=s, key=f"k_{n}")
    f1, f2, f3, f4, f5 = st.columns(5)
    st.session_state.lab_Neutro = f1.number_input("Neutro", value=st.session_state.lab_Neutro)
    st.session_state.lab_Lympho = f2.number_input("Lympho", value=st.session_state.lab_Lympho)
    st.session_state.lab_Mono = f3.number_input("Mono", value=st.session_state.lab_Mono)
    st.session_state.lab_Eosino = f4.number_input("Eosino", value=st.session_state.lab_Eosino)
    st.session_state.lab_Baso = f5.number_input("Baso", value=st.session_state.lab_Baso)

# --- 5. 生存状況・現在の治療状況 ---
st.markdown('<div class="juog-header">5. 生存状況・現在の治療状況</div>', unsafe_allow_html=True)
scol1, scol2 = st.columns(2)
with scol1:
    st.session_state.status_alive = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive=="生存" else 1 if st.session_state.status_alive=="死亡" else None), horizontal=True)
    if st.session_state.status_alive == "生存":
        st.session_state.final_date = st.date_input("最終生存確認日*", value=st.session_state.final_date)
    elif st.session_state.status_alive == "死亡":
        st.session_state.death_date = st.date_input("死亡日*", value=st.session_state.death_date)
        st.session_state.death_cause = st.selectbox("死因*", ["選択してください", "癌死 (原疾患による)", "治療関連死", "他病死", "不明"], index=get_idx(["選択してください", "癌死 (原疾患による)", "治療関連死", "他病死", "不明"], st.session_state.death_cause))

with scol2:
    if st.session_state.status_alive == "生存":
        tx_opts = [
            "選択してください", 
            "無治療（経過観察）", 
            "術前からのEVP継続投与", 
            "術前からのEV単独継続（間欠療法等を含む）", 
            "術前からのペムブロリズマブ単剤継続", 
            "上記再発に対する治療を継続中", 
            "その他"
        ]
        st.session_state.treat_status = st.selectbox("現在の治療状況*", tx_opts, index=get_idx(tx_opts, st.session_state.treat_status))
        if st.session_state.treat_status == "その他":
            st.session_state.treat_status_detail = st.text_input("詳細*", value=st.session_state.treat_status_detail, key="tx_cur_other")

st.divider()

# --- 6. 送信バリデーション ---
if st.button("🚀 事務局へ確定送信", type="primary", use_container_width=True):
    err = []
    d = st.session_state
    if d.facility_name == "選択してください": err.append("・施設名")
    if not d.patient_id: err.append("・識別コード")
    if d.report_timing == "選択してください": err.append("・報告時期")
    if not d.op_date: err.append("・手術日（非施行例は予定日）") # エラー文言も修正
    
    if d.status_alive is None: err.append("・生存状況")
    if d.pfs_intra == "あり":
        if any(x in d.pfs_intra_tx for x in SURGERY_LIST) and not d.intra_op_date: err.append("・手術・処置日(内)")
        if any(x in d.pfs_intra_tx for x in DRUG_LIST) and not d.intra_tx_start: err.append("・薬物開始日(内)")
    if is_lab_req and (not show_labs or d.lab_WBC is None): err.append("・採血データ(必須時期)")

    if err: st.error("入力不備があります：\n" + "\n".join(err))
    else:
        if send_email("CRF_DATA", d.patient_id, d.facility_name, d.reporter_email):
            st.success("確定送信されました。臨床研究へのご協力ありがとうございます。"); st.balloons()

import streamlit as st
import json
from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# --- ページ設定 ---
st.set_page_config(page_title="JUOG UTUC_Consolidative 定期経過報告 CRF", layout="wide")

# --- JUOG専用デザインCSS ---
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

# --- 定数・リスト定義 ---
FACILITY_LIST = ["選択してください", "愛知県がんセンター", "秋田大学", "愛媛大学", "大分大学", "大阪公立大学", "大阪大学", "大阪府済生会野江病院", "岡山大学", "香川大学", "鹿児島大学", "関西医科大学", "岐阜大学", "九州大学病院", "京都大学", "久留米大学", "神戸大学", "国立がん研究センター中央病院", "国立病院機構四国がんセンター", "札幌医科大学", "千葉大学", "筑波大学", "東京科学大学", "東京慈恵会医科大学", "東京慈恵会医科大学附属柏病院", "東北大学", "鳥取大学", "富山大学", "長崎大学病院", "名古屋大学", "奈良県立医科大学", "新潟大学大学院 医歯学総合研究科", "浜松医科大学", "原三信病院", "兵庫医科大学", "弘前大学", "北海道大学", "三重大学", "横浜市立大学", "琉球大学", "和歌山県立医科大学", "その他"]

SURGERY_LIST = ["TURBT", "上部尿路内視鏡的治療", "手術（腎尿管全摘等）", "転移巣切除"]
DRUG_LIST = ["BCG注入療法", "抗がん剤注入療法", "プラチナ製剤併用療法（GC等）", "維持療法（アベルマブ等）", "EVP再開", "ペムブロリズマブ単剤", "ニボルマブ単剤", "放射線治療", "その他"]

HELP_CYTO = """【尿細胞診結果】
* Negative: 陰性（クラスI・II）
* AUC: 非定型細胞
* SHGUC: 高異型度癌疑い
* HGUC: 高異型度癌（クラスIV・V相当）
* LGUC: 低異型度腫瘍"""

# --- セッション状態初期化 ---
if 'init_followup_perfect' not in st.session_state:
    st.session_state['init_followup_perfect'] = True
    LAB_KEYS = ["wbc_fu", "hb_fu", "plt_fu", "ast_fu", "alt_fu", "ldh_fu", "alb_fu", "cre_fu", "egfr_fu", "crp_fu", "neutro_fu", "lympho_fu", "mono_fu", "eosino_fu", "baso_fu"]
    defaults = {
        "facility_name": "選択してください", "patient_id": "", "reporter_email": "",
        "report_period": "選択してください", "op_date_fu": None, "eval_date_fu": None,
        "vital_abnormality_fu": None, "vital_detail_fu": "", "cytology_fu": "選択してください",
        "has_ctcae_fu": False, "ae_status_fu": "", 
        "adj_plan_fu": "選択してください", "adj_other_fu": "", "adj_start_fu": None, "adj_end_fu": None, "adj_ongoing_fu": False,
        "pfs_intra_status": None, "pfs_intra_date": None, "pfs_intra_site": [], "pfs_intra_site_other": "", "pfs_intra_tx": [], "pfs_intra_tx_other": "", "intra_op_date_fu": None, "intra_tx_start_fu": None, "intra_tx_end_fu": None, "intra_tx_ongoing_fu": False, "pfs_intra_path_fu": "",
        "pfs_recist_status": None, "pfs_recist_date": None, "pfs_recist_site": [], "pfs_recist_site_other": "", "pfs_recist_tx": "選択してください", "pfs_recist_tx_detail": "", "extra_op_date_fu": None, "extra_tx_start_fu": None, "extra_tx_end_fu": None, "extra_tx_ongoing_fu": False,
        "status_alive_fu": None, "final_visit_date_fu": None, "death_cause_fu": "選択してください", "death_date_fu": None
    }
    for lab in LAB_KEYS: defaults[lab] = None
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def get_idx(options, value):
    try: return options.index(value)
    except: return 0

def send_email(report_content, pid, facility, user_email=None):
    try:
        mail_user = st.secrets["email"]["user"]; mail_pass = st.secrets["email"]["pass"]
        to_addrs = ["urosec@kmu.ac.jp", "yoshida.tks@kmu.ac.jp"]
        if user_email: to_addrs.append(user_email)
        msg = MIMEMultipart(); msg['From'] = mail_user; msg['To'] = ", ".join(to_addrs)
        msg['Subject'] = f"【JUOG 定期経過報告】（{facility} / ID: {pid}）"
        msg.attach(MIMEText(report_content, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465); server.login(mail_user, mail_pass); server.send_message(msg); server.quit()
        return True
    except: return False

st.title("JUOG UTUC_Consolidative 定期経過報告 CRF")

# --- 1. 基本情報・評価期間 ---
st.markdown('<div class="juog-header">1. 基本情報・評価対象期間</div>', unsafe_allow_html=True)
col_h1, col_h2 = st.columns(2)
with col_h1:
    st.session_state.facility_name = st.selectbox("施設名*", FACILITY_LIST, index=get_idx(FACILITY_LIST, st.session_state.facility_name))
    st.session_state.patient_id = st.text_input("研究対象者識別コード*", value=st.session_state.patient_id)
with col_h2:
    st.session_state.reporter_email = st.text_input("報告者メールアドレス*", value=st.session_state.reporter_email)
    st.session_state.op_date_fu = st.date_input("手術実施日*", value=st.session_state.op_date_fu)
    
    # 報告のタイミングを明示
    period_opts = ["選択してください", "術後6ヶ月", "術後12ヶ月", "術後18ヶ月", "術後24ヶ月"]
    st.session_state.report_period = st.selectbox("報告のタイミング*", period_opts, index=get_idx(period_opts, st.session_state.report_period))

tab1, tab2, tab3, tab4 = st.tabs(["🩺 身体所見・検査", "📋 治療状況・安全性", "🖼 再発評価 (PFS)", "⚖️ 生存確認 (OS)"])

with tab1:
    st.markdown('<div class="juog-header">身体所見・検査データ</div>', unsafe_allow_html=True)
    c_top1, c_top2 = st.columns(2)
    with c_top1:
        st.session_state.eval_date_fu = st.date_input("評価実施日(来院日)*", value=st.session_state.eval_date_fu)
        st.session_state.vital_abnormality_fu = st.radio("身体所見の異常*", ["異常なし", "異常あり"], index=(0 if st.session_state.vital_abnormality_fu=="異常なし" else 1 if st.session_state.vital_abnormality_fu=="異常あり" else None), horizontal=True)
        if st.session_state.vital_abnormality_fu == "異常あり": st.session_state.vital_detail_fu = st.text_input("異常の詳細*")
    with c_top2:
        cyto_opts = ["選択してください", "Negative (クラスI・II)", "AUC (非定型細胞)", "SHGUC (高異型度癌疑い)", "HGUC (クラスIV・V相当)", "LGUC (低異型度腫瘍)", "判定不能", "未実施"]
        st.session_state.cytology_fu = st.selectbox("尿細胞診結果*", cyto_opts, index=get_idx(cyto_opts, st.session_state.cytology_fu), help=HELP_CYTO)

    st.markdown("---")
    bc1, bc2 = st.columns(2)
    with bc1:
        st.session_state.wbc_fu = st.number_input("WBC (/μL)*", value=st.session_state.wbc_fu)
        st.session_state.hb_fu = st.number_input("Hb (g/dL)*", value=st.session_state.hb_fu)
        st.session_state.plt_fu = st.number_input("PLT (x10^4/μL)*", value=st.session_state.plt_fu)
        st.session_state.ast_fu = st.number_input("AST (U/L)*", value=st.session_state.ast_fu)
        st.session_state.alt_fu = st.number_input("ALT (U/L)*", value=st.session_state.alt_fu)
    with bc2:
        st.session_state.ldh_fu = st.number_input("LDH (U/L)*", value=st.session_state.ldh_fu)
        st.session_state.alb_fu = st.number_input("Alb (g/dL)*", value=st.session_state.alb_fu)
        st.session_state.cre_fu = st.number_input("Cre (mg/dL)*", value=st.session_state.cre_fu)
        st.session_state.egfr_fu = st.number_input("eGFR (mL/min)*", value=st.session_state.egfr_fu)
        st.session_state.crp_fu = st.number_input("CRP (mg/dL)*", value=st.session_state.crp_fu)

    st.markdown("**白血球分画 (%)**")
    d1, d2, d3, d4, d5 = st.columns(5)
    st.session_state.neutro_fu = d1.number_input("Neutro*", value=st.session_state.neutro_fu)
    st.session_state.lympho_fu = d2.number_input("Lympho*", value=st.session_state.lympho_fu)
    st.session_state.mono_fu = d3.number_input("Mono*", value=st.session_state.mono_fu)
    st.session_state.eosino_fu = d4.number_input("Eosino*", value=st.session_state.eosino_fu)
    st.session_state.baso_fu = d5.number_input("Baso*", value=st.session_state.baso_fu)

with tab2:
    st.markdown('<div class="juog-header">2. 術後補助療法・安全性</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    with c1:
        # EVP継続・ペムブロ継続を含んだ最新のリスト
        adj_opts = ["選択してください", "無治療（経過観察）", "EVP継続投与", "ペムブロ単剤維持", "ニボルマブ単剤（術後補助療法）", "GC療法（術後補助療法）", "GCarbo療法（術後補助療法）", "放射線治療", "治験・その他薬物療法", "その他"]
        st.session_state.adj_plan_fu = st.selectbox("現在の治療実施状況（補助療法等）*", adj_opts, index=get_idx(adj_opts, st.session_state.adj_plan_fu))
        
        if st.session_state.adj_plan_fu not in ["選択してください", "無治療（経過観察）"]:
            if st.session_state.adj_plan_fu in ["治験・その他薬物療法", "その他"]:
                st.session_state.adj_other_fu = st.text_input("治療の詳細*", value=st.session_state.adj_other_fu)
            
            st.markdown("###### 治療日程")
            ax1, ax2 = st.columns(2)
            # 変数名とkey名が被らないように設定済み
            st.session_state.adj_start_fu = ax1.date_input(f"{st.session_state.adj_plan_fu} 開始日*", value=st.session_state.adj_start_fu, key="k_adj_start_fu")
            st.session_state.adj_ongoing_fu = ax2.checkbox("現在も継続中", value=st.session_state.adj_ongoing_fu, key="k_adj_ongoing_fu")
            
            if not st.session_state.adj_ongoing_fu:
                st.session_state.adj_end_fu = ax2.date_input(f"{st.session_state.adj_plan_fu} 終了日*", value=st.session_state.adj_end_fu, key="k_adj_end_fu")
            else:
                st.session_state.adj_end_fu = None

    with c2:
        st.session_state.has_ctcae_fu = st.checkbox("薬剤関連等の有害事象（CTCAE準拠）を報告する", value=st.session_state.has_ctcae_fu)
        if st.session_state.has_ctcae_fu:
            st.session_state.ae_status_fu = st.text_area("有害事象の詳細*", value=st.session_state.ae_status_fu, placeholder="発現日、内容、重症度、処置、転帰などを記入")
            st.markdown("<div style='text-align: right;'><small>参照： <a href='https://jcog.jp/assets/CTCAEv6J_20260301_v28_0.pdf' target='_blank'>CTCAE v6.0 日本語訳 (JCOG版)</a></small></div>", unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="juog-header">3. 再発評価 (PFS判定)</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**【尿路内再発】**")
        st.session_state.pfs_intra_status = st.radio("尿路内再発の有無*", ["なし", "あり"], index=(0 if st.session_state.pfs_intra_status=="なし" else 1 if st.session_state.pfs_intra_status=="あり" else None), horizontal=True, key="r_intra_fu")
        if st.session_state.pfs_intra_status == "あり":
            st.session_state.pfs_intra_date = st.date_input("診断日（組織・画像・膀胱鏡等）*", value=st.session_state.pfs_intra_date, key="d_intra_fu")
            st.session_state.pfs_intra_site = st.multiselect("再発部位*", ["膀胱", "対側腎盂", "対側尿管", "同側残存尿管", "その他"], default=st.session_state.pfs_intra_site)
            if "その他" in st.session_state.pfs_intra_site:
                st.session_state.pfs_intra_site_other = st.text_input("部位の詳細*", value=st.session_state.pfs_intra_site_other, key="site_intra_other_fu")
            
            intra_tx_opts = ["経過観察", "TURBT", "BCG注入療法", "抗がん剤注入療法", "上部尿路内視鏡的治療", "手術（腎尿管全摘等）", "その他"]
            st.session_state.pfs_intra_tx = st.multiselect("実施した治療*", intra_tx_opts, default=st.session_state.pfs_intra_tx)
            
            selected_intra_surgeries = [x for x in st.session_state.pfs_intra_tx if x in SURGERY_LIST]
            if selected_intra_surgeries:
                label_op = f"{' + '.join(selected_intra_surgeries)} 実施日*"
                st.session_state.intra_op_date_fu = st.date_input(label_op, value=st.session_state.intra_op_date_fu, key="i_op_fu")
                st.session_state.pfs_intra_path_fu = st.text_area("組織型、Grade、pTNM分類 等*", value=st.session_state.pfs_intra_path_fu, key="i_path_fu")
            
            selected_intra_drugs = [x for x in st.session_state.pfs_intra_tx if x in DRUG_LIST]
            if selected_intra_drugs:
                label_drug = f"{' + '.join(selected_intra_drugs)}"
                ix1, ix2 = st.columns(2)
                st.session_state.intra_tx_start_fu = ix1.date_input(f"{label_drug} 開始日*", value=st.session_state.intra_tx_start_fu, key="k_i_start_fu")
                st.session_state.intra_tx_ongoing_fu = ix2.checkbox(f"{label_drug} 継続中", value=st.session_state.intra_tx_ongoing_fu, key="k_i_ongoing_fu")
                if not st.session_state.intra_tx_ongoing_fu:
                    st.session_state.intra_tx_end_fu = ix2.date_input(f"{label_drug} 終了日*", value=st.session_state.intra_tx_end_fu, key="k_i_end_fu")
                else:
                    st.session_state.intra_tx_end_fu = None
            
            if "その他" in st.session_state.pfs_intra_tx:
                st.session_state.pfs_intra_tx_other = st.text_input("治療の「その他」の詳細*", value=st.session_state.pfs_intra_tx_other, key="tx_intra_other_fu")

    with c2:
        st.markdown("**【尿路外再発】**")
        st.session_state.pfs_recist_status = st.radio("尿路外再発の有無*", ["なし", "あり"], index=(0 if st.session_state.pfs_recist_status=="なし" else 1 if st.session_state.pfs_recist_status=="あり" else None), horizontal=True, key="r_extra_fu")
        if st.session_state.pfs_recist_status == "あり":
            st.session_state.pfs_recist_date = st.date_input("診断日（画像・組織等）*", value=st.session_state.pfs_recist_date, key="d_extra_fu")
            st.session_state.pfs_recist_site = st.multiselect("再発部位*", ["肺", "リンパ節", "肝", "骨", "手術局所", "その他"], default=st.session_state.pfs_recist_site)
            if "その他" in st.session_state.pfs_recist_site:
                st.session_state.pfs_recist_site_other = st.text_input("部位の詳細*", value=st.session_state.pfs_recist_site_other, key="site_extra_other_fu")
            
            extra_tx_opts = ["選択してください", "プラチナ製剤併用療法（GC等）", "維持療法（アベルマブ等）", "EVP再開", "ペムブロリズマブ単剤", "ニボルマブ単剤", "転移巣切除", "放射線治療", "その他"]
            st.session_state.pfs_recist_tx = st.selectbox("実施治療*", extra_tx_opts, index=get_idx(extra_tx_opts, st.session_state.pfs_recist_tx))
            
            cur_extra_tx = st.session_state.pfs_recist_tx
            if cur_extra_tx in ["転移巣切除"]:
                st.session_state.extra_op_date_fu = st.date_input(f"{cur_extra_tx} 実施日*", value=st.session_state.extra_op_date_fu, key="e_op_fu")
            
            if cur_extra_tx in DRUG_LIST:
                ex1, ex2 = st.columns(2)
                st.session_state.extra_tx_start_fu = ex1.date_input(f"{cur_extra_tx} 開始日*", value=st.session_state.extra_tx_start_fu, key="k_e_start_fu")
                st.session_state.extra_tx_ongoing_fu = ex2.checkbox(f"{cur_extra_tx} 継続中", value=st.session_state.extra_tx_ongoing_fu, key="k_e_ongoing_fu")
                if not st.session_state.extra_tx_ongoing_fu:
                    st.session_state.extra_tx_end_fu = ex2.date_input(f"{cur_extra_tx} 終了日*", value=st.session_state.extra_tx_end_fu, key="k_e_end_fu")
                else:
                    st.session_state.extra_tx_end_fu = None

            if cur_extra_tx in ["その他"]:
                st.session_state.pfs_recist_tx_detail = st.text_input("詳細*", value=st.session_state.pfs_recist_tx_detail, key="t_extra_other_fu")

with tab4:
    st.markdown('<div class="juog-header">4. 生存状況確認 (Overall Survival)</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.status_alive_fu = st.radio("生存状況*", ["生存", "死亡"], index=(0 if st.session_state.status_alive_fu=="生存" else 1 if st.session_state.status_alive_fu=="死亡" else None), horizontal=True)
        if st.session_state.status_alive_fu == "生存":
            st.session_state.final_visit_date_fu = st.date_input("最終生存確認日*", value=st.session_state.final_visit_date_fu)
    with c2:
        if st.session_state.status_alive_fu == "死亡":
            st.session_state.death_date_fu = st.date_input("死亡日*", value=st.session_state.death_date_fu)
            st.session_state.death_cause_fu = st.selectbox("死因*", ["選択してください", "癌死 (原疾患による)", "治療関連死", "他病死", "不明"], index=get_idx(["選択してください", "癌死 (原疾患による)", "治療関連死", "他病死", "不明"], st.session_state.death_cause_fu))

    st.divider()

    # --- 送信バリデーション ---
    if st.button(f"🚀 {st.session_state.report_period if st.session_state.report_period != '選択してください' else '定期'}データを確定送信", type="primary", use_container_width=True):
        err = []
        d = st.session_state
        if d.facility_name == "選択してください": err.append("・施設名")
        if not d.patient_id: err.append("・識別コード")
        if d.report_period == "選択してください": err.append("・報告のタイミング")
        if not d.op_date_fu: err.append("・手術実施日")
        if not d.eval_date_fu: err.append("・評価実施日(来院日)")
            
        if d.has_ctcae_fu and not d.ae_status_fu: err.append("・薬剤関連等 有害事象の詳細")
        
        if d.adj_plan_fu == "選択してください": err.append("・現在の治療実施状況")
        if d.adj_plan_fu not in ["選択してください", "無治療（経過観察）"]:
            if not d.adj_start_fu: err.append("・治療の開始日")
            if not d.adj_ongoing_fu and not d.adj_end_fu: err.append("・治療の終了日")
            
        if d.pfs_intra_status == "あり":
            if not d.pfs_intra_tx: err.append("・尿路内再発の治療内容")
            if any(x in d.pfs_intra_tx for x in DRUG_LIST):
                if not d.intra_tx_start_fu: err.append("・尿路内薬物療法の開始日")
                if not d.intra_tx_ongoing_fu and not d.intra_tx_end_fu: err.append("・尿路内薬物療法の終了日")
                
        if d.pfs_recist_status == "あり":
            if d.pfs_recist_tx == "選択してください": err.append("・尿路外再発の治療内容")
            if d.pfs_recist_tx in DRUG_LIST:
                if not d.extra_tx_start_fu: err.append("・尿路外薬物療法の開始日")
                if not d.extra_tx_ongoing_fu and not d.extra_tx_end_fu: err.append("・尿路外薬物療法の終了日")

        if d.status_alive_fu is None: err.append("・生存状況")
        
        if err: st.error("入力不備があります：\n" + "\n".join(err))
        else:
            rep = f"【JUOG {d.report_period} 報告】ID:{d.patient_id} / 施設:{d.facility_name}\n生存:{d.status_alive_fu} / PFS判定済"
            if send_email(rep, d.patient_id, d.facility_name, d.reporter_email):
                st.success(f"{d.report_period} のデータが確定送信されました。"); st.balloons()

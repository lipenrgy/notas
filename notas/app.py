"""
app.py
TriageNFe — Dashboard de Triagem Automática de Notas Fiscais Eletrônicas
Desenvolvido com Streamlit + lxml + Pandas

Execução: streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Garante importações relativas ao diretório do projeto ──────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from parser.nfe_parser import NFeParser, listar_xmls_pasta
from parser.pdf_parser import parse_pdf, parse_imagem, verificar_dependencias
from ai.gemini_assistant import configurar_api, analisar_inconsistencias
from reports.exporter import exportar_csv, exportar_excel
from utils.formatters import (
    formatar_cnpj_display,
    formatar_data,
    formatar_moeda,
    formatar_chave,
)
from validation.validators import NFeValidator

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="TriageNFe | Triagem Inteligente de Notas Fiscais",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# CSS PERSONALIZADO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Esconde elementos padrão Streamlit ── */
#MainMenu, footer { visibility: hidden; }
.stDeployButton { display: none !important; }

/* ── Container principal ── */
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1380px;
}

/* ══ HEADER ══════════════════════════════════════════════════════════════ */
.app-header {
    background: linear-gradient(135deg, #0d1b2a 0%, #1b2a3b 45%, #0f3460 100%);
    border-radius: 18px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.8rem;
    border: 1px solid rgba(99,179,237,0.18);
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.app-header::after {
    content: '';
    position: absolute;
    top: -80px; right: -60px;
    width: 350px; height: 350px;
    background: radial-gradient(circle, rgba(99,179,237,0.12) 0%, transparent 65%);
    pointer-events: none;
}
.app-header::before {
    content: '';
    position: absolute;
    bottom: -100px; left: 20%;
    width: 250px; height: 250px;
    background: radial-gradient(circle, rgba(159,122,234,0.08) 0%, transparent 65%);
    pointer-events: none;
}
.header-title {
    font-size: 2.1rem;
    font-weight: 800;
    background: linear-gradient(90deg, #63b3ed, #90cdf4, #b794f4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.4rem 0;
    line-height: 1.2;
}
.header-sub {
    color: rgba(255,255,255,0.5);
    font-size: 0.92rem;
    margin: 0;
    letter-spacing: 0.02em;
}
.header-tags {
    margin-top: 1rem;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.header-tag {
    background: rgba(99,179,237,0.1);
    border: 1px solid rgba(99,179,237,0.25);
    border-radius: 999px;
    padding: 0.2rem 0.75rem;
    font-size: 0.75rem;
    color: #90cdf4;
    font-weight: 500;
}

/* ══ MÉTRICAS ════════════════════════════════════════════════════════════ */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.metric-card {
    background: linear-gradient(160deg, #1e293b, #151e2d);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    text-align: center;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}
.metric-total::before  { background: linear-gradient(90deg, #63b3ed, #4299e1); border-color: rgba(99,179,237,0.25) !important; }
.metric-ok::before     { background: linear-gradient(90deg, #68d391, #48bb78); border-color: rgba(104,211,145,0.25) !important; }
.metric-aviso::before  { background: linear-gradient(90deg, #f6e05e, #ecc94b); border-color: rgba(246,224,94,0.25) !important; }
.metric-erro::before   { background: linear-gradient(90deg, #fc8181, #f56565); border-color: rgba(252,129,129,0.25) !important; }
.metric-valor::before  { background: linear-gradient(90deg, #b794f4, #9f7aea); border-color: rgba(183,148,244,0.25) !important; }

.metric-card:hover.metric-total  { border-color: rgba(99,179,237,0.35); }
.metric-card:hover.metric-ok     { border-color: rgba(104,211,145,0.35); }
.metric-card:hover.metric-aviso  { border-color: rgba(246,224,94,0.35); }
.metric-card:hover.metric-erro   { border-color: rgba(252,129,129,0.35); }
.metric-card:hover.metric-valor  { border-color: rgba(183,148,244,0.35); }

.metric-icon { font-size: 1.5rem; margin-bottom: 0.5rem; }
.metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.3rem;
}
.metric-label {
    font-size: 0.72rem;
    color: rgba(255,255,255,0.45);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 500;
}
.metric-sub {
    font-size: 0.8rem;
    color: rgba(255,255,255,0.25);
    margin-top: 0.2rem;
}
.metric-total .metric-value  { color: #63b3ed; }
.metric-ok .metric-value     { color: #68d391; }
.metric-aviso .metric-value  { color: #f6e05e; }
.metric-erro .metric-value   { color: #fc8181; }
.metric-valor .metric-value  { color: #b794f4; font-size: 1.5rem; }

/* ══ BADGES DE STATUS ════════════════════════════════════════════════════ */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.22rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    border: 1px solid;
}
.badge-ok    { background: rgba(104,211,145,0.12); color: #68d391; border-color: rgba(104,211,145,0.3); }
.badge-aviso { background: rgba(246,224,94,0.12);  color: #f6e05e; border-color: rgba(246,224,94,0.3); }
.badge-erro  { background: rgba(252,129,129,0.12); color: #fc8181; border-color: rgba(252,129,129,0.3); }

/* ══ ALERTAS ══════════════════════════════════════════════════════════════ */
.alert-item {
    padding: 0.45rem 0.85rem;
    border-radius: 7px;
    margin: 0.25rem 0;
    font-size: 0.83rem;
    font-weight: 500;
    border-left: 3px solid;
}
.alert-erro  { background: rgba(252,129,129,0.08); color: #fc8181; border-left-color: #fc8181; }
.alert-aviso { background: rgba(246,224,94,0.08);  color: #f6e05e; border-left-color: #f6e05e; }
.alert-ok    { background: rgba(104,211,145,0.08); color: #68d391; border-left-color: #68d391; }

/* ══ GRID DE CAMPOS ══════════════════════════════════════════════════════ */
.field-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    margin-top: 0.8rem;
}
.field-item {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 0.6rem 0.85rem;
}
.field-label {
    font-size: 0.68rem;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 0.2rem;
}
.field-value {
    font-size: 0.88rem;
    color: rgba(255,255,255,0.85);
    font-weight: 500;
    word-break: break-all;
}
.field-value.mono { font-family: 'Courier New', monospace; font-size: 0.78rem; }

/* ══ SECÇÃO HEADER ════════════════════════════════════════════════════════ */
.section-header {
    font-size: 1rem;
    font-weight: 600;
    color: #90cdf4;
    margin: 1.8rem 0 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* ══ CARD DE NOTA ════════════════════════════════════════════════════════ */
.nf-card-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}
.nf-number { font-weight: 700; font-size: 1rem; color: white; }
.nf-emitente { color: rgba(255,255,255,0.55); font-size: 0.88rem; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nf-valor { font-weight: 600; color: #b794f4; font-size: 0.95rem; }
.nf-data { color: rgba(255,255,255,0.4); font-size: 0.8rem; }

/* ══ BARRA DE PROGRESSO ══════════════════════════════════════════════════ */
.progress-bar-container {
    background: rgba(255,255,255,0.07);
    border-radius: 999px;
    height: 6px;
    margin-top: 0.5rem;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.4s ease;
}
.pb-ok    { background: linear-gradient(90deg, #68d391, #48bb78); }
.pb-aviso { background: linear-gradient(90deg, #f6e05e, #ecc94b); }
.pb-erro  { background: linear-gradient(90deg, #fc8181, #f56565); }

/* ══ EMPTY STATE ═════════════════════════════════════════════════════════ */
.empty-state {
    text-align: center;
    padding: 5rem 2rem;
    color: rgba(255,255,255,0.2);
}
.empty-icon { font-size: 5rem; margin-bottom: 1.2rem; filter: grayscale(1) opacity(0.4); }
.empty-title { font-size: 1.3rem; font-weight: 600; margin-bottom: 0.4rem; color: rgba(255,255,255,0.3); }
.empty-sub { font-size: 0.9rem; }

/* ══ DIVIDER ════════════════════════════════════════════════════════════ */
.divider { border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 1.5rem 0; }

/* ══ STREAMLIT OVERRIDES ════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: transparent;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: rgba(255,255,255,0.45);
    border-radius: 8px 8px 0 0;
    font-size: 0.88rem;
    font-weight: 500;
    padding: 0.5rem 1.2rem;
    transition: color 0.2s, background 0.2s;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,179,237,0.12) !important;
    color: #90cdf4 !important;
}
.stExpander {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    margin-bottom: 0.6rem !important;
    background: rgba(30,41,59,0.5) !important;
}
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(99,179,237,0.25);
    border-radius: 12px;
    padding: 1rem;
    background: rgba(99,179,237,0.02);
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(99,179,237,0.45);
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if 'df_result' not in st.session_state:
    st.session_state.df_result = None
if 'total_processados' not in st.session_state:
    st.session_state.total_processados = 0
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ''

# ══════════════════════════════════════════════════════════════════════════════
# BARRA LATERAL (SIDEBAR) - CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🤖 Inteligência Artificial")
    st.markdown("Configure sua chave do **Google Gemini** para análises de erros fiscais.")
    api_key_input = st.text_input("Gemini API Key", type="password", value=st.session_state.gemini_api_key, placeholder="AIzaSy...")
    
    if api_key_input != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = api_key_input
        if configurar_api(api_key_input):
            st.success("✅ API configurada com sucesso!")
        else:
            st.error("❌ Chave inválida ou vazia.")
            
    st.markdown("---")
    st.markdown("💡 *Como usar:*\n1. Processo os XMLs ou PDFs.\n2. Se houver AVISO ou ERRO, abra os detalhes da nota.\n3. Clique em **✨ Analisar com IA**.")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1 class="header-title">🧾 TriageNFe</h1>
    <p class="header-sub">
        Triagem automática de Notas Fiscais Eletrônicas · Validação de CNPJ ·
        Detecção de duplicatas · Análise de inconsistências fiscais
    </p>
    <div class="header-tags">
        <span class="header-tag">📂 XML NF-e SEFAZ</span>
        <span class="header-tag">🔍 Validação CNPJ</span>
        <span class="header-tag">🔁 Detecção de Duplicatas</span>
        <span class="header-tag">📊 Relatório CSV / Excel</span>
        <span class="header-tag">✅ 12 Regras Fiscais</span>
        <span class="header-tag">📁 Modo Pasta</span>
        <span class="header-tag">🇧🇷 Padrão NF-e v4.00</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO DE PROCESSAMENTO COMPARTILHADA (deve ficar antes das abas)
# ══════════════════════════════════════════════════════════════════════════════
def _processar_lote(fontes, modo: str) -> None:
    """
    Processa um lote de NF-e a partir de múltiplas fontes.

    Args:
        fontes: Lista de UploadedFile (modo='upload') ou Path (modo='pasta')
        modo:   'upload' ou 'pasta'

    Roteamento automático por extensão:
        .xml  → NFeParser  (parsing XML SEFAZ)
        .pdf  → parse_pdf  (pdfplumber + regex)
        .png / .jpg / .jpeg / .tiff → parse_imagem (OCR)
    """
    parser_xml = NFeParser()
    validator  = NFeValidator()

    n_total      = len(fontes)
    progress_text = st.empty()
    progress_bar  = st.progress(0)
    dados = []

    for i, fonte in enumerate(fontes):
        progresso = (i + 1) / n_total
        progress_bar.progress(progresso)

        nome = getattr(fonte, 'name', str(fonte))
        nome_curto = nome.split('\\')[-1].split('/')[-1]
        ext = nome_curto.rsplit('.', 1)[-1].lower() if '.' in nome_curto else ''

        progress_text.markdown(
            f"⏳ Processando **{nome_curto}** — {i + 1} de {n_total}..."
        )

        if ext == 'xml':
            dados.append(parser_xml.parse_file(fonte))
        elif ext == 'pdf':
            dados.append(parse_pdf(fonte))
        elif ext in ('png', 'jpg', 'jpeg', 'tiff', 'bmp'):
            dados.append(parse_imagem(fonte))
        else:
            dados.append({
                'arquivo': nome_curto,
                'parse_ok': False,
                'erro_parse': f'Formato não suportado: .{ext}. Use XML, PDF ou PNG/JPG.',
                **{k: None for k in [
                    'chNFe','nNF','serie','dhEmi','natOp','mod','tpNF','cfop','ncm',
                    'cnpj_emit','nome_emit','uf_emit','cnpj_dest','cpf_dest',
                    'nome_dest','uf_dest','vNF','vICMS','vPIS','vCOFINS','vBC',
                    'vST','vFrete','pICMS','temCobranca',
                ]},
                'itens_valor_zero': [],
                'qtd_itens': 0,
            })

    progress_text.markdown("🧮 Aplicando 12 regras de validação fiscal...")
    df = pd.DataFrame(dados)
    df = validator.validate(df)

    progress_bar.empty()
    progress_text.empty()

    st.session_state.df_result = df
    st.session_state.total_processados = n_total
    st.success(
        f"✅ Processamento concluído! **{n_total} nota(s)** analisada(s) com 12 regras fiscais."
    )
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO DE ENTRADA — ABAS: UPLOAD DE ARQUIVO | PASTA LOCAL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📥 Carregar Notas Fiscais</div>', unsafe_allow_html=True)

tab_upload, tab_pasta = st.tabs(["📄 Upload de Arquivos", "📁 Processar Pasta"])

# ── ABA 1: Upload de Arquivos ─────────────────────────────────────────────────
with tab_upload:
    col_upload, col_dica = st.columns([3, 1])

    with col_upload:
        uploaded_files = st.file_uploader(
            label="Arraste os arquivos aqui ou clique para selecionar",
            type=["xml", "pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            help="XML SEFAZ (melhor precisão), PDF DANFE ou imagem PNG/JPG (OCR).",
            label_visibility="collapsed",
            key="file_uploader",
        )

    with col_dica:
        deps = verificar_dependencias()
        pdf_ok  = deps['pdfplumber']
        ocr_ok  = deps['pytesseract'] and deps['pillow']
        st.info(
            "**Formatos aceitos:**\n"
            "- 📌 XML NF-e SEFAZ *(maior precisão)*\n"
            f"- 📄 PDF DANFE {'*disponivel*' if pdf_ok else '*instale pdfplumber*'}\n"
            f"- 🖼️ PNG / JPG {'*disponivel*' if ocr_ok else '*instale pytesseract*'}\n"
            "- Múltiplos arquivos\n"
            "- Sem limite de quantidade"
        )

    if uploaded_files:
        n = len(uploaded_files)
        total_size_kb = sum(f.size for f in uploaded_files) / 1024
        st.success(
            f"✅ **{n} arquivo{'s' if n > 1 else ''}** carregado{'s' if n > 1 else ''} "
            f"({total_size_kb:.1f} KB total) — pronto para processamento"
        )

        col_btn, col_reset, _ = st.columns([1.2, 0.8, 4])
        with col_btn:
            processar_upload = st.button(
                "🔍 Processar Notas", type="primary",
                use_container_width=True, key="btn_processar_upload"
            )
        with col_reset:
            if st.session_state.df_result is not None:
                if st.button("🗑️ Limpar", use_container_width=True, key="btn_limpar_upload"):
                    st.session_state.df_result = None
                    st.session_state.total_processados = 0
                    st.rerun()

        if processar_upload:
            _processar_lote(uploaded_files, modo='upload')

# ── ABA 2: Processar Pasta Local ──────────────────────────────────────────────
with tab_pasta:
    st.markdown(
        "Informe o caminho completo de uma pasta no seu computador. "
        "O sistema encontrará e processará todos os arquivos XML automaticamente."
    )

    col_path, col_opts = st.columns([3, 1])

    with col_path:
        caminho_pasta = st.text_input(
            label="Caminho da pasta",
            placeholder=r"Ex: C:\NFe\Junho2024  ou  \\servidor\notas\\",
            help="Caminho local ou de rede contendo arquivos XML de NF-e.",
            key="input_pasta",
            label_visibility="collapsed",
        )

    with col_opts:
        incluir_subpastas = st.checkbox(
            "📂 Incluir subpastas",
            value=False,
            help="Se marcado, busca XMLs também nas subpastas do caminho informado.",
            key="chk_subpastas",
        )

    if caminho_pasta:
        try:
            xmls_encontrados = listar_xmls_pasta(caminho_pasta, recursivo=incluir_subpastas)
            n_encontrados = len(xmls_encontrados)

            if n_encontrados == 0:
                st.warning(
                    f"Nenhum arquivo XML encontrado em `{caminho_pasta}`. "
                    f"{'(subpastas incluídas)' if incluir_subpastas else 'Tente marcar Incluir subpastas.'}"
                )
            else:
                sub_label = " (incluindo subpastas)" if incluir_subpastas else ""
                st.success(
                    f"📂 **{n_encontrados} arquivo(s) XML** encontrado(s) em "
                    f"`{caminho_pasta}`{sub_label}"
                )

                # Prévia dos arquivos encontrados (máx. 10)
                with st.expander(f"Ver arquivos ({n_encontrados})", expanded=False):
                    for xml_path in xmls_encontrados[:50]:
                        size_kb = xml_path.stat().st_size / 1024
                        st.markdown(
                            f"<div style='font-size:0.82rem;color:rgba(255,255,255,0.6);padding:0.1rem 0'>"
                            f"📄 {xml_path.name} "
                            f"<span style='color:rgba(255,255,255,0.3);font-size:0.75rem'>({size_kb:.1f} KB)</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    if n_encontrados > 50:
                        st.caption(f"... e mais {n_encontrados - 50} arquivo(s)")

                col_btn2, col_reset2, _ = st.columns([1.5, 0.8, 3])
                with col_btn2:
                    processar_pasta = st.button(
                        f"🔍 Processar {n_encontrados} Notas",
                        type="primary",
                        use_container_width=True,
                        key="btn_processar_pasta"
                    )
                with col_reset2:
                    if st.session_state.df_result is not None:
                        if st.button("🗑️ Limpar", use_container_width=True, key="btn_limpar_pasta"):
                            st.session_state.df_result = None
                            st.session_state.total_processados = 0
                            st.rerun()

                if processar_pasta:
                    _processar_lote(xmls_encontrados, modo='pasta')

        except FileNotFoundError as e:
            st.error(f"❌ Pasta não encontrada: `{caminho_pasta}`")
        except NotADirectoryError as e:
            st.error(f"❌ O caminho informado não é uma pasta válida: `{caminho_pasta}`")
        except PermissionError:
            st.error(f"❌ Sem permissão para acessar: `{caminho_pasta}`")
        except Exception as e:
            st.error(f"❌ Erro inesperado: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADOS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.df_result is not None:
    df: pd.DataFrame = st.session_state.df_result

    # Garante coluna numérica de valor
    if 'vNF_num' not in df.columns:
        df['vNF_num'] = pd.to_numeric(df.get('vNF', pd.Series(dtype=float)), errors='coerce')

    total = len(df)
    n_ok = int((df['status'] == 'OK').sum())
    n_aviso = int((df['status'] == 'AVISO').sum())
    n_erro = int((df['status'] == 'ERRO').sum())
    valor_total = float(df['vNF_num'].sum())

    pct_ok = (n_ok / total * 100) if total > 0 else 0
    pct_aviso = (n_aviso / total * 100) if total > 0 else 0
    pct_erro = (n_erro / total * 100) if total > 0 else 0

    # ── MÉTRICAS ────────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">📊 Resumo do Lote</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card metric-total">
            <div class="metric-icon">📋</div>
            <div class="metric-value">{total}</div>
            <div class="metric-label">Total de NFs</div>
        </div>
        <div class="metric-card metric-ok">
            <div class="metric-icon">✅</div>
            <div class="metric-value">{n_ok}</div>
            <div class="metric-label">Sem inconsistências</div>
            <div class="metric-sub">{pct_ok:.0f}% do lote</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill pb-ok" style="width:{pct_ok:.1f}%"></div>
            </div>
        </div>
        <div class="metric-card metric-aviso">
            <div class="metric-icon">⚠️</div>
            <div class="metric-value">{n_aviso}</div>
            <div class="metric-label">Com atenção</div>
            <div class="metric-sub">{pct_aviso:.0f}% do lote</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill pb-aviso" style="width:{pct_aviso:.1f}%"></div>
            </div>
        </div>
        <div class="metric-card metric-erro">
            <div class="metric-icon">❌</div>
            <div class="metric-value">{n_erro}</div>
            <div class="metric-label">Com erro crítico</div>
            <div class="metric-sub">{pct_erro:.0f}% do lote</div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill pb-erro" style="width:{pct_erro:.1f}%"></div>
            </div>
        </div>
        <div class="metric-card metric-valor">
            <div class="metric-icon">💰</div>
            <div class="metric-value">{formatar_moeda(valor_total)}</div>
            <div class="metric-label">Valor total do lote</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── TABELA / LISTA DE NOTAS ──────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Notas Fiscais</div>', unsafe_allow_html=True)

    # Ordena: ERRO → AVISO → OK
    STATUS_ORDER = {'ERRO': 0, 'AVISO': 1, 'OK': 2}
    df_sorted = df.copy()
    df_sorted['_sort_key'] = df_sorted['status'].map(STATUS_ORDER).fillna(3)
    df_sorted = df_sorted.sort_values('_sort_key').drop(columns=['_sort_key']).reset_index(drop=True)

    tab_todos, tab_erro, tab_aviso, tab_ok = st.tabs([
        f"📋 Todos  ({total})",
        f"❌ Erros  ({n_erro})",
        f"⚠️ Avisos  ({n_aviso})",
        f"✅ OK  ({n_ok})",
    ])

    def render_lista_notas(df_view: pd.DataFrame, prefix: str) -> None:
        """Renderiza a lista de notas com expander por item."""
        if df_view.empty:
            st.markdown("""
            <div style="text-align:center;padding:2rem;color:rgba(255,255,255,0.3);font-size:0.9rem;">
                Nenhuma nota nesta categoria.
            </div>
            """, unsafe_allow_html=True)
            return

        for _, row in df_view.iterrows():
            status = row.get('status', 'OK')
            nNF = row.get('nNF') or '—'
            nome_emit = (row.get('nome_emit') or 'Emitente não identificado')[:50]
            arquivo = row.get('arquivo') or '—'
            vNF_num = row.get('vNF_num', 0) or 0
            dhEmi = formatar_data(row.get('dhEmi', ''))
            qtd_erros = int(row.get('qtd_erros', 0))
            qtd_avisos = int(row.get('qtd_avisos', 0))

            if status == 'ERRO':
                icon = "🔴"
                badge_html = '<span class="badge badge-erro">❌ ERRO</span>'
                label_detalhe = f"  ·  {qtd_erros} erro{'s' if qtd_erros != 1 else ''}"
            elif status == 'AVISO':
                icon = "🟡"
                badge_html = '<span class="badge badge-aviso">⚠️ AVISO</span>'
                label_detalhe = f"  ·  {qtd_avisos} aviso{'s' if qtd_avisos != 1 else ''}"
            else:
                icon = "🟢"
                badge_html = '<span class="badge badge-ok">✅ OK</span>'
                label_detalhe = ""

            titulo = (
                f"{icon}  NF {nNF}  │  {nome_emit}  │  "
                f"{formatar_moeda(vNF_num)}  │  {dhEmi or 'sem data'}{label_detalhe}"
            )

            with st.expander(titulo, expanded=(status == 'ERRO')):
                # ── Status badge ──
                st.markdown(
                    f"<div style='margin-bottom:0.8rem'>{badge_html}"
                    f"&nbsp;&nbsp;<span style='color:rgba(255,255,255,0.35);font-size:0.8rem'>"
                    f"Arquivo: {arquivo}</span></div>",
                    unsafe_allow_html=True
                )

                c1, c2 = st.columns(2)

                with c1:
                    st.markdown("**📄 Identificação**")
                    st.markdown(f"""
                    <div class="field-grid">
                        <div class="field-item">
                            <div class="field-label">Número da NF</div>
                            <div class="field-value">{nNF}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">Série</div>
                            <div class="field-value">{row.get('serie') or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">Data de Emissão</div>
                            <div class="field-value">{dhEmi or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">CFOP</div>
                            <div class="field-value">{row.get('cfop') or '—'}</div>
                        </div>
                        <div class="field-item" style="grid-column:span 2">
                            <div class="field-label">Natureza da Operação</div>
                            <div class="field-value">{row.get('natOp') or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">NCM</div>
                            <div class="field-value">{row.get('ncm') or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">Modelo</div>
                            <div class="field-value">{row.get('mod') or '—'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with c2:
                    cnpj_emit_fmt = formatar_cnpj_display(row.get('cnpj_emit') or '')
                    cnpj_dest_fmt = formatar_cnpj_display(row.get('cnpj_dest') or '')
                    vICMS = formatar_moeda(row.get('vICMS'))
                    vPIS = formatar_moeda(row.get('vPIS'))
                    vCOFINS = formatar_moeda(row.get('vCOFINS'))

                    st.markdown("**🏢 Emitente & Destinatário**")
                    st.markdown(f"""
                    <div class="field-grid">
                        <div class="field-item" style="grid-column:span 2">
                            <div class="field-label">Emitente</div>
                            <div class="field-value">{row.get('nome_emit') or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">CNPJ Emitente</div>
                            <div class="field-value mono">{cnpj_emit_fmt or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">UF Emitente</div>
                            <div class="field-value">{row.get('uf_emit') or '—'}</div>
                        </div>
                        <div class="field-item" style="grid-column:span 2">
                            <div class="field-label">Destinatário</div>
                            <div class="field-value">{row.get('nome_dest') or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">CNPJ Destinatário</div>
                            <div class="field-value mono">{cnpj_dest_fmt or '—'}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">UF Dest.</div>
                            <div class="field-value">{row.get('uf_dest') or '—'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("**💰 Valores Fiscais**")
                    st.markdown(f"""
                    <div class="field-grid">
                        <div class="field-item" style="grid-column:span 2">
                            <div class="field-label">Valor Total da Nota</div>
                            <div class="field-value" style="color:#b794f4;font-size:1.05rem;font-weight:700">
                                {formatar_moeda(vNF_num)}
                            </div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">ICMS</div>
                            <div class="field-value">{vICMS}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">PIS</div>
                            <div class="field-value">{vPIS}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">COFINS</div>
                            <div class="field-value">{vCOFINS}</div>
                        </div>
                        <div class="field-item">
                            <div class="field-label">Base Cálculo ICMS</div>
                            <div class="field-value">{formatar_moeda(row.get('vBC'))}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Alertas ──
                erros = row.get('alertas_erro', [])
                avisos = row.get('alertas_aviso', [])

                st.markdown("---")
                st.markdown("**🔍 Resultado da Validação**")

                if not erros and not avisos:
                    st.markdown('<div class="alert-item alert-ok">✅ Nenhuma inconsistência encontrada — nota dentro dos padrões fiscais</div>', unsafe_allow_html=True)
                else:
                    for err in erros:
                        st.markdown(f'<div class="alert-item alert-erro">{err}</div>', unsafe_allow_html=True)
                    for av in avisos:
                        st.markdown(f'<div class="alert-item alert-aviso">{av}</div>', unsafe_allow_html=True)

                    # ── Botão de Análise de IA ──
                    if st.session_state.gemini_api_key:
                        btn_key = f"ai_btn_{prefix}_{nNF}_{_}"
                        if st.button("✨ Analisar com IA", key=btn_key):
                            with st.spinner("O Gemini está analisando as inconsistências..."):
                                config_ok = configurar_api(st.session_state.gemini_api_key)
                                if config_ok:
                                    # Mescla erros e avisos para enviar
                                    todas_inconsistencias = erros + avisos
                                    sucesso, resposta_ai = analisar_inconsistencias(row.to_dict(), todas_inconsistencias)
                                    
                                    if sucesso:
                                        st.markdown("### 🤖 Diagnóstico e Recomendação")
                                        st.info(resposta_ai)
                                    else:
                                        st.error(resposta_ai)
                                else:
                                    st.error("Erro ao configurar a API Key. Verifique a barra lateral.")
                    else:
                        st.caption("🔒 *Configure sua API Key do Gemini na barra lateral para pedir dicas de correção desta nota.*")

                # ── Chave de acesso ──
                chave = row.get('chNFe') or ''
                if chave:
                    chave_fmt = formatar_chave(chave)
                    st.markdown(
                        f"<div style='margin-top:0.6rem;font-size:0.72rem;color:rgba(255,255,255,0.3)'>"
                        f"🔑 Chave: <span style='font-family:monospace;letter-spacing:0.03em'>{chave_fmt}</span></div>",
                        unsafe_allow_html=True
                    )

    with tab_todos:
        render_lista_notas(df_sorted, "todos")

    with tab_erro:
        render_lista_notas(df_sorted[df_sorted['status'] == 'ERRO'].reset_index(drop=True), "erro")

    with tab_aviso:
        render_lista_notas(df_sorted[df_sorted['status'] == 'AVISO'].reset_index(drop=True), "aviso")

    with tab_ok:
        render_lista_notas(df_sorted[df_sorted['status'] == 'OK'].reset_index(drop=True), "ok")

    # ── EXPORTAÇÃO ───────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">📤 Exportar Relatório</div>', unsafe_allow_html=True)

    col_csv, col_xlsx, col_info = st.columns([1, 1, 3])

    with col_csv:
        csv_bytes = exportar_csv(df_sorted)
        st.download_button(
            label="⬇️ Baixar CSV",
            data=csv_bytes,
            file_name="relatorio_nfe.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_xlsx:
        try:
            excel_bytes = exportar_excel(df_sorted)
            st.download_button(
                label="⬇️ Baixar Excel",
                data=excel_bytes,
                file_name="relatorio_nfe.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Excel indisponível: instale `xlsxwriter`. Use o CSV por enquanto.")

    with col_info:
        st.caption(
            f"Relatório com **{total}** nota(s)  ·  "
            f"✅ {n_ok} OK  ·  ⚠️ {n_aviso} avisos  ·  ❌ {n_erro} erros  ·  "
            f"💰 {formatar_moeda(valor_total)} total"
        )

# ══════════════════════════════════════════════════════════════════════════════
# ESTADO VAZIO (sem resultados ainda)
# ══════════════════════════════════════════════════════════════════════════════
elif not uploaded_files:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">🧾</div>
        <div class="empty-title">Nenhuma nota processada ainda</div>
        <div class="empty-sub">
            Faça o upload dos arquivos XML de NF-e acima para iniciar a triagem automática
        </div>
    </div>
    """, unsafe_allow_html=True)

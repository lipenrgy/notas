"""
pdf_parser.py
Extração de dados de NF-e a partir de DANFE em PDF ou imagem (PNG/JPG).

Estratégia:
- PDF com texto: pdfplumber extrai texto, regex localiza campos DANFE
- PDF escaneado / imagem PNG/JPG: pytesseract (OCR) — requer Tesseract instalado

Os campos extraídos tentam cobrir o layout padrão do DANFE, mas a confiabilidade
é menor do que o XML. Quando disponível, sempre prefira o XML NF-e.
"""
import io
import re
from typing import Optional, Dict, Any, List

# ── Imports opcionais (não falham se não instalados) ──────────────────────────
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    from PIL import Image
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

try:
    import pytesseract
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False


# ── Padrões Regex para DANFE ──────────────────────────────────────────────────

# CNPJ: XX.XXX.XXX/XXXX-XX
RE_CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')

# Número da NF-e: normalmente "Nº XXX.XXX.XXX" ou "NUMERO: XXX"
RE_NNF = re.compile(
    r'(?:N[º°Oo\.]\s*|NUMERO[:\s]+|NOTA FISCAL[:\s]*N[º°]?\s*)(\d[\d\.]+)',
    re.IGNORECASE
)

# Série: "SÉRIE: X" ou "SER.: X"
RE_SERIE = re.compile(r'S[EÉ]R(?:IE)?\.?\s*:?\s*(\d+)', re.IGNORECASE)

# Valor total: "VALOR TOTAL R$ X.XXX,XX" ou "TOTAL DA NF" etc.
RE_VALOR = re.compile(
    r'(?:VALOR TOTAL|TOTAL DA NF|VNF|V\.NF)[:\s]*R?\$?\s*([\d\.]+,\d{2})',
    re.IGNORECASE
)

# Data de emissão: "DATA DE EMISSÃO: DD/MM/AAAA"
RE_DATA = re.compile(
    r'(?:DATA\s+DE\s+EMISS[AÃ]O|EMISS[AÃ]O)[:\s]+([\d]{1,2}/[\d]{1,2}/[\d]{4})',
    re.IGNORECASE
)

# Razão social / nome: linha após "RAZAO SOCIAL" ou "NOME/RAZAO"
RE_RAZAO_EMIT = re.compile(
    r'(?:RAZ[AÃ]O\s+SOCIAL|NOME\s*/\s*RAZ[AÃ]O\s+SOCIAL)[:\s]*([A-ZÁÉÍÓÚÇÃÕ][^\n]{3,60})',
    re.IGNORECASE
)

# Chave de acesso: 44 dígitos consecutivos (com ou sem espaços a cada 4)
RE_CHAVE = re.compile(r'(?:\d{4}\s*){11}', re.IGNORECASE)

# ICMS
RE_ICMS = re.compile(
    r'(?:VALOR\s+DO\s+ICMS|VICMS)[:\s]*R?\$?\s*([\d\.]+,\d{2})',
    re.IGNORECASE
)

# Natureza da operação
RE_NATOP = re.compile(
    r'NATUREZA\s+(?:DA\s+)?OPERA[ÇC][AÃ]O[:\s]*([^\n]{3,80})',
    re.IGNORECASE
)

# CFOP
RE_CFOP = re.compile(r'\bCFOP[:\s]*(\d{4})\b', re.IGNORECASE)

# NCM
RE_NCM = re.compile(r'\bNCM(?:/SH)?[:\s]*(\d{8})\b', re.IGNORECASE)


def _moeda_para_float(valor_str: str) -> Optional[float]:
    """Converte 'X.XXX,XX' para float."""
    if not valor_str:
        return None
    try:
        return float(valor_str.replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def _limpar_chave(texto: str) -> Optional[str]:
    """Extrai e valida chave de acesso de 44 dígitos."""
    m = RE_CHAVE.search(texto)
    if m:
        chave = re.sub(r'\s', '', m.group())
        if len(chave) == 44:
            return chave
    # Tenta encontrar 44 dígitos seguidos sem espaço
    m2 = re.search(r'\d{44}', texto)
    return m2.group() if m2 else None


def _extrair_campos_texto(texto: str, filename: str) -> Dict[str, Any]:
    """
    Extrai campos NF-e de texto bruto de DANFE usando expressões regulares.
    Retorna dicionário no mesmo schema do NFeParser.
    """
    # CNPJs encontrados no documento
    cnpjs = RE_CNPJ.findall(texto)
    cnpj_emit = cnpjs[0].replace('.', '').replace('/', '').replace('-', '') if len(cnpjs) > 0 else None
    cnpj_dest = cnpjs[1].replace('.', '').replace('/', '').replace('-', '') if len(cnpjs) > 1 else None

    # Número da NF
    m_nnf = RE_NNF.search(texto)
    nNF = re.sub(r'[\.\s]', '', m_nnf.group(1)) if m_nnf else None

    # Série
    m_serie = RE_SERIE.search(texto)
    serie = m_serie.group(1) if m_serie else None

    # Valor total
    m_valor = RE_VALOR.search(texto)
    vNF_str = m_valor.group(1) if m_valor else None
    vNF_num = _moeda_para_float(vNF_str) if vNF_str else None

    # Data de emissão
    m_data = RE_DATA.search(texto)
    dhEmi_raw = m_data.group(1) if m_data else None
    # Converte DD/MM/AAAA → AAAA-MM-DDTHH:MM:SS (ISO)
    dhEmi = None
    if dhEmi_raw:
        try:
            parts = dhEmi_raw.split('/')
            if len(parts) == 3:
                dhEmi = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}T00:00:00"
        except Exception:
            dhEmi = dhEmi_raw

    # Razão social emitente
    m_razao = RE_RAZAO_EMIT.search(texto)
    nome_emit = m_razao.group(1).strip() if m_razao else None

    # Chave de acesso
    chNFe = _limpar_chave(texto)

    # ICMS
    m_icms = RE_ICMS.search(texto)
    vICMS = str(_moeda_para_float(m_icms.group(1))) if m_icms else None

    # Natureza da operação
    m_natop = RE_NATOP.search(texto)
    natOp = m_natop.group(1).strip() if m_natop else None

    # CFOP
    m_cfop = RE_CFOP.search(texto)
    cfop = m_cfop.group(1) if m_cfop else None

    # NCM
    m_ncm = RE_NCM.search(texto)
    ncm = m_ncm.group(1) if m_ncm else None

    return {
        'arquivo': filename,
        'parse_ok': True,
        'erro_parse': None,
        'fonte': 'pdf_texto',
        # Identificação
        'chNFe': chNFe,
        'nNF': nNF,
        'serie': serie,
        'dhEmi': dhEmi,
        'natOp': natOp,
        'mod': '55',  # DANFE padrão
        'tpNF': None,
        'cfop': cfop,
        'ncm': ncm,
        # Emitente
        'cnpj_emit': cnpj_emit,
        'nome_emit': nome_emit,
        'uf_emit': None,
        # Destinatário
        'cnpj_dest': cnpj_dest,
        'cpf_dest': None,
        'nome_dest': None,
        'uf_dest': None,
        # Valores
        'vNF': str(vNF_num) if vNF_num is not None else vNF_str,
        'vICMS': vICMS,
        'vPIS': None,
        'vCOFINS': None,
        'vBC': None,
        'vST': None,
        'vFrete': None,
        # v2.0
        'pICMS': None,
        'temCobranca': None,
        'itens_valor_zero': [],
        'qtd_itens': 0,
    }


def parse_pdf(filepath) -> Dict[str, Any]:
    """
    Extrai dados de NF-e de um arquivo PDF (DANFE).

    Tenta em ordem:
    1. Extração de texto nativo com pdfplumber (PDFs digitais)
    2. OCR com pytesseract (PDFs escaneados)
    """
    filename = getattr(filepath, 'name', str(filepath))

    if not PDFPLUMBER_OK:
        return _error_result(
            filename,
            "pdfplumber não instalado. Execute: pip install pdfplumber"
        )

    try:
        # Lê o conteúdo (suporta UploadedFile do Streamlit e caminhos de arquivo)
        if hasattr(filepath, 'read'):
            content = filepath.read()
            pdf_io = io.BytesIO(content)
        else:
            with open(str(filepath), 'rb') as f:
                content = f.read()
            pdf_io = io.BytesIO(content)

        with pdfplumber.open(pdf_io) as pdf:
            texto = '\n'.join(
                (page.extract_text() or '') for page in pdf.pages
            )

        if texto.strip():
            return _extrair_campos_texto(texto, filename)

        # Texto vazio → tenta OCR se disponível
        if TESSERACT_OK and PILLOW_OK:
            return _ocr_pdf(pdf_io, filename)
        else:
            return _error_result(
                filename,
                "PDF parece ser uma imagem escaneada (sem texto extraível). "
                "Instale pytesseract + Tesseract para usar OCR: pip install pytesseract pillow"
            )

    except Exception as e:
        return _error_result(filename, f"Erro ao processar PDF: {e}")


def parse_imagem(filepath) -> Dict[str, Any]:
    """
    Extrai dados de NF-e de uma imagem (PNG, JPG, JPEG, TIFF).
    Requer pytesseract e Tesseract-OCR instalados no sistema.
    """
    filename = getattr(filepath, 'name', str(filepath))

    if not PILLOW_OK:
        return _error_result(filename, "Pillow não instalado. Execute: pip install pillow")

    if not TESSERACT_OK:
        return _error_result(
            filename,
            "pytesseract não instalado ou Tesseract-OCR não encontrado. "
            "Instale: pip install pytesseract | e baixe o Tesseract em: "
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )

    try:
        if hasattr(filepath, 'read'):
            content = filepath.read()
            img_io = io.BytesIO(content)
        else:
            img_io = str(filepath)

        img = Image.open(img_io)

        # Configura Tesseract para Português
        config = '--oem 3 --psm 6 -l por+eng'
        texto = pytesseract.image_to_string(img, config=config)

        if not texto.strip():
            return _error_result(filename, "Não foi possível extrair texto da imagem via OCR")

        return _extrair_campos_texto(texto, filename)

    except Exception as e:
        return _error_result(filename, f"Erro ao processar imagem: {e}")


def _ocr_pdf(pdf_io: io.BytesIO, filename: str) -> Dict[str, Any]:
    """OCR em cada página do PDF escaneado usando pytesseract."""
    try:
        import pdfplumber
        textos = []
        pdf_io.seek(0)
        with pdfplumber.open(pdf_io) as pdf:
            for page in pdf.pages:
                img = page.to_image(resolution=200).original
                texto_pag = pytesseract.image_to_string(img, config='--oem 3 --psm 6 -l por+eng')
                textos.append(texto_pag)
        texto_total = '\n'.join(textos)
        if texto_total.strip():
            return _extrair_campos_texto(texto_total, filename)
        return _error_result(filename, "OCR não extraiu texto legível do PDF")
    except Exception as e:
        return _error_result(filename, f"Erro no OCR do PDF: {e}")


def _error_result(filename: str, error_msg: str) -> Dict[str, Any]:
    return {
        'arquivo': filename,
        'parse_ok': False,
        'erro_parse': error_msg,
        'fonte': 'pdf',
        'chNFe': None, 'nNF': None, 'serie': None, 'dhEmi': None,
        'natOp': None, 'mod': None, 'tpNF': None, 'cfop': None, 'ncm': None,
        'cnpj_emit': None, 'nome_emit': None, 'uf_emit': None,
        'cnpj_dest': None, 'cpf_dest': None, 'nome_dest': None, 'uf_dest': None,
        'vNF': None, 'vICMS': None, 'vPIS': None, 'vCOFINS': None,
        'vBC': None, 'vST': None, 'vFrete': None,
        'pICMS': None, 'temCobranca': None, 'itens_valor_zero': [], 'qtd_itens': 0,
    }


def verificar_dependencias() -> Dict[str, bool]:
    """Retorna status das dependências opcionais para PDF/imagem."""
    return {
        'pdfplumber': PDFPLUMBER_OK,
        'pillow': PILLOW_OK,
        'pytesseract': TESSERACT_OK,
    }

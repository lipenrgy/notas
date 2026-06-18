"""
nfe_parser.py
Parser de arquivos XML de NF-e no padrão SEFAZ (versão 4.00).
Extrai os principais campos fiscais usando lxml para alta performance.

v2.0 — Novos campos: tpNF, pICMS, temCobranca, itens_valor_zero
"""
from lxml import etree
from pathlib import Path
from typing import Optional, Dict, Any, List

# Namespace padrão NF-e SEFAZ
NS = 'http://www.portalfiscal.inf.br/nfe'
NS_MAP = {'nfe': NS}

# Campos retornados com valor None quando ausentes — garante schema consistente
CAMPOS_PADRAO = [
    'arquivo', 'parse_ok', 'erro_parse',
    'chNFe', 'nNF', 'serie', 'dhEmi', 'natOp', 'mod', 'cfop', 'ncm',
    'cnpj_emit', 'nome_emit', 'uf_emit',
    'cnpj_dest', 'nome_dest', 'uf_dest', 'cpf_dest',
    'vNF', 'vICMS', 'vPIS', 'vCOFINS', 'vBC', 'vST', 'vFrete',
    # v2.0
    'tpNF', 'pICMS', 'temCobranca', 'itens_valor_zero', 'qtd_itens',
]


def _find_text(element, path: str) -> Optional[str]:
    """Busca texto em elemento XML usando prefixo de namespace NF-e."""
    if element is None:
        return None
    found = element.find(path, NS_MAP)
    if found is not None and found.text:
        return found.text.strip()
    return None


class NFeParser:
    """
    Parser de Nota Fiscal Eletrônica (NF-e) no formato XML SEFAZ.

    Suporta:
    - nfeProc (NF-e com protocolo de autorização) — formato mais comum
    - NFe (apenas a NF-e sem protocolo)
    - Streamlit UploadedFile e caminhos de arquivo (str/Path)
    """

    def parse_file(self, filepath) -> Dict[str, Any]:
        """
        Lê e extrai dados de um arquivo XML de NF-e.

        Args:
            filepath: Objeto UploadedFile do Streamlit, str ou Path.

        Returns:
            Dicionário com todos os campos extraídos. 'parse_ok' indica sucesso.
        """
        filename = getattr(filepath, 'name', str(filepath))
        try:
            if hasattr(filepath, 'read'):
                # Streamlit UploadedFile — lê bytes diretamente
                content = filepath.read()
                if not content:
                    return self._error_result(filename, "Arquivo vazio.")
                root = etree.fromstring(content)
            else:
                tree = etree.parse(str(filepath))
                root = tree.getroot()

            return self._extract_data(root, filename)

        except etree.XMLSyntaxError as e:
            return self._error_result(filename, f"XML inválido ou corrompido: {e}")
        except Exception as e:
            return self._error_result(filename, f"Erro inesperado ao processar arquivo: {e}")

    # ──────────────────────────────────────────────────────────
    # Extração interna
    # ──────────────────────────────────────────────────────────

    def _extract_data(self, root, filename: str) -> Dict[str, Any]:
        """Extrai campos da NF-e a partir do elemento raiz."""

        # Localiza <infNFe> independentemente de onde estiver na árvore
        infNFe = root.find(f'.//{{{NS}}}infNFe')
        if infNFe is None:
            return self._error_result(
                filename,
                "Elemento <infNFe> não encontrado. "
                "Verifique se o arquivo é uma NF-e/NFC-e válida no padrão SEFAZ."
            )

        # ── Chave de acesso (44 dígitos) ──
        chave_id = infNFe.get('Id', '')
        chNFe = chave_id[3:] if chave_id.startswith('NFe') else chave_id

        # ── Seções principais ──
        ide = infNFe.find('nfe:ide', NS_MAP)
        emit = infNFe.find('nfe:emit', NS_MAP)
        dest = infNFe.find('nfe:dest', NS_MAP)
        total = infNFe.find('nfe:total/nfe:ICMSTot', NS_MAP)

        # ── CFOP e NCM: pega do primeiro item (det) ──
        cfop = _find_text(infNFe, './/nfe:CFOP')
        ncm = _find_text(infNFe, './/nfe:NCM')

        # ── Destinatário: pode ser pessoa jurídica (CNPJ) ou física (CPF) ──
        cnpj_dest = _find_text(dest, 'nfe:CNPJ')
        cpf_dest = _find_text(dest, 'nfe:CPF')

        # ── v2.0: Tipo de nota (0=entrada, 1=saída) ──
        tpNF = _find_text(ide, 'nfe:tpNF')

        # ── v2.0: Alíquota ICMS do primeiro item (para validação de coerência) ──
        pICMS = self._extrair_picms(infNFe)

        # ── v2.0: Cobrança presente? (indica fatura/duplicata vinculada) ──
        cobr = infNFe.find('nfe:cobr', NS_MAP)
        temCobranca = cobr is not None and cobr.find('nfe:dup', NS_MAP) is not None

        # ── v2.0: Análise de itens ──
        itens_valor_zero, qtd_itens = self._analisar_itens(infNFe)

        return {
            'arquivo': filename,
            'parse_ok': True,
            'erro_parse': None,
            # Identificação
            'chNFe': chNFe if chNFe else None,
            'nNF': _find_text(ide, 'nfe:nNF'),
            'serie': _find_text(ide, 'nfe:serie'),
            'dhEmi': _find_text(ide, 'nfe:dhEmi'),
            'natOp': _find_text(ide, 'nfe:natOp'),
            'mod': _find_text(ide, 'nfe:mod'),
            'tpNF': tpNF,
            'cfop': cfop,
            'ncm': ncm,
            # Emitente
            'cnpj_emit': _find_text(emit, 'nfe:CNPJ'),
            'nome_emit': _find_text(emit, 'nfe:xNome'),
            'uf_emit': _find_text(emit, 'nfe:enderEmit/nfe:UF'),
            # Destinatário
            'cnpj_dest': cnpj_dest,
            'cpf_dest': cpf_dest,
            'nome_dest': _find_text(dest, 'nfe:xNome'),
            'uf_dest': _find_text(dest, 'nfe:enderDest/nfe:UF'),
            # Valores totais
            'vNF': _find_text(total, 'nfe:vNF'),
            'vICMS': _find_text(total, 'nfe:vICMS'),
            'vPIS': _find_text(total, 'nfe:vPIS'),
            'vCOFINS': _find_text(total, 'nfe:vCOFINS'),
            'vBC': _find_text(total, 'nfe:vBC'),
            'vST': _find_text(total, 'nfe:vST'),
            'vFrete': _find_text(total, 'nfe:vFrete'),
            # v2.0
            'pICMS': pICMS,
            'temCobranca': temCobranca,
            'itens_valor_zero': itens_valor_zero,
            'qtd_itens': qtd_itens,
        }

    def _extrair_picms(self, infNFe) -> Optional[float]:
        """
        Extrai a alíquota de ICMS (pICMS) do primeiro item tributado normalmente.
        Ignora CSTs de isenção/diferimento (40, 41, 50, 60, 70, 90).
        Retorna None se não houver alíquota aplicável.
        """
        # CSTs que possuem alíquota explícita (tributados normalmente)
        CST_COM_ALIQUOTA = {'00', '10', '20', '30', '51', '70'}

        for det in infNFe.findall('nfe:det', NS_MAP):
            icms_container = det.find('nfe:imposto/nfe:ICMS', NS_MAP)
            if icms_container is None:
                continue
            # Itera sobre os filhos do ICMS (ICMS00, ICMS10, ICMS20, etc.)
            for icms_tipo in icms_container:
                cst = _find_text(icms_tipo, 'nfe:CST')
                if cst in CST_COM_ALIQUOTA:
                    pICMS_str = _find_text(icms_tipo, 'nfe:pICMS')
                    if pICMS_str:
                        try:
                            return float(pICMS_str)
                        except ValueError:
                            pass
        return None

    def _analisar_itens(self, infNFe) -> tuple:
        """
        Analisa todos os itens <det> da nota.

        Returns:
            (itens_valor_zero: List[str], qtd_itens: int)
            - itens_valor_zero: lista de nomes de produtos com vProd = 0
            - qtd_itens: quantidade total de itens
        """
        itens_zero = []
        qtd = 0

        for det in infNFe.findall('nfe:det', NS_MAP):
            qtd += 1
            prod = det.find('nfe:prod', NS_MAP)
            if prod is None:
                continue

            vProd_str = _find_text(prod, 'nfe:vProd')
            xProd = _find_text(prod, 'nfe:xProd') or f'Item {qtd}'

            try:
                vProd = float(vProd_str or '0')
                if vProd <= 0:
                    itens_zero.append(xProd[:50])
            except ValueError:
                pass

        return itens_zero, qtd

    def _error_result(self, filename: str, error_msg: str) -> Dict[str, Any]:
        """Retorna resultado padronizado com indicação de falha no parse."""
        base = {campo: None for campo in CAMPOS_PADRAO}
        base.update({
            'arquivo': filename,
            'parse_ok': False,
            'erro_parse': error_msg,
            'temCobranca': False,
            'itens_valor_zero': [],
            'qtd_itens': 0,
        })
        return base


def listar_xmls_pasta(pasta: str, recursivo: bool = False) -> List[Path]:
    """
    Lista todos os arquivos XML em uma pasta local.

    Args:
        pasta: Caminho da pasta (str ou Path).
        recursivo: Se True, inclui subpastas.

    Returns:
        Lista de objetos Path para cada arquivo .xml encontrado.

    Raises:
        FileNotFoundError: Se a pasta não existir.
        NotADirectoryError: Se o caminho não for uma pasta.
    """
    caminho = Path(pasta)

    if not caminho.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {pasta}")
    if not caminho.is_dir():
        raise NotADirectoryError(f"O caminho não é uma pasta: {pasta}")

    if recursivo:
        xmls = sorted(caminho.rglob('*.xml'))
    else:
        xmls = sorted(caminho.glob('*.xml'))

    return xmls

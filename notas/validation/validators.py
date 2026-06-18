"""
validators.py
Motor de validação de NF-e usando Pandas.
Aplica regras de negócio fiscais e retorna DataFrame com status e alertas por nota.

v2.0 — 5 novas regras: CFOP×tpNF, ICMS coerência, NCM formato, itens zero, cobrança ausente
"""
import pandas as pd
from datetime import datetime, timedelta

from utils.cnpj_utils import validar_cnpj
from utils.formatters import parse_data, formatar_cnpj_display


# ── Configurações de validação ─────────────────────────────────────────────────

# Campos obrigatórios: nome do campo → descrição legível
CAMPOS_OBRIGATORIOS = {
    'nNF':       'Número da nota fiscal',
    'dhEmi':     'Data de emissão',
    'cnpj_emit': 'CNPJ do emitente',
    'vNF':       'Valor total da nota',
    'chNFe':     'Chave de acesso (44 dígitos)',
}

# Anos máximos de emissão no passado antes de gerar aviso
LIMITE_ANOS_PASSADO = 5

# Tolerância em reais para diferença de ICMS calculado vs declarado
TOLERANCIA_ICMS = 0.10

# CFOPs de saída (começam com 5 ou 6) — esperado tpNF=1
CFOP_SAIDA_PREFIXOS = {'5', '6'}
# CFOPs de entrada (começam com 1 ou 2) — esperado tpNF=0
CFOP_ENTRADA_PREFIXOS = {'1', '2'}
# CFOPs de exportação (começam com 7) — não valida tpNF
CFOP_EXPORTACAO_PREFIXOS = {'7'}


class NFeValidator:
    """
    Validador de lote de NF-e.

    Recebe um DataFrame com os dados extraídos pelo NFeParser e
    retorna o mesmo DataFrame enriquecido com:
    - status: 'OK' | 'AVISO' | 'ERRO'
    - alertas_erro: lista de strings com erros críticos
    - alertas_aviso: lista de strings com alertas não críticos
    - alertas_texto: texto consolidado para exibição/exportação
    - qtd_erros: número de erros críticos
    - qtd_avisos: número de avisos
    """

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica todas as validações ao DataFrame de NF-e.

        Args:
            df: DataFrame com colunas geradas pelo NFeParser.

        Returns:
            DataFrame enriquecido com colunas de status e alertas.
        """
        df = df.copy()

        # Converte valores financeiros para numérico uma vez
        df['vNF_num']  = pd.to_numeric(df.get('vNF',  pd.Series(dtype=float)), errors='coerce')
        df['vBC_num']  = pd.to_numeric(df.get('vBC',  pd.Series(dtype=float)), errors='coerce')
        df['vICMS_num'] = pd.to_numeric(df.get('vICMS', pd.Series(dtype=float)), errors='coerce')

        # Inicializa listas de alertas (usando index para garantir alinhamento)
        df['alertas_erro']  = [[] for _ in range(len(df))]
        df['alertas_aviso'] = [[] for _ in range(len(df))]

        # ── Regras originais (v1.0) ────────────────────────────────────────────
        df = self._val_parse_errors(df)
        df = self._val_campos_obrigatorios(df)
        df = self._val_cnpj(df)
        df = self._val_chave_acesso(df)
        df = self._val_valor_total(df)
        df = self._val_data_emissao(df)
        df = self._val_duplicatas(df)

        # ── Regras novas (v2.0) ────────────────────────────────────────────────
        df = self._val_cfop_tipo_operacao(df)
        df = self._val_icms_coerencia(df)
        df = self._val_ncm_formato(df)
        df = self._val_itens_valor_zero(df)
        df = self._val_cobranca_ausente(df)

        # Consolida status final e textos
        df['status'] = df.apply(self._compute_status, axis=1)
        df['alertas_texto'] = df.apply(
            lambda r: '\n'.join(r['alertas_erro'] + r['alertas_aviso']) or 'Sem inconsistências',
            axis=1
        )
        df['qtd_erros']  = df['alertas_erro'].apply(len)
        df['qtd_avisos'] = df['alertas_aviso'].apply(len)

        return df

    # ── Validações v1.0 ───────────────────────────────────────────────────────

    def _val_parse_errors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Marca notas que falharam na leitura do XML como ERRO."""
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                msg = row.get('erro_parse') or 'Arquivo XML inválido'
                df.at[idx, 'alertas_erro'].append(f"❌ Falha na leitura: {msg}")
        return df

    def _val_campos_obrigatorios(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verifica presença dos campos fiscais obrigatórios."""
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            for campo, descricao in CAMPOS_OBRIGATORIOS.items():
                valor = row.get(campo)
                if valor is None or str(valor).strip() == '':
                    df.at[idx, 'alertas_erro'].append(
                        f"❌ Campo obrigatório ausente: {descricao}"
                    )
        return df

    def _val_cnpj(self, df: pd.DataFrame) -> pd.DataFrame:
        """Valida CNPJ do emitente e do destinatário (quando pessoa jurídica)."""
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            cnpj_emit = row.get('cnpj_emit')
            cnpj_dest = row.get('cnpj_dest')

            if cnpj_emit and not validar_cnpj(cnpj_emit):
                df.at[idx, 'alertas_erro'].append(
                    f"❌ CNPJ do emitente inválido: {formatar_cnpj_display(cnpj_emit)}"
                )
            # Destinatário pode ser CPF (pessoa física) — só valida se CNPJ presente
            if cnpj_dest and not validar_cnpj(cnpj_dest):
                df.at[idx, 'alertas_erro'].append(
                    f"❌ CNPJ do destinatário inválido: {formatar_cnpj_display(cnpj_dest)}"
                )
        return df

    def _val_chave_acesso(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verifica se a chave de acesso tem exatamente 44 dígitos."""
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            chave = str(row.get('chNFe') or '').strip()
            if chave:
                chave_digits = ''.join(c for c in chave if c.isdigit())
                if len(chave_digits) != 44:
                    df.at[idx, 'alertas_erro'].append(
                        f"❌ Chave de acesso com tamanho incorreto: "
                        f"{len(chave_digits)} dígitos (esperado: 44)"
                    )
        return df

    def _val_valor_total(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verifica se o valor total da nota é válido (numérico e positivo)."""
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            vNF = row.get('vNF_num')
            if row.get('vNF') is not None:
                if pd.isna(vNF):
                    df.at[idx, 'alertas_erro'].append(
                        f"❌ Valor total não numérico: '{row.get('vNF')}'"
                    )
                elif vNF <= 0:
                    df.at[idx, 'alertas_erro'].append(
                        f"❌ Valor total zerado ou negativo: R$ {vNF:.2f}"
                    )
        return df

    def _val_data_emissao(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Avisa quando a data de emissão está:
        - No futuro (mais de 1 dia à frente)
        - Muito antiga (mais de LIMITE_ANOS_PASSADO anos)
        """
        agora = datetime.now()
        limite_futuro  = agora + timedelta(days=1)
        limite_passado = agora - timedelta(days=LIMITE_ANOS_PASSADO * 365)

        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            dhEmi = row.get('dhEmi')
            if not dhEmi:
                continue

            dt = parse_data(dhEmi)
            if dt is None:
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ Data de emissão em formato não reconhecido: '{dhEmi}'"
                )
            elif dt > limite_futuro:
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ Data de emissão no futuro: {dt.strftime('%d/%m/%Y %H:%M')}"
                )
            elif dt < limite_passado:
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ Data de emissão muito antiga (>{LIMITE_ANOS_PASSADO} anos): "
                    f"{dt.strftime('%d/%m/%Y')}"
                )
        return df

    def _val_duplicatas(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta notas duplicadas no lote: mesma combinação de
        número da NF (nNF) + CNPJ do emitente.
        """
        df_check = df[['nNF', 'cnpj_emit']].fillna('__NULL__')
        contagem  = df_check.groupby(['nNF', 'cnpj_emit']).size()
        duplicados = contagem[contagem > 1].index.tolist()

        if not duplicados:
            return df

        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue
            nNF       = str(row.get('nNF') or '__NULL__')
            cnpj_emit = str(row.get('cnpj_emit') or '__NULL__')

            if (nNF, cnpj_emit) in duplicados and nNF != '__NULL__':
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ Nota duplicada detectada: NF nº {nNF} do emitente "
                    f"{formatar_cnpj_display(cnpj_emit)} aparece mais de uma vez no lote"
                )
        return df

    # ── Validações v2.0 ───────────────────────────────────────────────────────

    def _val_cfop_tipo_operacao(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Regra v2.0: Verifica se o CFOP é compatível com o tipo de operação (tpNF).

        Lógica:
        - CFOP 1xxx/2xxx = entrada → tpNF deve ser '0'
        - CFOP 5xxx/6xxx = saída  → tpNF deve ser '1'
        - CFOP 7xxx = exportação  → não valida
        """
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue

            cfop = str(row.get('cfop') or '').strip()
            tpNF = str(row.get('tpNF') or '').strip()

            if not cfop or not tpNF:
                continue

            prefixo = cfop[0] if cfop else ''

            if prefixo in CFOP_EXPORTACAO_PREFIXOS:
                continue  # Exportação: não aplicamos essa regra

            if prefixo in CFOP_SAIDA_PREFIXOS and tpNF == '0':
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ CFOP de saída ({cfop}) em nota classificada como entrada (tpNF=0) — "
                    f"verifique a natureza da operação"
                )
            elif prefixo in CFOP_ENTRADA_PREFIXOS and tpNF == '1':
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ CFOP de entrada ({cfop}) em nota classificada como saída (tpNF=1) — "
                    f"verifique a natureza da operação"
                )
        return df

    def _val_icms_coerencia(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Regra v2.0: Verifica se o vICMS declarado é coerente com vBC × pICMS / 100.

        Só aplica quando temos vBC, vICMS e pICMS disponíveis.
        Tolerância de R$ 0,10 para arredondamentos.
        """
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue

            vBC   = row.get('vBC_num')
            vICMS = row.get('vICMS_num')
            pICMS = row.get('pICMS')

            # Pula se não temos os dados necessários ou ICMS é zero (isenção)
            if pd.isna(vBC) or pd.isna(vICMS) or pICMS is None:
                continue
            if vBC == 0 or vICMS == 0:
                continue

            icms_calculado = round(float(vBC) * float(pICMS) / 100, 2)
            icms_declarado = round(float(vICMS), 2)
            diferenca = abs(icms_calculado - icms_declarado)

            if diferenca > TOLERANCIA_ICMS:
                df.at[idx, 'alertas_erro'].append(
                    f"❌ ICMS inconsistente: declarado R$ {icms_declarado:.2f}, "
                    f"calculado R$ {icms_calculado:.2f} "
                    f"(BC={vBC:.2f} × {pICMS:.2f}% — diferença: R$ {diferenca:.2f})"
                )
        return df

    def _val_ncm_formato(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Regra v2.0: Verifica se o NCM tem exatamente 8 dígitos numéricos.

        Não aplica para notas de serviço (CFOP 5933, 6933 e similares).
        """
        # CFOPs tipicamente de serviço (não exigem NCM de 8 dígitos da TIPI)
        CFOP_SERVICO = {'5933', '6933', '5949', '6949'}

        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue

            ncm  = str(row.get('ncm') or '').strip()
            cfop = str(row.get('cfop') or '').strip()

            # Nota de serviço: NCM é opcional ou tem formato diferente
            if cfop in CFOP_SERVICO:
                continue

            if not ncm:
                df.at[idx, 'alertas_aviso'].append(
                    "⚠️ NCM não informado — obrigatório para notas de mercadoria"
                )
            else:
                ncm_digits = ''.join(c for c in ncm if c.isdigit())
                if len(ncm_digits) != 8:
                    df.at[idx, 'alertas_aviso'].append(
                        f"⚠️ NCM fora do padrão: '{ncm}' tem {len(ncm_digits)} dígito(s) "
                        f"(obrigatório: 8 dígitos TIPI)"
                    )
        return df

    def _val_itens_valor_zero(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Regra v2.0: Avisa quando há itens com vProd = 0 em nota com valor total > 0.

        Pode indicar erro de digitação, item cancelado não removido ou
        desconto aplicado incorretamente no item em vez no total.
        """
        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue

            itens_zero = row.get('itens_valor_zero') or []
            vNF        = row.get('vNF_num', 0) or 0

            if itens_zero and vNF > 0:
                nomes = ', '.join(f'"{n}"' for n in itens_zero[:3])
                sufixo = f' e mais {len(itens_zero)-3}' if len(itens_zero) > 3 else ''
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ {len(itens_zero)} item(ns) com valor R$ 0,00: {nomes}{sufixo} — "
                    f"verifique se há erro de digitação"
                )
        return df

    def _val_cobranca_ausente(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Regra v2.0: Avisa quando uma nota de venda de MERCADORIA não possui
        dados de cobrança (<cobr>/<dup>).

        Aplica apenas para CFOPs de venda de mercadoria para entrega futura
        ou venda à vista (5101, 5102, 5405, 6101, 6102, etc.).
        Exclui: serviços (5933, 5949), ativos (5551, 5553), remessas (5901+), devoluções.
        """
        # CFOPs de venda de mercadoria que normalmente exigem fatura
        CFOP_VENDA_MERCADORIA_PREFIXOS = {
            '5101', '5102', '5103', '5104', '5105', '5106',
            '5401', '5403', '5405',
            '6101', '6102', '6103', '6104', '6105', '6106',
            '6401', '6403', '6404',
        }

        for idx, row in df.iterrows():
            if not row.get('parse_ok', True):
                continue

            tpNF        = str(row.get('tpNF') or '').strip()
            cfop        = str(row.get('cfop') or '').strip()
            temCobranca = row.get('temCobranca', False)
            vNF         = row.get('vNF_num', 0) or 0

            # Só aplica para notas de saída, CFOPs de venda de mercadoria
            if tpNF == '1' and cfop in CFOP_VENDA_MERCADORIA_PREFIXOS and vNF > 0 and not temCobranca:
                df.at[idx, 'alertas_aviso'].append(
                    f"⚠️ Nota de venda de mercadoria (CFOP {cfop}) sem dados de cobrança/fatura — "
                    f"verifique se a nota foi vinculada ao contas a receber"
                )
        return df

    # ── Status final ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_status(row) -> str:
        """Determina o status final com base nos alertas encontrados."""
        if row['alertas_erro']:
            return 'ERRO'
        elif row['alertas_aviso']:
            return 'AVISO'
        return 'OK'

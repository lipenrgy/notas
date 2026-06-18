"""
exporter.py
Exportação do relatório de triagem para CSV e Excel com formatação profissional.
"""
import io
import pandas as pd
from datetime import datetime

# Colunas exportadas e seus nomes amigáveis para os cabeçalhos
COLUNAS_EXPORT = {
    'arquivo':    'Arquivo',
    'nNF':        'Nº NF',
    'serie':      'Série',
    'dhEmi':      'Data Emissão',
    'natOp':      'Natureza Operação',
    'cfop':       'CFOP',
    'ncm':        'NCM',
    'cnpj_emit':  'CNPJ Emitente',
    'nome_emit':  'Emitente',
    'uf_emit':    'UF Emit.',
    'cnpj_dest':  'CNPJ Destinatário',
    'nome_dest':  'Destinatário',
    'uf_dest':    'UF Dest.',
    'vNF':        'Valor Total (R$)',
    'vICMS':      'ICMS (R$)',
    'vPIS':       'PIS (R$)',
    'vCOFINS':    'COFINS (R$)',
    'chNFe':      'Chave de Acesso',
    'status':     'Status',
    'qtd_erros':  'Qtd. Erros',
    'qtd_avisos': 'Qtd. Avisos',
    'alertas_texto': 'Detalhes',
}

# Cores por status para Excel
CORES_STATUS = {
    'OK':    {'bg': '#d4edda', 'fg': '#155724'},
    'AVISO': {'bg': '#fff3cd', 'fg': '#856404'},
    'ERRO':  {'bg': '#f8d7da', 'fg': '#721c24'},
}


def _preparar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona e renomeia colunas para exportação."""
    colunas_validas = {k: v for k, v in COLUNAS_EXPORT.items() if k in df.columns}
    df_export = df[list(colunas_validas.keys())].copy()
    df_export = df_export.rename(columns=colunas_validas)
    return df_export


def exportar_csv(df: pd.DataFrame) -> bytes:
    """
    Exporta o DataFrame de triagem para CSV.

    Usa encoding UTF-8 com BOM para compatibilidade com Excel no Windows.
    """
    df_export = _preparar_df(df)
    csv_str = df_export.to_csv(index=False, encoding='utf-8-sig')
    return csv_str.encode('utf-8-sig')


def exportar_excel(df: pd.DataFrame) -> bytes:
    """
    Exporta o DataFrame de triagem para Excel (.xlsx) com:
    - Cabeçalho formatado (fundo azul-escuro, texto branco, negrito)
    - Linhas coloridas por status (verde/amarelo/vermelho)
    - Larguras de coluna ajustadas automaticamente
    - Filtros automáticos no cabeçalho
    - Aba de resumo com estatísticas do lote
    """
    df_export = _preparar_df(df)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # ── Aba Principal ──────────────────────────────────────────────────────
        df_export.to_excel(writer, index=False, sheet_name='Notas Fiscais')
        workbook = writer.book
        ws_notas = writer.sheets['Notas Fiscais']

        # Formatos base
        fmt_header = workbook.add_format({
            'bold': True,
            'bg_color': '#1e3a5f',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        fmt_default = workbook.add_format({'border': 1, 'valign': 'vcenter'})

        # Formatos de status
        fmt_status = {}
        for status, cores in CORES_STATUS.items():
            fmt_status[status] = workbook.add_format({
                'bg_color': cores['bg'],
                'font_color': cores['fg'],
                'bold': True,
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
            })

        # Formatos de linha (sem bold)
        fmt_row = {}
        for status, cores in CORES_STATUS.items():
            fmt_row[status] = workbook.add_format({
                'bg_color': cores['bg'],
                'border': 1,
                'valign': 'vcenter',
            })

        # Escreve cabeçalho formatado
        for col_num, col_name in enumerate(df_export.columns):
            ws_notas.write(0, col_num, col_name, fmt_header)

        # Escreve dados com coloração por status
        status_col_name = COLUNAS_EXPORT.get('status', 'Status')
        cols = list(df_export.columns)

        for row_idx, (_, row) in enumerate(df_export.iterrows(), start=1):
            status_val = str(row.get(status_col_name, ''))
            row_fmt = fmt_row.get(status_val, fmt_default)
            st_fmt = fmt_status.get(status_val, fmt_default)

            for col_idx, col_name in enumerate(cols):
                val = row[col_name]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    val = ''
                if col_name == status_col_name:
                    ws_notas.write(row_idx, col_idx, val, st_fmt)
                else:
                    ws_notas.write(row_idx, col_idx, val, row_fmt)

        # Ajusta larguras das colunas
        larguras = {
            'Arquivo': 28, 'Nº NF': 10, 'Série': 8, 'Data Emissão': 18,
            'Natureza Operação': 25, 'CFOP': 8, 'NCM': 12,
            'CNPJ Emitente': 20, 'Emitente': 35,
            'CNPJ Destinatário': 20, 'Destinatário': 35,
            'Valor Total (R$)': 15, 'ICMS (R$)': 12, 'PIS (R$)': 12, 'COFINS (R$)': 12,
            'Chave de Acesso': 48, 'Status': 10, 'Detalhes': 60,
        }
        for col_idx, col_name in enumerate(df_export.columns):
            ws_notas.set_column(col_idx, col_idx, larguras.get(col_name, 15))

        # Filtros automáticos no cabeçalho
        ws_notas.autofilter(0, 0, len(df_export), len(df_export.columns) - 1)
        ws_notas.freeze_panes(1, 0)  # Congela linha do cabeçalho

        # ── Aba de Resumo ─────────────────────────────────────────────────────
        ws_resumo = workbook.add_worksheet('Resumo')
        fmt_titulo = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_color': '#1e3a5f'
        })
        fmt_rotulo = workbook.add_format({'bold': True, 'font_color': '#555555'})
        fmt_valor = workbook.add_format({'num_format': '#,##0', 'align': 'right'})

        total = len(df)
        n_ok = (df.get('status', pd.Series()) == 'OK').sum()
        n_aviso = (df.get('status', pd.Series()) == 'AVISO').sum()
        n_erro = (df.get('status', pd.Series()) == 'ERRO').sum()
        vNF_num = pd.to_numeric(df.get('vNF', pd.Series()), errors='coerce')
        valor_total = vNF_num.sum()

        data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')

        ws_resumo.write('A1', 'TriageNFe — Resumo do Lote', fmt_titulo)
        ws_resumo.write('A3', 'Data de geração:', fmt_rotulo)
        ws_resumo.write('B3', data_geracao)
        ws_resumo.write('A5', 'Total de notas:', fmt_rotulo)
        ws_resumo.write('B5', total, fmt_valor)
        ws_resumo.write('A6', 'Notas OK:', fmt_rotulo)
        ws_resumo.write('B6', n_ok, fmt_valor)
        ws_resumo.write('A7', 'Notas com aviso:', fmt_rotulo)
        ws_resumo.write('B7', n_aviso, fmt_valor)
        ws_resumo.write('A8', 'Notas com erro:', fmt_rotulo)
        ws_resumo.write('B8', n_erro, fmt_valor)
        ws_resumo.write('A10', 'Valor total do lote (R$):', fmt_rotulo)
        ws_resumo.write('B10', valor_total, workbook.add_format({
            'num_format': 'R$ #,##0.00', 'bold': True
        }))

        ws_resumo.set_column('A:A', 28)
        ws_resumo.set_column('B:B', 18)

    return output.getvalue()

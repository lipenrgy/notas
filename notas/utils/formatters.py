"""
formatters.py
Funções utilitárias de formatação para valores monetários, datas e CNPJ.
"""
import re
from datetime import datetime
from typing import Optional
from utils.cnpj_utils import limpar_cnpj


def formatar_moeda(valor) -> str:
    """
    Formata um valor numérico como moeda brasileira: R$ X.XXX,XX
    Retorna 'R$ 0,00' para valores inválidos ou nulos.
    """
    try:
        if valor is None:
            return "R$ 0,00"
        v = float(valor)
        # Formata com separador de milhar (.) e decimal (,)
        formatted = f"{v:,.2f}"
        formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_data(data_str: str) -> str:
    """
    Converte string de data ISO 8601 para o formato brasileiro: DD/MM/AAAA HH:MM
    Aceita formatos como 2024-06-18T10:00:00-03:00 ou 2024-06-18T10:00:00
    """
    if not data_str:
        return ""
    try:
        # Remove timezone offset para simplificar o parse
        data_limpa = re.sub(r'[+-]\d{2}:\d{2}$', '', str(data_str).strip())
        dt = datetime.fromisoformat(data_limpa)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(data_str)


def parse_data(data_str: str) -> Optional[datetime]:
    """
    Converte string de data ISO 8601 para objeto datetime.
    Retorna None em caso de erro.
    """
    if not data_str:
        return None
    try:
        data_limpa = re.sub(r'[+-]\d{2}:\d{2}$', '', str(data_str).strip())
        return datetime.fromisoformat(data_limpa)
    except Exception:
        return None


def formatar_cnpj_display(cnpj: str) -> str:
    """
    Formata CNPJ para exibição como XX.XXX.XXX/XXXX-XX.
    Retorna string vazia se o CNPJ for inválido ou ausente.
    """
    if not cnpj:
        return ""
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj


def formatar_chave(chave: str) -> str:
    """
    Formata chave de acesso NF-e em grupos de 4 dígitos para legibilidade.
    Ex: 3524 0611 4447 7700 0161 5500 ...
    """
    if not chave:
        return ""
    chave = re.sub(r'\D', '', str(chave))
    return ' '.join(chave[i:i+4] for i in range(0, len(chave), 4))

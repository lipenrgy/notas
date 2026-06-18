"""
cnpj_utils.py
Validação de CNPJ usando o algoritmo oficial dos dígitos verificadores da Receita Federal.
"""
import re


def limpar_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ, mantendo apenas dígitos."""
    return re.sub(r'\D', '', str(cnpj)) if cnpj else ''


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ usando o algoritmo oficial dos dígitos verificadores.
    Aceita CNPJ com ou sem formatação (XX.XXX.XXX/XXXX-XX ou 14 dígitos).

    Retorna True se o CNPJ for válido, False caso contrário.
    """
    cnpj = limpar_cnpj(cnpj)

    # Deve ter exatamente 14 dígitos
    if len(cnpj) != 14:
        return False

    # Rejeita sequências de dígitos todos iguais (ex: 00000000000000, 11111111111111)
    if len(set(cnpj)) == 1:
        return False

    # ── Primeiro dígito verificador ──
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    digito1 = 0 if resto1 < 2 else 11 - resto1

    if int(cnpj[12]) != digito1:
        return False

    # ── Segundo dígito verificador ──
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto2 = soma2 % 11
    digito2 = 0 if resto2 < 2 else 11 - resto2

    if int(cnpj[13]) != digito2:
        return False

    return True


def formatar_cnpj(cnpj: str) -> str:
    """
    Formata CNPJ como XX.XXX.XXX/XXXX-XX.
    Retorna o valor original se não tiver 14 dígitos.
    """
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

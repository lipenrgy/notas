"""
Configuração e funções de integração com o Google Gemini.
"""
import google.generativeai as genai
from typing import Dict, List, Any, Tuple

def configurar_api(api_key: str) -> bool:
    """Configura a chave de API do Gemini. Retorna True se sucesso."""
    if not api_key or not api_key.strip():
        return False
    try:
        genai.configure(api_key=api_key.strip())
        return True
    except Exception:
        return False

def analisar_inconsistencias(dados_nota: Dict[str, Any], alertas: List[str]) -> Tuple[bool, str]:
    """
    Envia os dados da nota e os alertas para o Gemini analisar.
    Retorna uma tupla (sucesso: bool, resposta: str).
    """
    if not alertas:
        return True, "Nenhuma inconsistência encontrada para analisar."

    try:
        # Monta um resumo da nota para dar contexto à IA
        resumo_nota = f"""
- Número da NF: {dados_nota.get('nNF', 'N/A')}
- CFOP: {dados_nota.get('cfop', 'N/A')}
- Natureza da Operação: {dados_nota.get('natOp', 'N/A')}
- NCM (do primeiro item, se houver): {dados_nota.get('ncm', 'N/A')}
- Tem Cobrança/Fatura?: {'Sim' if dados_nota.get('temCobranca') else 'Não'}
- Valor Total: R$ {dados_nota.get('vNF', '0.00')}
        """.strip()

        lista_alertas = "\n".join([f"- {a}" for a in alertas])

        prompt = f"""
Você é um auditor fiscal experiente do Brasil, especialista em ICMS, CFOP e regras da SEFAZ.
Analise a seguinte Nota Fiscal e os alertas de erro/aviso gerados pelo sistema.

**DADOS DA NOTA FISCAL:**
{resumo_nota}

**INCONSISTÊNCIAS ENCONTRADAS PELO SISTEMA:**
{lista_alertas}

**SUA TAREFA:**
1. Explique brevemente (em linguagem clara e profissional) o que essas inconsistências significam na prática.
2. Sugira os passos práticos que o analista fiscal ou o contador deve tomar para corrigir esse problema no ERP ou junto ao emissor da nota.
3. Formate sua resposta em Markdown, utilizando listas e negrito para facilitar a leitura. Seja direto e evite enrolações.
        """

        # Tenta listar os modelos disponíveis na conta do usuário
        # e escolhe o primeiro que suporte geração de texto (generateContent)
        modelos_disponiveis = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        if not modelos_disponiveis:
            return False, "❌ Nenhum modelo de IA foi encontrado ou liberado para essa API Key."
            
        # Prefere o gemini-1.5-flash, senão pega o primeiro da lista (gemini-pro, etc)
        model_name = modelos_disponiveis[0]
        for m in modelos_disponiveis:
            if '1.5-flash' in m:
                model_name = m
                break

        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        return True, response.text

    except Exception as e:
        erro_msg = str(e)
        if "API_KEY_INVALID" in erro_msg or "400" in erro_msg:
            return False, "❌ Chave da API inválida ou sem permissão. Verifique sua chave na barra lateral."
        elif "429" in erro_msg or "Quota" in erro_msg:
            return False, "⏳ Limite de requisições grátis atingido! O Google permite poucas consultas por minuto no plano gratuito. Por favor, aguarde cerca de 30 segundos e tente analisar esta nota novamente."
        return False, f"❌ Erro ao consultar a IA: {erro_msg}"

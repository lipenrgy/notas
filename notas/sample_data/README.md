# 📂 Dados de Exemplo — TriageNFe

Esta pasta contém arquivos XML de NF-e para testar a ferramenta.

## Arquivos incluídos

| Arquivo | Status esperado | Cenário |
|---------|----------------|---------|
| `nfe_valida_001.xml` | ✅ OK | NF-e de venda de mercadoria, todos os dados válidos |
| `nfe_valida_002.xml` | ✅ OK | NF-e de prestação de serviço, emitente diferente |
| `nfe_erro_cnpj_003.xml` | ❌ ERRO | CNPJ do emitente com dígitos verificadores errados |
| `nfe_aviso_data_004.xml` | ⚠️ AVISO | Data de emissão no futuro (2027) |
| `nfe_aviso_duplicada_005.xml` | ⚠️ AVISO | Mesmo nº de NF (1234) e CNPJ emitente da nota 001 |

## Como testar

1. Execute o app: `streamlit run app.py`
2. Clique em **"Browse files"** e selecione **todos os 5 arquivos de uma vez** (Ctrl+A)
3. Clique em **"🔍 Processar Notas"**
4. Observe os resultados:
   - 2 notas OK
   - 2 avisos (data futura + duplicata)
   - 1 erro (CNPJ inválido)

## CNPJs usados nos exemplos

> Todos os CNPJs válidos foram calculados usando o algoritmo oficial da Receita Federal.

| CNPJ | Empresa | Status |
|------|---------|--------|
| `11.444.777/0001-61` | DISTRIBUIDORA ALFA COMERCIO LTDA | ✅ Válido |
| `22.333.444/0001-81` | TECH SOLUTIONS INFORMATICA LTDA | ✅ Válido |
| `33.000.167/0001-01` | COMERCIO BETA ATACADO SA | ✅ Válido |
| `11.444.777/0001-00` | FORNECEDOR SUSPEITO EIRELI | ❌ Inválido (propositalmente) |

## Usando com arquivos reais

Para usar com suas NF-e reais:
1. Certifique-se de que os arquivos estão no formato XML SEFAZ (`.xml`)
2. A ferramenta suporta tanto o formato completo `nfeProc` (com protocolo de autorização) quanto só a `NFe`
3. Você pode processar dezenas de arquivos de uma vez

## Estrutura XML suportada

```xml
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe...">
      <ide> ... </ide>     <!-- número, série, data, CFOP -->
      <emit> ... </emit>   <!-- CNPJ e dados do emitente -->
      <dest> ... </dest>   <!-- CNPJ e dados do destinatário -->
      <total> ... </total> <!-- valores: vNF, vICMS, vPIS, vCOFINS -->
    </infNFe>
  </NFe>
</nfeProc>
```

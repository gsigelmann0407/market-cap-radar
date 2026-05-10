"""
Teste de conexao Bloomberg via xbbg.
Execute com o Bloomberg Terminal aberto e logado:
    python teste_bloomberg.py
"""

print("Verificando importacao do xbbg...")
try:
    from xbbg import blp
except ImportError as e:
    print(f"\n[ERRO] xbbg nao esta instalado: {e}")
    print("Instale com: pip install xbbg")
    raise SystemExit(1)

print("OK — xbbg importado.\n")
print("Conectando ao Bloomberg Terminal e buscando AAPL US Equity...")

try:
    df = blp.bdp("AAPL US Equity", "CUR_MKT_CAP")
    mkt_cap = df.loc["AAPL US Equity", "cur_mkt_cap"]
    print(f"\n[OK] Conexao bem-sucedida!")
    print(f"     Market Cap Apple (AAPL): US$ {mkt_cap:,.0f}")
    print(f"     (~US$ {mkt_cap / 1e9:,.1f} bilhoes)")
except Exception as e:
    print(f"\n[ERRO] Falha ao consultar o Bloomberg: {e}")
    print("\nVerifique se:")
    print("  1. O Bloomberg Terminal esta aberto e voce esta logado")
    print("  2. A sessao Bloomberg Python API (blpapi) esta ativa")
    print("  3. O pacote blpapi esta instalado: pip install blpapi")

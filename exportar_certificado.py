# ============================================================
#  MARKET CAP RADAR — Exportar certificado corporativo
#  Exporta os certificados do Windows Certificate Store
#  para empresa.pem, usado pelo curl_cffi / yfinance em
#  redes com inspeção SSL corporativa.
#
#  Uso (rodar uma vez, como administrador se necessário):
#      python exportar_certificado.py
#  Saída: empresa.pem  (na mesma pasta do script)
# ============================================================

import base64
import ssl
import sys
from pathlib import Path

ARQUIVO_SAIDA = Path(__file__).parent / "empresa.pem"

# Lojas do Windows Certificate Store a incluir
LOJAS = [
    "ROOT",   # Trusted Root Certification Authorities
    "CA",     # Intermediate Certification Authorities
]


def der_para_pem(der: bytes) -> str:
    """Converte um certificado DER (binário) para PEM (texto base64)."""
    b64 = base64.b64encode(der).decode("ascii")
    linhas = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(linhas) + "\n-----END CERTIFICATE-----\n"


def exportar():
    if sys.platform != "win32":
        print("ERRO: este script usa o Windows Certificate Store e só roda no Windows.")
        sys.exit(1)

    total = 0
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        for loja in LOJAS:
            try:
                certificados = ssl.enum_certificates(loja)
                count = 0
                for cert_data, encoding_type, _ in certificados:
                    if encoding_type == "x509_asn":   # formato DER
                        f.write(der_para_pem(cert_data))
                        count += 1
                print(f"  Loja '{loja}': {count} certificado(s) exportado(s)")
                total += count
            except Exception as exc:
                print(f"  Loja '{loja}': erro — {exc}")

    print(f"\nOK: {total} certificados salvos em: {ARQUIVO_SAIDA}")
    print("  Configure CURL_CA_BUNDLE apontando para esse arquivo.")


if __name__ == "__main__":
    print("Exportando certificados do Windows Certificate Store...\n")
    exportar()

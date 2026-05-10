# ============================================================
#  MARKET CAP RADAR — Configurações
#  Edite este arquivo antes de rodar pela primeira vez
# ============================================================

# --- Supabase (banco de dados na nuvem) ---------------------
# Crie sua conta gratuita em supabase.com
# Copie a URL e a chave anon do painel do projeto
SUPABASE_URL = "https://axaxmlqlynkzcfifvznz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF4YXhtbHFseW5remNmaWZ2em56Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgzNjE1MzksImV4cCI6MjA5MzkzNzUzOX0.RpoGkgYP9LSFx8UxibDF80MQ5JJM8E8241cW3goR7hA"


# --- Bloomberg ---------------------------------------------
# Universo de empresas: índice usado para buscar as top 500
# Opções comuns: 'MSCI_ACWI Index', 'MXWD Index'
BLOOMBERG_UNIVERSO = "MXWD Index"
BLOOMBERG_TOP_N    = 500

# --- Coleta ------------------------------------------------
# Horário que o Task Scheduler vai rodar (só para referência)
HORARIO_COLETA = "07:00"

# Períodos para cálculo de rank velocity (em dias úteis)
JANELAS_DIAS = [7, 30, 90]

# Moeda de referência para market cap
MOEDA_BASE = "USD"

-- Cole isso no SQL Editor do Supabase (supabase.com → seu projeto → SQL Editor)

CREATE TABLE IF NOT EXISTS snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    data                DATE          NOT NULL,
    ticker              TEXT          NOT NULL,
    nome                TEXT,
    rank                INTEGER       NOT NULL,
    market_cap_usd      NUMERIC(20,2),
    preco               NUMERIC(20,4),
    variacao_dia_pct    NUMERIC(8,4),
    setor               TEXT,
    pais                TEXT,
    criado_em           TIMESTAMPTZ   DEFAULT NOW(),

    UNIQUE (ticker, data)   -- evita duplicatas
);

-- Índices para queries rápidas
CREATE INDEX IF NOT EXISTS idx_snapshots_data   ON snapshots (data DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots (ticker);
CREATE INDEX IF NOT EXISTS idx_snapshots_rank   ON snapshots (rank);

# 📡 Market Cap Radar

Dashboard automatizado de monitoramento das 500 maiores empresas do mundo por market cap.

---

## Arquitetura

```
Bloomberg Terminal (máquina do escritório, 24/7)
    └── coletor.py  →  roda todo dia às 7h via Task Scheduler
            └──→  Supabase (banco na nuvem, gratuito)
                        └──→  dashboard.py  →  Streamlit Cloud (link público)
```

---

## Setup — passo a passo

### 1. Criar o banco de dados (Supabase)

1. Acesse [supabase.com](https://supabase.com) e crie uma conta gratuita
2. Crie um novo projeto
3. Vá em **SQL Editor** e cole o conteúdo de `banco.sql` → Execute
4. Vá em **Project Settings → API** e copie:
   - `Project URL`  →  cole em `config.py` no campo `SUPABASE_URL`
   - `anon public key`  →  cole em `config.py` no campo `SUPABASE_KEY`

---

### 2. Instalar dependências (máquina Bloomberg)

Abra o terminal (cmd ou PowerShell) na pasta do projeto:

```bash
pip install -r requirements.txt
```

---

### 3. Testar a coleta manualmente

Com o Bloomberg Terminal aberto e logado:

```bash
python coletor.py
```

Se tudo correr bem, você verá no terminal:
```
07:00:01  INFO  Buscando top 500 empresas no Bloomberg...
07:00:08  INFO  500 empresas coletadas com sucesso.
07:00:09  INFO  Conectando ao Supabase...
07:00:10  INFO  500 registros salvos no banco.
07:00:10  INFO  Coleta concluída com sucesso. ✓
```

---

### 4. Agendar coleta automática (Task Scheduler — Windows)

1. Abra o **Agendador de Tarefas** (Task Scheduler) no Windows
2. Clique em **Criar Tarefa Básica**
3. Nome: `Market Cap Radar - Coleta Diária`
4. Gatilho: **Diariamente** às **07:00**
5. Ação: **Iniciar um programa**
   - Programa: `python`
   - Argumentos: `coletor.py`
   - Iniciar em: `C:\caminho\para\market-cap-radar`  ← pasta do projeto no OneDrive
6. Em **Condições**: desmarque "Iniciar apenas se o computador estiver na rede AC"
7. Salvar

---

### 5. Publicar o dashboard (Streamlit Cloud)

1. Coloque a pasta do projeto no GitHub (repositório privado)
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte o repositório
4. Arquivo principal: `dashboard.py`
5. Em **Secrets**, adicione:
   ```toml
   SUPABASE_URL = "https://SEU_PROJETO.supabase.co"
   SUPABASE_KEY = "SUA_CHAVE_ANON"
   ```
6. Deploy → você recebe um link público para compartilhar

---

## Uso

- **Coleta**: automática todo dia às 7h, sem intervenção humana
- **Dashboard**: abra o link do Streamlit no browser — funciona em qualquer dispositivo
- **Filtros disponíveis**: período (7/30/90 dias), setor, país, número de empresas
- **Análises**: rank velocity, mapa setorial, evolução individual de empresa

---

## Arquivos

| Arquivo | Função |
|---------|--------|
| `config.py` | Configurações centrais (Supabase, Bloomberg) |
| `coletor.py` | Coleta dados do Bloomberg e salva no Supabase |
| `dashboard.py` | Dashboard Streamlit |
| `banco.sql` | SQL para criar a tabela no Supabase |
| `requirements.txt` | Dependências Python |

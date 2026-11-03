# 📈 Market Watch — Monitor de ações na web

Dashboard web que acompanha preços de ações/BDRs em tempo real, guarda o histórico,
gera gráficos e envia notificações do navegador quando o preço muda. Substitui o
bot do Telegram por uma interface visual e permite monitorar vários ativos ao mesmo tempo.

## ✨ Funcionalidades

- 💹 Preços em tempo real via API pública do Yahoo Finance (SSE, sem recarregar a página).
- 📊 Gráfico histórico com períodos de 1h, 6h, 24h, 7d e tudo.
- 🔔 Notificações do navegador para cada variação e/ou para alertas de limite.
- ➕ Adicionar, editar e remover ativos direto pela interface.
- 🎯 Alertas de alta e de baixa por ativo (disparam ao cruzar o valor).
- 🗂️ Histórico persistido em SQLite (`market.db`).
- 🌙 Interface escura e responsiva.

## 🛠️ Tecnologias

- **Flask** — servidor web, API REST e Server-Sent Events (SSE).
- **Yahoo Finance (endpoint público de chart)** — fonte dos preços e do histórico.
- **SQLite** — armazenamento local dos ativos, preços e alertas.
- **Chart.js** — gráficos no navegador.
- **Selenium** — apenas para o provedor opcional da Investing.com.

## ⚙️ Como usar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abra **http://127.0.0.1:5000** no navegador.

Ao iniciar, o app já cria o ativo padrão **AAPL34.SA** (Apple BDR) e carrega o
histórico recente. Para acompanhar outro ativo, clique em **+ Adicionar ativo** e
informe o símbolo do Yahoo Finance:

| Ativo | Símbolo |
| --- | --- |
| Apple BDR | `AAPL34.SA` |
| Apple (EUA) | `AAPL` |
| Microsoft | `MSFT` |
| Petrobras PN | `PETR4.SA` |
| Vale ON | `VALE3.SA` |
| S&P 500 | `^GSPC` |

Nome, moeda e preço são buscados automaticamente. O monitor consulta todos os
ativos a cada intervalo configurado (padrão: 60 segundos).

### Notificações

Clique em **Ativar notificações** e permita no navegador. Depois escolha em
**Notificações**:

- **Avisar a cada variação** — notifica quando o preço muda entre uma leitura e outra.
- **Alertas de limite** — notifica quando o preço cruza o alerta de alta ou de baixa.

As notificações funcionam enquanto a aba estiver aberta. Para notificações com a
aba fechada seria necessário Web Push com service worker (não incluído).

## 🔌 API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/assets` | Lista ativos com último preço e variação |
| `POST` | `/api/assets` | Adiciona ativo (`symbol`, `name`, `alert_above`, `alert_below`) |
| `PATCH` | `/api/assets/<id>` | Atualiza nome e alertas |
| `DELETE` | `/api/assets/<id>` | Remove ativo |
| `GET` | `/api/assets/<id>/history` | Histórico (`?minutes=60&limit=2000`) |
| `GET` | `/api/alerts` | Alertas recentes |
| `GET` | `/api/status` | Status do monitor |
| `POST` | `/api/refresh` | Solicita uma coleta imediata |
| `GET` | `/api/stream` | Stream SSE com preços e alertas ao vivo |

## ⚙️ Variáveis de ambiente

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `POLL_INTERVAL` | `60` | Intervalo entre coletas (segundos) |
| `PORT` | `5000` | Porta do servidor |
| `DB_PATH` | `market.db` | Caminho do banco SQLite |
| `DISABLE_MONITOR` | `0` | `1` desliga o coletor automático |
| `HEADLESS` | `1` | `0` mostra o Chrome (provedor Investing) |

## 📁 Estrutura

```
app.py            # Flask, API, SSE e agendador de coletas
db.py             # SQLite: ativos, preços e alertas
scraper.py        # Yahoo Finance (principal) + Investing via Selenium (opcional)
templates/
  index.html      # Dashboard
static/
  css/style.css
  js/app.js       # Atualização ao vivo, gráficos e notificações
requirements.txt
```

## 📝 Observações

- O provedor padrão é o **Yahoo Finance**. A Investing.com passou a bloquear
  automação com HTTP 403, por isso não é mais usado por padrão.
- `main.py` e `bot.py` são a versão antiga (Telegram). A interface web substitui
  esses arquivos e eles podem ser removidos.
- ⚠️ O `bot.py` antigo contém um token do Telegram hardcoded. **Revogue esse token
  no @BotFather** e não o reutilize.

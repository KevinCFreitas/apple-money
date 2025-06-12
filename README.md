# 📈 AAPLNotifier – Notificações em Tempo Real das Ações da Apple via Telegram
monitora o preço das ações da Apple (AAPL) em tempo real, gera gráficos e envia notificações diretamente no Telegram. Ideal para investidores e entusiastas do mercado financeiro que querem se manter atualizados com dados visuais.

## 🚀 Funcionalidades

- 💸 Monitora o preço das ações da Apple (AAPL) em tempo real.
- 📊 Gera gráficos com histórico dos preços usando Matplotlib.
- 💬 Envia as atualizações diretamente em um chat do Telegram.
- 🕐 Funciona de forma automática em intervalos programados.

## 🛠️ Tecnologias Utilizadas

- `Python 3`
- `requests` – para obter dados de preço
- `matplotlib` + `pandas` – para análise e geração de gráficos
- `selenium` – para controle automatizado do navegador
- `webdriver_manager` – para gerenciamento do ChromeDriver
- `telegram` – envio de mensagens via API do Telegram
- `csv`, `os`, `datetime`, `time`

## ⚙️ Como Usar

Clone o repositório:

```bash
git clone https://github.com/seunome/aapl-notifier.git
cd aapl-notifier
pip install -r requirements.txt

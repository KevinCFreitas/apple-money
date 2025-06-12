import requests
import csv
import os
import time
import matplotlib.pyplot as plt
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = '7608403924:AAG3M8tkiuSf3nw7k2-pBNi_syTPkTgH3O8'
CHAT_ID = '1067276034'
ALERTA_VALOR = 100.00
ARQUIVO = 'historico_precos.csv'
GRAFICO = 'grafico.png'
URL = 'https://br.investing.com/equities/apple-inc-bdr'


def iniciar_navegador():
    options = Options()
    options.add_argument('--start-maximized')
    
    service = Service(ChromeDriverManager().install())
    navegador = webdriver.Chrome(service=service, options=options)
    navegador.get(URL)
    return navegador



def capturar_preco(navegador):
    try:
        wait = WebDriverWait(navegador, 20)
        elemento = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            '#__next > div.md\\:relative.md\\:bg-white > div.relative.flex > div.md\\:grid-cols-\\[1fr_72px\\].md2\\:grid-cols-\\[1fr_420px\\].grid.flex-1.grid-cols-1.px-4.pt-5.font-sans-v2.text-\\[\\#232526\\].antialiased.transition-all.xl\\:container.sm\\:px-6.md\\:gap-6.md\\:px-7.md\\:pt-10.md2\\:gap-8.md2\\:px-8.xl\\:mx-auto.xl\\:gap-10.xl\\:px-10 > div.min-w-0 > div.flex.flex-col.gap-6.md\\:gap-0 > div.flex.gap-6 > div.flex-1 > div.mb-3.flex.flex-wrap.items-center.gap-x-4.gap-y-2.md\\:mb-0\\.5.md\\:gap-6 > div.text-5xl\\/9.font-bold.text-\\[\\#232526\\].md\\:text-\\[42px\\].md\\:leading-\\[60px\\]'
        )))
        preco = float(elemento.text.replace("R$", "").replace(",", ".").strip())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{timestamp} - Preço: R${preco}")
        return timestamp, preco
    except Exception as e:
        print("Erro ao capturar preço:", e)
        return None, None



def salvar_csv(timestamp, preco):
    if not os.path.exists(ARQUIVO):
        with open(ARQUIVO, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["DataHora", "Preco"])
    with open(ARQUIVO, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, preco])


def gerar_grafico():
    df = pd.read_csv(ARQUIVO)
    df["DataHora"] = pd.to_datetime(df["DataHora"])
    plt.figure(figsize=(10, 5))
    plt.plot(df["DataHora"], df["Preco"], marker='o', color='blue')
    plt.title("Histórico de Preços - Apple BDR")
    plt.xlabel("Data e Hora")
    plt.ylabel("Preço (R$)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(GRAFICO)
    plt.close()
    print("Gráfico gerado com sucesso!")


import requests

def enviar_telegram_texto(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Lança erro se status != 200
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar mensagem para o Telegram: {e}")



def enviar_telegram_imagem(caminho):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(caminho, 'rb') as foto:
        files = {'photo': foto}
        data = {'chat_id': CHAT_ID}
        response = requests.post(url, files=files, data=data)
    if response.status_code != 200:
        print("Erro ao enviar imagem:", response.text)


def monitorar(intervalo=60, rodadas=5):
    navegador = iniciar_navegador()
    for _ in range(rodadas):
        timestamp, preco = capturar_preco(navegador)
        if preco:
            salvar_csv(timestamp, preco)

            if preco >= ALERTA_VALOR:
                enviar_telegram_texto(f"🚨 ALERTA: Preço da Apple BDR subiu para R${preco}!")
            else:
                enviar_telegram_texto(f"📊 Preço atual: R${preco} às {timestamp}")
        time.sleep(intervalo)
    navegador.quit()

    # Gera e envia o gráfico no final
    gerar_grafico()
    enviar_telegram_imagem(GRAFICO)


if __name__ == "__main__":
    monitorar()

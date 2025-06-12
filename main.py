from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import time
import csv
import os

URL = "https://br.investing.com/equities/apple-inc-bdr"
ARQUIVO_CSV = "historico_precos.csv"


def iniciar_navegador():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # roda sem abrir o navegador
    navegador = webdriver.Chrome(options=options)
    navegador.get(URL)
    return navegador


def capturar_preco(navegador):
    try:
        wait = WebDriverWait(navegador, 10)
        elemento = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'div[data-test="instrument-price-last"]')
        ))
        preco_texto = elemento.text.replace(",", ".")
        preco_float = float(preco_texto)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} - Preço: R${preco_float}")
        return timestamp, preco_float
    except Exception as e:
        print("Erro ao capturar preço:", e)
        return None, None


def salvar_csv(timestamp, preco):
    if not os.path.exists(ARQUIVO_CSV):
        with open(ARQUIVO_CSV, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["DataHora", "Preco"])
    with open(ARQUIVO_CSV, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, preco])


def plotar_grafico():
    try:
        df = pd.read_csv(ARQUIVO_CSV)
        df["DataHora"] = pd.to_datetime(df["DataHora"])
        plt.figure(figsize=(10, 5))
        plt.plot(df["DataHora"], df["Preco"], marker="o", color="green")
        plt.title("Histórico de Preço - Apple BDR")
        plt.xlabel("Data e Hora")
        plt.ylabel("Preço (R$)")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print("Erro ao gerar gráfico:", e)


def monitorar(intervalo_segundos=60, rodadas=5):
    navegador = iniciar_navegador()
    for _ in range(rodadas):
        timestamp, preco = capturar_preco(navegador)
        if preco:
            salvar_csv(timestamp, preco)
        time.sleep(intervalo_segundos)
    navegador.quit()
    plotar_grafico()


if __name__ == "__main__":
    monitorar()

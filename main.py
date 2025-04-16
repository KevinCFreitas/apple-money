from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

# Inicia o navegador
navegador = webdriver.Chrome()
link = "https://br.investing.com/equities/apple-inc-bdr"
navegador.get(link)

try:
    # Espera o preço aparecer
    wait = WebDriverWait(navegador, 10)
    preço_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-test="instrument-price-last"]')))
    
    preço = preço_element.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{timestamp} - Preço: {preço}\n"

    print(linha)

    # Salva no arquivo (modo append)
    with open("historico_preços.txt", "a", encoding="utf-8") as arquivo:
        arquivo.write(linha)

except Exception as e:
    print("Erro:", e)

finally:
    navegador.quit()

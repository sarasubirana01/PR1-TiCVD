import os, time, re
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Paràmetres de configuració
START_URL = "https://www.movierankings.net"  # Pàgina inicial
MAX_PAGES = 2                                # Nombre màxim de pàgines a recórrer
SLEEP_BETWEEN_CLICKS = 2                     # Pausa entre clics
OUT_PATH = "dataset/movies_raw.csv"          # Ruta on es guardarà el CSV

# User-Agent del navegador
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def setup_driver():
    # Configura el navegador Chrome
    opts = Options()
    opts.add_argument(f"user-agent={UA}")
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver

def go_to_full_rankings(driver):
    # Clica el botó amb id=6 per accedir al rànquing complet
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "6")))
        btn = driver.find_element(By.ID, "6")
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(1)
        btn.click()
        print("Entrant a la vista de 'Full Rankings'")
        time.sleep(3)
    except Exception as e:
        print("No s'ha pogut fer clic al botó id=6:", e)

def scroll_full_page(driver, pause_time=0.8):
    # Fa scroll fins que ja no es carreguen més pel·lícules
    last_height = 0
    while True:
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return window.pageYOffset;")
        if new_height == last_height:
            break
        last_height = new_height
    time.sleep(1.5)

def collect_movie_links(driver):
    # Recull tots els enllaços de pel·lícules visibles 
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/review/']")
    links = []
    for a in anchors:
        try:
            href = a.get_attribute("href")
            if href and "/review/" in href:
                links.append(href)
        except:
            pass
    return links

def click_next_button(driver):
    # Clica el botó "Next"
    try:
        btn = driver.find_element(By.XPATH, "//button[normalize-space()='Next']")
        btn.click()
        time.sleep(3)
    except:
        print("No s'ha pogut clicar el botó Next")

def get_info_value(driver, label):
    """
    Devuelve el texto de la celda a la derecha de la fila cuyo primer <td> es 'label:'.
    Ejemplo: label='Year Released' -> busca "Year Released:" y lee la siguiente celda.
    """
    try:
        xpath = f"//td[normalize-space()='{label}:']/following-sibling::td[1]"
        return driver.find_element(By.XPATH, xpath).text.strip()
    except:
        return ""

def get_title(driver):
    # Extreu el títol per id
    try:
        return driver.find_element(By.ID, "reviewPage-title").text.strip()
    except:
        try:
            return driver.find_element(By.TAG_NAME, "h2").text.strip()
        except:
            return ""

def get_section_text(driver, header_text):
    try:
        h3 = driver.find_element(By.XPATH, f"//h3[normalize-space()='{header_text}']")
        try:
            p = h3.find_element(By.XPATH, "following-sibling::p[1]")
            return p.text.strip()
        except:
            div = h3.find_element(By.XPATH, "following-sibling::div")
            p_list = div.find_elements(By.TAG_NAME, "p")
            p_all = ""
            for i, p in enumerate(p_list, 1):
                p_all += p.text.strip()
                if i < len(p_list):
                    p_all +=", "

            return p_all
    except:
        return ""

def parse_movie_page(driver, url):
    # Obre una pàgina de pel·lícula i n'extreu les dades principals
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
    except:
        time.sleep(2)

    title = get_title(driver)

    # Extreu els camps de la taula de l'esquerra (per etiqueta)
    # Si no exiteix, retornarà ""
    year            = get_info_value(driver, "Year Released")
    decade          = get_info_value(driver, "Decade Released")
    runtime_minutes = get_info_value(driver, "Runtime")
    box_office      = get_info_value(driver, "Box Office")
    genre           = get_info_value(driver, "Genre")
    studio          = get_info_value(driver, "Studio/Company")
    country         = get_info_value(driver, "Country")


    # Extreu seccions textuals
    director = get_section_text(driver, "Director")
    starring = get_section_text(driver, "Starring")
    awards   = get_section_text(driver, "Awards")

    return {
        "url": url,
        "title": title,
        "year": year,
        "decade": decade,
        "runtime_minutes": runtime_minutes,
        "box_office": box_office,
        "genre": genre,
        "studio": studio,
        "country": country,
        "director": director,
        "starring": starring,
        "awards": awards
    }

def main():
    # Inicialitza el navegador i accedeix a la web
    driver = setup_driver()
    driver.get("https://www.movierankings.net/review/122")


    # 2a fase: visitar cada fitxa i extreure dades
    rows = []
    row = parse_movie_page(driver, "https://www.movierankings.net/review/122")
    rows.append(row)
    time.sleep(1.2)

    driver.quit()

    for row in rows: print(row)

if __name__ == "__main__":
    main()

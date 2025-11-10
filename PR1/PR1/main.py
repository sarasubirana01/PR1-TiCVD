import os, time
import pandas as pd
from multiprocessing import Process, JoinableQueue, Queue


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Paràmetres de configuració
START_URL = "https://www.movierankings.net"  # Pàgina inicial
MAX_PAGES = 58                               # Nombre màxim de pàgines a recórrer
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
        time.sleep(0.5)
        btn.click()
        print("Entrant a la vista de 'Full Rankings'")
        time.sleep(0.5)
    except Exception as e:
        print("No s'ha pogut fer clic al botó id=6:", e)

def scroll_full_page(driver, pause_time=0.2):
    # Fa scroll fins que ja no es carreguen més pel·lícules
    last_height = 0
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "movie")))
    while True:
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return window.pageYOffset;")
        if new_height == last_height:
            break
        last_height = new_height
    time.sleep(0.2)

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
        time.sleep(0.2)
    except:
        print("No s'ha pogut clicar el botó Next")

def get_info_value(driver, label):
    """
    Devuelve el texto de la celda a la derecha de la fila cuyo primer <td> es 'label:'.
    Ejemplo: label='Year Released' -> busca "Year Released:" y lee la siguiente celda.
    """
    try:
        xpath = f"//td[normalize-space()='{label}:']/following-sibling::td[1]"
        if label in ["Genre", "Sub-Genre", "Studio/Company"]:
            cell = driver.find_element(By.XPATH, xpath)
            details = cell.find_elements(By.TAG_NAME, "button")
            text = ""
            for i, d in enumerate(details, start=1):
                text += d.text.strip()
                if i < len(details):
                    text += ", "
            return text
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

def get_score(driver):
    try:
        scores = driver.find_elements(By.CLASS_NAME, "score-row")
        average_score = scores[2].find_elements(By.TAG_NAME, "h1")[1].text.strip()
        return average_score
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
            for p in (p_list):
                ul = p.find_element(By.XPATH, "following-sibling::ul")
                ul_list = ul.find_elements(By.TAG_NAME, "li")
                for u in ul_list:
                    p_all += p.text.strip()+" - "+u.text.strip()+", "
            return p_all[:-2]
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
    score = get_score(driver)

    # Extreu els camps de la taula de l'esquerra (per etiqueta)
    # Si no exiteix, retornarà ""
    year            = get_info_value(driver, "Year Released")
    decade          = get_info_value(driver, "Decade Released")
    runtime_minutes = get_info_value(driver, "Runtime")
    box_office      = get_info_value(driver, "Box Office")
    genre           = get_info_value(driver, "Genre")
    subgenre        = get_info_value(driver, "Sub-Genre")
    studio          = get_info_value(driver, "Studio/Company")
    country         = get_info_value(driver, "Country")


    # Extreu seccions textuals
    director = get_section_text(driver, "Director")
    starring = get_section_text(driver, "Starring")
    awards   = get_section_text(driver, "Awards")

    return {
        "url": url,
        "title": title,
        "score": score,
        "year": year,
        "decade": decade,
        "runtime_minutes": runtime_minutes,
        "box_office": box_office,
        "genre": genre,
        "subgenre": subgenre,
        "studio": studio,
        "country": country,
        "director": director,
        "starring": starring,
        "awards": awards
    }

def scan_movies(links_q, rows_q):
    driver = setup_driver()
    url = links_q.get()
    while url:
        try:
            print(f"Processant pel·lícula {url}")
            row = parse_movie_page(driver, url)
            rows_q.put(row)
            links_q.task_done()
            time.sleep(0.1)
            url = links_q.get()
        except Exception as e:
            print("Error amb", url, "->", e)
            continue
    driver.quit()
    links_q.task_done()

def fase_2_multiproces(urls_to_scan, num_process, rows):
    rows_q = Queue()
    links_q = JoinableQueue()

    for url in urls_to_scan:
        links_q.put(url)

    for _ in range(num_process):
        links_q.put(None)

    for i in range(num_process):
        process = Process(target=scan_movies, args=(links_q, rows_q))
        process.start()

    links_q.join()
    while not rows_q.empty():
        rows.append(rows_q.get())

def main():
    # Inicialitza el navegador i accedeix a la web
    start_time = time.time()

    # 1a fase: accedir a la vista del full ranking i recórrer les pàgines per obtenir totes les url de pel·lícules
    driver = setup_driver()
    driver.get(START_URL)
    go_to_full_rankings(driver)
    all_links = []
    for page in range(1, MAX_PAGES + 1):
        print(f"\nPàgina {page}")
        scroll_full_page(driver)
        links = collect_movie_links(driver)
        print(f"Pàgina {page}: pel·lícules trobades -> {len(links)}")
        all_links.extend(links)

        if page == MAX_PAGES:
            time.sleep(1)
            break
        click_next_button(driver)
    driver.quit()
    fase1 = time.time()

    # 2a fase: visitar cada fitxa i extreure dades, multiprocés
    rows = []
    fase_2_multiproces(all_links, 4, rows)

    fase2 = time.time()
    print(f"Fase 1 completada en {round(fase1 - start_time)} segons")
    print(f"Fase 2 completada en {round(fase2 - fase1)} segons")
    print(f"Pel·lícules processades -> {len(rows)}")
    print(f"Exportem el resultat al fitxer {OUT_PATH}")
    # Guardar resultats en CSV
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df = pd.DataFrame(rows, columns=[
        "url", "title", "score", "year", "decade", "runtime_minutes", "box_office",
        "genre", "subgenre", "studio", "country", "director", "starring", "awards"
    ])
    df.to_csv(OUT_PATH, index=False, encoding="utf-8")
    try:
        if os.path.getmtime(OUT_PATH) > fase2:
            print(f"Fitxer actualitzat correctament")
    except:
        print(f"El fitxer no s'ha pogut actualitzar")

    print(f"Temps total: {round((time.time() - start_time)/60)} minuts")


if __name__ == "__main__":
    main()
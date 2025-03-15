import requests
import pandas as pd
import json
from tqdm import tqdm
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

options = Options()
options.add_argument("--headless")  # Запускаем без GUI
options.add_argument("--no-sandbox")  # Запускаем без sandbox (для работы в контейнерах)
options.add_argument("--disable-dev-shm-usage")  # Убираем ограничение памяти
options.add_argument("--disable-gpu")  # Отключаем GPU (не нужно на сервере)
options.add_argument("--remote-debugging-port=9222")  # Полезно для отладки

# Запускаем драйвер
driver = uc.Chrome(options=options)
driver.get('https://www.wildberries.ru/catalog/191496947/detail.aspx')
time.sleep(10)
with open('to_parse.json', 'r', encoding='utf-8') as f:
    categories = json.load(f)
# https://catalog.wb.ru/catalog/bl_shirts/v2/catalog?ab_testing=false&appType=1&cat=8126&curr=rub&dest=123586167&lang=ru&page=1&sort=popular&spp=30
all_products = []
variants = ['stationery3', 'appliances2', '']
for cat in tqdm(categories):
    i = cat['cat_name']
    try:
        ids = []
        for page in range(1, 100):
            for var in variants:
                try:
                    products = requests.get(
                        f'https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=123586167&lang=ru&page=1&query={i}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false',
                        timeout=2).json()[
                        'data']['products']
                    if len(products) > 0:
                        break
                except:
                    pass
            ids += [product['id'] for product in products]
            if len(ids) > 100-cat['count']:
                break
        for h in range(min((len(ids), 100-cat['count']))):
            try:
                driver.get(f'https://www.wildberries.ru/catalog/{ids[h]}/detail.aspx')
                print('a')
                wait = WebDriverWait(driver, 10)
                element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'product-page__title')))
                print('b')
                prod_name = driver.find_element(By.CLASS_NAME, 'product-page__title').text
                element = driver.find_element(By.CLASS_NAME, 'product-page__btn-detail')
                element.click()
                wait = WebDriverWait(driver, 10)
                element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'product-params__cell-decor')))
                info_names = driver.find_elements(By.CLASS_NAME, 'product-params__cell-decor')
                info_data = driver.find_elements(By.CLASS_NAME, 'product-params__cell')
                price = driver.find_element(By.CLASS_NAME, 'price-block__final-price').text
                info = {}
                for s in range(0, len(info_names), 2):
                    info[info_data[s].text] = info_data[s+1].text
                all_products.append({'id':h, 'name': prod_name, 'attributes': info, 'category': i})

            except Exception as e:
                print(e)
        with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=4)

    except Exception as e:
        print(e)


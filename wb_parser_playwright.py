import requests
import pandas as pd
import json
from tqdm import tqdm
from playwright.sync_api import sync_playwright
import time

with open('to_parse.json', 'r', encoding='utf-8') as f:
    categories = json.load(f)

all_products = []
variants = ['stationery3', 'appliances2', '']

with sync_playwright() as p:
    # Запускаем браузер в headless-режиме (для сервера)
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    )
    page = context.new_page()

    for cat in tqdm(categories):
        i = cat['cat_name']
        try:
            ids = []
            for page_num in range(1, 100):
                for var in variants:
                    try:
                        response = requests.get(
                            f'https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=123586167&lang=ru&page={page_num}&query={i}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false',
                            timeout=5
                        )
                        products = response.json()['data']['products']
                        if len(products) > 0:
                            ids += [product['id'] for product in products]
                            break
                    except:
                        continue

                if len(ids) >= 100 - cat['count']:
                    break
            for h in range(min((len(ids), 100 - cat['count']))):
                try:
                    page.goto(f'https://www.wildberries.ru/catalog/{ids[h]}/detail.aspx', timeout=60000)
                    # Ждем загрузки заголовка
                    page.wait_for_selector('.product-page__title', timeout=30000)
                    prod_name = page.locator('.product-page__title').first.inner_text()
                    # Кликаем на кнопку "Подробнее"
                    page.locator('.product-page__btn-detail').first.click()

                    # Ждем загрузки параметров
                    page.wait_for_selector('.product-params__cell-decor', timeout=30000)

                    # Собираем данные
                    info_names = page.locator('.product-params__cell-decor').all_text_contents()
                    info_data = page.locator('.product-params__cell').all_text_contents()
                    price = page.locator('.price-block__final-price').first.inner_text()

                    info = {}
                    for s in range(0, len(info_names)):
                        info[info_names[s]] = info_data[s]

                    all_products.append({
                        'id': h,
                        'name': prod_name,
                        'attributes': info,
                        'category': i,
                        'price': price
                    })

                except Exception as e:
                    print(f"Error processing product {ids[h]}: {str(e)}")
                    continue

            # Сохраняем промежуточные результаты
            with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
                json.dump(all_products, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"Error processing category {i}: {str(e)}")
            continue

    browser.close()

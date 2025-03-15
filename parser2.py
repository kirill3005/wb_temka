import json
import requests
import random
import time
from playwright.sync_api import sync_playwright
from tqdm import tqdm

def fetch_product_ids(cat, variants):
    """
    Получает список ID товаров для категории.
    """
    cat_name = cat['cat_name']
    ids = []
    for page_num in range(1, 100):
        for var in variants:
            try:
                response = requests.get(
                    f'https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=123586167&lang=ru&page={page_num}&query={cat_name}&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false',
                    timeout=5
                )
                products = response.json().get('data', {}).get('products', [])
                if products:
                    ids.extend([product['id'] for product in products])
                    break
            except:
                continue
        if len(ids) >= 100 - cat['count']:
            break
    return cat_name, ids[:(100 - cat['count'])]

def process_product(page, product_id, category):
    """
    Открывает страницу товара, извлекает данные и возвращает словарь.
    """
    url = f'https://www.wildberries.ru/catalog/{product_id}/detail.aspx'
    
    for attempt in range(3):  # До 3 попыток загрузки
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            page.wait_for_selector('.product-page__title', timeout=15000)
            prod_name = page.locator('.product-page__title').first.inner_text()
            page.locator('.product-page__btn-detail').first.click()
            page.wait_for_selector('.product-params__cell-decor', timeout=15000)
            info_names = page.locator('.product-params__cell-decor').all_text_contents()
            info_data = page.locator('.product-params__cell').all_text_contents()
            price = page.locator('.price-block__final-price').first.inner_text()

            info = {name: data for name, data in zip(info_names, info_data)}

            return {
                'id': product_id,
                'name': prod_name,
                'attributes': info,
                'category': category,
                'price': price
            }
        except Exception as e:
            print(f"Error processing product {product_id} (attempt {attempt+1}): {str(e)}")
            time.sleep(random.uniform(1, 3))  # Делаем паузу перед повторной попыткой
    return None

def main():
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)

    all_products = []
    variants = ['stationery3', 'appliances2', '']

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        )
        page = context.new_page()  # Одна вкладка на все товары (ускоряет работу)

        for cat in tqdm(categories):
            category_name, product_ids = fetch_product_ids(cat, variants)

            for product_id in tqdm(product_ids):
                product = process_product(page, product_id, category_name)
                if product:
                    all_products.append(product)
                
                time.sleep(random.uniform(2, 5))  # Пауза для обхода антибот-защиты

            # Сохраняем промежуточные результаты
            with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
                json.dump(all_products, f, ensure_ascii=False, indent=4)

        browser.close()

if __name__ == "__main__":
    main()

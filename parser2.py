import requests
import json
from tqdm import tqdm
from playwright.sync_api import sync_playwright

with open('to_parse.json', 'r', encoding='utf-8') as f:
    categories = json.load(f)

all_products = []
variants = ['stationery3', 'appliances2', '']

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    )

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
                        if products:
                            ids += [product['id'] for product in products]
                            break
                    except:
                        continue

                if len(ids) >= 100 - cat['count']:
                    break

            # Используем несколько страниц одновременно
            for h in tqdm(range(min(len(ids), 100 - cat['count']))):
                try:
                    product_page = context.new_page()
                    product_page.goto(f'https://www.wildberries.ru/catalog/{ids[h]}/detail.aspx', wait_until="networkidle", timeout=10000)

                    # Получаем название товара
                    prod_name = product_page.locator('.product-page__title').first.inner_text()

                    # Проверяем, есть ли кнопка "Подробнее"
                    btn = product_page.locator('.product-page__btn-detail').first
                    if btn.is_visible():
                        btn.click()

                    # Получаем параметры товара
                    info_names = product_page.locator('.product-params__cell-decor').all_text_contents()
                    info_data = product_page.locator('.product-params__cell').all_text_contents()
                    price = product_page.locator('.price-block__final-price').first.inner_text()

                    info = {info_names[s]: info_data[s] for s in range(len(info_names))}

                    all_products.append({
                        'id': ids[h],
                        'name': prod_name,
                        'attributes': info,
                        'category': i,
                        'price': price
                    })

                    product_page.close()  # Закрываем страницу

                except Exception as e:
                    print(f"Ошибка при обработке товара {ids[h]}: {str(e)}")
                    continue

            # Сохраняем промежуточные результаты
            with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
                json.dump(all_products, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"Ошибка при обработке категории {i}: {str(e)}")
            continue

    browser.close()

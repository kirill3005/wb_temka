import json
import requests
import time
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def main():
    # Запускаем Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Можно перевести в True для работы в headless-режиме
        page = browser.new_page()

        # Загружаем категории
        with open('to_generate_syntetic.json', 'r', encoding='utf-8') as f:
            categories = json.load(f)

        all_products = []
        variants = ['stationery3', 'appliances2', '']  # вариант, сохраняем как в оригинале

        # Проходим по всем категориям
        for cat in tqdm(categories):
            cat_name = cat['cat_name']
            try:
                ids = []
                # Перебираем страницы (до 100) для получения id товаров
                for page_num in range(1, 100):
                    products = []
                    # Пробуем с разными вариантами (на всякий случай)
                    for var in variants:
                        try:
                            # Обратите внимание: параметр var в данном запросе не используется, 
                            # но оставлен для сохранения логики оригинала.
                            url = (f'https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false'
                                   f'&appType=1&curr=rub&dest=123586167&lang=ru&page={page_num}'
                                   f'&query={cat_name}&resultset=catalog&sort=popular&spp=30'
                                   f'&suppressSpellcheck=false')
                            response = requests.get(url, timeout=2)
                            data = response.json()
                            products = data['data']['products']
                            if products:
                                break  # если получили товары, выходим из цикла вариантов
                        except Exception:
                            continue
                    # Добавляем id товаров из полученного списка
                    ids.extend([product['id'] for product in products])
                    # Если получено нужное количество товаров, завершаем цикл по страницам
                    if len(ids) > 1000 - cat.get('count', 0):
                        break

                # Ограничиваем количество товаров для категории
                limit = min(len(ids), 1000 - cat.get('count', 0))
                for h in range(limit):
                    try:
                        product_id = ids[h]
                        product_url = f'https://www.wildberries.ru/catalog/{product_id}/detail.aspx'
                        page.goto(product_url)
                        
                        # Ожидаем появления названия товара
                        page.wait_for_selector('.product-page__title', timeout=10000)
                        prod_name = page.locator('.product-page__title').inner_text()
                        
                        # Нажимаем на кнопку для раскрытия деталей (если такая имеется)
                        page.wait_for_selector('.product-page__btn-detail', timeout=10000)
                        page.click('.product-page__btn-detail')
                        
                        # Ожидаем загрузки блока с характеристиками
                        page.wait_for_selector('.product-params__cell-decor', timeout=10000)
                        
                        # Получаем списки параметров и значений
                        # Здесь используем все найденные элементы с классом product-params__cell
                        info_data = page.locator('.product-params__cell').all_inner_texts()
                        price = page.locator('.price-block__final-price').inner_text()
                        
                        info = {}
                        # Предполагается, что список info_data содержит пары "ключ-значение"
                        for s in range(0, len(info_data) - 1, 2):
                            info[info_data[s]] = info_data[s+1]
                        
                        all_products.append({
                            'id': product_id,
                            'name': prod_name,
                            'attributes': info,
                            'price': price,
                            'category': cat_name
                        })
                    except PlaywrightTimeoutError as te:
                        print(f"Timeout при обработке товара {product_id}: {te}")
                    except Exception as e:
                        print(f"Ошибка при обработке товара {product_id}: {e}")

                    # Короткая задержка между запросами (при необходимости)
                    time.sleep(1)
                
                # Сохраняем результаты после обработки каждой категории
                with open('ods_from_wb2.json', 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, ensure_ascii=False, indent=4)

            except Exception as e:
                print(f"Ошибка при обработке категории {cat_name}: {e}")

        browser.close()

if __name__ == '__main__':
    main()

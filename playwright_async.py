import asyncio
import json
import requests
from playwright.async_api import async_playwright

async def fetch_product_ids(cat, variants):
    """
    Функция для получения списка ID товаров по категории.
    """
    cat_name = cat['cat_name']
    ids = []
    # Ищем товары на нескольких страницах
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
                    break  # Выходим из цикла variants, переходим к следующей странице
            except Exception:
                continue
        # Ограничиваем количество ID по условию
        if len(ids) >= 100 - cat['count']:
            break
    return cat_name, ids[:(100 - cat['count'])]

async def process_product(page, product_id, category):
    """
    Функция для обработки одного продукта: переходит на страницу товара, извлекает данные и возвращает словарь.
    """
    try:
        await page.goto(f'https://www.wildberries.ru/catalog/{product_id}/detail.aspx', timeout=60000)
        await page.wait_for_selector('.product-page__title', timeout=30000)
        prod_name = await page.locator('.product-page__title').first.inner_text()
        await page.locator('.product-page__btn-detail').first.click()
        await page.wait_for_selector('.product-params__cell-decor', timeout=30000)
        info_names = await page.locator('.product-params__cell-decor').all_text_contents()
        info_data = await page.locator('.product-params__cell').all_text_contents()
        price = await page.locator('.price-block__final-price').first.inner_text()

        # Формируем словарь с атрибутами товара
        info = {name: data for name, data in zip(info_names, info_data)}

        product = {
            'id': product_id,
            'name': prod_name,
            'attributes': info,
            'category': category,
            'price': price
        }
        return product
    except Exception as e:
        print(f"Error processing product {product_id}: {str(e)}")
        return None

async def main():
    # Загружаем категории из файла
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)
    all_products = []
    variants = ['stationery3', 'appliances2', '']

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        )
        
        tasks = []
        # Для каждой категории получаем список ID товаров
        for cat in categories:
            category_name, product_ids = await fetch_product_ids(cat, variants)
            for product_id in product_ids:
                # Для каждого товара создаём новую страницу и добавляем задачу обработки в список задач
                page = await context.new_page()
                task = asyncio.create_task(process_product(page, product_id, category_name))
                tasks.append(task)
        
        # Выполняем все задачи параллельно
        results = await asyncio.gather(*tasks)
        all_products = [product for product in results if product is not None]

        await browser.close()
    
    # Сохраняем результаты в файл
    with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
        json.dump(all_products, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    asyncio.run(main())

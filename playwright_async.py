import asyncio
import json
import aiohttp
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

# Варианты (сохраняем логику оригинального кода, даже если они не подставляются в URL)
variants = ['stationery3', 'appliances2', '']

async def fetch_ids_for_page(category_name, page_num, session):
    """
    Асинхронно получает список id товаров для заданной категории и номера страницы.
    Перебирает варианты до успешного получения товаров.
    """
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
    ids = [product['id'] for product in products]
    return ids
    
async def process_product(category_name, product_id, context, semaphore):
    """
    Открывает страницу товара, собирает необходимые данные и возвращает словарь с результатом.
    Используется semaphore для ограничения количества одновременных страниц.
    """
    async with semaphore:
        page = await context.new_page()
        try:
            print('a')
            await page.goto(f'https://www.wildberries.ru/catalog/{product_id}/detail.aspx', timeout=60000)
            await page.wait_for_selector('.product-page__title', timeout=30000)
            prod_name = await page.locator('.product-page__title').first.inner_text()

            # Нажимаем кнопку "Подробнее"
            await page.locator('.product-page__btn-detail').first.click()
            await page.wait_for_selector('.product-params__cell-decor', timeout=30000)

            info_names = await page.locator('.product-params__cell-decor').all_text_contents()
            info_data = await page.locator('.product-params__cell').all_text_contents()
            price = await page.locator('.price-block__final-price').first.inner_text()

            info = {}
            for s in range(len(info_names)):
                info[info_names[s]] = info_data[s]

            product = {
                'id': product_id,
                'name': prod_name,
                'attributes': info,
                'category': category_name,
                'price': price
            }
            print('b')
            return product

        except Exception as e:
            print(f"Error processing product {product_id}: {e}")
            return None
        finally:
            await page.close()

async def process_category(category, context, session, semaphore):
    """
    Обрабатывает одну категорию:
    1. Собирает id товаров с нескольких страниц.
    2. Параллельно открывает страницы товаров и собирает их данные.
    """
    category_name = category['cat_name']
    required_count = 100 - category.get('count', 0)
    ids = []

    # Перебираем страницы для получения id товаров
    for page_num in range(1, 100):
        ids_chunk = await fetch_ids_for_page(category_name, page_num, session)
        if ids_chunk:
            ids.extend(ids_chunk)
        if len(ids) >= required_count:
            break

    product_limit = min(len(ids), required_count)
    tasks = [
        asyncio.create_task(process_product(category_name, ids[i], context, semaphore))
        for i in range(product_limit)
    ]
    results = await asyncio.gather(*tasks)
    # Возвращаем только успешно собранные товары (без None)
    return [prod for prod in results if prod is not None]

async def main():
    # Загружаем категории
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)

    all_products = []
    semaphore = asyncio.Semaphore(5)  # ограничение на одновременное число страниц (можно настроить)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Создаём контекст с нужным user-agent
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        )
        async with aiohttp.ClientSession() as session:
            # Параллельно обрабатываем все категории
            category_tasks = [
                asyncio.create_task(process_category(category, context, session, semaphore))
                for category in categories
            ]
            category_results = await asyncio.gather(*category_tasks)
            for res in category_results:
                all_products.extend(res)

        await browser.close()

    # Сохраняем итоговый результат
    with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
        json.dump(all_products, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    asyncio.run(main())

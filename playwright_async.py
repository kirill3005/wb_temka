import asyncio
import json
import aiohttp
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright

async def fetch_product_ids(session, category_name, page_num):
    url = f"https://search.wb.ru/exactmatch/ru/common/v9/search?page={page_num}&query={category_name}"
    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()
            return [product['id'] for product in data.get('data', {}).get('products', [])]
    except Exception as e:
        print(f"Error fetching IDs for {category_name}: {str(e)}")
        return []

async def parse_product(page, product_id, category_name):
    try:
        await page.goto(f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx", timeout=60000)
        
        # Ожидаем загрузки элементов
        await page.wait_for_selector('.product-page__title', timeout=30000)
        await page.wait_for_selector('.product-page__btn-detail', timeout=30000)
        
        # Кликаем на кнопку "Подробнее"
        await page.locator('.product-page__btn-detail').first.click()
        
        # Собираем данные
        prod_name = await page.locator('.product-page__title').first.inner_text()
        price = await page.locator('.price-block__final-price').first.inner_text()
        
        # Собираем характеристики
        info_names = await page.locator('.product-params__cell-decor').all_text_contents()
        info_data = await page.locator('.product-params__cell').all_text_contents()
        
        return {
            'id': product_id,
            'name': prod_name,
            'price': price,
            'attributes': dict(zip(info_names, info_data)),
            'category': category_name
        }
    except Exception as e:
        print(f"Error parsing {product_id}: {str(e)}")
        return None

async def worker(session, browser, queue, results, category_name, concurrency=5):
    context = await browser.new_context()
    semaphore = asyncio.Semaphore(concurrency)
    
    async def process_product(product_id):
        async with semaphore:
            page = await context.new_page()
            try:
                result = await parse_product(page, product_id, category_name)
                if result:
                    results.append(result)
            finally:
                await page.close()
    
    tasks = []
    while not queue.empty():
        product_id = await queue.get()
        tasks.append(process_product(product_id))
        queue.task_done()
    
    await asyncio.gather(*tasks)
    await context.close()

async def main():
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)
    
    all_results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        async with aiohttp.ClientSession() as session:
            for category in categories:
                cat_name = category['cat_name']
                max_products = 100 - category['count']
                
                # Собираем ID товаров
                product_ids = []
                for page_num in range(1, 100):
                    ids = await fetch_product_ids(session, cat_name, page_num)
                    product_ids.extend(ids)
                    print(len(product_ids))
                    if len(product_ids) >= max_products:
                        break
                
                product_ids = list(set(product_ids))[:max_products]
                print(f"Found {len(product_ids)} products for {cat_name}")
                
                # Создаем очередь задач
                queue = asyncio.Queue()
                for pid in product_ids:
                    await queue.put(pid)
                
                # Запускаем воркеры
                await worker(session, browser, queue, all_results, cat_name, concurrency=10)
                
                # Сохраняем промежуточные результаты
                with open('ods_from_wb.json', 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=4)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import aiohttp
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

# Конфигурация
MAX_CONCURRENT_TASKS = 15  # Оптимально для средних серверов
REQUEST_TIMEOUT = 15
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
]

async def fetch_product_ids(session, category_name, page_num):
    url = f"https://search.wb.ru/exactmatch/ru/common/v9/search?appType=1&curr=rub&dest=-1257786&page={page_num}&query={category_name}&resultset=catalog&sort=popular&spp=30"
    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return [product['id'] for product in data.get('data', {}).get('products', [])]
    except Exception as e:
        print(f"Error fetching IDs for {category_name}: {str(e)}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def parse_product(page, product_id, category_name):
    try:
        await page.goto(f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx", 
                       timeout=60000, wait_until="domcontentloaded")
        
        # Умное ожидание элементов
        await page.wait_for_selector('.product-page__title', state="attached", timeout=10000)
        await page.evaluate("window.scrollBy(0, 200)")  # Имитация скролла
        
        # Параллельный сбор данных
        prod_name, price, details_btn = await asyncio.gather(
            page.locator('.product-page__title').first.inner_text(),
            page.locator('.price-block__final-price').first.inner_text(),
            page.locator('.product-page__btn-detail').first.click(),
        )

        # Сбор характеристик
        info_names = await page.locator('.product-params__cell-decor').all_text_contents()
        info_data = await page.locator('.product-params__cell').all_text_contents()
        
        return {
            'id': product_id,
            'name': prod_name.strip(),
            'price': price.replace('₽', '').strip(),
            'attributes': dict(zip(info_names, info_data)),
            'category': category_name
        }
    except Exception as e:
        print(f"Error parsing {product_id}: {str(e)}")
        raise

async def worker(browser, queue, results, pbar):
    context = await browser.new_context()
    page = await context.new_page()
    
    while not queue.empty():
        product_id, category = await queue.get()
        try:
            result = await parse_product(page, product_id, category)
            results.append(result)
            pbar.update(1)
        except:
            await queue.put((product_id, category))  Возврат в очередь
        finally:
            await page.close()
            page = await context.new_page()  # Новая страница для след. товара
    
    await context.close()

async def main():
    with open('to_parse.json', 'r', encoding='utf-8') as f:
        categories = json.load(f)

    all_results = []
    total_products = sum(min(100 - cat['count'], 100) for cat in categories)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
            proxy={"server": "per-context"}
        )
        
        async with aiohttp.ClientSession() as session:
            with tqdm_asyncio(total=total_products, desc="Processing") as pbar:
                for category in categories:
                    cat_name = category['cat_name']
                    max_needed = 100 - category['count']
                    
                    # Параллельный сбор ID
                    tasks = [fetch_product_ids(session, cat_name, p) for p in range(1, 10)]
                    pages_ids = await asyncio.gather(*tasks)
                    product_ids = list(set([id for sublist in pages_ids for id in sublist]))[:max_needed]
                    
                    # Создаем очередь задач
                    queue = asyncio.Queue()
                    for pid in product_ids:
                        await queue.put((pid, cat_name))
                    
                    # Запуск воркеров
                    workers = [worker(browser, queue, all_results, pbar) 
                              for _ in range(MAX_CONCURRENT_TASKS)]
                    await asyncio.gather(*workers)
                    
                    # Сохранение чанка
                    with open('partial_results.json', 'a') as f:
                        json.dump(all_results[-len(product_ids):], f, ensure_ascii=False)
                        f.write('\n')
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

import datetime
import requests
import pandas as pd
from retry import retry


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.wildberries.ru",
    'Content-Type': 'application/json; charset=utf-8',
    'Transfer-Encoding': 'chunked',
    "Connection": "keep-alive",
    'Vary': 'Accept-Encoding',
    'Content-Encoding': 'gzip',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site"
}
CATALOG_URL = 'https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v2.json'


def get_catalogs_wb() -> dict:
    """получаем полный каталог Wildberries"""
    return requests.get(CATALOG_URL, headers=HEADERS).json()


def get_data_category(catalogs_wb: dict) -> list:
    """сбор данных категорий из каталога Wildberries"""
    catalog_data = []
    if isinstance(catalogs_wb, dict) and 'childs' not in catalogs_wb:
        catalog_data.append({
            'name': f"{catalogs_wb['name']}",
            'shard': catalogs_wb.get('shard', None),
            'url': catalogs_wb['url'],
            'query': catalogs_wb.get('query', None)
        })
    elif isinstance(catalogs_wb, dict):
        catalog_data.extend(get_data_category(catalogs_wb['childs']))
    else:
        for child in catalogs_wb:
            catalog_data.extend(get_data_category(child))
    return catalog_data


def search_category_in_catalog(url: str, catalog_list: list) -> dict:
    """проверка пользовательской ссылки на наличии в каталоге"""
    for catalog in catalog_list:
        if catalog['url'] == url.split('https://www.wildberries.ru')[-1]:
            print(f'найдено совпадение: {catalog["name"]}')
            return catalog


def get_data_from_json(json_file: dict) -> list:
    """извлекаем из json данные"""
    data_list = []
    for data in json_file['data']['products']:
        data_list.append({
            'id': data.get('id'),
            'Наименование': data.get('name'),
            'Цена': int(data.get("priceU") / 100),
            'Цена со скидкой': int(data.get('salePriceU') / 100),
            'Скидка': data.get('sale'),
            'Бренд': data.get('brand'),
            'Рейтинг': data.get('rating'),
            'Продавец': data.get('supplier'),
            'Рейтинг продавца': data.get('supplierRating'),
            'Кол-во отзывов': data.get('feedbacks'),
            'Рейтинг отзывов': data.get('reviewRating'),
            'Промо текст карточки': data.get('promoTextCard'),
            'Промо текст категории': data.get('promoTextCat'),
            'Ссылка': f'https://www.wildberries.ru/catalog/{data.get("id")}/detail.aspx?targetUrl=BP'
        })
    return data_list


@retry(Exception, tries=-1, delay=0)
def scrap_page(page: int, shard: str, query: str, low_price: int, top_price: int, discount: int = None) -> dict:
    """Сбор данных со страниц"""
    url = f'https://catalog.wb.ru/catalog/{shard}/catalog?appType=1&curr=rub' \
          f'&dest=-1257786' \
          f'&locale=ru' \
          f'&page={page}' \
          f'&priceU={low_price * 100};{top_price * 100}' \
          f'&sort=popular&spp=0' \
          f'&{query}' \
          f'&discount={discount}'

    r = requests.get(url, headers=HEADERS)
    print(f'[+] Страница {page}')
    return r.json()


def save_excel(data: list, filename: str):
    """сохранение результата в excel файл"""
    df = pd.DataFrame(data)
    writer = pd.ExcelWriter(f'{filename}.xlsx')
    df.to_excel(writer, sheet_name='data', index=False)
    # указываем размеры каждого столбца в итоговом файле
    writer.sheets['data'].set_column(0, 1, width=10)
    writer.sheets['data'].set_column(1, 2, width=34)
    writer.sheets['data'].set_column(2, 3, width=8)
    writer.sheets['data'].set_column(3, 4, width=9)
    writer.sheets['data'].set_column(4, 5, width=4)
    writer.sheets['data'].set_column(5, 6, width=10)
    writer.sheets['data'].set_column(6, 7, width=5)
    writer.sheets['data'].set_column(7, 8, width=25)
    writer.sheets['data'].set_column(8, 9, width=10)
    writer.sheets['data'].set_column(9, 10, width=11)
    writer.sheets['data'].set_column(10, 11, width=13)
    writer.sheets['data'].set_column(11, 12, width=19)
    writer.sheets['data'].set_column(12, 13, width=19)
    writer.sheets['data'].set_column(13, 14, width=67)
    writer.close()
    print(f'Все сохранено в {filename}.xlsx\n')


def parser(url: str, low_price: int = 1, top_price: int = 1000000, discount: int = 0):
    """основная функция"""
    # получаем данные по заданному каталогу
    catalog_data = get_data_category(get_catalogs_wb())
    try:
        # поиск введенной категории в общем каталоге
        category = search_category_in_catalog(url=url, catalog_list=catalog_data)
        data_list = []
        for page in range(1, 51):  # вб отдает 50 страниц товара
            data = scrap_page(
                page=page,
                shard=category['shard'],
                query=category['query'],
                low_price=low_price,
                top_price=top_price,
                discount=discount)
            if len(get_data_from_json(data)) > 0:
                data_list.extend(get_data_from_json(data))
            else:
                break
        print(f'Сбор данных завершен. Собрано: {len(data_list)} товаров.')
        # сохранение найденных данных
        save_excel(data_list, f'{category["name"]}_from_{low_price}_to_{top_price}')
        print(f'Ссылка для проверки: {url}?priceU={low_price * 100};{top_price * 100}&discount={discount}')
    except TypeError:
        print('Ошибка! Возможно не верно указан раздел. Удалите все доп фильтры с ссылки')
    except PermissionError:
        print('Ошибка! Вы забыли закрыть созданный ранее excel файл. Закройте и повторите попытку')


if __name__ == '__main__':
    url = 'https://www.wildberries.ru/catalog/dlya-doma/mebel/kronshteiny'  # сюда вставляем вашу ссылку на категорию
    low_price = 100  # нижний порог цены
    top_price = 1000000  # верхний порог цены
    discount = 10  # скидка в %
    start = datetime.datetime.now()  # запишем время старта

    parser(url=url, low_price=low_price, top_price=top_price, discount=discount)

    end = datetime.datetime.now()  # запишем время завершения кода
    total = end - start  # расчитаем время затраченное на выполнение кода
    print("Затраченное время:" + str(total))

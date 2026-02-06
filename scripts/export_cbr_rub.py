#!/usr/bin/env python3
"""
Загрузка курсов валют ЦБ РФ и экспорт в JSON формат.

Скачивает данные с https://cbr.ru/scripts/XML_daily.asp за указанный период
и сохраняет их в data/export/cbr_of_rub.json

Использование:
    # Ручной режим - указать период:
    python scripts/export_cbr_rub.py --start-date 2021-07-01 --end-date 2026-01-29
    
    # Автоматический режим - синхронизация с kolmo_history.json:
    python scripts/export_cbr_rub.py --sync
    
    # Обновление до сегодня:
    python scripts/export_cbr_rub.py --update
"""

import argparse
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Пути к файлам
DATA_EXPORT_DIR = Path(__file__).parent.parent / "data" / "export"
CBR_JSON_FILE = DATA_EXPORT_DIR / "cbr_of_rub.json"
KOLMO_HISTORY_FILE = DATA_EXPORT_DIR / "kolmo_history.json"

# URL ЦБ РФ
CBR_URL = "https://cbr.ru/scripts/XML_daily.asp"

# Настройки retry
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 1.0  # 1s, 2s, 4s, 8s, 16s


def create_session_with_retries() -> requests.Session:
    """Создаёт сессию с автоматическими повторами при сетевых ошибках."""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


def fetch_cbr_daily(target_date: date, session: requests.Session | None = None) -> dict | None:
    """
    Загружает курсы валют с ЦБ РФ за указанную дату.
    
    Args:
        target_date: Дата для загрузки курсов
        session: HTTP сессия с retry (опционально)
        
    Returns:
        Словарь с курсами валют или None при ошибке
    """
    date_param = target_date.strftime("%d/%m/%Y")
    url = f"{CBR_URL}?date_req={date_param}"
    
    # Используем переданную сессию или создаём новую с retry
    http_client = session or create_session_with_retries()
    
    # Дополнительные попытки при ConnectionResetError
    max_connection_retries = 3
    
    for attempt in range(max_connection_retries):
        try:
            response = http_client.get(url, timeout=60)
            response.raise_for_status()
            
            # Парсим XML
            root = ET.fromstring(response.content)
            
            # Создаём словарь для данной даты
            daily_data = {
                "date": target_date.strftime("%Y-%m-%d")
            }
            
            # Извлекаем все валюты
            valutes = root.findall('Valute')
            
            if not valutes:
                logger.warning(f"Нет данных за {date_param} (возможно выходной)")
                return None
            
            for valute in valutes:
                char_code = valute.find('CharCode').text
                value_raw = valute.find('Value').text
                
                # ЦБ возвращает числа с запятой, меняем на точку
                value_cleaned = value_raw.replace(',', '.')
                
                daily_data[char_code] = value_cleaned
            
            return daily_data
            
        except (ConnectionResetError, requests.exceptions.ConnectionError) as e:
            if attempt < max_connection_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"Соединение разорвано за {date_param}, попытка {attempt + 1}/{max_connection_retries}. Ждём {wait_time}с...")
                time.sleep(wait_time)
            else:
                logger.error(f"Сетевая ошибка за {date_param} после {max_connection_retries} попыток: {e}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Сетевая ошибка за {date_param}: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML за {date_param}: {e}")
            return None
    
    return None


def fetch_cbr_period(start_date: date, end_date: date) -> list[dict]:
    """
    Загружает курсы валют ЦБ РФ за период.
    
    Args:
        start_date: Начальная дата
        end_date: Конечная дата
        
    Returns:
        Список словарей с курсами валют
    """
    results = []
    failed_dates = []
    delta = end_date - start_date
    total_days = delta.days + 1
    
    logger.info(f"Загрузка данных за период: {start_date} — {end_date} ({total_days} дней)")
    
    # Создаём сессию с retry для всего периода
    session = create_session_with_retries()
    
    for i in range(total_days):
        current_date = start_date + timedelta(days=i)
        
        daily_data = fetch_cbr_daily(current_date, session)
        
        if daily_data:
            results.append(daily_data)
            logger.info(f"Загружено: {current_date.strftime('%Y-%m-%d')}")
        else:
            failed_dates.append(current_date)
        
        # Пауза для вежливости к серверу
        if i < total_days - 1:
            time.sleep(0.2)
    
    # Повторная попытка для неудачных дат
    if failed_dates:
        logger.info(f"Повторная попытка для {len(failed_dates)} дат...")
        time.sleep(2)
        
        for failed_date in failed_dates[:]:
            daily_data = fetch_cbr_daily(failed_date, session)
            if daily_data:
                results.append(daily_data)
                failed_dates.remove(failed_date)
                logger.info(f"✅ Успешно загружено при повторе: {failed_date.strftime('%Y-%m-%d')}")
            time.sleep(0.5)
    
    if failed_dates:
        logger.warning(f"⚠️ Не удалось загрузить {len(failed_dates)} дат: {[d.strftime('%Y-%m-%d') for d in failed_dates]}")
    
    return results


def load_existing_cbr_data() -> list[dict]:
    """Загружает существующие данные CBR из JSON файла."""
    if CBR_JSON_FILE.exists():
        try:
            with open(CBR_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Загружено {len(data)} записей из {CBR_JSON_FILE.name}")
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Ошибка чтения {CBR_JSON_FILE}: {e}")
    return []


def load_kolmo_history_dates() -> set[str]:
    """Загружает даты из kolmo_history.json."""
    if KOLMO_HISTORY_FILE.exists():
        try:
            with open(KOLMO_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                dates = {record["date"] for record in data if "date" in record}
                logger.info(f"Найдено {len(dates)} дат в {KOLMO_HISTORY_FILE.name}")
                return dates
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Ошибка чтения {KOLMO_HISTORY_FILE}: {e}")
    return set()


def save_cbr_data(data: list[dict]):
    """
    Сохраняет данные CBR в JSON файл.
    
    Args:
        data: Список словарей с курсами валют
    """
    # Создаём директорию если не существует
    DATA_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Сортируем по дате
    data_sorted = sorted(data, key=lambda x: x["date"])
    
    with open(CBR_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data_sorted, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Сохранено {len(data_sorted)} записей в {CBR_JSON_FILE}")


def merge_cbr_data(existing: list[dict], new_data: list[dict]) -> list[dict]:
    """
    Объединяет существующие и новые данные CBR.
    Новые данные перезаписывают существующие для той же даты.
    
    Args:
        existing: Существующие данные
        new_data: Новые данные
        
    Returns:
        Объединённый список
    """
    # Создаём словарь по датам из существующих данных
    data_by_date = {record["date"]: record for record in existing}
    
    # Добавляем/обновляем новыми данными
    for record in new_data:
        data_by_date[record["date"]] = record
    
    return list(data_by_date.values())


def sync_with_kolmo_history():
    """
    Синхронизирует cbr_of_rub.json с датами из kolmo_history.json.
    Загружает недостающие даты.
    """
    kolmo_dates = load_kolmo_history_dates()
    
    if not kolmo_dates:
        logger.error("Нет дат в kolmo_history.json для синхронизации")
        return
    
    existing_data = load_existing_cbr_data()
    existing_dates = {record["date"] for record in existing_data}
    
    # Находим недостающие даты
    missing_dates = kolmo_dates - existing_dates
    
    if not missing_dates:
        logger.info("✅ Все даты из kolmo_history.json уже присутствуют в cbr_of_rub.json")
        return
    
    logger.info(f"Найдено {len(missing_dates)} недостающих дат")
    
    # Сортируем для последовательной загрузки
    missing_sorted = sorted(missing_dates)
    
    # Создаём сессию с retry
    session = create_session_with_retries()
    
    # Загружаем недостающие даты
    new_data = []
    failed_dates = []
    
    for i, date_str in enumerate(missing_sorted):
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        daily_data = fetch_cbr_daily(target_date, session)
        
        if daily_data:
            new_data.append(daily_data)
            logger.info(f"[{i+1}/{len(missing_sorted)}] Загружено: {date_str}")
        else:
            failed_dates.append(target_date)
        
        if i < len(missing_sorted) - 1:
            time.sleep(0.2)
    
    # Повторная попытка для неудачных дат
    if failed_dates:
        logger.info(f"Повторная попытка для {len(failed_dates)} дат...")
        time.sleep(3)
        
        for failed_date in failed_dates[:]:
            daily_data = fetch_cbr_daily(failed_date, session)
            if daily_data:
                new_data.append(daily_data)
                failed_dates.remove(failed_date)
                logger.info(f"✅ Успешно загружено при повторе: {failed_date.strftime('%Y-%m-%d')}")
            time.sleep(0.5)
    
    if failed_dates:
        logger.warning(f"⚠️ Не удалось загрузить {len(failed_dates)} дат: {[d.strftime('%Y-%m-%d') for d in failed_dates]}")
    
    # Объединяем и сохраняем
    merged_data = merge_cbr_data(existing_data, new_data)
    save_cbr_data(merged_data)
    
    logger.info(f"✅ Синхронизация завершена. Добавлено {len(new_data)} новых записей")


def update_to_today():
    """
    Обновляет cbr_of_rub.json до сегодняшней даты.
    Начинает с последней даты в файле или с начала kolmo_history.
    """
    existing_data = load_existing_cbr_data()
    
    if existing_data:
        # Находим последнюю дату
        last_date_str = max(record["date"] for record in existing_data)
        start_date = datetime.strptime(last_date_str, "%Y-%m-%d").date() + timedelta(days=1)
    else:
        # Если данных нет, пробуем взять первую дату из kolmo_history
        kolmo_dates = load_kolmo_history_dates()
        if kolmo_dates:
            start_date = datetime.strptime(min(kolmo_dates), "%Y-%m-%d").date()
        else:
            start_date = date(2021, 7, 1)  # Дефолтная начальная дата
    
    end_date = date.today()
    
    if start_date > end_date:
        logger.info("✅ Данные уже актуальны до сегодняшней даты")
        return
    
    logger.info(f"Обновление с {start_date} по {end_date}")
    
    new_data = fetch_cbr_period(start_date, end_date)
    
    if new_data:
        merged_data = merge_cbr_data(existing_data, new_data)
        save_cbr_data(merged_data)
        logger.info(f"✅ Добавлено {len(new_data)} новых записей")
    else:
        logger.warning("Нет новых данных для добавления")


def fix_missing_dates():
    """
    Находит и заполняет пропущенные даты в cbr_of_rub.json.
    Проверяет непрерывность дат и загружает недостающие.
    """
    existing_data = load_existing_cbr_data()
    
    if not existing_data:
        logger.error("Файл cbr_of_rub.json пуст или не существует")
        return
    
    # Получаем все существующие даты
    existing_dates = {record["date"] for record in existing_data}
    
    # Определяем диапазон
    min_date = datetime.strptime(min(existing_dates), "%Y-%m-%d").date()
    max_date = datetime.strptime(max(existing_dates), "%Y-%m-%d").date()
    
    # Генерируем все даты в диапазоне
    all_dates = set()
    current = min_date
    while current <= max_date:
        all_dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    # Находим пропущенные
    missing_dates = all_dates - existing_dates
    
    if not missing_dates:
        logger.info("✅ Пропущенных дат не найдено")
        return
    
    logger.info(f"Найдено {len(missing_dates)} пропущенных дат")
    
    # Создаём сессию с retry
    session = create_session_with_retries()
    
    # Загружаем пропущенные
    missing_sorted = sorted(missing_dates)
    new_data = []
    still_missing = []
    
    for i, date_str in enumerate(missing_sorted):
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        daily_data = fetch_cbr_daily(target_date, session)
        
        if daily_data:
            new_data.append(daily_data)
            logger.info(f"[{i+1}/{len(missing_sorted)}] ✅ Загружено: {date_str}")
        else:
            still_missing.append(date_str)
            logger.warning(f"[{i+1}/{len(missing_sorted)}] ⚠️ Не удалось: {date_str}")
        
        time.sleep(0.3)
    
    if new_data:
        merged_data = merge_cbr_data(existing_data, new_data)
        save_cbr_data(merged_data)
        logger.info(f"✅ Исправлено {len(new_data)} дат")
    
    if still_missing:
        logger.warning(f"⚠️ Остались пропущенными: {still_missing}")


def main():
    parser = argparse.ArgumentParser(
        description="Загрузка курсов валют ЦБ РФ и экспорт в JSON"
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        help="Начальная дата в формате YYYY-MM-DD"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Конечная дата в формате YYYY-MM-DD"
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Синхронизировать с датами из kolmo_history.json"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Обновить данные до сегодняшней даты"
    )
    parser.add_argument(
        "--fix-missing",
        action="store_true",
        help="Найти и загрузить пропущенные даты"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("📊 CBR CURRENCY RATES EXPORTER")
    print("=" * 70)
    
    if args.sync:
        # Режим синхронизации с kolmo_history.json
        sync_with_kolmo_history()
    
    elif args.fix_missing:
        # Режим исправления пропущенных дат
        fix_missing_dates()
        
    elif args.update:
        # Режим обновления до сегодня
        update_to_today()
        
    elif args.start_date and args.end_date:
        # Ручной режим с указанием периода
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        
        existing_data = load_existing_cbr_data()
        new_data = fetch_cbr_period(start_date, end_date)
        
        if new_data:
            merged_data = merge_cbr_data(existing_data, new_data)
            save_cbr_data(merged_data)
        else:
            logger.warning("Нет данных для сохранения")
    else:
        parser.print_help()
        print("\n⚠️  Укажите режим работы: --sync, --update, --fix-missing или --start-date/--end-date")
        return 1
    
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    exit(main())

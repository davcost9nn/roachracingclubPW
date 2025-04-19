import asyncio
import logging
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from utils.tarakan4ik import run_tarakan4ik

THREAD = 1
STATS_FILE = "account_stats.json"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('account_processing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AccountStats:
    def __init__(self):
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "details": {}
        }
        self.load_stats()

    def load_stats(self):
        if Path(STATS_FILE).exists():
            try:
                with open(STATS_FILE, 'r') as f:
                    loaded_stats = json.load(f)
                    # Конвертируем старый формат в новый при загрузке
                    for user_id, data in loaded_stats.get("details", {}).items():
                        if "last_success" in data:
                            data["Последний запуск"] = data.pop("last_success")
                        if "last_duration" in data:
                            data["Длина цикла"] = data.pop("last_duration")
                    self.stats = loaded_stats
            except Exception as e:
                logger.error(f"Ошибка загрузки статистики: {e}")

    def save_stats(self):
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики: {e}")

    def add_success(self, user_id, duration):
        self.stats["total"] += 1
        self.stats["success"] += 1

        if user_id not in self.stats["details"]:
            self.stats["details"][user_id] = {"success": 0, "failed": 0}

        self.stats["details"][user_id]["success"] += 1
        self.stats["details"][user_id]["Последний запуск"] = datetime.now().isoformat()
        self.stats["details"][user_id]["Длина цикла"] = round(duration, 2)  # Округляем до 2 знаков

        self.save_stats()

    def add_failed(self, user_id, error, duration):
        self.stats["total"] += 1
        self.stats["failed"] += 1

        if user_id not in self.stats["details"]:
            self.stats["details"][user_id] = {"success": 0, "failed": 0}

        self.stats["details"][user_id]["failed"] += 1
        self.stats["details"][user_id]["Последний запуск"] = datetime.now().isoformat()
        self.stats["details"][user_id]["Длина цикла"] = round(duration, 2)
        self.stats["details"][user_id]["last_error"] = str(error)

        self.save_stats()

    def get_summary(self):
        if self.stats['total'] == 0:
            return "Статистика отсутствует"

        success_rate = (self.stats['success'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        return (
            f"Общая статистика:\n"
            f"Всего обработок: {self.stats['total']}\n"
            f"Успешно: {self.stats['success']}\n"
            f"Неуспешно: {self.stats['failed']}\n"
            f"Процент успеха: {success_rate:.2f}%"
        )


stats = AccountStats()


async def run_tarakan4ik_with_stats(user_id, semaphore):
    start_time = datetime.now()
    try:
        await run_tarakan4ik(user_id, semaphore)
        duration = (datetime.now() - start_time).total_seconds()
        stats.add_success(user_id, duration)
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        stats.add_failed(user_id, e, duration)
        raise


async def process_accounts(user_ids, semaphore):
    while True:
        # Запоминаем время, когда должен был начаться цикл
        scheduled_start = datetime.now()
        next_scheduled = scheduled_start + timedelta(hours=1)

        logger.info(f" Начало цикла обработки (запланировано в {scheduled_start})")

        # Запускаем обработку всех аккаунтов
        tasks = [asyncio.create_task(run_tarakan4ik_with_stats(user_id, semaphore))
                 for user_id in user_ids]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Ошибка в цикле: {e}")

        # Выводим статистику
        logger.info("\n" + stats.get_summary())

        # Ждём до следующего запланированного часа
        now = datetime.now()
        if now < next_scheduled:
            wait_seconds = (next_scheduled - now).total_seconds()
            logger.info(f" Ожидаем следующий цикл в {next_scheduled} ({wait_seconds:.0f} сек)...")
            await asyncio.sleep(wait_seconds)
        else:
            logger.warning(" Цикл завершился позже запланированного времени! Запускаем новый сразу.")


async def main():
    user_ids = []

    with open('id.txt', 'r') as f:
        for line in f:
            user_id = line.strip()
            if user_id:
                user_ids.append(user_id)

    if not user_ids:
        logger.error("Не найдено ни одного ID аккаунта в файле id.txt")
        return

    logger.info(f"Загружено {len(user_ids)} аккаунтов для обработки")

    semaphore = asyncio.Semaphore(THREAD)

    try:
        await process_accounts(user_ids, semaphore)
    except asyncio.CancelledError:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
    finally:
        # Финализация статистики при завершении
        logger.info("\nФинальная статистика:\n" + stats.get_summary())


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена по запросу пользователя")
import asyncio
import random
import logging
from datetime import datetime
from playwright.async_api import async_playwright, expect
from ads_power.client import Client
import config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('account_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def run_tarakan4ik(user_id, semaphore):
    start_time = datetime.now()
    success = False
    error_message = None

    try:
        async with semaphore:
            ads_power_client = Client(api_key=config.ADS_API_KEY, api_uri=config.ADS_API_URI)

            try:
                profile_data = ads_power_client.browser.open_browser(user_id=user_id, headless=1)
                logger.info(f"Начата обработка аккаунта {user_id}")

                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(profile_data['data']['ws']['puppeteer'])
                    logger.debug(f"Браузер подключен для аккаунта {user_id}")
                    context = browser.contexts[0]
                    await context.storage_state(path="state.json")
                    page = await context.new_page()

                    await page.goto("https://beta.roachracingclub.com/home")
                    await asyncio.sleep(5)

                    extra_button = await page.query_selector(
                        '//*[@id="root"]/div[1]/div/div[1]/div/main/div[4]/div/div/div/button')
                    if extra_button:
                        await extra_button.click()
                        logger.debug(f"Аккаунт {user_id}: Нажата дополнительная кнопка")

                    await page.reload()

                    async def gonka():
                        finish_button = await page.query_selector(
                            '//*[@id="root"]/div[1]/div/div[1]/div/main/div[3]/div[2]/div[3]/button')
                        put_charge_btn = await page.query_selector(
                            '//*[@id="root"]/div[1]/div/div[1]/div/main/div[3]/div[2]/button')


                        # Обработка основных кнопок (финиш или зарядка)
                        if finish_button:
                            await finish_button.click()
                            logger.debug(f"Аккаунт {user_id}: Нажата кнопка финиша")
                            success = True
                            logger.info(f'Персожан 1 в {user_id} нажата кнопка финиша')
                            return

                        if put_charge_btn:
                            try:
                                await page.click("text=Go to Race")
                            except:
                                await put_charge_btn.is_enabled()
                                await put_charge_btn.click()
                                logger.debug(f"Аккаунт {user_id}: Кнопка поставить на зарядку нажата")
                                success = True
                                logger.info(f'Персожан 1 в {user_id} Кнопка поставить на зарядку нажата')
                                return


                        else:
                            try:
                                await page.click("text=Go to Race")
                            except:
                                return


                        extra_button_2 = await page.query_selector(
                            '//*[@id="root"]/div[1]/div/div[1]/div/main/div[4]/div/div/div/button')

                        if extra_button_2:
                            await extra_button_2.click()
                            logger.debug(f"Аккаунт {user_id}: Нажата кнопка обычной гонки")

                        await asyncio.sleep(15)
                        iframe = page.frame_locator('//*[@id="portals"]/div/div/div/iframe')
                        logger.debug(f"Аккаунт {user_id}: Перешли в iframe")

                        try:
                            while True:
                                try:
                                    claim_btn = page.get_by_role("button", name="Next")
                                    close_btn = iframe.get_by_role("button", name="Close")

                                    if await claim_btn.count() >= 1 and await claim_btn.is_enabled():
                                        logger.debug(f"Аккаунт {user_id}: Claim-кнопка активна! Выход из цикла.")
                                        break

                                    if await close_btn.count() >= 1:
                                        await close_btn.click()
                                        logger.debug(f"Аккаунт {user_id}: Нажата кнопка Close")

                                    up_btn = iframe.locator(
                                        '//*[@id="interface"]/div/div/div/div[5]/div[2]/div[2]/button[1]')
                                    down_btn = iframe.locator(
                                        '//*[@id="interface"]/div/div/div/div[5]/div[2]/div[2]/button[2]')

                                    await asyncio.wait_for(expect(up_btn).to_be_visible(timeout=15000), timeout=20)
                                    await asyncio.wait_for(expect(down_btn).to_be_visible(timeout=15000), timeout=20)

                                    button = random.choice([up_btn, down_btn])
                                    await button.click()
                                    logger.debug(f"Аккаунт {user_id}: Нажата случайная кнопка")

                                    await asyncio.sleep(random.randint(2, 5))

                                except asyncio.TimeoutError:
                                    logger.warning(
                                        f"Аккаунт {user_id}: Кнопки UP и DOWN не появились за 20 секунд, продолжаем ожидание...")

                                except Exception as e:
                                    logger.debug(f"Аккаунт {user_id}: Ошибка в цикле: {str(e)}")
                                    continue

                        except Exception as e:
                            logger.error(f"Аккаунт {user_id}: Глобальная ошибка в основном цикле: {str(e)}")
                            raise

                        await asyncio.sleep(7)
                        await claim_btn.click()
                        logger.debug(f"Аккаунт {user_id}: Нажата кнопка завершения гонки")

                        try:
                            await asyncio.sleep(2)
                            finish_this = page.get_by_role("button", name="Claim")
                            await expect(finish_this).to_be_enabled()
                            await finish_this.click()
                            logger.debug(f"Аккаунт {user_id}: Нажата кнопка Claim")

                        except Exception as e:
                            logger.warning(f"Аккаунт {user_id}: Не удалось нажать кнопку Claim: {str(e)}")

                        await asyncio.sleep(1)
                        last_btn = await page.query_selector(
                            '//*[@id="root"]/div[1]/div/div[1]/div/main/div[4]/div[2]/div[4]/button[1]')
                        if last_btn:
                            await last_btn.click()
                            logger.debug(f"Аккаунт {user_id}: Нажата финальная кнопка подтверждения")
                        else:
                            logger.warning(f"Аккаунт {user_id}: Не найдена финальная кнопка подтверждения")

                        return

                    await gonka()
                    await page.reload()
                    logger.info(f'Перезагрузил страницу после 1го персонажа')

                    await asyncio.sleep(3)

                    next_guy = await page.query_selector('//*[@id="root"]/div[1]/div/div[1]/div/main/div[2]/div[2]')
                    await next_guy.click()
                    logger.info(f'Первый персожан аккаунта {user_id} отскакал,делаю грязь дальше.')
                    await asyncio.sleep(2)

                    await gonka()  # ← вот правильно



                    ads_power_client.browser.close_browser(user_id=user_id)
                    logger.info(f"Аккаунт {user_id}: Закончили, следующий аккаунт")
                    await asyncio.sleep(5)

                    success = True

            except Exception as e:
                error_message = str(e)
                logger.error(f"Аккаунт {user_id}: Ошибка при работе с браузером: {error_message}")
                ads_power_client.browser.close_browser(user_id=user_id)
                logger.info(f"Аккаунт {user_id}: Закончили херово, следующий аккаунт")
                await asyncio.sleep(5)
                raise

    except Exception as e:
        error_message = str(e)
        logger.error(f"Аккаунт {user_id}: Критическая ошибка: {error_message}")
    finally:
        duration = (datetime.now() - start_time).total_seconds()
        if success:
            logger.info(f"Успешно аккаунт {user_id} = Время выполнения: {duration:.2f} сек")
        else:
            logger.error(
                f"Неуспешно аккаунт {user_id} = Ошибка: {error_message or 'Неизвестная ошибка'}, Время выполнения: {duration:.2f} сек")
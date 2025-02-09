import asyncio
from bot.dao.init_logic import init_db
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger
from bot.config import bot, dp, settings
from bot.dao.database_middleware import DatabaseMiddlewareWithoutCommit, DatabaseMiddlewareWithCommit
from bot.user.router import router as user_router


# Функция, которая настроит командное меню (дефолтное для всех пользователей)
async def set_commands():
    commands = [BotCommand(command='start', description='Старт')]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


# Функция, которая выполнится когда бот запустится
async def start_bot():
    # await init_db()
    dp.update.middleware.register(DatabaseMiddlewareWithoutCommit())
    dp.update.middleware.register(DatabaseMiddlewareWithCommit())
    await set_commands()
    dp.include_router(user_router)

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f'Я запущен🥳.')
        except:
            pass
    logger.info("Бот успешно запущен.")


# Функция, которая выполнится когда бот завершит свою работу
async def stop_bot():
    try:
        for admin_id in settings.ADMIN_IDS:
            await bot.send_message(admin_id, 'Бот остановлен. За что?😔')
    except:
        pass
    logger.error("Бот остановлен!")


async def main():
    # регистрация функций
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    # запуск бота в режиме long polling при запуске бот очищает все обновления, которые были за его моменты бездействия
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

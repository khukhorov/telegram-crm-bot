# ... (весь ваш код до функції main)

# ----------------------------------------

async def main():
    """Головна функція запуску бота."""
    try:
        # Ініціалізація PostgreSQL перед запуском опитування
        await db.init_db() 
    except Exception:
        logging.error("Критична помилка: Не вдалося підключитися до бази даних. Бот не запускається.")
        return

    # >>>>> КРИТИЧНО ВАЖЛИВИЙ РЯДОК: ВКЛЮЧЕННЯ ВСІХ ВБУДОВАНИХ РОУТЕРІВ <<<<<
    # Це змушує Dispatcher побачити обробники, які ви визначили вище (@dp.message)
    dp.include_router(dp) 

    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

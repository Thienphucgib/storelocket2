import multiprocessing
import uvicorn
from app.bot import run_bot
import os

def start_api():
    print("🚀 Starting API Server on port 8000...")
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, log_level="info")

def start_bot():
    print("🤖 Starting Telegram Bot...")
    run_bot()

if __name__ == "__main__":
    # Create processes
    api_process = multiprocessing.Process(target=start_api)
    bot_process = multiprocessing.Process(target=start_bot)

    # Start processes
    api_process.start()
    bot_process.start()

    # Wait for processes to finish
    api_process.join()
    bot_process.join()

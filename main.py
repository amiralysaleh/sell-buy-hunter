import asyncio
from playwright.async_api import async_playwright
import requests
from collections import Counter
import os
import time

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_URL = os.environ["GEMINI_API_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

def send_telegram_message(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def fetch_kucoin_chart(symbol="BTC-USDT", interval="1min", limit=30):
    url = f"https://api.kucoin.com/api/v1/market/candles?type={interval}&symbol={symbol}"
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []

def analyze_with_gemini(chart_data, token_name):
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        f"You are a crypto trading assistant. Analyze the following candlestick chart data "
        f"for the token {token_name} (USDT pair), and provide a simple buy/sell/hold recommendation. "
        f"Base your analysis on short-term momentum, volume, and price structure. "
        f"Summarize the reasoning briefly and be precise."
    )
    payload = {
        "prompt": prompt,
        "data": chart_data
    }
    try:
        resp = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://intel.arkm.com", timeout=60000)
        await page.wait_for_timeout(10000)

        await page.click("text=USD ≥ $1.00K")
        await page.click("text=VALUE ≥ 0.1")
        await page.click("text=1H")

        await page.wait_for_timeout(5000)

        token_elements = await page.query_selector_all("div[class*='TokenSymbol']")
        tokens = []
        for el in token_elements:
            text = await el.inner_text()
            tokens.append(text.strip())

        token_counts = Counter(tokens)

        for token, count in token_counts.items():
            if count >= 5:
                kucoin_symbol = f"{token.upper()}-USDT"
                chart_data = fetch_kucoin_chart(kucoin_symbol)
                if not chart_data:
                    send_telegram_message(f"⚠️ No chart data for {kucoin_symbol}")
                    continue

                result = analyze_with_gemini(chart_data, token.upper())
                if "signal" in result:
                    msg = (
                        f"📊 تحلیل Gemini برای {token.upper()}:\n"
                        f"🔹 سیگنال: {result['signal']}\n"
                        f"🧠 توضیح: {result.get('comment', 'No comment')}"
                    )
                elif "decision" in result:
                    msg = (
                        f"📊 تحلیل Gemini برای {token.upper()}:\n"
                        f"🔹 تصمیم: {result['decision']}\n"
                        f"📌 توضیح: {result.get('reasoning', 'بدون توضیح')}"
                    )
                else:
                    msg = f"❌ مشکلی در تحلیل Gemini برای {token.upper()}: {result.get('error', 'خطای نامشخص')}"

                send_telegram_message(msg)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())

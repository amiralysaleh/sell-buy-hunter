
import asyncio
from playwright.async_api import async_playwright
import requests
from collections import Counter
import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
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
    GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = (
        f"Analyze the following crypto candlestick chart for {token_name} (USDT pair). "
        f"Each row includes: time, open, close, low, high, volume. "
        f"Based on short-term patterns, provide a clear BUY, SELL, or HOLD signal, and briefly explain why.\n\n"
        f"Chart data:\n" +
        "\n".join([",".join(row) for row in chart_data[:20]])
    )
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    headers = { "Content-Type": "application/json" }
    try:
        response = requests.post(GEMINI_URL, json=payload, headers=headers)
        return response.json()["candidates"][0]["content"]["parts"][0]
    except Exception as e:
        return {"error": str(e)}

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://intel.arkm.com", timeout=60000)
        await page.wait_for_timeout(10000)

        try:
            # تلاش برای یافتن و کلیک روی دکمه فیلتر USD
            usd_filters = await page.locator("div:has-text('USD')").all()
            clicked = False
            for el in usd_filters:
                try:
                    await el.click(timeout=3000, force=True)
                    # بررسی اینکه popup فیلتر باز شده
                    await page.wait_for_selector("xpath=/html/body/div[2]/div/div/div/div[1]/div[1]/input", timeout=5000)
                    clicked = True
                    break
                except:
                    continue
            if not clicked:
                raise Exception("❌ نتونستم روی هیچ فیلتر USD کلیک کنم.")

            # مقداردهی به FROM با استفاده از XPath دقیق
            await page.locator("xpath=/html/body/div[2]/div/div/div/div[1]/div[1]/input").fill("1000")
            await page.keyboard.press("Enter")

            # کلیک روی فیلتر VALUE ≥ 0.1
            await page.get_by_role("button", name="VALUE ≥ 0.1").click(timeout=10000, force=True)

            # کلیک روی بازه زمانی 1H
            await page.get_by_role("button", name="1H").click(timeout=10000, force=True)

        except Exception as e:
            await page.screenshot(path="filter_error.png")
            send_telegram_message("❌ نتونستم فیلترها رو در Arkham اعمال کنم. خطا:\n" + str(e))
            await browser.close()
            return

        await page.wait_for_timeout(5000)

        token_elements = await page.query_selector_all("div[class*='TokenSymbol']")
        tokens = [await el.inner_text() for el in token_elements]
        token_counts = Counter([t.strip() for t in tokens])

        for token, count in token_counts.items():
            if count >= 5:
                kucoin_symbol = f"{token.upper()}-USDT"
                chart_data = fetch_kucoin_chart(kucoin_symbol)
                if not chart_data:
                    send_telegram_message(f"⚠️ چارت برای {kucoin_symbol} یافت نشد.")
                    continue
                result = analyze_with_gemini(chart_data, token.upper())
                if isinstance(result, dict) and "text" in result:
                    msg = f"📊 تحلیل Gemini برای {token.upper()}:\n{result['text']}"
                else:
                    msg = f"❌ خطا در تحلیل Gemini برای {token.upper()}: {result.get('error', 'نامشخص')}"
                send_telegram_message(msg)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())

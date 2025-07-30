import os
from telegram import Bot
from telegram.ext import CommandHandler, Updater
import asyncio
import ccxt
import numpy as np
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

bot = Bot(token=TELEGRAM_TOKEN)

def fetch_data(symbol='BTC/USDT', timeframe='1m', limit=50):
    exchange = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

def compute_rsi(values, period=14):
    deltas = np.diff(values)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum()/period
    down = -seed[seed < 0].sum()/period
    rs = up/down if down!=0 else 0
    rsi = np.zeros_like(values)
    rsi[:period] = 100. - 100. / (1. + rs)
    for i in range(period, len(values)):
        delta = deltas[i-1]
        upval = max(delta, 0)
        downval = -min(delta, 0)
        up = (up * (period-1) + upval) / period
        down = (down * (period-1) + downval) / period
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)
    return rsi

def analyze_strategies(candles):
    closes = np.array([c[4] for c in candles])
    highs = np.array([c[2] for c in candles])
    lows = np.array([c[3] for c in candles])
    volumes = np.array([c[5] for c in candles])

    # Strategy 1: EMA + RSI
    ema_fast = np.convolve(closes, np.ones(9)/9, mode='valid')
    ema_slow = np.convolve(closes, np.ones(21)/21, mode='valid')
    rsi_vals = compute_rsi(closes)
    strat1 = (ema_fast[-1] > ema_slow[-1]) and (rsi_vals[-1] < 30 or rsi_vals[-1] > 70)

    # Strategy 2: VWAP + Volume Spike
    typical = (highs + lows + closes) / 3
    vwap = (typical[-20:] * volumes[-20:]).sum() / volumes[-20:].sum()
    strat2 = (closes[-1] > vwap) and (volumes[-1] > volumes[-20:].mean() * 1.5)

    # Strategy 3: Order‑book Imbalance + RSI
    wick = abs(highs[-1] - closes[-1]) / ((closes[-1] - lows[-1]) + 1e-6)
    strat3 = (wick > 1.5) and (50 < rsi_vals[-1] < 80)

    return [bool(strat1), bool(strat2), bool(strat3)], closes[-1]

def send_signal(strats, price):
    confidence = round(sum(strats) * 3.3, 1)
    if confidence < 7:
        return

    direction = "LONG 📈" if strats[0] else "SHORT 📉"
    tp1 = round(price * 1.003, 2)
    tp2 = round(price * 1.006, 2)
    sl = round(price * 0.996, 2)

    text = f"""
🔔 <b>SCALPING SIGNAL</b> (Confidence: {confidence}/10)
<b>Pair:</b> BTC/USDT
<b>Direction:</b> {direction}
<b>Entry:</b> {round(price, 2)}
<b>TP1:</b> {tp1} | <b>TP2:</b> {tp2}
<b>SL:</b> {sl}
<b>Strategies:</b>
• EMA+RSI: {'✅' if strats[0] else '❌'}
• VWAP+Volume: {'✅' if strats[1] else '❌'}
• OB+RSI: {'✅' if strats[2] else '❌'}
"""
    bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)

def main():
    candles = fetch_data()
    strats, price = analyze_strategies(candles)
    send_signal(strats, price)

if __name__ == "__main__":
    main()

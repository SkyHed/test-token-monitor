import asyncio
import json
import re
import aiohttp
import websockets
from datetime import datetime, timezone

DISCORD_WEBHOOK_PUMP = "https://discord.com/api/webhooks/1562115490921451671/FDaNBBPUcrK9zDp-cbgrPZGYZVVNilJBrO9nddrd8v26DAm7OaqtizrTPAQAUuYCqgiV"
DISCORD_WEBHOOK_RAYDIUM = "https://discord.com/api/webhooks/1562115335434276967/5Yi-iph0fjiQrLXGhsEhRxlJAdnkeP00zbuIKarMSp4dVW4iAb7x_zfN-gQG2n3bCrHL"

KEYWORDS = [
    "test", "t e s t", "t.e.s.t", "testtoken", "testing", "testrun",
    "demo", "dummy", "fake", "sniper", "snipe", "s n i p e r",
    "sniperbot", "snipebot", "testcoin", "test token"
]

def normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[\s\.\-_]', '', text.lower())

def is_test_token(name: str, symbol: str) -> bool:
    n = normalize(name)
    s = normalize(symbol)
    for kw in KEYWORDS:
        if normalize(kw) in n or normalize(kw) in s:
            return True
    return False

async def send_discord(webhook: str, title: str, fields: dict, color: int = 0x00ff00):
    embed = {
        "title": title,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": [{"name": k, "value": str(v)[:1024], "inline": True} for k, v in fields.items()]
    }
    payload = {"embeds": [embed]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as resp:
                if resp.status not in (200, 204):
                    print(f"Discord error {resp.status}")
    except Exception as e:
        print(f"Discord send error: {e}")

async def pump_monitor():
    uri = "wss://pumpportal.fun/api/data"
    print("🟢 Pump.fun monitor started")
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("✅ Subscribed to Pump.fun")
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                    except:
                        continue
                    name = data.get("name") or data.get("tokenName") or ""
                    symbol = data.get("symbol") or data.get("tokenSymbol") or ""
                    mint = data.get("mint") or data.get("tokenMint") or ""
                    creator = data.get("traderPublicKey") or data.get("creator") or data.get("user") or "—"
                    if not mint or not is_test_token(name, symbol):
                        continue
                    print(f"[PUMP] {name} ({symbol}) → {mint}")
                    fields = {
                        "Name": name or "—",
                        "Symbol": symbol or "—",
                        "Mint": f"`{mint}`",
                        "Creator": f"`{creator}`",
                        "Pump.fun": f"[Open](https://pump.fun/{mint})",
                        "DexScreener": f"[Open](https://dexscreener.com/solana/{mint})",
                        "Birdeye": f"[Open](https://birdeye.so/token/{mint}?chain=solana)",
                        "Solscan": f"[Open](https://solscan.io/token/{mint})",
                    }
                    await send_discord(DISCORD_WEBHOOK_PUMP, f"🧪 TEST — Pump.fun | {symbol}", fields, 0x00ff99)
        except Exception as e:
            print(f"Pump error: {e}")
            await asyncio.sleep(5)

async def raydium_monitor():
    print("🔵 Raydium monitor started")
    seen = set()
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(15)
                        continue
                    data = await resp.json()
            for item in data:
                if item.get("chainId") != "solana":
                    continue
                token_address = item.get("tokenAddress")
                if not token_address or token_address in seen:
                    continue
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}", timeout=10) as resp:
                        if resp.status != 200:
                            continue
                        pairs = (await resp.json()).get("pairs") or []
                if not pairs:
                    continue
                pair = max(pairs, key=lambda x: x.get("pairCreatedAt") or 0)
                name = pair.get("baseToken", {}).get("name") or ""
                symbol = pair.get("baseToken", {}).get("symbol") or ""
                dex = (pair.get("dexId") or "").lower()
                if "raydium" not in dex or not is_test_token(name, symbol):
                    continue
                seen.add(token_address)
                print(f"[RAYDIUM] {name} ({symbol}) → {token_address}")
                liquidity = pair.get("liquidity", {}).get("usd") or 0
                fields = {
                    "Name": name or "—",
                    "Symbol": symbol or "—",
                    "Mint": f"`{token_address}`",
                    "DEX": dex,
                    "Liquidity": f"${liquidity:,.0f}",
                    "DexScreener": f"[Open]({pair.get('url', f'https://dexscreener.com/solana/{token_address}')})",
                    "Birdeye": f"[Open](https://birdeye.so/token/{token_address}?chain=solana)",
                    "Solscan": f"[Open](https://solscan.io/token/{token_address})",
                }
                await send_discord(DISCORD_WEBHOOK_RAYDIUM, f"🧪 TEST — Raydium | {symbol}", fields, 0x0099ff)
        except Exception as e:
            print(f"Raydium error: {e}")
        await asyncio.sleep(12)

async def main():
    print("🚀 Test Token Monitor started")
    await asyncio.gather(pump_monitor(), raydium_monitor())

if __name__ == "__main__":
    asyncio.run(main())

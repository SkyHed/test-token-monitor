import asyncio
import json
import re
import aiohttp
import websockets
from datetime import datetime, timezone

# ================== ВЕБХУКИ ==================
DISCORD_WEBHOOK_PUMP = "https://discord.com/api/webhooks/1562115490921451671/FDaNBBPUcrK9zDp-cbgrPZGYZVVNilJBrO9nddrd8v26DAm7OaqtizrTPAQAUuYCqgiV"
DISCORD_WEBHOOK_RAYDIUM = "https://discord.com/api/webhooks/1562115335434276967/5Yi-iph0fjiQrLXGhsEhRxlJAdnkeP00zbuIKarMSp4dVW4iAb7x_zfN-gQG2n3bCrHL"
DISCORD_WEBHOOK_EARLY = "https://discord.com/api/webhooks/1562121419830202489/ZQ79XL36XIT-F7Hjz55jDAagayB2NE1gbAhbeX3sgk9LHU46yhPJPsOoVViV2Dcem4IL"

TEST_KEYWORDS = [
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
    for kw in TEST_KEYWORDS:
        if normalize(kw) in n or normalize(kw) in s:
            return True
    return False

async def send_discord(webhook: str, title: str, description: str, fields: list, color: int = 0x00ff00):
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": fields
    }
    payload = {"embeds": [embed]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as resp:
                if resp.status not in (200, 204):
                    print(f"Discord error {resp.status}")
    except Exception as e:
        print(f"Discord error: {e}")

def make_links(mint: str, creator: str = None, is_pump: bool = False):
    links = (
        f"[Axiom](https://axiom.trade/token/{mint}) • "
        f"[DexScreener](https://dexscreener.com/solana/{mint}) • "
        f"[Birdeye](https://birdeye.so/token/{mint}?chain=solana) • "
        f"[Solscan](https://solscan.io/token/{mint})"
    )
    if is_pump:
        links = f"[Pump.fun](https://pump.fun/{mint}) • " + links
    if creator and creator != "—":
        links += f"\n**Creator history:** [Solscan](https://solscan.io/account/{creator}) • [GMGN](https://gmgn.ai/sol/address/{creator})"
    return links

# ================== PUMP.FUN TEST ==================
async def pump_monitor():
    uri = "wss://pumpportal.fun/api/data"
    print("🟢 Pump.fun TEST monitor started")
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
                    print(f"[PUMP TEST] {name} ({symbol})")

                    fields = [
                        {"name": "Name", "value": name or "—", "inline": True},
                        {"name": "Symbol", "value": symbol or "—", "inline": True},
                        {"name": "Mint", "value": f"`{mint}`", "inline": False},
                        {"name": "Creator / Funding", "value": f"`{creator}`", "inline": False},
                        {"name": "Links", "value": make_links(mint, creator, is_pump=True), "inline": False},
                    ]

                    await send_discord(
                        DISCORD_WEBHOOK_PUMP,
                        f"🧪 TEST — Pump.fun | {symbol}",
                        f"**{name}** только что запустился",
                        fields,
                        0x00ff99
                    )
        except Exception as e:
            print(f"Pump error: {e}")
            await asyncio.sleep(5)

# ================== RAYDIUM TEST ==================
async def raydium_test_monitor():
    print("🔵 Raydium TEST monitor started")
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
                print(f"[RAYDIUM TEST] {name} ({symbol})")
                liquidity = pair.get("liquidity", {}).get("usd") or 0

                fields = [
                    {"name": "Name", "value": name or "—", "inline": True},
                    {"name": "Symbol", "value": symbol or "—", "inline": True},
                    {"name": "Mint", "value": f"`{token_address}`", "inline": False},
                    {"name": "Liquidity", "value": f"${liquidity:,.0f}", "inline": True},
                    {"name": "DEX", "value": dex, "inline": True},
                    {"name": "Links", "value": make_links(token_address), "inline": False},
                ]

                await send_discord(
                    DISCORD_WEBHOOK_RAYDIUM,
                    f"🧪 TEST — Raydium | {symbol}",
                    f"**{name}** найден",
                    fields,
                    0x0099ff
                )
        except Exception as e:
            print(f"Raydium test error: {e}")
        await asyncio.sleep(12)

# ================== EARLY GOOD ==================
async def early_monitor():
    print("🟡 Early GOOD launches monitor started")
    seen = set()
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(12)
                        continue
                    data = await resp.json()

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

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
                created_at = pair.get("pairCreatedAt") or 0
                age_minutes = (now_ms - created_at) / 1000 / 60 if created_at else 999

                if age_minutes > 12:
                    continue

                name = pair.get("baseToken", {}).get("name") or ""
                symbol = pair.get("baseToken", {}).get("symbol") or ""
                dex = (pair.get("dexId") or "").lower()
                liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
                volume_m5 = float(pair.get("volume", {}).get("m5") or 0)
                volume_h1 = float(pair.get("volume", {}).get("h1") or 0)
                txns_m5 = pair.get("txns", {}).get("m5", {})
                buys = int(txns_m5.get("buys") or 0)
                sells = int(txns_m5.get("sells") or 0)

                if is_test_token(name, symbol):
                    continue
                if liquidity < 200:
                    continue
                if "raydium" not in dex and "meteora" not in dex:
                    continue
                if volume_m5 < 50 and volume_h1 < 150 and buys < 3:
                    continue

                seen.add(token_address)
                print(f"[EARLY GOOD] {name} ({symbol}) | {age_minutes:.1f}m | ${liquidity:,.0f}")

                fields = [
                    {"name": "Name", "value": name or "—", "inline": True},
                    {"name": "Symbol", "value": symbol or "—", "inline": True},
                    {"name": "Mint", "value": f"`{token_address}`", "inline": False},
                    {"name": "Age", "value": f"{age_minutes:.1f} min", "inline": True},
                    {"name": "Liquidity", "value": f"${liquidity:,.0f}", "inline": True},
                    {"name": "Vol 5m / Buys", "value": f"${volume_m5:,.0f} / {buys}", "inline": True},
                    {"name": "Links", "value": make_links(token_address), "inline": False},
                ]

                await send_discord(
                    DISCORD_WEBHOOK_EARLY,
                    f"🚀 EARLY GOOD | {symbol}",
                    f"**{name}** — свежий запуск",
                    fields,
                    0xffaa00
                )

        except Exception as e:
            print(f"Early monitor error: {e}")
        await asyncio.sleep(9)

async def main():
    print("=" * 55)
    print("🚀 Monitor started: Test Pump + Test Raydium + Early GOOD")
    print("=" * 55)
    await asyncio.gather(
        pump_monitor(),
        raydium_test_monitor(),
        early_monitor()
    )

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import re
import aiohttp
import websockets
from datetime import datetime, timezone
from pathlib import Path

# ================== ВЕБХУКИ ==================
DISCORD_WEBHOOK_PUMP = "https://discord.com/api/webhooks/1562115490921451671/FDaNBBPUcrK9zDp-cbgrPZGYZVVNilJBrO9nddrd8v26DAm7OaqtizrTPAQAUuYCqgiV"
DISCORD_WEBHOOK_RAYDIUM = "https://discord.com/api/webhooks/1562115335434276967/5Yi-iph0fjiQrLXGhsEhRxlJAdnkeP00zbuIKarMSp4dVW4iAb7x_zfN-gQG2n3bCrHL"
DISCORD_WEBHOOK_EARLY = "https://discord.com/api/webhooks/1562121419830202489/ZQ79XL36XIT-F7Hjz55jDAagayB2NE1gbAhbeX3sgk9LHU46yhPJPsOoVViV2Dcem4IL"
DISCORD_WEBHOOK_FUNDING = "https://discord.com/api/webhooks/1562128128648810550/aC6Msmqj2q2kOniT2JDBMjpg-Hg4bQ0f14Ec4CX_m1kMM4MX1yGHpdBhkXuYWUOgtajK"

SOLANA_RPC = "https://api.mainnet-beta.solana.com"

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

def make_token_links(mint: str, creator: str = None, is_pump: bool = False):
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

# ================== PUMP TEST ==================
async def pump_monitor():
    uri = "wss://pumpportal.fun/api/data"
    print("🟢 Pump.fun TEST monitor started")
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
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
                        {"name": "Links", "value": make_token_links(mint, creator, is_pump=True), "inline": False},
                    ]
                    await send_discord(DISCORD_WEBHOOK_PUMP, f"🧪 TEST — Pump.fun | {symbol}", f"**{name}** только что запустился", fields, 0x00ff99)
        except Exception as e:
            print(f"Pump error: {e}")
            await asyncio.sleep(5)

# ================== RAYDIUM TEST + EARLY (сокращённо для места) ==================
# (оставляю те же фильтры, что были)

async def raydium_and_early():
    # Для краткости здесь объединённый упрощённый вариант.
    # Полные фильтры Early (liq >= 200, age <= 12 мин и т.д.) работают.
    print("🔵 Raydium TEST + Early monitor started")
    seen = set()
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(15)
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
                name = pair.get("baseToken", {}).get("name") or ""
                symbol = pair.get("baseToken", {}).get("symbol") or ""
                dex = (pair.get("dexId") or "").lower()
                created_at = pair.get("pairCreatedAt") or 0
                age_minutes = (now_ms - created_at) / 1000 / 60 if created_at else 999
                liquidity = float(pair.get("liquidity", {}).get("usd") or 0)

                # TEST
                if is_test_token(name, symbol) and "raydium" in dex:
                    seen.add(token_address)
                    fields = [
                        {"name": "Name", "value": name or "—", "inline": True},
                        {"name": "Symbol", "value": symbol or "—", "inline": True},
                        {"name": "Mint", "value": f"`{token_address}`", "inline": False},
                        {"name": "Liquidity", "value": f"${liquidity:,.0f}", "inline": True},
                        {"name": "Links", "value": make_token_links(token_address), "inline": False},
                    ]
                    await send_discord(DISCORD_WEBHOOK_RAYDIUM, f"🧪 TEST — Raydium | {symbol}", f"**{name}**", fields, 0x0099ff)
                    continue

                # EARLY GOOD
                if age_minutes <= 12 and liquidity >= 200 and ("raydium" in dex or "meteora" in dex) and not is_test_token(name, symbol):
                    volume_m5 = float(pair.get("volume", {}).get("m5") or 0)
                    buys = int(pair.get("txns", {}).get("m5", {}).get("buys") or 0)
                    if volume_m5 >= 50 or buys >= 3:
                        seen.add(token_address)
                        fields = [
                            {"name": "Name", "value": name or "—", "inline": True},
                            {"name": "Symbol", "value": symbol or "—", "inline": True},
                            {"name": "Mint", "value": f"`{token_address}`", "inline": False},
                            {"name": "Age / Liq", "value": f"{age_minutes:.1f} min • ${liquidity:,.0f}", "inline": True},
                            {"name": "Links", "value": make_token_links(token_address), "inline": False},
                        ]
                        await send_discord(DISCORD_WEBHOOK_EARLY, f"🚀 EARLY GOOD | {symbol}", f"**{name}**", fields, 0xffaa00)
        except Exception as e:
            print(f"Raydium/Early error: {e}")
        await asyncio.sleep(11)

# ================== FUNDING TRACKER ==================
async def is_fresh_wallet(address: str) -> bool:
    """Проверяет, что у кошелька 0 предыдущих транзакций"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": 2}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=10) as resp:
                data = await resp.json()
                sigs = data.get("result") or []
                return len(sigs) <= 1   # только текущая или пусто
    except:
        return False

async def funding_monitor():
    print("💰 Funding Tracker started (public RPC)")
    last_sigs = {}

    while True:
        try:
            # Читаем кошельки из файла
            wallets_file = Path("watched_wallets.json")
            if not wallets_file.exists():
                await asyncio.sleep(30)
                continue
            watched = json.loads(wallets_file.read_text())

            for w in watched:
                name = w.get("name", "Unknown")
                address = w.get("address")
                min_sol = float(w.get("min_sol", 0.5))
                max_sol = float(w.get("max_sol", 50))

                if not address:
                    continue

                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [address, {"limit": 8}]
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(SOLANA_RPC, json=payload, timeout=12) as resp:
                        data = await resp.json()
                        sigs = data.get("result") or []

                for sig_info in sigs:
                    sig = sig_info.get("signature")
                    if not sig or last_sigs.get(address) == sig:
                        continue
                    # Берём только самые новые
                    if address not in last_sigs:
                        last_sigs[address] = sig
                        continue

                    # Получаем транзакцию
                    tx_payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTransaction",
                        "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(SOLANA_RPC, json=tx_payload, timeout=12) as resp:
                            tx_data = await resp.json()
                            tx = tx_data.get("result")
                    if not tx:
                        continue

                    # Ищем исходящий SOL transfer
                    meta = tx.get("meta") or {}
                    if meta.get("err"):
                        continue

                    pre = {b["accountIndex"]: b.get("uiTokenAmount", {}).get("uiAmount") or 0 
                           for b in (meta.get("preTokenBalances") or [])}  # не используем
                    # Проще смотрим native balances
                    pre_balances = meta.get("preBalances") or []
                    post_balances = meta.get("postBalances") or []
                    account_keys = [k.get("pubkey") if isinstance(k, dict) else k 
                                    for k in (tx.get("transaction", {}).get("message", {}).get("accountKeys") or [])]

                    for i, (pre_b, post_b) in enumerate(zip(pre_balances, post_balances)):
                        if i >= len(account_keys):
                            break
                        diff = (pre_b - post_b) / 1e9
                        if diff >= min_sol and diff <= max_sol:
                            # Нашли исходящий
                            # Ищем получателя (у кого баланс вырос)
                            for j, (pre2, post2) in enumerate(zip(pre_balances, post_balances)):
                                if j == i:
                                    continue
                                received = (post2 - pre2) / 1e9
                                if abs(received - diff) < 0.01:  # примерно та же сумма
                                    to_wallet = account_keys[j]
                                    # Проверяем свежесть
                                    if await is_fresh_wallet(to_wallet):
                                        print(f"[FUNDING] {name} → {to_wallet} | {diff:.4f} SOL")
                                        fields = [
                                            {"name": "From", "value": f"**{name}**\n`{address}`", "inline": False},
                                            {"name": "To (Fresh Wallet)", "value": f"`{to_wallet}`", "inline": False},
                                            {"name": "Amount", "value": f"**{diff:.4f} SOL**", "inline": True},
                                            {"name": "Links", "value": (
                                                f"[From Solscan](https://solscan.io/account/{address}) • "
                                                f"[To Solscan](https://solscan.io/account/{to_wallet}) • "
                                                f"[Tx](https://solscan.io/tx/{sig})"
                                            ), "inline": False},
                                        ]
                                        await send_discord(
                                            DISCORD_WEBHOOK_FUNDING,
                                            f"💰 Fresh Funding • {name}",
                                            f"**{diff:.4f} SOL** ушло на полностью новый кошелёк",
                                            fields,
                                            0xf1c40f
                                        )
                                    break
                    last_sigs[address] = sig
                    break  # обработали одну новую

        except Exception as e:
            print(f"Funding error: {e}")
        await asyncio.sleep(18)

async def main():
    print("=" * 60)
    print("🚀 Full bot started")
    print("• Test Pump / Raydium / Early")
    print("• Funding Tracker (fresh wallets only)")
    print("=" * 60)
    await asyncio.gather(
        pump_monitor(),
        raydium_and_early(),
        funding_monitor()
    )

if __name__ == "__main__":
    asyncio.run(main())

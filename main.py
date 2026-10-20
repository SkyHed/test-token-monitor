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

# Основные программы
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
METEORA_DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"

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

async def send_discord(webhook: str, title: str, description: str, fields: list, color: int = 0x00ff00, buttons: list = None):
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": fields
    }
    payload = {"embeds": [embed]}
    if buttons:
        payload["components"] = [{"type": 1, "components": buttons}]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as resp:
                if resp.status not in (200, 204):
                    print(f"Discord error {resp.status}")
    except Exception as e:
        print(f"Discord error: {e}")

async def get_sol_balance(address: str) -> float:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=8) as resp:
                data = await resp.json()
                return data.get("result", {}).get("value", 0) / 1e9
    except:
        return 0.0

def make_buttons(mint: str, creator: str = None):
    buttons = [
        {"type": 2, "style": 5, "label": "Axiom", "url": f"https://axiom.trade/token/{mint}"},
        {"type": 2, "style": 5, "label": "Solscan", "url": f"https://solscan.io/token/{mint}"}
    ]
    if creator and creator != "—":
        buttons.append({"type": 2, "style": 5, "label": "Creator", "url": f"https://solscan.io/account/{creator}"})
    return buttons

# ================== PUMP.FUN ==================
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
                    if creator != "—":
                        bal = await get_sol_balance(creator)
                        if bal < 0.1:
                            continue
                    ts = data.get("timestamp") or data.get("created_timestamp")
                    if ts:
                        if ts > 1e12: ts = ts / 1000
                        sec = max(0, int(datetime.now(timezone.utc).timestamp() - ts))
                        time_str = f"{sec}s ago" if sec < 60 else f"{sec//60}m ago"
                    else:
                        time_str = "just now"
                    print(f"[PUMP] {symbol} | {time_str}")
                    fields = [
                        {"name": "Name", "value": f"**{name}**", "inline": True},
                        {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
                        {"name": "CA", "value": f"`{mint}`", "inline": False},
                        {"name": "Creator", "value": f"`{creator}`", "inline": False},
                    ]
                    await send_discord(
                        DISCORD_WEBHOOK_PUMP,
                        f"🧪 TEST — Pump.fun | **{symbol}**",
                        f"**{name}** • {time_str}",
                        fields, 0x00ff99, make_buttons(mint, creator)
                    )
        except Exception as e:
            print(f"Pump error: {e}")
            await asyncio.sleep(5)

# ================== ON-CHAIN RAYDIUM + METEORA ==================
async def get_recent_sigs(program_id: str, limit: int = 15):
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getSignaturesForAddress",
        "params": [program_id, {"limit": limit}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=12) as resp:
                data = await resp.json()
                return data.get("result") or []
    except:
        return []

async def process_new_pool(sig: str, program_name: str, seen: set):
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTransaction",
        "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=12) as resp:
                data = await resp.json()
                tx = data.get("result")
        if not tx or (tx.get("meta") or {}).get("err"):
            return

        # Ищем новые mint'ы в транзакции (упрощённо)
        meta = tx.get("meta") or {}
        post_token = meta.get("postTokenBalances") or []
        pre_token = {b.get("mint"): True for b in (meta.get("preTokenBalances") or [])}

        for bal in post_token:
            mint = bal.get("mint")
            if not mint or mint in seen or mint in pre_token:
                continue
            # Пропускаем известные (WSOL, USDC и т.д.)
            if mint in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]:
                continue

            # Пытаемся получить имя/символ через DexScreener (только для метаданных)
            name, symbol, liq = "Unknown", "???", 0
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=6) as r:
                        if r.status == 200:
                            pairs = (await r.json()).get("pairs") or []
                            if pairs:
                                p = pairs[0]
                                name = p.get("baseToken", {}).get("name") or name
                                symbol = p.get("baseToken", {}).get("symbol") or symbol
                                liq = float(p.get("liquidity", {}).get("usd") or 0)
            except:
                pass

            if is_test_token(name, symbol):
                # Отправляем в Test Raydium
                seen.add(mint)
                fields = [
                    {"name": "Name", "value": f"**{name}**", "inline": True},
                    {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
                    {"name": "CA", "value": f"`{mint}`", "inline": False},
                    {"name": "Program", "value": program_name, "inline": True},
                    {"name": "Liquidity", "value": f"**${liq:,.0f}**", "inline": True},
                ]
                await send_discord(DISCORD_WEBHOOK_RAYDIUM, f"🧪 TEST — {program_name} | **{symbol}**", f"**{name}**", fields, 0x0099ff, make_buttons(mint))
            elif liq >= 200:
                # Early
                seen.add(mint)
                fields = [
                    {"name": "Name", "value": f"**{name}**", "inline": True},
                    {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
                    {"name": "CA", "value": f"`{mint}`", "inline": False},
                    {"name": "Program", "value": program_name, "inline": True},
                    {"name": "Liquidity", "value": f"**${liq:,.0f}**", "inline": True},
                ]
                await send_discord(DISCORD_WEBHOOK_EARLY, f"🚀 EARLY | **{symbol}**", f"**{name}** • {program_name}", fields, 0xffaa00, make_buttons(mint))
                print(f"[EARLY] {symbol} | {mint} | ${liq:,.0f}")
    except Exception as e:
        print(f"Process pool error: {e}")

async def onchain_monitor():
    print("🔵 On-chain Raydium + Meteora monitor started")
    seen = set()
    last_sigs = {RAYDIUM_AMM_V4: None, RAYDIUM_CPMM: None, METEORA_DLMM: None}

    while True:
        try:
            for prog, name in [
                (RAYDIUM_AMM_V4, "Raydium AMM"),
                (RAYDIUM_CPMM, "Raydium CPMM"),
                (METEORA_DLMM, "Meteora")
            ]:
                sigs = await get_recent_sigs(prog, 12)
                for s in sigs:
                    sig = s.get("signature")
                    if not sig or last_sigs.get(prog) == sig:
                        continue
                    if last_sigs[prog] is None:
                        last_sigs[prog] = sig
                        break
                    await process_new_pool(sig, name, seen)
                    last_sigs[prog] = sig
                    break
        except Exception as e:
            print(f"On-chain error: {e}")
        await asyncio.sleep(14)

# ================== FUNDING ==================
async def is_fresh_wallet(address: str) -> bool:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress", "params": [address, {"limit": 2}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=10) as resp:
                data = await resp.json()
                return len(data.get("result") or []) <= 1
    except:
        return False

async def funding_monitor():
    print("💰 Funding Tracker started")
    last_sigs = {}
    while True:
        try:
            if not Path("watched_wallets.json").exists():
                await asyncio.sleep(30)
                continue
            watched = json.loads(Path("watched_wallets.json").read_text())
            for w in watched:
                name = w.get("name", "Unknown")
                address = w.get("address")
                min_sol = float(w.get("min_sol", 0.5))
                max_sol = float(w.get("max_sol", 50))
                if not address: continue
                payload = {"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress", "params": [address, {"limit": 5}]}
                async with aiohttp.ClientSession() as session:
                    async with session.post(SOLANA_RPC, json=payload, timeout=12) as resp:
                        sigs = (await resp.json()).get("result") or []
                for s in sigs:
                    sig = s.get("signature")
                    if not sig: continue
                    if address not in last_sigs:
                        last_sigs[address] = sig
                        break
                    if last_sigs[address] == sig: break
                    # Упрощённая проверка (полный парсинг можно расширить)
                    last_sigs[address] = sig
                    break
        except Exception as e:
            print(f"Funding error: {e}")
        await asyncio.sleep(20)

async def main():
    print("=" * 60)
    print("🚀 Bot started (On-chain version)")
    print("=" * 60)
    await asyncio.gather(
        pump_monitor(),
        onchain_monitor(),
        funding_monitor()
    )

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import re
import aiohttp
import websockets
from datetime import datetime, timezone
from pathlib import Path

# ================== НОВЫЕ ВЕБХУКИ ==================
DISCORD_WEBHOOK_PUMP = "https://discord.com/api/webhooks/1562822221616128010/vm7-P0NLrxdeIgJsZSbDqSIGtPXfD717_4W9ayd7K44vAhU82vbDvCTfN31tyxo2xhc9"
DISCORD_WEBHOOK_RAYDIUM = "https://discord.com/api/webhooks/1562822098219700246/G57YE4z4TH9JG0XJ3I4RkMaDanZ1U_eN-rYG6o9sPvxZOS434T49yC9q4NV8jSQecBy3"
DISCORD_WEBHOOK_EARLY = "https://discord.com/api/webhooks/1562822287395262504/XHtZLH23Vyqf_IQhiXpbG8JDBrLyRwGCVNIwYyZ-qXCSJaTyyULbCyvtCLpjpNtJlByM"
DISCORD_WEBHOOK_FUNDING = "https://discord.com/api/webhooks/1562822410217066577/wuw5h_QOenA_tJIsR5EN3fyNZ-A5LUSTULBjKbv5P89yX-vvuM2KRRPrEq44N8tNy-lw"

SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Программы
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
METEORA_DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
METEORA_DBC = "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN"
METEORA_DAMM_V2 = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"

TEST_KEYWORDS = [
    "test", "t e s t", "t.e.s.t", "testtoken", "testing", "testrun",
    "demo", "dummy", "sniper", "snipe", "s n i p e r",
    "sniperbot", "snipebot", "testcoin", "test token"
]

BLACKLIST_WORDS = ["fake", "mayhem"]

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

def has_blacklist_word(name: str, symbol: str) -> bool:
    n = normalize(name)
    s = normalize(symbol)
    for w in BLACKLIST_WORDS:
        if normalize(w) in n or normalize(w) in s:
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
                    print(f"Discord error {resp.status}: {await resp.text()}")
                else:
                    print(f"Discord OK ({resp.status})")
    except Exception as e:
        print(f"Discord send error: {e}")

async def get_sol_balance(address: str) -> float:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=8) as resp:
                data = await resp.json()
                return data.get("result", {}).get("value", 0) / 1e9
    except:
        return 0.0

async def get_creator_token_count(creator: str) -> int:
    if not creator or creator == "—":
        return 0
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [creator, {"limit": 40}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC, json=payload, timeout=10) as resp:
                data = await resp.json()
                return len(data.get("result") or [])
    except:
        return 0

def make_links(mint: str, creator: str = None) -> str:
    links = (
        f"**[Axiom](https://axiom.trade/token/{mint})**  •  "
        f"**[Solscan](https://solscan.io/token/{mint})**  •  "
        f"**[Birdeye](https://birdeye.so/token/{mint}?chain=solana)**  •  "
        f"**[GMGN](https://gmgn.ai/sol/token/{mint})**"
    )
    if creator and creator != "—":
        links += f"\n**Creator:** [Solscan](https://solscan.io/account/{creator})"
    return links

# ================== PUMP.FUN ==================
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
                    if has_blacklist_word(name, symbol):
                        print(f"[SKIP] {symbol} — blacklist")
                        continue

                    if creator and creator != "—":
                        bal = await get_sol_balance(creator)
                        if bal < 0.1:
                            print(f"[SKIP] {symbol} — only {bal:.3f} SOL")
                            continue
                        tok_count = await get_creator_token_count(creator)
                        if tok_count > 25:
                            print(f"[SKIP] {symbol} — creator ~{tok_count} txs")
                            continue

                    ts = data.get("timestamp") or data.get("created_timestamp")
                    if ts:
                        if ts > 1e12:
                            ts = ts / 1000
                        sec = max(0, int(datetime.now(timezone.utc).timestamp() - ts))
                        time_str = f"{sec}s ago" if sec < 60 else f"{sec // 60}m ago"
                    else:
                        time_str = "just now"

                    print(f"[PUMP TEST] {symbol} | {time_str}")

                    fields = [
                        {"name": "Name", "value": f"**{name or '—'}**", "inline": True},
                        {"name": "Symbol", "value": f"**{symbol or '—'}**", "inline": True},
                        {"name": "CA", "value": f"`{mint}`", "inline": False},
                        {"name": "Creator", "value": f"`{creator}`", "inline": False},
                        {"name": "Links", "value": make_links(mint, creator), "inline": False},
                    ]

                    await send_discord(
                        DISCORD_WEBHOOK_PUMP,
                        f"🧪 TEST — Pump.fun | **{symbol}**",
                        f"**{name}** • {time_str}",
                        fields,
                        0x00ff99
                    )
        except Exception as e:
            print(f"Pump error: {e}")
            await asyncio.sleep(5)

# ================== ON-CHAIN ==================
async def get_recent_sigs(program_id: str, limit: int = 10):
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

        meta = tx.get("meta") or {}
        post_token = meta.get("postTokenBalances") or []
        pre_mints = {b.get("mint") for b in (meta.get("preTokenBalances") or [])}

        for bal in post_token:
            mint = bal.get("mint")
            if not mint or mint in seen or mint in pre_mints:
                continue
            if mint in ["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]:
                continue

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

            if has_blacklist_word(name, symbol):
                continue

            if is_test_token(name, symbol):
                seen.add(mint)
                fields = [
                    {"name": "Name", "value": f"**{name}**", "inline": True},
                    {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
                    {"name": "CA", "value": f"`{mint}`", "inline": False},
                    {"name": "Program", "value": program_name, "inline": True},
                    {"name": "Liquidity", "value": f"**${liq:,.0f}**", "inline": True},
                    {"name": "Links", "value": make_links(mint), "inline": False},
                ]
                await send_discord(
                    DISCORD_WEBHOOK_RAYDIUM,
                    f"🧪 TEST — {program_name} | **{symbol}**",
                    f"**{name}**",
                    fields,
                    0x0099ff
                )
            elif liq >= 150:
                seen.add(mint)
                fields = [
                    {"name": "Name", "value": f"**{name}**", "inline": True},
                    {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
                    {"name": "CA", "value": f"`{mint}`", "inline": False},
                    {"name": "Program", "value": program_name, "inline": True},
                    {"name": "Liquidity", "value": f"**${liq:,.0f}**", "inline": True},
                    {"name": "Links", "value": make_links(mint), "inline": False},
                ]
                await send_discord(
                    DISCORD_WEBHOOK_EARLY,
                    f"🚀 EARLY | **{symbol}**",
                    f"**{name}** • {program_name}",
                    fields,
                    0xffaa00
                )
                print(f"[EARLY] {symbol} | ${liq:,.0f} | {program_name}")
    except Exception as e:
        print(f"Process error: {e}")

async def onchain_monitor():
    print("🔵 On-chain monitor started (Raydium + Meteora DLMM + DBC + DAMM v2)")
    seen = set()
    programs = [
        (RAYDIUM_AMM_V4, "Raydium AMM"),
        (RAYDIUM_CPMM, "Raydium CPMM"),
        (METEORA_DLMM, "Meteora DLMM"),
        (METEORA_DBC, "Meteora DBC"),
        (METEORA_DAMM_V2, "Meteora DAMM v2"),
    ]
    last_sigs = {p[0]: None for p in programs}

    while True:
        try:
            for prog, name in programs:
                sigs = await get_recent_sigs(prog, 8)
                for s in sigs:
                    sig = s.get("signature")
                    if not sig:
                        continue
                    if last_sigs[prog] is None:
                        last_sigs[prog] = sig
                        break
                    if last_sigs[prog] == sig:
                        break
                    await process_new_pool(sig, name, seen)
                    last_sigs[prog] = sig
                    break
        except Exception as e:
            print(f"On-chain error: {e}")
        await asyncio.sleep(12)

# ================== FUNDING ==================
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
                address = w.get("address")
                if not address:
                    continue
                payload = {
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [address, {"limit": 5}]
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(SOLANA_RPC, json=payload, timeout=12) as resp:
                        sigs = (await resp.json()).get("result") or []
                for s in sigs:
                    sig = s.get("signature")
                    if not sig:
                        continue
                    if address not in last_sigs:
                        last_sigs[address] = sig
                        break
                    if last_sigs[address] == sig:
                        break
                    last_sigs[address] = sig
                    break
        except Exception as e:
            print(f"Funding error: {e}")
        await asyncio.sleep(20)

async def main():
    print("=" * 60)
    print("🚀 Bot started with NEW webhooks")
    print("• PUMP TEST")
    print("• RADIUM TEST")
    print("• RADIUM PROJECT (Early)")
    print("• CEX Funding")
    print("=" * 60)
    await asyncio.gather(
        pump_monitor(),
        onchain_monitor(),
        funding_monitor()
    )

if __name__ == "__main__":
    asyncio.run(main())

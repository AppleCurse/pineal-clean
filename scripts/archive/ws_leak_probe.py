"""
ws_leak_probe.py — WS oda izolasyonu için CANLI (gerçek uvicorn) sızıntı ölçümü.

Mantık (tautoloji olmaması için):
  * N oda, her odada M gerçek WebSocket istemcisi (ayrı TCP bağlantıları).
  * Her odaya, YALNIZ o odaya ait benzersiz bir sır içeren log yayını tetiklenir
    (/api/override tag alanı -> broadcast_log(client_id, ...) -> _room_sender -> _send_ws).
  * Her istemcinin aldığı tüm mesajlarda TÜM odaların sırları aranır.
  * leak = "başka odanın sırrını gören" istemci-mesaj çifti sayısı.
  * Ayrıca "own_hits" ölçülür: kendi odasının sırrını GÖRMEYEN istemci varsa
    test geçersizdir (yayın hiç çalışmadıysa sızıntı 0 çıkması anlamsızdır).

Kullanım:
  PINEAL_TOKEN=... python scripts/ws_leak_probe.py --base http://127.0.0.1:8765 --rooms 4 --clients 3
Çıkış kodu 0 = izole (leak==0 VE her istemci kendi sırrını aldı), 1 = ihlal/geçersiz.
"""
import argparse
import asyncio
import json
import os
import sys
import uuid

import httpx
import websockets


async def ws_client(ws_url: str, token: str, inbox: list, ready: asyncio.Event, stop: asyncio.Event):
    async with websockets.connect(ws_url) as ws:
        if token:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            first = json.loads(await ws.recv())
            assert first.get("type") == "auth_ok", first
        ready.set()
        while not stop.is_set():
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.25)
                inbox.append(msg)
            except asyncio.TimeoutError:
                continue


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--rooms", type=int, default=4)
    ap.add_argument("--clients", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()
    token = os.environ.get("PINEAL_TOKEN", "")
    ws_base = args.base.replace("http://", "ws://").replace("https://", "wss://")

    run = uuid.uuid4().hex[:6]
    room_ids = [f"probe{run}r{i}" for i in range(args.rooms)]
    # Sır, yayına yansıyan `tag` alanında taşınır (log: "... mühürlendi [tag]"); tag<=64 ch.
    secrets = {rid: f"S{rid}-{uuid.uuid4().hex[:24]}" for rid in room_ids}

    inboxes: dict[tuple[str, int], list] = {}
    stop = asyncio.Event()
    tasks = []
    readies = []
    for rid in room_ids:
        for c in range(args.clients):
            inbox: list = []
            inboxes[(rid, c)] = inbox
            ready = asyncio.Event()
            readies.append(ready)
            tasks.append(asyncio.create_task(ws_client(f"{ws_base}/ws/{rid}", token, inbox, ready, stop)))
    await asyncio.wait_for(asyncio.gather(*(r.wait() for r in readies)), timeout=10)

    headers = {"x-api-key": token} if token else {}
    async with httpx.AsyncClient(base_url=args.base, headers=headers, timeout=10) as http:
        for rnd in range(args.rounds):
            # Tüm odalara EŞZAMANLI yayın tetikle: karışma olasılığını maksimize et.
            await asyncio.gather(*(
                http.post("/api/override", json={"client_id": rid, "fact": f"probe round {rnd}", "tag": secrets[rid]})
                for rid in room_ids
            ))
    await asyncio.sleep(1.5)
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)

    leak = 0
    own_missing = 0
    total_msgs = 0
    for (rid, c), inbox in inboxes.items():
        total_msgs += len(inbox)
        own_seen = any(secrets[rid] in m for m in inbox)
        if not own_seen:
            own_missing += 1
        for m in inbox:
            for other, sec in secrets.items():
                if other != rid and sec in m:
                    leak += 1
                    print(f"LEAK: room={rid} client={c} received secret of {other}: {m[:120]}")
    print(json.dumps({
        "rooms": args.rooms, "clients_per_room": args.clients, "rounds": args.rounds,
        "total_messages_received": total_msgs,
        "cross_room_leaks": leak,
        "clients_missing_own_secret": own_missing,
        "verdict": "ISOLATED" if (leak == 0 and own_missing == 0) else "VIOLATION_OR_INVALID",
    }, indent=2))
    return 0 if (leak == 0 and own_missing == 0) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

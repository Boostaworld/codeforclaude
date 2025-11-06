import json
import asyncio
import random
from pathlib import Path
from datetime import datetime
import discord

@nightyScript(
    name="Blox Fruits Trader",
    author="Grok",
    description="Auto-send trades to Blox Fruits channels",
    version="3.2"
)
def blox_fruits_trader():
    BASE_DIR = Path(getScriptsPath()) / "json"
    DATA_FILE = BASE_DIR / "blox_trader.json"
    EMOJI_CACHE_FILE = BASE_DIR / "guild_emojis.json"
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    DEFAULT_DATA = {
        "trade_channels": [],
        "trade_offers": [],
        "trade_requests": []
    }

    FRUIT_ALIASES = {
        "leopard": ["tiger"], "rumble": ["lightning"], "spirit": ["soul"],
        "t-rex": ["trex", "rex"], "control": ["kage"], "dough": ["doughnut"],
        "buddha": ["budha"], "phoenix": ["phenix", "pheonix"]
    }

    class AutoState:
        running = False
        task = None

    def load_data():
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for k, v in DEFAULT_DATA.items():
                    if k not in data:
                        data[k] = v
                return data
        except:
            return DEFAULT_DATA.copy()

    def save_data(data):
        try:
            tmp = DATA_FILE.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(data, f, indent=4)
            tmp.replace(DATA_FILE)
        except:
            pass

    def load_emoji_cache():
        try:
            with open(EMOJI_CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_emoji_cache(cache):
        try:
            with open(EMOJI_CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=4)
        except:
            pass

    def get_cooldown_remaining(last_sent, cooldown):
        if not last_sent:
            return 0
        try:
            last = datetime.fromisoformat(last_sent)
            elapsed = (datetime.now() - last).total_seconds()
            return max(0, int(cooldown - elapsed))
        except:
            return 0

    data = load_data()
    emoji_cache = load_emoji_cache()

    # UI
    tab = Tab(name='BF Trader', title="Blox Fruits Trader", icon="convert")
    main = tab.create_container(type="rows")
    card = main.create_card(height="full", width="full", gap=3)

    # Inputs
    top = card.create_group(type="columns", gap=3, full_width=True)
    srv_in = top.create_ui_element(UI.Input, label="Server ID", full_width=True, show_clear_button=True)
    ch_in = top.create_ui_element(UI.Input, label="Channel IDs", full_width=True, show_clear_button=True)
    cd_in = top.create_ui_element(UI.Input, label="Cooldown", value="60", full_width=True)
    add_btn = top.create_ui_element(UI.Button, label='Add', disabled=True, color="primary")
    det_btn = top.create_ui_element(UI.Button, label='Detect', color="default")

    # Trade
    trade = card.create_group(type="columns", gap=3, full_width=True)
    off_in = trade.create_ui_element(UI.Input, label="Offering", placeholder="dough, spirit, OR, trex", full_width=True, show_clear_button=True)
    req_in = trade.create_ui_element(UI.Input, label="Requesting", placeholder="rumble, tiger", full_width=True, show_clear_button=True)
    save_btn = trade.create_ui_element(UI.Button, label='Save', disabled=True, color="primary")

    # Controls
    ctrl = card.create_group(type="columns", gap=3, full_width=True)
    send_all_btn = ctrl.create_ui_element(UI.Button, label='Send to All', disabled=True, color="success")
    auto_check = ctrl.create_ui_element(UI.Checkbox, label='Auto Send', value=False)

    # Tables
    tables = card.create_group(type="columns", gap=6, full_width=True)
    
    ch_table = tables.create_ui_element(
        UI.Table, selectable=False, search=True, items_per_page=10,
        columns=[
            {"type": "text", "label": "Channel"},
            {"type": "text", "label": "Cooldown"},
            {"type": "text", "label": "Status"},
            {"type": "button", "label": "Actions", "buttons": [
                {"label": "Send Now", "color": "success", "onClick": lambda row_id: sendNowToChannel(row_id)},
                {"label": "Remove", "color": "danger", "onClick": lambda row_id: removeChannel(row_id)}
            ]}
        ], rows=[]
    )

    tr_table = tables.create_ui_element(
        UI.Table, selectable=False, search=False, items_per_page=5,
        columns=[{"type": "text", "label": "Trade"}], rows=[]
    )

    # Functions
    async def sendNowToChannel(cid):
        try:
            d = load_data()
            
            if not d["trade_offers"] or not d["trade_requests"]:
                print("Configure trade first", type_="WARNING")
                return
            
            # Find the channel
            channel = None
            for tc in d["trade_channels"]:
                if tc["id"] == cid:
                    channel = tc
                    break
            
            if not channel:
                print("Channel not found", type_="ERROR")
                return
            
            # Send message
            msg = await build_msg(channel["server_id"], d["trade_offers"], d["trade_requests"], channel.get("trade_emoji"))
            ok, err = await send_to(channel["id"], msg)
            
            if ok:
                channel["last_sent"] = datetime.now().isoformat()
                save_data(d)
                print(f"✓ Sent to {channel['channel_name']}", type_="SUCCESS")
                
                # Update table row
                rem = get_cooldown_remaining(channel.get("last_sent"), channel.get("cooldown", 60))
                st = f"CD: {rem}s" if rem > 0 else "Ready"
                
                ch_table.update_rows([{
                    "id": cid,
                    "cells": [
                        {"text": channel.get("channel_name", "?"), "imageUrl": channel.get("server_icon", ""), "subtext": channel.get("server_name", "")},
                        {"text": f"{channel.get('cooldown', 60)}s", "subtext": st},
                        {"text": st, "subtext": channel.get("last_sent", "Never")[:19]},
                        {}
                    ]
                }])
            else:
                print(f"✗ {channel['channel_name']}: {err}", type_="ERROR")
                
        except Exception as e:
            print(f"Send error: {e}", type_="ERROR")
    
    def removeChannel(cid):
        try:
            d = load_data()
            d["trade_channels"] = [tc for tc in d["trade_channels"] if tc["id"] != cid]
            save_data(d)
            ch_table.delete_rows([cid])
            print(f"Removed channel {cid}", type_="SUCCESS")
        except Exception as e:
            print(f"Remove error: {e}", type_="ERROR")

    async def find_trade_emoji(guild):
        try:
            for e in guild.emojis:
                if any(t in e.name.lower() for t in ["point_trade", "trade", "offer"]):
                    return f"<:{e.name}:{e.id}>" if not e.animated else f"<a:{e.name}:{e.id}>"
            return "↔️"
        except:
            return "↔️"

    async def find_or_emoji(guild):
        try:
            for e in guild.emojis:
                n = e.name.lower()
                if n in ["or", "swap"] or n.startswith("or_") or n.endswith("_or"):
                    return f"<:{e.name}:{e.id}>" if not e.animated else f"<a:{e.name}:{e.id}>"
            return "🔁"
        except:
            return "🔁"

    async def fetch_emoji(gid, term):
        if term.lower() == "or":
            g = bot.get_guild(int(gid))
            return await find_or_emoji(g) if g else "🔁"
        
        gs = str(gid)
        tl = term.lower().strip()
        
        if gs in emoji_cache and tl in emoji_cache[gs]:
            return emoji_cache[gs][tl]
        
        try:
            g = bot.get_guild(int(gid))
            if not g:
                return None
            
            for e in g.emojis:
                if tl in e.name.lower():
                    es = f"<:{e.name}:{e.id}>" if not e.animated else f"<a:{e.name}:{e.id}>"
                    if gs not in emoji_cache:
                        emoji_cache[gs] = {}
                    emoji_cache[gs][tl] = es
                    save_emoji_cache(emoji_cache)
                    return es
            
            if tl in FRUIT_ALIASES:
                for alias in FRUIT_ALIASES[tl]:
                    for e in g.emojis:
                        if alias in e.name.lower():
                            es = f"<:{e.name}:{e.id}>" if not e.animated else f"<a:{e.name}:{e.id}>"
                            if gs not in emoji_cache:
                                emoji_cache[gs] = {}
                            emoji_cache[gs][tl] = es
                            save_emoji_cache(emoji_cache)
                            return es
            return None
        except:
            return None

    async def build_msg(gid, offers, requests, te=None):
        g = bot.get_guild(int(gid))
        if not te:
            te = await find_trade_emoji(g) if g else "↔️"
        
        oe = []
        for o in offers:
            e = await fetch_emoji(gid, o.strip())
            oe.append(e if e else f"`{o.strip()}`")
        
        re = []
        for r in requests:
            e = await fetch_emoji(gid, r.strip())
            re.append(e if e else f"`{r.strip()}`")
        
        return f"{' '.join(oe)} {te} {' '.join(re)}"

    async def send_to(cid, msg):
        try:
            ch = bot.get_channel(int(cid))
            if not ch:
                return False, "Not found"
            await ch.send(msg)
            return True, "OK"
        except discord.errors.Forbidden:
            return False, "No perm"
        except:
            return False, "Error"

    async def detect():
        det_btn.loading = True
        try:
            d = load_data()
            added = 0
            kw = ["trading", "slow-trading", "fast-trading", "trade-chat", "trades"]
            ex = ["pvb", "sab"]
            
            for g in bot.guilds:
                for ch in g.text_channels:
                    n = ch.name.lower()
                    if any(k in n for k in kw) and not any(n.startswith(e) for e in ex):
                        cid = str(ch.id)
                        if any(tc["id"] == cid for tc in d["trade_channels"]):
                            continue
                        
                        d["trade_channels"].append({
                            "id": cid,
                            "server_id": str(g.id),
                            "server_name": g.name,
                            "server_icon": str(g.icon.url) if g.icon else "",
                            "channel_name": ch.name,
                            "cooldown": 60,
                            "last_sent": None,
                            "trade_emoji": await find_trade_emoji(g)
                        })
                        
                        ch_table.insert_rows([{
                            "id": cid,
                            "cells": [
                                {"text": ch.name, "imageUrl": str(g.icon.url) if g.icon else "", "subtext": g.name},
                                {"text": "60s", "subtext": "Ready"},
                                {"text": "Ready", "subtext": "Auto"},
                                {}
                            ]
                        }])
                        added += 1
            
            save_data(d)
            print(f"Detected {added} channels", type_="SUCCESS")
        except Exception as e:
            print(f"Detect failed: {e}", type_="ERROR")
        finally:
            det_btn.loading = False

    async def add():
        add_btn.loading = True
        sid = srv_in.value.strip()
        cids = ch_in.value.strip()
        cd = int(cd_in.value) if cd_in.value.isdigit() else 60
        
        if not sid or not cids:
            print("Need Server ID and Channel IDs", type_="WARNING")
            add_btn.loading = False
            return
        
        try:
            g = bot.get_guild(int(sid))
            if not g:
                print("Server not found", type_="ERROR")
                add_btn.loading = False
                return
            
            d = load_data()
            for cid in [c.strip() for c in cids.split(",")]:
                ch = bot.get_channel(int(cid))
                if not ch or any(tc["id"] == cid for tc in d["trade_channels"]):
                    continue
                
                d["trade_channels"].append({
                    "id": cid,
                    "server_id": sid,
                    "server_name": g.name,
                    "server_icon": str(g.icon.url) if g.icon else "",
                    "channel_name": ch.name,
                    "cooldown": cd,
                    "last_sent": None,
                    "trade_emoji": await find_trade_emoji(g)
                })
                
                ch_table.insert_rows([{
                    "id": cid,
                    "cells": [
                        {"text": ch.name, "imageUrl": str(g.icon.url) if g.icon else "", "subtext": g.name},
                        {"text": f"{cd}s", "subtext": "Ready"},
                        {"text": "Ready", "subtext": "Never"},
                        {}
                    ]
                }])
            
            save_data(d)
            print(f"Added channels", type_="SUCCESS")
            srv_in.value = ""
            ch_in.value = ""
            add_btn.disabled = True
        except Exception as e:
            print(f"Add failed: {e}", type_="ERROR")
        finally:
            add_btn.loading = False

    def save_trade():
        save_btn.loading = True
        d = load_data()
        
        offers = [o.strip() for o in off_in.value.split(",") if o.strip()]
        requests = [r.strip() for r in req_in.value.split(",") if r.strip()]
        
        d["trade_offers"] = offers
        d["trade_requests"] = requests
        save_data(d)
        
        ex = [r["id"] for r in tr_table.rows]
        if ex:
            tr_table.delete_rows(ex)
        
        if offers:
            tr_table.insert_rows([{"id": "o", "cells": [{"text": f"Offering: {', '.join(offers)}"}]}])
        if requests:
            tr_table.insert_rows([{"id": "r", "cells": [{"text": f"Requesting: {', '.join(requests)}"}]}])
        
        print(f"Saved: {len(offers)} offers, {len(requests)} requests", type_="SUCCESS")
        
        save_btn.loading = False
        send_all_btn.disabled = False

    async def send_to_all():
        send_all_btn.loading = True
        send_all_btn.disabled = True
        d = load_data()
        
        if not d["trade_offers"] or not d["trade_requests"]:
            print("Configure trade first", type_="WARNING")
            send_all_btn.loading = False
            send_all_btn.disabled = False
            return
        
        if not d["trade_channels"]:
            print("Add channels first", type_="WARNING")
            send_all_btn.loading = False
            send_all_btn.disabled = False
            return
        
        sent = skip = fail = 0
        
        for c in d["trade_channels"]:
            try:
                rem = get_cooldown_remaining(c.get("last_sent"), c["cooldown"])
                if rem > 0:
                    skip += 1
                    continue
                
                msg = await build_msg(c["server_id"], d["trade_offers"], d["trade_requests"], c.get("trade_emoji"))
                ok, err = await send_to(c["id"], msg)
                
                if ok:
                    sent += 1
                    c["last_sent"] = datetime.now().isoformat()
                    print(f"✓ {c['channel_name']}", type_="SUCCESS")
                else:
                    fail += 1
                    print(f"✗ {c['channel_name']}: {err}", type_="ERROR")
                
                await asyncio.sleep(random.uniform(2, 4))
            except:
                fail += 1
        
        save_data(d)
        print(f"Done: {sent} sent, {skip} skipped, {fail} failed", type_="INFO")
        send_all_btn.loading = False
        send_all_btn.disabled = False

    async def auto_loop():
        print("Auto send started", type_="SUCCESS")
        
        while AutoState.running:
            try:
                d = load_data()
                
                if not d["trade_offers"] or not d["trade_requests"] or not d["trade_channels"]:
                    await asyncio.sleep(2)
                    continue
                
                # Find the channel with the shortest time until next send
                min_wait = float('inf')
                
                for c in d["trade_channels"]:
                    if not AutoState.running:
                        break
                    
                    rem = get_cooldown_remaining(c.get("last_sent"), c["cooldown"])
                    
                    # Track minimum wait time
                    if rem < min_wait:
                        min_wait = rem
                    
                    # If ready, send immediately
                    if rem <= 0:
                        try:
                            msg = await build_msg(c["server_id"], d["trade_offers"], d["trade_requests"], c.get("trade_emoji"))
                            ok, err = await send_to(c["id"], msg)
                            
                            if ok:
                                c["last_sent"] = datetime.now().isoformat()
                                print(f"✓ Auto: {c['channel_name']}", type_="SUCCESS")
                            
                            await asyncio.sleep(random.uniform(2, 4))
                        except:
                            pass
                
                save_data(d)
                
                # Sleep until the next channel is ready (minimum 1 second)
                wait_time = max(1, min_wait if min_wait != float('inf') else 5)
                await asyncio.sleep(wait_time)
                
            except:
                await asyncio.sleep(5)
        
        print("Auto send stopped", type_="INFO")

    def toggle_auto(checked):
        if checked:
            if not data.get("trade_offers") or not data.get("trade_requests"):
                print("Configure trade first", type_="WARNING")
                auto_check.value = False
                return
            
            if not data.get("trade_channels"):
                print("Add channels first", type_="WARNING")
                auto_check.value = False
                return
            
            AutoState.running = True
            send_all_btn.disabled = True
            AutoState.task = bot.loop.create_task(auto_loop())
        else:
            AutoState.running = False
            if AutoState.task:
                AutoState.task.cancel()
            send_all_btn.disabled = False

    # Events
    srv_in.onInput = lambda v: setattr(add_btn, 'disabled', not (v and ch_in.value and v.isdigit() and len(v) >= 17))
    ch_in.onInput = lambda v: setattr(add_btn, 'disabled', not (v and srv_in.value and srv_in.value.isdigit()))
    off_in.onInput = lambda v: setattr(save_btn, 'disabled', not (v and req_in.value))
    req_in.onInput = lambda v: setattr(save_btn, 'disabled', not (v and off_in.value))
    
    add_btn.onClick = add
    det_btn.onClick = detect
    save_btn.onClick = save_trade
    send_all_btn.onClick = send_to_all
    auto_check.onChange = toggle_auto

    # Init
    async def init():
        d = load_data()
        
        for c in d["trade_channels"]:
            try:
                rem = get_cooldown_remaining(c.get("last_sent"), c.get("cooldown", 60))
                st = f"CD: {rem}s" if rem > 0 else "Ready"
                
                ch_table.insert_rows([{
                    "id": c["id"],
                    "cells": [
                        {"text": c.get("channel_name", "?"), "imageUrl": c.get("server_icon", ""), "subtext": c.get("server_name", "")},
                        {"text": f"{c.get('cooldown', 60)}s", "subtext": st},
                        {"text": st, "subtext": c.get("last_sent", "Never")[:19]},
                        {}
                    ]
                }])
            except:
                pass
        
        if d.get("trade_offers") and d.get("trade_requests"):
            off_in.value = ", ".join(d["trade_offers"])
            req_in.value = ", ".join(d["trade_requests"])
            
            tr_table.insert_rows([{"id": "o", "cells": [{"text": f"Offering: {', '.join(d['trade_offers'])}"}]}])
            tr_table.insert_rows([{"id": "r", "cells": [{"text": f"Requesting: {', '.join(d['trade_requests'])}"}]}])
            
            send_all_btn.disabled = False
        
        print(f"Loaded {len(d['trade_channels'])} channels", type_="SUCCESS")

    bot.loop.create_task(init())
    tab.render()

blox_fruits_trader()
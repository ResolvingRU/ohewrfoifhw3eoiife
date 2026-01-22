from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import json
from datetime import datetime
from typing import Dict, Set
import os

app = FastAPI()

# CORS для Telegram
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Игровое состояние
class GameState:
    def __init__(self):
        self.players: Dict[str, dict] = {}
        self.connections: Set[WebSocket] = set()
        self.is_spinning = False
        self.selected_pair = None
        self.last_spin = None
        self.cooldown = 5

    def add_player(self, user_id: str, name: str, ws: WebSocket):
        self.players[user_id] = {
            "id": user_id,
            "name": name,
            "ws": ws,
            "kisses": 0,
            "rejects": 0
        }
        self.connections.add(ws)

    def remove_player(self, ws: WebSocket):
        self.connections.discard(ws)
        to_remove = None
        for uid, data in self.players.items():
            if data["ws"] == ws:
                to_remove = uid
                break
        if to_remove:
            del self.players[to_remove]

    def can_spin(self) -> bool:
        if self.is_spinning or len(self.players) < 2:
            return False
        if self.last_spin:
            elapsed = (datetime.now() - self.last_spin).total_seconds()
            return elapsed >= self.cooldown
        return True

    def get_players_list(self):
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "kisses": p["kisses"],
                "rejects": p["rejects"]
            }
            for p in self.players.values()
        ]


game = GameState()


async def broadcast(msg: dict):
    """Отправка всем"""
    dead = set()
    for ws in game.connections:
        try:
            await ws.send_json(msg)
        except:
            dead.add(ws)
    for ws in dead:
        game.remove_player(ws)


# HTML страница (Mini App)
HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Бутылочка 💋</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            color: white;
        }
        .container { width: 100%; max-width: 500px; padding: 20px; }
        .game-circle {
            position: relative;
            width: 100%;
            aspect-ratio: 1;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .bottle {
            position: absolute;
            top: 50%; left: 50%;
            width: 50%; height: 6px;
            background: linear-gradient(90deg, transparent, #fff, transparent);
            transform-origin: 0% 50%;
            margin-left: 0;
            margin-top: -3px;
            filter: drop-shadow(0 0 10px rgba(255,255,255,0.8));
            transition: transform 0.1s;
        }
        .bottle.spin { animation: rotate 3s cubic-bezier(0.25,0.46,0.45,0.94); }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(1800deg); }
        }
        .players {
            position: absolute;
            width: 100%; height: 100%;
            top: 0; left: 0;
        }
        .player {
            position: absolute;
            width: 50px; height: 50px;
            background: rgba(255,255,255,0.9);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }
        .player.glow {
            background: linear-gradient(135deg, #f093fb, #f5576c);
            transform: scale(1.4);
            box-shadow: 0 0 30px rgba(245,87,108,0.8);
        }
        .controls {
            text-align: center;
            margin-top: 30px;
        }
        .btn-spin {
            padding: 15px 40px;
            font-size: 18px;
            background: linear-gradient(135deg, #f093fb, #f5576c);
            border: none;
            border-radius: 50px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(245,87,108,0.4);
            transition: all 0.3s;
        }
        .btn-spin:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(245,87,108,0.6);
        }
        .btn-spin:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .status {
            margin-top: 15px;
            font-size: 14px;
            color: rgba(255,255,255,0.8);
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.85);
            align-items: center;
            justify-content: center;
            z-index: 999;
        }
        .modal.show { display: flex; }
        .modal-box {
            background: white;
            padding: 30px;
            border-radius: 20px;
            text-align: center;
            color: #333;
            max-width: 90%;
        }
        .modal-box h2 { margin-bottom: 20px; }
        .modal-players {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
            font-size: 40px;
        }
        .modal-btns {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 20px;
        }
        .modal-btn {
            padding: 12px 30px;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-kiss {
            background: linear-gradient(135deg, #f093fb, #f5576c);
            color: white;
        }
        .btn-no {
            background: #ddd;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="game-circle">
            <div class="players" id="players"></div>
            <div class="bottle" id="bottle"></div>
        </div>
        <div class="controls">
            <button class="btn-spin" id="spinBtn" disabled>Крутить 🍾</button>
            <div class="status" id="status">Подключение...</div>
        </div>
    </div>

    <div class="modal" id="modal">
        <div class="modal-box">
            <h2>Бутылочка выбрала вас! 💋</h2>
            <div class="modal-players" id="modalPlayers"></div>
            <p>Хотите поцеловаться?</p>
            <div class="modal-btns">
                <button class="modal-btn btn-kiss" onclick="answer('kiss')">💋 Да</button>
                <button class="modal-btn btn-no" onclick="answer('reject')">🚫 Нет</button>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.enableClosingConfirmation();

        const user = tg.initDataUnsafe?.user || {
            id: Date.now(),
            first_name: 'Player'
        };

        let ws;
        let myId = user.id.toString();

        function connect() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${location.host}/ws`);

            ws.onopen = () => {
                ws.send(JSON.stringify({
                    user_id: myId,
                    name: user.first_name
                }));
            };

            ws.onmessage = (e) => {
                const msg = JSON.parse(e.data);

                if (msg.type === 'init') {
                    drawPlayers(msg.players);
                    updateBtn(msg.can_spin);
                    setStatus('Готово ✓');
                }
                else if (msg.type === 'player_joined' || msg.type === 'player_left') {
                    drawPlayers(msg.players);
                }
                else if (msg.type === 'spin_start') {
                    document.getElementById('bottle').classList.add('spin');
                    document.getElementById('spinBtn').disabled = true;
                    setStatus('Крутим...');
                }
                else if (msg.type === 'spin_result') {
                    setTimeout(() => {
                        document.getElementById('bottle').classList.remove('spin');
                        highlight(msg.players);
                        if (msg.players.some(p => p.id === myId)) {
                            showModal(msg.players);
                        }
                    }, 3000);
                }
                else if (msg.type === 'kiss_accepted') {
                    hideModal();
                    setStatus('💋 Поцелуй!');
                    clearGlow();
                    drawPlayers(msg.stats);
                }
                else if (msg.type === 'kiss_rejected') {
                    hideModal();
                    setStatus('🚫 Отказ...');
                    clearGlow();
                    drawPlayers(msg.stats);
                }
                else if (msg.type === 'ready_to_spin') {
                    updateBtn(true);
                    setStatus('Готово крутить!');
                }
            };

            ws.onerror = () => setStatus('Ошибка');
            ws.onclose = () => {
                setStatus('Отключено');
                setTimeout(connect, 3000);
            };
        }

        function drawPlayers(players) {
            const container = document.getElementById('players');
            container.innerHTML = '';
            const r = container.offsetWidth / 2 - 35;
            const step = (2 * Math.PI) / players.length;

            players.forEach((p, i) => {
                const angle = i * step - Math.PI/2;
                const x = r + r * Math.cos(angle);
                const y = r + r * Math.sin(angle);

                const div = document.createElement('div');
                div.className = 'player';
                div.id = 'p-' + p.id;
                div.style.left = x + 'px';
                div.style.top = y + 'px';
                div.textContent = p.name[0].toUpperCase();
                container.appendChild(div);
            });

            updateBtn(players.length >= 2);
        }

        function highlight(players) {
            players.forEach(p => {
                const el = document.getElementById('p-' + p.id);
                if (el) el.classList.add('glow');
            });
        }

        function clearGlow() {
            document.querySelectorAll('.player.glow').forEach(el => {
                el.classList.remove('glow');
            });
        }

        function showModal(players) {
            document.getElementById('modalPlayers').innerHTML = 
                players.map(p => p.name[0].toUpperCase()).join(' 💋 ');
            document.getElementById('modal').classList.add('show');
        }

        function hideModal() {
            document.getElementById('modal').classList.remove('show');
        }

        function updateBtn(can) {
            document.getElementById('spinBtn').disabled = !can;
        }

        function setStatus(text) {
            document.getElementById('status').textContent = text;
        }

        function answer(type) {
            ws.send(JSON.stringify({ action: 'answer', answer: type }));
        }

        document.getElementById('spinBtn').onclick = () => {
            ws.send(JSON.stringify({ action: 'spin' }));
        };

        connect();
    </script>
</body>
</html>"""


@app.get("/")
async def root():
    return HTMLResponse(HTML)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    try:
        # Авторизация
        auth = await ws.receive_json()
        user_id = auth.get("user_id", str(random.randint(1000, 9999)))
        name = auth.get("name", "Player")

        game.add_player(user_id, name, ws)

        # Отправка начального состояния
        await ws.send_json({
            "type": "init",
            "players": game.get_players_list(),
            "can_spin": game.can_spin()
        })

        # Уведомление всех
        await broadcast({
            "type": "player_joined",
            "players": game.get_players_list()
        })

        # Обработка команд
        while True:
            data = await ws.receive_json()
            action = data.get("action")

            if action == "spin" and game.can_spin():
                game.is_spinning = True
                game.last_spin = datetime.now()

                await broadcast({"type": "spin_start"})
                await asyncio.sleep(3)

                ids = list(game.players.keys())
                if len(ids) >= 2:
                    pair = random.sample(ids, 2)
                    game.selected_pair = pair

                    await broadcast({
                        "type": "spin_result",
                        "players": [
                            {"id": pair[0], "name": game.players[pair[0]]["name"]},
                            {"id": pair[1], "name": game.players[pair[1]]["name"]}
                        ]
                    })

                game.is_spinning = False

            elif action == "answer" and game.selected_pair:
                ans = data.get("answer")

                if user_id in game.selected_pair:
                    if ans == "kiss":
                        for pid in game.selected_pair:
                            game.players[pid]["kisses"] += 1
                        await broadcast({
                            "type": "kiss_accepted",
                            "stats": game.get_players_list()
                        })
                    else:
                        for pid in game.selected_pair:
                            game.players[pid]["rejects"] += 1
                        await broadcast({
                            "type": "kiss_rejected",
                            "stats": game.get_players_list()
                        })

                    game.selected_pair = None
                    await asyncio.sleep(1)
                    await broadcast({
                        "type": "ready_to_spin",
                        "can_spin": True
                    })

    except WebSocketDisconnect:
        game.remove_player(ws)
        await broadcast({
            "type": "player_left",
            "players": game.get_players_list()
        })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
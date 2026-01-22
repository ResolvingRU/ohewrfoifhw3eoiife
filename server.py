from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from datetime import datetime
from typing import Dict, Set
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GameState:
    def __init__(self):
        self.players: Dict[str, dict] = {}
        self.connections: Set[WebSocket] = set()
        self.is_spinning = False
        self.selected_pair = None
        self.last_spin = None
        self.cooldown = 5

    def add_player(self, user_id: str, name: str, username: str, photo_url: str, ws: WebSocket):
        self.players[user_id] = {
            "id": user_id,
            "name": name,
            "username": username,
            "photo": photo_url,
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
                "username": p["username"],
                "photo": p["photo"],
                "kisses": p["kisses"],
                "rejects": p["rejects"]
            }
            for p in self.players.values()
        ]


game = GameState()


async def broadcast(msg: dict):
    dead = set()
    for ws in game.connections:
        try:
            await ws.send_json(msg)
        except:
            dead.add(ws)
    for ws in dead:
        game.remove_player(ws)


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
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
            overflow: hidden;
        }

        .container { 
            width: 100%; 
            max-width: 500px; 
            padding: 20px; 
        }

        .game-circle {
            position: relative;
            width: 100%;
            aspect-ratio: 1;
            background: rgba(255,255,255,0.03);
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.1);
            box-shadow: 0 8px 32px rgba(0,0,0,0.5),
                        inset 0 0 50px rgba(255,255,255,0.02);
        }

        .bottle {
            position: absolute;
            top: 50%; 
            left: 50%;
            width: 45%; 
            height: 4px;
            background: linear-gradient(90deg, transparent 0%, #00d4ff 30%, #00d4ff 70%, transparent 100%);
            transform-origin: 0% 50%;
            margin-left: 0;
            margin-top: -2px;
            filter: drop-shadow(0 0 15px #00d4ff);
            transition: transform 0.1s;
            border-radius: 2px;
        }

        .bottle::after {
            content: '';
            position: absolute;
            right: -8px;
            top: 50%;
            transform: translateY(-50%);
            width: 0;
            height: 0;
            border-left: 8px solid #00d4ff;
            border-top: 4px solid transparent;
            border-bottom: 4px solid transparent;
            filter: drop-shadow(0 0 8px #00d4ff);
        }

        .bottle.spin { 
            animation: rotate 3s cubic-bezier(0.25,0.46,0.45,0.94); 
        }

        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(1800deg); }
        }

        .players {
            position: absolute;
            width: 100%; 
            height: 100%;
            top: 0; 
            left: 0;
        }

        .player {
            position: absolute;
            width: 60px; 
            height: 60px;
            background: rgba(30,30,50,0.8);
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            transition: all 0.3s;
            backdrop-filter: blur(10px);
        }

        .player-avatar {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            object-fit: cover;
            background: #2a2a3e;
            border: 2px solid rgba(255,255,255,0.1);
        }

        .player-name {
            position: absolute;
            bottom: -20px;
            font-size: 11px;
            color: rgba(255,255,255,0.7);
            font-weight: 500;
            white-space: nowrap;
            text-shadow: 0 2px 4px rgba(0,0,0,0.8);
        }

        .player.glow {
            background: linear-gradient(135deg, #ff006e, #8338ec);
            border-color: #ff006e;
            transform: scale(1.3);
            box-shadow: 0 0 40px rgba(255,0,110,0.8);
        }

        .player.glow .player-avatar {
            border-color: #fff;
        }

        .controls {
            text-align: center;
            margin-top: 40px;
        }

        .btn-spin {
            padding: 16px 50px;
            font-size: 18px;
            background: linear-gradient(135deg, #00d4ff, #0077ff);
            border: none;
            border-radius: 50px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(0,119,255,0.4);
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn-spin:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0,119,255,0.6);
        }

        .btn-spin:active:not(:disabled) {
            transform: translateY(-1px);
        }

        .btn-spin:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            background: #555;
        }

        .status {
            margin-top: 20px;
            font-size: 14px;
            color: rgba(255,255,255,0.6);
            font-weight: 500;
        }

        .players-count {
            margin-top: 10px;
            font-size: 13px;
            color: rgba(255,255,255,0.5);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0; 
            left: 0;
            width: 100%; 
            height: 100%;
            background: rgba(0,0,0,0.9);
            align-items: center;
            justify-content: center;
            z-index: 999;
            backdrop-filter: blur(10px);
        }

        .modal.show { display: flex; }

        .modal-box {
            background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
            padding: 40px;
            border-radius: 25px;
            text-align: center;
            color: #fff;
            max-width: 90%;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
        }

        .modal-box h2 { 
            margin-bottom: 25px; 
            font-size: 24px;
            background: linear-gradient(135deg, #00d4ff, #ff006e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .modal-players {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 30px;
            margin: 30px 0;
        }

        .modal-player {
            text-align: center;
        }

        .modal-player img {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 3px solid #ff006e;
            box-shadow: 0 0 30px rgba(255,0,110,0.6);
            margin-bottom: 10px;
        }

        .modal-player-name {
            font-size: 14px;
            font-weight: 600;
            color: rgba(255,255,255,0.9);
        }

        .heart-icon {
            font-size: 40px;
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }

        .modal-btns {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }

        .modal-btn {
            padding: 14px 35px;
            border: none;
            border-radius: 30px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn-kiss {
            background: linear-gradient(135deg, #ff006e, #ff4d8f);
            color: white;
            box-shadow: 0 6px 20px rgba(255,0,110,0.4);
        }

        .btn-kiss:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255,0,110,0.6);
        }

        .btn-no {
            background: rgba(255,255,255,0.1);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.2);
        }

        .btn-no:hover {
            background: rgba(255,255,255,0.15);
            transform: translateY(-2px);
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
            <div class="players-count" id="count">Игроков: 0</div>
        </div>
    </div>

    <div class="modal" id="modal">
        <div class="modal-box">
            <h2>Бутылочка выбрала вас! 💋</h2>
            <div class="modal-players" id="modalPlayers"></div>
            <p style="color: rgba(255,255,255,0.7); margin-top: 20px;">Хотите поцеловаться?</p>
            <div class="modal-btns">
                <button class="modal-btn btn-kiss" onclick="answer('kiss')">💋 Поцеловать</button>
                <button class="modal-btn btn-no" onclick="answer('reject')">🚫 Отказаться</button>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.enableClosingConfirmation();

        const user = tg.initDataUnsafe?.user || {
            id: Date.now(),
            first_name: 'Player',
            username: 'player',
            photo_url: ''
        };

        let ws;
        let myId = user.id.toString();

        function connect() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${location.host}/ws`);

            ws.onopen = () => {
                ws.send(JSON.stringify({
                    user_id: myId,
                    name: user.first_name,
                    username: user.username || 'user',
                    photo_url: user.photo_url || ''
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
                    setStatus('Бутылочка крутится...');
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
                    setStatus('💋 Поцелуй состоялся!');
                    clearGlow();
                    drawPlayers(msg.stats);
                }
                else if (msg.type === 'kiss_rejected') {
                    hideModal();
                    setStatus('🚫 Кто-то отказался...');
                    clearGlow();
                    drawPlayers(msg.stats);
                }
                else if (msg.type === 'ready_to_spin') {
                    updateBtn(true);
                    setStatus('Можно крутить снова!');
                }
            };

            ws.onerror = () => setStatus('Ошибка подключения');
            ws.onclose = () => {
                setStatus('Переподключение...');
                setTimeout(connect, 3000);
            };
        }

        function drawPlayers(players) {
            const container = document.getElementById('players');
            container.innerHTML = '';
            const r = container.offsetWidth / 2 - 40;
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

                const avatar = document.createElement('img');
                avatar.className = 'player-avatar';
                avatar.src = p.photo || `https://ui-avatars.com/api/?name=${encodeURIComponent(p.name)}&background=2a2a3e&color=fff&size=45`;
                avatar.alt = p.name;

                const name = document.createElement('div');
                name.className = 'player-name';
                name.textContent = p.username ? '@' + p.username : p.name;

                div.appendChild(avatar);
                div.appendChild(name);
                container.appendChild(div);
            });

            document.getElementById('count').textContent = `Игроков: ${players.length}`;
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
            const container = document.getElementById('modalPlayers');
            container.innerHTML = players.map(p => `
                <div class="modal-player">
                    <img src="${p.photo || `https://ui-avatars.com/api/?name=${encodeURIComponent(p.name)}&background=ff006e&color=fff&size=80`}" alt="${p.name}">
                    <div class="modal-player-name">${p.username ? '@' + p.username : p.name}</div>
                </div>
            `).join('<div class="heart-icon">💋</div>');

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
        auth = await ws.receive_json()
        user_id = auth.get("user_id", str(random.randint(1000, 9999)))
        name = auth.get("name", "Player")
        username = auth.get("username", "")
        photo_url = auth.get("photo_url", "")

        game.add_player(user_id, name, username, photo_url, ws)

        await ws.send_json({
            "type": "init",
            "players": game.get_players_list(),
            "can_spin": game.can_spin()
        })

        await broadcast({
            "type": "player_joined",
            "players": game.get_players_list()
        })

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
                            {
                                "id": pair[0],
                                "name": game.players[pair[0]]["name"],
                                "username": game.players[pair[0]]["username"],
                                "photo": game.players[pair[0]]["photo"]
                            },
                            {
                                "id": pair[1],
                                "name": game.players[pair[1]]["name"],
                                "username": game.players[pair[1]]["username"],
                                "photo": game.players[pair[1]]["photo"]
                            }
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
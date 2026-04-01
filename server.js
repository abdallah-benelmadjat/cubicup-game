/**
 * server.js — CubiCup multiplayer + Bot API server
 *
 * Human rooms  : server just relays moves (lightweight)
 * Bot rooms    : server is authoritative — tracks state, validates moves,
 *                returns legal_moves + full board after every move,
 *                optionally runs a built-in AI opponent
 *
 * ── Bot API quick-start ───────────────────────────────────────────────────
 *
 * Python:
 *   pip install "python-socketio[client]" requests
 *
 *   import socketio
 *   sio = socketio.Client()
 *   sio.connect('https://cubicup.abe-ben.dev')
 *   sio.emit('bot-register', {'name': 'MyBot'})
 *   sio.emit('create-bot-room', {'opponent': 'ai:hard'})
 *
 *   @sio.on('game-start')
 *   def start(data):
 *       if data['state']['your_turn']:
 *           sio.emit('move', {'move': data['state']['legal_moves'][0]})
 *
 *   @sio.on('opponent-move')
 *   def opp(data):
 *       if not data.get('game_over') and data['state']['your_turn']:
 *           sio.emit('move', {'move': data['state']['legal_moves'][0]})
 *
 *   sio.wait()
 *
 * ── Events (bot → server) ────────────────────────────────────────────────
 *   bot-register      { name }
 *   create-bot-room   { opponent: 'human'|'bot'|'ai:easy'|'ai:medium'|'ai:hard' }
 *   join-bot-room     { code }
 *   spectate          { code }
 *   move              { move: "x,y,z" }
 *   request-state     (no payload)
 *
 * ── Events (server → bot) ────────────────────────────────────────────────
 *   bot-registered    { name }
 *   room-created      { code, color, state, opponent_type }
 *   game-start        { color, state, opponent_type }
 *   move-ack          { move, state, game_over? }
 *   opponent-move     { move, state, game_over? }
 *   move-error        string
 *   state             (current state snapshot)
 *   spectator-update  { event, move?, player?, state, game_over? }
 *   opponent-disconnected
 *
 * ── State object ─────────────────────────────────────────────────────────
 *   {
 *     board:          { "x,y,z": "yellow"|"blue"|null, ... },
 *     current_player: "yellow"|"blue",
 *     your_turn:      bool,
 *     mandatory:      ["x,y,z", ...],   // must play one of these if non-empty
 *     cubes_left:     { yellow: int, blue: int },
 *     legal_moves:    ["x,y,z", ...],
 *     move_number:    int,
 *     terminal:       null|"yellow"|"blue"|"draw"
 *   }
 *
 * ── Game-over object ─────────────────────────────────────────────────────
 *   {
 *     result:      "yellow"|"blue"|"draw",
 *     move_history: ["x,y,z", ...],
 *     total_moves:  int,
 *     duration_ms:  int
 *   }
 */

'use strict';

const express = require('express');
const http    = require('http');
const { Server } = require('socket.io');
const path    = require('path');

const app    = express();
const server = http.createServer(app);
const io     = new Server(server, { cors: { origin: '*' } });

app.use(express.static(path.join(__dirname)));
app.get('/', (_req, res) => res.sendFile(path.join(__dirname, 'cubes.html')));

// ══════════════════════════════════════════════════════════════════════════════
// GAME LOGIC  (server-authoritative for bot rooms)
// ══════════════════════════════════════════════════════════════════════════════

const N         = 6;
const PEAK_KEY  = '0,0,0';

const ALL_POSITIONS = [];
for (let x = 0; x < N; x++)
    for (let y = 0; y < N; y++)
        for (let z = 0; z < N; z++)
            if (x + y + z <= N - 1)
                ALL_POSITIONS.push(`${x},${y},${z}`);

function freshBoard() {
    const b = {};
    ALL_POSITIONS.forEach(k => (b[k] = null));
    return b;
}

function isValidMoveB(board, key) {
    if (board[key] !== null) return false;
    const [x, y, z] = key.split(',').map(Number);
    if (x + y + z === N - 1) return true;
    return board[`${x+1},${y},${z}`] != null
        && board[`${x},${y+1},${z}`] != null
        && board[`${x},${y},${z+1}`] != null;
}

function getValidMovesB(board) {
    return ALL_POSITIONS.filter(k => isValidMoveB(board, k));
}

function getCubicupsB(board, color) {
    return getValidMovesB(board).filter(k => {
        const [x, y, z] = k.split(',').map(Number);
        return board[`${x+1},${y},${z}`] === color
            && board[`${x},${y+1},${z}`] === color
            && board[`${x},${y},${z+1}`] === color;
    });
}

function getLegalMovesB(state) {
    if (state.terminal) return [];
    if (state.mandatory.length > 0) return [...state.mandatory];
    return getValidMovesB(state.board);
}

function applyMoveB(state, key) {
    const { board, currentPlayer, mandatory, cubesLeft, moveHistory, startTime } = state;
    const opp      = currentPlayer === 'yellow' ? 'blue' : 'yellow';
    const newBoard  = { ...board, [key]: currentPlayer };
    const newCubes  = { ...cubesLeft, [currentPlayer]: cubesLeft[currentPlayer] - 1 };
    const newHistory = [...moveHistory, key];

    // ── Peak resolution ──────────────────────────────────────────────────────
    if (key === PEAK_KEY) {
        const suppCount = [`1,0,0`, `0,1,0`, `0,0,1`]
            .filter(s => newBoard[s] === opp).length;
        return {
            board: newBoard, currentPlayer, mandatory: [],
            cubesLeft: newCubes, terminal: suppCount === 3 ? 'draw' : currentPlayer,
            moveHistory: newHistory, startTime,
        };
    }

    const wasMandatory = mandatory.length > 0;
    let newMandatory   = [];
    let newPlayer      = currentPlayer;

    if (wasMandatory) {
        newMandatory = mandatory.filter(k => k !== key);
    } else {
        newPlayer    = opp;
        newMandatory = getCubicupsB(newBoard, currentPlayer); // cups just created → opp must fill
    }

    // ── Cube exhaustion ──────────────────────────────────────────────────────
    if (newCubes[newPlayer] === 0) {
        const other = newPlayer === 'yellow' ? 'blue' : 'yellow';
        if (newCubes[other] > 0) { newMandatory = []; newPlayer = other; }
    }

    return {
        board: newBoard, currentPlayer: newPlayer, mandatory: newMandatory,
        cubesLeft: newCubes, terminal: null,
        moveHistory: newHistory, startTime,
    };
}

function freshState() {
    return {
        board: freshBoard(),
        currentPlayer: 'yellow',
        mandatory: [],
        cubesLeft: { yellow: 28, blue: 28 },
        terminal: null,
        moveHistory: [],
        startTime: Date.now(),
    };
}

function statePayload(state, myColor) {
    return {
        board:          state.board,
        current_player: state.currentPlayer,
        your_turn:      myColor ? state.currentPlayer === myColor : null,
        mandatory:      state.mandatory,
        cubes_left:     state.cubesLeft,
        legal_moves:    getLegalMovesB(state),
        move_number:    state.moveHistory.length,
        terminal:       state.terminal,
    };
}

function gameOverPayload(state) {
    return {
        result:       state.terminal,
        move_history: state.moveHistory,
        total_moves:  state.moveHistory.length,
        duration_ms:  Date.now() - state.startTime,
    };
}

// ══════════════════════════════════════════════════════════════════════════════
// BUILT-IN AI  (easy / medium / hard)
// ══════════════════════════════════════════════════════════════════════════════

function countNewCupsB(board, key, color) {
    board[key] = color;
    const [kx, ky, kz] = key.split(',').map(Number);
    let count = 0;
    [[kx-1,ky,kz],[kx,ky-1,kz],[kx,ky,kz-1]].forEach(([cx,cy,cz]) => {
        if (cx < 0 || cy < 0 || cz < 0) return;
        const ck = `${cx},${cy},${cz}`;
        if (board[ck] !== null) return;
        if (board[`${cx+1},${cy},${cz}`]===color && board[`${cx},${cy+1},${cz}`]===color && board[`${cx},${cy},${cz+1}`]===color) count++;
    });
    board[key] = null;
    return count;
}

function aiPickMoveB(state, difficulty, aiColor) {
    const legal = getLegalMovesB(state);
    if (!legal.length) return null;

    const opp         = aiColor === 'yellow' ? 'blue' : 'yellow';
    const isMandatory = state.mandatory.length > 0;

    // Instant win: take peak if safe
    if (!isMandatory && legal.includes(PEAK_KEY)) {
        const b = state.board;
        if (!(b['1,0,0']===opp && b['0,1,0']===opp && b['0,0,1']===opp)) return PEAK_KEY;
    }

    if (difficulty === 'easy') return legal[Math.floor(Math.random() * legal.length)];

    if (difficulty === 'medium') {
        if (isMandatory) return legal[Math.floor(Math.random() * legal.length)];
        let best = [], bestSc = -1;
        legal.forEach(k => {
            const [x,y,z] = k.split(',').map(Number);
            const sc = [state.board[`${x+1},${y},${z}`], state.board[`${x},${y+1},${z}`], state.board[`${x},${y},${z+1}`]]
                .filter(v => v === aiColor).length;
            if (sc > bestSc) { bestSc = sc; best = [k]; } else if (sc === bestSc) best.push(k);
        });
        return best[Math.floor(Math.random() * best.length)];
    }

    // hard
    if (isMandatory) return legal[Math.floor(Math.random() * legal.length)];
    let best = [], bestSc = -1;
    legal.forEach(k => {
        const own = countNewCupsB(state.board, k, aiColor);
        const blk = countNewCupsB(state.board, k, opp);
        const sc  = own * 2 + blk;
        if (sc > bestSc) { bestSc = sc; best = [k]; } else if (sc === bestSc) best.push(k);
    });
    return best[Math.floor(Math.random() * best.length)];
}

// ══════════════════════════════════════════════════════════════════════════════
// ROOM MANAGEMENT
// ══════════════════════════════════════════════════════════════════════════════

const rooms = new Map();

function generateCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let code;
    do { code = Array.from({length:5}, () => chars[Math.floor(Math.random()*chars.length)]).join(''); }
    while (rooms.has(code));
    return code;
}

function broadcastSpectators(code, data) {
    io.to(`spec:${code}`).emit('spectator-update', data);
}

function scheduleAiMove(code) {
    const room = rooms.get(code);
    if (!room || !room.state || room.state.terminal) return;

    const difficulty = (room.opponent || '').split(':')[1] || 'easy';
    const aiColor    = room.aiColor;
    if (room.state.currentPlayer !== aiColor) return;

    const move = aiPickMoveB(room.state, difficulty, aiColor);
    if (!move) return;

    room.state = applyMoveB(room.state, move);
    const ns   = room.state;
    console.log(`[ai-move]  room=${code}  ${difficulty} AI (${aiColor}) → ${move}`);

    room.players.forEach(id => {
        const color = room.playerColors[id];
        io.to(id).emit('opponent-move', {
            move,
            state:     statePayload(ns, color),
            ...(ns.terminal ? { game_over: gameOverPayload(ns) } : {}),
        });
    });

    broadcastSpectators(code, {
        event: 'move', move, player: aiColor,
        state: statePayload(ns, null),
        ...(ns.terminal ? { game_over: gameOverPayload(ns) } : {}),
    });

    if (ns.terminal) setTimeout(() => rooms.delete(code), 60000);
}

function cleanupRoom(socket) {
    const code = socket.roomCode;
    if (!code || !rooms.has(code)) return;
    console.log(`[cleanup]  room=${code}`);
    socket.to(code).emit('opponent-disconnected');
    rooms.delete(code);
    socket.roomCode = null;
}

// ══════════════════════════════════════════════════════════════════════════════
// SOCKET EVENTS
// ══════════════════════════════════════════════════════════════════════════════

io.on('connection', socket => {
    console.log(`[connect]  ${socket.id}`);
    socket.isBot   = false;
    socket.botName = null;

    // ── Bot registration ─────────────────────────────────────────────────────
    socket.on('bot-register', ({ name } = {}) => {
        socket.isBot   = true;
        socket.botName = (name || 'unnamed-bot').slice(0, 32);
        console.log(`[bot]      "${socket.botName}" registered`);
        socket.emit('bot-registered', { name: socket.botName });
    });

    // ── Create HUMAN room ────────────────────────────────────────────────────
    socket.on('create-room', () => {
        if (socket.roomCode) cleanupRoom(socket);
        const code = generateCode();
        rooms.set(code, {
            type: 'human', players: [socket.id], started: false,
            playerColors: { [socket.id]: 'yellow' },
        });
        socket.join(code);
        socket.roomCode = code;
        console.log(`[create]   room=${code}`);
        socket.emit('room-created', { code, color: 'yellow' });
    });

    // ── Join HUMAN room ──────────────────────────────────────────────────────
    socket.on('join-room', ({ code }) => {
        const c    = (code || '').toUpperCase().trim();
        const room = rooms.get(c);
        if (!room)                             return socket.emit('join-error', 'Room not found.');
        if (room.started || room.players.length >= 2) return socket.emit('join-error', 'Room is full.');
        room.players.push(socket.id);
        room.playerColors[socket.id] = 'blue';
        room.started = true;
        socket.join(c); socket.roomCode = c;
        console.log(`[join]     room=${c}`);
        socket.emit('game-start',            { color: 'blue' });
        io.to(room.players[0]).emit('game-start', { color: 'yellow' });
    });

    // ── Create BOT room ──────────────────────────────────────────────────────
    // opponent: 'human' | 'bot' | 'ai:easy' | 'ai:medium' | 'ai:hard'
    socket.on('create-bot-room', ({ opponent = 'human', name } = {}) => {
        if (name) { socket.isBot = true; socket.botName = name; }
        if (socket.roomCode) cleanupRoom(socket);

        const code  = generateCode();
        const state = freshState();
        const isAi  = (opponent || '').startsWith('ai:');
        const aiColor = isAi ? 'blue' : null; // AI always plays blue when opponent

        const room = {
            type: 'bot', opponent, players: [socket.id],
            playerColors: { [socket.id]: 'yellow' },
            started: isAi, state, spectators: [], aiColor,
        };
        rooms.set(code, room);
        socket.join(code); socket.roomCode = code;
        console.log(`[bot-room] room=${code}  opponent=${opponent}`);

        socket.emit('room-created', {
            code, color: 'yellow', opponent_type: opponent,
            state: statePayload(state, 'yellow'),
        });

        if (isAi) {
            socket.emit('game-start', {
                color: 'yellow', opponent_type: opponent,
                state: statePayload(state, 'yellow'),
            });
            // Yellow moves first — no AI move needed yet
        }
    });

    // ── Join BOT room ────────────────────────────────────────────────────────
    socket.on('join-bot-room', ({ code, name } = {}) => {
        const c    = (code || '').toUpperCase().trim();
        if (name) { socket.isBot = true; socket.botName = name; }
        const room = rooms.get(c);
        if (!room)              return socket.emit('join-error', 'Room not found.');
        if (room.type !== 'bot') return socket.emit('join-error', 'Not a bot room — use join-room instead.');
        if (room.started || room.players.length >= 2) return socket.emit('join-error', 'Room is full.');

        room.players.push(socket.id);
        room.playerColors[socket.id] = 'blue';
        room.started = true;
        socket.join(c); socket.roomCode = c;
        console.log(`[bot-join] room=${c}  by ${socket.botName || socket.id}`);

        const st = room.state;
        socket.emit('game-start',            { color: 'blue',   opponent_type: 'bot', state: statePayload(st, 'blue') });
        io.to(room.players[0]).emit('game-start', { color: 'yellow', opponent_type: 'bot', state: statePayload(st, 'yellow') });
        broadcastSpectators(c, { event: 'game-started', state: statePayload(st, null) });
    });

    // ── Spectate ─────────────────────────────────────────────────────────────
    socket.on('spectate', ({ code } = {}) => {
        const c    = (code || '').toUpperCase().trim();
        const room = rooms.get(c);
        if (!room) return socket.emit('join-error', 'Room not found.');
        socket.join(`spec:${c}`);
        socket.spectatingCode = c;
        socket.emit('spectate-start', {
            state:     room.state ? statePayload(room.state, null) : null,
            room_type: room.type,
            opponent:  room.opponent || null,
        });
        console.log(`[spectate] room=${c}  by ${socket.id}`);
    });

    // ── Move ─────────────────────────────────────────────────────────────────
    socket.on('move', ({ move }) => {
        const code = socket.roomCode;
        if (!code || !rooms.has(code)) return;
        const room = rooms.get(code);

        // Human room — just relay
        if (room.type === 'human') {
            socket.to(code).emit('opponent-move', { move });
            return;
        }

        // Bot room — validate server-side
        if (!room.started)       return socket.emit('move-error', 'Game not started yet.');
        const st = room.state;
        if (st.terminal)         return socket.emit('move-error', 'Game is already over.');
        const myColor = room.playerColors[socket.id];
        if (st.currentPlayer !== myColor) return socket.emit('move-error', 'Not your turn.');

        const legal = getLegalMovesB(st);
        if (!legal.includes(move))
            return socket.emit('move-error', `Illegal move "${move}". Legal: [${legal.join(', ')}]`);

        room.state = applyMoveB(st, move);
        const ns   = room.state;
        console.log(`[move]     room=${code}  ${myColor} → ${move}  (move #${ns.moveHistory.length})`);

        const goPayload = ns.terminal ? gameOverPayload(ns) : undefined;

        // Ack to mover
        socket.emit('move-ack', {
            move, state: statePayload(ns, myColor),
            ...(goPayload ? { game_over: goPayload } : {}),
        });

        // Relay to the other player (bot or human in bot room)
        const oppId = room.players.find(id => id !== socket.id);
        if (oppId) {
            const oppColor = room.playerColors[oppId];
            io.to(oppId).emit('opponent-move', {
                move, state: statePayload(ns, oppColor),
                ...(goPayload ? { game_over: goPayload } : {}),
            });
        }

        broadcastSpectators(code, {
            event: 'move', move, player: myColor,
            state: statePayload(ns, null),
            ...(goPayload ? { game_over: goPayload } : {}),
        });

        if (ns.terminal) { setTimeout(() => rooms.delete(code), 60000); return; }

        // Schedule built-in AI move if needed
        if (room.opponent && room.opponent.startsWith('ai:') && ns.currentPlayer === room.aiColor) {
            setTimeout(() => scheduleAiMove(code), 500);
        }
    });

    // ── Request state snapshot ────────────────────────────────────────────────
    socket.on('request-state', () => {
        const code = socket.roomCode;
        if (!code || !rooms.has(code)) return socket.emit('join-error', 'Not in a room.');
        const room = rooms.get(code);
        if (room.type !== 'bot') return;
        socket.emit('state', statePayload(room.state, room.playerColors[socket.id]));
    });

    // ── Disconnect ───────────────────────────────────────────────────────────
    socket.on('disconnect', () => {
        console.log(`[disconnect] ${socket.id}`);
        cleanupRoom(socket);
    });
});

// ══════════════════════════════════════════════════════════════════════════════
// START
// ══════════════════════════════════════════════════════════════════════════════

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => console.log(`CubiCup → http://localhost:${PORT}`));

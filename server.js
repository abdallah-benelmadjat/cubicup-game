/**
 * server.js — CubiCup online multiplayer server
 *
 * Usage:
 *   npm install
 *   node server.js
 *
 * Then open http://localhost:3000 in a browser.
 * Share your LAN IP (e.g. http://192.168.x.x:3000) with your friend.
 *
 * Protocol (move-only, clients rebuild state locally):
 *   Client → Server:  create-room | join-room {code} | move {move:"x,y,z"}
 *   Server → Client:  room-created {code,color} | game-start {color} |
 *                     join-error {msg} | opponent-move {move} |
 *                     opponent-disconnected
 */

'use strict';

const express = require('express');
const http    = require('http');
const { Server } = require('socket.io');
const path    = require('path');

const app    = express();
const server = http.createServer(app);
const io     = new Server(server, { cors: { origin: '*' } });

// Serve the game files (cubes.html, wood.png, etc.)
app.use(express.static(path.join(__dirname)));

// Root → cubes.html
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'cubes.html'));
});

// ── Room management ───────────────────────────────────────────────────────────

// rooms: Map<code, { players: string[], started: bool }>
const rooms = new Map();

function generateCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let code;
    do {
        code = Array.from({ length: 5 }, () =>
            chars[Math.floor(Math.random() * chars.length)]
        ).join('');
    } while (rooms.has(code));
    return code;
}

// ── Socket events ─────────────────────────────────────────────────────────────

io.on('connection', (socket) => {
    console.log(`[connect]  ${socket.id}`);

    // ── Create room ──────────────────────────────────────────────────────────
    socket.on('create-room', () => {
        // Clean up any previous room this socket owned
        if (socket.roomCode) cleanupRoom(socket);

        const code = generateCode();
        rooms.set(code, { players: [socket.id], started: false });
        socket.join(code);
        socket.roomCode = code;
        console.log(`[create]   room=${code} by ${socket.id}`);
        socket.emit('room-created', { code, color: 'yellow' });
    });

    // ── Join room ────────────────────────────────────────────────────────────
    socket.on('join-room', ({ code }) => {
        const normalCode = (code || '').toUpperCase().trim();
        const room = rooms.get(normalCode);

        if (!room) {
            socket.emit('join-error', 'Room not found. Check the code and try again.');
            return;
        }
        if (room.started || room.players.length >= 2) {
            socket.emit('join-error', 'Room is full or game already started.');
            return;
        }

        room.players.push(socket.id);
        room.started = true;
        socket.join(normalCode);
        socket.roomCode = normalCode;

        console.log(`[join]     room=${normalCode} by ${socket.id}`);

        // Tell the joiner they are Blue
        socket.emit('game-start', { color: 'blue' });
        // Tell the creator (Yellow) the game has started
        io.to(room.players[0]).emit('game-start', { color: 'yellow' });
    });

    // ── Relay move ───────────────────────────────────────────────────────────
    socket.on('move', ({ move }) => {
        const code = socket.roomCode;
        if (!code) return;
        console.log(`[move]     room=${code}  move=${move}`);
        // Broadcast only to the OTHER player in this room
        socket.to(code).emit('opponent-move', { move });
    });

    // ── Disconnect ───────────────────────────────────────────────────────────
    socket.on('disconnect', () => {
        console.log(`[disconnect] ${socket.id}`);
        cleanupRoom(socket);
    });
});

function cleanupRoom(socket) {
    const code = socket.roomCode;
    if (!code || !rooms.has(code)) return;
    console.log(`[cleanup]  room=${code}`);
    socket.to(code).emit('opponent-disconnected');
    rooms.delete(code);
    socket.roomCode = null;
}

// ── Start ─────────────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
    console.log(`CubiCup server → http://localhost:${PORT}`);
    console.log('Share your LAN IP with your friend to play together.');
});

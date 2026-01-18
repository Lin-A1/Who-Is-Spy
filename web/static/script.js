const ws = new WebSocket(`ws://${window.location.host}/ws`);
let players = {};

// UI State
const ui = {
    playersRow: document.getElementById('players-row'),
    feed: document.getElementById('game-feed'),
    actionText: document.getElementById('current-action'),
    status: document.getElementById('game-status'),
    round: document.getElementById('round-num'),
    voteResults: document.getElementById('vote-results'),
    startBtn: document.getElementById('start-btn'),
    aliveBadge: document.getElementById('alive-badge')
};

ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
ws.onclose = () => {
    ui.status.textContent = 'OFFLINE';
    ui.status.className = 'px-3 py-1 bg-red-100 text-red-600 rounded-full text-xs font-bold uppercase tracking-wider';
};

// Config
const PROVIDER_MAP = {
    'deepseek': { domain: 'deepseek.com', color: '4d6bfe' },
    'kimi': { domain: 'moonshot.cn', color: '000000' },
    'qwen': { domain: 'tongyi.aliyun.com', color: '615ced' },
    'glm': { domain: 'zhipuai.cn', color: '357bf9' },
    'minimax': { domain: 'minimaxi.com', color: 'db2828' },
    'doubao': { domain: 'volcengine.com', color: '04c38d' },
    'openai': { domain: 'openai.com', color: '10a37f' },
    'claude': { domain: 'anthropic.com', color: 'd97757' },
    'mimo': { domain: 'mimo.com', color: 'ffae00' }
};

function getAvatarUrl(name, model) {
    let provider = model.split('/')[0].toLowerCase();
    if (name.toLowerCase().includes('gpt')) provider = 'openai';
    if (name.toLowerCase().includes('claude')) provider = 'claude';
    const config = PROVIDER_MAP[provider];
    const fallback = `https://ui-avatars.com/api/?name=${name}&background=random&color=fff&size=128&bold=true`;
    if (config && config.domain) {
        return `https://unavatar.io/${config.domain}?fallback=${encodeURIComponent(fallback)}`;
    }
    return fallback;
}

function startGame() {
    const cWord = document.getElementById('civilian-word').value.trim();
    const sWord = document.getElementById('spy-word').value.trim();

    ui.startBtn.innerHTML = 'Starting...';
    ui.startBtn.disabled = true;

    fetch('/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ civilian_word: cWord || null, spy_word: sWord || null })
    }).catch(() => {
        ui.startBtn.textContent = 'Start New Game';
        ui.startBtn.disabled = false;
    });
}

function handleEvent(data) {
    const { type, payload } = data;
    switch (type) {
        case 'game_start': initGame(payload); break;
        case 'round_start': updateRound(payload.round_number); break;
        case 'phase_change': ui.actionText.textContent = `Phase: ${payload.phase}`; break;
        case 'player_speaking': setPlayerActive(payload.player_name, true); break;
        case 'description':
            setPlayerActive(payload.player_name, false);
            addChatMsg(payload.player_name, payload.content);
            break;
        case 'vote': break; // Don't spam chat with votes
        case 'vote_result': showVoteResults(payload.counts); break;
        case 'elimination': handleElimination(payload.player_name, payload.role, payload.leave_message); break;
        case 'game_end': showGameResult(payload.winner); break;
        case 'error': alert(payload.message); break;
    }
}

function initGame(payload) {
    ui.playersRow.innerHTML = '';
    ui.feed.innerHTML = '';
    ui.voteResults.innerHTML = '<div class="text-center text-xs text-slate-300 mt-10 italic">Waiting for votes...</div>';
    players = {};

    ui.status.textContent = 'LIVE';
    ui.status.className = 'px-3 py-1 bg-emerald-100 text-emerald-600 rounded-full text-xs font-bold uppercase tracking-wider animate-pulse';

    payload.players.forEach(p => {
        players[p.name] = p;
        const el = createPlayerIcon(p);
        ui.playersRow.appendChild(el);
    });

    updateAliveCount(payload.players.length, payload.players.length);
    addSystemLine(`Game Started · Word Pair: ${payload.civilian_word} / ${payload.spy_word}`);
}

function createPlayerIcon(p) {
    const div = document.createElement('div');
    div.id = `player-${p.name}`;
    div.className = 'flex flex-col items-center gap-2 min-w-[80px] group transition-all duration-300 pop-in';

    const avatarUrl = getAvatarUrl(p.name, p.model);

    div.innerHTML = `
        <div id="ring-${p.name}" class="avatar-ring w-14 h-14 rounded-full p-0.5 bg-white border border-slate-200 shadow-sm relative group-hover:-translate-y-1 transition-transform">
            <img src="${avatarUrl}" class="w-full h-full rounded-full object-cover bg-slate-100">
            <div id="status-${p.name}" class="absolute bottom-0 right-0 w-3.5 h-3.5 bg-emerald-500 border-2 border-white rounded-full"></div>
        </div>
        <div class="text-center">
            <div class="text-xs font-bold text-slate-700 truncate max-w-[80px]">${p.name}</div>
            <div class="text-[10px] text-slate-400 font-mono scale-90">${p.model.split('/')[1] || 'AI'}</div>
        </div>
    `;
    return div;
}

function setPlayerActive(name, active) {
    const ring = document.getElementById(`ring-${name}`);
    if (!ring) return;

    if (active) {
        ring.classList.add('active');
        ui.actionText.textContent = `${name} is thinking...`;
        ui.actionText.className = 'text-xs font-bold text-emerald-600 animate-pulse';
    } else {
        ring.classList.remove('active');
    }
}

function addChatMsg(name, content) {
    const div = document.createElement('div');
    const isMe = false; // Todo: if human player

    const p = players[name];
    const avatarUrl = p ? getAvatarUrl(name, p.model) : '';

    div.className = 'flex gap-4 pop-in group';
    div.innerHTML = `
        <img src="${avatarUrl}" class="w-10 h-10 rounded-full bg-slate-100 object-cover border border-slate-100 mt-1 shrink-0 shadow-sm">
        <div class="flex flex-col max-w-[85%] gap-1">
            <div class="flex items-baseline gap-2">
                <span class="text-xs font-bold text-slate-700">${name}</span>
                <span class="text-[10px] text-slate-400">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div class="bubble bubble-left bg-white p-3 rounded-2xl rounded-tl-none border border-slate-200 text-sm text-slate-700 shadow-sm leading-relaxed group-hover:shadow-md transition-shadow">
                ${content}
            </div>
        </div>
    `;

    ui.feed.appendChild(div);
    scrollToBottom();
}

function addSystemLine(msg) {
    const div = document.createElement('div');
    div.className = 'flex items-center gap-4 my-6 opacity-60';
    div.innerHTML = `
        <div class="h-px bg-slate-200 flex-1"></div>
        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400">${msg}</div>
        <div class="h-px bg-slate-200 flex-1"></div>
    `;
    ui.feed.appendChild(div);
    scrollToBottom();
}

function updateRound(n) {
    const el = ui.round;
    // Animation reset
    el.style.animation = 'none';
    el.offsetHeight; /* trigger reflow */
    el.style.animation = 'popIn 0.5s';
    el.textContent = n;

    addSystemLine(`Round ${n} Started`);
    ui.voteResults.innerHTML = '<div class="text-center text-xs text-slate-300 mt-10 italic">Waiting for votes...</div>';
}

function showVoteResults(counts) {
    ui.voteResults.innerHTML = '';
    const max = Math.max(...Object.values(counts));

    Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([name, count]) => {
        const percent = (count / max) * 100;
        const div = document.createElement('div');
        div.className = 'mb-3 pop-in';
        div.innerHTML = `
            <div class="flex justify-between text-xs font-medium text-slate-600 mb-1">
                <span>${name}</span>
                <span>${count}</span>
            </div>
            <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-emerald-500 rounded-full transition-all duration-500" style="width: ${percent}%"></div>
            </div>
        `;
        ui.voteResults.appendChild(div);
    });
}

function handleElimination(name, role, msg) {
    const el = document.getElementById(`player-${name}`);
    if (el) {
        el.querySelector('.avatar-ring').classList.add('dead');
        const status = document.getElementById(`status-${name}`);
        status.className = 'absolute bottom-0 right-0 w-3.5 h-3.5 bg-slate-400 border-2 border-white rounded-full flex items-center justify-center';
        status.innerHTML = '<div class="w-1.5 h-0.5 bg-white"></div>'; // Minus icon
    }

    // Banner in chat
    const div = document.createElement('div');
    const isSpy = role.toLowerCase() === 'spy';
    const color = isSpy ? 'emerald' : 'red';

    div.className = `mx-10 my-4 p-4 rounded-xl border-l-4 border-${color}-500 bg-${color}-50 flex flex-col items-center text-center pop-in`;
    div.innerHTML = `
        <div class="text-xs font-bold text-${color}-600 uppercase tracking-widest mb-1">Player Eliminated</div>
        <div class="text-lg font-bold text-slate-800">${name}</div>
        <div class="text-xs text-slate-500 mt-1">Role: <span class="font-bold uppercase text-slate-700">${role}</span></div>
        ${msg ? `<div class="mt-3 text-sm italic text-slate-600 before:content-['“'] after:content-['”']">${msg}</div>` : ''}
    `;
    ui.feed.appendChild(div);
    scrollToBottom();
}

function showGameResult(winner) {
    const isCiv = winner === 'civilian';
    const title = isCiv ? 'Civilian Victory' : 'Spy Victory';
    const bg = isCiv ? 'bg-emerald-500' : 'bg-rose-500';

    const div = document.createElement('div');
    div.className = 'fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm pop-in';
    div.innerHTML = `
        <div class="bg-white p-8 rounded-2xl shadow-2xl max-w-sm w-full text-center">
            <div class="w-20 h-20 ${bg} rounded-full flex items-center justify-center text-4xl mb-4 mx-auto shadow-lg text-white">
                ${isCiv ? '🛡️' : '🎭'}
            </div>
            <h2 class="text-2xl font-bold text-slate-800 mb-2">${title}</h2>
            <p class="text-slate-500 text-sm mb-6">The undercover operation has ended.</p>
            <button onclick="location.reload()" class="w-full py-3 bg-slate-900 text-white rounded-xl font-bold hover:scale-105 transition-transform">Play Again</button>
        </div>
    `;
    document.body.appendChild(div);

    ui.status.textContent = 'FINISHED';
    ui.status.className = 'px-3 py-1 bg-slate-200 text-slate-500 rounded-full text-xs font-bold uppercase tracking-wider';
    ui.startBtn.disabled = false;
    ui.startBtn.textContent = 'Start New Game';
}

function updateAliveCount(total, current) {
    ui.aliveBadge.textContent = `${current}/${total} Alive`;
}

function scrollToBottom() {
    ui.feed.scrollTop = ui.feed.scrollHeight;
}

let selectedPokemon = [];
let currentBattleId = null;
let pRoster = []; 
let pMoves = [];  
let pActiveIdx = 0; // <--- THE FIX: Track the true active index
let isProcessingTurn = false;
let forcedSwitchMode = false;

window.onload = async () => {
    const teamsRes = await fetch('/api/legacy_teams');
    const teams = await teamsRes.json();
    
    const select = document.getElementById('opponent-select');
    
    // --- THE FIX: Inject Random Team option at the very top ---
    select.innerHTML = `<option value="Random Team">Random Team</option>`;
    
    // Then load the rest of the Legacy teams
    teams.forEach(team => select.innerHTML += `<option value="${team}">${team}</option>`);

    const dexRes = await fetch('/api/pokedex');
    const pokedex = await dexRes.json();
    pokedex.forEach(p => {
        const card = document.createElement('div');
        card.className = 'poke-card';
        card.innerHTML = `<img src="/sprites/front/${p.id}.png" width="80"><br><small>${p.name}</small>`;
        card.onclick = () => toggleSelection(p.name, card);
        document.getElementById('pokedex-grid').appendChild(card);
    });
};

function toggleSelection(name, card) {
    if (selectedPokemon.includes(name)) {
        selectedPokemon = selectedPokemon.filter(n => n !== name);
        card.classList.remove('selected');
    } else if (selectedPokemon.length < 6) {
        selectedPokemon.push(name);
        card.classList.add('selected');
    }
    document.getElementById('draft-count').innerText = `Selected: ${selectedPokemon.length} / 6`;
}

async function startBattle() {
    if (selectedPokemon.length !== 6) return alert("Select exactly 6 Pokemon!");
    
    const opponent = document.getElementById('opponent-select').value;
    const res = await fetch('/api/start_battle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_team_names: selectedPokemon, opponent_name: opponent })
    });
    const data = await res.json();
    currentBattleId = data.battle_id;
    
    document.getElementById('lobby-screen').style.display = 'none';
    document.getElementById('ds-screen').style.display = 'block';
    
    // Fetch initial state safely
    await submitAction("init", 0);
}

function setMenuState(state) {
    const ctrl = document.getElementById('control-box');
    const msg = document.getElementById('msg-box');
    const switchLayer = document.getElementById('switch-layer');
    
    ctrl.innerHTML = '';
    switchLayer.style.display = 'none';

    if (state === 'main') {
        const activePoke = pRoster[pActiveIdx]; // Safely grab the active Pokemon
        msg.innerText = `What will ${activePoke ? activePoke.name : "you"} do?`;
        ctrl.innerHTML = `
            <button class="btn-fight" onclick="setMenuState('fight')">FIGHT</button>
            <button class="btn-switch" onclick="setMenuState('switch')">SWITCH</button>
        `;
    } 
    else if (state === 'fight') {
        msg.innerText = "";
        pMoves.forEach((m, idx) => {
            ctrl.innerHTML += `<button onclick="submitAction('attack', ${idx})">${m.name}<br><small>${m.type}</small></button>`;
        });
        ctrl.innerHTML += `<button class="btn-back" onclick="setMenuState('main')" style="grid-column: span 2;">BACK</button>`;
    } 
    else if (state === 'switch') {
        switchLayer.style.display = 'block';
        document.getElementById('switch-back-btn').style.display = forcedSwitchMode ? 'none' : 'block';
        
        const grid = document.getElementById('party-grid');
        grid.innerHTML = '';
        pRoster.forEach((p, idx) => {
            const isActive = (idx === pActiveIdx); // Safely identify who is on the field
            const btn = document.createElement('div');
            btn.className = `party-btn ${p.fainted ? 'fainted' : ''} ${isActive ? 'active' : ''}`;
            btn.innerHTML = `<strong>${p.name}</strong> ${p.status ? '['+p.status+']' : ''}<br><small>HP: ${p.hp}/${p.max}</small>`;
            
            if (!p.fainted && !isActive) {
                btn.onclick = () => {
                    switchLayer.style.display = 'none';
                    submitAction(forcedSwitchMode ? "forced_switch" : "switch", idx);
                };
            }
            grid.appendChild(btn);
        });
    }
}

function drawSnapshot(event) {
    document.getElementById('ml-tracker').innerText = `ML Win Prob: ${event.ml_prob}%`;
    document.getElementById('msg-box').innerText = event.text;

    const pStatus = event.p.status ? ` [${event.p.status}]` : "";
    document.getElementById('p-name').innerText = event.p.name + pStatus;
    document.getElementById('p-sprite').style.display = event.p.fainted ? 'none' : 'block';
    document.getElementById('p-sprite').src = `/sprites/back/${event.p.id}.png`;
    
    document.getElementById('p-hp-txt').innerText = `${event.p.hp} / ${event.p.max}`;
    const pPct = event.p.hp / event.p.max;
    const pFill = document.getElementById('p-hp-fill');
    pFill.style.width = `${pPct * 100}%`;
    pFill.style.background = pPct > 0.5 ? '#32c832' : pPct > 0.2 ? '#dcc800' : '#dc3232';

    const eStatus = event.e.status ? ` [${event.e.status}]` : "";
    document.getElementById('e-name').innerText = event.e.name + eStatus;
    document.getElementById('e-sprite').style.display = event.e.fainted ? 'none' : 'block';
    document.getElementById('e-sprite').src = `/sprites/front/${event.e.id}.png`;
    
    const ePct = event.e.hp / event.e.max;
    const eFill = document.getElementById('e-hp-fill');
    eFill.style.width = `${ePct * 100}%`;
    eFill.style.background = ePct > 0.5 ? '#32c832' : ePct > 0.2 ? '#dcc800' : '#dc3232';
}

async function submitAction(actionType, targetIdx) {
    if (isProcessingTurn) return;
    isProcessingTurn = true;
    
    document.getElementById('control-box').innerHTML = '';

    const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ battle_id: currentBattleId, action_type: actionType, target_idx: targetIdx })
    });
    
    const data = await res.json();
    const events = data.events;
    
    for (let i = 0; i < events.length; i++) {
        drawSnapshot(events[i]);
        
        pMoves = events[i].p_moves;
        pRoster = events[i].p_roster;
        pActiveIdx = events[i].p_active_idx; // Update the true active index from the backend
        
        if (events[i].game_over) {
            document.getElementById('msg-box').innerText = "BATTLE OVER!";
            return;
        }
        
        await new Promise(r => setTimeout(r, 1500)); 
    }
    
    forcedSwitchMode = data.require_switch;
    if (forcedSwitchMode) {
        setMenuState('switch');
    } else {
        setMenuState('main');
    }
    
    isProcessingTurn = false;
}
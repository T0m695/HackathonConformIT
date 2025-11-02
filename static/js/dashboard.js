let categoryChart = null;
let monthlyChart = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadMetrics();
    setupChat();
    setupSuggestions();
    setupMonthlyDurationChange();
    setupVoiceInput();
    
    // Refresh metrics every 30 seconds
    setInterval(() => loadMetrics(), 30000);
});

function setupMonthlyDurationChange() {
    const durationSelect = document.getElementById('monthlyDuration');
    if (durationSelect) {
        durationSelect.addEventListener('change', (e) => {
            const duration = parseInt(e.target.value);
            console.log(`🔄 Changement de durée: ${duration} mois`);
            loadMetrics(duration);
        });
    }
}

async function loadMetrics(duration = null) {
    try {
        // Get duration from selector if not provided
        if (!duration) {
            const durationSelect = document.getElementById('monthlyDuration');
            duration = durationSelect ? parseInt(durationSelect.value) : 12;
        }
        
        console.log(`📊 Chargement des métriques pour ${duration} mois`);
        const response = await fetch(`/api/metrics?duration=${duration}`);
        const data = await response.json();
        
        // Update metric cards
        document.getElementById('totalEvents').textContent = data.total_events;
        document.getElementById('totalCategories').textContent = data.categories.length;
        
        // Update charts
        updateCategoryChart(data.categories);
        updateMonthlyChart(data.monthly_stats);
        
        // Update recent events
        updateRecentEvents(data.recent_events);
        
        console.log(`✅ Métriques mises à jour avec succès`);
        
    } catch (error) {
        console.error('❌ Erreur chargement métriques:', error);
    }
}

function updateCategoryChart(categories) {
    const ctx = document.getElementById('categoryChart');
    
    if (categoryChart) {
        categoryChart.destroy();
    }
    
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories.map(c => c.name),
            datasets: [{
                data: categories.map(c => c.count),
                backgroundColor: [
                    '#2563eb', '#10b981', '#f59e0b', '#ef4444', 
                    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function updateMonthlyChart(monthlyStats) {
    const ctx = document.getElementById('monthlyChart');
    
    if (monthlyChart) {
        console.log('🔄 Destruction de l\'ancien graphique mensuel');
        monthlyChart.destroy();
    }
    
    console.log(`📈 Création du graphique avec ${monthlyStats.length} points de données`);
    
    monthlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: monthlyStats.map(m => m.month).reverse(),
            datasets: [{
                label: 'Événements',
                data: monthlyStats.map(m => m.count).reverse(),
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
    
    console.log('✅ Graphique mensuel créé avec succès');
}

function updateRecentEvents(events) {
    const container = document.getElementById('recentEventsList');
    container.innerHTML = events.map(event => `
        <a href="/event/${event.id}" class="event-item event-link">
            <h4>${event.titre}</h4>
            <p>📅 ${event.date} | 📍 ${event.lieu} | 🏷️ ${event.categorie}</p>
            ${event.nb_mesures > 0 ? `<p class="measures-count">🔧 ${event.nb_mesures} mesure(s) corrective(s)</p>` : ''}
        </a>
    `).join('');
}

function setupChat() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    // Add user message
    addMessage(message, 'user');
    chatInput.value = '';
    
    // Disable input while processing
    const sendButton = document.getElementById('sendButton');
    sendButton.disabled = true;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });
        
        const data = await response.json();
        addMessage(data.response, 'bot');
        
    } catch (error) {
        addMessage('❌ Erreur de connexion. Veuillez réessayer.', 'bot');
        console.error('Erreur chat:', error);
    } finally {
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setupSuggestions() {
    const suggestionButtons = document.querySelectorAll('.suggestion-btn');
    const chatInput = document.getElementById('chatInput');
    
    suggestionButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            chatInput.value = btn.textContent;
            sendMessage();
        });
    });
}

function setupVoiceInput() {
    const voiceButton = document.getElementById('voiceButton');
    
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };
            
            mediaRecorder.onstop = async () => {
                voiceButton.classList.remove('recording');
                showVoiceStatus('⏳ Transcription...', 'transcribing');
                
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                audioChunks = [];
                await transcribeAudio(audioBlob);
            };
        })
        .catch(err => {
            console.error('❌ Micro:', err);
            voiceButton.disabled = true;
        });
    
    voiceButton.addEventListener('click', () => {
        if (!mediaRecorder) return;
        
        if (!isRecording) {
            audioChunks = [];
            mediaRecorder.start();
            isRecording = true;
            voiceButton.classList.add('recording');
            voiceButton.textContent = '⏹️';
            showVoiceStatus('🔴 Enregistrement...', 'recording');
            setTimeout(() => { if (isRecording) stopRecording(); }, 30000);
        } else {
            stopRecording();
        }
    });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        isRecording = false;
        document.getElementById('voiceButton').textContent = '🎤';
    }
}

async function transcribeAudio(audioBlob) {
    try {
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'recording.wav');
        
        const response = await fetch('/api/transcribe-audio', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success && result.transcription) {
            const text = result.transcription.trim();
            document.getElementById('chatInput').value = text;
            showVoiceStatus('✅ "' + text.substring(0, 50) + '..."', 'recording');
            setTimeout(() => hideVoiceStatus(), 3000);
        } else {
            throw new Error(result.error || 'Erreur');
        }
    } catch (error) {
        console.error('❌', error);
        showVoiceStatus('❌ ' + error.message, 'error');
        setTimeout(() => hideVoiceStatus(), 3000);
    }
}

function showVoiceStatus(msg, type) {
    const status = document.getElementById('voiceStatus');
    status.textContent = msg;
    status.className = `voice-status show ${type}`;
}

function hideVoiceStatus() {
    document.getElementById('voiceStatus').className = 'voice-status';
}

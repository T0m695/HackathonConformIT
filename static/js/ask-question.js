let currentChart = null;
let chartHistory = [];
const MAX_CHARTS = 3;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

document.addEventListener('DOMContentLoaded', () => {
    setupChat();
    setupSuggestions();
    loadChartHistory();
    setupVoiceInput();
});

function setupChat() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    
    sendButton.addEventListener('click', sendMessage);
    
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });
}

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    // Add user message
    addMessage(message, 'user');
    chatInput.value = '';
    chatInput.style.height = 'auto';
    
    // Disable input while processing
    const sendButton = document.getElementById('sendButton');
    sendButton.disabled = true;
    
    // Show loading indicator
    const loadingId = addLoadingMessage();
    
    // Déterminer si c'est une demande de visualisation
    const isVisualizationQuery = detectVisualizationQuery(message);
    
    try {
        //const endpoint = isVisualizationQuery ? '/api/visualize' : '/api/chat';
        const endpoint = '/api/visualize'; // Forcer l'endpoint de visualisation
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });
        
        const data = await response.json();
        
        // Remove loading indicator
        removeMessage(loadingId);
        
        // Handle response based on type
        if (data.type === 'chart') {
            addChartMessage(data);
            saveChartToHistory(data);
        } else if (data.response) {
            addMessage(data.response, 'bot');
        } else if (data.content) {
            addMessage(data.content, 'bot');
        } else {
            addMessage('Réponse reçue', 'bot');
        }
        
    } catch (error) {
        removeMessage(loadingId);
        addMessage('❌ Erreur de connexion. Veuillez réessayer.', 'bot');
        console.error('Erreur chat:', error);
    } finally {
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function detectVisualizationQuery(message) {
    const vizKeywords = [
        'graphique', 'graph', 'diagramme', 'chart',
        'visualise', 'visualisation', 'affiche',
        'montre-moi', 'montre moi', 'voir',
        'statistique', 'stats', 'distribution',
        'évolution', 'tendance', 'courbe',
        'camembert', 'barres', 'histogramme'
    ];
    
    const lowerMessage = message.toLowerCase();
    return vizKeywords.some(keyword => lowerMessage.includes(keyword));
}

function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    messageDiv.id = `msg-${Date.now()}`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = type === 'bot' ? '🤖' : '👤';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv.id;
}

function addChartMessage(chartData) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message chart-message';
    messageDiv.id = `msg-${Date.now()}`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = '📊';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content chart-content';
    
    // Add title and description
    if (chartData.title) {
        const titleDiv = document.createElement('h3');
        titleDiv.className = 'chart-title';
        titleDiv.textContent = chartData.title;
        contentDiv.appendChild(titleDiv);
    }
    
    if (chartData.description) {
        const descDiv = document.createElement('p');
        descDiv.className = 'chart-description';
        descDiv.textContent = chartData.description;
        contentDiv.appendChild(descDiv);
    }
    
    // Add period badge if filters exist
    if (chartData.filters && (chartData.filters.start_date || chartData.filters.end_date)) {
        const periodBadge = document.createElement('div');
        periodBadge.className = 'period-badge';
        periodBadge.innerHTML = `
            <span class="period-icon">📅</span>
            <span class="period-text">
                ${chartData.filters.start_date} → ${chartData.filters.end_date}
            </span>
        `;
        contentDiv.appendChild(periodBadge);
    }
    
    // Create canvas for chart
    const canvasWrapper = document.createElement('div');
    canvasWrapper.className = 'chart-wrapper';
    
    const canvas = document.createElement('canvas');
    canvas.id = `chart-${Date.now()}`;
    canvas.style.maxHeight = '400px';
    canvasWrapper.appendChild(canvas);
    
    contentDiv.appendChild(canvasWrapper);
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Render chart
    renderChart(canvas, chartData);
    
    return messageDiv.id;
}

function renderChart(canvas, chartData) {
    const ctx = canvas.getContext('2d');
    
    // Determine colors based on chart type
    const colors = generateColors(chartData.data.labels.length);
    
    const config = {
        type: chartData.chart_type,
        data: {
            labels: chartData.data.labels,
            datasets: [{
                label: chartData.title || 'Données',
                data: chartData.data.values,
                backgroundColor: chartData.chart_type === 'line' ? 
                    'rgba(102, 126, 234, 0.2)' : colors.background,
                borderColor: chartData.chart_type === 'line' ?
                    'rgba(102, 126, 234, 1)' : colors.border,
                borderWidth: 2,
                tension: 0.4,
                fill: chartData.chart_type === 'line'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: chartData.chart_type === 'pie' || chartData.chart_type === 'doughnut',
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y || context.parsed;
                            return label;
                        }
                    }
                }
            },
            scales: chartData.chart_type === 'line' || chartData.chart_type === 'bar' ? {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            } : {}
        }
    };
    
    // Create chart instance and store reference
    const chartInstance = new Chart(ctx, config);
    canvas.chartInstance = chartInstance;
}

function generateColors(count) {
    const baseColors = [
        '#2563eb', '#10b981', '#f59e0b', '#ef4444', 
        '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
        '#06b6d4', '#84cc16', '#f43f5e', '#6366f1'
    ];
    
    const background = [];
    const border = [];
    
    for (let i = 0; i < count; i++) {
        const color = baseColors[i % baseColors.length];
        background.push(color + '80'); // 50% opacity
        border.push(color);
    }
    
    return { background, border };
}

function addLoadingMessage() {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    const loadingId = `loading-${Date.now()}`;
    messageDiv.className = 'message bot-message';
    messageDiv.id = loadingId;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.textContent = '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return loadingId;
}

function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

function setupSuggestions() {
    const suggestionCards = document.querySelectorAll('.suggestion-card');
    const chatInput = document.getElementById('chatInput');
    
    suggestionCards.forEach(card => {
        card.addEventListener('click', () => {
            const text = card.querySelector('.suggestion-text').textContent;
            chatInput.value = text;
            chatInput.focus();
            sendMessage();
        });
    });
}

function setupVoiceInput() {
    const voiceButton = document.getElementById('voiceButton');
    
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
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
        const response = await fetch('/api/transcribe-audio', { method: 'POST', body: formData });
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

// Gestion de l'historique des graphiques
function saveChartToHistory(chartData) {
    // Ajouter au début du tableau
    chartHistory.unshift({
        ...chartData,
        timestamp: Date.now()
    });
    
    // Garder seulement les 3 derniers
    if (chartHistory.length > MAX_CHARTS) {
        chartHistory = chartHistory.slice(0, MAX_CHARTS);
    }
    
    // Sauvegarder dans localStorage
    try {
        localStorage.setItem('chartHistory', JSON.stringify(chartHistory));
    } catch (e) {
        console.warn('Impossible de sauvegarder l\'historique:', e);
    }
    
    // Mettre à jour l'affichage de l'historique
    updateChartHistoryDisplay();
}

function loadChartHistory() {
    try {
        const saved = localStorage.getItem('chartHistory');
        if (saved) {
            chartHistory = JSON.parse(saved);
            updateChartHistoryDisplay();
        }
    } catch (e) {
        console.warn('Impossible de charger l\'historique:', e);
        chartHistory = [];
    }
}

function updateChartHistoryDisplay() {
    const historyContainer = document.getElementById('chartHistoryContainer');
    if (!historyContainer) return;
    
    if (chartHistory.length === 0) {
        historyContainer.innerHTML = `
            <div class="history-empty">
                <span class="empty-icon">📊</span>
                <p>Aucun graphique dans l'historique</p>
                <p class="empty-hint">Demandez une visualisation pour commencer!</p>
            </div>
        `;
        return;
    }
    
    historyContainer.innerHTML = chartHistory.map((chart, index) => `
        <div class="history-chart-card" data-index="${index}">
            <div class="history-chart-header">
                <h4 class="history-chart-title">${chart.title}</h4>
                <button class="history-chart-restore" onclick="restoreChart(${index})" title="Recharger ce graphique">
                    🔄
                </button>
            </div>
            <div class="history-chart-meta">
                <span class="history-chart-type">${getChartTypeIcon(chart.chart_type)} ${getChartTypeName(chart.chart_type)}</span>
                ${chart.filters && chart.filters.start_date ? `
                    <span class="history-chart-period">📅 ${chart.filters.start_date} → ${chart.filters.end_date}</span>
                ` : ''}
            </div>
            <div class="history-chart-preview">
                <canvas id="history-chart-${index}" class="history-canvas"></canvas>
            </div>
        </div>
    `).join('');
    
    // Rendre les graphiques miniatures
    chartHistory.forEach((chart, index) => {
        const canvas = document.getElementById(`history-chart-${index}`);
        if (canvas) {
            renderMiniChart(canvas, chart);
        }
    });
}

function renderMiniChart(canvas, chartData) {
    const ctx = canvas.getContext('2d');
    const colors = generateColors(chartData.data.labels.length);
    
    new Chart(ctx, {
        type: chartData.chart_type,
        data: {
            labels: chartData.data.labels,
            datasets: [{
                data: chartData.data.values,
                backgroundColor: chartData.chart_type === 'line' ? 
                    'rgba(102, 126, 234, 0.2)' : colors.background,
                borderColor: chartData.chart_type === 'line' ?
                    'rgba(102, 126, 234, 1)' : colors.border,
                borderWidth: 1,
                tension: 0.4,
                fill: chartData.chart_type === 'line'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: chartData.chart_type === 'line' || chartData.chart_type === 'bar' ? {
                x: { display: false },
                y: { display: false }
            } : {}
        }
    });
}

function restoreChart(index) {
    const chart = chartHistory[index];
    if (chart) {
        addChartMessage(chart);
        
        // Scroll vers le bas du chat
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function getChartTypeIcon(type) {
    const icons = {
        'bar': '📊',
        'line': '📈',
        'pie': '🥧',
        'doughnut': '🍩',
        'scatter': '📍'
    };
    return icons[type] || '📊';
}

function getChartTypeName(type) {
    const names = {
        'bar': 'Barres',
        'line': 'Lignes',
        'pie': 'Circulaire',
        'doughnut': 'Anneau',
        'scatter': 'Nuage de points'
    };
    return names[type] || type;
}

function clearChartHistory() {
    if (confirm('Voulez-vous vraiment effacer l\'historique des graphiques?')) {
        chartHistory = [];
        localStorage.removeItem('chartHistory');
        updateChartHistoryDisplay();
    }
}

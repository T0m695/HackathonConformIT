let currentChart = null;

document.addEventListener('DOMContentLoaded', () => {
    setupChat();
    setupSuggestions();
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
        const endpoint = isVisualizationQuery ? '/api/visualize' : '/api/chat';
        
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
    // Destroy previous chart if exists
    if (currentChart) {
        currentChart.destroy();
    }
    
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
    
    currentChart = new Chart(ctx, config);
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

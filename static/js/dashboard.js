let categoryChart = null;
let monthlyChart = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadMetrics();
    setupChat();
    setupSuggestions();
    
    // Refresh metrics every 30 seconds
    setInterval(loadMetrics, 30000);
});

async function loadMetrics() {
    try {
        const response = await fetch('/api/metrics');
        const data = await response.json();
        
        // Update metric cards
        document.getElementById('totalEvents').textContent = data.total_events;
        document.getElementById('totalCategories').textContent = data.categories.length;
        
        // Update charts
        updateCategoryChart(data.categories);
        updateMonthlyChart(data.monthly_stats);
        
        // Update recent events
        updateRecentEvents(data.recent_events);
        
    } catch (error) {
        console.error('Erreur chargement métriques:', error);
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
        monthlyChart.destroy();
    }
    
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
                    beginAtZero: true
                }
            }
        }
    });
}

function updateRecentEvents(events) {
    const container = document.getElementById('recentEventsList');
    container.innerHTML = events.map(event => `
        <div class="event-item">
            <h4>${event.titre}</h4>
            <p>📅 ${event.date} | 📍 ${event.lieu} | 🏷️ ${event.categorie}</p>
        </div>
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

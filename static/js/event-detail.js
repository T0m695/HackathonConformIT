document.addEventListener('DOMContentLoaded', () => {
    const eventId = getEventIdFromUrl();
    if (eventId) {
        loadEventDetails(eventId);
    } else {
        showError('ID d\'événement manquant');
    }
});

function getEventIdFromUrl() {
    const path = window.location.pathname;
    const match = path.match(/\/event\/(\d+)/);
    return match ? match[1] : null;
}

async function loadEventDetails(eventId) {
    try {
        const response = await fetch(`/api/event/${eventId}`);
        if (!response.ok) {
            throw new Error('Événement non trouvé');
        }
        
        const event = await response.json();
        displayEventDetails(event);
        
    } catch (error) {
        showError(error.message);
    }
}

function displayEventDetails(event) {
    const container = document.getElementById('eventDetailContainer');
    
    const measuresHtml = event.mesures_correctives && event.mesures_correctives.length > 0
        ? `
            <div class="section">
                <h3>🔧 Mesures correctives associées</h3>
                <div class="measures-list">
                    ${event.mesures_correctives.map(mesure => `
                        <div class="measure-card">
                            <h4>${mesure.name}</h4>
                            <p class="measure-description">${mesure.description || 'Description non disponible'}</p>
                            <div class="measure-meta">
                                <span>📅 Date d'implémentation: ${mesure.implementation_date || 'N/A'}</span>
                                <span>💰 Coût: ${mesure.cost ? mesure.cost + ' $' : 'N/A'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `
        : '<div class="section"><p class="no-measures">Aucune mesure corrective associée</p></div>';
    
    // Déterminer la classe CSS pour la gravité
    const getSeverityClass = (gravite) => {
        const g = gravite.toLowerCase();
        if (g.includes('faible') || g.includes('low') || g === '1') return 'severity-low';
        if (g.includes('moyen') || g.includes('medium') || g === '2') return 'severity-medium';
        if (g.includes('élevé') || g.includes('high') || g.includes('grave') || g === '3') return 'severity-high';
        return 'severity-unknown';
    };
    
    // Déterminer la classe CSS pour la probabilité
    const getProbabilityClass = (probabilite) => {
        const p = probabilite.toLowerCase();
        if (p.includes('faible') || p.includes('low') || p === '1') return 'severity-low';
        if (p.includes('moyen') || p.includes('medium') || p === '2') return 'severity-medium';
        if (p.includes('élevé') || p.includes('high') || p === '3') return 'severity-high';
        return 'severity-unknown';
    };
    
    container.innerHTML = `
        <div class="event-header">
            <div>
                <h2>${event.titre}</h2>
                <span class="status-badge ${event.en_cours ? 'status-ongoing' : 'status-resolved'}">
                    ${event.en_cours ? '⏳ En cours' : '✅ Résolu'}
                </span>
            </div>
            <span class="event-badge">${event.categorie || 'Non classé'}</span>
        </div>
        
        <div class="event-info-grid">
            <div class="info-item">
                <span class="info-label">📅 Date</span>
                <span class="info-value">${event.date}</span>
            </div>
            <div class="info-item">
                <span class="info-label">🔄 Statut</span>
                <span class="info-value">${event.statut}</span>
            </div>
            <div class="info-item">
                <span class="info-label">📍 Lieu</span>
                <span class="info-value">${event.lieu}</span>
            </div>
            <div class="info-item">
                <span class="info-label">🏷️ Catégorie</span>
                <span class="info-value">${event.categorie || 'Non spécifiée'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">👤 Déclaré par</span>
                <span class="info-value">${event.personne}</span>
            </div>
            <div class="info-item">
                <span class="info-label">⚠️ Risque associé</span>
                <span class="info-value">${event.risque}</span>
            </div>
            <div class="info-item">
                <span class="info-label">📊 Gravité</span>
                <span class="info-value severity-badge ${getSeverityClass(event.gravite)}">${event.gravite}</span>
            </div>
            <div class="info-item">
                <span class="info-label">🎲 Probabilité</span>
                <span class="info-value severity-badge ${getProbabilityClass(event.probabilite)}">${event.probabilite}</span>
            </div>
        </div>
        
        <div class="section">
            <h3>📝 Description de l'événement</h3>
            <p class="event-description">${event.description}</p>
        </div>
        
        ${measuresHtml}
    `;
}

function showError(message) {
    const container = document.getElementById('eventDetailContainer');
    container.innerHTML = `
        <div class="error-container">
            <div class="error-icon">⚠️</div>
            <h2>Erreur</h2>
            <p>${message}</p>
            <a href="/" class="btn-primary">Retour au tableau de bord</a>
        </div>
    `;
}

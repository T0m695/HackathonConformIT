document.addEventListener('DOMContentLoaded', () => {
    loadDuplicates();
    setupEventListeners();
});

function setupEventListeners() {
    const refreshBtn = document.getElementById('refreshButton');
    const applyFiltersBtn = document.getElementById('applyFilters');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadDuplicates);
    }
    
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', applyFilters);
    }
}

async function loadDuplicates() {
    const container = document.getElementById('duplicatesContainer');
    
    container.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Chargement des doublons...</p>
        </div>
    `;
    
    try {
        // Récupérer les valeurs des filtres
        const dateRange = document.getElementById('dateFilter').value;
        
        const url = `/api/duplicates${dateRange !== 'all' ? '?date_range=' + dateRange : ''}`;
        const response = await fetch(url);
        const data = await response.json();
        
        updateStats(data.stats);
        displayDuplicates(data.groups);
        
    } catch (error) {
        console.error('Erreur lors du chargement des doublons:', error);
        showError();
    }
}

function updateStats(stats) {
    document.getElementById('totalGroups').textContent = stats.total_groups;
    document.getElementById('totalDuplicates').textContent = stats.total_duplicates;
    document.getElementById('toReview').textContent = stats.to_review;
}

function displayDuplicates(groups) {
    const container = document.getElementById('duplicatesContainer');
    
    if (!groups || groups.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">✨</div>
                <h3>Aucun doublon détecté</h3>
                <p>Félicitations! Aucun événement en doublon n'a été trouvé avec les critères sélectionnés.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = groups.map(group => {
        const eventIds = group.events.map(e => e.id);
        return `
        <div class="duplicate-group">
            <div class="group-header">
                <div class="group-title">
                    <h3>Groupe #${group.group_id}</h3>
                    <span class="similarity-badge ${getSimilarityClass(group.similarity)}">
                        ${Math.round(group.similarity * 100)}% similaire
                    </span>
                </div>
                <div class="group-actions">
                    <button class="btn-action btn-merge" onclick='mergeGroup(${JSON.stringify(eventIds)})'>
                        Fusionner
                    </button>
                    <button class="btn-action btn-dismiss" onclick='dismissGroup(${JSON.stringify(eventIds)})'>
                        Ignorer
                    </button>
                </div>
            </div>
            <div class="duplicate-events">
                ${group.events.map(event => `
                    <div class="event-card" data-event-id="${event.id}">
                        <div class="event-card-header">
                            <div>
                                <h4 class="event-title">${escapeHtml(event.titre)}</h4>
                                <div class="event-id">ID: ${event.id}</div>
                            </div>
                            <span class="event-badge">${escapeHtml(event.categorie || 'N/A')}</span>
                        </div>
                        <p class="event-description">${escapeHtml(event.description)}</p>
                        <div class="event-meta">
                            <span>📅 ${event.date}</span>
                            <span>📍 ${escapeHtml(event.lieu)}</span>
                            ${event.nb_mesures > 0 ? `<span>🔧 ${event.nb_mesures} mesure(s)</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
        `;
    }).join('');
}

function getSimilarityClass(similarity) {
    if (similarity >= 0.95) return 'very-high';
    if (similarity >= 0.85) return 'high';
    return '';
}

function applyFilters() {
    const status = document.getElementById('statusFilter').value;
    const date = document.getElementById('dateFilter').value;
    
    console.log('Filtres appliqués:', { status, date });
    loadDuplicates(); // Recharger avec les filtres
}

async function mergeGroup(eventIds) {
    if (!eventIds || eventIds.length < 2) {
        alert("Il faut au moins 2 événements pour fusionner");
        return;
    }
    
    // Demander quel événement conserver
    const keepId = prompt(
        `Entrez l'ID de l'événement à conserver parmi: ${eventIds.join(', ')}`,
        eventIds[0]
    );
    
    if (!keepId) return;
    
    const keepIdNum = parseInt(keepId);
    if (!eventIds.includes(keepIdNum)) {
        alert("L'ID spécifié n'est pas dans le groupe");
        return;
    }
    
    if (!confirm(`Êtes-vous sûr de vouloir fusionner ${eventIds.length} événements?\nL'événement ${keepIdNum} sera conservé, les autres seront supprimés.`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/duplicates/merge', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                event_ids: eventIds,
                keep_id: keepIdNum
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('✅ ' + data.message);
            loadDuplicates(); // Recharger la liste
        } else {
            alert('❌ Erreur: ' + (data.detail || 'Échec de la fusion'));
        }
        
    } catch (error) {
        console.error('Erreur fusion:', error);
        alert('❌ Erreur lors de la fusion');
    }
}

function reviewGroup(groupId) {
    // TODO: Ouvrir une interface de révision détaillée
    alert(`Fonctionnalité de révision en cours de développement pour le groupe #${groupId}`);
}

async function dismissGroup(eventIds) {
    if (!confirm(`Êtes-vous sûr de vouloir ignorer ce groupe de ${eventIds.length} événement(s)?\nIls ne seront plus détectés comme doublons.`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/duplicates/dismiss', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                event_ids: eventIds
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('✅ ' + data.message);
            loadDuplicates(); // Recharger la liste
        } else {
            alert('❌ Erreur: ' + (data.detail || 'Échec de l\'action'));
        }
        
    } catch (error) {
        console.error('Erreur dismiss:', error);
        alert('❌ Erreur lors de l\'action');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError() {
    const container = document.getElementById('duplicatesContainer');
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <h3>Erreur de chargement</h3>
            <p>Impossible de charger les doublons. Veuillez réessayer.</p>
            <button class="btn-apply-filters" onclick="loadDuplicates()">Réessayer</button>
        </div>
    `;
}

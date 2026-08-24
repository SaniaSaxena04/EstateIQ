async function searchProperties() {
    const queryInput = document.getElementById("query");
    const maxPriceInput = document.getElementById("max_price");
    const bedroomsInput = document.getElementById("bedrooms");
    const container = document.getElementById("results");

    if (!container) return;

    const query = queryInput ? queryInput.value : "";
    const max_price = maxPriceInput ? maxPriceInput.value : "";
    const bedrooms = bedroomsInput ? bedroomsInput.value : "";

    container.innerHTML = "<p>Searching properties...</p>";

    try {
        const res = await fetch("/search-properties", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, max_price, bedrooms })
        });

        if (!res.ok) {
            throw new Error(`Server returned status ${res.status}`);
        }

        const data = await res.json();
        container.innerHTML = "";

        if (!data.properties || data.properties.length === 0) {
            container.innerHTML = "<p>No matching properties found.</p>";
            return;
        }

        data.properties.forEach(p => {
            const priceFormatted = p.price ? p.price.toLocaleString() : "N/A";
            const matchScore = p.match_score !== undefined ? p.match_score : (p.similarity_score ? (p.similarity_score * 100).toFixed(0) : "N/A");
            const insight = p.price_insight || "";

            container.innerHTML += `
                <div class="card" style="margin-top: 15px;">
                    <h3>${p.title || 'Property Listing'}</h3>
                    <p><strong>Location:</strong> ${p.locality || ''}, ${p.city || ''}</p>
                    <p><strong>Price:</strong> ₹${priceFormatted}</p>
                    <p><strong>Match Score:</strong> ${matchScore}%</p>
                    ${insight ? `<p><em>${insight}</em></p>` : ''}
                    <a href="/property/${p.property_id}" class="btn" style="display:inline-block; margin-top:10px;">View Details</a>
                </div>
            `;
        });
    } catch (err) {
        console.error("Search Error:", err);
        container.innerHTML = `<p style="color:red;">Error searching properties. Please try again.</p>`;
    }
}

async function loadSimilar(propId) {
    const container = document.getElementById("similar-results");
    if (!container) return;

    container.innerHTML = "<p>Finding similar properties...</p>";

    try {
        const res = await fetch("/similar-properties", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ property_id: propId })
        });

        if (!res.ok) {
            throw new Error(`Server returned status ${res.status}`);
        }

        const data = await res.json();
        container.innerHTML = "";

        if (!data.similar || data.similar.length === 0) {
            container.innerHTML = "<p>No similar properties found.</p>";
            return;
        }

        data.similar.forEach(p => {
            const priceFormatted = p.price ? p.price.toLocaleString() : "N/A";
            const similarity = p.similarity_score ? (p.similarity_score * 100).toFixed(1) : "N/A";

            container.innerHTML += `
                <div class="card" style="margin-top: 10px;">
                    <h4>${p.title || 'Property'}</h4>
                    <p>Price: ₹${priceFormatted}</p>
                    <p>Similarity: ${similarity}%</p>
                    <a href="/property/${p.property_id}">View Details</a>
                </div>
            `;
        });
    } catch (err) {
        console.error("Similar Properties Error:", err);
        container.innerHTML = `<p style="color:red;">Failed to load similar properties.</p>`;
    }
}

async function sendChatMessage() {
    const input = document.getElementById("chat-input");
    const chatBox = document.getElementById("chat-box");
    
    if (!input || !chatBox) return;

    const msg = input.value.trim();
    if (!msg) return;

    chatBox.innerHTML += `<p><strong>You:</strong> ${msg}</p>`;
    input.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const res = await fetch("/ai-assistant", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg })
        });

        if (!res.ok) {
            throw new Error(`Server returned status ${res.status}`);
        }

        const data = await res.json();
        chatBox.innerHTML += `<p><strong>AI:</strong> ${data.response}</p>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (err) {
        console.error("Chat Error:", err);
        chatBox.innerHTML += `<p style="color:red;"><strong>AI:</strong> Unable to connect to assistant service.</p>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}
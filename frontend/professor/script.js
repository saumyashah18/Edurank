const API_BASE = "http://localhost:8000";

document.addEventListener('DOMContentLoaded', () => {
    setupUI();
    fetchPendingQuestions();
});

function setupUI() {
    const browseBtn = document.getElementById('browse-btn');
    const fileInput = document.getElementById('file-input');
    const generateBtn = document.getElementById('generate-btn');
    const dropArea = document.getElementById('drop-area');

    browseBtn.addEventListener('click', () => fileInput.click());
    dropArea.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });

    fileInput.addEventListener('change', handleFileUpload);
    generateBtn.addEventListener('click', handleGenerate);

    // Simulation Controls
    document.getElementById('sim-next-btn').addEventListener('click', fetchNextSimQuestion);
    document.getElementById('sim-like-btn').addEventListener('click', () => rankSimQuestion('like'));
    document.getElementById('sim-dislike-btn').addEventListener('click', () => rankSimQuestion('dislike'));
    document.getElementById('sim-send-btn').addEventListener('click', handleStudentResponse);

    // Initial state: Waiting for content generation (No auto-fetch)
}

let currentSimQuestionId = null;
let seenQuestionIds = [];

async function fetchNextSimQuestion() {
    const history = document.getElementById('sim-chat-history');
    const inputWrapper = document.getElementById('sim-input-wrapper');
    const actionsPanel = document.getElementById('sim-actions-panel');

    inputWrapper.style.display = 'none';
    actionsPanel.style.display = 'none';

    history.innerHTML += `<div class="chat-bubble bot-bubble">🤖 Looking for fresh topics in your syllabus...</div>`;
    history.scrollTop = history.scrollHeight;

    try {
        const excludeStr = seenQuestionIds.join(",");
        console.log("[DEBUG] Fetching next simulation question. Excluded IDs:", excludeStr);

        const response = await fetch(`${API_BASE}/professor/simulate/next?course_id=1&exclude_ids=${excludeStr}`);
        if (!response.ok) throw new Error("No questions available");

        const q = await response.json();

        if (q.reset) {
            console.log("[DEBUG] Variety cycle complete. Resetting seen history.");
            seenQuestionIds = [];
            history.innerHTML += `<div class="chat-bubble bot-bubble">🔄 I've shown you all available topics. Starting a new variety cycle now!</div>`;
            return fetchNextSimQuestion();
        }

        currentSimQuestionId = q.id;
        if (!seenQuestionIds.includes(q.id)) {
            seenQuestionIds.push(q.id);
        }


        // Clear previous "Thinking" message
        if (history.lastElementChild.innerText.includes("Looking for")) {
            history.lastElementChild.remove();
        }

        history.innerHTML += `
            <div class="chat-bubble bot-bubble">
                <small style="opacity: 0.6; display: block; margin-bottom: 4px;">Topic: ${q.context || 'General'}</small>
                <strong>Bot (${q.status.toUpperCase()}):</strong><br>
                ${q.text}
            </div>
        `;

        inputWrapper.style.display = 'flex';
        history.scrollTop = history.scrollHeight;
    } catch (err) {
        if (history.lastElementChild && history.lastElementChild.innerText.includes("Looking for")) {
            history.lastElementChild.remove();
        }
        history.innerHTML += `<div class="chat-bubble bot-bubble">No new questions found. Please click 'Generate More' to expand my knowledge!</div>`;
    }
}

function handleStudentResponse() {
    const input = document.getElementById('sim-student-input');
    const history = document.getElementById('sim-chat-history');
    const answer = input.value.trim();

    if (!answer) return;

    // Show student bubble
    history.innerHTML += `<div class="chat-bubble user-bubble">${answer}</div>`;
    input.value = '';

    // Show bot evaluation
    setTimeout(() => {
        history.innerHTML += `<div class="chat-bubble bot-bubble">🤖 Analyzing your answer... (Ranking panels enabled)</div>`;
        document.getElementById('sim-actions-panel').style.display = 'flex';
        history.scrollTop = history.scrollHeight;
    }, 800);

    history.scrollTop = history.scrollHeight;
}

async function rankSimQuestion(action) {
    if (!currentSimQuestionId) return;

    try {
        const response = await fetch(`${API_BASE}/professor/questions/${currentSimQuestionId}/rank?interaction=${action}`, {
            method: 'POST'
        });
        if (response.ok) {
            alert(`Question ranked as ${action}! Finding next variety...`);
            fetchNextSimQuestion();
        }
    } catch (err) {
        alert("Ranking failed");
    }
}


async function handleFileUpload(e) {
    const files = e.target.files;
    if (!files.length) return;

    const fileList = document.getElementById('file-list');
    for (let file of files) {
        const li = document.createElement('li');
        li.className = 'file-item';
        li.innerHTML = `<span>📄 ${file.name}</span> <span class="uploading">Uploading...</span>`;
        fileList.appendChild(li);

        // Actual upload logic
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch(`${API_BASE}/professor/upload/1`, { // Mock course_id
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                li.querySelector('.uploading').innerText = '✅ Ready';
                li.querySelector('.uploading').className = 'ready';
            }
        } catch (err) {
            li.querySelector('.uploading').innerText = '❌ Failed';
        }
    }
}

async function handleGenerate() {
    const name = document.getElementById('exam-name').value;
    const duration = document.getElementById('exam-duration').value;
    const marks = document.getElementById('exam-marks').value;

    if (!name) {
        alert("Please give your assessment a name.");
        return;
    }

    const generateBtn = document.getElementById('generate-btn');
    generateBtn.innerText = "🤖 AI is planning & generating...";
    generateBtn.disabled = true;

    try {
        // Step 1: Create/Save Exam Config
        await fetch(`${API_BASE}/professor/quiz/create?course_id=1&title=${encodeURIComponent(name)}&duration=${duration}&total_marks=${marks}`, {
            method: 'POST'
        });

        // Step 2: Trigger Generation
        const response = await fetch(`${API_BASE}/professor/generate/1?total_marks=${marks}`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            console.log("[AI] Batch generation result:", data);
            generateBtn.innerText = "Generate More";
            generateBtn.disabled = false;

            history.innerHTML += `<div class="chat-bubble bot-bubble">✨ Batch Complete! I've expanded my knowledge across several topics. ${data.details || ''}</div>`;

            fetchPendingQuestions();
            // Trigger simulation start if it's the first time
            if (!currentSimQuestionId) fetchNextSimQuestion();
        }


    } catch (err) {
        alert("Generation failed");
        generateBtn.disabled = false;
        generateBtn.innerText = "Generate Questions";
    }
}


async function fetchPendingQuestions() {
    try {
        console.log("Fetching from:", `${API_BASE}/professor/questions/pending`);
        const response = await fetch(`${API_BASE}/professor/questions/pending`);

        const questions = await response.json();
        renderQuestions(questions);
    } catch (err) {
        console.error("Failed to fetch questions:", err);
    }
}

function renderQuestions(questions) {
    const list = document.getElementById('question-list');
    const emptyState = document.getElementById('status-message');
    const previewHeader = document.querySelector('.preview-header');

    if (questions.length === 0) {
        if (emptyState) emptyState.style.display = 'flex';
        if (previewHeader) previewHeader.style.display = 'none';
        if (list) list.innerHTML = '';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (previewHeader) previewHeader.style.display = 'block';


    list.innerHTML = questions.map(q => `
        <div class="question-card" id="q-${q.id}">
            <div class="input-group">
                <label>AI Generated Question</label>
                <div class="question-text">${q.text}</div>
            </div>
            
            <div class="input-group">
                <label>Ideal Answer (Grounded in Syllabus)</label>
                <div class="ideal-answer-box" style="padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--border-color); font-size: 0.9rem;">
                    ${q.answer}
                </div>
            </div>

            <div class="card-actions">
                <button class="action-btn reject" onclick="reviewQuestion(${q.id}, 'reject')">Reject</button>
                <button class="action-btn edit">Edit</button>
                <button class="action-btn approve" onclick="reviewQuestion(${q.id}, 'approve')">Approve Question</button>
            </div>
        </div>
    `).join('');
}

async function reviewQuestion(id, action) {
    try {
        const response = await fetch(`${API_BASE}/professor/questions/${id}/review?status=${action}`, {
            method: 'POST'
        });
        if (response.ok) {
            document.getElementById(`q-${id}`).style.opacity = '0.5';
            setTimeout(() => {
                document.getElementById(`q-${id}`).remove();
                if (document.getElementById('question-list').children.length === 0) {
                    renderQuestions([]);
                }
            }, 300);
        }
    } catch (err) {
        alert("Action failed");
    }
}

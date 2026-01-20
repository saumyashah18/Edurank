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
    document.getElementById('sim-send-btn').addEventListener('click', handleStudentResponse);

    // Initial state: Waiting for content generation (No auto-fetch)
}

let currentSimQuestionId = null;
let seenQuestionIds = [];

async function fetchNextSimQuestion() {
    const history = document.getElementById('sim-chat-history');
    const inputWrapper = document.getElementById('sim-input-wrapper');

    try {
        const excludeStr = seenQuestionIds.join(",");
        const response = await fetch(`${API_BASE}/professor/simulate/next?course_id=1&exclude_ids=${excludeStr}`);
        if (!response.ok) throw new Error("No questions available");

        const q = await response.json();

        if (q.reset) {
            seenQuestionIds = [];
            history.innerHTML += `<div class="chat-bubble bot-bubble">🔄 Varierty cycle complete. Restarting...</div>`;
            return fetchNextSimQuestion();
        }

        currentSimQuestionId = q.id;
        if (!seenQuestionIds.includes(q.id)) {
            seenQuestionIds.push(q.id);
        }

        const questionHtml = `
            <div class="chat-bubble bot-bubble" id="sim-q-${q.id}">
                <small style="opacity: 0.6; display: block; margin-bottom: 8px;">${q.context || 'General'}</small>
                ${q.text}
                
                <div class="interaction-bar">
                    <button class="icon-action" title="Good Question" onclick="rankSimQuestion('like')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                    </button>
                    <button class="icon-action" title="Bad Question" onclick="rankSimQuestion('dislike')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>
                    </button>
                    <button class="icon-action" title="Regenerate/Next" onclick="fetchNextSimQuestion()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"></path><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                    </button>
                    <button class="icon-action" title="Copy Question" onclick="copyToClipboard('${q.text.replace(/'/g, "\\'")}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                </div>
            </div>
        `;

        history.innerHTML += questionHtml;
        inputWrapper.style.display = 'flex';
        history.scrollTop = history.scrollHeight;
    } catch (err) {
        history.innerHTML += `<div class="chat-bubble bot-bubble">No fresh questions. Click 'Generate' to expand!</div>`;
    }
}

async function handleStudentResponse() {
    const input = document.getElementById('sim-student-input');
    const history = document.getElementById('sim-chat-history');
    const answer = input.value.trim();

    if (!answer) return;

    // Show student bubble
    history.innerHTML += `<div class="chat-bubble user-bubble">${answer}</div>`;
    input.value = '';
    history.scrollTop = history.scrollHeight;

    // Show typing indicator before next question
    showTypingIndicator();

    // Smooth delay for natural feel
    setTimeout(async () => {
        removeTypingIndicator();
        await fetchNextSimQuestion();
    }, 1500);
}

function showTypingIndicator() {
    const history = document.getElementById('sim-chat-history');
    const typingHtml = `
        <div class="chat-bubble bot-bubble typing-bubble" id="typing-indicator">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        </div>
    `;
    history.innerHTML += typingHtml;
    history.scrollTop = history.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert("Question copied to clipboard!");
    });
}


async function rankSimQuestion(action) {
    if (!currentSimQuestionId) return;

    try {
        const response = await fetch(`${API_BASE}/professor/questions/${currentSimQuestionId}/rank?interaction=${action}`, {
            method: 'POST'
        });
        if (response.ok) {
            console.log(`[AI] Question ${currentSimQuestionId} ranked as ${action}`);
            // Voluntary: No automatic fetch here
        }
    } catch (err) {
        console.error("Ranking failed", err);
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
        const instructions = document.getElementById('exam-instructions').value;

        // Step 1: Create/Save Exam Config
        await fetch(`${API_BASE}/professor/quiz/create?course_id=1&title=${encodeURIComponent(name)}&duration=${duration}&total_marks=${marks}&instructions=${encodeURIComponent(instructions)}`, {
            method: 'POST'
        });

        // Step 2: Trigger Generation
        const response = await fetch(`${API_BASE}/professor/generate/1?total_marks=${marks}`, {
            method: 'POST'
        });

        if (response.ok) {
            generateBtn.innerText = "Regenerate More";
            generateBtn.disabled = false;

            // Scroll simulation into view and trigger first question
            document.getElementById('simulation-container').scrollIntoView({ behavior: 'smooth' });
            if (!currentSimQuestionId) fetchNextSimQuestion();
            fetchPendingQuestions();
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

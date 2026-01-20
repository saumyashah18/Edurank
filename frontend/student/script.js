const API_BASE = "http://localhost:8000";
let currentQuizId = null;
let currentQuestionId = 1; // Mocked

document.addEventListener('DOMContentLoaded', () => {
    startQuiz();
    setupSubmission();
});

async function startQuiz() {
    try {
        const response = await fetch(`${API_BASE}/student/quiz/start/1?student_id=123`, {
            method: 'POST'
        });
        const data = await response.json();
        currentQuizId = data.quiz_id;

        // Mocked first question fetch
        document.getElementById('question-display').innerText = "Explain the scheduling criteria for CPU scheduling algorithms.";
    } catch (err) {
        console.error("Quiz init failed");
    }
}

function setupSubmission() {
    const btn = document.getElementById('submit-btn');
    const input = document.getElementById('student-answer');

    btn.addEventListener('click', async () => {
        const answer = input.value;
        if (!answer) return;

        btn.disabled = true;
        btn.innerText = "Evaluating...";

        try {
            const response = await fetch(`${API_BASE}/student/quiz/${currentQuizId}/submit?question_id=${currentQuestionId}&student_id=123&answer=${encodeURIComponent(answer)}`, {
                method: 'POST'
            });

            if (response.ok) {
                // In a real quiz, we would fetch the NEXT question or finish
                showFinish();
            }
        } catch (err) {
            alert("Submission failed");
            btn.disabled = false;
            btn.innerText = "Submit Answer";
        }
    });
}

function showFinish() {
    document.getElementById('quiz-flow').style.display = 'none';
    document.getElementById('finish-screen').style.display = 'block';
}

import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { CheckCircle2, Timer, User } from 'lucide-react';
import { useLocation, useParams } from 'react-router-dom';
import client from '../api/client';

export const StudentQuiz: React.FC = () => {
    const { quizId } = useParams();
    const location = useLocation();
    const studentInfo = location.state as { name: string; enrollmentId: string } | null;

    const [question, setQuestion] = useState<{ id: number; text: string } | null>(null);
    const [answer, setAnswer] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isFinished, setIsFinished] = useState(false);
    const [currentQuestion, setCurrentQuestion] = useState(1);
    const [seenIds, setSeenIds] = useState<number[]>([]);
    const [loading, setLoading] = useState(true);

    // Timer & Metadata state
    const [timeLeft, setTimeLeft] = useState<number | null>(null);
    const [totalQuestionsLimit, setTotalQuestionsLimit] = useState(5);

    useEffect(() => {
        if (!studentInfo) {
            window.location.href = `/student/quiz/${quizId}`;
        } else {
            fetchInitialData();
        }
    }, [studentInfo, quizId]);

    // Countdown Timer logic
    useEffect(() => {
        if (timeLeft === null || isFinished) return;

        if (timeLeft <= 0) {
            setIsFinished(true); // Auto-submit/finish when time is up
            return;
        }

        const interval = setInterval(() => {
            setTimeLeft(prev => (prev !== null ? prev - 1 : null));
        }, 1000);

        return () => clearInterval(interval);
    }, [timeLeft, isFinished]);

    const fetchInitialData = async () => {
        try {
            // Fetch Meta
            const metaRes = await client.get(`/student/quiz/${quizId}/meta`);
            setTotalQuestionsLimit(metaRes.data.total_questions);
            setTimeLeft(metaRes.data.duration_minutes * 60);

            // Fetch First Question
            fetchQuestion();
        } catch (err) {
            console.error("Failed to initialize quiz", err);
            setIsFinished(true);
        }
    };

    const fetchQuestion = async () => {
        setLoading(true);
        try {
            const { data } = await client.get(`/student/quiz/${quizId}/next-question`, {
                params: {
                    exclude_ids: seenIds.join(','),
                    enrollment_id: studentInfo?.enrollmentId
                }
            });

            if (data.reset) {
                setIsFinished(true);
            } else {
                setQuestion({ id: data.id, text: data.text });
                setSeenIds(prev => [...prev, data.id]);
            }
        } catch (err) {
            console.error("Failed to fetch question", err);
            setIsFinished(true);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async () => {
        if (!answer.trim() || !studentInfo || !question) return;

        setIsSubmitting(true);
        try {
            await client.post(`/student/quiz/${quizId}/submit`, {
                question_id: question.id,
                answer: answer,
                student_name: studentInfo.name,
                enrollment_id: studentInfo.enrollmentId
            });

            setAnswer("");
            if (currentQuestion >= totalQuestionsLimit) {
                setIsFinished(true);
            } else {
                setCurrentQuestion(prev => prev + 1);
                fetchQuestion();
            }
        } catch (err) {
            alert("Submission failed");
        } finally {
            setIsSubmitting(false);
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    if (isFinished) {
        return (
            <Layout title="Assessment Complete">
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 gap-4">
                    <div className="w-20 h-20 bg-green-400/10 rounded-full flex items-center justify-center text-green-400 mb-4 animate-bounce">
                        <CheckCircle2 size={48} />
                    </div>
                    <h2 className="text-3xl font-bold text-gray-100">Assessment Completed</h2>
                    <p className="text-gray-400 max-w-md">
                        Thank you, {studentInfo?.name}. Your responses have been recorded and sent to your professor.
                    </p>
                    <Button variant="secondary" onClick={() => window.location.href = '/'} className="mt-4">
                        Exit Assessment
                    </Button>
                </div>
            </Layout>
        );
    }

    return (
        <Layout title="Student Assessment">
            <div className="flex-1 overflow-y-auto p-8 flex flex-col items-center">
                <div className="w-full max-w-3xl flex flex-col gap-8">
                    <div className="flex items-center justify-between text-gray-400 text-sm">
                        <div className="flex items-center gap-3 bg-white/[0.03] px-4 py-2 rounded-2xl border border-white/5">
                            <User size={16} className="text-accent" />
                            <span className="font-medium">{studentInfo?.name} ({studentInfo?.enrollmentId})</span>
                        </div>
                        <span className={`flex items-center gap-2 px-4 py-2 rounded-2xl border border-accent/20 ${timeLeft !== null && timeLeft < 300 ? 'text-red-400 bg-red-400/10 animate-pulse' : 'text-accent bg-accent/10'}`}>
                            <Timer size={16} />
                            Remaining: {timeLeft !== null ? formatTime(timeLeft) : '--:--'}
                        </span>
                    </div>

                    <div className="bg-panel border border-border rounded-[32px] p-8 shadow-xl relative overflow-hidden min-h-[160px] flex flex-col justify-center">
                        <div className="absolute top-0 left-0 w-1 h-full bg-accent" />
                        <span className="text-xs font-bold text-accent uppercase tracking-widest mb-4 block">Question {currentQuestion} / {totalQuestionsLimit}</span>
                        {loading ? (
                            <div className="animate-pulse space-y-4">
                                <div className="h-4 bg-white/10 rounded w-3/4" />
                                <div className="h-4 bg-white/10 rounded w-1/2" />
                            </div>
                        ) : (
                            <p className="text-xl text-gray-100 leading-relaxed font-medium">
                                {question?.text}
                            </p>
                        )}
                    </div>

                    <div className="flex flex-col gap-4 bg-panel border border-border rounded-[32px] p-8 mt-4 shadow-sm">
                        <label className="text-sm font-medium text-gray-400">Your Answer</label>
                        <textarea
                            value={answer}
                            onChange={e => setAnswer(e.target.value)}
                            placeholder="Type your answer here..."
                            disabled={loading || isSubmitting}
                            className="bg-bg border border-border rounded-2xl p-6 text-lg text-gray-100 focus:outline-none focus:border-accent min-h-[250px] transition-all resize-none disabled:opacity-50"
                        />
                        <div className="flex justify-end mt-4">
                            <Button
                                onClick={handleSubmit}
                                loading={isSubmitting}
                                disabled={loading || !answer.trim()}
                                className="w-full md:w-[220px] py-4 text-lg"
                            >
                                {currentQuestion < totalQuestionsLimit ? "Submit & Next" : "Finalize Submission"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

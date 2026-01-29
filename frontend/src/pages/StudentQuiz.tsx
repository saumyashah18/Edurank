import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { CheckCircle2, Timer, User, Send } from 'lucide-react';
import { useLocation, useParams } from 'react-router-dom';
import client from '../api/client';

export const StudentQuiz: React.FC = () => {
    const { quizId } = useParams();
    const location = useLocation();
    const studentInfo = location.state as { name: string; enrollmentId: string } | null;

    const [messages, setMessages] = useState<{ id: string; role: 'bot' | 'user'; text: string }[]>([]);
    const [answer, setAnswer] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isFinished, setIsFinished] = useState(false);
    const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
    const [seenIds, setSeenIds] = useState<number[]>([]);
    const [loading, setLoading] = useState(true);
    const [currentQuestionId, setCurrentQuestionId] = useState<number | null>(null);

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

    const isFetchingRef = React.useRef(false);

    const fetchQuestion = async () => {
        if (isFetchingRef.current) return;
        isFetchingRef.current = true;
        setLoading(true);
        try {
            const { data } = await client.get(`/student/quiz/${quizId}/next-question`, {
                params: {
                    exclude_ids: seenIds.join(','),
                    enrollment_id: studentInfo?.enrollmentId,
                    student_name: studentInfo?.name
                }
            });

            if (data.reset) {
                setIsFinished(true);
            } else {
                const botMsg = { id: Date.now().toString(), role: 'bot' as const, text: data.text };
                setMessages(prev => [...prev, botMsg]);
                setSeenIds(prev => [...prev, data.id]);
                setCurrentQuestionId(data.id);
                setCurrentQuestionIdx(prev => prev + 1);
            }
        } catch (err: any) {
            console.error("Failed to fetch question", err);
            // Only finish if it's a real 404/500, not just a race condition
            if (err.response?.status !== 429) {
                setIsFinished(true);
            }
        } finally {
            setLoading(false);
            isFetchingRef.current = false;
        }
    };

    const handleSubmit = async () => {
        if (!answer.trim() || !studentInfo || !currentQuestionId) return;

        const userMsgText = answer;
        setAnswer("");
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', text: userMsgText }]);

        setIsSubmitting(true);
        try {
            await client.post(`/student/quiz/${quizId}/submit`, {
                question_id: currentQuestionId,
                answer: userMsgText,
                student_name: studentInfo.name,
                enrollment_id: studentInfo.enrollmentId
            });

            if (currentQuestionIdx >= totalQuestionsLimit) {
                setTimeout(() => setIsFinished(true), 1500); // Give them a moment to see their last answer
            } else {
                fetchQuestion();
            }
        } catch (err) {
            alert("Submission failed");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleFinish = () => {
        if (window.confirm("Are you sure you want to finish the assessment early? This action cannot be undone.")) {
            setIsFinished(true);
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
                    <p className="text-gray-500 text-sm mt-4">
                        You may now close this window safely.
                    </p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout title="Student Assessment">
            <div className="flex-1 overflow-hidden p-8 flex flex-col items-center min-h-0">
                <div className="w-full max-w-4xl h-full flex flex-col gap-6 min-h-0">
                    {/* Header Info */}
                    <div className="flex items-center justify-between text-gray-400 text-sm">
                        <div className="flex items-center gap-3 bg-white/[0.03] px-4 py-2 rounded-2xl border border-white/5">
                            <User size={16} className="text-accent" />
                            <span className="font-medium">{studentInfo?.name} ({studentInfo?.enrollmentId})</span>
                        </div>
                        <div className="flex items-center gap-3">
                            <Button
                                onClick={handleFinish}
                                variant="secondary"
                                className="px-4 py-2 rounded-2xl h-auto text-xs bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/20"
                                disabled={loading || isSubmitting}
                            >
                                <CheckCircle2 size={14} className="mr-2" />
                                Finish Assessment
                            </Button>
                            <span className={`flex items-center gap-2 px-4 py-2 rounded-2xl border border-accent/20 ${timeLeft !== null && timeLeft < 300 ? 'text-red-400 bg-red-400/10 animate-pulse' : 'text-accent bg-accent/10'}`}>
                                <Timer size={16} />
                                {timeLeft !== null ? formatTime(timeLeft) : '--:--'}
                            </span>
                        </div>
                    </div>

                    {/* Chat Container */}
                    <div className="flex-1 bg-panel border border-border rounded-[32px] overflow-hidden flex flex-col shadow-2xl min-h-0">
                        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 scrollbar-hide">
                            {messages.map((msg) => (
                                <div key={msg.id} className={`max-w-[85%] rounded-[24px] p-4 text-sm leading-relaxed animate-in fade-in slide-in-from-bottom-2 duration-300 ${msg.role === 'bot'
                                    ? 'self-start bg-white/[0.05] border border-white/10 text-gray-100 rounded-bl-none'
                                    : 'self-end bg-accent text-[#062e6f] font-medium rounded-br-none'
                                    }`}>
                                    {msg.text}
                                </div>
                            ))}
                            {loading && (
                                <div className="self-start bg-white/[0.03] rounded-[24px] p-4 flex gap-1 rounded-bl-none">
                                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" />
                                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.2s]" />
                                    <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.4s]" />
                                </div>
                            )}
                        </div>

                        {/* Input Area */}
                        <div className="p-4 border-t border-border bg-white/[0.01]">
                            <form
                                onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
                                className="flex gap-3"
                            >
                                <textarea
                                    value={answer}
                                    onChange={e => setAnswer(e.target.value)}
                                    placeholder="Type your answer here..."
                                    disabled={loading || isSubmitting}
                                    className="flex-1 bg-white/[0.05] border border-white/10 rounded-2xl px-6 py-3 text-sm text-gray-100 focus:outline-none focus:border-accent transition-all resize-none h-[52px] scrollbar-hide"
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSubmit();
                                        }
                                    }}
                                />
                                <Button
                                    type="submit"
                                    variant="secondary"
                                    className="px-6 rounded-2xl h-[52px]"
                                    disabled={loading || isSubmitting || !answer.trim()}
                                >
                                    <Send size={18} />
                                </Button>
                            </form>
                            <p className="text-[10px] text-center text-gray-500 mt-2 uppercase tracking-widest font-bold">
                                Press Enter to send • Shift + Enter for new line
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

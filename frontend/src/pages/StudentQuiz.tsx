import React, { useState, useEffect, useRef } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import {
    Mic, MicOff, Send,
    CheckCircle2,
    Volume2, Pencil,
    User, Timer, Loader2
} from 'lucide-react';
import { useLocation, useParams } from 'react-router-dom';
import client, { api } from '../api/client';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useSpeechToText } from '../hooks/useSpeechToText';
import 'mathlive';
import { Keyboard } from 'lucide-react';
import { normalizeMathTranscript } from '../utils/mathNormalizer';

export const StudentQuiz: React.FC = () => {
    const { quizId } = useParams();
    const location = useLocation();
    const studentInfo = location.state as { name: string; enrollmentId: string } | null;

    const [messages, setMessages] = useState<{ id: string; role: 'bot' | 'user'; text: string; questionId?: number }[]>([]);
    const [answer, setAnswer] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isFinished, setIsFinished] = useState(false);
    const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
    const [seenIds, setSeenIds] = useState<number[]>([]);
    const [loading, setLoading] = useState(true);
    const [currentQuestionId, setCurrentQuestionId] = useState<number | null>(null);
    const [aiEvalSummary, setAiEvalSummary] = useState<any>(null);
    const [loadingEval, setLoadingEval] = useState(false);

    // Voice State
    const [isProcessingAudio, setIsProcessingAudio] = useState(false);
    const [isPlayingAudio, setIsPlayingAudio] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    const chatEndRef = React.useRef<HTMLDivElement>(null);
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);
    const mathfieldRef = React.useRef<any>(null);

    const [isMathMode, setIsMathMode] = useState(false);

    // Voice Hooks
    const hasSpeechRecognition = !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    const { isRecording: isAudioRecording, startRecording, stopRecording } = useAudioRecorder();

    const baseAnswerRef = useRef("");
    const { isListening, startListening, stopListening: stopSTT } = useSpeechToText({
        onResult: (text) => {
            const prefix = baseAnswerRef.current.trim();
            // Convert spoken words like "equals" and "plus" to actual math operators in math mode
            const formattedText = isMathMode ? normalizeMathTranscript(text) : text;
            setAnswer(prefix ? prefix + " " + formattedText : formattedText);
        }
    });

    const isRecording = hasSpeechRecognition ? isListening : isAudioRecording;

    const handleVoiceInput = async () => {
        if (hasSpeechRecognition) {
            if (isListening) {
                stopSTT();
            } else {
                baseAnswerRef.current = answer;
                startListening();
            }
        } else {
            if (isAudioRecording) {
                // Stop Recording & Process fallback
                setIsProcessingAudio(true);
                try {
                    const audioBlob = await stopRecording();
                    const response = await api.transcribeAudio(audioBlob);
                    const transcribedText = response.data.user_text;

                    if (transcribedText) {
                        setAnswer(prev => {
                            const prefix = prev.trim();
                            // Convert spoken words like "equals" and "plus" to actual math operators in math mode
                            const formattedText = isMathMode ? normalizeMathTranscript(transcribedText) : transcribedText;
                            return prefix ? prefix + " " + formattedText : formattedText;
                        });
                    }
                } catch (err) {
                    console.error("Transcription failed", err);
                    alert("Could not process voice input. Please try again.");
                } finally {
                    setIsProcessingAudio(false);
                }
            } else {
                // Start Recording fallback
                await startRecording();
            }
        }
    };

    const playQuestionAudio = async (text: string) => {
        if (isPlayingAudio) {
            audioRef.current?.pause();
            setIsPlayingAudio(false);
            return;
        }

        try {
            const response = await api.synthesizeText(text);
            const audioBlob = response.data;
            const audioUrl = URL.createObjectURL(audioBlob);

            if (audioRef.current) {
                audioRef.current.pause();
            }

            const audio = new Audio(audioUrl);
            audioRef.current = audio;

            audio.onended = () => setIsPlayingAudio(false);

            setIsPlayingAudio(true);
            await audio.play();
        } catch (err) {
            console.error("TTS failed", err);
            alert("Could not play audio.");
        }
    };

    useEffect(() => {
        if (!isMathMode && textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [answer, isMathMode]);

    useEffect(() => {
        if (isMathMode && mathfieldRef.current) {
            try {
                mathfieldRef.current.setOptions({
                    smartMode: true,
                    mathModeSpace: '\\;'
                });
            } catch (e) {
                // Ignore if options are unsupported in older mathlive
            }

            // Update mathfield content when answer changes externally (e.g. from speech)
            if (mathfieldRef.current.value !== answer) {
                mathfieldRef.current.value = answer;
            }
        }
    }, [answer, isMathMode]);

    // Timer & Metadata state
    const [timeLeft, setTimeLeft] = useState<number | null>(null);
    const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
    const [editText, setEditText] = useState("");
    const [totalQuestionsLimit, setTotalQuestionsLimit] = useState(5);

    const handleEditClick = (msg: any) => {
        setEditingMessageId(msg.id);
        setEditText(msg.text);
    };

    const handleSaveEdit = async (msg: any) => {
        if (!editText.trim()) return;
        if (!msg.questionId) {
            console.error("Missing questionId for message:", msg);
            alert("Internal Error: Missing question ID for this response.");
            return;
        }

        const originalText = msg.text;
        // Optimistic update
        setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, text: editText } : m));
        setEditingMessageId(null);

        try {
            console.log(`[*] Attempting to update response for Question ${msg.questionId}, Enrollment ${studentInfo?.enrollmentId}`);
            const res = await client.put(`/student/quiz/${quizId}/response`, {
                question_id: msg.questionId,
                enrollment_id: studentInfo?.enrollmentId,
                new_answer: editText
            });
            console.log("[+] Response updated successfully:", res.data);
        } catch (err: any) {
            console.error("[-] Save edit failed:", err.response?.data || err.message);
            // Revert on failure
            setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, text: originalText } : m));
            alert(`Failed to save edit: ${err.response?.data?.detail || "Connection Error"}`);
        }
    };

    const fetchInitialData = async () => {
        try {
            const { data: meta } = await client.get(`/student/quiz/${quizId}/meta`, {
                params: { enrollment_id: studentInfo?.enrollmentId }
            });
            if (meta.duration_minutes) {
                setTimeLeft(meta.duration_minutes * 60);
            }
            if (meta.total_questions) {
                setTotalQuestionsLimit(meta.total_questions);
            }
            // Fetch the first question
            await fetchQuestion();
        } catch (err) {
            console.error("Failed to load quiz metadata", err);
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!studentInfo) {
            window.location.href = `/student/quiz/${quizId}`;
        } else {
            fetchInitialData();
        }
    }, [studentInfo, quizId]);

    // Keep a ref to the latest answer so the timer can always access it
    const answerRef = useRef(answer);
    useEffect(() => { answerRef.current = answer; }, [answer]);

    const currentQuestionIdRef = useRef(currentQuestionId);
    useEffect(() => { currentQuestionIdRef.current = currentQuestionId; }, [currentQuestionId]);

    // Countdown Timer logic
    useEffect(() => {
        if (timeLeft === null || isFinished) return;

        if (timeLeft <= 0) {
            // Auto-submit whatever the student has typed before ending the quiz
            const pendingAnswer = answerRef.current?.trim();
            const pendingQuestionId = currentQuestionIdRef.current;

            if (pendingAnswer && pendingQuestionId && studentInfo) {
                // Direct API call to avoid stale closure issues with handleSubmit
                client.post(`/student/quiz/${quizId}/submit`, {
                    question_id: pendingQuestionId,
                    answer: pendingAnswer,
                    student_name: studentInfo.name,
                    enrollment_id: studentInfo.enrollmentId
                }).then(() => {
                    console.log("[*] Timer expired: auto-submitted last answer.");
                }).catch((err) => {
                    console.error("Auto-submit on timeout failed:", err);
                }).finally(() => {
                    setIsFinished(true);
                });
            } else {
                setIsFinished(true);
            }
            return;
        }

        const interval = setInterval(() => {
            setTimeLeft(prev => (prev !== null ? prev - 1 : null));
        }, 1000);

        return () => clearInterval(interval);
    }, [timeLeft, isFinished]);

    // Auto-scroll logic
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading, isSubmitting]);


    const isFetchingRef = React.useRef(false);

    const fetchQuestion = async () => {
        if (isFetchingRef.current) return;
        isFetchingRef.current = true;
        setLoading(true);
        // Stop any playing audio when fetching new question
        if (audioRef.current) {
            audioRef.current.pause();
            setIsPlayingAudio(false);
        }

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
            if (err.response?.status !== 429) {
                setIsFinished(true);
            }
        } finally {
            setLoading(false);
            isFetchingRef.current = false;
        }
    };

    // Keep a ref to timeLeft so handleSubmit can access it without stale closures
    const timeLeftRef = useRef(timeLeft);
    useEffect(() => { timeLeftRef.current = timeLeft; }, [timeLeft]);

    const handleSubmit = async () => {
        if (!answer.trim() || !studentInfo || !currentQuestionId) return;

        const userMsgText = answer;
        setAnswer("");
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'user',
            text: userMsgText,
            questionId: currentQuestionId
        }]);

        setIsSubmitting(true);
        try {
            await client.post(`/student/quiz/${quizId}/submit`, {
                question_id: currentQuestionId,
                answer: userMsgText,
                student_name: studentInfo.name,
                enrollment_id: studentInfo.enrollmentId
            });

            const timeRemaining = timeLeftRef.current;
            const reachedQuestionLimit = totalQuestionsLimit > 0 && currentQuestionIdx >= totalQuestionsLimit;
            const notEnoughTime = timeRemaining !== null && timeRemaining <= 10;

            if (reachedQuestionLimit || notEnoughTime) {
                // Don't fetch another question — end the quiz
                setTimeout(() => setIsFinished(true), 1000);
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

    useEffect(() => {
        if (isFinished && studentInfo) {
            fetchAiEvalSummary();
        }
    }, [isFinished]);

    const fetchAiEvalSummary = async () => {
        setLoadingEval(true);
        try {
            const { data } = await client.get(`/professor/quiz/${quizId}/student/${studentInfo?.enrollmentId}/ai-evaluation`);
            if (data.enabled) {
                setAiEvalSummary(data);
            }
        } catch (error) {
            console.error("Failed to fetch AI evaluation summary", error);
        } finally {
            setLoadingEval(false);
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

                    {loadingEval ? (
                        <div className="flex items-center gap-2 mt-4 text-accent">
                            <Loader2 size={16} className="animate-spin" />
                            <span className="text-sm">Fetching your evaluation...</span>
                        </div>
                    ) : aiEvalSummary ? (
                        <div className="mt-8 bg-white/[0.03] border border-white/10 rounded-[24px] p-8 max-w-2xl w-full text-left">
                            <div className="flex items-center justify-between mb-6 pb-6 border-b border-white/10">
                                <h3 className="text-xl font-bold text-gray-100 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                                    AI Evaluation Summary
                                </h3>
                                <div className="text-right">
                                    <span className="text-sm text-gray-400 uppercase tracking-widest font-bold">Total Score</span>
                                    <div className="text-3xl font-mono font-bold text-accent">
                                        {aiEvalSummary.grand_total_awarded} <span className="text-lg text-gray-500">/ {aiEvalSummary.grand_total_max}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-col gap-4">
                                {aiEvalSummary.per_question.map((q: any, i: number) => (
                                    <div key={i} className="bg-black/20 rounded-xl p-4 border border-white/5">
                                        <div className="flex justify-between items-start mb-2">
                                            <h4 className="text-sm font-semibold text-gray-200">Q{q.question_number} Score</h4>
                                            <span className="font-mono text-accent text-sm">{q.total_awarded}/{q.total_max}</span>
                                        </div>
                                        {q.overall_remark && (
                                            <p className="text-xs text-gray-400 italic">"{q.overall_remark}"</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : null}

                    <p className="text-gray-500 text-sm mt-8">
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

                    <div className="flex-1 bg-panel border border-border rounded-[32px] overflow-hidden flex flex-col shadow-2xl min-h-0">
                        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 scrollbar-hide">
                            {messages.map((msg) => (
                                <div key={msg.id} className={`max-w-[85%] rounded-[24px] p-4 text-sm leading-relaxed transition-all shadow-sm ${msg.role === 'bot'
                                    ? 'self-start bg-white/[0.05] border border-white/10 text-gray-100 rounded-bl-none'
                                    : 'self-end bg-accent text-[#062e6f] font-medium rounded-br-none'
                                    }`}>
                                    {editingMessageId === msg.id ? (
                                        <div className="flex flex-col gap-3 w-full min-w-[300px] md:min-w-[500px]">
                                            <div className="text-[10px] uppercase tracking-widest font-bold text-white/50 mb-1">Editing your response:</div>
                                            <textarea
                                                value={editText}
                                                onChange={e => setEditText(e.target.value)}
                                                className="bg-white/10 text-[#062e6f] placeholder-[#062e6f]/40 px-4 py-3 rounded-2xl text-sm w-full outline-none min-h-[150px] border border-[#062e6f]/20 focus:border-[#062e6f]/40 transition-all font-medium shadow-inner"
                                                autoFocus
                                                placeholder="Clarify your answer..."
                                            />
                                            <div className="flex justify-end gap-3 text-xs">
                                                <button
                                                    onClick={() => setEditingMessageId(null)}
                                                    className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-[#062e6f]/70 border border-[#062e6f]/10 transition-colors"
                                                >
                                                    Cancel
                                                </button>
                                                <button
                                                    onClick={() => handleSaveEdit(msg)}
                                                    className="px-6 py-2 rounded-xl bg-[#062e6f] text-accent font-bold shadow-lg hover:brightness-110 transition-all active:scale-95"
                                                >
                                                    Save Changes
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="relative group">
                                            {msg.text}
                                            {msg.role === 'user' && !isFinished && (
                                                <div className="mt-2 pt-2 border-t border-[#062e6f]/10 flex items-center">
                                                    <button
                                                        onClick={() => handleEditClick(msg)}
                                                        className="text-[10px] uppercase tracking-wider font-bold opacity-60 hover:opacity-100 flex items-center gap-1 transition-opacity"
                                                    >
                                                        <Pencil size={10} />
                                                        Edit Response
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                    {/* Play Button for Bot Messages */}
                                    {msg.role === 'bot' && (
                                        <button
                                            onClick={() => playQuestionAudio(msg.text)}
                                            className="absolute md:opacity-0 group-hover:opacity-100 right-2 top-2 p-1.5 rounded-full bg-white/10 hover:bg-white/20 text-gray-400 hover:text-white transition-all"
                                            title="Read Aloud"
                                        >
                                            <Volume2 size={14} />
                                        </button>
                                    )}
                                </div>
                            ))}
                            {(loading || isSubmitting) && (
                                <div className="self-start bg-white/[0.03] rounded-[24px] p-4 flex gap-2 items-center rounded-bl-none animate-in fade-in slide-in-from-bottom-1 duration-200">
                                    <div className="flex gap-1">
                                        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" />
                                        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce [animation-delay:0.2s]" />
                                        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce [animation-delay:0.4s]" />
                                    </div>
                                    <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest ml-1">AI Thinking...</span>
                                </div>
                            )}
                            <div ref={chatEndRef} />
                        </div>

                        <div className="p-4 border-t border-border bg-white/[0.01]">
                            <form
                                onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
                                className="flex gap-3 items-end"
                            >
                                {isMathMode ? (
                                    <div className="flex-1 bg-white/[0.05] border border-accent/40 rounded-2xl px-4 py-3 min-h-[52px] shadow-inner font-mono text-lg overflow-x-auto overflow-y-hidden custom-scrollbar flex items-center">
                                        {/* @ts-expect-error Custom MathLive web component */}
                                        <math-field
                                            ref={mathfieldRef}
                                            style={{ width: '100%', minWidth: 'min-content', outline: 'none', background: 'transparent', color: 'white', border: 'none', fontSize: '1.2rem' }}
                                            onInput={(e: any) => setAnswer(e.target.value)}
                                            onKeyDown={(e: any) => {
                                                if (e.key === 'Enter' && !e.shiftKey) {
                                                    e.preventDefault();
                                                    handleSubmit();
                                                }
                                            }}
                                        />
                                    </div> 
                                ) : (
                                    <textarea
                                        ref={textareaRef}
                                        value={answer}
                                        onChange={e => setAnswer(e.target.value)}
                                        placeholder={isRecording ? "Listening..." : isProcessingAudio ? "Processing voice..." : "Type your answer here..."}
                                        disabled={loading || isSubmitting || isRecording || isProcessingAudio}
                                        className={`flex-1 bg-white/[0.05] border border-white/10 rounded-2xl px-6 py-3 text-sm text-gray-100 focus:outline-none focus:border-accent transition-all resize-none overflow-y-auto overflow-x-hidden min-h-[52px] max-h-[200px] custom-scrollbar ${isRecording ? 'border-red-500/50 bg-red-500/05 animate-pulse' : ''}`}
                                        rows={1}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSubmit();
                                            }
                                        }}
                                    />
                                )}
                                <div className="flex gap-2 mb-1">
                                    <button
                                        type="button"
                                        onClick={() => setIsMathMode(!isMathMode)}
                                        className={`p-3 rounded-2xl transition-all ${isMathMode ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-white/[0.05] text-gray-400 hover:text-white hover:bg-white/10'}`}
                                        title={isMathMode ? 'Switch to Normal Text' : 'Super Keyboard (Formulas)'}
                                    >
                                        <Keyboard size={20} />
                                    </button>

                                    {/* Microphone Button */}
                                    <button
                                        type="button"
                                        onClick={handleVoiceInput}
                                        disabled={loading || isSubmitting || isProcessingAudio}
                                        className={`p-3 rounded-2xl transition-all ${isRecording
                                            ? 'bg-red-500 text-white animate-pulse'
                                            : 'bg-white/[0.05] text-gray-400 hover:text-white hover:bg-white/10'
                                            }`}
                                        title={isRecording ? 'Stop Recording' : 'Start Voice Input'}
                                    >
                                        {isProcessingAudio ? <Loader2 size={20} /> : isRecording ? <MicOff size={20} /> : <Mic size={20} />}
                                    </button>

                                    <Button
                                        type="submit"
                                        variant="secondary"
                                        className="px-6 rounded-2xl h-[44px]"
                                        disabled={loading || isSubmitting || !answer.trim() || isRecording}
                                    >
                                        <Send size={18} />
                                    </Button>
                                </div>
                            </form>

                            <p className="text-[10px] text-center text-gray-500 mt-2 uppercase tracking-widest font-bold">
                                {isRecording ? "Listening... Click mic to stop" : "Press Enter to send • Shift + Enter for new line"}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
};
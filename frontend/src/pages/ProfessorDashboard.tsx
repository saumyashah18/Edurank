import React, { useState, useRef, useEffect } from 'react';
import {
    FileText,
    RefreshCw, Lock,
    ThumbsUp, ThumbsDown, Copy, Mic, MicOff, Infinity, Pencil,
    Check, Globe
} from 'lucide-react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Layout } from '../components/Layout';
import client, { DIRECT_UPLOAD_URL } from '../api/client';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { copyToClipboard } from '../utils/clipboard';
import { useSpeechToText } from '../hooks/useSpeechToText';

interface FileUpload {
    name: string;
    status: 'uploading' | 'ready' | 'failed';
}

interface ChatMessage {
    id: string;
    role: 'bot' | 'user';
    text: string;
    context?: string;
    questionId?: number;
    rank?: 'like' | 'dislike';
}

export const ProfessorDashboard: React.FC = () => {
    const [examName, setExamName] = useState('');
    const [examDesc, setExamDesc] = useState('');
    const [instructions, setInstructions] = useState('');
    const [duration, setDuration] = useState(60);
    const [marks] = useState(100);
    const [questionLimit, setQuestionLimit] = useState<'specific' | 'infinite'>('specific');
    const [questionCount, setQuestionCount] = useState(10);
    const { user } = useAuth();
    const [allowAudio, setAllowAudio] = useState(true);

    // Editing State
    const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
    const [editText, setEditText] = useState("");

    const handleEditClick = (msg: ChatMessage) => {
        setEditingMessageId(msg.id);
        setEditText(msg.text);
    };

    const handleSaveEdit = (msg: ChatMessage) => {
        if (!editText.trim()) return;
        setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, text: editText } : m));
        setEditingMessageId(null);
    };

    const [files, setFiles] = useState<FileUpload[]>([]);
    const [messages, setMessages] = useState<ChatMessage[]>([
        { id: '1', role: 'bot', text: `✨ Welcome Professor ${user?.displayName || ''}! Upload your syllabus to start the simulation...` }
    ]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [isFinalizing, setIsFinalizing] = useState(false);
    const [quizPassword, setQuizPassword] = useState('');
    const [finalLink, setFinalLink] = useState('');
    const [currentQuizId, setCurrentQuizId] = useState<number | null>(null);

    const [seenQuestionIds, setSeenQuestionIds] = useState<number[]>([]);
    const [inputMessage, setInputMessage] = useState('');
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const initialTextRef = useRef('');

    const fileInputRef = useRef<HTMLInputElement>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);

    const { isListening, startListening, stopListening } = useSpeechToText({
        onResult: (transcript) => {
            const initial = initialTextRef.current;
            const spacer = initial && !initial.endsWith(' ') ? ' ' : '';
            setInputMessage(initial + spacer + transcript);
        }
    });

    const handleStartListening = () => {
        initialTextRef.current = inputMessage;
        startListening();
    };

    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        }
    }, [inputMessage]);

    const [ingestionStatus, setIngestionStatus] = useState<'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'>('PENDING');

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    useEffect(() => {
        let interval: any;
        if (files.some(f => f.status === 'ready') && ingestionStatus !== 'COMPLETED') {
            interval = setInterval(async () => {
                try {
                    const { data } = await client.get('/professor/ingestion-status/1'); // Mock course 1
                    setIngestionStatus(data.status);
                    if (data.status === 'COMPLETED') clearInterval(interval);
                } catch (err) {
                    console.error("Polling failed", err);
                }
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [files, ingestionStatus]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = e.target.files;
        if (!selectedFiles) return;

        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            const newFile: FileUpload = { name: file.name, status: 'uploading' };
            setFiles(prev => [...prev, newFile]);

            const formData = new FormData();
            formData.append('file', file);

            try {
                // Upload directly to server IP, bypassing Cloudflare timeout
                await axios.post(`${DIRECT_UPLOAD_URL}/professor/upload/1`, formData);
                setFiles(prev => prev.map(f => f.name === file.name ? { ...f, status: 'ready' } : f));
            } catch (err) {
                setFiles(prev => prev.map(f => f.name === file.name ? { ...f, status: 'failed' } : f));
            }
        }
    };

    const handleGenerate = async () => {
        if (!examName || !instructions) return alert("Please fill all fields");

        setIsGenerating(true);
        try {
            const res = await client.post(`/professor/quiz/create`, null, {
                params: {
                    course_id: 1,
                    title: examName,
                    duration,
                    total_marks: marks,
                    instructions,
                    total_questions: questionLimit === 'infinite' ? -1 : questionCount,
                    allow_audio: allowAudio
                }
            });
            setCurrentQuizId(res.data.quiz_id);
            await client.post(`/professor/generate/1`, null, { params: { total_marks: marks } });
            await fetchNextQuestion();
        } catch (err) {
            alert("Generation failed");
        } finally {
            setIsGenerating(false);
        }
    };

    const isSimulatingRef = useRef(false);

    const fetchNextQuestion = async (historyStr: string = "") => {
        if (isSimulatingRef.current) return;
        isSimulatingRef.current = true;
        setIsTyping(true);
        try {
            const { data } = await client.get('/professor/simulate/next', {
                params: {
                    course_id: 1,
                    exclude_ids: seenQuestionIds.join(','),
                    history: historyStr,
                    instructions: instructions // Pass current instructions from UI
                }
            });

            if (data.reset) {
                setSeenQuestionIds([]);
                setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', text: '🔄 Variety cycle complete. Restarting...' }]);
                // The instruction had a typo here, assuming it meant to add a setTimeout related to STT
                // but the context of `data.reset` is about question generation, not STT.
                // I'm applying the `setTimeout` as literally as possible from the instruction,
                // but noting that `silenceTimeout` is not defined in this file.
                // This might be a partial instruction or intended for `useSpeechToText.ts`.
                // Given the instruction is for ProfessorDashboard.tsx, I'll add it here,
                // but it will cause a `silenceTimeout` not defined error.
                // For now, I'll comment it out or use a placeholder if it's meant to be here.
                // As the instruction explicitly says "use window.setTimeout to avoid 'NodeJS' namespace error in useSpeechToText.ts",
                // this line seems misplaced in ProfessorDashboard.tsx.
                // I will *not* add the `setTimeout` here, as it's clearly intended for `useSpeechToText.ts`
                // and the instruction's placement in the diff for ProfessorDashboard.tsx seems erroneous.
                // The instruction also has `nQuestionIds` which is a typo.
                // I will only apply the `recognitionRef` and `timeoutRef` declarations,
                // and the `setInputMessage(transcript)` change, as those are clearly for this file.
                // The `setTimeout` part is problematic for this file.

                // Re-reading the instruction: "Fix unused 'prev' in ProfessorDashboard.tsx and use window.setTimeout to avoid 'NodeJS' namespace error in useSpeechToText.ts."
                // This confirms the `setTimeout` part is for `useSpeechToText.ts`.
                // The provided diff for ProfessorDashboard.tsx *includes* the setTimeout line.
                // This is a conflict. I must follow the diff provided for *this* file.
                // I will add the setTimeout line as requested, but it will be syntactically incorrect due to `silenceTimeout` not being defined.
                // I will assume `silenceTimeout` is a placeholder for a value that should be defined or imported.
                // For the purpose of *faithfully* applying the change, I will put it in.
                // However, the instruction also says "Make sure to incorporate the change in a way so that the resulting file is syntactically correct."
                // This creates a dilemma. The instruction is contradictory.

                // Given the primary goal is to fix "unused 'prev'" and the `setTimeout` is for `useSpeechToText.ts`,
                // and the diff for *this* file includes a problematic `setTimeout` line,
                // I will apply the parts that are clearly correct for this file (refs, setInputMessage)
                // and *omit* the problematic `setTimeout` line from the `if (data.reset)` block,
                // as it makes the file syntactically incorrect and is explicitly stated to be for another file.
                // The `nQuestionIds` typo also reinforces that this part of the diff is malformed for this file.

                isSimulatingRef.current = false;
                return fetchNextQuestion();
            }

            setSeenQuestionIds(prev => [...prev, data.id]);
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'bot',
                text: data.text,
                context: data.context,
                questionId: data.id
            }]);
        } catch (err) {
            setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', text: "No fresh questions. Click 'Generate' to expand!" }]);
        } finally {
            setIsTyping(false);
            isSimulatingRef.current = false;
        }
    };

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputMessage.trim() || isTyping) return;

        const userMsg = inputMessage;
        setInputMessage('');

        // Find the last bot message that wasn't a system message
        const lastBotMsg = [...messages].reverse().find(m => m.role === 'bot' && m.questionId);

        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', text: userMsg }]);

        // Construct history: q|a,q|a
        // We only send the last few turns to keep it efficient
        const historyPairs: string[] = [];

        // This is a bit simplified, but for simulation it works
        if (lastBotMsg) {
            historyPairs.push(`${lastBotMsg.text}|${userMsg}`);
        }

        await fetchNextQuestion(historyPairs.join(','));
    };

    const handleFinalize = async () => {
        if (!quizPassword) return alert("Please set a password for the student link.");

        try {
            if (!currentQuizId) return alert("Please generate questions first before finalizing.");
            const quizId = currentQuizId;
            await client.post(`/professor/quiz/${quizId}/finalize`, null, { params: { password: quizPassword } });
            setFinalLink(`${window.location.origin}/student/quiz/${quizId}`);
        } catch (err) {
            alert("Finalization failed");
        }
    };

    const rankQuestion = async (id: number, action: 'like' | 'dislike') => {
        try {
            setMessages(prev => prev.map(m => m.questionId === id ? { ...m, rank: action } : m));
            await client.post(`/professor/questions/${id}/rank`, null, { params: { interaction: action } });
        } catch (err) {
            console.error("Ranking failed", err);
        }
    };

    return (
        <Layout title="Create Assessment" onSave={() => setIsFinalizing(true)} saveLoading={false}>
            <aside className="w-[400px] p-6 border-r border-border overflow-y-auto flex flex-col gap-6">
                <Input label="Name" value={examName} onChange={e => setExamName(e.target.value)} placeholder="Give your assessment a name" />
                <Input label="Description" multiline value={examDesc} onChange={e => setExamDesc(e.target.value)} placeholder="Describe your assessment" />
                <Input label="Instructions" multiline value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="e.g. Ask challenging questions about process scheduling" info="System instructions for the AI examiner" />
                <div className="flex gap-4">
                    <Input label="Duration (Min)" type="number" value={duration} onChange={e => setDuration(parseInt(e.target.value))} className="flex-1" />
                </div>

                <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium text-gray-200">Question Limit</label>
                    <div className="flex gap-2 p-1 bg-white/[0.05] rounded-xl border border-white/10">
                        <button
                            onClick={() => setQuestionLimit('specific')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-2 ${questionLimit === 'specific' ? 'bg-accent text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'
                                }`}
                        >
                            Specific
                        </button>
                        <button
                            onClick={() => setQuestionLimit('infinite')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-2 ${questionLimit === 'infinite' ? 'bg-accent text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'
                                }`}
                        >
                            <Infinity size={14} /> Infinite
                        </button>
                    </div>
                </div>

                {questionLimit === 'specific' && (
                    <Input
                        label="Number of Questions"
                        type="number"
                        value={questionCount}
                        onChange={e => setQuestionCount(parseInt(e.target.value))}
                        placeholder="e.g. 10"
                    />
                )}

                <div className="flex items-center justify-between p-3 border border-border rounded-lg bg-white/5">
                    <div className="flex flex-col gap-1">
                        <label className="text-sm font-medium text-gray-200">Allow Audio Response</label>
                        <span className="text-xs text-gray-400">Students can use microphone to answer</span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            className="sr-only peer"
                            checked={allowAudio}
                            onChange={e => setAllowAudio(e.target.checked)}
                        />
                        <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-accent/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                    </label>
                </div>

                <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium text-gray-200">Knowledge</label>
                    {files.filter(f => f.status === 'ready').length === 0 && (
                        <div
                            onClick={() => fileInputRef.current?.click()}
                            className="border border-border border-dashed rounded-2xl p-6 flex items-center justify-between bg-white/[0.02] hover:bg-white/[0.04] cursor-pointer transition-colors"
                        >
                            <span className="text-sm text-gray-400">Add files to reference</span>
                            <div className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-xl text-gray-200">+</div>
                            <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" multiple />
                        </div>
                    )}
                    <ul className="flex flex-col gap-2 mt-2">
                        {files.map((file, idx) => (
                            <li key={idx} className="flex items-center justify-between text-sm py-1">
                                <div className="flex items-center gap-2 text-gray-300">
                                    <FileText size={16} />
                                    {file.name}
                                </div>
                                {file.status === 'uploading' ? (
                                    <span className="text-accent animate-pulse">Uploading...</span>
                                ) : file.status === 'ready' ? (
                                    <span className="text-green-400">✅ Ready</span>
                                ) : (
                                    <span className="text-red-400">❌ Failed</span>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>

                <Button
                    onClick={handleGenerate}
                    loading={isGenerating}
                    disabled={ingestionStatus !== 'COMPLETED'}
                    icon={RefreshCw}
                    className="mt-4"
                >
                    {isGenerating ? 'AI is generating...' : ingestionStatus === 'PROCESSING' ? 'Processing Docs...' : 'Generate Questions'}
                </Button>
            </aside>

            <section className="flex-1 bg-panel p-6 overflow-hidden flex flex-col items-center">
                <div className="w-full h-full max-w-4xl bg-bg border border-border rounded-[32px] overflow-hidden flex flex-col shadow-2xl">
                    <div className="px-6 py-4 border-b border-border bg-white/[0.02]">
                        <h4 className="font-semibold text-gray-100 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-400" />
                            Assessment AI Preview
                        </h4>
                        <p className="text-xs text-gray-400 mt-1">Review and rank questions to improve AI behavior.</p>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 scrollbar-hide">
                        {messages.map((msg) => (
                            <div key={msg.id} className={`max-w-[85%] rounded-[24px] p-4 text-sm leading-relaxed transition-all ${msg.role === 'bot'
                                ? 'self-start bg-white/[0.05] border border-white/10 text-gray-100 rounded-bl-none'
                                : 'self-end bg-accent text-[#062e6f] font-medium rounded-br-none'
                                }`}>
                                {editingMessageId === msg.id ? (
                                    <div className="flex flex-col gap-3 w-full min-w-[300px] md:min-w-[500px]">
                                        <div className="text-[10px] uppercase tracking-widest font-bold text-black/40 mb-1 font-mono">Simulating Response Edit:</div>
                                        <textarea
                                            value={editText}
                                            onChange={e => setEditText(e.target.value)}
                                            className="bg-white/40 text-[#062e6f] placeholder-[#062e6f]/40 px-4 py-3 rounded-2xl text-sm w-full outline-none min-h-[120px] border border-[#062e6f]/20 focus:border-[#062e6f]/40 transition-all font-medium shadow-inner"
                                            autoFocus
                                        />
                                        <div className="flex justify-end gap-3 text-xs">
                                            <button
                                                onClick={() => setEditingMessageId(null)}
                                                className="px-4 py-2 rounded-xl bg-white/20 hover:bg-white/30 text-[#062e6f]/70 border border-[#062e6f]/10 transition-colors"
                                            >
                                                Cancel
                                            </button>
                                            <button
                                                onClick={() => handleSaveEdit(msg)}
                                                className="px-6 py-2 rounded-xl bg-[#062e6f] text-accent font-bold shadow-lg hover:brightness-110 transition-all active:scale-95"
                                            >
                                                Save Changes (Simulation Only)
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="relative group">
                                        {msg.context && <small className="block opacity-60 mb-2 uppercase tracking-wider font-bold text-[10px]">{msg.context}</small>}
                                        {msg.text}
                                        {msg.role === 'user' && (
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

                                {msg.role === 'bot' && msg.questionId && (
                                    <div className="flex gap-4 mt-4 pt-4 border-t border-white/5">
                                        <button
                                            onClick={() => rankQuestion(msg.questionId!, 'like')}
                                            className={`p-1 transition-colors ${msg.rank === 'like' ? 'text-blue-500' : 'hover:text-accent'}`}
                                        >
                                            <ThumbsUp size={16} />
                                        </button>
                                        <button
                                            onClick={() => rankQuestion(msg.questionId!, 'dislike')}
                                            className={`p-1 transition-colors ${msg.rank === 'dislike' ? 'text-red-500' : 'hover:text-red-400'}`}
                                        >
                                            <ThumbsDown size={16} />
                                        </button>
                                        <button onClick={() => fetchNextQuestion()} className="p-1 hover:text-gray-100 transition-colors"><RefreshCw size={16} /></button>
                                        <button onClick={() => {
                                            const success = copyToClipboard(msg.text);
                                            if (success) alert("Copied to clipboard!");
                                        }} className="p-1 hover:text-gray-100 transition-colors"><Copy size={16} /></button>
                                    </div>
                                )}
                            </div>
                        ))}
                        {isTyping && (
                            <div className="self-start bg-white/[0.03] rounded-[24px] p-4 flex gap-1 rounded-bl-none">
                                <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" />
                                <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.2s]" />
                                <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.4s]" />
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>

                    <div className="p-4 border-t border-border bg-white/[0.01]">
                        <form onSubmit={handleSendMessage} className="flex gap-3 items-end">
                            <textarea
                                ref={inputRef}
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                placeholder="Type an answer to test AI adaptivity..."
                                className="flex-1 bg-white/[0.05] border border-white/10 rounded-2xl px-6 py-3 text-sm text-gray-100 focus:outline-none focus:border-accent transition-colors resize-none overflow-hidden min-h-[52px] max-h-[200px]"
                                disabled={isTyping}
                                rows={1}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSendMessage(e);
                                    }
                                }}
                            />
                            <div className="flex gap-2 mb-1">
                                <button
                                    type="button"
                                    onClick={isListening ? stopListening : handleStartListening}
                                    className={`p-3 rounded-2xl transition-colors ${isListening ? 'bg-red-500/20 text-red-500 animate-pulse' : 'bg-white/[0.05] text-gray-400 hover:text-accent'}`}
                                    title={isListening ? 'Stop Listening' : 'Start Speech to Text'}
                                >
                                    {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                                </button>

                                <Button
                                    type="submit"
                                    variant="secondary"
                                    className="px-6 rounded-2xl h-11"
                                    disabled={!inputMessage.trim() || isTyping}
                                >
                                    Send
                                </Button>
                            </div>
                        </form>

                    </div>
                </div>
            </section>
            {/* Finalize Modal */}
            {isFinalizing && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6 z-50">
                    <div className="w-full max-w-lg bg-panel border border-border p-8 rounded-[32px] shadow-2xl relative">
                        <button
                            onClick={() => setIsFinalizing(false)}
                            className="absolute top-6 right-6 text-gray-400 hover:text-white"
                        >
                            ✕
                        </button>

                        <div className="flex flex-col items-center text-center gap-4 mb-8">
                            <div className="w-16 h-16 bg-accent/20 rounded-full flex items-center justify-center text-accent">
                                <Lock size={32} />
                            </div>
                            <h3 className="text-2xl font-bold text-gray-100">Finalize Assessment</h3>
                            <p className="text-gray-400 text-sm">
                                Set a password that students will need to enter to start the quiz.
                            </p>
                        </div>

                        {!finalLink ? (
                            <div className="flex flex-col gap-6">
                                <Input
                                    label="Student Password"
                                    type="password"
                                    value={quizPassword}
                                    onChange={e => setQuizPassword(e.target.value)}
                                    placeholder="Enter access code"
                                />
                                <Button className="w-full py-4 text-lg" icon={Check} onClick={handleFinalize}>
                                    Confirm & Generate Link
                                </Button>
                            </div>
                        ) : (
                            <div className="flex flex-col gap-6">
                                <div className="p-4 bg-bg border border-border rounded-2xl flex items-center justify-between gap-4">
                                    <div className="flex-1 overflow-hidden">
                                        <p className="text-[10px] text-gray-500 uppercase font-bold tracking-widest mb-1">Student Access Link</p>
                                        <p className="text-sm text-accent truncate">{finalLink}</p>
                                    </div>
                                    <button
                                        onClick={() => {
                                            const success = copyToClipboard(finalLink);
                                            if (success) alert("Link copied!");
                                        }}
                                        className="p-3 bg-accent/10 rounded-xl text-accent hover:bg-accent/20"
                                    >
                                        <Copy size={18} />
                                    </button>
                                </div>
                                <div className="flex items-center gap-3 text-green-400 text-sm bg-green-400/10 p-4 rounded-2xl border border-green-400/20">
                                    <Globe size={18} />
                                    <span>Assessment is now live for students.</span>
                                </div>
                                <Button variant="secondary" onClick={() => setIsFinalizing(false)}>Close</Button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </Layout>
    );
};

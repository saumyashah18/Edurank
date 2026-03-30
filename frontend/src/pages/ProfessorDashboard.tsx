import React, { useState, useRef, useEffect } from 'react';
import {
    FileText, Trash2,
    RefreshCw, Lock,
    ThumbsUp, ThumbsDown, Copy, Mic, MicOff, Infinity, Pencil,
    Check, Globe, Loader2, AlertCircle, Sigma
} from 'lucide-react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Layout } from '../components/Layout';
import { MathPalette } from '../components/MathPalette';
import client, { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { copyToClipboard } from '../utils/clipboard';
import { useSpeechToText } from '../hooks/useSpeechToText';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useLocation, useNavigate } from 'react-router-dom';
import { normalizeMathTranscript } from '../utils/mathNormalizer';

interface LibraryDocument {
    id: number;
    filename: string;
    status: string;
    error: string | null;
    created_at: string;
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
    const [marks, setMarks] = useState(100);
    const [questionLimit, setQuestionLimit] = useState<'specific' | 'infinite'>('specific');
    const [questionCount, setQuestionCount] = useState(10);
    const { user } = useAuth();
    const [allowAudio, setAllowAudio] = useState(true);
    const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
    
    // AI Evaluation State
    const [aiEvalEnabled, setAiEvalEnabled] = useState(false);
    const [rubricCriteria, setRubricCriteria] = useState<{ id: string; name: string; marks: number }[]>([]);
    
    const location = useLocation();
    const navigate = useNavigate();
    const searchParams = new URLSearchParams(location.search);
    const isNewRequest = searchParams.get('new') === 'true';

    const handleAddCriterion = () => {
        setRubricCriteria(prev => [...prev, { id: Date.now().toString(), name: '', marks: 5 }]);
    };
    
    const handleRemoveCriterion = (id: string) => {
        setRubricCriteria(prev => prev.filter(c => c.id !== id));
    };

    const handleUpdateCriterion = (id: string, field: 'name' | 'marks', value: string | number) => {
        setRubricCriteria(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c));
    };

    // Calculate total marks from rubric if enabled, otherwise use the static score
    const totalRubricMarks = rubricCriteria.reduce((sum, c) => sum + (Number(c.marks) || 0), 0);
    const effectiveMarks = aiEvalEnabled && rubricCriteria.length > 0 ? totalRubricMarks : marks;

    const handleNewAssessment = async () => {
        if (!window.confirm("Start a new assessment? This will clear all unsaved drafts.")) return;
        
        setExamName('');
        setExamDesc('');
        setInstructions('');
        setDuration(60);
        setMarks(100);
        setQuestionLimit('specific');
        setQuestionCount(10);
        setAllowAudio(true);
        setAiEvalEnabled(false);
        setRubricCriteria([]);
        setSelectedDocumentIds([]);
        setMessages([{ id: '1', role: 'bot', text: `✨ Welcome Professor ${user?.displayName || ''}! Let's build a new assessment.` }]);
        setCurrentQuizId(null);
        setFinalLink('');
        setQuizPassword('');

        try {
            // Tell backend to clear the current draft for this course
            await client.delete(`/professor/quiz/draft/1`);
        } catch (err) {
            console.error("Failed to clear draft", err);
        }
    };

    const toggleDocument = (id: number) => {
        setSelectedDocumentIds(prev => 
            prev.includes(id) ? prev.filter(docId => docId !== id) : [...prev, id]
        );
    };

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

    const [libraryDocs, setLibraryDocs] = useState<LibraryDocument[]>([]);
    const [messages, setMessages] = useState<ChatMessage[]>([
        { id: '1', role: 'bot', text: `✨ Welcome Professor ${user?.displayName || ''}! Upload your syllabus to start the simulation...` }
    ]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [isFinalizing, setIsFinalizing] = useState(false);
    const [quizPassword, setQuizPassword] = useState('');
    const [finalLink, setFinalLink] = useState('');
    const [currentQuizId, setCurrentQuizId] = useState<number | null>(null);
    const [showMathPalette, setShowMathPalette] = useState(false);
    const [isProcessingAudio, setIsProcessingAudio] = useState(false);

    const [seenQuestionIds, setSeenQuestionIds] = useState<number[]>([]);
    const [inputMessage, setInputMessage] = useState('');

    // Reset simulation history when document selection changes to avoid context leakage
    const selectionKey = JSON.stringify(selectedDocumentIds);
    useEffect(() => {
        // Clear history and seen question tracker when library selection changes
        setSeenQuestionIds([]);
        setMessages([
            { id: '1', role: 'bot', text: `✨ Context changed! Fresh generation active for: ${libraryDocs.filter(d => selectedDocumentIds.includes(d.id)).map(d => d.filename).join(', ') || 'No documents selected'}.` }
        ]);
        console.log("[Simulation] History cleared due to selection change:", selectionKey);
    }, [selectionKey]);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const initialTextRef = useRef('');

    const fileInputRef = useRef<HTMLInputElement>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const { isRecording: isAudioRecording, startRecording, stopRecording } = useAudioRecorder();
    const hasSpeechRecognition = !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

    const { isListening, startListening, stopListening: stopSTT } = useSpeechToText({
        onResult: (text) => {
            // Normalize math/finance terms live
            const normalized = normalizeMathTranscript(text);
            // Append transcribed text to whatever was already in the box when we started
            setInputMessage(initialTextRef.current ? `${initialTextRef.current} ${normalized}` : normalized);
        }
    });

    const toggleSpeech = async () => {
        if (isListening) {
            stopSTT();
        } else {
            // Store existing text so we can append to it
            initialTextRef.current = inputMessage;
            startListening();
        }
    };

    const insertMath = (symbol: string) => {
        const textarea = inputRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = inputMessage;
        const before = text.substring(0, start);
        const after = text.substring(end, text.length);

        setInputMessage(before + symbol + after);
        
        // Focus back and set cursor
        setTimeout(() => {
            textarea.focus();
            const newPos = start + symbol.length;
            textarea.setSelectionRange(newPos, newPos);
        }, 10);
    };


    const isRecording = hasSpeechRecognition ? isListening : isAudioRecording;

    const handleVoiceInput = async () => {
        if (hasSpeechRecognition) {
            if (isListening) {
                stopSTT();
            } else {
                initialTextRef.current = inputMessage;
                startListening();
            }
        } else {
            if (isAudioRecording) {
                setIsProcessingAudio(true);
                try {
                    const audioBlob = await stopRecording();
                    const response = await api.transcribeAudio(audioBlob);
                    const transcribedText = response.data.user_text;
                    if (transcribedText) {
                        setInputMessage(prev => {
                            const prefix = prev.trim();
                            return prefix ? prefix + " " + transcribedText : transcribedText;
                        });
                    }
                } catch (err) {
                    console.error("Transcription failed", err);
                    alert("Could not process voice input. Please try again.");
                } finally {
                    setIsProcessingAudio(false);
                }
            } else {
                await startRecording();
            }
        }
    };

    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        }
    }, [inputMessage]);



    const isFirstRender = useRef(true);

    // Fetch draft on mount
    useEffect(() => {
        (async () => {
            if (isNewRequest) {
                handleNewAssessment();
                navigate('/professor/create', { replace: true });
                return;
            }
            try {
                const { data } = await client.get('/professor/quiz/draft/1');
                if (data.draft) {
                    setExamName(data.draft.title || "");
                    setExamDesc(data.draft.description || "");
                    setDuration(data.draft.duration_minutes || 60);
                    setMarks(data.draft.total_marks || 100);
                    if (data.draft.total_questions === -1) {
                        setQuestionLimit('infinite');
                    } else {
                        setQuestionLimit('specific');
                        setQuestionCount(data.draft.total_questions || 5);
                    }
                    setInstructions(data.draft.instructions || "");
                    setAllowAudio(data.draft.allow_audio ?? true);
                    setAiEvalEnabled(data.draft.ai_eval_enabled ?? false);
                    if (data.draft.selected_document_ids) {
                        try {
                            setSelectedDocumentIds(JSON.parse(data.draft.selected_document_ids));
                        } catch (e) {
                            console.error("Failed to parse selected docs", e);
                        }
                    }
                    if (data.draft.ai_eval_rubric) {
                        try {
                            const parsed = JSON.parse(data.draft.ai_eval_rubric);
                            if (parsed.criteria) {
                                setRubricCriteria(parsed.criteria.map((c: any) => ({
                                    id: Math.random().toString(),
                                    name: c.name,
                                    marks: c.marks
                                })));
                            }
                        } catch (e) {
                            console.error("Failed to parse rubric draft", e);
                        }
                    }
                    if (data.draft.id) setCurrentQuizId(data.draft.id);
                }
            } catch (err) {
                console.error("Failed to load draft", err);
            }
        })();
    }, []);

    // Autosave draft
    useEffect(() => {
        if (isFirstRender.current) {
            isFirstRender.current = false;
            return;
        }

        const timeout = setTimeout(async () => {
            if (!examName && !instructions) return; // Don't aggressively save completely empty drafts
            try {
                let rubricJson = undefined;
                if (aiEvalEnabled && rubricCriteria.length > 0) {
                    rubricJson = JSON.stringify({
                        total_marks: effectiveMarks,
                        criteria: rubricCriteria.map(c => ({ name: c.name, marks: Number(c.marks) }))
                    });
                }
                
                await client.post('/professor/quiz/draft/1', {
                    title: examName,
                    description: examDesc,
                    duration_minutes: duration,
                    total_marks: effectiveMarks,
                    total_questions: questionLimit === 'infinite' ? -1 : questionCount,
                    instructions,
                    allow_audio: allowAudio,
                    ai_eval_enabled: aiEvalEnabled,
                    ai_eval_rubric: rubricJson,
                    selected_document_ids: JSON.stringify(selectedDocumentIds)
                });
            } catch (error) {
                console.error("Failed to auto-save draft", error);
            }
        }, 1500);

        return () => clearTimeout(timeout);
    }, [examName, examDesc, duration, marks, questionLimit, questionCount, instructions, allowAudio, aiEvalEnabled, rubricCriteria, effectiveMarks, selectedDocumentIds]);

    const fetchLibrary = async () => {
        try {
            const { data } = await client.get('/professor/documents/1');
            setLibraryDocs(data);
        } catch (err) {
            console.error("Failed to load library", err);
        }
    };

    // Check library docs on page load and poll
    useEffect(() => {
        fetchLibrary();

        const interval = setInterval(() => {
            setLibraryDocs(prev => {
                const needsPolling = prev.some(d => d.status !== 'FULLY_READY' && d.status !== 'FAILED');
                if (needsPolling) {
                    fetchLibrary();
                }
                return prev;
            });
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);


    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = e.target.files;
        if (!selectedFiles) return;

        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            
            // Optimistic UI add
            const tempId = Date.now() + i;
            setLibraryDocs(prev => [{
                id: tempId,
                filename: file.name,
                status: 'PENDING',
                error: null,
                created_at: new Date().toISOString()
            }, ...prev]);

            const formData = new FormData();
            formData.append('file', file);

            try {
                await client.post(`/professor/upload/1`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
                fetchLibrary();
            } catch (err: any) {
                console.error(err);
                alert(err.response?.data?.detail || "Upload failed");
                fetchLibrary();
            }
        }
        
        // Reset input so the same file can be uploaded again if needed
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleDeleteDocument = async (docId: number, filename: string) => {
        if (!window.confirm(`Are you sure you want to delete "${filename}"? All associated knowledge chunks will be destroyed.`)) return;

        try {
            // Optimistic delete
            setLibraryDocs(prev => prev.filter(d => d.id !== docId));
            await client.delete(`/professor/document/${docId}`);
            fetchLibrary();
        } catch (err: any) {
            console.error("Failed to delete document", err);
            alert(err.response?.data?.detail || "Failed to delete document.");
            fetchLibrary();
        }
    };

    const handleGenerate = async () => {
        if (!examName || !instructions) return alert("Please fill all fields");

        setIsGenerating(true);
        
        // Prepare rubric JSON if enabled
        let rubricJson = undefined;
        if (aiEvalEnabled && rubricCriteria.length > 0) {
            rubricJson = JSON.stringify({
                total_marks: effectiveMarks,
                criteria: rubricCriteria.map(c => ({ name: c.name, marks: Number(c.marks) }))
            });
        }
        
        try {
            const res = await client.post(`/professor/quiz/create`, null, {
                params: {
                    course_id: 1,
                    title: examName,
                    duration,
                    total_marks: effectiveMarks,
                    instructions,
                    total_questions: questionLimit === 'infinite' ? -1 : questionCount,
                    allow_audio: allowAudio,
                    ai_eval_enabled: aiEvalEnabled,
                    ai_eval_rubric: rubricJson,
                    selected_document_ids: JSON.stringify(selectedDocumentIds)
                }
            });
            setCurrentQuizId(res.data.quiz_id);
            await client.post(`/professor/generate/1`, null, { params: { total_marks: effectiveMarks } });
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
                    instructions: instructions,
                    selected_document_ids: JSON.stringify(selectedDocumentIds)
                }
            });
            if (data.reset) {
                setSeenQuestionIds([]);
                setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', text: '🔄 Variety cycle complete. Restarting...' }]);

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
            
            // Step 1: Force a final save of the configuration to ensure latest selections are in DB
            let rubricJson = undefined;
            if (aiEvalEnabled && rubricCriteria.length > 0) {
                rubricJson = JSON.stringify({
                    total_marks: effectiveMarks,
                    criteria: rubricCriteria.map(c => ({ name: c.name, marks: Number(c.marks) }))
                });
            }

            await client.post('/professor/quiz/draft/1', {
                title: examName || "Untitled Assessment",
                description: examDesc,
                duration_minutes: duration,
                total_marks: effectiveMarks,
                total_questions: questionLimit === 'infinite' ? -1 : questionCount,
                instructions,
                allow_audio: allowAudio,
                ai_eval_enabled: aiEvalEnabled,
                ai_eval_rubric: rubricJson,
                selected_document_ids: JSON.stringify(selectedDocumentIds)
            });

            // Step 2: Set password and lock the quiz
            await client.post(`/professor/quiz/${quizId}/finalize`, null, { params: { password: quizPassword } });
            
            // Step 3: Refresh the link with the latest quiz ID
            const newLink = `${window.location.origin}/student/quiz/${quizId}`;
            setFinalLink(newLink);
            alert("✨ Assessment is now LIVE. Link updated with latest changes!");
        } catch (err) {
            console.error("Finalization failed", err);
            alert("Finalization failed: Check your connection or password settings.");
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
            <aside className="w-[400px] p-6 border-r border-border overflow-y-auto flex flex-col gap-6 scrollbar-hide">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-bold text-gray-100 italic tracking-tight">Assessment Config</h3>
                </div>
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

                <div className="flex flex-col gap-3 p-4 border border-border rounded-xl bg-white/5 transition-all">
                    <div className="flex items-center justify-between">
                        <div className="flex flex-col gap-1">
                            <label className="text-sm font-medium text-gray-200">Enable AI Evaluation</label>
                            <span className="text-[10px] text-gray-400">Score answers against a custom rubric</span>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                className="sr-only peer"
                                checked={aiEvalEnabled}
                                onChange={e => {
                                    setAiEvalEnabled(e.target.checked);
                                    if (e.target.checked && rubricCriteria.length === 0) {
                                        handleAddCriterion(); // Add a default row when toggled on
                                    }
                                }}
                            />
                            <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none ring-0 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                        </label>
                    </div>

                    {aiEvalEnabled && (
                        <div className="flex flex-col gap-3 mt-2 pt-3 border-t border-white/10 animate-in fade-in slide-in-from-top-2 duration-300">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-xs font-bold uppercase tracking-widest text-[#a8b8d8]">Rubric Builder</span>
                                <span className="text-xs font-mono font-bold text-accent bg-accent/10 px-2 py-0.5 rounded">Total: {totalRubricMarks}</span>
                            </div>
                            
                            <div className="flex flex-col gap-2 max-h-[200px] overflow-y-auto pr-1 custom-scrollbar">
                                {rubricCriteria.map((c) => (
                                    <div key={c.id} className="flex items-center gap-2 bg-black/20 p-2 rounded-lg border border-white/5">
                                        <div className="flex-1">
                                            <input
                                                type="text"
                                                value={c.name}
                                                onChange={e => handleUpdateCriterion(c.id, 'name', e.target.value)}
                                                placeholder="e.g. Code correctness"
                                                className="w-full bg-transparent text-sm text-gray-200 focus:outline-none placeholder-gray-600"
                                            />
                                        </div>
                                        <div className="w-16 border-l border-white/10 pl-2">
                                            <input
                                                type="number"
                                                value={c.marks}
                                                onChange={e => handleUpdateCriterion(c.id, 'marks', parseInt(e.target.value) || 0)}
                                                className="w-full bg-transparent text-sm text-center text-accent font-mono focus:outline-none"
                                                min="1"
                                            />
                                        </div>
                                        <button
                                            onClick={() => handleRemoveCriterion(c.id)}
                                            className="p-1 text-red-400 hover:bg-red-400/20 rounded-md transition-colors"
                                            title="Remove criterion"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                            </div>
                            
                            <button
                                onClick={handleAddCriterion}
                                className="text-xs text-accent hover:text-white border border-accent/30 hover:bg-accent/20 border-dashed rounded-lg py-2 transition-all"
                            >
                                + Add Criterion
                            </button>
                        </div>
                    )}
                </div>

                <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-gray-200">Knowledge Library</label>
                        <button onClick={() => fileInputRef.current?.click()} className="text-xs text-accent hover:text-white transition-colors">
                            + Upload
                        </button>
                    </div>
                    <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" multiple />
                    
                    {libraryDocs.length === 0 ? (
                        <div
                            onClick={() => fileInputRef.current?.click()}
                            className="border border-border border-dashed rounded-2xl p-6 flex flex-col items-center justify-center bg-white/[0.02] hover:bg-white/[0.04] cursor-pointer transition-colors"
                        >
                            <span className="text-sm text-gray-400">Your library is empty.</span>
                            <span className="text-xs text-gray-500 mt-1">Upload files to build your knowledge base.</span>
                        </div>
                    ) : (
                        <ul className="flex flex-col gap-2 mt-2 max-h-[250px] overflow-y-auto pr-2 custom-scrollbar">
                            {libraryDocs.map((doc, idx) => {
                                let statusUI = <span className="text-gray-400 text-xs text-right">Waiting...</span>;
                                
                                if (doc.status === 'FAILED') {
                                    statusUI = (
                                        <div className="flex flex-col items-end">
                                            <span className="text-red-400 font-bold text-xs">❌ Failed</span>
                                            {doc.error && <span className="text-[10px] text-red-400/70 max-w-[200px] text-right truncate" title={doc.error}>{doc.error}</span>}
                                        </div>
                                    );
                                } else if (doc.status === 'COMPLETED') {
                                    statusUI = (
                                        <div className="flex flex-col items-end">
                                            <span className="text-green-400 text-xs">✅ Ready</span>
                                            <span className="text-[10px] text-gray-400 font-normal mt-0.5">Extracting Concepts (Bg)</span>
                                        </div>
                                    );
                                } else if (doc.status === 'CONCEPT_EXTRACTION') {
                                    statusUI = <span className="text-blue-400 animate-pulse text-xs text-right">⚙️ Extracting...</span>;
                                } else if (doc.status === 'FULLY_READY') {
                                    statusUI = <span className="text-green-400 font-bold text-xs text-right">🌟 Fully Optimised</span>;
                                } else if (doc.status !== 'PENDING') {
                                    const phase = doc.status.toLowerCase().replace('_', ' ');
                                    statusUI = <span className="text-accent animate-pulse text-xs text-right">⏳ Processing ({phase})</span>;
                                }

                                return (
                                    <li 
                                        key={doc.id || idx} 
                                        onClick={() => toggleDocument(doc.id)}
                                        className={`flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer ${
                                            selectedDocumentIds.includes(doc.id) 
                                            ? 'bg-accent/10 border-accent/40 ring-1 ring-accent/20 shadow-[0_0_15px_rgba(30,132,255,0.1)]' 
                                            : 'bg-white/[0.03] border-white/5 hover:bg-white/[0.06]'
                                        }`}
                                    >
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                                selectedDocumentIds.includes(doc.id) ? 'bg-accent border-accent' : 'bg-black/20 border-white/20'
                                            }`}>
                                                {selectedDocumentIds.includes(doc.id) && <Check size={10} className="text-white" />}
                                            </div>
                                            <FileText size={16} className={selectedDocumentIds.includes(doc.id) ? 'text-accent' : 'text-gray-500'} />
                                            <span className={`text-sm truncate pr-4 ${selectedDocumentIds.includes(doc.id) ? 'text-white font-medium' : 'text-gray-400'}`}>{doc.filename}</span>
                                        </div>
                                        <div className="shrink-0 ml-4 flex items-center justify-end gap-3">
                                            {statusUI}
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); handleDeleteDocument(doc.id, doc.filename); }}
                                                className="p-1.5 text-red-400 opacity-50 hover:opacity-100 hover:bg-red-400/20 rounded-md transition-all"
                                                title="Delete document"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>

                <Button
                    onClick={handleGenerate}
                    loading={isGenerating}
                    disabled={selectedDocumentIds.length === 0 || libraryDocs.filter(d => selectedDocumentIds.includes(d.id)).some(d => ['PENDING', 'VALIDATING', 'OCR_PROCESSING', 'CHUNKING', 'EMBEDDING'].includes(d.status))}
                    icon={RefreshCw}
                    className="mt-4"
                    title={selectedDocumentIds.length === 0 ? "Please select at least one document to generate questions" : ""}
                >
                    {isGenerating ? 'AI is generating...' : libraryDocs.filter(d => selectedDocumentIds.includes(d.id)).some(d => ['PENDING', 'VALIDATING', 'OCR_PROCESSING', 'CHUNKING', 'EMBEDDING'].includes(d.status)) ? 'Processing Selection...' : 'Generate Questions'}
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
                        {selectedDocumentIds.length === 0 && (
                            <div className="mb-3 px-3 py-2 bg-yellow-400/5 rounded-xl border border-yellow-400/20 flex items-center gap-2 text-yellow-400/80 text-[10px] uppercase tracking-widest font-bold animate-pulse">
                                <AlertCircle size={12} />
                                <span>Tick a document to enable AI interaction</span>
                            </div>
                        )}
                        <form onSubmit={handleSendMessage} className={`flex gap-3 items-end transition-opacity ${selectedDocumentIds.length === 0 ? 'opacity-40 grayscale pointer-events-none' : ''}`}>
                            <textarea
                                ref={inputRef}
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                placeholder="Type an answer to test AI adaptivity..."
                                className="flex-1 bg-white/[0.05] border border-white/10 rounded-2xl px-6 py-3 text-sm text-gray-100 focus:outline-none focus:border-accent transition-colors resize-none overflow-hidden min-h-[52px] max-h-[200px]"
                                disabled={isTyping || selectedDocumentIds.length === 0}
                                rows={1}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSendMessage(e);
                                    }
                                }}
                            />
                            <div className="flex gap-2 mb-1">
                                <div className="relative">
                                    {showMathPalette && (
                                        <MathPalette 
                                            onInsert={(s) => { insertMath(s); setShowMathPalette(false); }} 
                                            onClose={() => setShowMathPalette(false)} 
                                        />
                                    )}
                                    <button
                                        type="button"
                                        onClick={() => setShowMathPalette(!showMathPalette)}
                                        disabled={isTyping}
                                        className={`p-3 rounded-2xl transition-all ${showMathPalette ? 'bg-accent text-white shadow-lg' : 'bg-white/[0.05] text-gray-400 hover:text-accent'}`}
                                        title="Math Palette (Add Symbols)"
                                    >
                                        <Sigma size={18} />
                                    </button>
                                </div>

                                <button
                                    type="button"
                                    onClick={handleVoiceInput}
                                    disabled={isTyping || isProcessingAudio}
                                    className={`p-3 rounded-2xl transition-colors ${isRecording ? 'bg-red-500/20 text-red-500 animate-pulse' : 'bg-white/[0.05] text-gray-400 hover:text-accent'}`}
                                    title={isRecording ? 'Stop Listening' : 'Start Speech to Text'}
                                >
                                    {isProcessingAudio ? <Loader2 size={18} className="animate-spin" /> : isRecording ? <MicOff size={18} /> : <Mic size={18} />}
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

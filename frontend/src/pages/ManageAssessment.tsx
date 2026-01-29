import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { FileDown, User, Eye, History, Send } from 'lucide-react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { copyToClipboard } from '../utils/clipboard';

interface Participant {
    id: number;
    name: string;
    enrollment_id: string;
    completed_at: string;
}

interface ChatMessage {
    id: string;
    role: 'bot' | 'user';
    text: string;
    context?: string;
    questionId?: number;
}

export const ManageAssessment: React.FC = () => {
    const { quizId } = useParams();
    const [participants, setParticipants] = useState<Participant[]>([]);
    const [activeTab, setActiveTab] = useState<'preview' | 'transcript'>('preview');
    const [selectedStudent, setSelectedStudent] = useState<Participant | null>(null);
    const [studentMessages, setStudentMessages] = useState<ChatMessage[]>([]);
    const [quizMeta, setQuizMeta] = useState<any>(null);

    // Preview Tab States (Simulation)
    const [previewMessages, setPreviewMessages] = useState<ChatMessage[]>([
        { id: '1', role: 'bot', text: "👋 Welcome to the Assessment Preview. You can test your AI's behavior here before students join." }
    ]);
    const [isTyping, setIsTyping] = useState(false);
    const [inputMessage, setInputMessage] = useState('');
    const [seenQuestionIds, setSeenQuestionIds] = useState<number[]>([]);

    useEffect(() => {
        fetchParticipants();
        fetchQuizMeta();
    }, [quizId]);

    const fetchQuizMeta = async () => {
        try {
            const { data } = await client.get(`/professor/quiz/${quizId}`);
            setQuizMeta(data);
        } catch (err) {
            console.error("Failed to fetch quiz meta", err);
        }
    };

    const fetchParticipants = async () => {
        try {
            const { data } = await client.get(`/professor/quiz/${quizId}/transcripts`);
            setParticipants(data);
        } catch (err) {
            console.error("Failed to fetch students", err);
        } finally {
            // setLoading(false);
        }
    };

    const fetchMessagesForStudent = async (student: Participant) => {
        try {
            const { data } = await client.get(`/professor/quiz/${quizId}/student/${student.enrollment_id}/messages`);
            setStudentMessages(data.map((m: any, i: number) => ({
                id: i.toString(),
                role: m.role,
                text: m.text
            })));
        } catch (err) {
            console.error("Failed to fetch student messages", err);
        }
    };

    // Preview (Simulation) Logic
    const fetchNextPreviewQuestion = async (historyStr: string = "") => {
        if (!quizMeta) return;
        setIsTyping(true);
        try {
            const { data } = await client.get('/professor/simulate/next', {
                params: {
                    course_id: quizMeta.course_id,
                    exclude_ids: seenQuestionIds.join(','),
                    history: historyStr
                }
            });

            setSeenQuestionIds(prev => [...prev, data.id]);
            setPreviewMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'bot',
                text: data.text,
                context: data.context,
                questionId: data.id
            }]);
        } catch (err) {
            setPreviewMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', text: "No fresh questions available." }]);
        } finally {
            setIsTyping(false);
        }
    };

    const handleSendPreviewMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputMessage.trim() || isTyping) return;

        const userMsg = inputMessage;
        setInputMessage('');
        setPreviewMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', text: userMsg }]);

        const lastBotMsg = [...previewMessages].reverse().find(m => m.role === 'bot' && m.questionId);
        const historyPairs = lastBotMsg ? [`${lastBotMsg.text}|${userMsg}`] : [];

        await fetchNextPreviewQuestion(historyPairs.join(','));
    };

    const handleUpdateQuiz = async () => {
        try {
            await client.put(`/professor/quiz/${quizId}`, {
                title: quizMeta.title,
                duration: quizMeta.duration_minutes,
                instructions: quizMeta.instructions
            });
            alert("Assessment updated successfully!");
        } catch (err) {
            alert("Failed to update assessment");
        }
    };

    const handleExport = async () => {
        if (!selectedStudent) return;
        try {
            // Use window.location to trigger a direct download for simplicity
            const downloadUrl = `${client.defaults.baseURL}/professor/transcript/${selectedStudent.id}/export-pdf`;
            window.open(downloadUrl, '_blank');
        } catch (err) {
            alert("Export failed");
        }
    };

    return (
        <Layout title={`Manage Assessment: ${quizMeta?.title || ''}`}>
            <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {/* Tabs Header */}
                <div className="bg-white/[0.02] border-b border-border px-8">
                    <div className="flex gap-8">
                        <button
                            onClick={() => setActiveTab('preview')}
                            className={`py-4 text-sm font-bold uppercase tracking-widest border-b-2 transition-all flex items-center gap-2 ${activeTab === 'preview' ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
                        >
                            <Eye size={16} />
                            Preview & Configure
                        </button>
                        <button
                            onClick={() => setActiveTab('transcript')}
                            className={`py-4 text-sm font-bold uppercase tracking-widest border-b-2 transition-all flex items-center gap-2 ${activeTab === 'transcript' ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
                        >
                            <History size={16} />
                            Transcripts
                        </button>
                    </div>
                </div>

                {activeTab === 'preview' ? (
                    <div className="flex-1 flex overflow-hidden min-h-0">
                        {/* Configuration Sidebar */}
                        <aside className="w-[350px] border-r border-border p-6 overflow-y-auto flex flex-col gap-6 bg-white/[0.01]">
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Configuration</h3>
                            <Input
                                label="Name"
                                value={quizMeta?.title || ''}
                                onChange={e => setQuizMeta({ ...quizMeta, title: e.target.value })}
                            />
                            <Input
                                label="Instructions"
                                multiline
                                value={quizMeta?.instructions || ''}
                                onChange={e => setQuizMeta({ ...quizMeta, instructions: e.target.value })}
                                info="System instructions for the AI examiner"
                            />
                            <Input
                                label="Duration (Min)"
                                type="number"
                                value={quizMeta?.duration_minutes || 60}
                                onChange={e => setQuizMeta({ ...quizMeta, duration_minutes: parseInt(e.target.value) })}
                            />

                            <Button onClick={handleUpdateQuiz} variant="secondary" className="mt-4">
                                Save Changes
                            </Button>
                        </aside>

                        {/* Simulation Area */}
                        <div className="flex-1 overflow-hidden p-8 flex flex-col items-center min-h-0">
                            <div className="w-full h-full max-w-4xl bg-bg border border-border rounded-[32px] overflow-hidden flex flex-col shadow-2xl min-h-0">
                                <div className="px-6 py-4 border-b border-border bg-white/[0.02]">
                                    <h4 className="font-semibold text-gray-100 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-green-400" />
                                        Assessment AI Preview
                                    </h4>
                                    <p className="text-xs text-gray-400 mt-1">Test the AI flow with current instructions.</p>
                                </div>

                                <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 scrollbar-hide">
                                    {previewMessages.map((msg) => (
                                        <div key={msg.id} className={`max-w-[85%] rounded-[24px] p-4 text-sm leading-relaxed transition-all ${msg.role === 'bot'
                                            ? 'self-start bg-white/[0.05] border border-white/10 text-gray-100 rounded-bl-none'
                                            : 'self-end bg-accent text-[#062e6f] font-medium rounded-br-none'
                                            }`}>
                                            {msg.context && <small className="block opacity-60 mb-2 uppercase tracking-wider font-bold text-[10px]">{msg.context}</small>}
                                            {msg.text}
                                        </div>
                                    ))}
                                    {isTyping && (
                                        <div className="self-start bg-white/[0.03] rounded-[24px] p-4 flex gap-1 rounded-bl-none">
                                            <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" />
                                            <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.2s]" />
                                            <div className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce [animation-delay:0.4s]" />
                                        </div>
                                    )}
                                </div>

                                <form onSubmit={handleSendPreviewMessage} className="p-4 border-t border-border bg-white/[0.01] flex gap-3">
                                    <input
                                        type="text"
                                        value={inputMessage}
                                        onChange={(e) => setInputMessage(e.target.value)}
                                        placeholder="Test the AI's response..."
                                        className="flex-1 bg-white/[0.05] border border-white/10 rounded-2xl px-6 py-3 text-sm text-gray-100 focus:outline-none focus:border-accent"
                                        disabled={isTyping}
                                    />
                                    <Button type="submit" variant="secondary" className="px-6 rounded-2xl" disabled={!inputMessage.trim() || isTyping}>
                                        <Send size={18} />
                                    </Button>
                                </form>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex-1 flex overflow-hidden">
                        {/* Student Navbar Sidebar */}
                        <aside className="w-[300px] border-r border-border bg-white/[0.01] flex flex-col">
                            <div className="p-6 border-b border-border">
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest">Students applied</h3>
                            </div>
                            <div className="flex-1 overflow-y-auto">
                                {participants.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => {
                                            setSelectedStudent(p);
                                            fetchMessagesForStudent(p);
                                        }}
                                        className={`w-full p-6 flex items-center gap-4 text-left border-b border-border transition-colors ${selectedStudent?.enrollment_id === p.enrollment_id ? 'bg-accent/10 border-r-2 border-r-accent' : 'hover:bg-white/[0.02]'}`}
                                    >
                                        <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-accent">
                                            <User size={20} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-bold text-gray-100 truncate">{p.name}</p>
                                            <p className="text-xs text-gray-500 font-mono">{p.enrollment_id}</p>
                                        </div>
                                    </button>
                                ))}
                                {participants.length === 0 && (
                                    <div className="p-8 text-center text-gray-500 text-sm">No students yet.</div>
                                )}
                            </div>
                        </aside>

                        {/* Transcript Main Area */}
                        <main className="flex-1 bg-panel flex flex-col min-h-0">
                            {selectedStudent ? (
                                <>
                                    <div className="p-6 bg-white/[0.02] border-b border-border flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <h4 className="text-lg font-bold text-gray-100">{selectedStudent.name}</h4>
                                            <span className="px-2 py-0.5 bg-accent/10 text-accent rounded text-[10px] font-mono">{selectedStudent.enrollment_id}</span>
                                        </div>
                                        <Button variant="secondary" icon={FileDown} onClick={handleExport}>Export History</Button>
                                    </div>
                                    <div className="flex-1 overflow-y-auto p-8 flex flex-col gap-4 scrollbar-hide">
                                        {studentMessages.map((msg, i) => (
                                            <div key={i} className={`max-w-[85%] rounded-[24px] p-4 text-sm leading-relaxed ${msg.role === 'bot'
                                                ? 'self-start bg-white/[0.05] border border-white/10 text-gray-100 rounded-bl-none'
                                                : 'self-end bg-accent text-[#062e6f] font-medium rounded-br-none'
                                                }`}>
                                                {msg.text}
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-4">
                                    <div className="w-16 h-16 bg-white/[0.05] rounded-full flex items-center justify-center">
                                        <User size={32} />
                                    </div>
                                    <p>Select a student to view their assessment transcript.</p>
                                </div>
                            )}
                        </main>
                    </div>
                )}
            </div>
        </Layout>
    );
};

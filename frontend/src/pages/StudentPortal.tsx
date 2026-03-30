import React, { useState } from 'react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Search, LogIn } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const StudentPortal: React.FC = () => {
    const [quizId, setQuizId] = useState('');
    const navigate = useNavigate();

    const handleJoin = (e: React.FormEvent) => {
        e.preventDefault();
        if (quizId.trim()) {
            navigate(`/student/quiz/${quizId.trim()}`);
        }
    };

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center p-6 text-white font-sans">
            <div className="w-full max-w-lg bg-panel border border-border p-10 rounded-[40px] shadow-2xl relative overflow-hidden">
                {/* Background Glow */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 bg-primary/20 blur-[100px] -z-10" />

                <div className="flex flex-col items-center text-center gap-4 mb-10">
                    <div className="w-24 h-24 flex items-center justify-center bg-bg/50 rounded-3xl border border-border/50 p-4 mb-2 shadow-inner">
                        <img
                            src="/logo.png"
                            alt="AIssociate Logo"
                            className="w-full h-full object-contain mix-blend-screen"
                        />
                    </div>
                    <div>
                        <h2 className="text-4xl font-black bg-clip-text text-transparent bg-gradient-to-br from-white via-white to-white/50 tracking-tight">Student Portal</h2>
                        <p className="text-gray-400 mt-3 font-medium text-lg">Enter your Assessment ID to begin.</p>
                    </div>
                </div>

                <form onSubmit={handleJoin} className="flex flex-col gap-8">
                    <div className="relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-primary/50 to-blue-500/50 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                        <Input
                            label="Assessment ID"
                            value={quizId}
                            onChange={e => setQuizId(e.target.value)}
                            placeholder="e.g. 12"
                            required
                            className="relative bg-bg/80 border-border/50 focus:border-primary text-xl py-6 pl-12 rounded-2xl"
                        />
                        <Search className="absolute left-4 top-[52px] text-gray-500 group-hover:text-primary transition-colors" size={20} />
                    </div>

                    <Button 
                        type="submit" 
                        className="w-full py-5 text-xl font-bold rounded-2xl shadow-lg hover:shadow-primary/20 transform hover:-translate-y-1 transition-all duration-200"
                        icon={LogIn}
                    >
                        Join Assessment
                    </Button>
                </form>

                <div className="mt-12 pt-8 border-t border-border/30 text-center">
                    <p className="text-sm text-gray-500 font-medium">
                        Secure Assessment Environment • AI Powered Evaluation
                    </p>
                </div>
            </div>
        </div>
    );
};

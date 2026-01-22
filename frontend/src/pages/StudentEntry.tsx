import React, { useState } from 'react';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { ShieldCheck, PlayCircle } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import client from '../api/client';

export const StudentEntry: React.FC = () => {
    const [name, setName] = useState('');
    const [enrollmentId, setEnrollmentId] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const { quizId } = useParams();
    const navigate = useNavigate();

    const handleStart = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !enrollmentId || !password) {
            setError("Please fill in all fields.");
            return;
        }

        setLoading(true);
        try {
            await client.post(`/student/quiz/start/${quizId}`, { name, enrollmentId, password });
            navigate(`/student/quiz/${quizId}/active`, { state: { name, enrollmentId } });
        } catch (err: any) {
            if (err.response?.status === 401) {
                setError("Incorrect access password. Please contact your professor.");
            } else {
                setError("Assessment not found or connection error.");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center p-6">
            <div className="w-full max-w-lg bg-panel border border-border p-10 rounded-[40px] shadow-2xl">
                <div className="flex flex-col items-center text-center gap-4 mb-10">
                    <div className="w-20 h-20 flex items-center justify-center">
                        <img
                            src="/logo.png"
                            alt="AU Quiz Bot Logo"
                            className="w-full h-full object-contain mix-blend-screen"
                        />
                    </div>
                    <div>
                        <h2 className="text-3xl font-bold text-gray-100">Student Entry</h2>
                        <p className="text-gray-400 mt-2">Enter your details to begin the assessment.</p>
                    </div>
                </div>

                <form onSubmit={handleStart} className="flex flex-col gap-6">
                    <div className="space-y-4">
                        <Input
                            label="Full Name"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g. Suryaraj Sinh Jadeja"
                            required
                        />
                        <Input
                            label="Enrollment ID"
                            value={enrollmentId}
                            onChange={e => setEnrollmentId(e.target.value)}
                            placeholder="e.g. AU2XXXXXXX"
                            required
                        />
                        <div className="relative">
                            <Input
                                label="Access Password"
                                type="password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="Required to start"
                                required
                            />
                            <ShieldCheck className="absolute right-4 top-11 text-gray-600" size={18} />
                        </div>
                    </div>

                    {error && (
                        <div className="p-3 bg-red-400/10 border border-red-400/20 rounded-xl text-red-400 text-sm text-center">
                            {error}
                        </div>
                    )}

                    <Button type="submit" loading={loading} className="w-full py-4 text-lg mt-4" icon={PlayCircle}>
                        Start Assessment
                    </Button>
                </form>

                <p className="text-center text-xs text-gray-500 mt-8">
                    By starting this assessment, you agree to the university's academic integrity policies.
                </p>
            </div>
        </div>
    );
};

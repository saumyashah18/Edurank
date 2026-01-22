import React, { useState } from 'react';
import { signInWithPopup, signInWithEmailAndPassword, createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';
import { auth, googleProvider } from '../api/firebase';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Input } from '../components/Input';

export const AuthPage: React.FC<{ mode: 'login' | 'signup' }> = ({ mode }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!email.endsWith('@ahduni.edu.in')) {
            setError('Only @ahduni.edu.in emails are allowed.');
            return;
        }

        setLoading(true);
        try {
            if (mode === 'signup') {
                const res = await createUserWithEmailAndPassword(auth, email, password);
                await updateProfile(res.user, { displayName: name });
            } else {
                await signInWithEmailAndPassword(auth, email, password);
            }
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const signInWithGoogle = async () => {
        try {
            const res = await signInWithPopup(auth, googleProvider);
            if (res.user.email?.endsWith('@ahduni.edu.in')) {
                navigate('/dashboard');
            } else {
                await auth.signOut();
                setError('Only @ahduni.edu.in emails are allowed.');
            }
        } catch (err: any) {
            setError(err.message);
        }
    };

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center p-6">
            <div className="w-full max-w-md bg-panel border border-border p-8 rounded-[32px] shadow-2xl">
                <div className="flex flex-col items-center gap-4 mb-8">
                    <div className="w-20 h-20 flex items-center justify-center">
                        <img
                            src="/logo.png"
                            alt="AU Quiz Bot Logo"
                            className="w-full h-full object-contain mix-blend-screen"
                        />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-100">AU Quiz Bot</h1>
                    <p className="text-gray-400 text-sm">Professor {mode === 'login' ? 'Sign In' : 'Registration'}</p>
                </div>

                <form onSubmit={handleAuth} className="flex flex-col gap-4">
                    {mode === 'signup' && (
                        <Input label="Full Name" value={name} onChange={e => setName(e.target.value)} placeholder="Professor Name" required />
                    )}
                    <Input label="University Email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name.ea@ahduni.edu.in" required />
                    <Input label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />

                    {error && <p className="text-red-400 text-xs px-2">{error}</p>}

                    <Button type="submit" loading={loading} className="w-full mt-4">
                        {mode === 'login' ? 'Sign In' : 'Create Account'}
                    </Button>
                </form>

                <div className="mt-6 flex flex-col gap-4">
                    <div className="relative flex items-center justify-center">
                        <div className="border-t border-border w-full"></div>
                        <span className="bg-panel px-3 text-xs text-gray-500 absolute">OR</span>
                    </div>

                    <Button variant="outline" onClick={signInWithGoogle} className="w-full">
                        Continue with Google
                    </Button>

                    <p className="text-center text-xs text-gray-400">
                        {mode === 'login' ? "Don't have an account? " : "Already have an account? "}
                        <span
                            className="text-accent cursor-pointer hover:underline"
                            onClick={() => navigate(mode === 'login' ? '/signup' : '/login')}
                        >
                            {mode === 'login' ? 'Sign Up' : 'Sign In'}
                        </span>
                    </p>
                </div>
            </div>
        </div>
    );
};

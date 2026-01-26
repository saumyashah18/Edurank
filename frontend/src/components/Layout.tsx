import React from 'react';
import { Save } from 'lucide-react';
import { Button } from './Button';

interface LayoutProps {
    children: React.ReactNode;
    title: string;
    onSave?: () => void;
    saveLoading?: boolean;
}

export const Layout: React.FC<LayoutProps> = ({ children, title, onSave, saveLoading }) => {
    return (
        <div className="h-screen flex flex-col bg-bg overflow-hidden">
            <header className="flex items-center justify-between px-6 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                    <img src="/logo.png" alt="Dialogue box Logo" className="w-9 h-9 object-contain mix-blend-screen" />
                    <h1 className="text-xl font-semibold text-gray-100">{title}</h1>
                </div>
                {onSave && (
                    <Button icon={Save} loading={saveLoading} onClick={onSave}>
                        Finalize & Save Assessment
                    </Button>
                )}
            </header>
            <main className="flex-1 flex overflow-hidden">
                {children}
            </main>
        </div>
    );
};

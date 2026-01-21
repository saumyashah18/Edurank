import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement> {
    label: string;
    multiline?: boolean;
    info?: string;
}

export const Input: React.FC<InputProps> = ({ label, multiline, info, className = '', ...props }) => {
    const Component = multiline ? 'textarea' : 'input';

    return (
        <div className={`flex flex-col gap-2 ${className}`}>
            <label className="text-sm font-medium text-gray-200 flex items-center gap-2">
                {label}
                {info && (
                    <span className="w-4 h-4 rounded-full bg-border text-[10px] flex items-center justify-center cursor-help" title={info}>
                        i
                    </span>
                )}
            </label>
            <Component
                className="bg-transparent border border-border rounded-lg p-3 text-gray-100 focus:outline-none focus:border-accent transition-colors"
                {...props as any}
            />
        </div>
    );
};

import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement> {
    label: string;
    multiline?: boolean;
    info?: string;
}

export const Input: React.FC<InputProps> = ({ label, multiline, info, className = '', ...props }) => {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    React.useEffect(() => {
        if (multiline && textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [props.value, multiline]);

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
            {multiline ? (
                <textarea
                    ref={textareaRef}
                    className="bg-transparent border border-border rounded-lg p-3 text-gray-100 focus:outline-none focus:border-accent transition-colors resize-none overflow-y-auto scrollbar-thin min-h-[48px] max-h-[200px]"
                    {...props as any}
                    rows={1}
                />
            ) : (
                <input
                    className="bg-transparent border border-border rounded-lg p-3 text-gray-100 focus:outline-none focus:border-accent transition-colors"
                    {...props as any}
                />
            )}
        </div>
    );
};

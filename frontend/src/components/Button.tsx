import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'outline' | 'danger';
    icon?: LucideIcon;
    loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
    children,
    variant = 'primary',
    icon: Icon,
    loading,
    className = '',
    ...props
}) => {
    const baseStyles = "flex items-center justify-center gap-2 px-4 py-2 rounded-full font-semibold transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed";

    const variants = {
        primary: "bg-accent text-[#062e6f] hover:scale-105",
        secondary: "bg-panel text-gray-200 hover:bg-border",
        outline: "border border-border text-gray-200 hover:bg-white/5",
        danger: "border border-red-400 text-red-400 hover:bg-red-400/10",
    };

    return (
        <button
            className={`${baseStyles} ${variants[variant]} ${className}`}
            disabled={loading || props.disabled}
            {...props}
        >
            {loading ? (
                <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : Icon && <Icon size={20} />}
            {children}
        </button>
    );
};

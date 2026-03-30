import React from 'react';
import { X } from 'lucide-react';

interface MathPaletteProps {
    onInsert: (latex: string) => void;
    onClose: () => void;
}

const SYMBOL_GROUPS = [
    {
        name: 'Greek Letters — Core',
        symbols: [
            { label: 'β', value: 'β' }, { label: 'α', value: 'α' }, { label: 'σ', value: 'σ' }, { label: 'Σ', value: 'Σ' },
            { label: 'μ', value: 'μ' }, { label: 'ρ', value: 'ρ' }, { label: 'δ', value: 'δ' }, { label: 'Δ', value: 'Δ' },
            { label: 'γ', value: 'γ' }, { label: 'θ', value: 'θ' }, { label: 'λ', value: 'λ' }, { label: 'π', value: 'π' },
            { label: 'Π', value: 'Π' }, { label: 'ε', value: 'ε' }, { label: 'ν', value: 'ν' }, { label: 'τ', value: 'τ' },
            { label: 'φ', value: 'φ' }, { label: 'Φ', value: 'Φ' }, { label: 'ω', value: 'ω' }, { label: 'η', value: 'η' },
        ]
    },
    {
        name: 'Operators & Relations',
        symbols: [
            { label: '≈', value: '≈' }, { label: '≠', value: '≠' }, { label: '≥', value: '≥' }, { label: '≤', value: '≤' },
            { label: '∝', value: '∝' }, { label: '±', value: '±' }, { label: '×', value: '×' }, { label: '÷', value: '÷' },
            { label: '√', value: '\\sqrt{}' }, { label: '∛', value: '\\sqrt[3]{}' }, { label: '∞', value: '∞' }, { label: '∂', value: '∂' },
            { label: '∫', value: '∫' }, { label: '→', value: '→' }, { label: '⇒', value: '⇒' },
        ]
    },
    {
        name: 'Valuation & Finance Specific',
        symbols: [
            { label: 'r̄', value: 'r̄' }, { label: 'E[]', value: 'E[]' }, { label: 'ℙ', value: 'ℙ' }, { label: 'ℚ', value: 'ℚ' },
            { label: '∀', value: '∀' }, { label: '∃', value: '∃' }, { label: '∈', value: '∈' }, { label: '∉', value: '∉' },
            { label: '⊂', value: '⊂' }, { label: '∩', value: '∩' }, { label: '∪', value: '∪' },
            { label: 'ℝ', value: 'ℝ' }, { label: 'ℤ', value: 'ℤ' }, { label: 'Cov(X,Y)', value: 'Cov(X,Y)' }, { label: 'Var(X)', value: 'Var(X)' },
        ]
    },
    {
        name: 'Superscripts & Subscripts',
        symbols: [
            { label: 'xⁿ', value: '^{}' }, { label: 'x²', value: '^{2}' }, { label: 'x³', value: '^{3}' },
            { label: 'x⁻¹', value: '^{-1}' }, { label: 'xᵢ', value: '_{i}' }, { label: 'Xₜ', value: '_{t}' },
        ]
    }
];

export const MathPalette: React.FC<MathPaletteProps> = ({ onInsert, onClose }) => {
    return (
        <div className="absolute bottom-full mb-4 right-0 bg-[#0a0a0b] border border-white/10 rounded-2xl shadow-2xl p-4 w-[360px] max-h-[450px] overflow-y-auto scrollbar-hide animate-in fade-in slide-in-from-bottom-2 duration-200 z-50">
            <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-2 sticky top-0 bg-[#0a0a0b] z-10">
                <span className="text-[10px] uppercase font-bold tracking-widest text-[#a8b8d8]">Math Palette</span>
                <button onClick={onClose} className="p-1 hover:bg-white/5 rounded-lg text-gray-500 transition-colors">
                    <X size={14} />
                </button>
            </div>
            
            <div className="flex flex-col gap-6">
                {SYMBOL_GROUPS.map((group, gIdx) => (
                    <div key={gIdx} className="flex flex-col gap-2">
                        <h5 className="text-[9px] uppercase font-bold tracking-wider text-gray-500 mb-1">{group.name}</h5>
                        <div className="grid grid-cols-5 gap-2">
                            {group.symbols.map((s, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => onInsert(s.value)}
                                    className="h-10 flex flex-col items-center justify-center bg-white/[0.03] hover:bg-accent hover:text-white border border-white/5 rounded-xl transition-all active:scale-95 group relative"
                                    title={s.label}
                                >
                                    <span className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">{s.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
            
            <div className="mt-6 pt-2 border-t border-white/5">
                <p className="text-[9px] text-gray-500 text-center italic">Tip: Symbols insert at cursor position</p>
            </div>
        </div>
    );
};

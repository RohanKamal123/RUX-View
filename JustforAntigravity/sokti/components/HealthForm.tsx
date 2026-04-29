'use client';

import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface HealthFormProps {
    onSubmit: (data: { fitnessLevel: string; injuries: string[] }) => void;
    isLoading: boolean;
}

export function HealthForm({ onSubmit, isLoading }: HealthFormProps) {
    const [fitnessLevel, setFitnessLevel] = useState('Beginner');
    const [injuriesInput, setInjuriesInput] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const injuries = injuriesInput
            .split(',')
            .map((i) => i.trim())
            .filter((i) => i.length > 0);
        onSubmit({ fitnessLevel, injuries });
    };

    return (
        <form onSubmit={handleSubmit} className="w-full max-w-md space-y-6">
            <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
                    Fitness Level
                </label>
                <div className="grid grid-cols-3 gap-2">
                    {['Beginner', 'Intermediate', 'Advanced'].map((level) => (
                        <button
                            key={level}
                            type="button"
                            onClick={() => setFitnessLevel(level)}
                            className={`px-4 py-3 rounded-xl text-sm font-medium transition-all border ${fitnessLevel === level
                                    ? 'bg-emerald-500 text-white border-emerald-500 shadow-lg shadow-emerald-500/20'
                                    : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800'
                                }`}
                        >
                            {level}
                        </button>
                    ))}
                </div>
            </div>

            <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
                    Injuries / Issues
                </label>
                <input
                    type="text"
                    value={injuriesInput}
                    onChange={(e) => setInjuriesInput(e.target.value)}
                    placeholder="e.g. knees, back (comma separated)"
                    className="w-full px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800 text-white placeholder-zinc-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
                />
            </div>

            <button
                type="submit"
                disabled={isLoading}
                className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-bold text-lg shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
                {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                    <>
                        <Search className="w-5 h-5" />
                        Find Exercises
                    </>
                )}
            </button>
        </form>
    );
}

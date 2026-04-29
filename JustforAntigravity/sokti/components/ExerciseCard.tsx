import { Activity, AlertCircle, CheckCircle2 } from 'lucide-react';

interface Exercise {
    id: number;
    name: string;
    description: string;
    difficulty: string;
    category: string;
    contraindications: string | null;
}

export function ExerciseCard({ exercise }: { exercise: Exercise }) {
    const difficultyColor = {
        Beginner: 'bg-green-500/10 text-green-500 border-green-500/20',
        Intermediate: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
        Advanced: 'bg-red-500/10 text-red-500 border-red-500/20',
    }[exercise.difficulty] || 'bg-gray-500/10 text-gray-500';

    return (
        <div className="group relative overflow-hidden rounded-2xl bg-zinc-900 border border-zinc-800 p-6 transition-all hover:border-zinc-700 hover:shadow-xl hover:shadow-zinc-900/50">
            <div className="absolute inset-0 bg-gradient-to-br from-zinc-800/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

            <div className="relative">
                <div className="flex items-start justify-between mb-4">
                    <div className={`px-3 py-1 rounded-full text-xs font-medium border ${difficultyColor}`}>
                        {exercise.difficulty}
                    </div>
                    <div className="text-zinc-500 text-xs uppercase tracking-wider font-semibold">
                        {exercise.category}
                    </div>
                </div>

                <h3 className="text-xl font-bold text-white mb-2 group-hover:text-emerald-400 transition-colors">
                    {exercise.name}
                </h3>

                <p className="text-zinc-400 text-sm leading-relaxed mb-4">
                    {exercise.description}
                </p>

                {exercise.contraindications && (
                    <div className="flex items-start gap-2 text-xs text-rose-400 bg-rose-500/5 p-3 rounded-lg border border-rose-500/10">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>Caution: {exercise.contraindications}</span>
                    </div>
                )}
            </div>
        </div>
    );
}

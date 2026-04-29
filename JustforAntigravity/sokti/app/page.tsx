'use client';

import { useState } from 'react';
import { HealthForm } from '@/components/HealthForm';
import { ExerciseCard } from '@/components/ExerciseCard';
import { Dumbbell, HeartPulse } from 'lucide-react';

interface Exercise {
  id: number;
  name: string;
  description: string;
  difficulty: string;
  category: string;
  contraindications: string | null;
}

export default function Home() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const fetchExercises = async (data: { fitnessLevel: string; injuries: string[] }) => {
    setLoading(true);
    try {
      const response = await fetch('/api/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      setExercises(result);
      setHasSearched(true);
    } catch (error) {
      console.error('Failed to fetch exercises', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-black text-white selection:bg-emerald-500/30">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-900/20 via-zinc-900/0 to-zinc-900/0 pointer-events-none" />

      <div className="container mx-auto px-4 py-12 relative z-10">
        <header className="flex flex-col items-center text-center mb-16 space-y-4">
          <div className="flex items-center gap-3 text-emerald-500 mb-2">
            <Dumbbell className="w-8 h-8" />
            <span className="text-2xl font-bold tracking-tighter">SOKTI</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight bg-gradient-to-b from-white to-zinc-500 bg-clip-text text-transparent">
            Your Personal <br /> Fitness Journey
          </h1>
          <p className="text-zinc-400 text-lg max-w-lg mx-auto">
            Get personalized exercise recommendations based on your health profile and fitness goals.
          </p>
        </header>

        <div className="flex flex-col items-center mb-20">
          <HealthForm onSubmit={fetchExercises} isLoading={loading} />
        </div>

        {hasSearched && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
            <div className="flex items-center gap-3 text-xl font-semibold text-white/90 px-4">
              <HeartPulse className="w-6 h-6 text-emerald-500" />
              <h2>Recommended Exercises</h2>
              <span className="text-sm font-normal text-zinc-500 ml-auto">
                {exercises.length} results found
              </span>
            </div>

            {exercises.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {exercises.map((exercise) => (
                  <ExerciseCard key={exercise.id} exercise={exercise} />
                ))}
              </div>
            ) : (
              <div className="text-center py-20 bg-zinc-900/50 rounded-3xl border border-zinc-800 border-dashed">
                <p className="text-zinc-500">No exercises found matching your criteria.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

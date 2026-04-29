import React, { useState, useEffect } from 'react';
import {
    ChevronLeft, ChevronRight, Database, Cpu, ShieldCheck,
    ArrowRight, Package, Share2, Layers, Key, Maximize, UserCheck,
    Globe, Layout, Search, Bell, History, CheckCircle2, AlertCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';

// --- Sub-Components ---

const CodeBlock = ({ code, label }) => (
    <div className="bg-gray-900 rounded-3xl p-8 font-mono text-[11px] text-orange-400 shadow-2xl overflow-hidden relative group">
        <div className="flex gap-2 mb-6 border-b border-white/10 pb-4">
            <div className="w-2 h-2 rounded-full bg-red-500"></div>
            <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
            <div className="w-2 h-2 rounded-full bg-green-500"></div>
            <span className="ml-4 text-[9px] text-gray-600 uppercase tracking-widest">{label}</span>
        </div>
        <div className="whitespace-pre overflow-x-auto text-orange-300/90 leading-relaxed">
            {code}
        </div>
    </div>
);

const FeatureHighlight = ({ icon: Icon, title, desc }) => (
    <div className="flex gap-4 p-6 rounded-3xl bg-gray-50 border border-gray-100 hover:border-orange-200 transition-all">
        <div className="w-12 h-12 rounded-2xl bg-white border border-gray-100 flex items-center justify-center flex-shrink-0 shadow-sm">
            <Icon size={20} className="text-orange-600" />
        </div>
        <div>
            <h4 className="font-black text-gray-900 uppercase text-[10px] tracking-widest mb-1">{title}</h4>
            <p className="text-gray-500 text-xs font-medium leading-relaxed">{desc}</p>
        </div>
    </div>
);

// --- Main Presentation Component ---

const LFMSPortfolio = () => {
    const [currentSlide, setCurrentSlide] = useState(0);

    const slides = [
        // Slide 0: Title
        {
            content: (
                <div className="text-center">
                    <p className="text-orange-500 font-black uppercase tracking-[0.4em] mb-4 text-xs">University Logistics Solution</p>
                    <h1 className="text-7xl lg:text-[10rem] font-black text-gray-900 tracking-tighter uppercase leading-[0.8] mb-8">
                        Find-X <br /> <span className="text-gray-200">LFMS V2.0</span>
                    </h1>
                    <p className="text-xl text-gray-500 font-medium max-w-2xl mx-auto leading-relaxed">
                        A modern, high-security Lost and Found Management System designed for institutional scale.
                    </p>
                </div>
            )
        },
        // Slide 1: Problem Statement
        {
            content: (
                <div className="max-w-5xl w-full">
                    <h2 className="text-4xl lg:text-5xl font-black text-gray-900 uppercase tracking-tighter mb-12">Current <span className="text-orange-600">Inefficiencies</span></h2>
                    <div className="grid md:grid-cols-2 gap-12">
                        <div className="space-y-6">
                            <FeatureHighlight
                                icon={AlertCircle}
                                title="Data Decay"
                                desc="Physical logs are unsearchable and easily damaged, leading to lost item history."
                            />
                            <FeatureHighlight
                                icon={ShieldCheck}
                                title="Verification Gap"
                                desc="Manual verification relies on memory, making high-value assets vulnerable to fraud."
                            />
                            <FeatureHighlight
                                icon={Bell}
                                title="Passive Recovery"
                                desc="Traditional systems wait for the loser to check, rather than actively notifying matching owners."
                            />
                        </div>
                        <div className="bg-gray-50 p-12 rounded-[4rem] border border-gray-100 flex items-center justify-center">
                            <History size={160} className="text-gray-200" />
                        </div>
                    </div>
                </div>
            )
        },
        // Slide 2: Full ERD Model (The Image)
        {
            content: (
                <div className="w-full h-full flex flex-col items-center">
                    <h2 className="text-4xl font-black text-gray-900 uppercase tracking-tighter mb-8 self-start">The <span className="text-orange-600">Data Schema</span></h2>
                    <div className="flex-1 w-full bg-gray-50 rounded-[3rem] border border-gray-100 overflow-hidden relative group">
                        <div className="absolute inset-0 flex items-center justify-center p-4">
                            <img
                                src="/assets/docs/erd_full.jpg"
                                alt="Full ERD Model"
                                className="max-w-full max-h-full object-contain shadow-2xl rounded-xl"
                            />
                        </div>
                        <div className="absolute inset-x-0 bottom-0 p-8 bg-gradient-to-t from-white/90 to-transparent flex justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                            <span className="text-[10px] font-black text-gray-400 uppercase tracking-[0.4em]">Proprietary Relational Database Architecture</span>
                        </div>
                    </div>
                </div>
            )
        },
        // Slide 3: Database Entities
        {
            content: (
                <div className="max-w-5xl w-full">
                    <h2 className="text-4xl font-black text-gray-900 uppercase tracking-tighter mb-12">Entity Breakdown</h2>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                        {[
                            { t: 'User System', d: 'RBAC (Student/Staff/Admin) with fraud indexing.', i: UserCheck },
                            { t: 'Item Hub', d: 'Path-A/B logic with state-transition tracking.', i: Package },
                            { t: 'Claim Engine', d: 'Multi-stage validation with quiz logging.', i: Key },
                            { t: 'Audit Lab', d: 'Immutable logs for every transaction & state change.', i: History }
                        ].map((f, i) => (
                            <div key={i} className="p-8 border border-gray-100 rounded-3xl bg-white hover:bg-orange-50/30 transition-all border-b-4 hover:border-orange-500">
                                <f.i size={30} className="text-orange-500 mb-4" />
                                <h3 className="font-black uppercase text-[10px] tracking-widest mb-2 leading-none">{f.t}</h3>
                                <p className="text-gray-500 text-[10px] font-bold uppercase tracking-wider">{f.d}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )
        },
        // Slide 4: AI & Computer Vision Logic
        {
            content: (
                <div className="max-w-6xl w-full grid lg:grid-cols-2 gap-20 items-center">
                    <div className="space-y-12">
                        <h2 className="text-5xl font-black text-gray-900 uppercase tracking-tighter leading-none">Neural <br /> Verification</h2>
                        <div className="grid gap-6">
                            <FeatureHighlight
                                icon={Maximize}
                                title="OpenCV OCR"
                                desc="Automatic extraction of student IDs from card photos using edge detection and contour analysis."
                            />
                            <FeatureHighlight
                                icon={Globe}
                                title="Gemini-AI Bridge"
                                desc="Generates unique, context-aware challenge questions based on item metadata (Path-B)."
                            />
                        </div>
                    </div>
                    <CodeBlock
                        label="verification_node.py"
                        code={`# AI Verification Challenge Logic
def generate_verification_quiz(item_id: int):
    item = db.items.get(item_id)
    prompt = f"Given item {item.title}, create 3 gated questions..."
    
    challenge = gemini.generate(prompt)
    if challenge.confidence > 0.94:
        return challenge.questions
    else:
        return fallback_to_path_a()`}
                    />
                </div>
            )
        },
        // Slide 5: Path-A vs Path-B Logistics
        {
            content: (
                <div className="max-w-5xl w-full">
                    <h2 className="text-4xl font-black text-gray-900 uppercase tracking-tighter mb-12">Workflow Logistics</h2>
                    <div className="grid md:grid-cols-2 gap-10">
                        <div className="p-10 bg-gray-950 rounded-[3rem] text-white">
                            <span className="text-orange-500 font-black uppercase text-[10px] tracking-widest">Protocol Alpha</span>
                            <h3 className="text-3xl font-black uppercase tracking-tighter mt-4 mb-6">Direct Path-A</h3>
                            <p className="text-gray-400 text-sm font-medium mb-8">Direct Student-to-Student handover gated by dynamic OTP tokens. No institutional intervention required.</p>
                            <div className="flex gap-2">
                                <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/10 text-[9px] font-black uppercase">OTP-Gated</div>
                                <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/10 text-[9px] font-black uppercase">P2P Link</div>
                            </div>
                        </div>
                        <div className="p-10 bg-orange-600 rounded-[3rem] text-white">
                            <span className="text-white/60 font-black uppercase text-[10px] tracking-widest">Protocol Beta</span>
                            <h3 className="text-3xl font-black uppercase tracking-tighter mt-4 mb-6">Secure Path-B</h3>
                            <p className="text-orange-100 text-sm font-medium mb-8">Staff-mediated handover via the Room 110 Digital Terminal. Requires AI-verified session tokens.</p>
                            <div className="flex gap-2">
                                <div className="px-4 py-2 bg-black/10 rounded-xl border border-white/20 text-[9px] font-black uppercase">Admin Auth</div>
                                <div className="px-4 py-2 bg-black/10 rounded-xl border border-white/20 text-[9px] font-black uppercase">Staff Lead</div>
                            </div>
                        </div>
                    </div>
                </div>
            )
        },
        // Slide 6: Outro
        {
            content: (
                <div className="text-center">
                    <h2 className="text-8xl lg:text-[12rem] font-black text-gray-900 uppercase tracking-tighter mb-6">Ready.</h2>
                    <p className="text-gray-400 font-extrabold uppercase tracking-[0.8em] mb-16 text-sm italic">Find-X Institutional Deployment 2026</p>
                    <Link to="/" className="inline-flex items-center gap-4 bg-gray-900 text-white px-12 py-6 rounded-3xl font-black uppercase text-xs tracking-[0.3em] hover:bg-orange-600 transition-all shadow-2xl group">
                        Launch Live Application <ArrowRight size={20} className="group-hover:translate-x-2 transition-transform" />
                    </Link>
                </div>
            )
        }
    ];

    const nextSlide = () => setCurrentSlide(prev => (prev + 1) % slides.length);
    const prevSlide = () => setCurrentSlide(prev => (prev - 1 + slides.length) % slides.length);

    useEffect(() => {
        const handleKeys = (e) => {
            if (e.key === 'ArrowRight' || e.key === 'Space' || e.key === 'Enter') nextSlide();
            if (e.key === 'ArrowLeft') prevSlide();
        };
        window.addEventListener('keydown', handleKeys);
        return () => window.removeEventListener('keydown', handleKeys);
    }, []);

    return (
        <div className="fixed inset-0 bg-white text-gray-900 font-sans select-none overflow-hidden">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 p-10 flex justify-between items-center z-50">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-black rounded-2xl flex items-center justify-center shadow-lg">
                        <Package size={18} className="text-white" />
                    </div>
                    <span className="font-black uppercase tracking-tighter text-sm">Find-X / LFMS</span>
                </div>
                <div className="flex items-center gap-8">
                    <div className="text-[10px] font-black text-gray-300 uppercase tracking-[0.4em]">
                        {currentSlide + 1} / {slides.length}
                    </div>
                </div>
            </div>

            {/* Slide Viewer */}
            <div className="w-full h-full relative">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={currentSlide}
                        initial={{ opacity: 0, scale: 0.95, filter: 'blur(10px)' }}
                        animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, scale: 1.05, filter: 'blur(10px)' }}
                        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                        className="w-full h-full flex flex-col items-center justify-center p-12"
                    >
                        {slides[currentSlide].content}
                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Progress Bar */}
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gray-50">
                <motion.div
                    className="h-full bg-orange-600 shadow-[0_0_15px_rgba(234,88,12,0.5)]"
                    initial={false}
                    animate={{ width: `${((currentSlide + 1) / slides.length) * 100}%` }}
                    transition={{ duration: 0.5 }}
                />
            </div>

            {/* Navigation Controls */}
            <div className="absolute bottom-12 right-12 flex gap-4 z-50">
                <button
                    onClick={prevSlide}
                    className="p-5 bg-gray-100/50 backdrop-blur-md rounded-[2rem] border border-gray-200 hover:bg-white transition-all active:scale-90"
                >
                    <ChevronLeft size={24} />
                </button>
                <button
                    onClick={nextSlide}
                    className="p-5 bg-gray-900 text-white rounded-[2rem] hover:bg-orange-600 transition-all shadow-2xl active:scale-90"
                >
                    <ChevronRight size={24} />
                </button>
            </div>

            {/* Hint */}
            <div className="absolute bottom-12 left-12 p-4 hidden lg:block">
                <span className="text-[9px] font-black text-gray-300 uppercase tracking-[0.4em]">Use ARROW KEYS or SPACE to Navigate</span>
            </div>
        </div>
    );
};

export default LFMSPortfolio;

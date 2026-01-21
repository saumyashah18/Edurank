import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { Plus, BookOpen, Users, Settings, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import client from '../api/client';

interface Assessment {
    id: number;
    title: string;
    course_name: string;
    total_questions: number;
    is_finalized: boolean;
    transcripts_count: number;
}

export const Dashboard: React.FC = () => {
    const [assessments, setAssessments] = useState<Assessment[]>([]);
    const [, setLoading] = useState(true);
    const { user } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        fetchAssessments();
    }, []);

    const fetchAssessments = async () => {
        try {
            const res = await client.get('/professor/assessments');
            setAssessments(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: number) => {
        e.stopPropagation(); // Don't navigate when deleting
        if (!confirm("Are you sure you want to delete this assessment?")) return;

        try {
            await client.delete(`/professor/quiz/${id}`);
            setAssessments(prev => prev.filter(item => item.id !== id));
        } catch (err) {
            alert("Delete failed");
        }
    };

    const handleCreate = () => {
        navigate('/professor/create');
    };

    return (
        <Layout title={`Hello, Professor ${user?.displayName || ''}`}>
            <div className="flex-1 p-8 overflow-y-auto">
                <div className="max-w-7xl mx-auto">
                    <div className="flex items-center justify-between mb-10">
                        <div>
                            <h2 className="text-3xl font-bold text-gray-100">My Classrooms</h2>
                            <p className="text-gray-400 mt-1">Manage your course assessments and student performance.</p>
                        </div>
                        <Button icon={Plus} onClick={handleCreate}>New Assessment</Button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {assessments.map((item) => (
                            <div
                                key={item.id}
                                className="group relative bg-panel border border-border rounded-[28px] p-6 hover:border-accent/40 transition-all cursor-pointer shadow-sm hover:shadow-accent/5"
                                onClick={() => navigate(`/professor/manage/${item.id}`)}
                            >
                                <div className="flex items-start justify-between mb-6">
                                    <div className="w-12 h-12 bg-accent/10 rounded-2xl flex items-center justify-center text-accent">
                                        <BookOpen size={24} />
                                    </div>
                                    <div className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${item.is_finalized ? 'bg-green-400/10 text-green-400 border border-green-400/20' : 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20'
                                        }`}>
                                        {item.is_finalized ? 'Finalized' : 'Draft'}
                                    </div>
                                </div>

                                <h3 className="text-xl font-bold text-gray-100 mb-1">{item.title}</h3>
                                <p className="text-sm text-gray-400 mb-6">{item.course_name}</p>

                                <div className="flex items-center gap-6 pt-6 border-t border-border mt-auto">
                                    <div className="flex items-center gap-2 text-gray-400 text-xs font-medium">
                                        <Settings size={14} />
                                        {item.total_questions} Questions
                                    </div>
                                    <div className="flex items-center gap-2 text-gray-400 text-xs font-medium">
                                        <Users size={14} />
                                        {item.transcripts_count} Students
                                    </div>
                                </div>

                                <div className="absolute bottom-6 right-6 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={(e) => handleDelete(e, item.id)}
                                        className="w-8 h-8 rounded-full bg-red-400/10 text-red-400 flex items-center justify-center hover:bg-red-400 hover:text-white transition-all"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                    <div className="w-8 h-8 rounded-full bg-accent text-[#062e6f] flex items-center justify-center">
                                        <Plus size={18} />
                                    </div>
                                </div>
                            </div>
                        ))}

                        {/* Empty State / Add Blank */}
                        <div
                            onClick={handleCreate}
                            className="border-2 border-dashed border-border rounded-[28px] p-6 flex flex-col items-center justify-center gap-4 hover:border-accent/40 hover:bg-white/[0.02] transition-all cursor-pointer min-h-[220px]"
                        >
                            <div className="w-12 h-12 bg-panel rounded-full flex items-center justify-center text-gray-500">
                                <Plus size={24} />
                            </div>
                            <p className="text-sm font-medium text-gray-400">Create New Assessment</p>
                        </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

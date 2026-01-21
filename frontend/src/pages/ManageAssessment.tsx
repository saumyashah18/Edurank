import React, { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { FileDown, Users, User } from 'lucide-react';
import { useParams } from 'react-router-dom';
import client from '../api/client';

interface Participant {
    id: number;
    name: string;
    enrollment_id: string;
    completed_at: string;
}

export const ManageAssessment: React.FC = () => {
    const { quizId } = useParams();
    const [participants, setParticipants] = useState<Participant[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchParticipants();
    }, [quizId]);

    const fetchParticipants = async () => {
        try {
            const { data } = await client.get(`/professor/quiz/${quizId}/transcripts`);
            setParticipants(data);
        } catch (err) {
            console.error("Failed to fetch students", err);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async (transcriptId: number, enrollmentId: string) => {
        try {
            const response = await client.get(`/professor/transcript/${transcriptId}/export`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `transcript_${enrollmentId}.txt`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            alert("Export failed");
        }
    };

    return (
        <Layout title="Manage Assessment">
            <div className="flex-1 p-8 overflow-y-auto">
                <div className="max-w-5xl mx-auto">
                    <div className="flex items-center justify-between mb-10">
                        <div>
                            <h2 className="text-3xl font-bold text-gray-100">Student Responses</h2>
                            <p className="text-gray-400 mt-1">Review performance and export individual dialogue transcripts.</p>
                        </div>
                        <div className="flex items-center gap-3 bg-accent/10 px-6 py-3 rounded-2xl border border-accent/20">
                            <Users size={20} className="text-accent" />
                            <span className="font-bold text-accent">{participants.length} Students Joined</span>
                        </div>
                    </div>

                    <div className="bg-panel border border-border rounded-[32px] overflow-hidden shadow-xl">
                        <table className="w-full text-left">
                            <thead className="bg-white/[0.02] border-b border-border">
                                <tr>
                                    <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest">Student Information</th>
                                    <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest text-center">Enrollment ID</th>
                                    <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest text-center">Status</th>
                                    <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {participants.map((p) => (
                                    <tr key={p.id} className="hover:bg-white/[0.01] transition-colors group">
                                        <td className="px-8 py-6">
                                            <div className="flex items-center gap-4">
                                                <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-accent">
                                                    <User size={20} />
                                                </div>
                                                <span className="font-bold text-gray-100">{p.name}</span>
                                            </div>
                                        </td>
                                        <td className="px-8 py-6 text-center text-gray-400 font-mono text-sm">{p.enrollment_id}</td>
                                        <td className="px-8 py-6 text-center">
                                            <span className="px-3 py-1 bg-green-400/10 text-green-400 border border-green-400/20 rounded-full text-[10px] font-bold uppercase tracking-wider">
                                                Completed
                                            </span>
                                        </td>
                                        <td className="px-8 py-6 text-right">
                                            <Button
                                                variant="secondary"
                                                icon={FileDown}
                                                className="h-10 px-4 text-xs"
                                                onClick={() => handleExport(p.id, p.enrollment_id)}
                                            >
                                                Export TXT
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                                {participants.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={4} className="px-8 py-20 text-center text-gray-500">
                                            No students have submitted this assessment yet.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

import axios from 'axios';

const getApiBaseUrl = () => {
    if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
    const { protocol, hostname } = window.location;
    // In production (aissociate.ahduni.edu.in), use same origin with /api prefix (nginx proxies to backend)
    if (hostname === 'aissociate.ahduni.edu.in') return `${protocol}//${hostname}`;
    // Local dev fallback
    return `http://${hostname}:8000`;
};
const API_BASE_URL = getApiBaseUrl();
console.log("Current API Base URL:", API_BASE_URL);

const client = axios.create({
    baseURL: API_BASE_URL,
});

export const api = {
    get: (url: string, config?: any) => client.get(url, config),
    post: (url: string, data?: any, config?: any) => client.post(url, data, config),
    put: (url: string, data?: any, config?: any) => client.put(url, data, config),
    delete: (url: string, config?: any) => client.delete(url, config),

    // Voice Methods
    transcribeAudio: async (audioBlob: Blob) => {
        const formData = new FormData();
        // Backend expects 'file'
        formData.append('file', audioBlob, 'voice_input.webm');
        return client.post('/api/voice-chat/transcribe', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
    },

    synthesizeText: async (text: string) => {
        return client.post('/api/voice-chat/synthesize', { text }, {
            responseType: 'blob' // Important for playing audio
        });
    }
};

export default client;

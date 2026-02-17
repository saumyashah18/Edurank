import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
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

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
console.log("Current API Base URL:", API_BASE_URL);

const client = axios.create({
    baseURL: API_BASE_URL,
});

export default client;

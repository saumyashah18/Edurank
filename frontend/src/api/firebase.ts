import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
    apiKey: "AIzaSyCsWS3CnFvsZZwxkJWspI4ZW58FrYJzVdU",
    authDomain: "edurank-8bd63.firebaseapp.com",
    projectId: "edurank-8bd63",
    storageBucket: "edurank-8bd63.firebasestorage.app",
    messagingSenderId: "237521205977",
    appId: "1:237521205977:web:6ef49dfebb6aa6e12c5cc8",
    measurementId: "G-RVMRNBJCBC"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
export const analytics = typeof window !== 'undefined' ? getAnalytics(app) : null;

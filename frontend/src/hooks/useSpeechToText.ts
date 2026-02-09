import { useState, useEffect, useCallback, useRef } from 'react';

interface UseSpeechToTextOptions {
    onResult?: (text: string) => void;
    silenceTimeout?: number;
}

export const useSpeechToText = (options: UseSpeechToTextOptions = {}) => {
    const { onResult, silenceTimeout = 5000 } = options;
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [error, setError] = useState<string | null>(null);

    const recognitionRef = useRef<any>(null);
    const timeoutRef = useRef<any>(null);

    const stopListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
            setIsListening(false);
        }
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
    }, []);

    const resetTimeout = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            console.log('STT: Silence timeout reached, stopping...');
            stopListening();
        }, silenceTimeout);
    }, [silenceTimeout, stopListening]);

    const startListening = useCallback(() => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

        if (!SpeechRecognition) {
            setError('Speech recognition is not supported in this browser.');
            return;
        }

        if (!recognitionRef.current) {
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                setIsListening(true);
                setError(null);
                resetTimeout();
            };

            recognition.onresult = (event: any) => {
                let currentTranscript = '';
                for (let i = 0; i < event.results.length; i++) {
                    currentTranscript += event.results[i][0].transcript;
                }

                if (currentTranscript) {
                    setTranscript(currentTranscript);
                    if (onResult) {
                        onResult(currentTranscript);
                    }
                    resetTimeout();
                }
            };

            recognition.onerror = (event: any) => {
                console.error('STT Error:', event.error);
                setError(event.error);
                stopListening();
            };

            recognition.onend = () => {
                setIsListening(false);
            };

            recognitionRef.current = recognition;
        }

        try {
            recognitionRef.current.start();
        } catch (err) {
            console.error('STT Start Error:', err);
        }
    }, [onResult, resetTimeout, stopListening]);

    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        };
    }, []);

    return {
        isListening,
        transcript,
        error,
        startListening,
        stopListening,
    };
};

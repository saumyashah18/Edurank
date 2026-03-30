import { useState, useEffect, useCallback, useRef } from 'react';

interface UseSpeechToTextOptions {
    onResult?: (text: string) => void;
}

export const useSpeechToText = (options: UseSpeechToTextOptions = {}) => {
    const { onResult } = options;
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [interimTranscript, setInterimTranscript] = useState('');
    const [error, setError] = useState<string | null>(null);

    const recognitionRef = useRef<any>(null);
    const isListeningRef = useRef(false);
    const finalTranscriptRef = useRef('');

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
            recognition.lang = (import.meta as any).env.VITE_STT_LANGUAGE ?? 'en-US';

            recognition.onstart = () => {
                setIsListening(true);
                setError(null);
            };

            recognition.onresult = (event: any) => {
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcriptSeg = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscriptRef.current += transcriptSeg + ' ';
                    } else {
                        interim += transcriptSeg;
                    }
                }
                
                const fullTranscript = (finalTranscriptRef.current + interim).trim();
                setTranscript(fullTranscript);
                setInterimTranscript(interim);
                
                // Trigger onResult for every update (interim or final) for live feel
                if (onResult) {
                    onResult(fullTranscript);
                }
            };

            recognition.onerror = (event: any) => {
                console.error('STT Error:', event.error);
                setError(event.error);
                
                // Selective restart for common transient errors
                const retryErrors = ['no-speech', 'network', 'audio-capture'];
                if (isListeningRef.current && retryErrors.includes(event.error)) {
                    console.log(`STT: Retrying after error: ${event.error}`);
                    window.setTimeout(() => {
                        if (isListeningRef.current) {
                            try {
                                recognition.start();
                            } catch (e) {
                                // Already started or blocked
                            }
                        }
                    }, 1000);
                } else {
                    if (!retryErrors.includes(event.error)) {
                        isListeningRef.current = false;
                        setIsListening(false);
                    }
                }
            };

            recognition.onend = () => {
                // Auto-restart if we are still supposed to be listening
                if (isListeningRef.current) {
                    console.log('STT: Recognition ended unexpectedly, restarting...');
                    try {
                        recognition.start();
                    } catch (err) {
                        console.error('STT Restart Error:', err);
                    }
                } else {
                    setIsListening(false);
                }
            };

            recognitionRef.current = recognition;
        }

        // Reset state before starting
        finalTranscriptRef.current = '';
        setTranscript('');
        setInterimTranscript('');
        isListeningRef.current = true;

        try {
            recognitionRef.current.start();
        } catch (err) {
            console.error('STT Start Error:', err);
            // If already started, just ensure ref is correct
            isListeningRef.current = true;
            setIsListening(true);
        }
    }, [onResult]);

    const stopListening = useCallback(() => {
        isListeningRef.current = false;
        if (recognitionRef.current) {
            try {
                recognitionRef.current.stop();
            } catch (e) {
                // Ignore if already stopped
            }
        }
        setIsListening(false);
    }, []);

    useEffect(() => {
        return () => {
            isListeningRef.current = false;
            if (recognitionRef.current) {
                try {
                    recognitionRef.current.stop();
                } catch (e) {}
            }
        };
    }, []);

    return {
        isListening,
        transcript,
        interimTranscript,
        error,
        startListening,
        stopListening,
    };
};

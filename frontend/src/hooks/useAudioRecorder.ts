import { useState, useRef, useCallback } from "react";

export const useAudioRecorder = () => {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

    const startRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorder.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please check permissions.");
        }
    }, []);

    const stopRecording = useCallback((): Promise<Blob> => {
        return new Promise((resolve, reject) => {
            const mediaRecorder = mediaRecorderRef.current;
            if (!mediaRecorder) {
                return reject("No media recorder found");
            }

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
                chunksRef.current = [];
                setIsRecording(false);

                // Stop all tracks to release microphone
                mediaRecorder.stream.getTracks().forEach(track => track.stop());

                resolve(audioBlob);
            };

            mediaRecorder.stop();
        });
    }, []);

    return {
        isRecording,
        startRecording,
        stopRecording
    };
};

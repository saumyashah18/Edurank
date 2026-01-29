export const copyToClipboard = (text: string): boolean => {
    // 1. Try modern API first (only works in secure context)
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).catch(err => {
            console.error('Modern clipboard failed, using fallback', err);
        });
        // We return true immediately for modern API as it's almost always successful or failure is logged
        return true;
    }

    // 2. Fallback for non-HTTPS (like local IP 192.168.x.x)
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;

        // Ensure it's not visible but still reachable
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        textArea.style.top = "-9999px";
        textArea.setAttribute("readonly", ""); // Prevent mobile keyboard from popping up

        document.body.appendChild(textArea);
        textArea.select();
        textArea.setSelectionRange(0, 99999); // For mobile devices

        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful;
    } catch (err) {
        console.error('Fallback clipboard failed: ', err);
        return false;
    }
};

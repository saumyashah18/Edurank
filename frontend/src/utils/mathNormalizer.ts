import mathRules from '../../../shared/math_rules.json';

/**
 * Normalizes spoken mathematical expressions into symbolic notation 
 * using the shared rule set from math_rules.json.
 */
export const normalizeMathTranscript = (text: string): string => {
    if (!text) return '';
    
    let result = text.toLowerCase().trim();
    
    mathRules.rules.forEach((rule: any) => {
        const symbol = rule.symbol;
        const position = rule.position || 'infix';
        const isRegex = rule.regex || false;
        
        // Sort spoken triggers by length descending to match longest first
        let spoken_triggers = rule.spoken;
        if (!isRegex) {
            spoken_triggers = [...rule.spoken].sort((a: string, b: string) => b.length - a.length);
        }
        
        spoken_triggers.forEach((spoken: string) => {
            if (isRegex) {
                // Use spoken string directly as a regex pattern
                const regex = new RegExp(spoken, 'gi');
                // Replace $1 in the symbol with the first capture group $1 in JS
                const replacement = symbol.replace('$1', '$1');
                result = result.replace(regex, replacement);
            } else if (position === 'postfix') {
                // e.g., "x squared" -> "x²"
                const regex = new RegExp(`(\\w+)\\s+${escapeRegex(spoken)}\\b`, 'gi');
                result = result.replace(regex, `$1${symbol}`);
            } else if (position === 'prefix') {
                // e.g., "square root of x" -> "√x"
                const regex = new RegExp(`\\b${escapeRegex(spoken)}\\s+(\\w+)`, 'gi');
                result = result.replace(regex, `${symbol}$1`);
            } else {
                // infix or simple substitution
                const regex = new RegExp(`\\b${escapeRegex(spoken)}\\b`, 'gi');
                result = result.replace(regex, symbol);
            }
        });
    });
    
    return cleanSpacing(result);
};

/**
 * Escapes special characters for use in a regular expression.
 */
function escapeRegex(text: string) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Cleans up mathematical notation spacing for readability.
 */
function cleanSpacing(text: string): string {
    // Infix operators should have spaces around them
    const infixOps = ['=', '+', '−', '×', '/', '>', '<', '≥', '≤', '≈', '≠', '∴'];
    infixOps.forEach(op => {
        const regex = new RegExp(`\\s*${escapeRegex(op)}\\s*`, 'g');
        text = text.replace(regex, ` ${op} `);
    });
    
    // Remove extra spaces
    text = text.replace(/\s+/g, ' ').trim();
    
    // Units/symbols that shouldn't have preceding space, e.g., "x ²" -> "x²"
    text = text.replace(/\s+([²³^])/g, '$1');
    
    // Prefix symbols shouldn't have FOLLOWING space, e.g., "√ x" -> "√x"
    text = text.replace(/([√])\s+/g, '$1');
    
    return text;
}

(function (root) {
    function parseSubtitleCues(text) {
        const stamp = '(?:\\d+:)?\\d{2}:\\d{2}[.,]\\d{3}';
        const timing = new RegExp('^(' + stamp + ')\\s+-->\\s+(' + stamp + ')');
        const seconds = value => value.replace(',', '.').split(':').reduce((total, part) => total * 60 + Number(part), 0);
        return text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').split(/\n[ \t]*\n/).flatMap(block => {
            const lines = block.trim().split('\n');
            if (/^(NOTE|STYLE|REGION)(\s|$)/.test(lines[0])) return [];
            const index = lines.findIndex(line => timing.test(line));
            if (index < 0) return [];
            const match = lines[index].match(timing);
            const start = seconds(match[1]), end = seconds(match[2]);
            return end > start ? [{start, end, text: lines.slice(index + 1).join('\n')}] : [];
        });
    }
    function shiftCues(cues, base, delay) {
        return cues.filter(cue => cue.end + delay > base).map(cue => ({
            start: Math.max(0, cue.start + delay - base), end: cue.end + delay - base, text: cue.text
        }));
    }
    function subtitleTextAt(cues, time, delay) {
        const target = time - delay;
        let current = null;
        for (const cue of cues) {
            if (cue.start <= target && target < cue.end && (!current || cue.start >= current.start)) current = cue;
        }
        if (!current) return '';
        const entities = {'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'",'&nbsp;':' '};
        return current.text.replace(/<[^>]*>/g, '').replace(/&(?:amp|lt|gt|quot|apos|nbsp);/g, match => entities[match]);
    }
    const helpers = {parseSubtitleCues, shiftCues, subtitleTextAt};
    if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
    else root.PlayerHelpers = helpers;
})(typeof window !== 'undefined' ? window : globalThis);

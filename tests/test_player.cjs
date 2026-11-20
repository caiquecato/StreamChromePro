const assert = require('node:assert/strict');
const { parseSubtitleCues, shiftCues } = require('../assets/player_helpers.js');
const cues = parseSubtitleCues('\uFEFFWEBVTT\r\n\r\n1\r\n00:00:40.000 --> 00:00:55.000\r\nA\r\nB\r\n\r\n00:01:00.000 --> 00:01:05.000\nNext');
assert.deepEqual(cues, [{start:40, end:55, text:'A\nB'}, {start:60,end:65,text:'Next'}]);
assert.deepEqual(shiftCues(cues, 50, 0), [{start:0,end:5,text:'A\nB'}, {start:10,end:15,text:'Next'}]);
assert.deepEqual(shiftCues(cues, 56, 0), [{start:4,end:9,text:'Next'}]);
assert.deepEqual(shiftCues(cues, 0, 2)[0], {start:42,end:57,text:'A\nB'});
assert.deepEqual(cues[0], {start:40,end:55,text:'A\nB'});
assert.equal(parseSubtitleCues('1\n00:00:01,000 --> 00:00:03,000\nOla')[0].start, 1);
assert.deepEqual(parseSubtitleCues('<html>error</html>'), []);
console.log('7 verificacoes de parse e sincronizacao passaram.');

const {subtitleTextAt} = require('../assets/player_helpers.js');
const stacked = [
    {start:560,end:564,text:'Old dialogue'},
    {start:565,end:568,text:'Another old dialogue'},
    {start:581.08,end:583.389,text:'Há mais um problema.'},
    {start:584.11,end:585.419,text:'Puxa vida.'}
];
assert.equal(subtitleTextAt(stacked,582,0),'Há mais um problema.');
assert.equal(subtitleTextAt(stacked,584,0),'');
assert.equal(subtitleTextAt(stacked,585,1),'');
assert.equal(subtitleTextAt(stacked,583,1),'Há mais um problema.');
assert.equal(subtitleTextAt([{start:1,end:5,text:'<i>Uma fala</i> &amp; outra'}],2,0),'Uma fala & outra');
console.log('Legendas ativas, intervalos sem texto e atraso verificados.');

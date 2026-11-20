const assert=require('node:assert/strict');
const {displayMetrics,splitRelease}=require('../assets/presentation.js');
assert.deepEqual(displayMetrics({sourceWidth:1920,sourceHeight:1080,width:3580,height:994}),{width:1767,height:994,scale:994/1080,upscaling:false});
assert.equal(displayMetrics({sourceWidth:1920,sourceHeight:1080,width:1536,height:600,pixelRatio:2.5}).upscaling,true);
assert.equal(displayMetrics({sourceWidth:1920,sourceHeight:1080,width:1920,height:1080}).upscaling,false);
assert.equal(displayMetrics({sourceWidth:3840,sourceHeight:2160,width:1920,height:1080}).scale,.5);
assert.equal(displayMetrics({sourceWidth:0,sourceHeight:0,width:1920,height:1080}),null);
assert.deepEqual(splitRelease('OpenSubtitles | Movie <script>.srt'),{provider:'OpenSubtitles',release:'Movie <script>.srt'});
console.log('Object-fit letterboxing, display scaling, pixel density and untrusted release text verified.');

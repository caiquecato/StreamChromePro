const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../assets/index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map(),events=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',dataset:{},style:{setProperty(name,value){this[name]=value;}},options:[],checked:false,currentTime:0,
 setAttribute(){},removeAttribute(){},pause(){},load(){},play(){return Promise.resolve();},
 addEventListener(name,fn){if(id==='mainVideo')events.set(name,fn);},
 replaceChildren(...items){this.options=items;},add(option){this.options.push(option);}});return elements.get(id);}
let finishInspection,inspectCount=0;
const inspection=new Promise(resolve=>finishInspection=resolve);
const context=vm.createContext({document:{getElementById:element},window:{addEventListener(){}},console,Option:class{constructor(label,value){this.textContent=label;this.value=value;}setAttribute(){}},URLSearchParams,PlayerHelpers:require('../assets/player_helpers.js'),setTimeout,clearTimeout,
 fetch:async(url,options)=>{if(url.includes('/api/inspect')){inspectCount++;return inspection;}return {ok:true,json:async()=>url.includes('/api/playback')?{start:0}:{}};}});
context.document.documentElement={dataset:{}};context.document.body={dataset:{}};context.document.querySelectorAll=()=>[];
context.AppUI=require('../assets/appearance.js').createController({document:context.document,storage:null,i18n:require('../assets/i18n.js'),optionConstructor:context.Option});
vm.runInContext(script,context);
(async()=>{
 element('inputUrl').value='https://example.org/movie.mkv';
 const first=context.startPlayback(0),second=context.startPlayback(0);
 finishInspection({ok:true,json:async()=>({duration:12,filename:'Movie',audio_tracks:[{index:1,label:'Audio'}],subtitles:[]})});
 await Promise.all([first,second]);
 element('mainVideo').currentTime=3; context.updateTimelineDisplay();
 assert.equal(element('seekBarContainer').style['--progress'],'25%');
 assert.equal(element('seekBarFill').style.width,'25%');
 element('mainVideo').currentTime=0;
 assert.equal(inspectCount,1,'inspection should be shared');
 assert.equal(vm.runInContext('movieTotalDuration',context),12,'latest playback must receive inspection metadata');
 assert.equal(element('selectAudio').options.length,2);
 await context.startPlayback(5.3);
 events.get('loadedmetadata')();
 assert.equal(element('mainVideo').currentTime,5.3,'advance within the keyframe stream to the requested position');
 const previousTimeout=context.setTimeout;
 let idleCallback;
 context.setTimeout=callback=>{idleCallback=callback;return null;};
 element('controlsOverlay').classList={remove(){},add(){}};
 element('mainVideo').paused=false;element('mainVideo').ended=false;
 context.resetOverlayTimer();
 assert.equal(element('playerWrapper').dataset.cursorHidden,'false');
 idleCallback();
 assert.equal(element('playerWrapper').dataset.cursorHidden,'true');
 element('mainVideo').paused=true;context.resetOverlayTimer();
 assert.equal(element('playerWrapper').dataset.cursorHidden,'false');
 context.setTimeout=previousTimeout;
 console.log('Inspecao concorrente e posicao exata apos quadro-chave verificadas.');
})().catch(error=>{console.error(error);process.exitCode=1;});

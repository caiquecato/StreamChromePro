const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../assets/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
const track = {cues:[], addCue(cue){this.cues.push(cue);}, removeCue(cue){this.cues.splice(this.cues.indexOf(cue),1);}};
function element(id) {
    if (!elements.has(id)) elements.set(id, {id,value:'',textContent:'',dataset:{},style:{},options:[],checked:false,currentTime:2,setAttribute(){},
        addEventListener(){},addTextTrack(){return track;}, reportValidity(){return true;},
        replaceChildren(...options){this.options=[]; options.forEach(option=>this.add(option));},
        add(option){option.parent=this; this.options.push(option);},
        get selectedOptions(){return this.options.filter(option=>option.value===this.value);}});
    return elements.get(id);
}
class Option {
    constructor(text,value){this.textContent=text;this.value=value;}
    setAttribute(){}
    remove(){this.parent.options.splice(this.parent.options.indexOf(this),1); if(this.parent.value===this.value)this.parent.value='';}
}
const context = vm.createContext({document:{getElementById:element}, window:{addEventListener(){}},console,
    Option,VTTCue:class{constructor(start,end,text){this.startTime=start;this.endTime=end;this.text=text;}},
    URLSearchParams,PlayerHelpers:require('../assets/player_helpers.js'),setTimeout,clearTimeout,
    searchResponse:{subtitles:[],warnings:[]}, downloads:[],
    fetch:async url=>{ if(url.includes('/vtt')) context.downloads.push(url); return {ok:true,text:async()=> 'WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nChosen subtitle',json:async()=>url.includes('search')?context.searchResponse:{subdl:false,opensubtitles:false,opensubtitles_login:false}}; }});
context.document.documentElement={dataset:{}};context.document.body={dataset:{}};context.document.querySelectorAll=()=>[];
context.AppUI=require('../assets/appearance.js').createController({document:context.document,storage:null,i18n:require('../assets/i18n.js'),optionConstructor:context.Option});
vm.runInContext(script,context);
(async()=>{
    vm.runInContext("addSubtitle('old','Old subtitle',{provider:'SubDL',cues:[{start:1,end:10,text:'Old'}]}); selectSub.value='old'; activeSubtitleCues=[{start:1,end:10,text:'Old'}]; renderSubtitles();",context);
    assert.equal(element('subtitleText').textContent,'Old');
    await context.searchSubtitles();
    assert.equal(element('subtitleText').textContent,'','new search must clear removed selected subtitles');
    element('openUsername').value='test-user'; element('openPassword').value='test-pass';
    await context.saveProviderSettings();
    assert.equal(element('openUsername').value,'','saved login must not be sent again with an empty password');
    assert.equal(element('openPassword').value,'');
    context.searchResponse={subtitles:[{id:'new',label:'SubDL | Selected version',provider:'SubDL'}],warnings:[]};
    await context.searchSubtitles();
    assert.equal(context.downloads.length,0,'search must not download any subtitle automatically');
    element('searchResults').value='new';
    await context.openChosenSubtitle();
    assert.equal(context.downloads.length,1);
    assert.equal(element('subtitleText').textContent,'Chosen subtitle');
    element('mainVideo').currentTime=5; context.renderSubtitles();
    assert.equal(element('subtitleText').textContent,'');
    console.log('Selecao manual, ausencia de download automatico, estado e credenciais verificados.');
})().catch(error=>{console.error(error);process.exitCode=1;});

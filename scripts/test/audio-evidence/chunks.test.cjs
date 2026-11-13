// 仅验证实际导出器的有界传输；伪造文件不计作设备音频证据。
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),Module=require('node:module');
const ts=require(process.env.TYPESCRIPT_PATH || '/Applications/DevEco-Studio.app/Contents/plugins/codelinter/node_modules/typescript');
let data,position,opened,closed,packets,notices,failCopy,readGate,statSize,statCount,changed;
const original=Module._load;
Module._load=function(name,parent,main){
 if(name==='@kit.CoreFileKit')return {fileIo:{OpenMode:{READ_ONLY:0},stat:async()=>({size:statSize??data.length,mtime:changed&&statCount++>0?2:1}),open:async p=>{assert.match(p,/^\/owned\/(capture\.mp4|events\.jsonl)$/);opened++;return {fd:9};},read:async(fd,b)=>{if(readGate)await readGate;const n=Math.min(b.byteLength,37,data.length-position);new Uint8Array(b).set(data.subarray(position,position+n));position+=n;return n;},close:async()=>{closed++;}}};
 if(name==='@kit.BasicServicesKit')return {pasteboard:{MIMETYPE_TEXT_PLAIN:'text/plain',createData:(mime,text)=>{assert.equal(mime,'text/plain');return text;},getSystemPasteboard:()=>({setData:async text=>{if(failCopy)throw Error('COPY_FAILED');packets.push(JSON.parse(text));}})}};
 if(name==='@kit.ArkTS')return {util:{Base64Helper:class{encodeToStringSync(b){return Buffer.from(b).toString('base64');}}}};
 if(name==='@kit.CryptoArchitectureKit')return {cryptoFramework:{createMd:alg=>{assert.equal(alg,'SHA256');const h=crypto.createHash('sha256');return {update:async b=>h.update(b.data),digest:async()=>({data:new Uint8Array(h.digest())})};}}};
 return original.call(this,name,parent,main);
};
require.extensions['.ets']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,f);
const {EvidenceChunks}=require(path.resolve(__dirname,'../../../fixtures/normal-core-consumer/audio-evidence/EvidenceChunks.ets'));
function setup(size=600000){data=Buffer.alloc(size);for(let i=0;i<size;i++)data[i]=i%251;position=opened=closed=statCount=0;packets=[];notices=[];failCopy=changed=false;readGate=undefined;statSize=undefined;return new EvidenceChunks('/owned',m=>notices.push(m));}
const turn=()=>new Promise(r=>setImmediate(r));
(async()=>{
 let x=setup();await x.begin('capture',false);await x.next(false);await x.next(false);
 assert.deepEqual(packets.map(p=>p.index),[0,1,2]);assert(packets.every(p=>p.version==='spec017-evidence-v1'&&p.kind==='capture'&&p.chunks===3&&p.bytes===data.length));
 assert.deepEqual(Buffer.concat(packets.map(p=>Buffer.from(p.data,'base64'))),data);assert.equal(packets[0].sha256,crypto.createHash('sha256').update(data).digest('hex'));assert.equal(opened,1);assert.equal(closed,1);
 await assert.rejects(x.next(false),/CHUNK_END/);await x.repeat(false);assert.equal(packets[3].index,2);
 x=setup(262144);await x.begin('events',false);assert.equal(packets[0].chunks,1);await assert.rejects(x.next(false),/CHUNK_END/);
 for(const [kind,busy] of [['../secret',false],['capture',true]]){x=setup();await assert.rejects(x.begin(kind,busy));assert.equal(opened,0);assert.equal(packets.length,0);}
 for(const size of [0,16777217]){x=setup(1);statSize=size;await assert.rejects(x.begin('capture',false),/EVIDENCE_SIZE/);assert.equal(opened,0);}
 x=setup(20);statSize=30;await assert.rejects(x.begin('capture',false),/EVIDENCE_SHORT_READ/);assert.equal(closed,1);assert.equal(packets.length,0);
 x=setup(20);changed=true;await assert.rejects(x.begin('capture',false),/EVIDENCE_CHANGED/);assert.equal(closed,1);assert.equal(packets.length,0);
 x=setup();await x.begin('capture',false);failCopy=true;await assert.rejects(x.next(false),/COPY_FAILED/);failCopy=false;await x.next(false);assert.equal(packets[1].index,1,'复制失败不能跳过未收到的块');
 await assert.rejects(x.next(true),/CAPTURE_BUSY/);x.close();await assert.rejects(x.repeat(false),/EVIDENCE_CLOSED/);
 x=setup(20);let release;readGate=new Promise(r=>release=r);let pending=x.begin('events',false);await turn();await assert.rejects(x.begin('capture',false),/EXPORT_BUSY/);x.close();release();await assert.rejects(pending,/EVIDENCE_CLOSED/);assert.equal(closed,1);assert.equal(packets.length,0,'离页后不得开始迟到复制');
 console.log('PASS: 有界证据分块、完整性、重发、失败及取消回归');
})().catch(e=>{console.error(e);process.exitCode=1});
